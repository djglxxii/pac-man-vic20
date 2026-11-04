#!/usr/bin/env python3
"""Record playable raster trials with identical logical-tick joystick inputs."""
import argparse
import json
from pathlib import Path

from rate_match import ROOT, capture, write_json
from record_playthrough import FPS

PROGRAMS = {'default': ROOT/'build/pacman.prg',
            **{mode: ROOT/f'build/beam-priority/{mode}/pacman.prg'
               for mode in ('reference', 'strict', 'focused')}}


def summarize(out):
    recordings = {mode: json.loads((out/mode/'recording.json').read_text())
                  for mode in PROGRAMS}
    baseline = recordings['default']
    expected = {r['tick']: r['picture_sha256'] for r in baseline['renders']}
    states = {r['tick']: (r['direction'], r['state_sha256']) for r in baseline['inputs']}
    result = {'same_logical_tick_inputs': True, 'programs': {}}
    for mode, r in recordings.items():
        assert not r['pc_render_gate'] and not r['code_bytes_patched']
        assert not r['mismatches'], (mode, r['mismatches'][:5])
        active = [s for s in r['inputs'] if s['phase'] == 'play' and s['tick'] in states]
        assert active and all((s['direction'], s['state_sha256']) == states[s['tick']]
                              for s in active), (mode, 'state mismatch')
        common = [s for s in r['renders'] if s['tick'] in expected]
        assert common and all(s['picture_sha256'] == expected[s['tick']] for s in common), mode
        frames = r['frames']
        assert all(s['line'] == 1 and s['cycle'] < 8 for s in frames)
        calls = frames[-1]['completed_renders'] - frames[0]['completed_renders']
        seconds = (len(frames)-1)/float(FPS)
        result['programs'][mode] = dict(prg_sha256=r['prg_sha256'],
            video_frames=len(frames), counter_interval_seconds=seconds,
            completed_render_calls=calls, render_calls_per_second=calls/seconds,
            compared_active_input_states=len(active), common_completed_pictures=len(common),
            loaded_program=r['loaded_program'])
    write_json(out/'summary.json', result)
    print(json.dumps(result, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=PROGRAMS, default='strict')
    p.add_argument('--frames', type=int, default=600)
    p.add_argument('--input', type=Path, default=ROOT/'build/rate-match/active-1200/trial/recording.json')
    p.add_argument('--output', type=Path, default=ROOT/'build/beam-priority/replay')
    p.add_argument('--summarize', action='store_true')
    args = p.parse_args()
    out = args.output.resolve()
    if args.summarize:
        summarize(out)
        return
    trace = json.loads(args.input.read_text())
    result = capture(PROGRAMS[args.mode], out/args.mode, args.frames,
                     reference=trace, gate=False, compare_pictures=False)
    assert not result['mismatches'], result['mismatches'][:5]
    print(f'{args.mode}: {len(result["frames"])} frames captured', flush=True)


if __name__ == '__main__':
    main()
