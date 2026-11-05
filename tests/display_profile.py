#!/usr/bin/env python3
"""Check the host-side visibility classifier, including false-blink controls."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/arcade'))
from analyze_display import (WIDTH, FRAME_CYCLES, classify, summarize,
                             validate_frame_spacing, displayed_bitmap, background,
                             bitmap_points, frame_window)
from profile_game import trace_summary


def actor(x=32, y=48):
    points = {(y+dy)*WIDTH+x+dx for dy in range(12) for dx in range(2, 6)}
    return dict(x=x, y=y, points=points)


class Visibility(unittest.TestCase):
    def test_prefix_window_preserves_source_and_excludes_future_events(self):
        frames = [dict(clock=65+FRAME_CYCLES*i, line=1, cycle=0) for i in range(4)]
        events = [dict(clock=f['clock']) for f in frames]
        source = dict(frames=frames, events=events)
        selected = frame_window(source, 3)
        self.assertEqual(selected['frames'], frames[:3])
        self.assertEqual(selected['events'], events[:3])
        self.assertEqual(len(source['frames']), 4)
        self.assertEqual(len(source['events']), 4)

    def test_prefix_window_rejects_bad_limits_and_any_source_gap(self):
        frames = [dict(clock=65+FRAME_CYCLES*i, line=1, cycle=0) for i in range(4)]
        for limit in (0, 1, 5):
            with self.assertRaises(ValueError):
                frame_window(dict(frames=frames, events=[]), limit)
        # A later source gap cannot be hidden by asking for a valid prefix.
        with self.assertRaisesRegex(AssertionError, 'Missing or duplicate'):
            frame_window(dict(frames=frames[:2]+[frames[3]], events=[]), 2)

    def test_pool_display_uses_matrix_and_keeps_home_background(self):
        data = bytearray(8192 + 196)
        for row in range(14):
            for col in range(14):
                data[0x200+row*14+col] = col*14+row
        # Screen row 3, column 5 has home glyph 73, not screen index 47.
        data[0x1000+73*16] = 0x80
        data[0x200+3*14+5] = 196
        data[0x1c40] = 0xc0
        actual = displayed_bitmap(data)
        self.assertEqual(actual[5*224+3*16], 0xc0)
        self.assertEqual(sum(actual), 0xc0)
        clean = background(data, {'__pool_capacity': 60})
        self.assertEqual(clean, bitmap_points(data[0x1000:0x1c40]))
        self.assertEqual(len(clean), 1)
        self.assertEqual(len(bitmap_points(actual)), 2)

    def test_complete_old_or_new_pose_is_present(self):
        old, new = actor(), actor(34)
        for points in (old['points'], new['points']):
            r = classify([old, new], points, set(), set())
            self.assertEqual(r['status'], 'present')

    def test_absent_and_partial_have_distinct_results(self):
        a = actor()
        self.assertEqual(classify([a], set(), set(), set())['status'], 'absent')
        partial = {p for p in a['points'] if p//WIDTH % 2}
        self.assertEqual(classify([a], partial, set(), set())['status'], 'partial')

    def test_mixed_old_new_scanlines_are_partial(self):
        old, new = actor(), actor(34)
        mixed = {p for p in old['points'] if p//WIDTH < 54}
        mixed |= {p for p in new['points'] if p//WIDTH >= 54}
        self.assertEqual(classify([old, new], mixed, set(), set())['status'], 'partial')

    def test_wall_pixels_cannot_prove_actor_present(self):
        a = actor()
        wall = set(sorted(a['points'])[:16])
        self.assertEqual(classify([a], wall, wall, set())['status'], 'absent')

    def test_ambiguous_wall_and_overlap_are_excluded(self):
        a = actor()
        self.assertEqual(classify([a], a['points'], a['points'], set())['reason'],
                         'insufficient-distinct-ink')
        self.assertEqual(classify([a], a['points'], set(), {48*WIDTH+32})['reason'],
                         'shared-colour-cell')

    def test_edges_and_hidden_actors_are_excluded(self):
        a = actor(-1)
        self.assertEqual(classify([a], a['points'], set(), set())['reason'], 'screen-edge-clipping')
        self.assertEqual(classify([], set(), set(), set())['reason'], 'hidden-or-empty')

    def test_motion_does_not_bridge_unknown_frames(self):
        rows = [dict(actor='pacman', frame=i, status=status, position=position)
                for i, (status, position) in enumerate([
                    ('present', [32, 48]), ('present', [32, 48]),
                    ('present', [33, 48]), ('present', [33, 48]),
                    ('present', [35, 48]), ('absent', None),
                    ('present', [36, 48]), ('present', [37, 48]),
                    ('present', [37, 48]), ('present', [39, 48])])]
        r = summarize(rows, 60)['pacman']
        self.assertEqual(r['displayed_move_interval_vic_frames'], {2: 2})
        self.assertEqual(r['absence_runs'], 1)
        self.assertEqual(r['displayed_move_distance_vic_pixels'], {1: 2, 2: 2})

    def test_phase_accounting_does_not_double_count_nested_routines(self):
        events = [(10, 'render-begin'), (15, 'mark-begin'), (20, 'mark-end'),
                  (30, 'render-end'), (35, 'wait-begin'), (45, 'wait-end')]
        r = trace_summary(events, 0, 50)
        self.assertEqual(r['phase_cycles'], {'logic_tasks_loop': 20, 'render': 20, 'wait': 10})
        self.assertEqual(r['routine_inclusive_cycles']['mark']['total'], 5)
        self.assertEqual(sum(r['phase_cycles'].values()), 50)

    def test_dropped_or_duplicate_video_frames_are_rejected(self):
        frames = [dict(clock=65+FRAME_CYCLES*i, line=1, cycle=0) for i in range(4)]
        validate_frame_spacing(frames)
        with self.assertRaisesRegex(AssertionError, 'Missing or duplicate'):
            validate_frame_spacing(frames[:1]+frames[2:])
        with self.assertRaisesRegex(AssertionError, 'Missing or duplicate'):
            validate_frame_spacing(frames[:1]+frames)

    def test_irq_sampling_jitter_keeps_exact_consecutive_frame_identity(self):
        frames = [dict(clock=65+FRAME_CYCLES*i+c, line=1, cycle=c)
                  for i, c in enumerate((0, 14, 1, 13))]
        validate_frame_spacing(frames)
        with self.assertRaisesRegex(AssertionError, 'Missing or duplicate'):
            validate_frame_spacing(frames[:1]+frames[2:])
        # A merely close timestamp must not pass as a consecutive raster.
        frames[1] = frames[1] | dict(clock=frames[1]['clock']+1)
        with self.assertRaisesRegex(AssertionError, 'Missing or duplicate'):
            validate_frame_spacing(frames)


if __name__ == '__main__':
    unittest.main(verbosity=2)
