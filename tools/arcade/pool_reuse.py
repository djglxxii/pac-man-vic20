#!/usr/bin/env python3
"""Count redundant pool work in saved, unmodified-game VICE snapshots.

This is an offline opportunity count, not a renderer or a cache simulation.
Byte equality is known after composition; dependency equality is a stricter
precondition a future cache could check, with its cost still unmeasured.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import zipfile

from analyze_display import labels, validate_frame_spacing
from pool_profile import analyse as pool_costs
from rate_match import digest, write_json

CELLS, BANK_SIZE, FIRST_CODE = 196, 24, 196


def glyph(data, code):
    return data[0x1000+code*16:0x1010+code*16]


def home(data, cell):
    return glyph(data, (cell % 14)*14+cell//14)


def displayed(data):
    return [(glyph(data, code), data[8192+cell])
            for cell, code in enumerate(data[0x200:0x2c4])]


def actor_footprints(data, sym, tables):
    """Conservative dependencies: full poses, including transparent coverage.

    Match allocation footprints and colour priority, not just visible ink.
    Deliberately keep source-frame/flip/palette distinctions even when their
    masks happen to be identical. No reward atlas is needed to identify cells.
    """
    actors = []
    for slot in range(12, 0, -2):
        x, y, attr, pal = (data[sym[n]+slot] for n in
                           ('cache_x', 'cache_y', 'cache_attr', 'cache_pal'))
        pal &= 31
        if not pal or 112 <= x < 249:
            continue
        code = attr >> 2
        right = pal == 31 and 40 <= code < 44
        eyes = pal == 25 and 32 <= code < 40
        klass = 1 if right or eyes else (
            tables['arcade_sprite_class'][code//4] >> ((code & 3)*2)) & 3
        colour = tables['arcade_colors'][(24 if right else pal)*4+klass]
        if not colour:
            continue
        col = -1 if x >= 249 else x//8
        cell = (y//16*14+col) & 255
        cells = []
        for offset, enabled in ((0, col != -1), (1, col != 13 and (x & 7))):
            if enabled:
                cells.append((cell+offset) & 255)
                if y & 15 >= 5:
                    cells.append((cell+offset+14) & 255)
        assert all(0 <= c < CELLS for c in cells), (slot, x, y, cells)
        actors.append(dict(slot=slot, x=x, y=y, colour=colour, cells=cells,
                           pose=(slot, x, y, attr, pal)))
    return actors


def pending(data, sym, tables):
    bank = data[sym['pool_bank']]
    assert bank in (0, 1) and data[sym['pool_failed']] == 0
    count = data[sym['pool_count']+bank]
    assert count <= BANK_SIZE
    start = bank*BANK_SIZE
    cells = list(data[sym['pool_cells']+start:sym['pool_cells']+start+count])
    assert len(set(cells)) == count and all(c < CELLS for c in cells)
    actors = actor_footprints(data, sym, tables)
    contributors, colours = defaultdict(list), {}
    order = []
    for actor in actors:
        for cell in actor['cells']:
            if cell not in contributors:
                order.append(cell)
            contributors[cell].append(actor['pose'])
            colours[cell] = actor['colour']
    assert order == cells, ('allocation footprint mismatch', order, cells)
    result = {}
    for slot, cell in enumerate(cells):
        colour = data[sym['pool_colours']+start+slot]
        assert colour == colours[cell]
        result[cell] = dict(slot=slot, code=FIRST_CODE+start+slot,
                            value=(glyph(data, FIRST_CODE+start+slot), colour),
                            key=(home(data, cell), tuple(contributors[cell]), colour))
    return dict(bank=bank, cells=result, actors=actors)


def compare_cells(current, previous, hidden, hidden_before, old_display):
    """Return exact-output ceilings and conservative dependency opportunities."""
    counts = Counter(cells=len(current['cells']), redraws=1)
    eligible = set()
    for cell, entry in current['cells'].items():
        value = entry['value']
        if value == old_display[cell]:
            counts['same_previous_pixels_and_colour'] += 1
        if value[0] == old_display[cell][0]:
            counts['same_previous_pixels'] += 1
        if value[1] == old_display[cell][1]:
            counts['same_previous_colour'] += 1
        prior = previous['cells'].get(cell)
        if prior and entry['key'] == prior['key']:
            assert value == old_display[cell], 'False dependency hit'
            counts['same_previous_dependencies'] += 1

        # The actual hidden bytes at refresh entry survive from its last use.
        # Byte matches at a different screen cell are counted separately: they
        # provide no cheap dependency key based on the cell's previous pose.
        if glyph(hidden_before, entry['code']) == value[0]:
            counts['hidden_same_slot_pixels_any_cell'] += 1
        if hidden is None:
            continue
        prior = hidden['cells'].get(cell)
        if prior and entry['key'] == prior['key']:
            assert value == prior['value'], 'False hidden-bank dependency hit'
        if prior and prior['value'][0] == value[0]:
            counts['hidden_same_cell_pixels_any_slot'] += 1
            if prior['slot'] == entry['slot']:
                counts['hidden_same_slot_cell_pixels'] += 1
                if entry['key'] == prior['key']:
                    counts['hidden_same_slot_cell_dependencies'] += 1
                    eligible.add(cell)
    for actor in current['actors']:
        counts['actor_stamps'] += 1
        if set(actor['cells']) <= eligible:
            counts['whole_actor_stamps_with_all_cells_reusable'] += 1
    return counts


def analyse(capture, profile_capture):
    recording_path = capture/'recording.json'
    recording = json.loads(recording_path.read_text())
    assert recording['renderer'] == 'glyph-pool'
    assert not recording['code_bytes_patched'] and not recording['pc_render_gate']
    assert recording['memory_layout'] == (
        '8 KiB $0000-$1fff followed by 196 colour nibbles $9600')
    validate_frame_spacing(recording['frames'])
    prg = capture/'captured-program.prg'
    assert digest(prg.read_bytes()) == recording['prg_sha256']
    identity = recording['loaded_program']
    assert identity['all_depacked_regions_match'] and identity['bytes_checked'] == 33792, identity
    sym = labels(prg.with_suffix('.lbl'))
    tables_path = capture/'tables.json'
    tables = json.loads(tables_path.read_text())
    first, last = recording['frames'][0]['clock'], recording['frames'][-1]['clock']
    events = recording['events']
    assert len(events) % 3 == 0
    assert all(a['clock'] < b['clock'] for a, b in zip(events, events[1:]))
    groups = defaultdict(Counter)
    histogram, repeat_runs, run = Counter(), Counter(), 0
    previous = previous_data = None
    banks = {}
    rows = []
    with zipfile.ZipFile(capture/'memory.zip') as archive:
        for offset in range(0, len(events), 3):
            render, paint, complete = events[offset:offset+3]
            assert [e['kind'] for e in (render, paint, complete)] == ['render', 'paint', 'complete']
            before, ink, after = (archive.read(e['memory']) for e in (render, paint, complete))
            assert all(len(m) == 8192+CELLS for m in (before, ink, after))
            current = pending(ink, sym, tables)
            assert current == pending(after, sym, tables), 'Pending glyphs changed during publication'
            assert after[sym['pool_bank']] != before[sym['pool_bank']]
            codes = range(FIRST_CODE+current['bank']*BANK_SIZE,
                          FIRST_CODE+(current['bank']+1)*BANK_SIZE)
            assert not any(c in codes for c in before[0x200:0x2c4]), 'Pending bank visible at entry'
            assert not any(c in codes for c in ink[0x200:0x2c4]), 'Pending bank visible before publication'
            actual = displayed(after)
            for cell, entry in current['cells'].items():
                assert after[0x200+cell] == entry['code']
                assert actual[cell] == entry['value'], 'Published glyph/colour mismatch'
            hidden = banks.get(current['bank'])
            if hidden:
                for entry in hidden['cells'].values():
                    assert glyph(before, entry['code']) == entry['value'][0], 'Hidden bank was overwritten'
            if previous is not None and first <= complete['clock'] <= last:
                counts = compare_cells(current, previous, hidden, before, displayed(previous_data))
                old_positions = {a['slot']: (a['x'], a['y']) for a in previous['actors']}
                positions = {a['slot']: (a['x'], a['y']) for a in current['actors']}
                moving = old_positions != positions
                category = 'some_actor_coordinates_changed' if moving else 'all_actor_coordinates_held'
                equal = actual == displayed(previous_data)
                same_poses = [a['pose'] for a in current['actors']] == [a['pose'] for a in previous['actors']]
                same_background = ink[0x1000:0x1c40] == previous_data[0x1000:0x1c40]
                counts['whole_display_identical'] += equal
                counts['all_poses_identical'] += same_poses
                counts['all_actor_composition_dependencies_identical'] += (
                    current['cells'].keys() == previous['cells'].keys() and all(
                        e['key'] == previous['cells'][cell]['key']
                        for cell, e in current['cells'].items()))
                background_idle = not any(before[sym[k]] for k in
                                           ('full_dirty', 'dirty_count', 'maze_flash', 'rebuild_phase'))
                counts['same_poses_and_background_idle_at_entry'] += same_poses and background_idle
                if same_poses and background_idle:
                    assert equal and same_background, 'Idle guard missed a visual/background change'
                counts['whole_clean_background_identical'] += same_background
                counts['whole_display_identical_and_poses_and_background_identical'] += (
                    equal and same_poses and same_background)
                counts['shared_actor_cells'] += sum(
                    len(e['key'][1]) > 1 for e in current['cells'].values())
                counts['pool_cells_with_only_home_pixels'] += sum(
                    e['value'][0] == home(ink, cell) for cell, e in current['cells'].items())
                groups['all'].update(counts)
                groups[category].update(counts)
                reward = any(a['pose'][4] == 31 and 40 <= a['pose'][3] >> 2 < 44
                             for a in current['actors'])
                groups['reward_score_visible' if reward else 'no_reward_score_visible'].update(counts)
                histogram[counts['same_previous_pixels_and_colour']] += 1
                if equal:
                    run += 1
                elif run:
                    repeat_runs[run] += 1
                    run = 0
                rows.append(dict(tick=complete['tick'], clock=complete['clock'],
                                 category=category, **dict(counts)))
            previous, previous_data = current, after
            banks[current['bank']] = current
    if run:
        repeat_runs[run] += 1
    assert groups['all']['redraws'] == (
        recording['frames'][-1]['completed_renders']-recording['frames'][0]['completed_renders'])
    profile = pool_costs(profile_capture)
    assert profile['prg_sha256'] == recording['prg_sha256']
    copy_cycles = profile['groups']['background_copy']['cycles']/profile['counters']['fresh_cells']
    assert copy_cycles == 209  # This build's unrolled 16-byte copy, exclusive of IRQs.
    duration_cycles = last-first
    metrics = {}
    for name, counts in groups.items():
        total = counts['cells']
        metrics[name] = dict(counts=counts, percent_of_pool_cells={
            k: v*100/total for k, v in counts.items() if
            k.startswith('same_previous_') or k.startswith('hidden_')})
    total = groups['all']
    copy_bounds = {key: dict(cells=total[key], cycles=total[key]*copy_cycles,
                              cycles_per_redraw=total[key]*copy_cycles/total['redraws'],
                              percent_of_capture_cpu_cycles=total[key]*copy_cycles*100/duration_cycles)
                   for key in ('hidden_same_slot_cell_pixels', 'hidden_same_slot_cell_dependencies')}
    result = dict(
        prg_sha256=recording['prg_sha256'], input_trace_sha256=recording['input_trace_sha256'],
        sources={name: digest((capture/name).read_bytes()) for name in
                 ('recording.json', 'memory.zip', 'tables.json', 'captured-program.lbl')},
        profile_source_summary_sha256=profile['source_summary_sha256'],
        profile_source_profile_sha256=profile['source_profile_sha256'],
        method='Offline exact glyph/colour comparison and conservative pose/home/shared-cell dependency keys',
        guest_code_changed=False, cache_implemented=False,
        window=dict(raster_frames=len(recording['frames']), first_clock=first, last_clock=last,
                    cpu_cycles=duration_cycles, seconds=duration_cycles/recording['cpu_hz']),
        metrics=metrics, same_previous_cells_per_redraw=dict(sorted(histogram.items())),
        whole_display_repeat_run_redraws=dict(sorted(repeat_runs.items())),
        background_copy_cycles_per_cell=copy_cycles, copy_only_upper_bounds=copy_bounds,
        validation=dict(snapshot_triplets=len(events)//3, pending_published_exactly=True,
                        pending_bank_not_visible=True, hidden_bytes_retained=True,
                        allocator_footprints_and_colour_priority_match=True,
                        false_dependency_hits=0),
        limitations=[
            'Exact equality is known after composition; checking bytes then cannot recover composition cost.',
            'Dependency keys keep full poses, so equivalent masks or unchanged local fragments can be missed.',
            'A byte equality count is not a speedup; invalidation, comparisons, allocation and bookkeeping cost cycles.',
            'Copy-only bounds assume zero checking overhead and no cadence changes; stamp savings are not included.',
            'Previous-display reuse needs mixed-bank ownership/capacity design; it is not the hidden-slot opportunity.',
            'Whole-display repeats include game pauses; coordinate-held does not establish that game logic is paused.',
            'Snapshots omit home colour RAM $9400: future invalidation must cover it as well as clean glyph bytes.',
            'One active-play replay does not cover all intermissions, maze flashes, attract screens or worst cases.',
        ])
    return result, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--profile-capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result, rows = analyse(args.capture.resolve(), args.profile_capture.resolve())
    write_json(args.output, result)
    write_json(args.output.with_name(args.output.stem+'-redraws.json'), rows)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
