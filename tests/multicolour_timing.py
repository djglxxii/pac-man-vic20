#!/usr/bin/env python3
"""Measure the complete multicolour game with joystick-only computer input."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from native import Sim, ROOT
from performance import start_game, CPU_HZ
sys.path.insert(0, str(ROOT / 'tools/arcade'))
from record_playthrough import Bot


def measure(prg, output, frames):
    output.mkdir(parents=True, exist_ok=True)
    sim = Sim(prg)
    bot = Bot(5)
    try:
        start_game(sim)
        for _ in range(2000):
            if sim.peek('rebuild_phase')[0] != 2 and sim.peek('mc_frames', 2) != b'\0\0':
                break
            memory = sim.peek(0, 4096)
            sim.cmd('joy ' + (bot.action(memory) if memory[0xe04] == 3 else '-'))
            sim.cmd('run 2')
        else:
            raise AssertionError('No playable picture')
        for name in ('video_background', 'mc_prepare_step', 'mc_prepare', 'mc_commit', 'audio_update'):
            if name in sim.labels: sim.cmd('watch ' + name + ' ' + name)
        sim.cmd('trace ' + str(output / 'play.trace'))
        first_cycle = int(sim.cmd('stats')[0].split()[1])
        first_tick = int.from_bytes(sim.peek('arcade_ticks', 2), 'little')
        first_update = int.from_bytes(sim.peek('mc_frames', 2), 'little')
        for _ in range(0, frames, 2):
            memory = sim.peek(0, 4096)
            sim.cmd('joy ' + (bot.action(memory) if memory[0xe04] == 3 else '-'))
            sim.cmd('run 2')
            assert sim.peek('mc_cache_errors') == b'\0', 'Background cache exhausted'
            assert sim.peek('mc_status') == b'\0', 'Actor allocation failed'
        last_cycle = int(sim.cmd('stats')[0].split()[1])
        ticks = (int.from_bytes(sim.peek('arcade_ticks', 2), 'little') - first_tick) & 65535
        updates = (int.from_bytes(sim.peek('mc_frames', 2), 'little') - first_update) & 65535
        sim.cmd('trace off')
        spans, starts, audio, publications = {}, {}, [], []
        for line in (output / 'play.trace').read_text().splitlines():
            cycle, kind = line.split()
            cycle = int(cycle)
            if kind == 'audio_update-begin': audio.append(cycle)
            if kind == 'mc_commit-end': publications.append(cycle)
            if kind.endswith('-begin'): starts[kind[:-6]] = cycle
            elif kind.endswith('-end') and kind[:-4] in starts:
                name = kind[:-4]
                spans.setdefault(name, []).append(cycle - starts.pop(name))
        seconds = (last_cycle - first_cycle) / CPU_HZ
        def max_gap(events):
            return round(max((b-a for a, b in zip(events, events[1:])), default=0) * 1000 / CPU_HZ, 2)
        return {
            'prg_sha256': hashlib.sha256(prg.read_bytes()).hexdigest(),
            'ntsc_cpu_hz': CPU_HZ, 'video_frames': frames, 'seconds': round(seconds, 4),
            'logic_ticks': ticks, 'logic_hz': round(ticks / seconds, 2),
            'publications': updates, 'updates_per_second': round(updates / seconds, 2),
            'max_audio_gap_ms': max_gap(audio), 'max_picture_gap_ms': max_gap(publications),
            'routines': {k: {'count': len(v), 'mean_cycles': round(sum(v)/len(v), 1),
                             'max_cycles': max(v)} for k, v in spans.items()},
            'cache_and_actor_errors': 0, 'joystick_only': True,
        }
    finally:
        sim.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prg', type=Path, default=ROOT / 'build/pacman-multicolour.prg')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/multicolour-game/timing')
    parser.add_argument('--frames', type=int, default=600)
    args = parser.parse_args()
    if args.frames < 60 or args.frames % 2: parser.error('--frames must be even and at least 60')
    report = measure(args.prg.resolve(), args.output.resolve(), args.frames)
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
