#!/usr/bin/env python3
"""Time real pool allocation/restoration on identical inputs, IRQs masked.

This is a kernel comparison, not a video or whole-game FPS measurement.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from profile_game import stats
from rate_match import ROOT, write_json
sys.path.insert(0, str(ROOT/'tests'))
from native import Sim, WORK


def measure(prg):
    sim = Sim(prg)
    rows, begins, restores = [], [], []
    background = bytes((i*37 + i//16) & 255 for i in range(3136))
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK/'pa.bin'
    path.write_bytes(background)
    try:
        sim.cmd('run 500')
        sim.cmd('until frame_wait 100')
        sim.cmd('call video_restore')
        sim.cmd(f'load $1000 {path}')
        # Match the lookup-generation phase despite different startup speeds.
        path.write_bytes(bytes(196))
        sim.cmd(f'load $96c4 {path}')
        sim.cmd('poke pool_epoch 0')
        sim.cmd('poke v_color 3')

        def call(name, value=''):
            return int(sim.cmd(f'call {name} {value}')[-1].split('cycles=')[1])

        for bank in (0, 1):
            for start in range(0, 196, 24):
                sim.cmd(f'poke pool_bank {bank ^ 1}')
                begins.append(call('video_update_begin'))
                for cell in range(start, min(start+24, 196)):
                    slot = cell-start
                    fresh = call('pool_cell', cell)
                    dest = int.from_bytes(sim.peek('v_base', 2), 'little')
                    assert dest == 0x1c40 + (bank*24+slot)*16
                    r, c = divmod(cell, 14)
                    assert sim.peek(dest, 16) == background[c*224+r*16:c*224+r*16+16]
                    hit = call('pool_cell', cell)
                    assert int.from_bytes(sim.peek('v_base', 2), 'little') == dest
                    assert sim.peek(sim.labels['pool_count']+bank)[0] == slot+1
                    rows.append(dict(bank=bank, cell=cell, slot=slot,
                                     allocation_cycles=fresh, hit_cycles=hit))
                restores.append(dict(cells=min(24, 196-start),
                                     cycles=call('video_restore')))
                for cell in range(start, min(start+24, 196)):
                    r, c = divmod(cell, 14)
                    assert sim.peek(0x200+cell)[0] == c*14+r
        assert sim.peek(0x1000, 3136) == background
        assert sim.peek('pool_failed') == b'\0'
        return dict(prg_sha256=hashlib.sha256(prg.read_bytes()).hexdigest(),
                    method='vicsim call command; IRQs masked; identical home bytes and allocator inputs',
                    cells_checked=len(rows), allocation_cycles=stats([r['allocation_cycles'] for r in rows]),
                    hit_cycles=stats([r['hit_cycles'] for r in rows]),
                    begin_cycles=stats(begins), restore_batches=restores,
                    cases=rows)
    finally:
        sim.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', type=Path, default=ROOT/'build/pacman.prg')
    p.add_argument('--trial', type=Path, default=ROOT/'build/pool-address/pacman.prg')
    p.add_argument('--output', type=Path, default=ROOT/'build/pool-address/evaluation/kernel.json')
    args = p.parse_args()
    result = {name: measure(prg.resolve()) for name, prg in
              (('baseline', args.baseline), ('trial', args.trial))}
    assert [(r['bank'], r['cell'], r['slot']) for r in result['baseline']['cases']] == [
        (r['bank'], r['cell'], r['slot']) for r in result['trial']['cases']]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps({name: {k: v for k, v in r.items() if k not in ('cases', 'restore_batches')}
                      for name, r in result.items()}, indent=2))


if __name__ == '__main__':
    main()
