#!/usr/bin/env python3
"""Exercise the complete VIC frontend and all cutscenes; save review images."""
import json
from pathlib import Path
from PIL import Image
from native import Sim, ROOT

OUT = ROOT / "build/preview"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sim = Sim()
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
            sim.cmd("dump " + str(OUT / (name + ".ram")))
            p = OUT / (name + ".ppm")
            sim.cmd("shot " + str(p))
            Image.open(p).save(OUT / (name + ".png"))
            p.unlink()
            report["screens"].append(name)

        sim.cmd("run 1000")
        shot("attract")
        for i in range(16):
            sim.cmd(f"poke ${0x1d40+i:x} 165")
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
        for i in range(16):
            assert sim.peek(0x1D40 + i)[0] == 165, "C stack overwrote its lower guard"
        irq = int.from_bytes(sim.peek(0x314, 2), "little")
        assert irq == sim.labels["clock_irq"], "Sprite storage overwrote IRQ vector"
        sim.cmd("run 3000")
        report["long_run_ticks"] = int.from_bytes(sim.peek("arcade_ticks", 2), "little")
        report["irq_vector_intact"] = True
        report["stack_guard_intact"] = True
        (OUT / "native-validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        sim.close()


if __name__ == "__main__":
    main()
