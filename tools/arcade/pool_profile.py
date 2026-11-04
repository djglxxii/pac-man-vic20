#!/usr/bin/env python3
"""Rebucket an existing, unmodified-game instruction profile by pool work."""
import argparse
import hashlib
import json
from pathlib import Path

from rate_match import write_json


def analyse(capture):
    summary_path = capture / 'summary.json'
    summary = json.loads(summary_path.read_text())
    prg = capture / 'captured-program.prg'
    assert hashlib.sha256(prg.read_bytes()).hexdigest() == summary['prg_sha256']
    labels = {p[2][1:]: int(p[1], 16) for line in
              prg.with_suffix('.lbl').read_text().splitlines()
              if len(p := line.split()) == 3}
    profile = [(int(a, 16), int(c), int(h)) for a, c, h in
               map(str.split, (capture / 'active.profile').read_text().splitlines())]
    renders = summary['completed_renders']
    assert renders > 0

    def ranges(groups):
        result = {}
        for name, start, end in groups:
            begin, limit = labels[start], labels[end]
            assert begin < limit, (name, start, end)
            cost = sum(c for a, c, h in profile if begin <= a < limit)
            result[name] = dict(begin=f'{begin:04x}', end=f'{limit:04x}',
                                cycles=cost, cycles_per_redraw=cost/renders,
                                cpu_percent=cost*100/summary['cycles'])
        return result

    groups = ranges([
        ('reuse_guard', 'pool_reuse_guard', 'pool_actors'),
        ('actor_pose_and_setup', 'pool_actors', 'pool_draw'),
        ('generic_stamp', 'pool_draw', 'pool_cell'),
        ('cell_lookup_and_allocation', 'pool_cell', 'pool_copy'),
        ('background_copy', 'pool_copy', 'pool_colour'),
        ('colour_and_pointer', 'pool_colour', 'pool_setup'),
        ('destination_setup', 'pool_setup', 'video_restore'),
        ('restore_control_and_publish', 'video_restore', 'pool_draw_ghost'),
        ('normal_ghost_stamp', 'pool_draw_ghost', 'pool_ghost_sources'),
    ])
    pool_total = next(s['cycles'] for s in summary['hotspots']['sections']
                      if s['section'] == '.text.pool')
    assert sum(g['cycles'] for g in groups.values()) == pool_total
    if 'pool_merge_low' in labels:
        detail = ranges([
            ('setup', 'pool_draw', 'pool_row'),
            ('fetch_and_dispatch', 'pool_row', 'pool_merge_low'),
            ('merge_low', 'pool_merge_low', 'pool_step'),
            ('row_control', 'pool_step', 'pool_merge_high'),
            ('merge_high', 'pool_merge_high', 'pool_reverse'),
            ('mirror', 'pool_reverse', 'pool_shift_0'),
            ('aligned_merge', 'pool_shift_0', 'pool_shift_1'),
            ('shifts', 'pool_shift_1', 'pool_shifts'),
        ])
    else:
        detail = ranges([
            ('setup', 'pool_draw', 'pool_row'),
            ('fetch_and_mirror', 'pool_row', 'pool_store'),
            ('right_shifts', 'pool_store', 'pool_split'),
            ('merge', 'pool_split', 'pool_step'),
            ('row_control', 'pool_step', 'pool_left_3'),
            ('left_shifts', 'pool_left_3', 'pool_mirrors'),
        ])
    assert sum(g['cycles'] for g in detail.values()) == groups['generic_stamp']['cycles']
    hits = {a: h for a, c, h in profile}
    counters = {name: hits.get(labels[symbol], 0) for name, symbol in (
        ('generic_calls', 'pool_draw'), ('normal_ghost_calls', 'pool_draw_ghost'),
        ('generic_rows', 'pool_row'), ('nonempty_generic_rows', 'pool_mirror'),
        ('cell_calls', 'pool_cell'), ('fresh_cells', 'pool_copy'))}
    counters['shared_cell_hits'] = counters['cell_calls'] - counters['fresh_cells']
    return dict(prg_sha256=summary['prg_sha256'],
                source_summary_sha256=hashlib.sha256(summary_path.read_bytes()).hexdigest(),
                source_profile_sha256=hashlib.sha256((capture/'active.profile').read_bytes()).hexdigest(),
                method='Exclusive instruction cycles in disjoint linked-label ranges; no guest changes',
                cycles=summary['cycles'], completed_redraws=renders,
                groups=groups, generic_detail=detail, counters=counters,
                caveat='Different redraw cadence samples different poses; use identical-input kernels for isolated savings')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = analyse(args.capture)
    write_json(args.output or args.capture/'pool-costs.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
