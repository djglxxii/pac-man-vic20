#!/usr/bin/env python3
"""Check normal-ghost rows against independent pixels and destination guards.

All body phases, shifts, flips and glyph-row offsets run on the linked,
unpatched renderer. Kernel cycles exclude the caller JSR and include RTS.
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
from native import Sim, WORK


def measure(prg):
    sim = Sim(prg)
    WORK.mkdir(parents=True, exist_ok=True)
    initial = bytes((i * 37 + i // 7) & 255 for i in range(96))
    rows, sources = [], []
    outputs = hashlib.sha256()
    path = WORK / 'pg.bin'
    try:
        sim.cmd('run 500')
        sim.cmd('until frame_wait 100')

        def poke(name, value, width=1):
            for byte in range(width):
                sim.cmd(f"poke ${sim.labels[name] + byte:x} {(value >> (byte * 8)) & 255}")

        for phase in range(2):
            mask = sim.peek(sim.labels['arcade_sprites'] + (32 + phase) * 12, 12)
            sources.append(mask.hex())
            assert mask[0] == mask[-1] == 0
            for shift in range(8):
                for flip in range(4):
                    for y in range(16):
                        expected = bytearray(initial)
                        for row in range(12):
                            bits = mask[11 - row if flip & 1 else row]
                            for dx in range(8):
                                if bits & (1 << (dx if flip & 2 else 7 - dx)):
                                    side, within = divmod(dx + shift, 8)
                                    glyph_row, line = divmod(y + row, 16)
                                    expected[16 + glyph_row * 32 + side * 16 + line] |= 128 >> within
                        for pointer, dest in (('v_addr', 0x1c40), ('v_right', 0x1c50),
                                              ('v_save', 0x1c60), ('v_saved_right', 0x1c70)):
                            # The ten ink rows cannot reach the bottom at y<=5.
                            if y <= 5:
                                dest = {'v_save': 0x1c30, 'v_saved_right': 0x1c80}.get(pointer, dest)
                            poke(pointer, dest, 2)
                        poke('v_sy', y)
                        poke('v_flip', flip)
                        path.write_bytes(initial)
                        sim.cmd(f'load $1c30 {path}')
                        result = sim.cmd(f'call pool_draw_ghost 0 {(phase * 8 + shift) * 2}')[-1]
                        actual = sim.peek(0x1c30, len(initial))
                        assert actual == expected, (phase, shift, flip, y)
                        outputs.update(actual)
                        rows.append(dict(phase=phase, shift=shift, flip=flip, y=y,
                                         cycles=int(result.split('cycles=')[1])))
        groups = defaultdict(list)
        for row in rows:
            for group in ('all', 'reverse' if row['flip'] & 1 else 'forward'):
                groups[group].append(row['cycles'])
        return dict(prg_sha256=hashlib.sha256(prg.read_bytes()).hexdigest(),
                    native_sha256=hashlib.sha256(sim.native_binary.read_bytes()).hexdigest(),
                    method='Unpatched pool_draw_ghost; IRQs masked; caller JSR excluded, RTS included',
                    oracle='Independent per-pixel body masks over nonzero background and adjacent guards',
                    unused_bottom_pointers_poisoned_at_y=list(range(6)),
                    sources=sources, cases_checked=len(rows), output_sha256=outputs.hexdigest(),
                    groups={k: stats(v) for k, v in groups.items()}, cases=rows)
    finally:
        sim.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--trial', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = {name: measure(prg.resolve()) for name, prg in
              (('baseline', args.baseline), ('trial', args.trial))}
    assert result['baseline']['sources'] == result['trial']['sources']
    assert result['baseline']['output_sha256'] == result['trial']['output_sha256']
    savings = defaultdict(list)
    for before, after in zip(result['baseline']['cases'], result['trial']['cases'], strict=True):
        assert {k: v for k, v in before.items() if k != 'cycles'} == {
            k: v for k, v in after.items() if k != 'cycles'}
        for group in ('all', 'reverse' if before['flip'] & 1 else 'forward'):
            savings[group].append(before['cycles'] - after['cycles'])
    result['cycle_savings'] = {k: stats(v) | {'min': min(v)} for k, v in savings.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps({name: {k: v for k, v in value.items() if k != 'cases'}
                      for name, value in result.items()}, indent=2))


if __name__ == '__main__':
    main()
