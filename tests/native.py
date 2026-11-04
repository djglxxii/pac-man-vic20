#!/usr/bin/env python3
"""Execute the built 6502 PRG and compare complete logical ticks to the ROM."""
import subprocess
import os
import unittest
from pathlib import Path
from arcade import Runner, compare, BUILD, WORK, ROOT
DEFAULT_PRG = Path(os.environ.get("PACMAN_PRG", ROOT / "build/pacman.prg")).resolve()


class Sim:
    def __init__(self, prg=None):
        prg = Path(prg).resolve() if prg is not None else DEFAULT_PRG
        self.prg = prg
        self.native_binary = (BUILD / "pacman-native.bin" if prg == ROOT / "build/pacman.prg"
                              else prg.with_name("pacman-native.bin"))
        self.labels = {
            p[2][1:]: int(p[1], 16)
            for line in prg.with_suffix(".lbl").read_text().splitlines()
            if len(p := line.split()) == 3
        }
        self.p = subprocess.Popen(
            [
                str(ROOT / "tools/vicsim/vicsim"),
                str(prg),
                "loader_start",
                "-",
                str(prg.with_suffix(".lbl")),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

    def cmd(self, s):
        self.p.stdin.write(s + "\nsync\n")
        self.p.stdin.flush()
        out = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("6502 simulator exited: " + self.p.stderr.read())
            if line.startswith("ok "):
                return out
            out.append(line.strip())

    def peek(self, addr, n=1):
        addr = self.labels.get(addr, addr)
        return bytes(
            int(v, 16)
            for v in self.cmd(f"peek ${addr:x} {n}")[-1].split(":")[1].split()
        )

    def dump(self):
        p = WORK / "vic.ram"
        self.cmd("dump " + str(p))
        return p.read_bytes()

    def finish_background(self):
        """Drain bounded slices for tests comparing a settled background."""
        costs = []
        for _ in range(1024):
            if not self.peek("full_dirty")[0]:
                return costs
            result = self.cmd("call video_rebuild")[-1]
            costs.append(int(result.split("cycles=")[1]))
        raise AssertionError("Background rebuild did not converge")

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.write("quit\n")
            self.p.stdin.flush()
            self.p.wait(timeout=3)
        self.p.stdin.close()
        self.p.stdout.close()
        self.p.stderr.close()


class NativeParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        if not (WORK / "game.ram").exists():
            raise RuntimeError("Run tests/arcade.py first")
        cls.game = (WORK / "game.ram").read_bytes()
        cls.ref = Runner("oracle")
        cls.ref.cmd("run 600")
        cls.sim = Sim()
        cls.sim.cmd("run 500")

    @classmethod
    def tearDownClass(cls):
        cls.ref.close()
        cls.sim.close()

    def load(self, patch=None):
        data = bytearray(self.game)
        for a, v in (patch or {}).items():
            if isinstance(v, int):
                data[a] = v
            else:
                data[a : a + len(v)] = v
        p = WORK / "native-fixture.ram"
        p.write_bytes(data)
        self.ref.load(p)
        self.sim.cmd("until frame_wait 100")
        (WORK / "vic-video.bin").write_bytes(data[0x4000:0x4800])
        (WORK / "vic-state.bin").write_bytes(data[0x4C00:0x5000])
        self.sim.cmd(f"load $0400 {WORK}/vic-video.bin")
        self.sim.cmd(f"load $0c00 {WORK}/vic-state.bin")
        (WORK / "flags.bin").write_bytes(data[0x4DA0:0x4E00])
        self.sim.cmd(f"load $00a0 {WORK}/flags.bin")
        self.sim.cmd("joy -")
        (WORK / "vic-io.bin").write_bytes(data[0x5000:0x5100])
        self.sim.cmd(f"load $1c40 {WORK}/vic-io.bin")
        self.base = int.from_bytes(self.sim.peek("arcade_ticks", 2), "little")

    def trace(self, count, inputs=None):
        for i in range(count):
            if inputs and i in inputs:
                joy, byte = inputs[i]
                self.sim.cmd("joy " + joy)
                self.ref.cmd(f"input {byte:x} ff")
            self.ref.cmd("run 1")
            self.sim.cmd("tick " + str((self.base + i + 1) & 65535))
            vic = self.sim.dump()
            original = self.ref.dump()
            mapped = bytearray(original)
            mapped[0x4000:0x4800] = vic[0x400:0xC00]
            mapped[0x4C00:0x4F00] = vic[0xC00:0xF00]
            mapped[0x4DA0:0x4E00] = vic[0xA0:0x100]
            mapped[0x5040:0x5060] = vic[0x1C80:0x1CA0]
            d = compare(original, mapped)
            if d:
                self.fail(f"6502 logical tick {i+1}\n" + "\n".join(d[:15]))

    def test_01_6502_movement_turns_and_score(self):
        self.load()
        self.trace(
            600,
            {
                0: ("-", 255),
                80: ("U", 254),
                180: ("R", 251),
                260: ("D", 247),
                380: ("L", 253),
                480: ("U", 254),
            },
        )

    def test_02_6502_frightened_rng(self):
        self.load(
            {0x4DA6: 1, 0x4DA7: b"\x01" * 4, 0x4DCB: b"\xd0\x02", 0x4DC9: b"\x00\x00"}
        )
        self.trace(300, {0: ("-", 255), 100: ("U", 254), 200: ("R", 251)})

    def test_03_build_memory_limits(self):
        # Native code and data must stay within the five real expansion blocks.
        # BLK1-3 + BLK5, followed by the temporary $0400-$07ff boot image.
        self.assertEqual(len(self.sim.native_binary.read_bytes()), 33792)
        p = self.sim.prg.read_bytes()
        self.assertEqual(p[:2], b"\x01\x12")
        self.assertLessEqual(0x1201 + len(p) - 2, 0x8000)

    def test_04_square_table_equivalence(self):
        import re

        source = (BUILD / "rom.c").read_text()
        s = re.search(r"arcade_squares.*?= \{(.*?)\};", source, re.S)[1]
        table = [int(v) for v in s.split(",") if v.strip()]
        self.assertEqual(len(table), 128)
        for n in range(256):
            self.assertEqual(
                (table[n & 127] + (((n & 127) << 8) + 0x4000 if n & 128 else 0))
                & 65535,
                n * n,
            )

    def test_05_exact_audio_divider_boundaries(self):
        frequencies = {1, 65535, 43000, 43001}
        for divisor in range(2, 128):
            boundary = 87272 // (2 * divisor - 1)
            frequencies.update((boundary - 1, boundary, boundary + 1))
        for frequency in sorted(frequencies):
            line = self.sim.cmd(f"call audio_divider {frequency&255} {frequency>>8}")[
                -1
            ]
            actual = int(line.split()[1], 16)
            expected = 255 - min(127, max(1, (43636 + frequency // 2) // frequency))
            self.assertEqual(actual, expected, f"frequency {frequency}")

    def test_06_audio_converter_registers(self):
        import random

        rng = random.Random(96000)
        shifts = (0, 0, 1, 0, 3, 4, 0, 1)
        for case in range(160):
            registers = bytearray(rng.randrange(16) for _ in range(32))
            for offset in (16, 22, 27):
                step = rng.randrange(1, 12000)
                for nibble in range(4):
                    registers[offset + nibble] = (step >> (nibble * 4)) & 15
            registers[20] = 1 if case % 17 == 0 else 0
            enabled = case % 7 != 0
            path = WORK / "sound.bin"
            path.write_bytes(registers)
            self.sim.cmd(f"load $1c80 {path}")
            self.sim.cmd(f"poke $1c41 {int(enabled)}")
            self.sim.cmd("call audio_update")
            actual = self.sim.peek(0x900A, 5)
            expected = [0, 0, 0, 0, 0]
            for voice, (offset, wave, port, bias) in enumerate(
                ((16, 5, 0, 0), (22, 10, 2, 2), (27, 15, 1, 3))
            ):
                volume = registers[offset + (5 if voice == 0 else 4)] & 15
                expected[4] = max(expected[4], volume) if enabled else 0
                if volume and enabled:
                    frequency = sum(
                        (registers[offset + n] & 15) << (n * 4) for n in range(4)
                    )
                    if voice == 0 and registers[20] & 15:
                        frequency = 65535
                    frequency = min(
                        65535, frequency << (shifts[registers[wave] & 7] + bias)
                    )
                    if frequency:
                        expected[port] = 255 - min(
                            127, max(1, (43636 + frequency // 2) // frequency)
                        )
            self.assertEqual(list(actual), expected, f"sound case {case}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
