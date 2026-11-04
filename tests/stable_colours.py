#!/usr/bin/env python3
"""Exercise the isolated colour trial against independent existing oracles."""
import csv
from pathlib import Path
import sys
import unittest

import colors
import flash
import native
import rebuild
import render
from native import ROOT, WORK

PRG = ROOT/'build/stable-colours/pacman.prg'
NativeSim = native.Sim


class TrialSim(NativeSim):
    def __init__(self, prg=None):
        super().__init__(prg or PRG)

    def cmd(self, command):
        result = super().cmd(command)
        parts = command.split()
        # Existing independent fixtures explicitly replace live colour RAM.
        # Seed the trial's authoritative work page with the same background.
        if len(parts) == 3 and parts[:2] == ['load', '$9600']:
            super().cmd('load colour_work '+parts[2])
        # These are isolated helper tests. The live game publishes from
        # video_refresh, video_sprites/update_end or explicit video_restore.
        if parts[:1] == ['call'] and parts[1] in (
                'video_background', 'video_rebuild', 'bitmap_tile', 'bitmap_maze_flash'):
            super().cmd('call colour_publish')
        return result


class StableNativeParity(native.NativeParity):
    def test_03_build_memory_limits(self):
        self.assertEqual(len(PRG.with_name('pacman-native.bin').read_bytes()), 33792)
        self.assertLessEqual(self.sim.labels['__bss_end'], 0x8000)
        self.assertEqual(self.sim.labels['colour_work'], 0x9400)
        self.assertEqual(self.sim.labels['__stack'], 0x2000)


class StableRenderer(render.Renderer):
    def test_09_no_intermediate_colour_on_overlapping_actor_redraw(self):
        actors = [[32, 0, p, 175, 158] for p in (1, 3, 5, 7, 9, 25)]
        self.check_scene(actors, retain=True)
        before = self.sim.peek(0x9600, 196)
        trace = WORK/'stable-colour-writes.csv'
        self.sim.cmd(f'colours {trace}')
        changed = [a.copy() for a in actors]
        for actor in changed:
            actor[0] = 33
            actor[1] = 2
        self.check_scene(changed, incremental=True, retain=True, refresh=True)
        self.sim.cmd('colours off')
        after = self.sim.peek(0x9600, 196)
        with trace.open() as f:
            rows = list(csv.reader(f))
        self.assertTrue(rows)
        values = {}
        for _, _, cell, old, new in rows:
            cell, old, new = int(cell), int(old), int(new)
            values.setdefault(cell, set()).add(new)
            if before[cell] == after[cell]:
                self.assertEqual(new, before[cell], (cell, old, new))
        self.assertTrue(all(len(v) == 1 for v in values.values()))

    def test_10_background_queue_overflow_and_colour_read_high_bits(self):
        # Arbitrary high bits emulate the unspecified bits read from colour RAM.
        expected = bytes((i % 8) for i in range(196))
        path = WORK/'cc.bin'
        path.write_bytes(bytes(c | 0xe0 for c in expected))
        self.sim.cmd(f'load colour_work {path}')
        self.sim.cmd('poke colour_full 1')
        self.sim.cmd('call colour_publish')
        self.assertEqual(self.sim.peek(0x9600, 196), expected)
        # Helper callers that exceed the bounded live tile queue fall back
        # safely instead of writing beyond the 16-entry cell array.
        self.sim.cmd('poke colour_count 16')
        self.sim.cmd('poke v_right 0')
        self.sim.cmd(f"poke ${self.sim.labels['v_right']+1:x} 148")
        self.sim.cmd('poke v_hi 16')
        self.sim.cmd('call bitmap_cell_colour 2')
        self.assertEqual(self.sim.peek('colour_count'), b'\x10')
        self.assertEqual(self.sim.peek('colour_full'), b'\x01')
        self.sim.cmd('call colour_publish')
        self.assertEqual(self.sim.peek('colour_count'), b'\x00')
        self.assertEqual(self.sim.peek('colour_full'), b'\x00')


class StableBackgroundColors(colors.Colors):
    pass


class StableFlash(flash.MazeFlash):
    pass


class StableRebuild(rebuild.Rebuild):
    pass


if __name__ == '__main__':
    native.Sim = render.Sim = colors.Sim = flash.Sim = rebuild.Sim = TrialSim
    unittest.main(verbosity=2)
