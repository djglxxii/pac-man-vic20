#!/usr/bin/env python3
"""Check the real loader, startup lifetime handoff and original stack bounds."""
import json
import unittest

from native import BUILD, Sim, WORK
from performance import start_game


class Memory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)

    def test_01_loader_delivers_all_three_regions_before_boot(self):
        sim = Sim()
        try:
            sim.cmd("until boot_start 300")
            raw = sim.native_binary.read_bytes()
            actual = sim.dump()
            self.assertEqual(actual[0x2000:0x8000], raw[:0x6000])
            self.assertEqual(actual[0xA000:0xC000], raw[0x6000:0x8000])
            self.assertEqual(actual[0x0400:0x0800], raw[0x8000:0x8400])
            self.assertEqual(sim.labels["boot_start"], 0x0400)
            self.assertLessEqual(sim.labels["__boot_end"], 0x0800)
            self.assertEqual(sim.labels["__boot_limit"], 0x0800)
            for routine in ("boot_start", "platform_init"):
                self.assertTrue(0x0400 <= sim.labels[routine] < 0x0800)
            self.assertTrue(0x2000 <= sim.labels["main"] < 0x8000)
        finally:
            sim.close()

    def test_02_cold_ram_is_reused_after_startup(self):
        sim = Sim()
        try:
            WORK.mkdir(parents=True, exist_ok=True)
            path = WORK / "cold.bin"
            path.write_bytes(bytes([0xA5]) * 0xC00)
            sim.cmd(f"load $0400 {path}")
            sim.cmd("until main 300")
            self.assertEqual(json.loads(sim.cmd("boot")[0]),
                             {"entries": 1, "released": False})
            # The guard activates when main actually executes its first opcode.
            sim.cmd("until frame_wait 100")
            boot = sim.native_binary.read_bytes()[0x8000:0x8400]
            self.assertNotEqual(sim.peek(0x0400, 1024), boot)
            self.assertNotEqual(sim.peek(0x0800, 1024), bytes([0xA5]) * 1024)
            start_game(sim)
            sim.cmd("run 600")
            self.assertEqual(json.loads(sim.cmd("boot")[0]),
                             {"entries": 1, "released": True})
        finally:
            sim.close()

    def test_03_stack_tracking_excludes_host_canaries(self):
        sim = Sim()
        try:
            start_game(sim)
            bottom = sim.labels.get("__stack_bottom", 0x1d40)
            sim.cmd("stack reset")
            sim.cmd(f"poke ${bottom:x} 165")
            sim.cmd("poke $100 165")
            self.assertEqual(json.loads(sim.cmd("stack")[0])["software_bytes_written"], 0)
            self.assertEqual(json.loads(sim.cmd("stack")[0])["hardware_bytes_written"], 0)
            sim.cmd("run 600")
            stack = json.loads(sim.cmd("stack")[0])
            self.assertGreater(stack["software_bytes_written"], 0)
            self.assertGreaterEqual(stack["software_lowest_write"], bottom + 16)
            self.assertGreater(stack["hardware_bytes_written"], 0)
            self.assertEqual(sim.peek(bottom), b"\xa5")
        finally:
            sim.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
