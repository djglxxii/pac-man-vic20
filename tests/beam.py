#!/usr/bin/env python3
"""Original bitmap/colour parity plus live beam-window coverage and bounds."""
import json
from pathlib import Path
import random
import unittest

import native
import render
from native import ROOT, WORK
from performance import start_game, CPU_HZ

PRG = ROOT / 'build/pacman-beam.prg'
NativeSim = native.Sim


def preview_sim(prg=None):
    return NativeSim(prg or PRG)


class BeamParity(native.NativeParity):
    def test_03_build_memory_limits(self):
        raw = (ROOT / 'build/beam-follow/pacman-native.bin').read_bytes()
        self.assertEqual(len(raw), 33792)
        sim = self.sim
        self.assertEqual(sim.labels['__stack_bottom'], 0x1f00)
        self.assertLessEqual(sim.labels['beam_state_end'], 0x1dc0)
        code = sim.labels['__beam_code_start']
        load = sim.labels['__beam_code_load']
        size = sim.labels['__beam_code_size']
        self.assertEqual(sim.peek(code, size), raw[0x8000 + load - 0x400:0x8000 + load - 0x400 + size])
        self.assertLessEqual(load + size, 0x800)
        self.assertLessEqual(code + size, sim.labels['__stack_bottom'])


class BeamRenderer(render.Renderer):
    """The complete existing independent pixel/colour and clipping oracle."""


class Groups(unittest.TestCase):
    def test_03_all_raster_phases_and_large_groups(self):
        sim = preview_sim()
        out = ROOT / 'build/beam-follow/timing'
        out.mkdir(parents=True, exist_ok=True)
        path, trace = WORK / 'phase.bin', out / 'phases.trace'

        def load(address, data):
            path.write_bytes(data)
            sim.cmd(f'load ${address:x} {path.relative_to(ROOT)}')

        def packet(case, shift):
            attrs, positions = bytearray(16), bytearray(16)
            for i, (code, flip, pal, x, y) in enumerate(case):
                off = 2 + i * 2
                attrs[off:off+2] = bytes((code * 4 + flip, pal))
                positions[off:off+2] = bytes((x - shift, y))
            load(0xc20, attrs); load(0xc30, positions)

        try:
            sim.cmd('run 500'); sim.cmd('until frame_wait 100')
            sim.cmd('call video_restore')
            for name in ('full_dirty', 'dirty_count', 'rebuild_phase', 'maze_flash'):
                sim.cmd(f'poke {name} 0')
            # A test-only delay advances the emulated beam without executing
            # game logic. Fine delay uses A, coarse delay X (1284 cycles/unit).
            # It occupies unused RAM above the copied helper, below the stack.
            scratch = (sim.labels['__beam_code_start'] + sim.labels['__beam_code_size'] + 15) & ~15
            delay = bytes((0xa8, 0xc0, 0, 0xf0, 3, 0x88, 0xd0, 0xfd,
                           0xe0, 0, 0xf0, 8, 0xa0, 0, 0x88, 0xd0, 0xfd,
                           0xca, 0xd0, 0xf8, 0x60))
            self.assertLessEqual(scratch + len(delay), sim.labels['__stack_bottom'])
            load(scratch, delay)
            cases = [[(32, 0, 1, 175, 216)], [(32, 3, 1, 250, 40)],
                     [(32, 3, 1, 17, 0)], [(38, 3, 25, 175, 80)],
                     [(47, 3, 9, 175, 16)],
                     [(32+i, 1, 1+i*2, 175+i*2, 216) for i in range(4)],
                     [(32+i, 1, 1+i*2, 175+i*2, 216) for i in range(5)],
                     [(32+i, 1, 1+i*2, 175+i*2, 216) for i in range(6)]]
            sim.cmd('trace ' + str(trace.relative_to(ROOT)))
            for case in cases:
                sim.cmd('call video_restore')
                packet(case, 0); sim.cmd('call video_sprites')
                for phase in range(131):
                    packet(case, 2 * ((phase + 1) & 1))
                    cycles = int(sim.cmd('stats')[0].split()[1])
                    delta = (phase * 130 - cycles % 16965) % 16965
                    coarse, fine = divmod(delta, 1284)
                    sim.cmd(f'call ${scratch:x} {fine // 5} {coarse}')
                    sim.cmd('call video_refresh')
            sim.cmd('trace off')
            active, protected, fallback, largest = None, 0, 0, 0
            for line in trace.read_text().splitlines():
                cycles, event = line.split(); cycles = int(cycles)
                if event.startswith('beam-begin-'):
                    mask, early, top, end, budget = map(int, event.split('-')[2:])
                    active = (cycles, mask, early, top, end, budget)
                elif event == 'beam-end':
                    start, mask, early, top, end, budget = active
                    if early == 255:
                        fallback += 1
                    else:
                        protected += 1; largest = max(largest, mask.bit_count())
                        self.assertLess(cycles - start, budget * 130, active)
                        for line_no in range(start // 65, cycles // 65 + 1):
                            self.assertFalse(top * 2 <= line_no % 261 < end * 2 - 2, active)
                    active = None
            self.assertGreater(protected, 800)
            self.assertEqual(largest, 5)
            self.assertGreaterEqual(fallback, 131)
            report = {'phase_fixture_calls': len(cases) * 131,
                      'protected_groups': protected, 'fallback_groups': fallback,
                      'largest_protected_group': largest,
                      'all_protected_groups_within_budget_and_outside_colour_rows': True}
            (out / 'phase-summary.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
        finally:
            sim.close()

    def test_01_grouped_updates_match_original(self):
        sim, reference = preview_sim(), NativeSim()
        path = WORK / 'beam.bin'
        rng = random.Random(261)

        def load(engine, address, data):
            path.write_bytes(data)
            engine.cmd(f'load ${address:x} {path.relative_to(ROOT)}')

        try:
            WORK.mkdir(parents=True, exist_ok=True)
            background = bytes(rng.randrange(256) for _ in range(3136))
            colours = bytes(rng.randrange(8) for _ in range(256))
            for engine in (sim, reference):
                engine.cmd('run 500')
                engine.cmd('until frame_wait 100')
                engine.cmd('call video_restore')
                for name in ('full_dirty', 'dirty_count', 'rebuild_phase', 'maze_flash'):
                    engine.cmd(f'poke {name} 0')
                load(engine, 0x1000, background)
                load(engine, 0x9600, colours)
            # Include separated actors, shared colour cells, chains, clipping,
            # disappearance, tunnel wrap, all artwork and large groups.
            for scene in range(480):
                attrs, positions = bytearray(16), bytearray(16)
                for i, off in enumerate(range(2, 14, 2)):
                    code = (scene + i * 7) % 64
                    pal = (25 if scene % 7 == 0 else 1 + i * 2) if scene % 19 else 0
                    if scene % 5 == 0:
                        x = 160 + i % 2 * 4
                        y = 100 + i * 3
                    elif scene % 5 == 1:
                        x, y = 210 - i * 28, 240 - i * 24
                    else:
                        x = rng.choice((1, 15, 16, 128, 157, 175, 224, 238, 239, 240, 253, 255))
                        y = rng.randrange(256)
                    attrs[off:off+2] = bytes((code * 4 + scene % 4, pal))
                    positions[off:off+2] = bytes((x, y))
                for engine in (sim, reference):
                    load(engine, 0xc20, attrs)
                    load(engine, 0xc30, positions)
                sim.cmd('call video_refresh')
                reference.cmd('call video_update_begin')
                reference.cmd('call video_update_end')
                actual, expected = sim.dump(), reference.dump()
                self.assertEqual(actual[0x1000:0x1c40], expected[0x1000:0x1c40], scene)
                self.assertEqual(actual[0x9600:0x9700], expected[0x9600:0x9700], scene)
            for engine in (sim, reference): engine.cmd('call video_restore')
            self.assertEqual(sim.peek(0x1000, 3136), background)
            self.assertEqual(sim.peek(0x9600, 256), colours)
        finally:
            sim.close(); reference.close()

    def test_02_live_groups_finish_before_beam_returns(self):
        sim = preview_sim()
        out = ROOT / 'build/beam-follow/timing'
        out.mkdir(parents=True, exist_ok=True)
        trace = out / 'play.trace'
        try:
            start_game(sim)
            sim.cmd('until frame_wait 100')
            sim.cmd('trace ' + str(trace.relative_to(ROOT)))
            sim.cmd('run 600')
            sim.cmd('trace off')
            groups, active, erases, protected_erases = [], None, 0, 0
            for line in trace.read_text().splitlines():
                cycles, event = line.split(); cycles = int(cycles)
                if event.startswith('beam-begin-'):
                    mask, early, top, end, budget = map(int, event.split('-')[2:])
                    active = {'start': cycles, 'mask': mask, 'early': early,
                              'top': top, 'end': end, 'budget': budget}
                elif event == 'beam-end':
                    self.assertIsNotNone(active)
                    active['cycles'] = cycles - active['start']
                    if active['early'] != 255:
                        self.assertLess(active['cycles'], active['budget'] * 130, active)
                        # Whole colour-cell rows must remain outside scanout
                        # throughout erasing AND drawing, not just at entry.
                        for line_no in range(active['start'] // 65, cycles // 65 + 1):
                            raster = line_no % 261
                            self.assertFalse(active['top'] * 2 <= raster < active['end'] * 2 - 2, active)
                    groups.append(active); active = None
                elif event.startswith('actor-') and event.endswith('-erase'):
                    erases += 1
                    if active is not None and active['early'] != 255: protected_erases += 1
            protected = [g for g in groups if g['early'] != 255]
            self.assertGreater(len(protected), 20)
            self.assertGreater(protected_erases, 0)
            report = {'video_frames': 600, 'groups': len(groups),
                      'protected_groups': len(protected), 'actor_erases': erases,
                      'protected_actor_erases': protected_erases,
                      'max_protected_group_cycles': max(g['cycles'] for g in protected),
                      'max_protected_group_ms': round(max(g['cycles'] for g in protected) * 1000 / CPU_HZ, 3),
                      'no_protected_group_crossed_its_colour_rows': True,
                      'all_protected_groups_within_budget': True}
            (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2))
        finally:
            sim.close()


if __name__ == '__main__':
    native.Sim = render.Sim = preview_sim
    unittest.main(verbosity=2)
