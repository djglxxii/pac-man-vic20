#!/usr/bin/env python3
"""Compare both ghost-update builds to the Z80 ROM on identical fixtures."""
import argparse
from collections import defaultdict
import hashlib
from itertools import product
import json
from pathlib import Path
import unittest

from arcade import ROOT, WORK, Runner, compare
from ghosts import fixtures as speed_fixtures
from native import Sim


def state_fixtures(game):
    base = bytearray(game)
    base[0x4D46:0x4D86] = bytes(64)
    base[0x4D9D] = 255
    base[0x4DA0:0x4DA4] = bytes((1,))*4
    base[0x4DA4:0x4DB0] = bytes(12)
    # Exercise all defined returning/house states, together and with a newly
    # eaten ghost. Selection must precede the four state machines.
    for states in product(range(3), range(3), range(4), range(4)):
        for selected in range(5):
            data = bytearray(base)
            data[0x4DAB] = selected
            data[0x4DAC:0x4DB0] = bytes(states)
            yield 'state-combinations', (states, selected), data
    for ghost in range(4):
        boundaries = [(1, 0x64, 0x80), (2, 0x7f, 0x80)]
        if ghost >= 2:
            boundaries.append((3, 0x80, 0x8f if ghost == 2 else 0x71))
        for state, y, x in boundaries:
            data = bytearray(base)
            data[0x4DAC+ghost] = state
            data[0x4D00+2*ghost:0x4D02+2*ghost] = bytes((y, x))
            if state == 1:
                # Keep the returning eyes at the door during the position
                # helper so this call actually advances to entering-house.
                data[0x4D14+2*ghost:0x4D16+2*ghost] = bytes(2)
            yield 'house-boundaries', (ghost, state), data
    limits = (0x78,)*4 + (0xb4, 0xc3, 0xd2, 0xe1, 0xf0, 0xff,
                           0x10e, 0x11d, 0x12c, 0x13b, 0x159, 0x1b8)
    for state, limit in enumerate(limits, 1):
        for count in (0, limit-2, limit-1, limit, 65535):
            data = bytearray(base)
            data[0x4DA5] = state
            data[0x4DC5:0x4DC7] = count.to_bytes(2, 'little')
            yield 'death-boundaries', (state, count), data
    for ghost, killed_state, killed_count, cocktail in product(
            range(1, 5), range(3), range(1, 5), range(2)):
        data = bytearray(base)
        data[0x4DA4] = ghost
        data[0x4DD0:0x4DD2] = bytes((killed_count, killed_state))
        data[0x4E09] = data[0x4E72] = cocktail
        yield 'reward-pause', (ghost, killed_state, killed_count, cocktail), data
    # Multiple simultaneous candidates check Clyde->Inky->Pinky->Blinky
    # collision priority. Tile and powered pixel checks are separate paths.
    for kind, matches, edible, powered in product(
            ('tile-collision', 'pixel-collision'), range(16), range(16), range(2)):
        data = bytearray(base)
        data[0x4DA6] = powered
        data[0x4D39:0x4D3B] = bytes((0x30, 0x30))
        data[0x4D08:0x4D0A] = bytes((0x80, 0x80))
        for ghost in range(4):
            match = bool(matches & (1 << ghost))
            data[0x4DA7+ghost] = bool(edible & (1 << ghost))
            tile = (0x30, 0x30) if kind == 'tile-collision' and match else (0x20+ghost, 0x20)
            pos = (0x82, 0x83) if kind == 'pixel-collision' and match else (0x60+ghost, 0x60)
            data[0x4D31+2*ghost:0x4D33+2*ghost] = bytes(tile)
            data[0x4D00+2*ghost:0x4D02+2*ghost] = bytes(pos)
        yield kind, (matches, edible, powered), data


class GhostUpdate(unittest.TestCase):
    baseline = ROOT/'build/audio-update-fast/pacman.prg'
    trial = ROOT/'build/ghost-update-fast/pacman.prg'
    output = ROOT/'build/ghost-update-fast/evaluation/ghost-kernel.json'

    @classmethod
    def setUpClass(cls):
        WORK.mkdir(parents=True, exist_ok=True)
        cls.game = (WORK/'game.ram').read_bytes()
        cls.ref = Runner('oracle')
        cls.ref.cmd('run 600')
        cls.sims = [Sim(p) for p in (cls.baseline, cls.trial)]
        for sim in cls.sims:
            sim.cmd('until frame_wait 300')
        cls.rows, cls.digests = [], [hashlib.sha256(), hashlib.sha256()]

    @classmethod
    def tearDownClass(cls):
        cls.ref.close()
        for sim in cls.sims:
            sim.close()
        groups = defaultdict(list)
        for row in cls.rows:
            groups[row['group']].append(row)
        report = dict(
            method='Actual 6502 routines vs original Z80 $1017; IRQs masked, RTS included, JSR excluded',
            cases=len(cls.rows), fixture_sha256=hashlib.sha256(cls.game).hexdigest(),
            programs=[dict(path=str(p.relative_to(ROOT)),
                           sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                           output_sha256=d.hexdigest())
                      for p, d in zip((cls.baseline, cls.trial), cls.digests)],
            groups={name: dict(
                count=len(rows),
                baseline_total=sum(r['baseline'] for r in rows),
                trial_total=sum(r['trial'] for r in rows),
                min_cycles_saved=min(r['baseline']-r['trial'] for r in rows),
                max_cycles_saved=max(r['baseline']-r['trial'] for r in rows))
                    for name, rows in groups.items()}, rows=cls.rows)
        cls.output.parent.mkdir(parents=True, exist_ok=True)
        cls.output.write_text(json.dumps(report, indent=2)+'\n')

    def check_fixture(self, group, key, data):
        path = WORK/'gu.ram'
        path.write_bytes(data)
        self.ref.load(path)
        self.ref.cmd('call 1017')
        original = self.ref.dump()
        if group == 'house-boundaries':
            ghost, state = key
            expected = 2 if state == 1 else 3 if state == 2 and ghost >= 2 else 0
            self.assertEqual(original[0x4DAC+ghost], expected, (group, key))
        costs = []
        outputs = []
        for sim, digest in zip(self.sims, self.digests):
            for address, payload in ((0x0400, data[0x4000:0x4800]),
                                     (0x0c00, data[0x4c00:0x5000]),
                                     (0x00a0, data[0x4da0:0x4e00]),
                                     (0x0300, data[0x5000:0x5008]),
                                     (0x0340, data[0x5040:0x5080])):
                path = WORK/'gu.bin'
                path.write_bytes(payload)
                sim.cmd(f'load ${address:x} {path}')
            for name in ('input0', 'input1'):
                sim.cmd(f'poke ${sim.labels[name]:x} 255')
            line = sim.cmd('call updateGhostStates_1017')[-1]
            costs.append(int(line.split('cycles=')[1]))
            memory, sound = sim.peek(0, 4096), sim.peek(0x0340, 32)
            mapped = bytearray(original)
            mapped[0x4000:0x4800] = memory[0x400:0xc00]
            mapped[0x4c00:0x4f00] = memory[0xc00:0xf00]
            mapped[0x4da0:0x4e00] = memory[0xa0:0x100]
            mapped[0x5040:0x5060] = sound
            self.assertEqual(compare(original, mapped), [], (group, key, sim.prg))
            logical = mapped[0x4000:0x4f00]+sound
            digest.update(logical)
            outputs.append(logical)
        self.assertEqual(outputs[0], outputs[1], (group, key))
        self.rows.append(dict(group=group, key=key, baseline=costs[0], trial=costs[1]))

    def test_01_speed_modes(self):
        for mode, pattern, data in speed_fixtures(self.game):
            with self.subTest(mode=mode, pattern=pattern):
                self.check_fixture('speed-'+mode, pattern, data)

    def test_02_state_transitions_and_collisions(self):
        for group, key, data in state_fixtures(self.game):
            with self.subTest(group=group, key=key):
                self.check_fixture(group, key, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, default=GhostUpdate.baseline)
    p.add_argument('--trial', type=Path, default=GhostUpdate.trial)
    p.add_argument('--output', type=Path, default=GhostUpdate.output)
    args = p.parse_args()
    GhostUpdate.baseline, GhostUpdate.trial = args.baseline.resolve(), args.trial.resolve()
    GhostUpdate.output = args.output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(GhostUpdate)
    if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
