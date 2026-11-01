#!/usr/bin/env python3
"""Behavioral regressions against the user's unmodified original Z80 ROMs."""
import random
import re
import selectors
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build/arcade"
WORK = BUILD / "tests"


class Runner:
    def __init__(self, name):
        self.name = name
        self.p = subprocess.Popen(
            [str(BUILD / name), str(BUILD / "program-rom.bin")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.select = selectors.DefaultSelector()
        self.select.register(self.p.stdout, selectors.EVENT_READ)

    def cmd(self, s):
        self.p.stdin.write(s + "\n")
        self.p.stdin.flush()
        lines = []
        while True:
            if not self.select.select(10):
                raise RuntimeError(f"{self.name} timeout: {s}")
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError(f"{self.name} exited {self.p.poll()}: {s}")
            if line.startswith("ok "):
                return line.strip()
            lines.append(line)

    def dump(self):
        path = WORK / (self.name + ".ram")
        self.cmd("dump " + str(path))
        return path.read_bytes()

    def load(self, path):
        self.cmd("input ff ff")
        return self.cmd("load " + str(path))

    def close(self):
        if self.p.poll() is None:
            self.p.stdin.write("quit\n")
            self.p.stdin.flush()
            self.p.wait(timeout=3)
        self.select.close()
        try:
            self.p.stdin.close()
        except BrokenPipeError:
            pass
        self.p.stdout.close()


def compare(a, b):
    diff = []
    for i in (*range(0x4000, 0x4F00), *range(0x5040, 0x5060)):
        # Namco latches only four bits of each frequency/volume byte. Original Z80
        # rotates full bytes; the C translation keeps just the meaningful nibbles.
        mask = 15 if 0x4E8C <= i < 0x4E9C or 0x5040 <= i < 0x5060 else 255
        if a[i] & mask != b[i] & mask:
            diff.append(f"{i:04x}: ROM={a[i]:02x} native={b[i]:02x}")
    return diff


class ArcadeParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        cls.ref = Runner("oracle")
        cls.native = Runner("native")
        cls.ref.cmd("run 400")
        cls.title = cls.ref.dump()
        (WORK / "title.ram").write_bytes(cls.title)
        cls.ref.cmd("run 200")
        cls.ref.cmd("input df ff")
        cls.ref.cmd("run 12")
        cls.ref.cmd("input ff ff")
        cls.ref.cmd("run 30")
        cls.ref.cmd("input ff df")
        cls.ref.cmd("run 12")
        cls.ref.cmd("input ff ff")
        for _ in range(400):
            state = cls.ref.cmd("run 1")
            if "state=3/0/3 " in state:
                break
        else:
            raise AssertionError("Original ROM did not reach gameplay")
        cls.game = cls.ref.dump()
        (WORK / "game.ram").write_bytes(cls.game)

    @classmethod
    def tearDownClass(cls):
        cls.ref.close()
        cls.native.close()

    def load(self, data=None, patch=None):
        data = bytearray(self.game if data is None else data)
        for addr, value in (patch or {}).items():
            if isinstance(value, int):
                data[addr] = value
            else:
                data[addr : addr + len(value)] = value
        path = WORK / "fixture.ram"
        path.write_bytes(data)
        for attr in ("ref", "native"):
            runner = getattr(type(self), attr)
            if runner.p.poll() is not None:
                runner.close()
                setattr(
                    type(self), attr, Runner("oracle" if attr == "ref" else "native")
                )
        self.ref.load(path)
        self.native.load(path)

    def equal(self, label):
        a, b = self.ref.dump(), self.native.dump()
        d = compare(a, b)
        if d:
            self.fail(label + "\n" + "\n".join(d[:18]))
        return a

    def call(self, addr, b=0, a=0, hl=0, de=0):
        cmd = f"call {addr:x} {b:x} {a:x} {hl:x} {de:x}"
        self.ref.cmd(cmd)
        self.native.cmd(cmd)
        return self.equal(cmd)

    def ticks(self, n, label="trace", inputs=None):
        for tick in range(n):
            if inputs and tick in inputs:
                v = inputs[tick]
                self.ref.cmd(f"input {v:x} ff")
                self.native.cmd(f"input {v:x} ff")
            self.ref.cmd("run 1")
            self.native.cmd("run 1")
            self.equal(f"{label} tick {tick+1}")

    def test_01_original_maze_and_attract(self):
        self.assertEqual(sum(v == 0x10 for v in self.game[0x4000:0x4400]), 240)
        self.assertEqual(sum(v == 0x14 for v in self.game[0x4000:0x4400]), 4)
        self.load(self.title)
        self.ticks(1100, "character introductions and attract chase")
        for off, color in ((0x304, 1), (0x307, 3), (0x30A, 5), (0x30D, 7)):
            self.load()
            self.call(0x05BF, a=color, hl=0x4000 + off)

    def test_02_gameplay_and_turn_trace(self):
        self.load()
        self.ticks(600, "first life")
        self.load()
        self.ticks(
            650,
            "turn sequence",
            {
                0: 0xFE,
                73: 0xFD,
                114: 0xF7,
                211: 0xFB,
                300: 0xFE,
                413: 0xFD,
                484: 0xFF,
                560: 0xFB,
            },
        )

    def test_03_difficulty_and_fruit(self):
        for board in range(21):
            self.load(patch={0x4E13: board, 0x4E0A: bytes((0x68 + board, 0))})
            self.call(0x070E)
            for eaten, first in ((70, 0), (170, 1)):
                self.load(
                    patch={
                        0x4E13: board,
                        0x4E0E: eaten,
                        0x4E0C: first,
                        0x4E0D: 0,
                        0x4DD4: 0,
                    }
                )
                data = self.call(0x0EAD)
                self.assertNotEqual(data[0x4DD4], 0)
        for board in (21, 50, 254):
            self.load(patch={0x4E13: board, 0x4E0E: 70, 0x4E0C: 0, 0x4DD4: 0})
            self.call(0x0EAD)

    def test_04_ghost_targets_ties_and_upward_bug(self):
        rng = random.Random(1980)
        corridors = []
        for off in range(0x40, 0x3C0):
            if self.game[0x4000 + off] in (0x10, 0x14):
                corridors.append((32 + ((off - 64) & 31), 32 + ((off - 64) >> 5)))
        vectors = ((0, 255), (1, 0), (0, 1), (255, 0))
        for trial in range(100):
            pac = rng.choice(corridors)
            ghost = rng.choice(corridors)
            direction = trial % 4
            for g, addr in enumerate((0x2730, 0x276C, 0x27A9, 0x27F1)):
                self.load(
                    patch={
                        0x4DC1: trial % 2,
                        0x4DB0: (trial // 2) % 2,
                        0x4D39: bytes(pac),
                        0x4D1C: bytes(vectors[direction]),
                        0x4D0A + g * 2: bytes(ghost),
                        0x4D2C + g: rng.randrange(4),
                    }
                )
                self.call(addr)

    def test_05_frightened_random_sequence(self):
        self.load(patch={0x4DC9: b"\x00\x00", 0x4DAC: b"\x00" * 4})
        for i in range(200):
            for addr in (0x283B, 0x2865, 0x288F, 0x28B9):
                self.call(addr)

    def test_06_elroy_and_score(self):
        for left in (244, 21, 20, 19, 11, 10, 9, 1):
            for modes in ((0, 0), (1, 0), (1, 1)):
                self.load(patch={0x4E0E: 244 - left, 0x4DA3: 1, 0x4DB0: bytes(modes)})
                self.call(0x20D7)
        for score, high in (
            (0, 0),
            (90, 0),
            (9990, 1000),
            (12340, 19900),
            (999990, 999990),
            (100000, 200000),
        ):

            def bcd(n):
                return bytes(int(str(n // (100**i) % 100), 16) for i in range(3))

            for points in range(14):
                self.load(
                    patch={
                        0x4E80: bcd(score) + b"\x00",
                        0x4E88: bcd(high),
                        0x4E14: 3,
                        0x4E15: 2,
                    }
                )
                self.call(0x2A5A, points)

    def test_07_intermission_selection(self):
        for board in range(24):
            self.load(patch={0x4E13: board, 0x4E04: 32, 0x4E06: b"\x00" * 3})
            self.call(0x0A2C)

    def test_08_complete_intermission_traces(self):
        for board in (1, 4, 8):
            self.load(patch={0x4E13: board, 0x4E0E: 244})
            # Let the original ROM finish its flash/maze setup tasks first; they span
            # multiple Z80 frames. Compare the complete animation from a shared state.
            for _ in range(1500):
                state = self.ref.cmd("run 1")
                if "state=3/0/32 " in state:
                    break
            else:
                self.fail(f"ROM did not reach board {board+1} intermission")
            scene = self.ref.dump()
            self.load(scene)
            for tick in range(1600):
                self.ref.cmd("run 1")
                self.native.cmd("run 1")
                data = self.equal(f"intermission {board+1}, tick {tick+1}")
                if data[0x4E04] != 32:
                    break
            else:
                self.fail(f"intermission after board {board+1} did not finish")

    def test_10_lives_history_and_split_screen(self):
        for board in (0, 1, 6, 7, 8, 12, 17, 18, 19, 20, 254, 255):
            self.load(patch={0x4E13: board})
            self.call(0x2BEA)
        for lives in range(8):
            self.load(patch={0x4E13: 6})
            self.call(0x2BEA)
            self.call(0x2B4A, lives)

    def test_11_credits_and_two_player_start(self):
        for credits in (1, 2, 3, 9, 0x10, 0x99, 0xFF):
            for button in (0xDF, 0xBF):
                self.load(
                    patch={
                        0x4E00: 2,
                        0x4E03: 1,
                        0x4E6E: credits,
                        0x4E6B: 0 if credits == 255 else 1,
                    }
                )
                self.ref.cmd(f"input ff {button:x}")
                self.native.cmd(f"input ff {button:x}")
                self.call(0x061B)

    def test_12_death_sequence(self):
        self.load()
        for tick in range(1500):
            self.ref.cmd("run 1")
            self.native.cmd("run 1")
            data = self.equal(f"death tick {tick+1}")
            if data[0x4E04] == 4:
                self.assertEqual(data[0x4E14], 2)
                break
        else:
            self.fail("The original first life did not finish")

    def test_13_coin_debounce_and_queued_credits(self):
        for coins, credits in ((1, 1), (1, 2), (2, 1)):
            self.load(
                patch={
                    0x4E66: b"\x0f" * 3,
                    0x4E69: b"\x00\x00",
                    0x4E6B: coins,
                    0x4E6C: 0,
                    0x4E6D: credits,
                    0x4E6E: 0,
                }
            )
            # Two slots close together exercise the mechanical counter's queue.
            for inputs in (0x9F, 0x9F, 0xFF, 0xFF):
                self.ref.cmd(f"input {inputs:x} ff")
                self.native.cmd(f"input {inputs:x} ff")
                self.call(0x0267)
            for _ in range(32):
                self.call(0x02AD)
            self.assertEqual(self.ref.dump()[0x4E6E], 2 * credits // coins)

    def test_14_songs_effects_and_channel_priority(self):
        cases = []
        for addr, bits in ((0x4E9C, 2), (0x4EAC, 8), (0x4EBC, 6)):
            cases.extend(({addr: 1 << bit}, 0x2D0C) for bit in range(bits))
            cases.append(({addr: (1 << bits) - 1}, 0x2D0C))
        for song in (1, 2):
            cases.append(({addr: song for addr in (0x4ECC, 0x4EDC, 0x4EEC)}, 0x2CC1))
        for patch, routine in cases:
            self.load(patch={0x4E8C: bytes(0x70), **patch})
            for tick in range(192):
                self.call(0x01DC)
                self.call(routine)

    def test_15_attract_maze_demo(self):
        self.load(self.title)
        # Full-screen setup is asynchronous on the arcade CPU. Start the
        # comparison once its maze and task queue are complete.
        for _ in range(3000):
            self.ref.cmd("run 1")
            data = self.ref.dump()
            if (
                data[0x4E00:0x4E05] == b"\x01\x00\x23\x00\x03"
                and data[0x4C80:0x4C82] == data[0x4C82:0x4C84]
            ):
                break
        else:
            self.fail("The ROM did not reach the attract maze demonstration")
        self.load(data)
        for tick in range(6000):
            self.ref.cmd("run 1")
            self.native.cmd("run 1")
            data = self.equal(f"attract maze tick {tick+1}")
            if data[0x4E04] != 3:
                self.assertGreater(tick, 300)
                break
        else:
            self.fail("The ROM did not complete its maze demonstration")

    def test_09_rng_storage_bound(self):
        source = (BUILD / "rom.c").read_text()
        body = re.search(r"rom_random.*?= \{(.*?)\};", source, re.S)[1]
        packed = bytes(int(v, 16) for v in re.findall(r"0x[0-9a-f]+", body))
        rom = (BUILD / "program-rom.bin").read_bytes()
        address = 0
        self.assertGreaterEqual(len(packed) * 4, 4 * 4 * 360 * 2 // 8 + 16)
        for n in range(len(packed) * 4):
            address = (address * 5 + 1) & 8191
            self.assertEqual((packed[n // 4] >> ((n & 3) * 2)) & 3, rom[address] & 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
