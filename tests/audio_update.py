#!/usr/bin/env python3
"""Compare complete audio adapters on all frequency/shift pairs and live inputs."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys
import unittest

from native import ROOT, WORK, Sim
sys.path.insert(0, str(ROOT/'tools/arcade'))
from profile_audio import voice_input


def stats(values):
    return dict(count=len(values), total=sum(values), mean=sum(values)/len(values),
                min=min(values), max=max(values))


def parse_bytes(line):
    return bytes(int(v, 16) for v in line.split(':')[1].split())


class AudioUpdateParity(unittest.TestCase):
    baseline = ROOT/'build/audio-divider-fast/pacman.prg'
    trial = ROOT/'build/audio-update-fast/pacman.prg'
    output = ROOT/'build/audio-update-fast/evaluation/update-kernel.json'

    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        cls.fixture = WORK/'au.bin'
        cls.sims = [Sim(p) for p in (cls.baseline, cls.trial)]
        for sim in cls.sims:
            sim.cmd('until frame_wait 300')
        cls.costs = [defaultdict(list), defaultdict(list)]
        cls.outputs = hashlib.sha256()
        cls.cases = 0
        cls.saved_input_corpus = None

    @classmethod
    def tearDownClass(cls):
        for sim in cls.sims:
            sim.close()
        result = dict(
            method='Actual complete audio_update calls, identical inputs, IRQs masked; RTS included, JSR excluded',
            frequency_shift_pairs=65536*8, cases=cls.cases,
            output_sha256=cls.outputs.hexdigest(),
            saved_input_corpus=cls.saved_input_corpus,
            programs=[dict(path=str(p.relative_to(ROOT)),
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in (cls.baseline, cls.trial)],
            baseline={n: stats(v) for n, v in cls.costs[0].items()},
            trial={n: stats(v) for n, v in cls.costs[1].items()})
        cls.output.parent.mkdir(parents=True, exist_ok=True)
        cls.output.write_text(json.dumps(result, indent=2)+'\n')

    def record(self, index, group, lines, expected):
        actual = parse_bytes(lines[-1])
        self.assertEqual(actual, expected, (index, group, type(self).cases))
        self.costs[index][group].append(int(lines[-2].split('cycles=')[1]))
        if index == 0:
            self.outputs.update(actual)
            type(self).cases += 1

    def check(self, registers, enabled, group, previous=None):
        expected = [0]*5
        voices = [voice_input(registers, enabled, v) for v in range(3)]
        for v in voices:
            expected[v['port']] = v['pitch']
        expected[4] = max(v['volume'] for v in voices) if enabled else 0
        self.fixture.write_bytes(registers)
        for index, sim in enumerate(self.sims):
            sim.cmd(f'load $0340 {self.fixture}\npoke $0301 {enabled}')
            if previous is not None:
                for port, value in enumerate(previous):
                    sim.cmd(f'poke ${0x900a+port:x} {value}')
            lines = sim.cmd('call audio_update\npeek $900a 5')
            self.record(index, group, lines, bytes(expected))
            self.assertEqual(sim.peek(0x340, 32), registers)
        return bytes(expected)

    def test_01_every_frequency_and_shift(self):
        # These voice/wave selections exercise every effective shift 0..7.
        # All four source nibbles vary, including exact saturation boundaries.
        selections = ((0, 0, 0), (1, 0, 2), (2, 1, 0), (3, 0, 4),
                      (4, 0, 5), (5, 1, 4), (6, 1, 5), (7, 2, 5))
        layout = ((16, 5, 0, 5), (22, 10, 2, 4), (27, 15, 1, 4))
        for shift, voice, wave in selections:
            offset, wave_offset, port, volume_offset = layout[voice]
            registers = bytearray(32)
            registers[wave_offset] = wave
            registers[offset+volume_offset] = 15
            self.fixture.write_bytes(registers)
            for sim in self.sims:
                sim.cmd(f'load $0340 {self.fixture}\npoke $0301 1')
            for frequency in range(65536):
                scaled = min(65535, frequency << shift)
                pitch = 255-min(127, max(1, (43636+scaled//2)//scaled)) if scaled else 0
                expected = bytearray((0, 0, 0, 0, 15))
                expected[port] = pitch
                commands = '\n'.join(f'poke ${0x340+offset+n:x} {(frequency >> (4*n)) & 15}'
                                     for n in range(4))
                for index, sim in enumerate(self.sims):
                    lines = sim.cmd(commands+'\ncall audio_update\npeek $900a 5')
                    self.record(index, f'shift-{shift}', lines, bytes(expected))
            print(f'  checked all 65536 inputs at shift {shift}', flush=True)

    def test_02_masks_volumes_and_transitions(self):
        rng = random.Random(0x900e)
        for case in range(2048):
            registers = bytes(rng.randrange(256) for _ in range(32))
            self.check(registers, (0, 1, 2, 255)[case % 4], 'masked-random')
        for fifth in range(256):
            for wave in range(8):
                registers = bytearray(32)
                registers[5] = wave
                registers[20] = fifth
                registers[21], registers[26], registers[31] = 1, 7, 15
                self.check(registers, 1, 'fifth-nibble')
        for volume in range(256):
            for voice, offset in enumerate((21, 26, 31)):
                registers = bytearray([0xff]*32)
                registers[offset] = volume
                # Other channels compete for global volume with different
                # nibble values; zero volume must independently silence pitch.
                registers[(21, 26, 31)[(voice+1) % 3]] = 0
                registers[(21, 26, 31)[(voice+2) % 3]] = 7
                self.check(registers, 1, 'volume-priority')
        self.check(bytes(32), 1, 'silence')
        self.check(bytes([255])*32, 0, 'disabled')
        self.check(bytes([255])*32, 255, 're-enabled')

    def test_03_abi_and_side_effects(self):
        for registers, enabled in ((bytes(32), 0), (bytes([255])*32, 1),
                                   (bytes(range(32)), 1)):
            self.fixture.write_bytes(registers)
            for index, sim in enumerate(self.sims):
                sim.cmd(f'load $0340 {self.fixture}\npoke $0301 {enabled}')
                before = sim.peek(0, 256)
                game = sim.peek(0xc00, 768)
                sim.cmd('call audio_update')
                after = sim.peek(0, 256)
                # The new kernel documents just rc2..4. The compiled C
                # baseline may use any caller-scratch register rc2..19.
                allowed = set(range(4, 7 if index else 22))
                for name, width in (('a_freq', 2), ('a_div', 1), ('a_bit', 1)):
                    allowed.update(range(sim.labels[name], sim.labels[name]+width))
                self.assertEqual([(a, b) for a, b in enumerate(before) if a not in allowed],
                                 [(a, b) for a, b in enumerate(after) if a not in allowed])
                self.assertEqual(sim.peek(0xc00, 768), game)
                self.assertEqual(sim.peek(0x340, 32), registers)

    def test_04_saved_live_inputs(self):
        capture = ROOT/'build/audio-divider-fast/evaluation/trial-cpu'
        if not (capture/'ticks.json').exists():
            self.skipTest('Optional saved native audio profile is unavailable')
        source = json.loads((capture/'summary.json').read_text())
        # These are archived inputs, replayed against both current programs.
        # Validate the capture against its own artifacts: an unrelated artwork
        # edit can change the current baseline's hash without changing audio.
        for name, key in (('captured-program.prg', 'prg_sha256'),
                          ('pacman-native.bin', 'native_sha256'),
                          ('converter.bin', 'converter_sha256')):
            self.assertEqual(source[key], hashlib.sha256((capture/name).read_bytes()).hexdigest())
        rows = json.loads((capture/'ticks.json').read_text())
        self.assertEqual(len(rows), source['ticks_checked'])
        self.assertEqual(hashlib.sha256(json.dumps([r['output'] for r in rows],
                                                  sort_keys=True).encode()).hexdigest(),
                         source['output_sha256'])
        type(self).saved_input_corpus = dict(
            path=str(capture.relative_to(ROOT)),
            summary_sha256=hashlib.sha256((capture/'summary.json').read_bytes()).hexdigest(),
            ticks_sha256=hashlib.sha256((capture/'ticks.json').read_bytes()).hexdigest(),
            captured_prg_sha256=source['prg_sha256'],
            captured_native_sha256=source['native_sha256'],
            ticks_checked=len(rows),
            historical_profile_cycles_reused=False)
        for row in rows:
            expected = self.check(bytes.fromhex(row['output']['arcade_sound_registers']),
                                  row['enabled'], 'live-'+row['phase'],
                                  bytes.fromhex(row['previous_vic']))
            self.assertEqual(expected.hex(), row['output']['vic_sound_registers'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, default=AudioUpdateParity.baseline)
    p.add_argument('--trial', type=Path, default=AudioUpdateParity.trial)
    p.add_argument('--output', type=Path, default=AudioUpdateParity.output)
    args = p.parse_args()
    AudioUpdateParity.baseline, AudioUpdateParity.trial = args.baseline.resolve(), args.trial.resolve()
    AudioUpdateParity.output = args.output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AudioUpdateParity)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
