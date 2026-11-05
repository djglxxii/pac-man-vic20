#!/usr/bin/env python3
"""Compare complete sprite transactions and exclusive setup on identical scenes.

The existing independent pixel/colour oracle checks every scene. Runtime code
is unpatched; only fixture RAM is loaded. IRQs are masked by vicsim's call.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

from profile_game import stats
from rate_match import ROOT, write_json
sys.path.insert(0, str(ROOT / 'tests'))
import render
from glyph_pool import PoolRenderer, PoolSim
from native import WORK


def scenes():
    # Every palette, including invisible and special-atlas combinations.
    for code in range(64):
        for pal in range(32):
            yield code, pal, (code + pal) & 3, 32 + ((code + pal) & 7), 80 + code % 16
    # Every frame through both tunnel edges, the bottom of the display, and
    # the 4/5 and 15/0 destination-row boundaries. Flips vary independently
    # across the position/palette matrix; all four are covered per frame.
    for code in range(64):
        for pal in (9, 25, 31):
            for x in (-7, -1, 0, 104, 105, 111, 112):
                for i, raw_y in enumerate((0, 144, 160, 158, 166)):
                    yield code, pal, (code + pal + x + i) & 3, x, raw_y


def measure(prg):
    rows, outputs = [], hashlib.sha256()

    class TimedSim(PoolSim):
        pending = False

        def __init__(self):
            super().__init__(prg)

        def cmd(self, command):
            result = super().cmd(command)
            if command == 'call video_sprites':
                self.last_cycles = int(result[-1].split('cycles=')[1])
                self.pending = True
            return result

        def dump(self):
            data = super().dump()
            if self.pending:
                outputs.update(data[0x1000:0x1c40])
                outputs.update(data[0x9600:0x96c4])
                outputs.update(data[0xc20:0xc40])
                self.pending = False
            return data

    previous = render.Sim
    render.Sim = TimedSim
    fixture = PoolRenderer()
    try:
        PoolRenderer.setUpClass()
        sim = fixture.sim
        fixture.setUp()
        # Equal bank/epoch phases remove startup timing from the comparison.
        sim.cmd('poke pool_bank 0\npoke pool_epoch 0')
        sim.cmd(f"poke ${sim.labels['pool_count']:x} 0\npoke ${sim.labels['pool_count'] + 1:x} 0")
        path = WORK / 'ps.bin'
        path.write_bytes(bytes(196))
        sim.cmd(f'load $96c4 {path}')
        # Verify linked descriptors independently of their generator.
        if 'pool_sprite_descriptors' in sim.labels:
            descriptors = sim.peek('pool_sprite_descriptors', 128)
            assert sim.labels['arcade_sprites'] % 4 == 0
            for code in range(64):
                address = int.from_bytes(descriptors[code * 2:code * 2 + 2], 'little')
                assert address & 65532 == sim.labels['arcade_sprites'] + code * 12
                assert address & 3 == (fixture.classes[code // 4] >> (code % 4 * 2)) & 3
        sim.cmd('profile reset')
        for code, pal, flip, x, raw_y in scenes():
            fixture.check_scene([(code, flip, pal, 239 - 2 * x, raw_y)])
            special = ('eyes' if pal == 25 and 32 <= code < 40 else
                       'score-right' if pal == 31 and 40 <= code < 44 else 'regular')
            group = ('hidden-palette' if pal == 0 else 'clipped' if x >= 112 else special)
            rows.append(dict(code=code, palette=pal, flip=flip, x=x,
                             raw_y=raw_y, group=group, cycles=sim.last_cycles))
        profile = WORK / 'ps.profile'
        sim.cmd(f'profile {profile}')
        instructions = [(int(a, 16), int(c)) for a, c, h in
                        map(str.split, profile.read_text().splitlines())]
        groups = defaultdict(list)
        for row in rows:
            groups['all'].append(row['cycles'])
            groups[row['group']].append(row['cycles'])
        setup = {}
        for name, start, end in (('actor_preparation', 'pool_actors', 'pool_draw'),
                                 ('destination_setup', 'pool_setup', 'video_restore')):
            cycles = sum(c for a, c in instructions if sim.labels[start] <= a < sim.labels[end])
            setup[name] = dict(cycles=cycles, cycles_per_scene=cycles / len(rows))
        return dict(prg_sha256=hashlib.sha256(prg.read_bytes()).hexdigest(),
                    native_sha256=hashlib.sha256(sim.native_binary.read_bytes()).hexdigest(),
                    method='Unpatched complete video_sprites calls, RTS included, caller JSR excluded; IRQs masked',
                    oracle='Independent Renderer.check_scene pixels, colours, retained inputs and restoration',
                    cases_checked=len(rows), output_sha256=outputs.hexdigest(),
                    artwork_sha256=hashlib.sha256(fixture.sprites + fixture.eyes + fixture.score_right +
                                                 fixture.classes + fixture.colors).hexdigest(),
                    exclusive_setup=setup, groups={k: stats(v) for k, v in groups.items()}, cases=rows)
    finally:
        if hasattr(PoolRenderer, 'sim'):
            PoolRenderer.tearDownClass()
        render.Sim = previous


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--trial', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = {name: measure(prg.resolve()) for name, prg in
              (('baseline', args.baseline), ('trial', args.trial))}
    assert result['baseline']['artwork_sha256'] == result['trial']['artwork_sha256']
    assert result['baseline']['output_sha256'] == result['trial']['output_sha256']
    savings = defaultdict(list)
    for before, after in zip(result['baseline']['cases'], result['trial']['cases'], strict=True):
        assert {k: v for k, v in before.items() if k != 'cycles'} == {
            k: v for k, v in after.items() if k != 'cycles'}
        delta = before['cycles'] - after['cycles']
        savings['all'].append(delta)
        savings[before['group']].append(delta)
    result['cycle_savings'] = {k: stats(v) | {'min': min(v)} for k, v in savings.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps({name: {k: v for k, v in value.items() if k != 'cases'}
                      if name != 'cycle_savings' else value
                      for name, value in result.items()}, indent=2))


if __name__ == '__main__':
    main()
