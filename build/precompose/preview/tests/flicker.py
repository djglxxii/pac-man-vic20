#!/usr/bin/env python3
"""Measure actor erase-to-paint windows without instrumenting the guest PRG.

This observes CPU work, not exact VIC pixel fetches. Use VICE raster captures
to assess the resulting appearance; a lower FPS alone cannot prove less flicker.
"""
import argparse
import hashlib
import json
from pathlib import Path

from native import ROOT, Sim
from performance import CPU_HZ, start_game, wait


def measure(scene, output, frames, prg=None):
    sim = Sim(prg)
    try:
        if scene == "attract-chase":
            sim.cmd("run 1000")
            wait(sim, 0xE02, lambda value: value == 34)
        else:
            start_game(sim)
            if scene == "frightened":
                for address, value in ((0xA6, 1), (0xA7, 1), (0xA8, 1),
                                       (0xA9, 1), (0xAA, 1), (0xCB, 0xD0),
                                       (0xCC, 2), (0xC9, 0), (0xCA, 0)):
                    sim.cmd(f"poke ${address:x} {value}")
            elif scene == "intermission":
                sim.cmd("poke $e13 1")
                sim.cmd("poke $e0e 244")
                wait(sim, 0xE06, lambda value: value == 4)
        sim.cmd("until frame_wait 100")
        for routine, name in (("bitmap_draw", "draw"),
                              ("bitmap_draw_ghost", "ghost")):
            sim.cmd(f"watch {routine} {name}")
        trace = output / f"{scene}.trace"
        start_cycle = int(sim.cmd("stats")[0].split()[1])
        sim.cmd(f"trace {trace}")
        sim.cmd(f"run {frames}")
        sim.cmd("trace off")
        seconds = (int(sim.cmd("stats")[0].split()[1]) - start_cycle) / CPU_HZ
        erased = {}
        painting = None
        gaps = []
        render = None
        render_count = 0
        erase_count = 0
        shadow_erases = 0
        publication = None
        publications = []
        for line in trace.read_text().splitlines():
            cycle, event = line.split()
            cycle = int(cycle)
            if event == "begin":
                erased.clear()
                render = cycle
            elif event == "end":
                render_count += 1
                render = None
            elif event == "publish-begin":
                publication = cycle
            elif event == "publish-end" and publication is not None:
                publications.append(cycle - publication)
                publication = None
            elif render is not None and event.startswith("shadow-"):
                if event.endswith("-erase"):
                    shadow_erases += 1
            elif render is not None and event.startswith("actor-"):
                _, actor, action = event.split("-")
                actor = int(actor)
                if action == "erase":
                    erase_count += 1
                    erased[actor] = cycle
                else:
                    painting = actor
            elif event in ("draw-end", "ghost-end") and painting is not None:
                if painting in erased:
                    start = erased.pop(painting)
                    gaps.append({"actor": painting, "cycles": cycle - start,
                                 "erase_raster_line": (start // 65) % 261,
                                 "paint_raster_line": (cycle // 65) % 261})
                painting = None
        if not (gaps or publications) or not render_count:
            raise AssertionError(f"No complete actor updates in {scene}")
        durations = sorted(gap["cycles"] * 1000 / CPU_HZ for gap in gaps)
        commits = sorted(cycles * 1000 / CPU_HZ for cycles in publications)
        def mean(values):
            return round(sum(values) / len(values), 3) if values else None
        def percentile(values, fraction):
            return round(values[int((len(values)-1)*fraction)], 3) if values else None
        (output / f"{scene}-actors.json").write_text(json.dumps(gaps, indent=2) + "\n")
        return {"scene": scene, "completed_renders": render_count,
                "seconds": round(seconds, 4), "actor_erases": erase_count,
                "actor_updates": len(gaps),
                "shadow_actor_erases": shadow_erases,
                "composed_transactions": len(commits),
                "shadow_erase_fraction": round(shadow_erases / (erase_count + shadow_erases), 4)
                    if erase_count + shadow_erases else 0,
                "publish_ms_mean": mean(commits),
                "publish_ms_p95": percentile(commits, .95),
                "publish_ms_max": round(max(commits), 3) if commits else None,
                "actor_window_ms_per_second": round(sum(durations) / seconds, 2),
                "erase_to_paint_ms_mean": mean(durations),
                "erase_to_paint_ms_p95": percentile(durations, .95),
                "erase_to_paint_ms_max": round(max(durations), 3) if durations else None}
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="build/flicker/current")
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--prg", type=Path, help="Measure a saved PRG and its sibling .lbl")
    args = parser.parse_args()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    report = {"cpu_hz": CPU_HZ, "video_frames_per_sample": args.frames,
              "metric": "Live bitmap_erase to painter return; shadow publication measured separately",
              "prg_sha256": hashlib.sha256((args.prg or ROOT / "build/pacman.prg").read_bytes()).hexdigest(),
              "samples": [measure(scene, output, args.frames, args.prg) for scene in
                          ("play", "frightened", "attract-chase", "intermission")]}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
