#!/usr/bin/env python3
"""Check the native compositor against an independent bitmap reference."""
import random
import re
import unittest
from native import Sim, BUILD, WORK
from performance import start_game


class Renderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        source = (BUILD / "rom.c").read_text()

        def table(name):
            body = re.search(name + r"\[.*?= \{(.*?)\};", source, re.S)[1]
            return bytes(int(x, 16) for x in re.findall(r"0x[0-9a-f]+", body))

        cls.sprites = table("arcade_sprites")
        cls.eyes = table("arcade_eyes")
        cls.classes = table("arcade_sprite_class")
        cls.colors = table("arcade_colors")
        cls.sim = Sim()
        cls.sim.cmd("run 500")
        cls.sim.cmd("until frame_wait 100")
        rng = random.Random(6560)
        cls.background = bytes(rng.randrange(256) for _ in range(3136))
        cls.cell_colors = bytes(rng.randrange(8) for _ in range(256))
        for address, data in ((0x1000, cls.background), (0x9600, cls.cell_colors)):
            p = WORK / "bg.bin"
            p.write_bytes(data)
            cls.sim.cmd(f"load ${address:x} {p}")

    @classmethod
    def tearDownClass(cls):
        cls.sim.close()

    def setUp(self):
        # The incremental test changes its background. Reset native memory
        # between test methods as well as resetting the Python fixture.
        self.sim.cmd("call video_restore")
        for address, data in ((0x1000, self.background), (0x9600, self.cell_colors)):
            path = WORK / "bg.bin"
            path.write_bytes(data)
            self.sim.cmd(f"load ${address:x} {path}")

    def check_scene(
        self, actors, incremental=False, retain=False, background_change=False,
        via_refresh=False,
    ):
        attrs = bytearray(16)
        positions = bytearray(16)
        expected = bytearray(self.background)
        colors = bytearray(self.cell_colors)
        for off, (code, flip, pal, raw_x, raw_y) in zip(range(12, 0, -2), actors):
            attrs[off : off + 2] = bytes((code * 4 + flip, pal))
            positions[off : off + 2] = bytes((raw_x, raw_y))
            x = (239 - raw_x - (off <= 4)) // 2
            y = (272 - raw_y) * 3 // 4
            if not pal or x <= -8 or x >= 112:
                continue
            eye = pal == 25 and 32 <= code < 40
            pixel = 1 if eye else (self.classes[code // 4] >> ((code & 3) * 2)) & 3
            color = self.colors[pal * 4 + pixel]
            if not color:
                continue
            image = (
                self.eyes[(code - 32) * 12 : (code - 31) * 12]
                if eye
                else self.sprites[code * 12 : (code + 1) * 12]
            )
            col, shift = x // 8, x & 7
            cell = (y // 16) * 14 + col
            for row in range(12):
                bits = image[11 - row if flip & 1 else row]
                if flip & 2:
                    bits = int(f"{bits:08b}"[::-1], 2)
                if col >= 0:
                    expected[col * 224 + y + row] |= bits >> shift
                if col < 13:
                    expected[(col + 1) * 224 + y + row] |= (bits << (8 - shift)) & 255
            for lower in (0, 14) if y & 15 > 4 else (0,):
                if col >= 0:
                    colors[(cell + lower) & 255] = color
                if col < 13 and shift:
                    colors[(cell + lower + 1) & 255] = color
        for address, data in ((0xC20, attrs), (0xC30, positions)):
            p = WORK / "actors.bin"
            p.write_bytes(data)
            self.sim.cmd(f"load ${address:x} {p}")
        if incremental:
            if background_change:
                # This fixture replaces the whole bitmap, not one queued tile.
                self.sim.cmd("poke full_dirty 1")
            if via_refresh:
                self.assertFalse(background_change)
                self.sim.cmd("call video_refresh")
            else:
                self.sim.cmd("call video_update_begin")
            if background_change:
                for address, data in (
                    (0x1000, self.background),
                    (0x9600, self.cell_colors),
                ):
                    p = WORK / "bg.bin"
                    p.write_bytes(data)
                    self.sim.cmd(f"load ${address:x} {p}")
                self.sim.cmd("poke full_dirty 0")
            if not via_refresh:
                self.sim.cmd("call video_update_end")
        else:
            self.sim.cmd("call video_sprites")
        actual = self.sim.dump()
        self.assertEqual(actual[0x1000:0x1C40], expected, f"sprite pixels: {actors}")
        self.assertEqual(actual[0x9600:0x9700], colors, f"sprite colors: {actors}")
        if retain:
            return
        self.sim.cmd("call video_restore")
        actual = self.sim.dump()
        self.assertEqual(
            actual[0x1000:0x1C40], self.background, f"restored pixels: {actors}"
        )
        self.assertEqual(
            actual[0x9600:0x9700], self.cell_colors, f"restored colors: {actors}"
        )

    def test_01_all_frames_shifts_and_flips(self):
        for code in range(64):
            for shift in range(8):
                for flip in range(4):
                    self.check_scene(
                        [
                            (
                                code,
                                flip,
                                1 + (code % 31),
                                175 - shift * 2,
                                80 + (code % 16),
                            )
                        ]
                    )

    def test_02_edges_overlap_priority_and_returning_eyes(self):
        rng = random.Random(1980)
        for trial in range(160):
            actors = []
            for actor in range(6):
                code = 32 + actor if trial % 3 == 0 else rng.randrange(64)
                pal = 25 if trial % 3 == 0 else rng.randrange(32)
                actors.append(
                    (
                        code,
                        rng.randrange(4),
                        pal,
                        rng.choice(
                            (
                                0,
                                1,
                                14,
                                15,
                                16,
                                224,
                                238,
                                239,
                                240,
                                252,
                                253,
                                254,
                                255,
                                128 + actor,
                            )
                        ),
                        rng.randrange(256),
                    )
                )
            self.check_scene(actors)

    def test_03_incremental_matches_full_redraw(self):
        self.sim.cmd("poke dirty_count 0")
        self.sim.cmd("poke full_dirty 0")
        rng = random.Random(60)
        actors = [
            [32 + i, 0, (1, 3, 5, 7, 9, 25)[i], 160 + i * 3, 100 + i * 3]
            for i in range(6)
        ]
        for frame in range(360):
            actor = rng.choice(actors)
            actor[3] = (actor[3] + rng.choice((-1, 1, 2))) & 255
            actor[4] = (actor[4] + rng.choice((-1, 0, 1))) & 255
            if frame % 7 == 0:
                actor[1] ^= 1
            if frame % 13 == 0:
                actor[0] = rng.randrange(64)
            if frame % 23 == 0:
                actor[2] = rng.randrange(32)
            if frame % 29 == 0:
                actor[3] = rng.choice((1, 15, 238, 253, 255))
            background_change = frame in (120, 240)
            if background_change:
                self.background = bytes(rng.randrange(256) for _ in self.background)
                self.cell_colors = bytes(rng.randrange(8) for _ in self.cell_colors)
            self.check_scene(
                actors,
                incremental=True,
                retain=frame < 359,
                background_change=background_change,
            )

    def test_04_preshifted_ghost_path(self):
        # Force a visible body palette so all eligible frames reach the fast
        # path; cover every sub-byte position and both hardware flip bits.
        self.sim.cmd("profile reset")
        for code in (28, 29, 32, 33, 34, 35, 36, 37):
            for shift in range(8):
                for flip in range(4):
                    self.check_scene(
                        [
                            (
                                code,
                                flip,
                                17 if code < 30 else 1,
                                175 - shift * 2,
                                80 + code % 16,
                            )
                        ]
                    )
        path = WORK / "ghost.profile"
        self.sim.cmd("profile " + str(path))
        self.sim.cmd("profile off")
        hits = {
            int(a, 16): int(h)
            for a, cycles, h in map(str.split, path.read_text().splitlines())
        }
        self.assertEqual(hits[self.sim.labels["bitmap_draw_ghost"]], 8 * 8 * 4)

    def test_06_clipped_kernel_memory_boundaries(self):
        # A clipped column is redirected into its unused underlay half. Check
        # both bitmap edges, including addresses that would hit video caches
        # or game I/O if an invisible column were written to its real address.
        sim = Sim()
        try:
            sim.cmd("run 500")
            sim.cmd("until frame_wait 100")
            rng = random.Random(6561)
            guards = bytes(rng.randrange(256) for _ in range(256))
            records = bytes(rng.randrange(256) for _ in range(216))
            under = sim.labels["under"]
            path = WORK / "kb.bin"

            def load(address, data):
                path.write_bytes(data)
                sim.cmd(f"load ${address:x} {path}")

            def poke(name, value, width=1):
                for byte in range(width):
                    sim.cmd(f"poke ${sim.labels[name] + byte:x} {(value >> (8 * byte)) & 255}")

            for code, eye in ((0, False), (9, False), (6, True)):
                atlas = self.eyes if eye else self.sprites
                source = sim.labels["arcade_eyes" if eye else "arcade_sprites"] + code * 12
                for shift in range(8):
                    for flip in range(4):
                        for column, flags in ((-1, 2), (13, 1)):
                            for y in (0, 15, 204):
                                for record in (0, 180):
                                    dest = 0x1000 + column * 224 + y
                                    save = under + record + 8
                                    for address, data in ((0x1000, self.background),
                                                          (0x0F00, guards), (0x1C40, guards),
                                                          (under, records)):
                                        load(address, data)
                                    for name, value, width in (("v_addr", dest, 2),
                                                               ("v_save", save, 2),
                                                               ("v_data", source, 2),
                                                               ("v_shift", shift, 1),
                                                               ("v_flip", flip, 1),
                                                               ("v_flags", flags, 1)):
                                        poke(name, value, width)
                                    sim.cmd("call bitmap_draw")
                                    actual = sim.dump()
                                    expected = bytearray(self.background)
                                    for row in range(12):
                                        bits = atlas[code * 12 + (11 - row if flip & 1 else row)]
                                        if flip & 2:
                                            bits = int(f"{bits:08b}"[::-1], 2)
                                        index = (column if flags == 1 else column + 1) * 224 + y + row
                                        expected[index] |= (bits >> shift if flags == 1
                                                            else (bits << (8 - shift)) & 255)
                                    case = (code, eye, shift, flip, column, y, record)
                                    self.assertEqual(actual[0x1000:0x1C40], expected, case)
                                    self.assertEqual(actual[under:save], records[:record + 8], case)
                                    self.assertEqual(actual[save + 24:under + 216], records[record + 32:], case)
                                    saved = save if flags == 1 else save + 12
                                    visible = dest if flags == 1 else dest + 224
                                    self.assertEqual(actual[saved:saved + 12],
                                                     self.background[visible - 0x1000:visible - 0x1000 + 12], case)
                                    # The frontend reloads the original address from
                                    # the record before restoring this actor.
                                    poke("v_addr", dest, 2)
                                    sim.cmd("call bitmap_erase")
                                    actual = sim.dump()
                                    self.assertEqual(actual[0x1000:0x1C40], self.background, case)
                                    self.assertEqual(actual[0x0F00:0x1000], guards, case)
                                    self.assertEqual(actual[0x1C40:0x1D40], guards, case)
        finally:
            sim.close()

    def test_05_dirty_tiles_preserve_actors_and_shared_colours(self):
        sim = Sim()
        try:
            start_game(sim)
            sim.cmd("until frame_wait 100")
            sim.cmd("call video_restore")
            # A white-only background isolates actor restoration from the
            # pre-existing last-writer colour rule for unrelated HUD art.
            path = WORK / "fbg.bin"
            path.write_bytes(bytes([64]) * 1024 + bytes([14]) * 1024)
            sim.cmd(f"load $0400 {path}")
            sim.cmd("poke full_dirty 2")
            sim.finish_background()
            attrs, positions = bytearray(16), bytearray(16)
            # Visible body at x=32, y=42, with two overlapping neighbours.
            for off, code, pal, raw_x, raw_y in (
                (12, 32, 1, 175, 216), (10, 33, 3, 171, 214),
                (8, 34, 5, 157, 200),
            ):
                attrs[off:off+2] = bytes((code * 4, pal))
                positions[off:off+2] = bytes((raw_x, raw_y))
            for address, data in ((0xC20, attrs), (0xC30, positions)):
                path = WORK / "fa.bin"
                path.write_bytes(data)
                sim.cmd(f"load ${address:x} {path}")
            sim.cmd("call video_sprites")
            sim.cmd("watch bitmap_erase erase")

            # Include both HUD orientations and a tile at y=36..41 sharing
            # an actor's colour row without overlapping its actual pixels.
            cases = [(30 * 32 + 21, True), (21 * 32 + 4, False),
                     (21 * 32 + 5, False), (21, False),
                     (19 * 32 + 8, False), (21 * 32 + 3, False)]
            rng = random.Random(9400)
            candidates = [i for i, code in enumerate(sim.peek(0x400, 1024))
                          if code < 192]
            cases += [(rng.choice(candidates), False) for _ in range(94)]
            for trial, (index, unrelated_hud) in enumerate(cases):
                code = sim.peek(0x400 + index)[0] if trial % 5 == 2 else trial % 10
                palette = 31 if sim.peek(0x800 + index)[0] == 14 else 14
                for address, value in ((0x400 + index, code),
                                       (0x800 + index, palette)):
                    sim.cmd(f"poke __rc2 {address & 255}")
                    sim.cmd(f"poke __rc3 {address >> 8}")
                    sim.cmd(f"call video_store {value}")
                trace = WORK / "fa.trace"
                sim.cmd(f"trace {trace}")
                sim.cmd("call video_refresh")
                sim.cmd("trace off")
                if unrelated_hud:
                    self.assertNotIn("erase-begin", trace.read_text())
                actual = sim.dump()
                sim.cmd("call video_restore")
                sim.cmd("poke full_dirty 2")
                sim.finish_background()
                sim.cmd("call video_sprites")
                expected = sim.dump()
                self.assertEqual(actual[0x1000:0x1C40], expected[0x1000:0x1C40], trial)
                for cell in range(196):
                    row, col = divmod(cell, 14)
                    offset = 0x1000 + col * 224 + row * 16
                    if any(expected[offset:offset+16]):
                        self.assertEqual(actual[0x9600+cell], expected[0x9600+cell],
                                         (trial, cell))
        finally:
            sim.close()

    def test_07_composed_overlaps_movement_and_underlay_restoration(self):
        self.sim.cmd("poke dirty_count 0")
        self.sim.cmd("poke full_dirty 0")
        rng = random.Random(6562)
        actors = [[32+i, 0, (1, 3, 5, 7, 9, 25)[i], 165+i*3, 200+i*3]
                  for i in range(6)]
        self.check_scene(actors, retain=True)
        stack = self.sim.peek(2, 2)
        self.sim.cmd("profile reset")
        for frame in range(480):
            for actor in rng.sample(actors, 1 + frame % 6):
                actor[3] = max(36, min(225, actor[3] + rng.choice((-2, -1, 1, 2))))
                actor[4] = max(25, min(250, actor[4] + rng.choice((-2, -1, 0, 1, 2))))
            if frame % 7 == 0:
                actors[frame % 6][1] = rng.randrange(4)
            if frame % 11 == 0:
                actors[frame % 6][0] = rng.choice((0, 9, 28, 29, 32, 33, 34, 35, 36, 37))
            if frame % 19 == 0:
                actors[frame % 6][2] = rng.choice((0, 1, 3, 5, 7, 17, 25))
            if frame % 31 == 0:
                actors[frame % 6][3:5] = [rng.choice((39, 104, 165, 211)),
                                        rng.choice((28, 100, 200, 248))]
            self.check_scene(actors, incremental=True, via_refresh=True,
                             retain=frame < 479)
            self.assertEqual(self.sim.peek("compose_active"), b"\0", frame)
            self.assertEqual(self.sim.peek(2, 2), stack, frame)
        path = WORK / "cp.profile"
        self.sim.cmd(f"profile {path}")
        self.sim.cmd("profile off")
        hits = {int(a, 16): int(h) for a, _, h in
                map(str.split, path.read_text().splitlines())}
        self.assertGreater(hits[self.sim.labels["compose_publish_row"]], 200)

    def test_08_composition_keeps_live_pixels_and_colours_until_publish(self):
        self.sim.cmd("poke dirty_count 0")
        self.sim.cmd("poke full_dirty 0")
        for raw_y in (214, 208, 202, 193):
            actors = [[32+i, i % 4, (1, 3, 5, 7, 9, 25)[i], 175-i*2, raw_y+i]
                      for i in range(6)]
            self.check_scene(actors, retain=True)
            before = self.sim.dump()
            stack = self.sim.peek(2, 2)
            for off, actor in zip(range(12, 0, -2), actors):
                actor[3] -= 2
                actor[4] += 1
                self.sim.cmd(f"poke ${0xc30+off:x} {actor[3]}")
                self.sim.cmd(f"poke ${0xc31+off:x} {actor[4]}")
            self.sim.cmd("call sprite_mark")
            self.sim.cmd("call compose_prepare")
            self.assertEqual(self.sim.peek("compose_active"), b"\1")
            self.assertEqual(int.from_bytes(self.sim.peek(2, 2), 'little'),
                             int.from_bytes(stack, 'little') - 512)
            self.sim.cmd("call restore_start")
            self.sim.cmd("call video_update_end")
            prepared = self.sim.dump()
            self.assertEqual(prepared[0x1000:0x1c40], before[0x1000:0x1c40])
            self.assertEqual(prepared[0x9600:0x9700], before[0x9600:0x9700])
            self.sim.cmd("call compose_commit")
            self.assertEqual(self.sim.peek("compose_active"), b"\0")
            self.assertEqual(self.sim.peek(2, 2), stack)
            self.check_scene(actors, incremental=True, via_refresh=True)

    def test_09_composition_fallbacks_restore_pointer_and_stack(self):
        self.sim.cmd("poke dirty_count 0")
        self.sim.cmd("poke full_dirty 0")
        fixtures = (
            ([(32, 0, 1, 241, 200)], {}),  # clipped left
            ([(32, 0, 1, 31, 200)], {}),   # clipped right
            ([(32, 0, 1, 175, 200)], {"full_dirty": 1}),
            ([(32, 0, 1, 175, 200)], {"maze_flash": 1}),
            ([(32, 0, 1, 175, 200)], {"dirty_count": 1}),
            ([(32, 0, 1, 175, 250), (33, 0, 3, 175, 25)], {}), # capacity
            ([(32, 0, 1, 175, 200)], {"__rc0": 0x80, "__rc1": 0x1f}),
            ([(32, 0, 1, 175, 200)], {"$e00": 3, "$e04": 4}), # intermission
        )
        for actors, patch in fixtures:
            self.check_scene(actors, retain=True)
            self.sim.cmd("call sprite_force_all")
            # check_scene has already committed the current cache coordinates.
            stack = self.sim.peek(2, 2)
            game_mode = self.sim.peek(0xe00, 5)
            for name, value in patch.items():
                self.sim.cmd(f"poke {name} {value}")
            expected_stack = self.sim.peek(2, 2)
            before = self.sim.dump()
            self.sim.cmd("call compose_prepare")
            after = self.sim.dump()
            self.assertEqual(self.sim.peek("compose_active"), b"\0", (actors, patch))
            self.assertEqual(self.sim.peek(2, 2), expected_stack, (actors, patch))
            self.assertEqual(self.sim.peek("v_colors", 2), b"\0\x96", (actors, patch))
            self.assertEqual(after[0x1000:0x1c40], before[0x1000:0x1c40])
            self.assertEqual(after[0x9600:0x9700], before[0x9600:0x9700])
            for address, value in enumerate(stack, 2):
                self.sim.cmd(f"poke ${address:x} {value}")
            for name in ("full_dirty", "maze_flash", "dirty_count"):
                self.sim.cmd(f"poke {name} 0")
            for address, value in enumerate(game_mode, 0xe00):
                self.sim.cmd(f"poke ${address:x} {value}")
            self.sim.cmd("call video_restore")


if __name__ == "__main__":
    unittest.main(verbosity=2)
