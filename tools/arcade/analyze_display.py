#!/usr/bin/env python3
"""Measure actor visibility and displayed motion from lossless VICE frames.

The classifier uses sprite masks, clean backgrounds recovered from saved
underlays, and every old/new pose that could have been scanned in a frame.
Foreground colour is measured separately from binary sprite ink. Overlapping,
clipped, hidden and insufficiently identifiable actors are explicitly excluded.
"""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import json
from pathlib import Path
import zipfile

from PIL import Image, ImageDraw

from rate_match import ROOT, digest, write_json
from profile_game import stats

WIDTH, HEIGHT = 112, 224
FRAME_CYCLES = 65*261
MIN_EVIDENCE = 12


def validate_frame_spacing(frames):
    assert len(frames) >= 2
    assert all(f['line'] == 1 and f['cycle'] < 8 for f in frames)
    assert all(abs((b['clock']-a['clock'])-FRAME_CYCLES) <= 8
               for a, b in zip(frames, frames[1:])), 'Missing or duplicate raster frame'


def frame_window(recording, limit=None):
    """Select an initial window without hiding gaps or altering source data."""
    validate_frame_spacing(recording['frames'])
    if limit is None:
        return recording
    if not 2 <= limit <= len(recording['frames']):
        raise ValueError('--frames must select 2 or more existing frames')
    frames = recording['frames'][:limit]
    return recording | dict(frames=frames, events=[e for e in recording['events']
                                                  if e['clock'] <= frames[-1]['clock']])


def labels(path):
    return {p[2][1:]: int(p[1], 16) for line in path.read_text().splitlines()
            if len(p := line.split()) == 3}


def bitmap_points(bitmap):
    return {y*WIDTH+x for x in range(WIDTH) for y in range(HEIGHT)
            if bitmap[(x//8)*224+y] & (128 >> (x & 7))}


def background(data, sym):
    """Undo all six saved underlays in the renderer's reverse paint order."""
    bitmap = bytearray(data[0x1000:0x1c40])
    if '__pool_capacity' in sym:
        return bitmap_points(bitmap)  # Home glyphs always contain clean ink.
    for offset in range(180, -1, -36):
        rec = data[sym['under']+offset:sym['under']+offset+36]
        if not rec[3]:
            continue
        address = int.from_bytes(rec[:2], 'little')-0x1000
        for side in range(2):
            if rec[5] & (1 << side):
                target = address+224*side
                assert 0 <= target <= len(bitmap)-12, (offset, target)
                bitmap[target:target+12] = rec[8+side*12:20+side*12]
    return bitmap_points(bitmap)


def poses(data, sym, tables):
    rows = []
    for off in range(2, 14, 2):
        attr = data[sym['cache_attr']+off]
        pal = data[sym['cache_pal']+off] & 31
        x, y = data[sym['cache_x']+off], data[sym['cache_y']+off]
        if x >= 249:
            x -= 256
        code, flip = attr >> 2, attr & 3
        right = pal == 31 and 40 <= code < 44
        eyes = pal == 25 and 32 <= code < 40
        klass = 1 if eyes or right else (tables['arcade_sprite_class'][code//4] >> (code % 4*2)) & 3
        color = tables['arcade_colors'][(24 if right else pal)*4+klass]
        if eyes:
            image = tables['arcade_eyes'][(code-32)*12:(code-31)*12]
        else:
            image = tables['arcade_sprites'][code*12:(code+1)*12]
        points = set()
        if pal and color and -8 < x < 112:
            for dy in range(12):
                bits = image[11-dy if flip & 1 else dy]
                for dx in range(8):
                    if bits & (1 << (dx if flip & 2 else 7-dx)):
                        if 0 <= x+dx < WIDTH and 0 <= y+dy < HEIGHT:
                            points.add((y+dy)*WIDTH+x+dx)
        rows.append(dict(slot=off, code=code, flip=flip, palette=pal, color=color,
                         x=x, y=y, points=points))
    pac = next((r['slot'] for r in rows if r['palette'] == 9), None)
    mapping = {2: 'blinky', 4: 'pinky', 6: 'inky', 8: 'clyde', 10: 'pacman', 12: 'fruit'}
    if pac == 2:
        mapping[2], mapping[10] = 'pacman', 'blinky'
    for row in rows:
        row['actor'] = mapping[row['slot']]
        row['key'] = (row['actor'], row['x'], row['y'], row['code'], row['flip'], row['palette'])
    return rows


def snapshot(data, sym, tables, event):
    rows = poses(data, sym, tables)
    reason = None
    if data[0xe00] != 3 or data[0xe04] != 3:
        reason = 'outside-active-play'
    elif any(data[sym[n]] for n in ('full_dirty', 'rebuild_phase', 'maze_flash')):
        reason = 'background-rebuild-or-flash'
    elif any(r['palette'] in (24, 31) and 40 <= r['code'] < 44 for r in rows):
        reason = 'reward-slot-expansion'
    return dict(event=event, poses=rows, background=background(data, sym), reason=reason)


def displayed_bitmap(data):
    """Read what the matrix selects, including off-screen pool glyphs."""
    bits = bytearray(3136)
    for r in range(14):
        for c in range(14):
            source = 0x1000 + data[0x200+r*14+c]*16
            target = c*224+r*16
            bits[target:target+16] = data[source:source+16]
    return bits


def screen_rgb(data):
    bits = displayed_bitmap(data)
    colors = data[8192:]
    return [colors[(y//16)*14+x//8] if bits[(x//8)*224+y] & (128 >> (x & 7)) else 0
            for y in range(HEIGHT) for x in range(WIDTH)]


def calibrate(image, data):
    """Find the fixed two-output-dots-per-VIC-dot origin from actual output."""
    on = [rgb != (0, 0, 0) for rgb in image.getdata()]
    expected = screen_rgb(data)
    scores = []
    # Most of the maze is static; actors account for a small fraction. Reject
    # calibration unless the best full-display alignment is unambiguous.
    for oy in range(image.height-HEIGHT+1):
        for ox in range(image.width-WIDTH*2+1):
            error = sum(bool(expected[y*WIDTH+x]) != on[(oy+y)*image.width+ox+x*2]
                        for y in range(HEIGHT) for x in range(WIDTH))
            scores.append((error, ox, oy))
    scores.sort()
    best = scores[0]
    # A one-output-dot horizontal shift can tie: both halves represent a dot.
    other = next(s for s in scores[1:] if abs(s[1]-best[1]) >= 2 or s[2] != best[2])
    assert best[0] < WIDTH*HEIGHT*.08 and other[0] > best[0]+100, (best, other)
    return dict(x=best[1], y=best[2], output_dots_per_vic_dot=2,
                mismatch_pixels=best[0], next_distinct_alignment_error=other[0])


def classify(candidates, on, bg, others, minimum=MIN_EVIDENCE):
    """Exact mask evidence, independent of hue; exclude ambiguous background bits.

    A complete old OR new pose is accepted. Several distinct full matches are
    presence with an ambiguous pose; they are excluded from the motion metric.
    A mixed old/new image or missing rows is partial. No identifiable ink is
    absent. Background/other-actor pixels cannot provide evidence of presence.
    """
    if not candidates or any(not c['points'] for c in candidates):
        return dict(status='excluded', reason='hidden-or-empty')
    if any(c['x'] < 0 or c['x'] > WIDTH-8 or c['y']+12 > 216 for c in candidates):
        return dict(status='excluded', reason='screen-edge-clipping')
    all_points = set().union(*(c['points'] for c in candidates))
    # Exclude shared cells as well as shared lit pixels. Their colour/underlay
    # dependencies otherwise make individual-actor attribution unreliable.
    cells = {(p//WIDTH//16, p % WIDTH//8) for p in all_points}
    if any((p//WIDTH//16, p % WIDTH//8) in cells for p in others):
        return dict(status='excluded', reason='shared-colour-cell')
    domain = all_points-bg-others
    masks = [(c, c['points'] & domain) for c in candidates]
    if any(len(m) < minimum or len({p//WIDTH for p in m}) < 4 for c, m in masks):
        return dict(status='excluded', reason='insufficient-distinct-ink')
    lit = on & domain
    exact = [c for c, m in masks if lit == m]
    if exact:
        positions = {(c['x'], c['y']) for c in exact}
        return dict(status='present', diagnostic_pixels=len(domain), lit_pixels=len(lit),
                    pose=exact[0] if len(positions) == 1 else None,
                    ambiguous_position=len(positions) != 1)
    if not lit:
        return dict(status='absent', diagnostic_pixels=len(domain), lit_pixels=0)
    best, mask = max(masks, key=lambda cm: len(cm[1] & lit)/len(cm[1]))
    return dict(status='partial', diagnostic_pixels=len(domain), lit_pixels=len(lit),
                best_mask_fraction=len(mask & lit)/len(mask),
                complete_pose_with_extra_ink=any(m <= lit for c, m in masks))


def summarize(records, rate):
    result = {}
    for actor in ('pacman', 'blinky', 'pinky', 'inky', 'clyde'):
        samples = [r for r in records if r['actor'] == actor]
        counts = Counter(s['status'] for s in samples)
        runs, run = [], 0
        for s in samples:
            if s['status'] == 'absent':
                run += 1
            elif run:
                runs.append(run)
                run = 0
        if run:
            runs.append(run)
        # Count only established displayed poses. An excluded/partial/absent
        # frame interrupts a timing series: no inferred positions fill gaps.
        intervals, distances, previous, last_change = [], [], None, None
        moves = []
        for s in samples:
            pose = s.get('position') if s['status'] == 'present' else None
            if pose is None:
                previous, last_change = None, None
                continue
            if previous is None:
                previous = pose
                continue
            if pose != previous:
                if last_change is not None:
                    intervals.append(s['frame']-last_change)
                distance = abs(pose[0]-previous[0])+abs(pose[1]-previous[1])
                distances.append(distance)
                moves.append(dict(frame=s['frame'], previous=previous, position=pose,
                                  vic_pixels=distance))
                last_change, previous = s['frame'], pose
        eligible = counts['present']+counts['partial']+counts['absent']
        result[actor] = dict(
            frames=dict(counts), eligible_frames=eligible,
            exclusions=dict(Counter(s.get('reason') for s in samples if s['status'] == 'excluded')),
            absent_frame_percent=100*counts['absent']/eligible if eligible else None,
            partial_frame_percent=100*counts['partial']/eligible if eligible else None,
            absence_runs=len(runs), absence_run_frames=dict(sorted(Counter(runs).items())),
            absence_runs_per_eligible_second=len(runs)*rate/eligible if eligible else None,
            displayed_move_interval_vic_frames=dict(sorted(Counter(intervals).items())),
            displayed_move_interval_ms=stats([v*1000/rate for v in intervals]),
            displayed_move_distance_vic_pixels=dict(sorted(Counter(distances).items())),
            motion_changes=moves,
            visible_ink_color_mismatch_frames=sum(bool(s.get('color_mismatch_pixels')) for s in samples))
    return result


def validate_snapshots(archive, events, sym, tables):
    """Reject false absences on fully settled output; inject host-only controls.

    These controls change only offline sets, never the guest or real capture.
    Reward frames use another atlas and are outside this classifier's scope.
    """
    checked, exclusions = 0, Counter()
    outcomes = Counter()
    controls = Counter()
    for event in events:
        if event['kind'] != 'complete':
            continue
        data = archive.read(event['memory'])
        s = snapshot(data, sym, tables, event)
        if s['reason']:
            exclusions[s['reason']] += 1
            continue
        checked += 1
        actual = bitmap_points(displayed_bitmap(data))
        if '__pool_capacity' in sym:
            assert data[sym['pool_failed']] == 0, 'Pool capacity exhausted'
            assert max(data[sym['pool_count']:sym['pool_count']+2]) <= 24
        recomposed = s['background'] | set().union(*(p['points'] for p in s['poses']))
        assert actual == recomposed, ('settled mask oracle mismatch', event['tick'])
        for p in s['poses']:
            if p['actor'] == 'fruit':
                continue
            others = set().union(*(q['points'] for q in s['poses'] if q is not p))
            row = classify([p], actual, s['background'], others)
            outcomes[row['status']] += 1
            assert row['status'] in ('present', 'excluded'), ('false blink on settled image', event, row)
            if row['status'] != 'present':
                continue
            evidence = p['points']-s['background']-others
            missing = actual-evidence
            assert classify([p], missing, s['background'], others)['status'] == 'absent'
            half = set(sorted(evidence)[::2])
            assert classify([p], missing | half, s['background'], others)['status'] == 'partial'
            controls['absent'] += 1
            controls['partial'] += 1
    assert checked and controls['absent']
    return dict(complete_snapshots_checked=checked, excluded_complete_snapshots=dict(exclusions),
                settled_actor_results=dict(outcomes), false_absent_or_partial_on_settled_images=0,
                synthetic_host_only_controls=dict(controls))


def evidence_sheet(out, recording, records, origin):
    """Real consecutive raster frames, with actor zooms below; no cleaned pixels."""
    rows = {(r['actor'], r['frame']): r for r in records}
    evidence = []
    pac = [r for r in records if r['actor'] == 'pacman']
    for status in ('absent', 'partial'):
        choices = [r for r in pac if r['status'] == status and 0 < r['frame'] < len(pac)-1]
        # Prefer an isolated event bracketed by visible frames, then any event.
        example = next((r for r in choices if
                        rows['pacman', r['frame']-1]['status'] == 'present' and
                        rows['pacman', r['frame']+1]['status'] == 'present'), choices[0] if choices else None)
        if example:
            evidence.append(example)
    if not evidence:
        return []
    sheet = Image.new('RGB', (3*360, len(evidence)*700), '#202020')
    draw = ImageDraw.Draw(sheet)
    examples = []
    for row, center in enumerate(evidence):
        box = center['candidates'][0]
        for col, frame_no in enumerate(range(center['frame']-1, center['frame']+2)):
            image = Image.open(out/recording['frames'][frame_no]['image']).convert('RGB')
            x, y = origin['x']+2*box['x'], origin['y']+box['y']
            zoom = image.crop((x-6, y-4, x+22, y+16)).resize((210, 200), Image.Resampling.NEAREST)
            full = image.resize((360, 464), Image.Resampling.NEAREST)
            ImageDraw.Draw(full).rectangle(((x-4)*1.5, (y-2)*2, (x+20)*1.5, (y+14)*2), outline='#ff00ff', width=1)
            sheet.paste(full, (col*360, row*700+28))
            sheet.paste(zoom, (col*360+75, row*700+496))
            status = rows['pacman', frame_no]['status']
            draw.text((col*360+8, row*700+8), f'Frame {frame_no}: Pac-Man {status}', fill='white')
        examples.append(dict(actor='pacman', frame=center['frame'], status=center['status']))
    sheet.save(out/'evidence.png')
    return examples


def analyze(out, frame_limit=None):
    recording = json.loads((out/'recording.json').read_text())
    captured_frames = len(recording['frames'])
    recording = frame_window(recording, frame_limit)
    sym = labels(out/'captured-program.lbl')
    tables = json.loads((out/'tables.json').read_text())
    archive = zipfile.ZipFile(out/'memory.zip')
    events = recording['events']
    prepared = {}

    def state(i):
        if i not in prepared:
            data = archive.read(events[i]['memory'])
            prepared[i] = snapshot(data, sym, tables, events[i])
        return prepared[i]

    first_frame = recording['frames'][0]
    closest = min(range(len(events)), key=lambda i: abs(events[i]['clock']-first_frame['clock']))
    origin = calibrate(Image.open(out/first_frame['image']).convert('RGB'), archive.read(events[closest]['memory']))
    records = []
    cursor = 0
    previous_clock = first_frame['clock']-FRAME_CYCLES
    for frame in recording['frames']:
        # A raster frame contains pixels fetched since the previous capture.
        # Include the last completed pose BEFORE this scan, then every old/new
        # cache observed during it. A paint after the scan cannot have supplied
        # pixels to this frame, so future poses must not be admitted.
        while cursor+1 < len(events) and events[cursor+1]['clock'] <= previous_clock:
            cursor += 1
        anchor = cursor
        while anchor > 0 and events[anchor]['kind'] != 'complete':
            anchor -= 1
        indexes = set()
        j = anchor
        while j < len(events) and events[j]['clock'] <= frame['clock']:
            indexes.add(j)
            j += 1
        states = [state(i) for i in sorted(indexes)]
        prepared = {i: s for i, s in prepared.items() if i in indexes}
        image = Image.open(out/frame['image']).convert('RGB')
        assert digest(image.tobytes()) == frame['raw_sha256'], frame['frame']
        rgb = list(image.getdata())
        pixels = [rgb[(origin['y']+y)*image.width+origin['x']+2*x]
                  for y in range(HEIGHT) for x in range(WIDTH)]
        on = {i for i, color in enumerate(pixels) if color != (0, 0, 0)}
        bg = set().union(*(s['background'] for s in states))
        by_actor = defaultdict(dict)
        for s in states:
            for pose in s['poses']:
                by_actor[pose['actor']][pose['key']] = pose
        reasons = [s['reason'] for s in states if s['reason']]
        for actor in ('pacman', 'blinky', 'pinky', 'inky', 'clyde'):
            candidates = list(by_actor[actor].values())
            others = set().union(*(p['points'] for who, poses_ in by_actor.items()
                                       if who != actor for p in poses_.values()))
            if reasons:
                row = dict(status='excluded', reason=reasons[0])
            else:
                row = classify(candidates, on, bg, others)
            pose = row.pop('pose', None)
            if pose:
                row.update(position=[pose['x'], pose['y']], code=pose['code'],
                           flip=pose['flip'], palette=pose['palette'])
                evidence = pose['points']-bg-others
                # Compare actual pixel colours with the VIC palette used in
                # the frame; the palette is saved by the capture tool.
                expected = tuple(recording['palette'][pose['color']*3:pose['color']*3+3])
                row['color_mismatch_pixels'] = sum(pixels[p] != expected for p in evidence & on)
            row.update(frame=frame['frame'], actor=actor,
                       candidates=[dict(x=p['x'], y=p['y'], code=p['code']) for p in candidates])
            records.append(row)
        previous_clock = frame['clock']
    validation = validate_snapshots(archive, events, sym, tables)
    archive.close()
    rate = float(Fraction(recording['frame_rate']))
    frames = recording['frames']
    calls = frames[-1]['completed_renders']-frames[0]['completed_renders']
    seconds = (frames[-1]['clock']-frames[0]['clock'])/1022727
    completed = [e for e in events if e['kind'] == 'complete' and
                 frames[0]['clock'] <= e['clock'] <= frames[-1]['clock']]
    result = dict(prg_sha256=recording['prg_sha256'], video_frames=len(frames),
                  counter_interval_seconds=seconds, completed_renders=calls,
                  completed_renders_per_second=calls/seconds, calibration=origin,
                  min_diagnostic_pixels=MIN_EVIDENCE, actors=summarize(records, rate),
                  method='exact distinct sprite ink; old/new poses; binary visibility separate from colour',
                  guest_modified=False, validation=validation,
                  evidence=evidence_sheet(out, recording, records, origin),
                  render_interval_ms=stats([(b['clock']-a['clock'])*1000/1022727
                                            for a, b in zip(completed, completed[1:])]),
                  render_interval_logical_ticks=dict(sorted(Counter(
                      b['tick']-a['tick'] for a, b in zip(completed, completed[1:])).items())))
    write_json(out/'actors.json', records)
    if frame_limit is not None:
        result['source_capture_frames'] = captured_frames
        result['analysis_window'] = f'First {frame_limit} consecutive source frames'
    write_json(out/'analysis.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'actors'}, indent=2))
    for actor, values in result['actors'].items():
        print(actor, {k: v for k, v in values.items() if k != 'motion_changes'})
    return result, records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, default=ROOT/'build/display-profile/current/vice')
    p.add_argument('--frames', type=int, help='Analyse this many initial frames; source capture stays unchanged')
    args = p.parse_args()
    analyze(args.capture.resolve(), args.frames)


if __name__ == '__main__':
    main()
