#!/usr/bin/env python3
"""Compare tick-indexed arcade sound state and VIC registers on a live replay.

Host PC observations only: no guest code, registers, clocks or sound are patched.
CPU timestamps can differ; this checks the values produced at each logical tick.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from rate_match import ROOT, call_sites, game_state, write_json

sys.path.insert(0, str(ROOT / 'tests'))
from native import Sim


def replay(prg, reference):
    sites = call_sites(prg)
    sim = Sim(prg)
    result = []
    sound = 0x0340 if '__pool_capacity' in sim.labels else 0x1c80
    try:
        sim.cmd('until frame_wait 300')
        for inp in reference['inputs']:
            sim.cmd(f"until ${sites['frame_wait']+3:x} 100")
            mem = sim.peek(0, 4096)
            tick = int.from_bytes(mem[sim.labels['arcade_ticks']:
                                          sim.labels['arcade_ticks']+2], 'little')
            assert tick == inp['tick'], (tick, inp['tick'])
            if inp['phase'] == 'play':
                assert game_state(mem) == inp['state_sha256'], ('state mismatch', tick)
            sim.cmd('joy '+inp['direction'])
            sim.cmd(f"until ${sites['audio_update']+3:x} 100")
            tick = int.from_bytes(sim.peek('arcade_ticks', 2), 'little')
            assert tick == inp['tick']+1
            result.append(dict(
                tick=tick,
                effect_and_song_state=sim.peek(0x0e9c, 96).hex(),
                frequency_and_volume_state=sim.peek(0x0e8c, 16).hex(),
                arcade_sound_registers=sim.peek(sound, 32).hex(),
                vic_sound_registers=sim.peek(0x900a, 5).hex()))
            sim.cmd('until frame_wait 100')
    finally:
        sim.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path,
                        default=ROOT/'build/pool-skip-empty/pacman.prg')
    parser.add_argument('--trial', type=Path,
                        default=ROOT/'build/sound-effect-fast/pacman.prg')
    parser.add_argument('--input', type=Path,
                        default=ROOT/'tests/fixtures/active-replay.json')
    parser.add_argument('--output', type=Path,
                        default=ROOT/'build/sound-effect-fast/evaluation/audio-replay')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    reference = json.loads(args.input.read_text())
    streams = []
    for name, prg in (('baseline', args.baseline), ('trial', args.trial)):
        rows = replay(prg.resolve(), reference)
        write_json(args.output/(name+'.json'), rows)
        streams.append(rows)
    assert len(streams[0]) == len(streams[1])
    for old, new in zip(*streams):
        assert old == new, ('audio mismatch', old, new)
    summary = dict(
        ticks_compared=len(streams[0]),
        all_sound_state_and_register_values_identical=True,
        first_tick=streams[0][0]['tick'], last_tick=streams[0][-1]['tick'],
        output_sha256=hashlib.sha256(json.dumps(streams[0], sort_keys=True).encode()).hexdigest(),
        input_sha256=hashlib.sha256(json.dumps(reference, sort_keys=True).encode()).hexdigest(),
        programs=[dict(path=str(p.resolve().relative_to(ROOT)),
                       sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in (args.baseline, args.trial)],
        guest_modified=False, method=__doc__.strip())
    write_json(args.output/'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
