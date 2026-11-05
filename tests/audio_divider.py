#!/usr/bin/env python3
"""Exhaustively check exact pitch mapping and time the two actual 6502 kernels."""
import argparse
import hashlib
import json
import random
import sys
import unittest
from collections import defaultdict
from pathlib import Path

from native import ROOT, WORK, Sim
sys.path.insert(0, str(ROOT/'tools/arcade'))
from profile_audio import voice_input

BASELINE = ROOT/'build/pool-stamp-fast/pacman.prg'
TRIAL = ROOT/'build/audio-divider-fast/pacman.prg'
OUTPUT = ROOT/'build/audio-divider-fast/evaluation/divider-kernel.json'


def pitch(frequency):
    return (255-min(127, max(1, (43636+frequency//2)//frequency))
            if frequency else 128)


def stats(values):
    return dict(count=len(values), total=sum(values), mean=sum(values)/len(values),
                min=min(values), max=max(values))


class DividerParity(unittest.TestCase):
    baseline, trial, output = BASELINE, TRIAL, OUTPUT

    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        cls.sims = [Sim(p) for p in (cls.baseline, cls.trial)]
        for sim in cls.sims:
            sim.cmd('until frame_wait 300')
        cls.costs = [defaultdict(list), defaultdict(list)]
        cls.timings = [{}, {}]
        cls.outputs = hashlib.sha256()

    @classmethod
    def tearDownClass(cls):
        for sim in cls.sims:
            sim.close()
        result = dict(
            method='Actual PRG calls with IRQs masked, RTS included, JSR excluded',
            frequencies_checked=65536, output_sha256=cls.outputs.hexdigest(),
            programs=[dict(path=str(p.relative_to(ROOT)),
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in (cls.baseline, cls.trial)],
            baseline={n: stats(v) for n, v in cls.costs[0].items()},
            trial={n: stats(v) for n, v in cls.costs[1].items()})
        capture = ROOT/'build/audio-translation-profile/baseline'
        if (capture/'ticks.json').exists():
            source = json.loads((capture/'summary.json').read_text())
            if source['prg_sha256'] == result['programs'][0]['sha256']:
                rows = json.loads((capture/'ticks.json').read_text())
                frequencies = [v['scaled_frequency'] for r in rows if r['phase']=='play'
                               for v in r['voices'] if v['scaled_frequency']]
                old, new = [sum(t[f] for f in frequencies) for t in cls.timings]
                assert old == source['exclusive_audio']['divider']['cycles']
                result['saved_replay_weighting'] = dict(
                    source_summary_sha256=hashlib.sha256((capture/'summary.json').read_bytes()).hexdigest(),
                    divider_calls=len(frequencies), baseline_cycles=old, trial_cycles=new,
                    cycles_saved=old-new, baseline_workload_cpu_percent_saved=(old-new)*100/source['cycles'])
        cls.output.parent.mkdir(parents=True, exist_ok=True)
        cls.output.write_text(json.dumps(result, indent=2)+'\n')

    def test_01_every_16_bit_frequency(self):
        for frequency in range(65536):
            expected = pitch(frequency)
            for index, sim in enumerate(self.sims):
                line = sim.cmd(f'call audio_divider {frequency & 255} {frequency >> 8}')[-1]
                actual = int(line.split()[1], 16)
                cycles = int(line.split('cycles=')[1])
                self.assertEqual(actual, expected, (index, frequency))
                self.timings[index][frequency] = cycles
                group = 'grid' if not frequency & 127 else 'fallback'
                self.costs[index][group].append(cycles)
            self.outputs.update(bytes([expected]))

    def test_02_lookup_contents(self):
        self.assertEqual(self.sims[1].peek('audio_pitch_lookup', 256),
                         bytes(pitch(index*128) for index in range(256)))

    def test_03_abi_and_input_guards(self):
        fixture = WORK/'adg.bin'
        for sim in self.sims:
            for f in (0, 1, 128, 256, 0x1234, 32768, 65408, 65535):
                preserved = bytes(range(0x91, 0x9d))
                fixture.write_bytes(preserved)
                sim.cmd(f'load $0016 {fixture}')
                stack = sim.peek(2, 2)
                source = sim.peek(0x340, 32)
                sim.cmd(f'call audio_divider {f & 255} {f >> 8}')
                self.assertEqual(sim.peek(0x16, 12), preserved)
                self.assertEqual(sim.peek(2, 2), stack)
                self.assertEqual(sim.peek(0x340, 32), source)

    def test_04_complete_converter_and_transitions(self):
        rng = random.Random(0x900a)
        fixture = WORK/'adr.bin'
        # Full bytes exercise masking as well as non-grid fallback. All-zero,
        # saturation, disable/re-enable and silence follow sounding voices.
        cases = [(bytes(32), 0), (bytes([255])*32, 1)]
        cases += [(bytes(rng.randrange(256) for _ in range(32)), n % 3)
                  for n in range(320)]
        cases += [(bytes(32), 1), (bytes([15])*32, 0), (bytes([15])*32, 255)]
        for registers, enabled in cases:
            expected = [0]*5
            voices = [voice_input(registers, enabled, v) for v in range(3)]
            for v in voices:
                expected[v['port']] = v['pitch']
            expected[4] = max(v['volume'] for v in voices) if enabled else 0
            for sim in self.sims:
                fixture.write_bytes(registers)
                sim.cmd(f'load $0340 {fixture}')
                sim.cmd(f'poke $0301 {enabled}')
                sim.cmd('call audio_update')
                self.assertEqual(sim.peek(0x900a, 5), bytes(expected))
                self.assertEqual(sim.peek(0x340, 32), registers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--trial', type=Path, default=TRIAL)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    DividerParity.baseline, DividerParity.trial = args.baseline.resolve(), args.trial.resolve()
    DividerParity.output = args.output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DividerParity)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
