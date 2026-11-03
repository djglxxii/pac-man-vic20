#!/usr/bin/env python3
"""Build artwork for the live multicolour game; no recorded poses or RAM fixture."""
from collections import Counter
import json
from pathlib import Path

from build_multicolour_motion import poses
from maze_mockup import ROOT, table
from multicolour_mockup import TRANSPARENT, ACCENT, font_glyph, tile_walls


def main():
    out = ROOT / 'build/multicolour-game'
    out.mkdir(parents=True, exist_ok=True)
    artwork = json.loads((ROOT / 'docs/artwork/multicolour/actors-and-font.json').read_text())
    names, images = poses(artwork)
    for phase in range(2):
        names.append(f'frightened-white-{phase}')
        images.append([[3 if value == 1 else 1 if value == 3 else value for value in row]
                       for row in images[8 + phase]])
    records, row_ids = [], []
    for image in images:
        for row in image:
            data = sum((0 if value == TRANSPARENT else value) << (14 - 2 * x)
                       for x, value in enumerate(row))
            mask = sum((0 if value == TRANSPARENT else 3) << (14 - 2 * x)
                       for x, value in enumerate(row)) ^ 0xffff
            fields = tuple((data >> shift) & 255 for shift in (8, 0))
            fields += tuple((mask >> shift) & 255 for shift in (8, 0))
            if fields not in records:
                records.append(fields)
            row_ids.append(records.index(fields))
    frequency = Counter(row_ids)
    order = sorted(range(len(records)), key=lambda row: (-frequency[row], row))
    remap = {old: new for new, old in enumerate(order)}
    (out / 'pose-rows.bin').write_bytes(bytes(remap[row] for row in row_ids))
    (out / 'row-records.bin').write_bytes(bytes(records[row][field] for field in range(4) for row in order))
    # Pre-shift the shared row dictionary, rather than every complete pose.
    # Two byte columns + packed third-column/colour tails use spare stack RAM;
    # the two mask columns stay in expansion RAM. No runtime shifting remains.
    shifted, tails = [], []
    for phase in range(4):
        bits = phase * 2
        for row in order:
            d0, d1, m0, m1 = records[row]
            data = ((d0 << 16) | (d1 << 8)) >> bits
            mask = (((m0 << 16) | (m1 << 8) | 255) >> bits)
            mask |= ((1 << bits) - 1) << (24 - bits)
            ds = tuple((data >> b) & 255 for b in (16, 8, 0))
            ms = tuple((mask >> b) & 255 for b in (16, 8, 0))
            accent = sum(bool(d & ~(d << 1) & 0xaa) << i for i, d in enumerate(ds))
            tail = (ds[2], ms[2], accent)
            if tail not in tails: tails.append(tail)
            shifted.append((ds[0], ds[1], ms[0], ms[1], tails.index(tail)))
    assert len(tails) <= 16 and len(shifted) <= 256 and len(shifted) % 2 == 0
    (out / 'shifted-data.bin').write_bytes(bytes(row[field] for field in range(2) for row in shifted))
    (out / 'shifted-masks.bin').write_bytes(bytes(row[field] for field in (2,3) for row in shifted))
    (out / 'shifted-tails.bin').write_bytes(bytes(shifted[i][4] | shifted[i+1][4] << 4
                                                for i in range(0,len(shifted),2)))
    (out / 'tail-records.bin').write_bytes(bytes(row[field] for field in range(3) for row in tails))
    (out / 'pose-accents.bin').write_bytes(bytes(any(ACCENT in row for row in im) for im in images))
    (out / 'mc-assets.inc').write_text(f'.set POSE_COUNT,{len(images)}\n.set ROW_RECORDS,{len(records)}\n.set SHIFTED_ROWS,{len(shifted)}\n.set TAIL_RECORDS,{len(tails)}\n')
    (out / 'poses.json').write_text(json.dumps({'names': names, 'images': images}, indent=2) + '\n')
    # Generic text/decorations use the existing masks. Maze walls and pellets
    # use exactly the approved custom artwork, independent of the ROM palette.
    source = (ROOT / 'build/arcade/rom.c').read_text()
    old_tiles = table(source, 'arcade_tiles')
    walls = tile_walls(json.loads((ROOT / 'docs/artwork/maze-wall-tiles.json').read_text())['tiles'])
    tiles = []
    for code in range(256):
        for y in range(6):
            if code in walls:
                row = walls[code][y]
            elif code == 16:
                row = [0, 3 if y == 3 else 0, 0]
            elif code == 20:
                row = [0, 3, 0] if y in (1, 4) else [3, 3, 3] if y in (2, 3) else [0, 0, 0]
            elif code in (18, 64, 252, 253):
                row = [0, 0, 0]
            else:
                raw = old_tiles[code * 3 + y // 2] >> (0 if y & 1 else 4) & 15
                row = [3 if raw & 8 else 0, 3 if raw & 6 else 0, 3 if raw & 1 else 0]
            tiles.append(sum(value << (4 - 2 * x) for x, value in enumerate(row)))
    fonts = [bytes(8)] + [font_glyph(artwork['font'][char]) for char in '0123456789UPHIG']
    fonts += [font_glyph(artwork['life_icon'], 0), font_glyph(artwork['cherry_icon'], 0)]
    tile_patterns = [bytes(tiles[i:i + 6]) for i in range(0, len(tiles), 6)]
    tile_atlas = sorted(set(tile_patterns))
    tile_ids = bytes(tile_atlas.index(tile) for tile in tile_patterns)
    def array(name, values):
        return f'const unsigned char {name}[{len(values)}] __attribute__((section(".arcade_data"))) = {{\n' + ','.join(str(v) for v in values) + '\n};\n'
    (out / 'assets.c').write_text(array('mc_tiles', b''.join(tile_atlas)) + array('mc_tile_ids', tile_ids) + array('mc_font', b''.join(fonts)).replace('.arcade_data', '.mc_low_tables'))
    (out / 'assets.h').write_text(f'extern const unsigned char mc_tiles[{len(tile_atlas) * 6}], mc_tile_ids[256], mc_font[144];\n')


if __name__ == '__main__':
    main()
