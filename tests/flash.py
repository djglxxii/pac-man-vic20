#!/usr/bin/env python3
"""Check the VIC maze flash against full redraws and its actual clock."""
import json
import unittest
from PIL import Image

from native import Sim, ROOT
from performance import CPU_HZ, start_game

OUT = ROOT / "build/maze-flash"


class MazeFlash(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.sim = Sim()
        start_game(self.sim)
        self.sim.cmd("until frame_wait 100")

    def tearDown(self):
        self.sim.close()

    def call(self, name, param=""):
        result = self.sim.cmd(f"call {name} {param}")[-1]
        return int(result.split("cycles=")[1])

    def test_01_colours_pixels_and_sprite_underlays(self):
        sim = self.sim
        checks = 0
        worst_palette = worst_recolour = 0
        # Include every fruit and several history lengths on a completed maze.
        self.call("clearPillsScreen_2a35")
        for board in (0, 3, 5, 7, 9, 11, 12, 20):
            sim.cmd("poke $e04 3")
            self.call("video_restore")
            sim.cmd(f"poke $e13 {board}")
            self.call("fruitHistoryLevelCheck_2bea")
            self.call("mazeColours_24d7", 0)
            sim.cmd("poke full_dirty 2")
            sim.finish_background()
            background = sim.dump()[0x1000:0x1C40]
            self.call("video_sprites")
            sim.cmd("poke $e04 15")
            for phase, param in enumerate((2, 0) * 4):
                with self.subTest(board=board, phase=phase):
                    cost = self.call("mazeColours_24d7", param)
                    worst_palette = max(worst_palette, cost)
                    self.assertEqual(sim.peek("full_dirty"), b"\x00")
                    self.assertEqual(sim.peek("maze_flash"), b"\x01")
                    logical = sim.peek(0x800, 1024)
                    self.assertEqual(
                        logical[0x40:0x3C0], bytes([31 if param else 16]) * 896
                    )
                    self.assertEqual(logical[0x3C0:], b"\x0f" * 64)
                    before = sim.dump()[0x1000:0x1C40]
                    self.call("video_update_begin")
                    if "__pool_capacity" in sim.labels:
                        self.assertEqual(sim.dump()[0x1000:0x1C40], before)
                        self.assertEqual(sim.peek(0x1000, 3136), background)
                    else:
                        self.assertEqual(sim.dump()[0x1000:0x1C40], background)
                    cost = self.call("bitmap_maze_flash")
                    worst_recolour = max(worst_recolour, cost)
                    sim.cmd("poke maze_flash 0")
                    self.call("video_update_end")
                    fast = sim.dump()
                    self.call("video_restore")
                    fast_underlay = sim.dump()
                    self.assertEqual(fast_underlay[0x1000:0x1C40], background)
                    # The original, expensive path is an independent oracle
                    # for cell colours, including mixed cells and the HUD.
                    sim.cmd("poke full_dirty 2")
                    sim.finish_background()
                    full_underlay = sim.dump()
                    self.assertEqual(
                        fast_underlay[0x9600:0x9700], full_underlay[0x9600:0x9700]
                    )
                    self.call("video_sprites")
                    full = sim.dump()
                    self.assertEqual(fast[0x1000:0x1C40], full[0x1000:0x1C40])
                    self.assertEqual(fast[0x9600:0x9700], full[0x9600:0x9700])
                    checks += 1
        self.assertLess(worst_palette + worst_recolour, 16875)
        report = {
            "comparisons": checks,
            "palette_cycles_max": worst_palette,
            "recolour_cycles_max": worst_recolour,
        }
        (OUT / "renderer.json").write_text(json.dumps(report, indent=2) + "\n")

    def test_02_complete_flash_timing(self):
        sim = self.sim
        # Complete the maze, retaining its walls and the player's last pose.
        self.call("clearPillsScreen_2a35")
        sim.cmd("poke $e0e 244")
        trace = OUT / "sequence.trace"
        sim.cmd("trace " + str(trace.relative_to(ROOT)))
        pictures = []
        for phase in range(8):
            sim.cmd("until maze_colour_done 180")
            sim.cmd("until video_frame_end 100")
            # Capture the settled phase after the arcade's next sprite-output
            # copy hides the ghosts, rather than its single transition frame.
            sim.cmd("run 2")
            sim.cmd("until video_frame_end 100")
            path = OUT / f"phase-{phase}.ppm"
            sim.cmd("shot " + str(path.relative_to(ROOT)))
            with Image.open(path) as picture:
                pictures.append(picture.copy())
            path.unlink()
        sim.cmd("run 180")
        sim.cmd("trace off")
        events = [(int(c), k) for c, k in map(str.split, trace.read_text().splitlines())]
        requests = [(c, k[6:]) for c, k in events if k.startswith("flash-")]
        presents = [(c, k[8:]) for c, k in events if k.startswith("present-")]
        self.assertEqual([k for c, k in requests], ["blue", "white"] * 4)
        self.assertEqual([k for c, k in presents], ["blue", "white"] * 4)
        delays = [(p - r) * 1000 / CPU_HZ for (r, _), (p, _) in zip(requests, presents)]
        # A colour change must finish within two arcade ticks, without a
        # blocked rebuild or a burst of skipped flash phases.
        self.assertLess(max(delays), 33.01)
        spacings = [
            (b - a) * 1000 / CPU_HZ
            for (a, _), (b, _) in zip(presents, presents[1:])
        ]
        expected = 12 * 16875 * 1000 / CPU_HZ
        self.assertTrue(
            all(abs(spacing - expected) < 33.01 for spacing in spacings), spacings
        )
        flash_events = [
            (c, k) for c, k in events if requests[0][0] <= c <= presents[-1][0]
        ]
        logic = [c for c, k in flash_events if k == "logic"]
        audio_gaps = [(b - a) * 1000 / CPU_HZ for a, b in zip(logic, logic[1:])]
        self.assertLess(max(audio_gaps), 33.01)
        report = {
            "phases": [k for _, k in presents],
            "request_to_present_ms": delays,
            "flash_spacing_ms": spacings,
            "audio_update_gap_ms_max": max(audio_gaps),
        }
        (OUT / "timing.json").write_text(json.dumps(report, indent=2) + "\n")
        pictures[0].save(
            OUT / "preview.gif",
            save_all=True,
            append_images=pictures[1:],
            duration=[round(ms) for ms in spacings] + [round(expected)],
            loop=0,
        )
        print(json.dumps(report, indent=2))

    def test_03_walls_survive_incremental_dot_removal(self):
        sim = self.sim
        self.call("video_restore")
        self.call("clearPillsScreen_2a35")
        # Exercise the ordinary dirty-bit path, retaining wall coverage from
        # the original dot-filled maze instead of forcing a fresh full rebuild.
        self.assertEqual(sim.peek("full_dirty"), b"\x01")
        sim.finish_background()
        sim.cmd("poke $e04 15")
        for param in (2, 0):
            self.call("mazeColours_24d7", param)
            self.call("video_update_begin")
            self.call("video_update_end")
            self.assertEqual(sim.peek("maze_flash"), b"\x00")
            fast = sim.dump()
            self.call("video_restore")
            sim.cmd("poke full_dirty 2")
            sim.finish_background()
            self.call("video_sprites")
            full = sim.dump()
            self.assertEqual(fast[0x1000:0x1C40], full[0x1000:0x1C40])
            # Erasing dots can leave colour bytes in entirely empty cells.
            # Compare all cells that actually contain foreground pixels.
            for cell in range(196):
                row, col = divmod(cell, 14)
                offset = 0x1000 + col * 224 + row * 16
                if any(full[offset : offset + 16]):
                    self.assertEqual(fast[0x9600 + cell], full[0x9600 + cell], cell)


if __name__ == "__main__":
    unittest.main(verbosity=2)
