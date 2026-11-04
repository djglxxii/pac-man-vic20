#!/usr/bin/env python3
"""Audit temporary colour changes separately from missing actor pixels.

Capture audit: actual VICE snapshots and lossless raster PNGs. Fruit is a useful
stationary diagnostic, not a renderer exception. Raster checks use persistent
background ink in fruit-owned cells, excluding other actors' whole colour cells.
Native audit: host-observed physical colour writes within complete refreshes.
Native timestamps identify the writing instruction, not the exact VIC bus cycle.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import zipfile

from PIL import Image

from analyze_display import background, labels, poses, validate_frame_spacing
from rate_match import write_json


def cells(pose):
    if not pose['points']:
        return set()
    return {(y//16)*14+x//8
            for y in range(pose['y'], min(224, pose['y']+12))
            for x in range(max(0, pose['x']), min(112, pose['x']+8))}


def write_audit(directory):
    directory = Path(directory)
    trace = [(int(c), e) for c, e in map(str.split,
             (directory/'active.trace').read_text().splitlines())]
    batches, start = [], None
    for clock, kind in trace:
        if kind == 'begin':
            start = clock
        elif kind == 'end' and start is not None:
            batches.append((start, clock))
            start = None
    writes = []
    with (directory/'active.colours.csv').open() as f:
        for cycle, pc, cell, old, new in csv.reader(f):
            writes.append((int(cycle), pc, int(cell), int(old), int(new)))
    summary, examples, cursor = Counter(), [], 0
    for begin, end in batches:
        group = defaultdict(list)
        while cursor < len(writes) and writes[cursor][0] < end:
            row = writes[cursor]
            if row[0] >= begin:
                group[row[2]].append(row)
            cursor += 1
        summary['complete_refreshes'] += 1
        for cell, rows in group.items():
            changes = [r for r in rows if r[3] != r[4]]
            summary['stores_in_complete_refreshes'] += len(rows)
            summary['colour_changes_in_complete_refreshes'] += len(changes)
            if rows[0][3] == rows[-1][4] and changes:
                summary['unchanged_final_cells_with_round_trip'] += 1
                if len(examples) < 8:
                    examples.append(dict(cell=cell, initial=rows[0][3],
                                         changes=changes, begin=begin, end=end))
    summary.setdefault('unchanged_final_cells_with_round_trip', 0)
    return dict(summary=summary, examples=examples,
                timestamp='Native instruction start, not exact bus store phase')


def capture_audit(directory):
    directory = Path(directory)
    recording = json.loads((directory/'recording.json').read_text())
    validate_frame_spacing(recording['frames'])
    sym = labels(directory/'captured-program.lbl')
    tables = json.loads((directory/'tables.json').read_text())
    summary, examples, batch, states = Counter(), [], {}, []
    with zipfile.ZipFile(directory/'memory.zip') as archive:
        for event in recording['events']:
            data = archive.read(event['memory'])
            states.append(dict(event=event, data=data, poses=poses(data, sym, tables)))
            if event['kind'] == 'render':
                batch = {'render': states[-1]}
            elif batch and event['kind'] in ('paint', 'complete'):
                batch[event['kind']] = states[-1]
                if event['kind'] == 'complete' and 'paint' in batch:
                    old, mid, new = [batch[k]['data'][8192:] for k in ('render', 'paint', 'complete')]
                    changed = [c for c in range(196) if old[c] == new[c] != mid[c]]
                    fruit = next(p for p in states[-1]['poses'] if p['actor'] == 'fruit')
                    fruit_changed = set(changed) & cells(fruit)
                    summary['complete_batches'] += 1
                    summary['unchanged_final_cells_with_paint_phase_mismatch'] += len(changed)
                    summary['fruit_cells_with_paint_phase_mismatch'] += len(fruit_changed)
                    if fruit_changed and len(examples) < 6:
                        examples.append(dict(tick=event['tick'],
                                             cells=[(c, old[c], mid[c], new[c]) for c in sorted(fruit_changed)]))
                    batch = {}

    palette = [tuple(recording['palette'][c*3:c*3+3]) for c in range(16)]
    # Existing capture geometry, validated against settled images by analyze_display.
    origin_x, origin_y = 8, 4
    frames, cursor, previous = [], 0, None
    for before, frame in zip(recording['frames'], recording['frames'][1:]):
        while cursor < len(states) and states[cursor]['event']['clock'] <= before['clock']:
            if states[cursor]['event']['kind'] == 'complete':
                previous = states[cursor]
            cursor += 1
        relevant = [previous] if previous is not None else []
        scan = cursor
        while scan < len(states) and states[scan]['event']['clock'] <= frame['clock']:
            relevant.append(states[scan])
            scan += 1
        row = dict(frame=frame['frame'], tick=frame['tick'], cells=0,
                   sampled_wall_pixels=0, expected_colour_pixels=0,
                   white_pixels=0, black_pixels=0, other_pixels=0)
        if not relevant or any(s['data'][0xe04] != 3 or any(s['data'][sym[n]]
                for n in ('full_dirty', 'rebuild_phase', 'maze_flash')) for s in relevant):
            continue
        fruits = [next(p for p in s['poses'] if p['actor'] == 'fruit') for s in relevant]
        if any(not p['points'] or p['color'] in (0, 1) for p in fruits):
            continue
        if len({(p['x'], p['y'], p['color'], p['palette']) for p in fruits}) != 1:
            continue
        expected = fruits[0]['color']
        eligible = set.intersection(*(cells(p) for p in fruits))
        for s in relevant:
            for p in s['poses']:
                if p['actor'] != 'fruit':
                    eligible -= cells(p)
            if s['event']['kind'] != 'paint':
                eligible = {c for c in eligible if s['data'][8192+c] == expected}
        if not eligible:
            continue
        ink = set.intersection(*(background(s['data'], sym) for s in relevant))
        image = Image.open(directory/frame['image']).convert('RGB')
        for cell in sorted(eligible):
            points = [p for p in ink if ((p//112)//16)*14+(p % 112)//8 == cell]
            if len(points) < 4:
                continue
            row['cells'] += 1
            for point in points:
                x, y = point % 112, point//112
                rgb = image.getpixel((origin_x+x*2, origin_y+y))
                key = ('expected_colour_pixels' if rgb == palette[expected] else
                       'white_pixels' if rgb == palette[1] else
                       'black_pixels' if rgb == (0, 0, 0) else 'other_pixels')
                row[key] += 1
                row['sampled_wall_pixels'] += 1
        if row['cells']:
            frames.append(row)
    raster = dict(eligible_frames=len(frames),
                  frames_with_white=sum(bool(f['white_pixels']) for f in frames),
                  **{k: sum(f[k] for f in frames) for k in (
                      'cells', 'sampled_wall_pixels', 'expected_colour_pixels',
                      'white_pixels', 'black_pixels', 'other_pixels')})
    return dict(prg_sha256=recording['prg_sha256'], phase_audit=dict(summary),
                phase_examples=examples, raster_wall_audit=raster, frames=frames,
                method='Persistent background ink in stationary fruit-owned cells; all other actor colour cells excluded; one RGB sample per VIC pixel')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path)
    parser.add_argument('--cpu', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {}
    if args.cpu:
        result['native'] = write_audit(args.cpu)
    if args.capture:
        result['vice'] = capture_audit(args.capture)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps({k: {n: v for n, v in data.items() if n != 'frames'}
                      for k, data in result.items()}, indent=2))


if __name__ == '__main__':
    main()
