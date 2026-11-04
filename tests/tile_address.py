#!/usr/bin/env python3
"""Exercise the actual ghost tunnel kernel across coordinates, colours and ABI."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import unittest

from native import ROOT, WORK, Sim


class TileAddress(unittest.TestCase):
    prg = ROOT / 'build/tile-address-fast/pacman.prg'
    output = ROOT / 'build/tile-address-fast/evaluation/tile-kernel.json'

    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        cls.sim = Sim(cls.prg)
        cls.sim.cmd('until frame_wait 300')
        cls.saved_stub = cls.sim.peek(0x0308, 4)
        cls.digest = hashlib.sha256()
        cls.groups = {}

    @classmethod
    def tearDownClass(cls):
        cls.load(0x0308, cls.saved_stub)
        cls.sim.close()
        cls.output.parent.mkdir(parents=True, exist_ok=True)
        cls.output.write_text(json.dumps(dict(
            program=str(cls.prg.resolve().relative_to(ROOT)),
            prg_sha256=hashlib.sha256(cls.prg.read_bytes()).hexdigest(),
            method='Actual PRG kernel with IRQs masked; independent original C offset expression',
            groups=cls.groups, output_sha256=cls.digest.hexdigest(),
            cycles_include_five_cycle_carry_stub=True,
        ), indent=2)+'\n')

    @classmethod
    def load(cls, address, data):
        path = WORK / 'tile-kernel.bin'
        path.write_bytes(data)
        cls.sim.cmd(f'load ${address:x} {path}')

    def configure(self, palette, carry, aux=0x0cfc):
        self.aux = aux
        self.load(0x0800, palette)
        self.load(aux-1, bytes((0x91, 0xa7, 0x92)))
        self.load(0x0004, aux.to_bytes(2, 'little'))
        self.load(0x0016, bytes(range(0x61, 0x6d)))
        entry = self.sim.labels['checkGhostEnterTunnel_205a']
        self.load(0x0308, bytes((0x38 if carry else 0x18, 0x4c,
                                entry & 255, entry >> 8)))
        self.protected_zp = self.sim.peek(0, 256)

    def check(self, x, y, expected, group):
        line = self.sim.cmd(f'call $0308 {y} {x}')[-1]
        cycles = int(line.split('cycles=')[1])
        self.assertEqual(self.sim.peek(self.aux-1, 3), bytes((0x91, expected, 0x92)),
                         f'x={x}, y={y}, group={group}')
        entry = self.groups.setdefault(group, dict(count=0, total=0, min=cycles, max=cycles))
        entry['count'] += 1
        entry['total'] += cycles
        entry['min'] = min(entry['min'], cycles)
        entry['max'] = max(entry['max'], cycles)
        self.digest.update(bytes((expected,)))

    def check_guards(self, palette):
        current = self.sim.peek(0, 256)
        # Only the two explicitly caller-scratch bytes may change. This also
        # protects the software stack pointer, aux pointer and renderer state.
        self.assertEqual(current[:6]+current[8:],
                         self.protected_zp[:6]+self.protected_zp[8:])
        self.assertEqual(self.sim.peek(0x0800, 1024), bytes(palette))

    def test_01_all_coordinates_and_incoming_carries(self):
        rng = random.Random(0x205a)
        palette = bytes(0x1b if rng.randrange(2) else (i*73+19) & 255
                        for i in range(1024))
        for carry in (0, 1):
            self.configure(palette, carry)
            for x in range(256):
                for y in range(256):
                    # The original C expression wraps each subtraction to a
                    # byte, then wraps the full offset to ten bits.
                    offset = ((((x-32) & 255) << 5) + ((y-32) & 255) + 64) & 1023
                    self.check(x, y, int(palette[offset] == 0x1b), f'carry-{carry}')
                self.check_guards(palette)

    def test_02_distinguish_all_ten_address_bits(self):
        # A binary result cannot distinguish every address with one palette.
        # Ten independent bit planes expose any wrong address in the 1K map.
        for bit in range(10):
            palette = bytes(0x1b if a & (1 << bit) else 0 for a in range(1024))
            self.configure(palette, bit & 1, aux=0x0dff)
            for col in range(32):
                for row in range(32):
                    offset = (col*32+row+64) & 1023
                    self.check(col+32, row+32, int(bool(offset & (1 << bit))), 'address-bits')
            self.check_guards(palette)

    def test_03_full_colour_byte_comparison(self):
        for colour in range(256):
            palette = bytes((colour,))*1024
            self.configure(palette, colour & 1)
            self.check(0xff, 0, int(colour == 0x1b), 'colours')
            self.check_guards(palette)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prg', type=Path, default=TileAddress.prg)
    parser.add_argument('--output', type=Path, default=TileAddress.output)
    args = parser.parse_args()
    TileAddress.prg, TileAddress.output = args.prg, args.output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TileAddress)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
