#!/usr/bin/env python3
"""Compare compiled ghost updates to the Z80 ROM and measure identical inputs."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import unittest

from arcade import Runner, compare, WORK
from native import ROOT, Sim, DEFAULT_PRG


def fixtures(game):
    rng = random.Random(1017)
    patterns = [0, 0xFFFFFFFF, 0x55555555, 0xAAAAAAAA]
    patterns += [1 << bit for bit in range(32)]
    patterns += [rng.getrandbits(32) for _ in range(12)]
    modes = (
        ("normal", False, False, 0),
        ("frightened", True, False, 0),
        ("tunnel", False, True, 0),
        ("tunnel-frightened", True, True, 0),
        ("elroy-1", False, False, 1),
        ("elroy-2", False, False, 2),
        ("frightened-elroy-2", True, False, 2),
        ("tunnel-frightened-elroy-2", True, True, 2),
        ("in-house", False, False, 0),
        ("returning", False, False, 0),
        ("death-pause", False, False, 0),
    )
    for mode, edible, tunnel, elroy in modes:
        for pattern in patterns:
            data = bytearray(game)
            # Keep Pac-Man still while all four ghosts exercise the selected
            # speed mode. Compare every other game/screen/sound byte as usual.
            data[0x4D46:0x4D4E] = bytes(8)
            data[0x4D4E:0x4D86] = pattern.to_bytes(4, "little") * 14
            data[0x4D9D] = 255
            data[0x4DA0:0x4DA4] = bytes([mode != "in-house"]) * 4
            data[0x4DA4:0x4DA7] = bytes((0, mode == "death-pause", edible))
            data[0x4DA7:0x4DAB] = bytes([edible]) * 4
            data[0x4DAB:0x4DB0] = bytes((0,)) + bytes([mode == "returning"]) * 4
            data[0x4DB6:0x4DB8] = bytes((elroy >= 1, elroy == 2))
            # Prevent the ordinary pellet thresholds from enabling Elroy.
            data[0x4DBB:0x4DBD] = bytes(2)
            data[0x4E0E] = 0
            data[0x4DC5:0x4DC7] = bytes(2)
            data[0x4DCB:0x4DCD] = (120).to_bytes(2, "little")
            # The game's tunnel test reads palette RAM at each ghost's tile.
            data[0x4400:0x4800] = bytes([0x1B if tunnel else 0x10]) * 1024
            yield mode, pattern, data


class GhostParity(unittest.TestCase):
    prg = DEFAULT_PRG
    report = None

    def test_01_speed_masks_and_mode_priorities(self):
        game = (WORK / "game.ram").read_bytes()
        sim = Sim(self.prg)
        ref = Runner("oracle")
        rows = []
        try:
            sim.cmd("run 500")
            sim.cmd("until frame_wait 100")
            ref.cmd("run 600")
            for mode, pattern, data in fixtures(game):
                with self.subTest(mode=mode, pattern=f"{pattern:08x}"):
                    path = WORK / "g.ram"
                    path.write_bytes(data)
                    ref.load(path)
                    for address, name, payload in (
                        (0x0400, "gv.bin", data[0x4000:0x4800]),
                        (0x0C00, "gs.bin", data[0x4C00:0x5000]),
                        (0x00A0, "gf.bin", data[0x4DA0:0x4E00]),
                        (0x1C40, "gi.bin", data[0x5000:0x5100]),
                    ):
                        path = WORK / name
                        path.write_bytes(payload)
                        sim.cmd(f"load ${address:x} {path}")
                    for name in ("input0", "input1"):
                        sim.cmd(f"poke ${sim.labels[name]:x} 255")
                    ref.cmd("call 1017")
                    result = sim.cmd("call updateGhostStates_1017")[-1]
                    cycles = int(result.split("cycles=")[1])
                    vic, original = sim.dump(), ref.dump()
                    mapped = bytearray(original)
                    mapped[0x4000:0x4800] = vic[0x400:0xC00]
                    mapped[0x4C00:0x4F00] = vic[0xC00:0xF00]
                    mapped[0x4DA0:0x4E00] = vic[0xA0:0x100]
                    mapped[0x5040:0x5060] = vic[0x1C80:0x1CA0]
                    self.assertEqual(compare(original, mapped), [])
                    # Ensure the oracle actually reached each intended path.
                    if mode not in ("in-house", "returning", "death-pause"):
                        offsets = (0x4D4E if elroy_mode(mode) == 2 else
                                   0x4D52 if elroy_mode(mode) == 1 else 0x4D56,
                                   0x4D62, 0x4D6E, 0x4D7A)
                        for ghost, offset in enumerate(offsets):
                            if "tunnel" in mode:
                                offset = (0x4D5E, 0x4D6A, 0x4D76, 0x4D82)[ghost]
                            elif "frightened" in mode:
                                offset = (0x4D5A, 0x4D66, 0x4D72, 0x4D7E)[ghost]
                            rotated = ((pattern << 1) | (pattern >> 31)) & 0xFFFFFFFF
                            self.assertEqual(int.from_bytes(original[offset:offset + 4],
                                                            "little"), rotated)
                    rows.append({"mode": mode, "pattern": pattern, "cycles": cycles})
            groups = defaultdict(list)
            for row in rows:
                groups["all"].append(row["cycles"])
                groups[row["mode"]].append(row["cycles"])
            type(self).report = {
                "prg_sha256": hashlib.sha256(self.prg.read_bytes()).hexdigest(),
                "fixture_sha256": hashlib.sha256(game).hexdigest(),
                "method": "call updateGhostStates_1017 with IRQs masked; compare Z80 call $1017",
                "cases": len(rows),
                "groups": {name: {"min": min(v), "mean": sum(v) / len(v), "max": max(v)}
                           for name, v in groups.items()},
                "rows": rows,
            }
        finally:
            sim.close()
            ref.close()


def elroy_mode(mode):
    return 2 if "elroy-2" in mode else 1 if mode == "elroy-1" else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path, default=GhostParity.prg)
    parser.add_argument("--output", type=Path, help="Save per-case cycle measurements")
    args = parser.parse_args()
    GhostParity.prg = args.prg
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GhostParity)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(GhostParity.report, indent=2) + "\n")
        print(json.dumps({k: v for k, v in GhostParity.report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
