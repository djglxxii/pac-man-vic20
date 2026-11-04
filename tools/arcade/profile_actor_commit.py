#!/usr/bin/env python3
"""Profile natural rendering with a saved logical-tick joystick trace."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from rate_match import ROOT, call_sites, game_state, write_json

sys.path.insert(0, str(ROOT / 'tests'))
from native import Sim


def measure(prg, trace, output, state_reference=None):
    output.mkdir(parents=True, exist_ok=True)
    sites = call_sites(prg)
    expected = {x['tick']: x['state_sha256'] for x in
                (state_reference['states'] if state_reference else trace['inputs'])}
    sim = Sim(prg)
    active, states, mismatches = False, [], []
    try:
        sim.cmd('until frame_wait 300')
        for routine, name in (('sprite_groups', 'groups'), ('sprite_mark', 'mark'),
                              ('video_background', 'background'),
                              ('bitmap_draw', 'draw'), ('bitmap_draw_ghost', 'ghost')):
            if routine in sim.labels:
                sim.cmd(f'watch {routine} {name}')
        for inp in trace['inputs']:
            sim.cmd(f"until ${sites['frame_wait']+3:x} 100")
            mem = sim.peek(0, 4096)
            addr = sim.labels['arcade_ticks']
            tick = int.from_bytes(mem[addr:addr+2], 'little')
            if tick != inp['tick']:
                raise AssertionError(('Input tick mismatch', tick, inp['tick']))
            if inp['phase'] == 'play':
                state = game_state(mem)
                states.append({'tick': tick, 'state_sha256': state})
                if state != expected.get(tick):
                    mismatches.append(tick)
                if not active:
                    sim.cmd('profile reset')
                    sim.cmd(f'trace {output}/active.trace')
                    first = int(sim.cmd('stats')[0].split()[1])
                    active = True
            sim.cmd('joy ' + inp['direction'])
            sim.cmd('until frame_wait 100')
        if not active:
            raise AssertionError('No active input interval')
        last = int(sim.cmd('stats')[0].split()[1])
        sim.cmd('trace off')
        sim.cmd(f'profile {output}/active.profile')
        events = [(int(c), e) for c, e in
                  map(str.split, (output/'active.trace').read_text().splitlines())]
        completed = sum(e == 'end' for c, e in events)
        rows = [(int(a, 16), int(c), int(h)) for a, c, h in
                map(str.split, (output/'active.profile').read_text().splitlines())]
        result = {'prg': str(prg.relative_to(ROOT)),
                  'prg_sha256': hashlib.sha256(prg.read_bytes()).hexdigest(),
                  'cpu_hz': 1022727, 'cycles': last-first,
                  'render_calls': completed,
                  'render_calls_per_second': completed*1022727/(last-first),
                  'compared_active_states': len(states), 'mismatch_ticks': mismatches,
                  'state_reference': 'supplied current-build profile' if state_reference else 'input capture',
                  'states': states}
        if 'sprite_groups' in sim.labels:
            lo = sim.labels['sprite_groups']
            hi = (sim.labels['sprite_groups_end'] if 'sprite_groups_end' in sim.labels
                  else sim.labels['group_background_next']+6)
            cost = sum(c for a, c, h in rows if lo <= a < hi)
            calls = sum(h for a, c, h in rows if a == lo)
            result.update(grouping_cycles=cost, grouping_calls=calls,
                          grouping_cycles_per_call=cost/calls if calls else 0,
                          grouping_cycles_per_render=cost/completed)
        windows, erased, painting = [], {}, None
        for cycle, event in events:
            if event == 'begin':
                erased.clear()
            elif event == 'end':
                erased.clear()
            elif event.startswith('actor-'):
                _, actor, action = event.split('-')
                if action == 'erase':
                    erased[actor] = cycle
                else:
                    painting = actor
            elif event in ('draw-end', 'ghost-end') and painting is not None:
                if painting in erased:
                    windows.append(cycle-erased.pop(painting))
                painting = None
        if windows:
            windows.sort()
            result['actor_window_ms_mean'] = sum(windows)/len(windows)*1000/1022727
            result['actor_window_ms_p95'] = windows[int((len(windows)-1)*.95)]*1000/1022727
        write_json(output/'summary.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'states'}, indent=2))
        return result
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prg', type=Path, required=True)
    parser.add_argument('--input', type=Path, default=ROOT/'build/rate-match/active-1200/trial/recording.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--state-reference', type=Path)
    args = parser.parse_args()
    measure(args.prg.resolve(), json.loads(args.input.read_text()), args.output.resolve(),
            json.loads(args.state_reference.read_text()) if args.state_reference else None)


if __name__ == '__main__':
    main()
