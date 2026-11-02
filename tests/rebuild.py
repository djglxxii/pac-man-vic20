#!/usr/bin/env python3
"""Check bounded work, live writes, queue order and the complete transition."""
import json
from pathlib import Path
import random
import unittest

from arcade import Runner, WORK
from native import Sim, ROOT
from performance import CPU_HZ, start_game, wait

OUT = ROOT / "build/bounded-rebuild"


class Rebuild(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.sim = Sim()
        start_game(self.sim)
        self.sim.cmd("until frame_wait 100")
        self.sim.finish_background()
        self.sim.cmd("call video_restore")

    def tearDown(self):
        self.sim.close()

    def call(self, name, args=""):
        result = self.sim.cmd(f"call {name} {args}")[-1].split()
        return int(result[1], 16), int(result[-1].split("=")[1])

    def store(self, address, value):
        self.sim.cmd(f"poke __rc2 {address & 255}")
        self.sim.cmd(f"poke __rc3 {address >> 8}")
        return self.call("video_store", str(value))

    def load(self, address, data):
        path = OUT / "fixture.bin"
        path.write_bytes(data)
        self.sim.cmd(f"load ${address:x} {path}")

    def test_01_dirty_addresses_cover_all_four_pages(self):
        for base in (0x400, 0x800):
            self.load(base, bytes(1024))
            self.load(self.sim.labels["dirty_bits"], bytes(128))
            self.sim.cmd("poke full_dirty 0")
            self.sim.cmd("poke dirty_count 0")
            self.sim.cmd("poke rebuild_phase 0")
            indices = list(range(1024))
            random.Random(base).shuffle(indices)
            expected = bytearray(128)
            for i in indices:
                self.store(base + i, 1)
                expected[i >> 3] |= 1 << (i & 7)
                self.assertEqual(self.sim.peek("dirty_bits", 128), expected, i)

    def test_02_bulk_slices_match_original_rom(self):
        reference = Runner("oracle")
        try:
            reference.cmd("run 600")
            fixture = bytearray((WORK / "game.ram").read_bytes())
            rng = random.Random(2419)
            fixture[0x4000:0x4800] = bytes(rng.randrange(256) for _ in range(2048))
            fixture[0x4E16:0x4E34] = bytes(rng.randrange(256) for _ in range(30))
            fixture[0x4E34:0x4E38] = bytes((20, 64, 20, 64))
            path = OUT / "original.ram"
            path.write_bytes(fixture)
            worst = 0
            for task, address, param in (
                (0, 0x23ED, 0), (0, 0x23ED, 1), (6, 0x240D, 0),
                (1, 0x24D7, 0), (1, 0x24D7, 1), (1, 0x24D7, 2),
                (2, 0x2419, 0), (3, 0x2448, 0), (19, 0x2A35, 0),
            ):
                with self.subTest(task=task, param=param):
                    reference.load(path)
                    reference.cmd(f"call {address:x} {param:x}")
                    expected = reference.dump()[0x4000:0x4800]
                    self.load(0x400, fixture[0x4000:0x4800])
                    self.load(0xE16, fixture[0x4E16:0x4E38])
                    self.sim.cmd("poke $e04 3")
                    self.sim.cmd("poke bulk_active 0")
                    self.sim.cmd("poke full_dirty 0")
                    self.sim.cmd("poke rebuild_phase 0")
                    self.sim.cmd("poke dirty_count 0")
                    self.load(self.sim.labels["dirty_bits"], bytes(128))
                    for slices in range(256):
                        result, cost = self.call("arcade_bulk_step", f"{task} {param}")
                        worst = max(worst, cost)
                        self.assertLess(cost, 14000)
                        if result == 2:
                            break
                        self.assertEqual(result, 1)
                    else:
                        self.fail("Bulk task did not finish")
                    self.assertGreater(slices, 0)
                    self.assertEqual(self.sim.peek(0x400, 2048), expected)
            (OUT / "bulk.json").write_text(json.dumps({"slice_cycles_max": worst}, indent=2) + "\n")
        finally:
            reference.close()

    def assert_settled_matches_fresh(self):
        actual = self.sim.dump()
        self.sim.cmd("poke full_dirty 2")
        costs = self.sim.finish_background()
        expected = self.sim.dump()
        self.assertEqual(actual[0x1000:0x1C40], expected[0x1000:0x1C40])
        # Empty cells may keep an unused foreground color after a dirty erase.
        for cell in range(196):
            row, col = divmod(cell, 14)
            offset = 0x1000 + col * 224 + row * 16
            if any(expected[offset:offset + 16]):
                self.assertEqual(actual[0x9600 + cell], expected[0x9600 + cell], cell)
        self.assertLess(max(costs), 14000)

    def test_03_writes_behind_and_ahead_of_cursor(self):
        self.sim.cmd("poke full_dirty 2")
        for _ in range(200):
            self.call("video_rebuild")
            cursor = int.from_bytes(self.sim.peek("rebuild_cursor", 2), "little")
            if self.sim.peek("rebuild_phase") == b"\x02" and cursor > 128:
                break
        else:
            self.fail("Full pass did not start")
        for i in (64, 120, 800, 920):
            self.store(0x400 + i, 64)
        self.assertEqual(self.sim.peek("rebuild_again"), b"\x01")
        self.sim.finish_background()
        self.assertFalse(any(self.sim.peek("dirty_bits", 128)))
        self.assert_settled_matches_fresh()

    def test_04_restart_in_every_rebuild_phase(self):
        logical = self.sim.peek(0x400, 2048)
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                self.load(0x400, logical)
                self.sim.cmd("poke full_dirty 2")
                seeded = False
                for _ in range(300):
                    self.call("video_rebuild")
                    if self.sim.peek("rebuild_phase")[0] == phase:
                        break
                    cursor = int.from_bytes(self.sim.peek("rebuild_cursor", 2), "little")
                    if phase == 3 and not seeded and self.sim.peek("rebuild_phase")[0] == 2 and cursor > 128:
                        for i in range(64, 96):
                            self.store(0x400 + i, logical[i] ^ 1)
                        seeded = True
                else:
                    self.fail("Requested rebuild phase was not reached")
                self.store(0x440, 64)
                self.sim.cmd("poke full_dirty 2")
                self.sim.finish_background()
                self.assert_settled_matches_fresh()

    def test_05_split_native_state_range_matches_rom(self):
        reference = Runner("oracle")
        try:
            reference.cmd("run 600")
            fixture = bytearray((WORK / "game.ram").read_bytes())
            fixture[0x4D00:0x4E00] = bytes(range(256))
            path = OUT / "state.ram"
            path.write_bytes(fixture)
            reference.load(path)
            reference.cmd("call 26a2")
            self.load(0xD00, fixture[0x4D00:0x4DA0])
            self.load(0xA0, fixture[0x4DA0:0x4E00])
            _, cost = self.call("clearGhostState_26a2")
            self.assertLess(cost, 3000)
            actual = self.sim.peek(0xD00, 160) + self.sim.peek(0xA0, 96)
            self.assertEqual(actual, reference.dump()[0x4D00:0x4E00])
        finally:
            reference.close()

    def test_06_complete_transition_service_and_queue_order(self):
        sim = self.sim
        sim.cmd("until frame_wait 100")
        for function, name in (("frame_wait", "wait"), ("video_rebuild", "rebuild"), ("arcade_bulk_step", "bulk")):
            sim.cmd(f"watch {function} {name}")
        start_board = sim.peek(0xE13)[0]
        sim.cmd("poke $e0e 244")
        trace = OUT / "transition.trace"
        sim.cmd("trace " + str(trace))
        queue_max = 0
        for _ in range(600):
            sim.cmd("run 1")
            pointers = sim.peek(0xC80, 4)
            end = int.from_bytes(pointers[:2], "little")
            begin = int.from_bytes(pointers[2:], "little")
            self.assertTrue(0x4CC0 <= begin < 0x4D00)
            self.assertTrue(0x4CC0 <= end < 0x4D00)
            self.assertFalse(begin == end and sim.peek(begin - 0x4000)[0] < 0x80, "Task queue filled its ring")
            queue_max = max(queue_max, ((end - begin) & 63) // 2)
        sim.cmd("trace off")
        self.assertEqual(sim.peek(0xE13)[0], start_board + 1)
        self.assertEqual(sim.peek("full_dirty"), b"\x00")
        events = [(int(c), k) for c, k in map(str.split, trace.read_text().splitlines())]
        requests = [c for c, k in events if k == "rebuild-request"]
        phase_ends = [c for c, k in events if k == "rebuild-phase-0"]
        self.assertTrue(requests)
        final = next(c for c, k in events if k == "end" and c >= phase_ends[-1])
        first = requests[0]
        report = {"queue_entries_max": queue_max, "settled_board_ms": (final - first) * 1000 / CPU_HZ}
        for kind, name in (("logic", "audio_update_gap_ms_max"), ("wait-end", "input_service_gap_ms_max")):
            times = [c for c, k in events if k == kind]
            gaps = [(b - a) * 1000 / CPU_HZ for a, b in zip(times, times[1:]) if b >= first and a <= final]
            report[name] = max(gaps)
            self.assertLess(max(gaps), 33.01)
        self.assertEqual([k for c, k in events if k.startswith("task-") and k.endswith("-begin")],
                         [f"task-{task}-begin" for task in (0, 6, 19, 0, 1, 2, 19, 3)])
        self.assertEqual([k for c, k in events if k.startswith("present-")], ["present-white", "present-blue"] * 4)
        # White-pellet ownership adds bounded neighbour checks during drawing.
        # Keep a completion bound as well as the unchanged service-gap limits.
        self.assertLess(report["settled_board_ms"], 2250)
        (OUT / "transition.json").write_text(json.dumps(report, indent=2) + "\n")

    def test_07_coin_is_serviced_during_rebuild(self):
        sim = self.sim
        sim.cmd("until frame_wait 100")
        sim.cmd("poke $e0e 244")
        wait(sim, sim.labels["rebuild_phase"], lambda phase: phase != 0, limit=600)
        credits = sim.peek(0xE6E)[0]
        sim.cmd("key 5")
        wait(sim, 0xE6E, lambda value: value == credits + 1, limit=12)
        self.assertNotEqual(sim.peek("rebuild_phase"), b"\x00")
        sim.cmd("key -")

    def test_08_completion_uses_current_actor_positions(self):
        sim = self.sim
        sim.cmd("poke full_dirty 2")
        self.call("video_refresh")
        attrs = bytearray(16)
        positions = bytearray(16)
        for actor, offset in enumerate(range(12, 0, -2)):
            attrs[offset:offset + 2] = bytes(((32 + actor) * 4, (1, 3, 5, 7, 9, 25)[actor]))
            positions[offset:offset + 2] = bytes((150 + actor * 3, 100 + actor * 3))
        self.load(0xC20, attrs)
        self.load(0xC30, positions)
        for step in range(400):
            self.call("video_refresh")
            if step == 30:
                for offset in range(2, 14, 2):
                    positions[offset] -= 8
                self.load(0xC30, positions)
            if not sim.peek("full_dirty")[0]:
                break
        else:
            self.fail("Actor rebuild did not finish")
        actual = sim.dump()
        self.call("video_restore")
        self.call("video_sprites")
        fresh = sim.dump()
        self.assertEqual(actual[0x1000:0x1C40], fresh[0x1000:0x1C40])
        self.assertEqual(actual[0x9600:0x9700], fresh[0x9600:0x9700])


if __name__ == "__main__":
    unittest.main(verbosity=2)
