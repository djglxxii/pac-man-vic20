#!/usr/bin/env python3
"""Profile the unmodified game on a logical-tick input replay (host observation)."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

from rate_match import ROOT, call_sites, game_state, write_json

sys.path.insert(0, str(ROOT / 'tests'))
from native import Sim

CPU_HZ = 1022727
WATCHES = (
    ('frame_wait', 'wait'), ('video_refresh', 'render'),
    ('audio_update', 'audio'), ('video_update_begin', 'restore'),
    ('sprite_mark', 'mark'), ('video_background', 'background'),
    ('video_update_end', 'paint'), ('bitmap_erase', 'erase'),
    ('bitmap_draw', 'draw'), ('bitmap_draw_ghost', 'ghost'),
    ('updateGhostStates_1017', 'ghost-state'),
    ('soundEffectsAllChannels_2d0c', 'sound-effects'),
    ('playSongsAllChannels_2cc1', 'songs'),
    ('soundEffectOneChannel_2dee', 'sound-channel'),
    ('playSongOneChannel_2d44', 'song-channel'),
)


def stats(values):
    values = sorted(values)
    if not values:
        return {'count': 0}
    return dict(count=len(values), mean=sum(values)/len(values),
                p50=values[(len(values)-1)//2],
                p95=values[int((len(values)-1)*.95)], max=values[-1])


def trace_summary(events, first, last):
    active, starts, durations = set(), {}, defaultdict(list)
    phases, previous = Counter(), first
    erases, windows, painting = {}, [], None
    completions = []
    for cycle, event in events:
        if cycle < first or cycle > last:
            continue
        phase = next((p for p in ('render', 'audio', 'wait') if p in active),
                     'logic_tasks_loop')
        phases[phase] += cycle-previous
        previous = cycle
        if event.endswith('-begin'):
            name = event[:-6]
            if name in active:
                raise AssertionError(('Nested same watch', name))
            active.add(name)
            starts[name] = cycle
        elif event.endswith('-end'):
            name = event[:-4]
            if name in starts:
                durations[name].append(cycle-starts.pop(name))
                active.remove(name)
        if event == 'begin':
            erases.clear()
        elif event == 'end':
            completions.append(cycle)
            erases.clear()
        elif event.startswith('actor-'):
            _, actor, action = event.split('-')
            if action == 'erase':
                erases[actor] = cycle
            else:
                painting = actor
        if event in ('draw-end', 'ghost-end') and painting is not None:
            if painting in erases:
                windows.append(cycle-erases.pop(painting))
            painting = None
    phase = next((p for p in ('render', 'audio', 'wait') if p in active),
                 'logic_tasks_loop')
    phases[phase] += last-previous
    assert sum(phases.values()) == last-first
    return dict(
        phase_cycles=dict(phases),
        phase_percent={p: c*100/(last-first) for p, c in phases.items()},
        routine_inclusive_cycles={name: stats(v) | {'total': sum(v)}
                                  for name, v in durations.items()},
        completed_renders=len(completions),
        completed_render_interval_ms=stats([(b-a)*1000/CPU_HZ for a, b in
                                           zip(completions, completions[1:])]),
        actor_erase_to_paint_ms=stats([v*1000/CPU_HZ for v in windows]))


def hotspots(profile, linker_map):
    # Linker input sections distinguish assembly kernels and compiler functions.
    # These are self costs: callees are charged to their own section.
    ranges = []
    pattern = re.compile(r'^\s*([0-9a-f]+)\s+[0-9a-f]+\s+([0-9a-f]+)\s+\d+\s+.*:\(([^)]+)\)')
    for line in linker_map.read_text().splitlines():
        m = pattern.match(line)
        if m and (m[3].startswith('.text') or m[3].startswith('.cold')):
            start, size = int(m[1], 16), int(m[2], 16)
            if size:
                ranges.append((start, start+size, m[3]))
    totals, instructions = Counter(), []
    for line in profile.read_text().splitlines():
        address, cost, hits = line.split()
        address, cost, hits = int(address, 16), int(cost), int(hits)
        name = next((n for a, b, n in ranges if a <= address < b), 'unmapped')
        totals[name] += cost
        instructions.append(dict(address=f'{address:04x}', cycles=cost,
                                 hits=hits, section=name))
    return dict(sections=[dict(section=n, cycles=c) for n, c in totals.most_common()],
                instructions=sorted(instructions, key=lambda x: x['cycles'], reverse=True)[:40],
                instruction_cycles=sum(totals.values()))


def measure(prg, trace, out, linker_map):
    out.mkdir(parents=True, exist_ok=True)
    snapshot = out/'captured-program.prg'
    if prg != snapshot:
        shutil.copy2(prg, snapshot)
        shutil.copy2(prg.with_suffix('.lbl'), snapshot.with_suffix('.lbl'))
    shutil.copy2(linker_map, out/'program.map')
    sites = call_sites(snapshot)
    sim = Sim(snapshot)
    states, active, first = [], False, None
    try:
        sim.cmd('until frame_wait 300')
        for routine, name in WATCHES:
            if routine in sim.labels:
                sim.cmd(f'watch {routine} {name}')
        for inp in trace['inputs']:
            sim.cmd(f"until ${sites['frame_wait']+3:x} 100")
            mem = sim.peek(0, 4096)
            tick = int.from_bytes(mem[sim.labels['arcade_ticks']:sim.labels['arcade_ticks']+2], 'little')
            assert tick == inp['tick'], (tick, inp['tick'])
            if inp['phase'] == 'play':
                actual = game_state(mem)
                assert actual == inp['state_sha256'], ('state mismatch', tick)
                states.append(dict(tick=tick, state_sha256=actual))
                if not active:
                    first = int(sim.cmd('stats')[0].split()[1])
                    sim.cmd('profile reset')
                    sim.cmd(f'trace {out}/active.trace')
                    active = True
            sim.cmd('joy '+inp['direction'])
            sim.cmd('until frame_wait 100')
        assert active
        last = int(sim.cmd('stats')[0].split()[1])
        sim.cmd('trace off')
        sim.cmd(f'profile {out}/active.profile')
        events = [(int(c), e) for c, e in
                  map(str.split, (out/'active.trace').read_text().splitlines())]
        result = dict(prg_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                      map_sha256=hashlib.sha256((out/'program.map').read_bytes()).hexdigest(),
                      cpu_hz=CPU_HZ, cycles=last-first, seconds=(last-first)/CPU_HZ,
                      states=states, guest_code_changed=False,
                      watches={r: n for r, n in WATCHES if r in sim.labels},
                      method='vicsim instruction cycles and host-only routine watches',
                      **trace_summary(events, first, last),
                      hotspots=hotspots(out/'active.profile', out/'program.map'))
        result['completed_renders_per_second'] = result['completed_renders']/result['seconds']
        # IRQ entry is seven cycles outside the instruction accounting. Phase
        # timing includes those cycles and any interrupts within a routine.
        result['unattributed_interrupt_entry_cycles'] = result['cycles']-result['hotspots']['instruction_cycles']
        write_json(out/'summary.json', result)
        print(json.dumps({k: v for k, v in result.items() if k not in ('states', 'hotspots')}, indent=2))
        return result
    finally:
        sim.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prg', type=Path, default=ROOT/'build/pacman.prg')
    p.add_argument('--input', type=Path, default=ROOT/'build/rate-match/active-1200/trial/recording.json')
    p.add_argument('--map', type=Path, default=ROOT/'build/arcade/pacman.map')
    p.add_argument('--output', type=Path, default=ROOT/'build/display-profile/current/cpu')
    args = p.parse_args()
    measure(args.prg.resolve(), json.loads(args.input.read_text()), args.output.resolve(), args.map.resolve())


if __name__ == '__main__':
    main()
