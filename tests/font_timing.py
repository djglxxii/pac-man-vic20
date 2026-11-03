#!/usr/bin/env python3
"""Measure isolated reward drawing on two archived native programs."""
import argparse
import hashlib
import json
from pathlib import Path

from native import ROOT, Sim

CPU_HZ = 1022727


def measure(prg):
    # Keep monitor filenames short: vicsim's command tokens are limited.
    work = Path("build/score-timing")
    work.mkdir(parents=True, exist_ok=True)
    sim = Sim(prg)
    try:
        sim.cmd("run 500")
        sim.cmd("until frame_wait 100")
        sim.cmd("call video_restore")
        path = work / "bg.bin"
        path.write_bytes(bytes([0x55]) * 3136)
        sim.cmd(f"load $1000 {path}")
        sim.cmd("poke full_dirty 0")
        sim.cmd("poke dirty_count 0")
        rows = []
        for slot in (2, 4, 6, 8):
            for code in range(40, 44):
                for shift in range(8):
                    attrs, positions = bytearray(16), bytearray(16)
                    attrs[slot:slot + 2] = bytes((code * 4, 24))
                    positions[slot:slot + 2] = bytes((239 - (slot <= 4) - 2 * (32 + shift), 168))
                    for address, payload in ((0xc20, attrs), (0xc30, positions)):
                        path = work / "actors.bin"
                        path.write_bytes(payload)
                        sim.cmd(f"load ${address:x} {path}")

                    def cost(routine):
                        return int(sim.cmd("call " + routine)[-1].split("cycles=")[1])

                    rows.append({"slot": slot, "code": code, "shift": shift,
                                 "draw": cost("video_sprites"),
                                 "steady": cost("video_refresh"),
                                 "erase": cost("video_restore")})
        return {
            "prg_sha256": hashlib.sha256(prg.read_bytes()).hexdigest(),
            "cases": len(rows),
            "cycles": {kind: {"min": min(row[kind] for row in rows),
                              "mean": sum(row[kind] for row in rows) / len(rows),
                              "max": max(row[kind] for row in rows)}
                       for kind in ("draw", "steady", "erase")},
            "rows": rows,
        }
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, default=ROOT / "build/pacman.prg")
    parser.add_argument("--output", type=Path, default=ROOT / "build/font-study/horizontal/score-timing.json")
    args = parser.parse_args()
    report = {"method": "Compiled 6502 calls with IRQs masked; identical isolated reward fixtures across four ghost slots, four values and eight shifts. Draw includes the full sprite frontend; steady is unchanged video_refresh; erase restores saved backgrounds.",
              "cpu_hz": CPU_HZ,
              "variants": {"stacked": measure(args.before), "horizontal": measure(args.after)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for kind in ("draw", "steady", "erase"):
        before, after = (report["variants"][name]["cycles"][kind]["mean"]
                         for name in ("stacked", "horizontal"))
        print(f"{kind}: {before:.1f} -> {after:.1f} cycles; {(after - before) * 1000 / CPU_HZ:+.3f} ms")


if __name__ == "__main__":
    main()
