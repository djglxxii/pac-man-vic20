#!/usr/bin/env python3
"""Measure the generic sprite kernel on identical inputs, with IRQs masked.

This excludes the sprite frontend and does not measure visible flicker. Use
performance.py, flicker.py and VICE captures for whole-game comparisons.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

from native import ROOT, Sim
from performance import CPU_HZ


def measure(prg):
    sim = Sim(prg)
    try:
        sim.cmd("run 500")
        sim.cmd("until frame_wait 100")

        def poke(name, value, width=1):
            for byte in range(width):
                address = sim.labels[name] + byte
                sim.cmd(f"poke ${address:x} {(value >> (8 * byte)) & 255}")

        rows = []
        for eyes in (False, True):
            atlas = sim.labels["arcade_eyes" if eyes else "arcade_sprites"]
            for code in range(8 if eyes else 64):
                poke("v_data", atlas + code * 12, 2)
                for shift in range(8):
                    poke("v_shift", shift)
                    for flip in range(4):
                        for flags in (1, 2, 3):
                            for column, y in ((0, 0), (7, 209)):
                                # Reload pointers/flip: the kernel may change
                                # scratch pointers and consumes its flip bit.
                                poke("v_addr", 0x1000 + column * 224 + y, 2)
                                poke("v_save", sim.labels["under"] + 8, 2)
                                poke("v_flip", flip)
                                poke("v_flags", flags)
                                result = sim.cmd("call bitmap_draw")[-1]
                                rows.append({
                                    "eyes": eyes, "code": code, "shift": shift,
                                    "flip": flip, "flags": flags,
                                    "column": column, "y": y,
                                    "cycles": int(result.split("cycles=")[1]),
                                })
        groups = defaultdict(list)
        for row in rows:
            groups["all"].append(row["cycles"])
            groups["full" if row["flags"] == 3 else "clipped"].append(row["cycles"])
            groups[f"shift-{row['shift']}"].append(row["cycles"])
        return {
            "cpu_hz": CPU_HZ,
            "prg_sha256": hashlib.sha256(prg.read_bytes()).hexdigest(),
            "method": "vicsim call bitmap_draw with IRQs masked; frontend excluded",
            "cases": len(rows),
            "groups": {name: {"min": min(v), "mean": sum(v) / len(v), "max": max(v)}
                       for name, v in groups.items()},
            "rows": rows,
        }
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path, default=ROOT / "build/pacman.prg")
    parser.add_argument("--output", type=Path, default=ROOT / "build/sprite-timing.json")
    args = parser.parse_args()
    report = measure(args.prg)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
