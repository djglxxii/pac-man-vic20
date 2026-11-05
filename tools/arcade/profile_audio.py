#!/usr/bin/env python3
"""Measure VIC translation and repeated pitch inputs without changing the guest."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys

from profile_game import hotspots, trace_summary
from rate_match import ROOT, call_sites, game_state, write_json

sys.path.insert(0, str(ROOT / 'tests'))
from native import Sim

CPU_HZ = 1022727
VOICES = ((16, 5, 0, 0, True), (22, 10, 2, 2, False),
          (27, 15, 1, 3, False))
SHIFTS = (0, 0, 1, 0, 3, 4, 0, 1)
# Audited LLVM-MOS layout. Refuse to silently attribute a changed converter.
BODY_HASH = '9a924a7f98aac81fde1f42fcc84987717413051121a832488ffc04cb876ad5cb'
RANGES = (
    ('save_restore', 0, 9), ('gating', 9, 0x22),
    ('unpacking', 0x22, 0x59), ('scaling', 0x59, 0x7d),
    ('zero_check_and_call', 0x7d, 0x8f), ('pitch_registers', 0x8f, 0x9b),
    ('gating', 0x9b, 0xb3), ('unpacking', 0xb3, 0xda),
    ('scaling', 0xda, 0x109), ('zero_check_and_call', 0x109, 0x117),
    ('pitch_registers', 0x117, 0x123), ('volume_and_noise', 0x123, 0x12d),
    ('gating', 0x12d, 0x141), ('unpacking', 0x141, 0x168),
    ('scaling', 0x168, 0x197), ('zero_check_and_call', 0x197, 0x1aa),
    ('pitch_registers', 0x1aa, 0x1b6),
    ('volume_and_noise', 0x1b6, 0x1cf), ('save_restore', 0x1cf, 0x1d9),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def voice_input(registers, enabled, voice):
    offset, wave, port, bias, first = VOICES[voice]
    volume = registers[offset + (5 if first else 4)] & 15
    raw = tuple(registers[offset+n] & 15 for n in range(5 if first else 4))
    key = raw + (registers[wave] & 7,)
    frequency = sum(raw[n] << (4*n) for n in range(4))
    if first and raw[4]:
        frequency = 65535
    shift = SHIFTS[key[-1]] + bias
    frequency = min(65535, frequency << shift)
    if not enabled or not volume:
        frequency = 0
    value = (255 - min(127, max(1, (43636 + frequency//2)//frequency))
             if frequency else 0)
    return dict(volume=volume, scaled_frequency=frequency, pitch=value,
                raw_key=key, shift=shift, port=port)


def summarize_repeats(rows):
    last_pitch, last_key = [None]*3, [None]*3
    counts = [Counter() for _ in VOICES]
    frequencies = [Counter() for _ in VOICES]
    sequence = [Counter() for _ in VOICES]
    for row in rows:
        for voice, item in enumerate(row['voices']):
            count = counts[voice]
            count['ticks'] += 1
            f = item['scaled_frequency']
            if not f:
                count['silent_or_zero_pitch_ticks'] += 1
                continue
            count['divider_calls'] += 1
            frequencies[voice][f] += 1
            sequence[voice][item['pitch']] += 1
            if f == last_pitch[voice]:
                count['same_as_last_audible_frequency'] += 1
            if tuple(item['raw_key']) == last_key[voice]:
                count['same_as_last_audible_raw_key'] += 1
            last_pitch[voice], last_key[voice] = f, tuple(item['raw_key'])
    for count in counts:
        for name in ('divider_calls', 'silent_or_zero_pitch_ticks',
                     'same_as_last_audible_frequency', 'same_as_last_audible_raw_key'):
            count.setdefault(name, 0)
    return [dict(**c, unique_scaled_frequencies=len(f), unique_output_pitches=len(p),
                 most_common_frequencies=f.most_common(12))
            for c, f, p in zip(counts, frequencies, sequence)]


def capture(prg, native, linker_map, reference, out):
    if (out/'summary.json').exists():
        raise FileExistsError(f'Use a new profile directory: {out}')
    out.mkdir(parents=True, exist_ok=True)
    files = {'captured-program.prg': prg, 'captured-program.lbl': prg.with_suffix('.lbl'),
             'pacman-native.bin': native, 'program.map': linker_map}
    for name, source in files.items():
        shutil.copy2(source, out/name)
    snapshot = out/'captured-program.prg'
    sites = call_sites(snapshot)
    sim = Sim(snapshot)
    rows, states, first = [], [], None
    try:
        sim.cmd('until boot_start 300')
        loaded = sim.peek(0x2000, 0x6000) + sim.peek(0xa000, 0x2000) + sim.peek(0x400, 0x400)
        assert loaded == (out/'pacman-native.bin').read_bytes(), 'Depacked image mismatch'
        start = sim.labels['audio_update']
        if 'audio_fast_end' in sim.labels:
            end = sim.labels['audio_fast_end']
            body = sim.peek(start, end-start)
            ranges = []
            for voice in range(3):
                prefix = f'audio_fast_voice_{voice}_'
                for name, begin, limit in (
                    ('gating', 'gate', 'unpack'), ('unpacking', 'unpack', 'scale'),
                    ('scaling', 'scale', 'pitch'),
                    ('zero_check_and_call', 'pitch', 'write'),
                    ('pitch_registers', 'write', 'end')):
                    ranges.append((name, sim.labels[prefix+begin], sim.labels[prefix+limit]))
            ranges.append(('volume_and_noise', sim.labels['audio_fast_volume'], end))
            layout = 'Assembly adapter with explicit disjoint linked-label ranges'
        else:
            body = sim.peek(start, 0x1d9)
            assert digest(body) == BODY_HASH, 'Converter changed: audit profiling ranges first'
            ranges = [(n, start+b, start+e) for n, b, e in RANGES]
            layout = 'Audited LLVM-MOS C layout with exact body hash guard'
        assert ranges[0][1] == start and ranges[-1][2] == start+len(body)
        assert all(a[2] == b[1] for a, b in zip(ranges, ranges[1:]))
        sim.cmd('until frame_wait 300')
        for symbol, name in (('frame_wait', 'wait'), ('video_refresh', 'render'),
                             ('audio_update', 'audio'), ('audio_divider', 'divider')):
            sim.cmd(f'watch {symbol} {name}')
        for inp in reference['inputs']:
            sim.cmd(f"until ${sites['frame_wait']+3:x} 100")
            mem = sim.peek(0, 4096)
            tick = int.from_bytes(mem[sim.labels['arcade_ticks']:sim.labels['arcade_ticks']+2], 'little')
            assert tick == inp['tick']
            if inp['phase'] == 'play':
                assert game_state(mem) == inp['state_sha256'], ('Game state changed', tick)
                states.append(tick)
                if first is None:
                    first = int(sim.cmd('stats')[0].split()[1])
                    sim.cmd('profile reset')
                    sim.cmd(f'trace {out}/active.trace')
            sim.cmd('joy '+inp['direction'])
            sim.cmd('until audio_update 100')
            start = int(sim.cmd('stats')[0].split()[1])
            registers, enabled = sim.peek(0x340, 32), sim.peek(0x301)[0]
            voices = [voice_input(registers, enabled, v) for v in range(3)]
            previous = sim.peek(0x900a, 5)
            sim.cmd(f"until ${sites['audio_update']+3:x} 100")
            duration = int(sim.cmd('stats')[0].split()[1])-start
            actual = sim.peek(0x900a, 5)
            expected = [0]*5
            for v in voices:
                expected[v['port']] = v['pitch']
            expected[4] = max(v['volume'] for v in voices) if enabled else 0
            assert actual == bytes(expected), ('Converter mismatch', tick, actual, expected)
            assert registers == sim.peek(0x340, 32), 'Converter changed source registers'
            rows.append(dict(tick=tick+1, phase=inp['phase'], enabled=enabled,
                             cycles=duration, voices=voices, previous_vic=previous.hex(),
                             output=dict(tick=tick+1,
                                         effect_and_song_state=sim.peek(0xe9c, 96).hex(),
                                         frequency_and_volume_state=sim.peek(0xe8c, 16).hex(),
                                         arcade_sound_registers=registers.hex(),
                                         vic_sound_registers=actual.hex())))
            sim.cmd('until frame_wait 100')
        last = int(sim.cmd('stats')[0].split()[1])
        sim.cmd('trace off')
        sim.cmd(f'profile {out}/active.profile')
        sim.cmd('profile off')
        # Dump source code used for attribution; no guest code/register writes.
        (out/'converter.bin').write_bytes(body)
        events = [(int(c), e) for c, e in map(str.split, (out/'active.trace').read_text().splitlines())]
        phases = trace_summary(events, first, last)
        exclusive = Counter()
        divider_end = sim.labels['divider_next']+11
        assert sim.peek(divider_end-1) == b'\x60', 'Audit divider extent'
        for line in (out/'active.profile').read_text().splitlines():
            a, cycles, hits = line.split()
            a, cycles = int(a, 16), int(cycles)
            if sim.labels['audio_update'] <= a < sim.labels['audio_update']+len(body):
                groups = [n for n, b, e in ranges if b <= a < e]
                assert len(groups) == 1, (a, groups)
                exclusive[groups[0]] += cycles
            if sim.labels['audio_divider'] <= a < divider_end:
                exclusive['divider'] += cycles
        play = [r for r in rows if r['phase'] == 'play']
        assert len(play) == len(states) == phases['routine_inclusive_cycles']['audio']['count']
        assert sum(r['cycles'] for r in play) == phases['phase_cycles']['audio']
        groups = {n: dict(cycles=c, cycles_per_tick=c/len(play),
                          audio_percent=c*100/phases['phase_cycles']['audio'],
                          cpu_percent=c*100/(last-first)) for n, c in exclusive.items()}
        summary = dict(
            method=__doc__.strip(), guest_modified=False,
            prg_sha256=digest(snapshot.read_bytes()), native_sha256=digest(loaded),
            input_sha256=digest(json.dumps(reference, sort_keys=True).encode()),
            converter_sha256=digest(body), depacked_bytes_verified=len(loaded),
            converter_layout=layout,
            converter_ranges=[dict(group=n, begin=f'{b:04x}', end=f'{e:04x}')
                              for n, b, e in ranges],
            cpu_hz=CPU_HZ, cycles=last-first, seconds=(last-first)/CPU_HZ,
            gameplay_states_checked=len(states), ticks_checked=len(rows),
            output_sha256=digest(json.dumps([r['output'] for r in rows], sort_keys=True).encode()),
            all_outputs_match_host_model=True, **phases, exclusive_audio=groups,
            interrupt_and_other_audio_cycles=phases['phase_cycles']['audio']-sum(exclusive.values()),
            repeated_inputs_all=summarize_repeats(rows), repeated_inputs_play=summarize_repeats(play),
            hotspots=hotspots(out/'active.profile', out/'program.map'))
        write_json(out/'ticks.json', rows)
        write_json(out/'summary.json', summary)
        return summary
    finally:
        sim.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prg', type=Path, default=ROOT/'build/pacman.prg')
    p.add_argument('--native', type=Path, default=ROOT/'build/arcade/pacman-native.bin')
    p.add_argument('--map', type=Path, default=ROOT/'build/arcade/pacman.map')
    p.add_argument('--input', type=Path, default=ROOT/'tests/fixtures/active-replay.json')
    p.add_argument('--output', type=Path, default=ROOT/'build/audio-translation-profile/current')
    args = p.parse_args()
    summary = capture(args.prg.resolve(), args.native.resolve(), args.map.resolve(),
                      json.loads(args.input.read_text()), args.output.resolve())
    print(json.dumps({k: v for k, v in summary.items() if k != 'hotspots'}, indent=2))


if __name__ == '__main__':
    main()
