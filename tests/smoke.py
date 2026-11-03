#!/usr/bin/env python3
"""Exercise the complete VIC frontend and all cutscenes; save review images."""
import json
import argparse
from pathlib import Path
from PIL import Image
from native import Sim, ROOT

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prg", type=Path)
    parser.add_argument("--output", default="build/preview")
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    sim = Sim(args.prg)
    report = {"screens": []}
    try:

        def wait(addr, predicate, limit=2500):
            for n in range(0, limit, 10):
                value = sim.peek(addr)
                if predicate(value):
                    return
                sim.cmd("run 10")
            raise AssertionError(
                f"VIC state ${addr:04x} did not reach requested phase: {value.hex()}"
            )

        def shot(name):
            sim.cmd("until frame_wait 100")
            if "__mc_shift_size" in sim.labels:
                tables = (ROOT / "build/multicolour-game/shifted-data.bin").read_bytes()
                tables += (ROOT / "build/multicolour-game/shifted-tails.bin").read_bytes()
                assert sim.peek(0x1d40, len(tables)) == tables, "Graphics tables corrupted"
            if "__beam_code_size" in sim.labels:
                load, size = sim.labels['__beam_code_load'], sim.labels['__beam_code_size']
                raw = (ROOT / 'build/beam-follow/pacman-native.bin').read_bytes()
                code = raw[0x8000 + load - 0x400:0x8000 + load - 0x400 + size]
                assert sim.peek(sim.labels['__beam_code_start'], size) == code, 'Beam helper corrupted'
            sim.cmd("dump " + str(out / (name + ".ram")))
            p = out / (name + ".ppm")
            sim.cmd("shot " + str(p))
            Image.open(p).save(out / (name + ".png"))
            p.unlink()
            report["screens"].append(name)
            report.setdefault("stack_by_scene", {})[name] = json.loads(sim.cmd("stack")[0])

        sim.cmd("stack reset")
        sim.cmd("run 1000")
        shot("attract")
        stack_bottom = sim.labels.get("__stack_bottom", 0x1d40)
        for i in range(16):
            sim.cmd(f"poke ${stack_bottom+i:x} 165")
        sim.cmd("key 5")
        sim.cmd("run 30")
        sim.cmd("key -")
        sim.cmd("run 60")
        shot("credits")
        sim.cmd("key 1")
        sim.cmd("run 80")
        sim.cmd("key -")
        wait(0xE00, lambda s: s[0] == 3)
        wait(0xE04, lambda s: s[0] == 3)
        sim.cmd("run 30")
        shot("maze")
        tick0 = int.from_bytes(sim.peek("arcade_ticks", 2), "little")
        sim.cmd("run 180")
        tick1 = int.from_bytes(sim.peek("arcade_ticks", 2), "little")
        elapsed = (tick1 - tick0) & 65535
        expected = 180 * 65 * 261 / 16875
        assert abs(elapsed - expected) <= 3, (elapsed, expected)
        report["clock"] = {
            "video_frames": 180,
            "arcade_ticks": elapsed,
            "expected": expected,
        }
        sim.cmd("poke $e0e 70")
        sim.cmd("run 30")
        assert sim.peek(0xD4)[0] != 0
        shot("cherry")
        for level, scene, target, title in (
            (1, 0xE06, 5, "intermission-1"),
            (4, 0xE07, 6, "intermission-2"),
            (8, 0xE08, 3, "intermission-3"),
        ):
            wait(0xE04, lambda s: s[0] == 3)
            sim.cmd(f"poke $e13 {level}")
            sim.cmd("poke $e0e 244")
            wait(scene, lambda s: s[0] == target, limit=3000)
            sim.cmd("run 35")
            shot(title)
            wait(0xE13, lambda s: s[0] == level + 1, limit=2500)
            wait(0xE04, lambda s: s[0] == 3)
        sim.cmd("run 3000")
        for i in range(16):
            assert sim.peek(stack_bottom + i)[0] == 165, "C stack overwrote its lower guard"
        irq = int.from_bytes(sim.peek(0x314, 2), "little")
        assert irq == sim.labels["clock_irq"], "Sprite storage overwrote IRQ vector"
        report["long_run_ticks"] = int.from_bytes(sim.peek("arcade_ticks", 2), "little")
        report["stack"] = json.loads(sim.cmd("stack")[0])
        report["boot"] = json.loads(sim.cmd("boot")[0])
        report["irq_vector_intact"] = True
        report["stack_guard_intact"] = True
        report["software_stack_reserved"] = 0x2000 - stack_bottom
        if "__mc_shift_size" in sim.labels:
            report["shifted_tables_intact_all_scenes"] = True
        if "__beam_code_size" in sim.labels:
            report['beam_helper_intact_all_scenes'] = True
        (out / "native-validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        sim.close()


if __name__ == "__main__":
    main()
