#!/usr/bin/env python3
"""Exercise the assembled sound player and background priorities in vicsim."""
import sys
import unittest

from bot import Sim
import mkdata
import mksound


class SoundTest(unittest.TestCase):
    def setUp(self):
        self.sim = Sim()
        self.sim.run(120)
        self.sim.joy("F")
        self.sim.run(2)
        self.sim.joy("")
        self.sim.run(2)
        self.poke("mtimer", [255, 255])  # stay in READY while auditioning

    def tearDown(self):
        self.sim.p.stdin.write("quit\n")
        self.sim.p.stdin.flush()
        self.sim.p.wait()
        for stream in (self.sim.p.stdin, self.sim.p.stdout, self.sim.p.stderr):
            stream.close()

    def poke(self, name, values):
        addr = self.sim.labels.get(name, name)
        for i, value in enumerate(values):
            self.sim.cmd(f"poke ${addr + i:04X} {value}")

    def install(self, name, voice, loop=False):
        self.poke("fx_on", [0] * 4)
        self.poke("bg_on", [0] * 4)
        addr = self.sim.labels["snd_" + name.lower()]
        if loop:
            for stem in ("bg_", "bg_p"):
                self.poke(self.sim.labels[stem + "lo"] + voice, [addr & 255])
                self.poke(self.sim.labels[stem + "hi"] + voice, [addr >> 8])
            self.poke(self.sim.labels["bg_cnt"] + voice, [0])
            self.poke(self.sim.labels["bg_on"] + voice, [1])
        else:
            self.poke(self.sim.labels["fx_lo"] + voice, [addr & 255])
            self.poke(self.sim.labels["fx_hi"] + voice, [addr >> 8])
            self.poke(self.sim.labels["fx_cnt"] + voice, [0])
            self.poke(self.sim.labels["fx_on"] + voice, [1])

    def output(self):
        self.sim.cmd("until read_joy 2")  # sound_update has written all voices
        return self.sim.peek(0x900A, 4)

    def test_stream_durations_loops_and_termination(self):
        voices = {"JINGLE_B": 0, "CHOMP1": 1, "CHOMP2": 1, "EAT": 1, "BONUS": 1}
        loops = {"FRIGHT", "EYES", *(f"SIREN{i}" for i in range(1, 6))}
        for name, pairs in mksound.SOUNDS.items():
            with self.subTest(sound=name):
                voice = 0 if name.startswith("SIREN") else voices.get(name, 2)
                expected = [value for value, frames in pairs for _ in range(frames)]
                self.sim.cmd("until sound_update 2")
                self.install(name, voice, name in loops)
                expected = expected * 2 + expected[:2] if name in loops else expected + [0]
                for value in expected:
                    actual = self.output()
                    self.assertEqual(actual[voice], value, name)
                    self.assertTrue(all(v == 0 for i, v in enumerate(actual) if i != voice), name)
                    self.sim.cmd("until sound_update 2")
                if name not in loops:
                    self.assertEqual(self.sim.peek(self.sim.labels["fx_on"] + voice), [0])

    def test_fright_and_eyes_replace_all_five_sirens(self):
        ids = {name: i for i, name in enumerate(mksound.SOUNDS)}
        self.poke("mode", [2])
        cases = [(mkdata.maze_tables()[3] * n // 5 - 1, 0, 0, f"SIREN{6-n}")
                 for n in range(4, 0, -1)]
        cases.insert(0, (mkdata.maze_tables()[3], 0, 0, "SIREN1"))
        cases += [(100, 200, 0, "FRIGHT"), (100, 200, 3, "EYES"),
                  (100, 0, 3, "EYES"), (100, 0, 0, "SIREN3")]
        for dots, fright, estate, name in cases:
            with self.subTest(background=name):
                self.sim.cmd("until play_sounds_bg 2")
                self.poke("dots_left", [dots])
                self.poke("ftimer", [fright, 0])
                self.poke("estate", [estate, 0, 0, 0])
                self.sim.cmd("until collide 2")
                actual = self.sim.peek("bg_id", 3)
                if name.startswith("SIREN"):
                    self.assertEqual((actual[0], actual[2]), (ids[name], 255))
                else:
                    self.assertEqual((actual[0], actual[2]), (255, ids[name]))

    def test_intro_and_pitch_landmarks(self):
        length = lambda name: sum(c for _, c in mksound.SOUNDS[name])
        self.assertEqual(length("JINGLE_S"), 249)
        self.assertEqual(length("JINGLE_B"), 257)
        self.assertEqual(length("CHOMP1"), 6)
        self.assertEqual(length("BONUS"), 24)
        self.assertEqual(length("EAT"), 33)
        self.assertEqual(length("DEATH"), 91)
        for name, voice, target in (("CHOMP1", "alto", 984.375),
                                    ("FRIGHT", "sop", 281.25),
                                    ("EYES", "sop", 2484.375)):
            value = mksound.SOUNDS[name][0][0]
            actual = mksound.CLK[voice] / (255 - value)
            self.assertLess(abs(actual / target - 1), 0.08, name)

    def assert_alto_effect(self, name):
        self.assertEqual(self.sim.peek("fx_on", 4), [0, 1, 0, 0])
        low = self.sim.peek(self.sim.labels["fx_lo"] + 1)[0]
        high = self.sim.peek(self.sim.labels["fx_hi"] + 1)[0]
        self.assertEqual(low | high << 8, self.sim.labels["snd_" + name])

    def test_fruit_pickup_uses_alto(self):
        self.poke("fx_on", [0] * 4)
        self.poke("mode", [2])
        self.sim.cmd("until bonus_update 2")
        self.poke("pt_c", [mkdata.BONUS_TILE[0]])
        self.poke("pt_r", [mkdata.BONUS_TILE[1]])
        self.poke("bshown", [1])
        self.sim.cmd("until play_sounds_bg 2")
        self.assert_alto_effect("bonus")
        self.assertEqual(self.sim.peek("bshown"), [0])

    def test_ghost_eaten_uses_alto(self):
        self.poke("fx_on", [0] * 4)
        self.poke("mode", [2])
        self.sim.cmd("until collide 2")
        self.poke("estate", [2, 0, 0, 0])
        self.poke("efright", [1, 0, 0, 0])
        self.poke("ex", self.sim.peek("px"))
        self.poke("ey", self.sim.peek("py"))
        self.sim.cmd("until build_eat 2")
        self.assert_alto_effect("eat")


if __name__ == "__main__":
    unittest.main()
