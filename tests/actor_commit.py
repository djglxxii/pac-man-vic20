#!/usr/bin/env python3
"""Check independent transactions against the original pixel/colour oracle."""
import argparse
from pathlib import Path
import sys
import unittest

import native
import render
from native import ROOT, WORK

PRG = ROOT / 'build/actor-commit/after/pacman.prg'
NativeSim = native.Sim


def preview_sim(prg=None):
    return NativeSim(prg or PRG)


class ActorCommitParity(native.NativeParity):
    def test_03_build_memory_limits(self):
        image = PRG.with_name('pacman-native.bin').read_bytes()
        self.assertEqual(len(image), 33792)
        self.assertLessEqual(self.sim.labels['__bss_end'], 0x8000)
        self.assertEqual(self.sim.labels['__stack'], 0x2000)
        sim = preview_sim()
        try:
            sim.cmd('until boot_start 300')
            for start, size, offset in ((0x2000, 0x6000, 0),
                                        (0xa000, 0x2000, 0x6000),
                                        (0x400, 0x400, 0x8000)):
                self.assertEqual(sim.peek(start, size), image[offset:offset+size])
        finally:
            sim.close()


class ActorCommitRenderer(render.Renderer):
    """Run inherited checks, including incremental parity through video_refresh."""

    def check_scene(self, *args, **kwargs):
        kwargs['refresh'] = True
        return super().check_scene(*args, **kwargs)

    @staticmethod
    def actors(points):
        return [[32+i % 6, 0, (1, 3, 5, 7, 9, 25)[i],
                 (239 - 2*x - (off <= 4)) & 255, raw_y]
                for i, (off, (x, raw_y)) in
                enumerate(zip(range(12, 0, -2), points))]

    def transaction(self, actors, name):
        for flag in ('full_dirty', 'dirty_count', 'rebuild_phase', 'maze_flash'):
            self.sim.cmd(f'poke {flag} 0')
        trace = WORK / f'commit-{name}.trace'
        self.sim.cmd(f'trace {trace}')
        self.check_scene(actors, incremental=True, retain=True)
        self.sim.cmd('trace off')
        return [event for _, event in map(str.split, trace.read_text().splitlines())
                if event.startswith('actor-')]

    def test_07_separated_actors_commit_before_next_erase(self):
        old = self.actors(((10, 216), (42, 216), (74, 216)))
        self.check_scene(old, retain=True)
        moved = [actor[:3] + [(actor[3]-2) & 255, actor[4]] for actor in old]
        events = self.transaction(moved, 'separated')
        self.assertEqual(len(events), 6, events)
        for erase, paint in zip(events[::2], events[1::2]):
            self.assertTrue(erase.endswith('-erase'), events)
            self.assertEqual(paint, erase.replace('-erase', '-paint'), events)

    def test_08_disjoint_pixels_sharing_restore_bytes_stay_together(self):
        old = self.actors(((32, 216), (40, 216), (80, 216)))
        self.check_scene(old, retain=True)
        changed = [a.copy() for a in old]
        for actor in changed:
            actor[1] ^= 1
        events = self.transaction(changed, 'shared-bytes')
        shared = [event for event in events if event.split('-')[1] in ('0', '1')]
        self.assertEqual(len(shared), 4, events)
        self.assertTrue(all(event.endswith('-erase') for event in shared[:2]), events)
        self.assertTrue(all(event.endswith('-paint') for event in shared[2:]), events)

    def test_09_old_new_crossing_and_colour_only_dependencies(self):
        cases = (
            (((32, 216), (64, 216)), ((64, 216), (32, 216))),
            # y=40..51 and 52..63 share colours despite disjoint bitmap rows.
            (((32, 218), (32, 202)), ((33, 218), (33, 202))),
            (((-3, 216), (6, 216), (108, 216)),
             ((2, 216), (-3, 216), (111, 216))),
        )
        for case, (old, new) in enumerate(cases):
            with self.subTest(case=case):
                self.sim.cmd('call video_restore')
                self.setUp()
                self.check_scene(self.actors(old), retain=True)
                events = self.transaction(self.actors(new), f'crossing-{case}')
                if case < 2:
                    self.assertTrue(all(e.endswith('-erase') for e in events[:2]), events)
                    self.assertTrue(all(e.endswith('-paint') for e in events[2:]), events)
                self.sim.cmd('call video_restore')
                actual = self.sim.dump()
                self.assertEqual(actual[0x1000:0x1c40], self.background)
                self.assertEqual(actual[0x9600:0x9700], self.cell_colors)

    def test_10_transitive_cluster_preserves_priority(self):
        actors = self.actors(((10, 216), (23, 216), (31, 216), (88, 216)))
        self.check_scene(actors, retain=True)
        for actor in actors:
            actor[1] ^= 1
        events = self.transaction(actors, 'transitive')
        cluster = [e for e in events if e.split('-')[1] in ('0', '1', '2')]
        self.assertEqual(len(cluster), 6, events)
        self.assertTrue(all(e.endswith('-erase') for e in cluster[:3]), events)
        self.assertTrue(all(e.endswith('-paint') for e in cluster[3:]), events)

    def test_11_reward_appears_with_no_underlay_in_borrowed_slot(self):
        # A newly borrowed slot can have no previous visible actor. Exercise
        # live refresh, rather than the full sprite painter used by the atlas
        # checks, so both halves must enter dependency construction immediately.
        for hole in (2, 10):
            for off in (2, 4, 6, 8, 10):
                if off == hole:
                    continue
                for code in range(40, 44):
                    for shift in (0, 5):
                        with self.subTest(hole=hole, slot=off, code=code, shift=shift):
                            self.setUp()
                            for flag in ('full_dirty', 'dirty_count', 'rebuild_phase', 'maze_flash'):
                                self.sim.cmd(f'poke {flag} 0')
                            old = [[32, 0, 0, 159, 168] for _ in range(6)]
                            other = 2 if hole == 10 else 10
                            old[(12-other)//2][:] = [32, 0, 9,
                                (239-(other <= 4)-2*88) & 255, 168]
                            actor = old[(12-off)//2]
                            actor[:] = [32, 0, 1,
                                        (239-(off <= 4)-2*(32+shift)) & 255, 168]
                            self.check_scene(old, retain=True)
                            new = [a.copy() for a in old]
                            new[(12-off)//2][:3] = [code, 0, 24]
                            self.check_scene(new, incremental=True, retain=True)
                            self.sim.cmd('call video_restore')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--prg', type=Path)
    args, rest = parser.parse_known_args()
    if args.prg is not None:
        PRG = args.prg.resolve()
    native.Sim = render.Sim = preview_sim
    unittest.main(argv=[sys.argv[0], *rest], verbosity=2)
