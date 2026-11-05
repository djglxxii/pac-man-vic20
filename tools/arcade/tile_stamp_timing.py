#!/usr/bin/env python3
"""Compare complete background-tile calls against an independent pixel oracle.

Exercise all logical offsets and every tile/palette on both nibble positions.
Nonzero neighbouring ink, packed-source page crossings and destination page
crossings are included. These masked-IRQ kernel timings are not game FPS.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

from profile_game import stats
from rate_match import ROOT, write_json
sys.path.insert(0, str(ROOT/'tests'))
from native import Sim, WORK


def xy(offset):
    a, b = divmod(offset, 32)
    if 2 <= a < 30:
        return 29-a, b+2
    if 2 <= b < 30:
        return 29-b, a+34 if a < 2 else a-30
    return None


def fixtures():
    # Includes the sixteen clipped corners, the two HUD strips, every output
    # line, both nibble positions and high palette bits that must be ignored.
    for offset in range(1024):
        yield offset, (offset*37) & 255, (offset*13) & 255
    for code in range(256):
        for palette in range(32):
            for x in (8, 9):
                y = 2+(code+palette) % 32
                yield (29-x)*32+y-2, code, palette


def measure(prg):
    source = (ROOT/'build/arcade/rom.c').read_text()
    body = re.search(r'arcade_tiles\[.*?= \{(.*?)\};', source, re.S)[1]
    packed = bytes(int(v, 16) for v in re.findall(r'0x[0-9a-f]+', body))
    tiles = [[n for b in packed[i:i+3] for n in (b >> 4, b & 15)]
             for i in range(0, len(packed), 3)]
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK/'tile-bg.bin'
    # Eight guard bytes on each side of the entire 196-home bitmap.
    expected = bytearray((i*37+i//7) & 255 for i in range(3152))
    path.write_bytes(expected)
    sim = Sim(prg)
    rows, groups = [], defaultdict(list)
    output = hashlib.sha256()
    try:
        sim.cmd('run 500')
        sim.cmd('until frame_wait 100')
        sim.cmd('call video_restore')
        assert sim.peek('arcade_tiles', len(packed)) == packed
        sim.cmd(f'load $0ff8 {path}')
        # Exercise the colour guard for both home and occupied matrix cells.
        path.write_bytes(bytes(196 if i % 3 == 0 else (i*14+i//14) % 196
                               for i in range(196)))
        sim.cmd(f'load $0200 {path}')
        sim.cmd('poke $0e04 0')
        logical = bytearray(sim.peek(0x400, 2048))
        for offset, code, palette in fixtures():
            sim.cmd(f'poke ${0x400+offset:x} {code}')
            sim.cmd(f'poke ${0x800+offset:x} {palette}')
            logical[offset], logical[1024+offset] = code, palette
            sim.cmd(f'poke v_save {offset & 255}')
            sim.cmd(f"poke ${sim.labels['v_save']+1:x} {offset >> 8}")
            cycles = int(sim.cmd('call bitmap_tile')[-1].split('cycles=')[1])
            position = xy(offset)
            case_groups = ['all']
            if position is None:
                case_groups.append('clipped')
                assert sim.peek(0x0ff8, len(expected)) == expected
                ink = b''
            else:
                x, y = position
                dest = 0x1000+(x//2)*224+y*6
                start = dest-0xff8
                shift = 0 if x & 1 else 4
                keep = 240 if x & 1 else 15
                image = tiles[code if palette & 31 else 64]
                for row, bits in enumerate(image):
                    expected[start+row] = (expected[start+row] & keep) | (bits << shift)
                ink = sim.peek(dest-2, 10)
                assert ink == expected[start-2:start+8], (offset, code, palette)
                case_groups += ['visible', f'nibble-{x & 1}']
                if (dest & 255)+5 > 255:
                    case_groups.append('destination-page-crossing')
                address = sim.labels['arcade_tiles']+(code if palette & 31 else 64)*3
                if (address & 255)+2 > 255:
                    case_groups.append('source-page-crossing')
            colours = sim.peek(0x9400, 196)+sim.peek(0x9600, 196)
            walls = sim.peek('maze_cells', 25)
            output.update(offset.to_bytes(2, 'little')+bytes((code, palette))+ink+colours+walls)
            for group in case_groups:
                groups[group].append(cycles)
            rows.append(dict(offset=offset, code=code, palette=palette,
                             groups=case_groups, cycles=cycles))
        assert sim.peek(0x0ff8, len(expected)) == expected
        # No logical tile/palette writes are allowed inside the drawing call.
        assert sim.peek(0x400, 2048) == logical
        return dict(prg_sha256=hashlib.sha256(prg.read_bytes()).hexdigest(),
                    native_sha256=hashlib.sha256(sim.native_binary.read_bytes()).hexdigest(),
                    method='Complete bitmap_tile call; IRQs masked; RTS included, caller JSR/fixture loading excluded',
                    cases_checked=len(rows), tiles_sha256=hashlib.sha256(packed).hexdigest(),
                    output_sha256=output.hexdigest(),
                    groups={k: stats(v) | {'min': min(v)} for k, v in groups.items()},
                    cases=rows)
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--trial', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = {name: measure(path.resolve()) for name, path in
              (('baseline', args.baseline), ('trial', args.trial))}
    assert result['baseline']['output_sha256'] == result['trial']['output_sha256']
    savings = defaultdict(list)
    for before, after in zip(result['baseline']['cases'], result['trial']['cases'], strict=True):
        assert {k: v for k, v in before.items() if k not in ('cycles', 'groups')} == {
            k: v for k, v in after.items() if k not in ('cycles', 'groups')}
        # Source-page crossings depend on each linked atlas address. Adding
        # read-only metadata can relocate an otherwise identical tile atlas.
        old_groups, new_groups = set(before['groups']), set(after['groups'])
        assert old_groups - {'source-page-crossing'} == new_groups - {'source-page-crossing'}
        delta = before['cycles']-after['cycles']
        for group in before['groups']:
            if group in new_groups:
                savings[group].append(delta)
        if ('source-page-crossing' in old_groups) != ('source-page-crossing' in new_groups):
            side = 'baseline' if 'source-page-crossing' in old_groups else 'trial'
            savings[f'{side}-only-source-page-crossing'].append(delta)
    result['cycle_savings'] = {k: stats(v) | {'min': min(v)} for k, v in savings.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, result)
    print(json.dumps({name: {k: v for k, v in value.items() if k != 'cases'}
                      if name != 'cycle_savings' else value
                      for name, value in result.items()}, indent=2))


if __name__ == '__main__':
    main()
