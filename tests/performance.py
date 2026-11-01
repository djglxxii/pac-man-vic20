#!/usr/bin/env python3
"""Measure completed renders and logical ticks using emulated CPU cycles."""
import argparse
import json
from pathlib import Path
from native import Sim, ROOT

CPU_HZ = 1022727


def wait(sim, address, predicate, limit=3000):
    for _ in range(limit):
        if predicate(sim.peek(address)[0]):
            return
        sim.cmd("run 1")
    raise RuntimeError(f"Performance setup timed out at ${address:04x}")


def start_game(sim):
    sim.cmd("run 1000")
    sim.cmd("key 5")
    sim.cmd("run 30")
    sim.cmd("key -")
    sim.cmd("run 60")
    sim.cmd("key 1")
    sim.cmd("run 80")
    sim.cmd("key -")
    wait(sim, 0xE00, lambda v: v == 3)
    wait(sim, 0xE04, lambda v: v == 3)
    sim.cmd("run 30")


def measure(scene, output, frames):
    sim = Sim()
    try:
        if scene == "attract-chase":
            sim.cmd("run 1000")
            wait(sim, 0xE02, lambda v: 30 <= v < 35)
        else:
            start_game(sim)
            if scene == "frightened":
                for address, value in (
                    (0xA6, 1),
                    (0xA7, 1),
                    (0xA8, 1),
                    (0xA9, 1),
                    (0xAA, 1),
                    (0xCB, 0xD0),
                    (0xCC, 2),
                    (0xC9, 0),
                    (0xCA, 0),
                ):
                    sim.cmd(f"poke ${address:x} {value}")
            elif scene == "intermission":
                sim.cmd("poke $e13 1")
                sim.cmd("poke $e0e 244")
                wait(sim, 0xE06, lambda v: v == 4)
            elif scene == "board-transition":
                sim.cmd("poke $e0e 244")
        sim.cmd("until frame_wait 100")
        start_state = list(sim.peek(0xE00, 9))
        start_board = sim.peek(0xE13)[0]
        first_tick = int.from_bytes(sim.peek("arcade_ticks", 2), "little")
        first_cycle = int(sim.cmd("stats")[0].split()[1])
        trace = output / (scene + ".trace")
        sim.cmd("profile reset")
        sim.cmd("trace " + str(trace))
        sim.cmd(f"run {frames}")
        sim.cmd("trace off")
        last_cycle = int(sim.cmd("stats")[0].split()[1])
        last_tick = int.from_bytes(sim.peek("arcade_ticks", 2), "little")
        sim.cmd("profile " + str(output / (scene + ".profile")))
        elapsed = (last_cycle - first_cycle) / CPU_HZ
        events = [
            (int(c), kind) for c, kind in map(str.split, trace.read_text().splitlines())
        ]
        begins = [c for c, k in events if k == "begin"]
        ends = [c for c, k in events if k == "end"]
        intervals = sorted((b - a) * 1000 / CPU_HZ for a, b in zip(ends, ends[1:]))
        durations = []
        begin = None
        for cycle, kind in events:
            if kind == "begin":
                begin = cycle
            elif kind == "end" and begin is not None:
                durations.append((cycle - begin) * 1000 / CPU_HZ)
                begin = None
        return {
            "scene": scene,
            "seconds": round(elapsed, 4),
            "completed_renders": len(ends),
            "fps": round(len(ends) / elapsed, 2),
            "logic_hz": round(((last_tick - first_tick) & 65535) / elapsed, 2),
            "render_ms_mean": round(sum(durations) / len(durations), 2),
            "render_ms_max": round(max(durations), 2),
            "frame_interval_ms_p95": round(
                intervals[int((len(intervals) - 1) * 0.95)], 2
            ),
            "frame_interval_ms_max": round(max(intervals), 2),
            "start_state": start_state,
            "end_state": list(sim.peek(0xE00, 9)),
            "start_board": start_board,
            "end_board": sim.peek(0xE13)[0],
            "video_frames": frames,
        }
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="build/performance/current")
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument(
        "--scenes",
        nargs="+",
        choices=(
            "play",
            "frightened",
            "attract-chase",
            "intermission",
            "board-transition",
        ),
        default=(
            "play",
            "frightened",
            "attract-chase",
            "intermission",
            "board-transition",
        ),
    )
    args = parser.parse_args()
    if args.frames < 30:
        parser.error("--frames must be at least 30")
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    report = {
        "cpu_hz": CPU_HZ,
        "video_frames_per_sample": args.frames,
        "samples": [
            measure(
                scene,
                output,
                max(360, args.frames) if scene == "board-transition" else args.frames,
            )
            for scene in args.scenes
        ],
    }
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
