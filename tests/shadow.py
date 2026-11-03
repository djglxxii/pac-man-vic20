#!/usr/bin/env python3
"""Exercise the original renderer with its temporary visible character copies."""
import random
import unittest

import native
import render
from native import ROOT, WORK

PRG = ROOT / 'build/pacman-shadow.prg'
NativeSim = native.Sim


def preview_sim(prg=None):
    return NativeSim(prg or PRG)


class ShadowParity(native.NativeParity):
    def test_03_build_memory_limits(self):
        raw = (ROOT / 'build/ghost-shadow/pacman-native.bin').read_bytes()
        self.assertEqual(len(raw), 33792)
        self.assertEqual(self.sim.labels['__shadow_glyphs'], 0x1d40)
        self.assertEqual(self.sim.labels['__shadow_capacity'], 24)
        self.assertEqual(self.sim.labels['__stack_bottom'], 0x1ec0)
        self.assertEqual(self.sim.labels['__stack'], 0x2000)
        self.assertLessEqual(0x1201 + len(PRG.read_bytes()) - 2, 0x8000)


class ShadowRenderer(render.Renderer):
    """Run the complete original bitmap/colour/overlap oracle on this target."""


class HiddenPixels(unittest.TestCase):
    def test_old_pixels_survive_restore_until_publication(self):
        sim = preview_sim()
        WORK.mkdir(parents=True, exist_ok=True)
        path = WORK / 'shadow-fixture.bin'
        rng = random.Random(212)

        def load(address, data):
            path.write_bytes(data)
            sim.cmd(f'load ${address:x} {path.relative_to(ROOT)}')

        def displayed(memory):
            return b''.join(memory[0x1000 + code * 16:0x1010 + code * 16]
                            for code in memory[0x200:0x2c4])

        def packet(actors):
            attrs, positions = bytearray(16), bytearray(16)
            for off, (code, flip, pal, raw_x, raw_y) in zip(range(12, 0, -2), actors):
                attrs[off:off+2] = bytes((code * 4 + flip, pal))
                positions[off:off+2] = bytes((raw_x, raw_y))
            load(0xc20, attrs)
            load(0xc30, positions)

        try:
            sim.cmd('run 500')
            sim.cmd('until frame_wait 100')
            sim.cmd('call video_restore')
            sim.cmd('poke full_dirty 0')
            sim.cmd('poke dirty_count 0')
            sim.cmd('poke maze_flash 0')
            background = bytes(rng.randrange(256) for _ in range(3136))
            load(0x1000, background)
            guard = bytes(rng.randrange(256) for _ in range(16))
            load(0x1ec0, guard)
            fixed = bytes(col * 14 + row for row in range(14) for col in range(14))
            actors = [[32, 0, 1, 239 - 2*x - (off <= 4), raw_y]
                      for off, (x, raw_y) in zip(range(12, 0, -2),
                          ((10, 216), (42, 216), (74, 216),
                           (10, 112), (42, 112), (74, 112)))]
            packet(actors)
            sim.cmd('call video_sprites')
            for scene in range(121):
                before = sim.dump()
                if scene == 0:
                    for actor in actors: actor[3] -= 2
                else:
                    for actor in actors:
                        actor[:] = [rng.randrange(64), rng.randrange(4), rng.randrange(32),
                                    rng.choice((1, 15, 128, 157, 175, 224, 238, 253, 255)),
                                    rng.randrange(256)]
                packet(actors)
                sim.cmd('call video_update_begin')
                hidden = sim.dump()
                count = hidden[sim.labels['shadow_count']]
                self.assertLessEqual(count, 24, scene)
                if scene == 0: self.assertEqual(count, 24)
                self.assertEqual(displayed(hidden), displayed(before), scene)
                self.assertEqual(hidden[0x1ec0:0x1ed0], guard)
                sim.cmd('call video_update_end')
                published = sim.dump()
                self.assertEqual(published[0x200:0x2c4], fixed, scene)
                self.assertEqual(published[sim.labels['shadow_count']], 0)
                self.assertEqual(published[0x1ec0:0x1ed0], guard)
            # An explicit restore must also release a pending display copy.
            packet([])
            sim.cmd('call video_update_begin')
            sim.cmd('call video_restore')
            self.assertEqual(sim.peek(0x200, 196), fixed)
            self.assertEqual(sim.peek('shadow_count'), b'\0')
            self.assertEqual(sim.peek(0x1000, 3136), background)
            # Full rebuilds and completion flashes intentionally use the old path.
            for flag in ('full_dirty', 'maze_flash'):
                sim.cmd(f'poke {flag} 1')
                sim.cmd('call shadow_begin')
                self.assertEqual(sim.peek('shadow_count'), b'\0')
                sim.cmd(f'poke {flag} 0')
        finally:
            sim.close()


if __name__ == '__main__':
    native.Sim = render.Sim = preview_sim
    unittest.main(verbosity=2)
