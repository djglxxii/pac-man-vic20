#!/usr/bin/env python3
"""Exercise bonus lettering through the compiled game's message painter."""
import unittest

from native import Sim, ROOT

OUT = ROOT / "build/font-study/checks"


def offset(x, y):
    return (29 - x) * 32 + y - 2


class FontMessages(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.sim = Sim()
        self.sim.cmd("run 500")
        self.sim.cmd("until frame_wait 100")
        self.sim.cmd("call video_restore")
        blank = OUT / "blank.bin"
        blank.write_bytes(bytes([64]) * 1024 + bytes([3]) * 1024)
        self.sim.cmd(f"load $0400 {blank}")
        self.sim.cmd("poke full_dirty 2")
        self.sim.finish_background()

    def tearDown(self):
        self.sim.close()

    def test_01_all_fruit_values_and_erase_footprints(self):
        sim = self.sim
        state = sim.peek(0xC00, 768), sim.peek(0xA0, 96)
        for message, value in enumerate((100, 300, 500, 700, 1000, 2000, 3000, 5000), 0x1b):
            with self.subTest(value=value):
                sim.cmd(f"call displayMsg_2c5e {message}")
                actual = [sim.peek(0x400 + offset(x, 20))[0] for x in range(12, 16)]
                expected = [64 if char == " " else int(char) for char in str(value).rjust(4)]
                self.assertEqual(actual, expected)
                sim.cmd("call video_background")
                self.assertEqual(sim.peek("dirty_count"), b"\0")
                pixels = sim.peek(0x1000, 3136)
                # The complete popup stays inside the existing four-tile space.
                self.assertTrue(any(pixels))
                for column in range(14):
                    for row in range(224):
                        if column not in (6, 7) or not 120 <= row < 126:
                            self.assertEqual(pixels[column * 224 + row], 0)
                # Both existing removal paths must clear even the widest value.
                for removal in (0x9b, 0xa2):
                    sim.cmd(f"call displayMsg_2c5e {removal}")
                    sim.cmd("call video_background")
                    self.assertEqual(sim.peek(0x1000, 3136), bytes(3136))
                    self.assertEqual([sim.peek(0x800 + offset(x, 20))[0]
                                      for x in range(12, 16)], [0x90] * 4)
                    sim.cmd(f"call displayMsg_2c5e {message}")
                    sim.cmd("call video_background")
                sim.cmd("call displayMsg_2c5e 155")
                sim.cmd("call video_background")
        self.assertEqual((sim.peek(0xC00, 768), sim.peek(0xA0, 96)), state)

    def test_02_ghost_chain_keeps_original_score_frames(self):
        sim = self.sim
        for count, code in enumerate((40, 41, 42, 43), 1):
            with self.subTest(points=200 << (count - 1)):
                for address in (0xa5, 0xab, 0xac, 0xad, 0xae, 0xaf):
                    sim.cmd(f"poke ${address:x} 0")
                sim.cmd("poke $a4 1")  # Blinky is the eaten ghost.
                sim.cmd(f"poke $d0 {count}")
                sim.cmd("poke $d1 0")
                sim.cmd("call updateGhostStates_1017")
                self.assertEqual(sim.peek(0xC02, 2), bytes((code, 24)))
                self.assertEqual(sim.peek(0xD1), b"\x01")
                sim.cmd("poke $d1 2")
                sim.cmd("call updateGhostStates_1017")
                self.assertEqual(sim.peek(0xC02), b"\x20")
                self.assertEqual(sim.peek(0xD1), b"\0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
