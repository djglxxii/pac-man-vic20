#!/usr/bin/env python3
"""Check white maze/pellet colors from source pixels and completion states."""
import json
import random
import re
import unittest

from native import Sim, ROOT, BUILD
from performance import start_game

OUT = ROOT / "build/white-maze"


def offset(x, y):
    return (29 - x) * 32 + y - 2


class Colors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (BUILD / "rom.c").read_text()
        body = re.search(r"arcade_tiles\[.*?= \{(.*?)\};", source, re.S)[1]
        packed = bytes(int(x, 16) for x in re.findall(r"0x[0-9a-f]+", body))
        cls.tiles = [
            [n for b in packed[i:i + 3] for n in (b >> 4, b & 15)]
            for i in range(0, len(packed), 3)
        ]
        OUT.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.sim = Sim()
        start_game(self.sim)
        self.sim.cmd("until frame_wait 100")
        self.sim.cmd("call video_restore")

    def tearDown(self):
        self.sim.close()

    def load(self, address, data):
        path = OUT / "fixture.bin"
        path.write_bytes(data)
        self.sim.cmd(f"load ${address:x} {path}")

    def store(self, address, value):
        self.sim.cmd(f"poke __rc2 {address & 255}")
        self.sim.cmd(f"poke __rc3 {address >> 8}")
        self.sim.cmd(f"call video_store {value}")

    def rebuild(self):
        self.sim.cmd("poke full_dirty 2")
        return self.sim.finish_background()

    def fixture(self, entries):
        screen = bytearray([64] * 1024)
        palette = bytearray([16] * 1024)
        for x, y, code, pal in entries:
            i = offset(x, y)
            screen[i], palette[i] = code, pal
        self.load(0x400, screen + palette)
        self.rebuild()

    def pellet_cells(self, mem):
        cells = set()
        for x in range(28):
            for y in range(2, 34):
                i = offset(x, y)
                code = mem[0x400 + i]
                if code not in (16, 18, 20) or not mem[0x800 + i] & 31:
                    continue
                cells.update(
                    ((y * 6 + row) // 16) * 14 + x // 2
                    for row, bits in enumerate(self.tiles[code]) if bits
                )
        return cells

    def assert_white_background(self):
        mem = self.sim.dump()
        white = self.pellet_cells(mem)
        walls = mem[self.sim.labels["maze_cells"]:][:25]
        for cell in range(196):
            if cell in white:
                self.assertEqual(mem[0x9600 + cell], 1, f"pellet cell {cell}")
            elif walls[cell // 8] & (1 << (cell & 7)):
                self.assertEqual(mem[0x9600 + cell], 1, f"wall cell {cell}")
        return mem, white

    def test_01_real_maze_white_walls_pellets_and_unchanged_pixels(self):
        self.rebuild()
        mem, cells = self.assert_white_background()
        self.assertGreater(len(cells), 100)
        # A separate tile rasterizer verifies that ownership never changes art.
        bitmap = bytearray(3136)
        for i, code in enumerate(mem[0x400:0x800]):
            a, b = divmod(i, 32)
            if 2 <= a < 30:
                x, y = 29 - a, b + 2
            elif 2 <= b < 30:
                x, y = 29 - b, a + 34 if a < 2 else a - 30
            else:
                continue
            if not mem[0x800 + i] & 31 or code in (64, 252, 253):
                continue
            for row, bits in enumerate(self.tiles[code]):
                bitmap[(x // 2) * 224 + y * 6 + row] |= bits << (0 if x & 1 else 4)
        self.assertEqual(mem[0x1000:0x1c40], bitmap)
        (OUT / "pellets.json").write_text(json.dumps({
            "visible_pellet_cells": len(cells), "white_pellet_cells": len(cells),
        }, indent=2) + "\n")
        self.sim.cmd("shot build/white-maze/after.ppm")

    def test_02_tile_order_does_not_change_white_maze(self):
        self.rebuild()
        expected, _ = self.assert_white_background()
        order = list(range(1024))
        random.Random(6560).shuffle(order)
        for i in order:
            self.sim.cmd(f"poke v_save {i & 255}")
            self.sim.cmd(f"poke ${self.sim.labels['v_save'] + 1:x} {i >> 8}")
            self.sim.cmd("call bitmap_tile")
        actual, _ = self.assert_white_background()
        self.assertEqual(actual[0x1000:0x1c40], expected[0x1000:0x1c40])

    def test_03_wall_stays_white_after_last_dot_and_power_pellet_blinks(self):
        self.fixture(((8, 11, 0xd2, 16), (9, 11, 16, 16), (9, 12, 16, 16)))
        self.assert_white_background()
        for y in (11, 12):
            self.store(0x400 + offset(9, y), 64)
            self.sim.cmd("call video_background")
            self.assert_white_background()
        self.assertEqual(self.sim.peek(0x9600 + 4 * 14 + 4), b"\x01")
        self.store(0x400 + offset(9, 11), 20)
        self.sim.cmd("call video_background")
        for pal in (0, 16, 0, 16):
            self.store(0x800 + offset(9, 11), pal)
            self.sim.cmd("call video_background")
            mem, _ = self.assert_white_background()
            pixel = 0x1000 + 4 * 224 + 11 * 6
            self.assertEqual(
                [b & 15 for b in mem[pixel:pixel + 6]],
                self.tiles[20] if pal else [0] * 6,
            )

    def test_04_pellet_ink_at_every_cell_boundary(self):
        rng = random.Random(216)
        for code in (16, 18, 20):
            entries = [(x, y, 0xd2, 16) for x in range(28) for y in range(2, 34)]
            entries += [(rng.randrange(28), y, code, 16) for y in range(2, 34)]
            self.fixture(entries)
            self.assert_white_background()
            for x, y, _, _ in entries[-32:]:
                self.store(0x400 + offset(x, y), 64)
            self.sim.finish_background()
            self.assert_white_background()

    def test_05_actor_releases_white_pellets_and_keeps_aligned_neighbor(self):
        self.fixture(((8, 11, 0xd2, 16), (9, 11, 16, 16), (11, 11, 16, 16)))
        background = self.sim.dump()
        attrs = bytearray(16)
        coords = bytearray(16)
        attrs[12:14] = bytes((32 * 4, 1))
        coords[12:14] = bytes((175, 184))  # Native x=32, y=66, aligned.
        self.load(0xc20, attrs)
        self.load(0xc30, coords)
        self.sim.cmd("call video_sprites")
        mem = self.sim.dump()
        cell = 4 * 14 + 4
        self.assertEqual(mem[0x9600 + cell], 2)
        self.assertEqual(mem[0x9600 + cell + 1], 1)
        self.sim.cmd("call video_restore")
        mem, _ = self.assert_white_background()
        self.assertEqual(mem[0x1000:0x1c40], background[0x1000:0x1c40])
        self.assertEqual(mem[0x9600:0x96c4], background[0x9600:0x96c4])

    def test_06_blue_is_limited_to_completion_flash(self):
        self.sim.cmd("call clearPillsScreen_2a35")
        for level in (3, 14, 15, 29, 30):
            for param in (0, 2):
                with self.subTest(level=level, param=param):
                    self.sim.cmd(f"poke $e04 {level}")
                    self.sim.cmd(f"call mazeColours_24d7 {param}")
                    self.rebuild()
                    mem = self.sim.dump()
                    walls = mem[self.sim.labels["maze_cells"]:][:25]
                    expected = 6 if 15 <= level < 30 and param == 2 else 1
                    for cell in range(196):
                        if walls[cell // 8] & (1 << (cell & 7)):
                            self.assertEqual(mem[0x9600 + cell], expected, cell)


if __name__ == "__main__":
    unittest.main(verbosity=2)
