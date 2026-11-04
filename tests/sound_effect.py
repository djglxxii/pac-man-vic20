#!/usr/bin/env python3
"""Compare the actual 6502 effect kernels, including exact output and ABI guards."""
import hashlib
import json
import random
import unittest
from collections import defaultdict
from pathlib import Path

from native import ROOT, WORK, Sim

BASELINE = ROOT / 'build/pool-skip-empty/pacman.prg'
TRIAL = ROOT / 'build/sound-effect-fast/pacman.prg'
OUTPUT = ROOT / 'build/sound-effect-fast/evaluation/effect-kernel.json'


def stats(values):
    return dict(count=len(values), mean=sum(values)/len(values),
                min=min(values), max=max(values), total=sum(values))


class SoundEffectParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        cls.sims = [Sim(BASELINE), Sim(TRIAL)]
        cls.times = [defaultdict(list), defaultdict(list)]
        cls.outputs = hashlib.sha256()
        cls.cases = 0
        cls.tables = []
        for sim in cls.sims:
            sim.cmd('until frame_wait 300')
        for address in (0x3b30, 0x3b40, 0x3b80):
            source = [sim.peek(sim.labels['rom_32f9']+address-0x32f9, 256)
                      for sim in cls.sims]
            if source[0] != source[1]:
                raise AssertionError('Effect definitions changed')
            cls.tables.append(source[0])

    @classmethod
    def tearDownClass(cls):
        for sim in cls.sims:
            sim.close()
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(dict(
            programs=[dict(path=str(p.relative_to(ROOT)),
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in (BASELINE, TRIAL)],
            cases=cls.cases, output_sha256=cls.outputs.hexdigest(),
            method='Actual PRG kernels, identical fixtures, IRQs masked for calls',
            baseline={k: stats(v) for k, v in cls.times[0].items()},
            trial={k: stats(v) for k, v in cls.times[1].items()},
        ), indent=2)+'\n')

    def check(self, state, frequency, table, counter, group,
              effect_address=0x08fc, frequency_address=0x0afd):
        # Relocated state, definition and frequency pointers exercise page
        # crossings. They live in suspended logical video RAM, not live code.
        results = []
        guard = bytes(range(0x90, 0x94))
        preserved = bytes(range(0x61, 0x6d))
        for index, sim in enumerate(self.sims):
            for address, data in (
                (0x04fd, table),
                (effect_address-4, guard+bytes(state)+guard),
                (frequency_address-4, guard+bytes(frequency)+guard),
                (0x0004, effect_address.to_bytes(2, 'little')+
                 frequency_address.to_bytes(2, 'little')+b'\xfd\x04'),
                (0x0016, preserved),
            ):
                fixture = WORK / 'sound-kernel.bin'
                fixture.write_bytes(data)
                sim.cmd(f'load ${address:x} {fixture}')
            sim.cmd(f'poke $0c84 {counter}')
            stack = sim.peek(0x0002, 2)
            line = sim.cmd('call soundEffectOneChannel_2dee')[-1]
            returned = int(line.split()[1], 16)
            cycles = int(line.split('cycles=')[1])
            effect = sim.peek(effect_address-4, 24)
            freq = sim.peek(frequency_address-4, 12)
            self.assertEqual(effect[:4], guard)
            self.assertEqual(effect[-4:], guard)
            self.assertEqual(freq[:4], guard)
            self.assertEqual(freq[-4:], guard)
            self.assertEqual(sim.peek(0x0002, 2), stack, 'software stack pointer')
            self.assertEqual(sim.peek(0x0016, 12), preserved, 'callee-saved registers')
            self.times[index][group].append(cycles)
            self.times[index]['all'].append(cycles)
            results.append((effect[4:20], freq[4:8], returned))
        self.assertEqual(results[1], results[0],
                         f'{group}, state={bytes(state).hex()}, counter={counter}')
        type(self).cases += 1
        self.outputs.update(results[0][0]+results[0][1]+bytes([results[0][2]]))
        return results[0]

    def test_01_all_real_effects_and_priorities(self):
        for channel, count in enumerate((2, 8, 6)):
            for mask in [1 << bit for bit in range(count)] + [(1 << count)-1]:
                state = bytearray(16)
                state[0] = mask
                frequency = bytes(4)
                for tick in range(192):
                    state, frequency, volume = self.check(
                        state, frequency, self.tables[channel], tick & 255,
                        'real-effect-traces', 0x0e9c+16*channel,
                        (0x0e8c, 0x0e92, 0x0e97)[channel])

    def test_02_cancellation_and_inactive_state(self):
        rng = random.Random(0x2df4)
        for current in (0, 1, 128, 255):
            state = bytearray(rng.randbytes(16))
            state[0], state[2] = 0, current
            before = bytes(state)
            frequency = b'\x12\x34\x56\x78'
            result, freq, volume = self.check(state, frequency, self.tables[1], 0,
                                             'cancellation')
            expected = bytearray(before)
            if current:
                for offset in (2, 13, 14, 15):
                    expected[offset] = 0
                frequency = bytes(4)
            self.assertEqual(result, bytes(expected))
            self.assertEqual(freq, frequency)
            self.assertEqual(volume, 0)

    def test_03_random_state_and_duration_boundaries(self):
        rng = random.Random(0x2dee)
        table = rng.randbytes(512)
        for case in range(2048):
            state = bytearray(rng.randbytes(16))
            state[11] &= 15  # Only the 16 valid volume handlers.
            state[12] = (0, 1, 2, 255)[case % 4]
            state[8] = (0, 1, 2, 255)[(case // 4) % 4]
            self.check(state, rng.randbytes(4), table, case & 255,
                       'random-boundaries')

    def test_04_all_frequency_steps_scales_and_envelopes(self):
        # Keep a current effect active for one ordinary update. Cover every
        # 8-bit accumulator value, all scales and all valid volume types.
        for value in range(256):
            for scale in range(8):
                state = bytearray(16)
                state[0] = state[2] = 1
                state[3] = scale << 4
                state[5] = (value * 31) & 255
                state[11] = value & 15
                state[12] = 2
                state[14] = value
                state[15] = value ^ 0xa5
                self.check(state, b'\xaa\xbb\xcc\xdd', self.tables[1],
                           value & 7, 'pitch-scales-volume')


if __name__ == '__main__':
    unittest.main(verbosity=2)
