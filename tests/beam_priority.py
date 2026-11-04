#!/usr/bin/env python3
"""Check the current-artwork beam trials, focus selection and complete windows."""
import argparse
import json
from pathlib import Path
import unittest

import beam
import native
import render
from native import ROOT, WORK

PRG = ROOT / 'build/beam-priority/strict/pacman.prg'


class Parity(beam.BeamParity):
    def test_03_build_memory_limits(self):
        raw = PRG.with_name('pacman-native.bin').read_bytes()
        self.assertEqual(len(raw), 33792)
        sim = self.sim
        self.assertLessEqual(sim.labels['__bss_end'], 0x8000)
        self.assertEqual(sim.labels['__stack_bottom'], 0x1f80)
        self.assertLessEqual(sim.labels['beam_state_end'], 0x1d90)
        code, load, size = [sim.labels[n] for n in
                            ('__beam_code_start', '__beam_code_load', '__beam_code_size')]
        self.assertEqual(sim.peek(code, size), raw[0x8000+load-0x400:0x8000+load-0x400+size])
        self.assertLessEqual(load + size, 0x800)
        self.assertLessEqual(code + size, sim.labels['__stack_bottom'])


class Renderer(beam.BeamRenderer):
    def check_scene(self, *args, **kwargs):
        kwargs['refresh'] = True
        return super().check_scene(*args, **kwargs)

    def test_09_focus_order_and_nearby_windows(self):
        if 'beam_focus' not in self.sim.labels:
            self.skipTest('Unprioritized reference')
        # Actor lists run from output slot 12 down to 2. Pac-Man is slot 10,
        # a nearby independent ghost is slot 8, and a distant one is slot 2.
        old = [(0, 0, 0, 0, 0), (48, 0, 9, 95, 216),
               (32, 0, 3, 95, 184), (0, 0, 0, 0, 0),
               (0, 0, 0, 0, 0), (32, 0, 1, 222, 216)]
        self.check_scene(old, retain=True)
        for flag in ('full_dirty', 'dirty_count', 'rebuild_phase', 'maze_flash'):
            self.sim.cmd(f'poke {flag} 0')
        changed = [a[:1] + (a[1] ^ 1,) + a[2:] if a[2] else a for a in old]
        trace = WORK / 'focused-order.trace'
        self.sim.cmd(f'trace {trace}')
        self.check_scene(changed, incremental=True, retain=True)
        self.sim.cmd('trace off')
        groups = [list(map(int, event.split('-')[2:]))
                  for _, event in map(str.split, trace.read_text().splitlines())
                  if event.startswith('beam-begin-')]
        self.assertEqual(groups[0][0], 16, groups)
        by_mask = {g[0]: g for g in groups}
        if PRG.parent.name != 'focused':
            self.assertNotEqual(groups[0][1], 255, groups)
            self.assertNotEqual(by_mask[8][1], 255)
        self.assertEqual(self.sim.peek('beam_focus')[0], 24)
        self.assertEqual(by_mask[1][1], 255)


class Groups(beam.Groups):
    # Focus trials deliberately leave distant groups unprotected. Timing is
    # still checked for every protected group, plus the exhaustive fixtures.
    minimum_live_protected_groups = 10

    def test_03_all_raster_phases_and_large_groups(self):
        sim = beam.preview_sim()
        out = PRG.parent / 'timing'
        out.mkdir(parents=True, exist_ok=True)
        path, trace = WORK / 'focus-phase.bin', out / 'phases.trace'

        def load(address, data):
            path.write_bytes(data)
            sim.cmd(f'load ${address:x} {path}')

        def packet(case, shift):
            attrs, positions = bytearray(16), bytearray(16)
            for i, (code, pal, x, y) in enumerate(case):
                off = 2 + i * 2
                attrs[off:off+2] = bytes((code * 4, pal))
                positions[off:off+2] = bytes(((x-shift) & 255, y))
            load(0xc20, attrs)
            load(0xc30, positions)

        try:
            sim.cmd('run 500')
            sim.cmd('until frame_wait 100')
            sim.cmd('call video_restore')
            for name in ('full_dirty', 'dirty_count', 'rebuild_phase', 'maze_flash'):
                sim.cmd(f'poke {name} 0')
            # Isolated manual-render fixture: $0800 is logical maze RAM,
            # deliberately replaced by a test delay. No game logic runs here.
            scratch = 0x800
            load(scratch, bytes((0xa8, 0xc0, 0, 0xf0, 3, 0x88, 0xd0, 0xfd,
                                 0xe0, 0, 0xf0, 8, 0xa0, 0, 0x88, 0xd0, 0xfd,
                                 0xca, 0xd0, 0xf8, 0x60)))
            cases = [[(48, 9, 175, y)] for y in (0, 16, 80, 216, 255)]
            cases += [[(48, 9, 250, 80)],
                      [(48, 9, 175, 216), (32, 1, 175, 184), (32, 3, 220, 80)],
                      [(48 if i == 0 else 32, 9 if i == 0 else 1,
                        175+i*2, 0) for i in range(5)],
                      [(48 if i == 0 else 32, 9 if i == 0 else 1,
                        175+i*2, 0) for i in range(6)]]
            sim.cmd(f'trace {trace}')
            for case in cases:
                sim.cmd('call video_restore')
                packet(case, 0)
                sim.cmd('call video_sprites')
                for phase in range(131):
                    packet(case, 2 * ((phase+1) & 1))
                    cycles = int(sim.cmd('stats')[0].split()[1])
                    delta = (phase*130 - cycles % 16965) % 16965
                    coarse, fine = divmod(delta, 1284)
                    sim.cmd(f'call ${scratch:x} {fine // 5} {coarse}')
                    sim.cmd('call video_refresh')
            sim.cmd('trace off')
            protected, fallback, largest = 0, 0, 0
            for line in trace.read_text().splitlines():
                cycles, event = line.split()
                cycles = int(cycles)
                if event.startswith('beam-begin-'):
                    mask, early, top, end, budget = map(int, event.split('-')[2:])
                    start = cycles
                elif event == 'beam-end':
                    if early == 255:
                        fallback += 1
                        continue
                    protected += 1
                    largest = max(largest, mask.bit_count())
                    self.assertLess(cycles-start, budget*130)
                    for line_no in range(start//65, cycles//65+1):
                        self.assertFalse(top*2 <= line_no % 261 < end*2-2)
            self.assertGreater(protected, 100 if PRG.parent.name == 'focused' else 900)
            self.assertGreaterEqual(fallback, 131)
            self.assertEqual(largest, 5)
            report = dict(phase_fixture_calls=len(cases)*131,
                          protected_groups=protected, fallback_groups=fallback,
                          largest_protected_group=largest)
            (out/'phase-summary.json').write_text(json.dumps(report, indent=2)+'\n')
            print(json.dumps(report, indent=2))
        finally:
            sim.close()

    def test_04_player_slot_and_nearby_boundaries(self):
        sim = beam.preview_sim()
        path = WORK / 'focus-cache.bin'

        def load(label, values):
            path.write_bytes(bytes(values))
            sim.cmd(f'load ${sim.labels[label]:x} {path}')

        try:
            sim.cmd('run 500')
            sim.cmd('until frame_wait 100')
            if 'beam_focus' not in sim.labels:
                self.skipTest('Unprioritized reference')
            for slot in (2, 10):
                for px, py in ((50, 100), (-5, 13), (105, 204)):
                    for dx, dy in ((0, 0), (24, 32), (-24, -32),
                                   (25, 0), (0, 33), (-25, 0), (0, -33), (0, 191)):
                        gx, gy = px+dx, py+dy
                        if not (-8 <= gx <= 119 and 13 <= gy <= 204):
                            continue
                        pal, attr, xs, ys = [bytearray(14) for _ in range(4)]
                        ghost = 10 if slot == 2 else 2
                        pal[slot], attr[slot] = 9, 48*4
                        pal[ghost], attr[ghost] = 1, 32*4
                        xs[slot], ys[slot] = px & 255, py
                        xs[ghost], ys[ghost] = gx & 255, gy
                        for label, values in zip(('cache_pal', 'cache_attr', 'new_x', 'new_y'),
                                                 (pal, attr, xs, ys)):
                            load(label, values)
                        sim.cmd('call beam_focus_priorities')
                        player = 1 << (slot//2-1)
                        expected = player
                        if abs(dx) <= 24 and abs(dy) <= 32:
                            expected |= 1 << (ghost//2-1)
                        self.assertEqual(sim.peek('beam_player')[0], player)
                        self.assertEqual(sim.peek('beam_focus')[0], expected,
                                         (slot, px, py, dx, dy))
            load('cache_pal', bytearray(14))
            sim.cmd('call beam_focus_priorities')
            self.assertEqual(sim.peek('beam_focus')[0], 0)
        finally:
            sim.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prg', type=Path, default=PRG)
    args, remaining = parser.parse_known_args()
    PRG = args.prg.resolve()
    beam.PRG = PRG
    beam.OUTPUT = PRG.parent
    native.Sim = render.Sim = beam.preview_sim
    unittest.main(argv=[__file__] + remaining, verbosity=2)
