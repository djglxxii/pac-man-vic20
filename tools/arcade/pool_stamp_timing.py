#!/usr/bin/env python3
"""Compare pooled generic stampers on identical masks, IRQs masked.

Every case checks pixels against a per-pixel oracle, including adjacent guards.
These are kernel timings; use profile_game.py and VICE for whole-game speed.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

from profile_game import stats
from rate_match import ROOT, write_json
sys.path.insert(0, str(ROOT/'tests'))
from native import Sim, WORK


def measure(prg, poison_unused_bottom=False):
    sim = Sim(prg)
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK/'pool-stamp.bin'
    # Four destination glyphs with a guard before/after. Nonzero initial ink
    # represents both a clean background and actors already composed into it.
    initial = bytes((i*37 + i//7) & 255 for i in range(96))
    rows = []
    try:
        sim.cmd('run 500')
        sim.cmd('until frame_wait 100')

        def poke(name, value, width=1):
            for byte in range(width):
                sim.cmd(f"poke ${sim.labels[name]+byte:x} {(value >> (byte*8)) & 255}")

        sources = []
        for name, count in (('arcade_sprites', 64), ('arcade_eyes', 8),
                            ('arcade_score_right', 4)):
            for code in range(count):
                address = sim.labels[name]+code*12
                sources.append((name, code, address, sim.peek(address, 12)))
        # Explicit fully empty/dense/wide/narrow rows expose both the saving
        # and the additional branch cost; actual atlases cover mixed rows.
        for value in (0, 255, 128, 1, 85, 170):
            sources.append(('synthetic', value, 0x1f40, bytes([value])*12))
        for name, code, address, mask in sources:
            if name == 'synthetic':
                path.write_bytes(mask)
                sim.cmd(f'load ${address:x} {path}')
            poke('v_data', address, 2)
            for shift in range(8):
                poke('v_shift', shift)
                for flip in range(4):
                    for y in (0, 4, 5, 15):
                        expected = bytearray(initial)
                        empty = 0
                        for row in range(12):
                            bits = mask[11-row if flip & 1 else row]
                            contributions = [0, 0]
                            for dx in range(8):
                                bit = dx if flip & 2 else 7-dx
                                if bits & (1 << bit):
                                    pos = dx+shift
                                    side, within = divmod(pos, 8)
                                    contributions[side] |= 128 >> within
                                    glyph_row, line = divmod(y+row, 16)
                                    expected[16+glyph_row*32+side*16+line] |= 128 >> within
                            empty += contributions.count(0)
                        for pointer, dest in (('v_addr', 0x1c40), ('v_right', 0x1c50),
                                              ('v_save', 0x1c60), ('v_saved_right', 0x1c70)):
                            # A twelve-row pose at y=0..4 cannot reach a bottom
                            # glyph. Point its unused scratch at the guards to
                            # catch an accidental dereference of those values.
                            if poison_unused_bottom and y < 5:
                                dest = {'v_save': 0x1c30, 'v_saved_right': 0x1c80}.get(pointer, dest)
                            poke(pointer, dest, 2)
                        poke('v_sy', y)
                        poke('v_flip', flip)
                        path.write_bytes(initial)
                        sim.cmd(f'load $1c30 {path}')
                        result = sim.cmd('call pool_draw')[-1]
                        actual = sim.peek(0x1c30, len(initial))
                        assert actual == expected, (name, code, shift, flip, y)
                        rows.append(dict(atlas=name, code=code, shift=shift, flip=flip,
                                         y=y, empty_halves=empty,
                                         cycles=int(result.split('cycles=')[1])))
        groups = defaultdict(list)
        for row in rows:
            for group in ('all', row['atlas'], f"shift-{row['shift']}"):
                groups[group].append(row['cycles'])
        return dict(prg_sha256=hashlib.sha256(prg.read_bytes()).hexdigest(),
                    method='vicsim call pool_draw; IRQs masked; identical masks and destinations',
                    background_sha256=hashlib.sha256(initial).hexdigest(),
                    unused_bottom_pointers_poisoned=poison_unused_bottom,
                    sources=[dict(atlas=name, code=code, rows=mask.hex())
                             for name, code, address, mask in sources],
                    cases_checked=len(rows), groups={k: stats(v) for k, v in groups.items()},
                    cases=rows)
    finally:
        sim.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, default=ROOT/'build/pool-address/pacman.prg')
    p.add_argument('--trial', type=Path, default=ROOT/'build/pool-skip-empty/pacman.prg')
    p.add_argument('--output', type=Path, default=ROOT/'build/pool-skip-empty/evaluation/kernel.json')
    p.add_argument('--poison-unused-bottom', action='store_true',
                   help='Point unused bottom destinations at guards for y=0 and y=4')
    args = p.parse_args()
    result = {name: measure(prg.resolve(), args.poison_unused_bottom) for name, prg in
              (('baseline', args.baseline), ('trial', args.trial))}
    assert result['baseline']['sources'] == result['trial']['sources']
    assert result['baseline']['background_sha256'] == result['trial']['background_sha256']
    savings = defaultdict(list)
    assert len(result['baseline']['cases']) == len(result['trial']['cases'])
    for before, after in zip(result['baseline']['cases'], result['trial']['cases']):
        assert {k: v for k, v in before.items() if k != 'cycles'} == {
            k: v for k, v in after.items() if k != 'cycles'}
        delta = before['cycles']-after['cycles']
        for group in ('all', before['atlas'], f"shift-{before['shift']}"):
            savings[group].append(delta)
    result['cycle_savings'] = {k: stats(v) | {'min': min(v)} for k, v in savings.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps({name: {k: v for k, v in value.items() if k not in ('cases', 'sources')}
                      if name != 'cycle_savings' else value
                      for name, value in result.items()}, indent=2))


if __name__ == '__main__':
    main()
