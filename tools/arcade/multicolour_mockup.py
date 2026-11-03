#!/usr/bin/env python3
"""Build VIC-native multicolour artwork, a complete pellet atlas and a static PRG.

This is an isolated visual study, not a replacement game renderer. Original
arcade screen codes, coordinates, score bytes and movement logic are inputs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw

from maze_mockup import COLORS, ROOT, font, position

NATIVE_WIDTH, HEIGHT, COLS, ROWS = 168, 216, 21, 27
MULTI_WIDTH, TILE_WIDTH, TILE_HEIGHT = 84, 3, 6
BACKGROUND, WALL, ACCENT, WHITE, TRANSPARENT = 0, 1, 2, 3, -1


def tile_walls(definitions):
    """Author square three-pixel contours from the existing custom wall pieces."""
    walls = {}
    for item in definitions:
        rows = []
        for row in item["rows"]:
            ink = [x for x, value in enumerate(row) if value == "#"]
            line = [0] * 3
            if ink:
                first, last = (0 if min(ink) < 2 else 2), (0 if max(ink) < 2 else 2)
                for x in range(first, last + 1):
                    line[x] = WALL
            rows.append(line)
        if item["codes"] == ["ce", "cf"]:
            rows = [[0] * 3 for _ in range(6)]
            rows[3] = [WHITE, 0, WHITE]
        for code in item["codes"]:
            walls[int(code, 16)] = rows
    return walls


def blank_grid():
    return [bytearray(MULTI_WIDTH) for _ in range(HEIGHT)]


def pack_grid(grid):
    return [bytes(sum(grid[cy * 8 + y][cx * 4 + x] << (6 - 2 * x) for x in range(4))
                  for y in range(8)) for cy in range(ROWS) for cx in range(COLS)]


def maze_grid(fixture, walls, pellets=True):
    grid = blank_grid()
    pellet_masks = []
    for offset, code in enumerate(fixture[0x4000:0x4400]):
        xy = position(offset)
        if xy is None or not fixture[0x4400 + offset] & 31:
            continue
        tx, ty = xy
        x, y = tx * TILE_WIDTH, ty * TILE_HEIGHT
        if code >= 192:
            for dy, row in enumerate(walls[code]):
                grid[y + dy][x:x + 3] = bytes(row)
        elif code in (16, 20):
            points = [(1, 3)] if code == 16 else [(1, 1), (0, 2), (1, 2), (2, 2), (0, 3), (1, 3), (2, 3), (1, 4)]
            fragments = {}
            for dx, dy in points:
                px, py = x + dx, y + dy
                cell = (py // 8) * COLS + px // 4
                fragments.setdefault(cell, bytearray(8))[py & 7] |= WHITE << (6 - 2 * (px & 3))
                if pellets:
                    grid[py][px] = WHITE
            pellet_masks.append({"offset": offset, "tile": [tx, ty], "code": code, "fragments": fragments})
    return grid, pellet_masks


def font_glyph(rows, inset=1):
    assert len(rows) in (7, 8) and all(len(row) + inset <= 8 for row in rows)
    return bytes([sum((value == "#") << (7 - x - inset) for x, value in enumerate(row)) for row in rows]
                 + [0] * (8 - len(rows)))


def score_text(fixture, address):
    """Retain six BCD positions and the arcade's four-leading-blank limit."""
    digits = "".join(f"{b:02x}" for b in reversed(fixture[address:address + 3]))
    assert set(digits) <= set("0123456789")
    result, blanks = [], 4
    for value in digits:
        if value != "0":
            blanks = 0
        result.append(" " if blanks else value)
        if blanks:
            blanks -= 1
    return "".join(result)


def add_hud(patterns, colors, fixture, assets, sample=False):
    glyphs = {char: font_glyph(rows) for char, rows in assets["font"].items()}
    glyphs[" "] = bytes(8)
    hud = {}
    for row in (0, 1, 26):
        for col in range(COLS):
            cell = row * COLS + col
            hud[cell] = bytes(8)
            colors[cell] = 1

    def text(col, row, value):
        for offset, char in enumerate(value):
            hud[row * COLS + col + offset] = glyphs[char]

    text(2, 0, "1UP")
    text(8, 0, "HIGH")
    text(0, 1, "123456" if sample else score_text(fixture, 0x4E80))
    text(7, 1, "789000" if sample else score_text(fixture, 0x4E88))
    if sample:
        text(16, 0, "2UP")
        text(14, 1, "038956")
    for col in (1, 2):
        cell = 26 * COLS + col
        hud[cell], colors[cell] = font_glyph(assets["life_icon"], 0), 7
    text(10, 26, str(fixture[0x4E13] + 1))
    cell = 26 * COLS + 19
    hud[cell], colors[cell] = font_glyph(assets["cherry_icon"], 0), 2
    for cell, pattern in hud.items():
        patterns[cell] = pattern
    return glyphs, hud


def ghost(assets, orientation=0, phase=0, frightened=False):
    body = assets["ghost_body_alternate" if phase else "ghost_body"]
    image = [[(WALL if frightened else ACCENT) if value == "a" else TRANSPARENT for value in row] for row in body]
    if frightened:
        for x in (1, 4):
            image[4][x] = image[5][x] = WHITE
        for x in range(1, 5):
            image[9 + (x & 1)][x] = WHITE
        return image
    for y in range(3, 7):
        for x in (0, 1, 4, 5):
            image[y][x] = WHITE
    pupil_x = (1, 5) if orientation == 0 else (0, 4) if orientation == 2 else (1, 4)
    pupil_y = (3, 4) if orientation == 3 else (5, 6) if orientation == 1 else (4, 5)
    for y in pupil_y:
        for x in pupil_x:
            image[y][x] = BACKGROUND
    return image


def pacman(orientation=0, phase=1):
    image = [[TRANSPARENT] * 6 for _ in range(14)]
    for y in range(14):
        for x in range(6):
            nx, ny = (x - 2.5) / 3, (y - 6.5) / 7
            if nx * nx + ny * ny > 1:
                continue
            forward, side = ((nx, ny), (ny, nx), (-nx, ny), (-ny, nx))[orientation]
            if phase and forward > 0 and abs(side) < forward * (0.55 if phase == 2 else 0.22):
                continue
            image[y][x] = ACCENT
    eye_x, eye_y = ((3, 3), (1, 7), (2, 3), (4, 6))[orientation]
    if image[eye_y][eye_x] == ACCENT:
        image[eye_y][eye_x] = BACKGROUND
    return image


def frame(fixture, walls, assets, kind="normal", pellets=True):
    base, _ = maze_grid(fixture, walls, pellets)
    grid = [bytearray(row) for row in base]
    colors = [8 | 6] * (COLS * ROWS)
    owners = {}
    overwritten = set()
    if kind not in ("maze", "digits"):
        for slot in (10, 8, 6, 4, 2):
            attr, pal = fixture[0x4C20 + slot:0x4C22 + slot]
            if not pal & 31:
                continue
            raw_x, raw_y = fixture[0x4C30 + slot:0x4C32 + slot]
            x = ((239 - raw_x - (slot <= 4)) * 3) // 8
            y = ((272 - raw_y) * 3) // 4 - 1
            if slot == 10:
                image = pacman(fixture[0x4D30] & 3, 2)
                accent = 7
            else:
                index = slot // 2 - 1
                image = ghost(assets, fixture[0x4D2C + index] & 3, (attr >> 2) & 1, kind == "frightened")
                accent = (2, 4, 3, 7)[index]
            if kind == "overlap" and slot != 10:
                x, y = 34 + slot // 2, 80 + slot // 2
            for dy, row in enumerate(image):
                for dx, value in enumerate(row):
                    px, py = x + dx, y + dy
                    if value == TRANSPARENT or not (0 <= px < MULTI_WIDTH and 16 <= py < 208):
                        continue
                    grid[py][px] = value
                    overwritten.add((px, py))
                    if value == ACCENT:
                        cell = (py // 8) * COLS + px // 4
                        colors[cell] = 8 | accent
                        owners.setdefault(cell, set()).add(accent)
    # Global blue and white pixels that actors do not cover retain their colours.
    assert all(grid[y][x] == value for y, row in enumerate(base) for x, value in enumerate(row)
               if value in (WALL, WHITE) and (x, y) not in overwritten)
    patterns = pack_grid(grid)
    glyphs, hud = add_hud(patterns, colors, fixture, assets, sample=kind == "digits")
    return patterns, colors, {"actor_accent_clash_cells": len([v for v in owners.values() if len(v) > 1])}, glyphs, hud


def decode(patterns, colors, palette=COLORS):
    im = Image.new("RGB", (NATIVE_WIDTH, HEIGHT))
    for cell, (pattern, color) in enumerate(zip(patterns, colors)):
        cx, cy = cell % COLS, cell // COLS
        for y, row in enumerate(pattern):
            if color & 8:
                sources = (0, 6, color & 7, 1)
                for x in range(4):
                    rgb = palette[sources[(row >> (6 - x * 2)) & 3]]
                    im.putpixel((cx * 8 + x * 2, cy * 8 + y), rgb)
                    im.putpixel((cx * 8 + x * 2 + 1, cy * 8 + y), rgb)
            else:
                for x in range(8):
                    im.putpixel((cx * 8 + x, cy * 8 + y), palette[color & 7] if row & (128 >> x) else palette[0])
    return im


def pellet_atlas(fixture, walls):
    empty, masks = maze_grid(fixture, walls, pellets=False)
    domains = [{p} for p in pack_grid(empty)]
    for pellet in masks:
        for cell, fragment in pellet["fragments"].items():
            domains[cell] |= {bytes(a | b for a, b in zip(pattern, fragment)) for pattern in domains[cell]}
    # The three HUD rows have separate hires glyphs and no maze pixels.
    for cell in list(range(COLS * 2)) + list(range(COLS * 26, COLS * 27)):
        assert domains[cell] == {bytes(8)}
    atlas = set().union(*domains)
    full, _ = maze_grid(fixture, walls)
    assert all(p in atlas for p in pack_grid(full))
    return atlas, masks, domains


def concurrent_pattern_bound(domains):
    """Prove an upper bound with equal-size matching and vertex-cover witnesses.

    A cell can show one of its local patterns. Every distinct visible pattern
    needs a different representative cell, so a maximum bipartite matching
    bounds the number of simultaneously distinct glyphs. Coupled power-pellet
    fragments only restrict the choices further.
    """
    matched = {}

    def augment(cell, seen):
        for pattern in sorted(domains[cell]):
            if pattern in seen:
                continue
            seen.add(pattern)
            if pattern not in matched or augment(matched[pattern], seen):
                matched[pattern] = cell
                return True
        return False

    for cell in range(len(domains)):
        augment(cell, set())
    reverse = {cell: pattern for pattern, cell in matched.items()}
    left = set(range(len(domains))) - set(reverse)
    right, pending = set(), list(left)
    while pending:
        cell = pending.pop()
        for pattern in domains[cell]:
            if reverse.get(cell) == pattern or pattern in right:
                continue
            right.add(pattern)
            if pattern in matched and matched[pattern] not in left:
                left.add(matched[pattern])
                pending.append(matched[pattern])
    cover_left = set(range(len(domains))) - left
    assert all(cell in cover_left or pattern in right
               for cell, patterns in enumerate(domains) for pattern in patterns)
    assert len(cover_left) + len(right) == len(matched)
    return {
        "matching_size": len(matched), "vertex_cover_size": len(cover_left) + len(right),
        "all_domain_edges_covered": True,
    }


def presentation(current, proposed):
    canvas = Image.new("RGB", (1856, 1112), "#111820")
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 26), "VIC-MAN / MULTICOLOUR ARTWORK PROTOTYPE", font=font(30, True), fill="white")
    draw.text((40, 75), "Original maze routes. Blue walls, white pellets, custom actors and hires score digits.", font=font(19), fill="#b7c5d3")
    for x, title, detail, im, size in (
        (40, "CURRENT GEOMETRY", "112 x 216 native dots; existing artwork", current, (672, 864)),
        (808, "WIDER VIC DESIGN", "168 x 216 native dots; six-pixel ghost faces", proposed, (1008, 864)),
    ):
        draw.text((x, 124), title, font=font(23, True), fill="#88e4cc" if x == 808 else "#d3dce6")
        draw.text((x, 157), detail, font=font(17), fill="#b7c5d3")
        canvas.paste(im.resize(size, Image.Resampling.NEAREST), (x, 194))
    draw.text((40, 1076), "Equal NTSC dot scale in both panels. Offline artwork study; game logic and playable build unchanged.", font=font(16), fill="#b7c5d3")
    return canvas


def gallery(assets):
    canvas = Image.new("RGB", (1104, 608), "#111820")
    draw = ImageDraw.Draw(canvas)
    draw.text((28, 20), "ACTOR AND SCORE READABILITY", font=font(28, True), fill="white")
    draw.text((28, 66), "Each multicolour pixel is three times as wide as a scanline is high on NTSC.", font=font(17), fill="#b7c5d3")
    for n, (name, sprite, accent) in enumerate([
        ("Right", ghost(assets, 0), 2), ("Down", ghost(assets, 1), 4),
        ("Left", ghost(assets, 2), 3), ("Up", ghost(assets, 3), 7),
        ("Frightened", ghost(assets, frightened=True), 6),
    ]):
        im = Image.new("RGB", (12, 14))
        for y, row in enumerate(sprite):
            for x, value in enumerate(row):
                if value != TRANSPARENT:
                    rgb = COLORS[(0, 6, accent, 1)[value]]
                    im.putpixel((x * 2, y), rgb); im.putpixel((x * 2 + 1, y), rgb)
        px = 32 + n * 210
        canvas.paste(im.resize((144, 112), Image.Resampling.NEAREST), (px, 125))
        draw.text((px, 252), name, font=font(18), fill="white")
    for n in range(3):
        sprite = pacman(0, n)
        im = Image.new("RGB", (12, 14))
        for y, row in enumerate(sprite):
            for x, value in enumerate(row):
                if value != TRANSPARENT:
                    rgb = COLORS[7] if value == ACCENT else COLORS[0]
                    im.putpixel((x * 2, y), rgb); im.putpixel((x * 2 + 1, y), rgb)
        canvas.paste(im.resize((144, 112), Image.Resampling.NEAREST), (32 + n * 210, 315))
    draw.text((710, 326), "Pac-Man: closed, small and open mouth", font=font(17), fill="#b7c5d3")
    draw.text((28, 463), "5 x 7 digits in separate hires characters", font=font(18), fill="#88e4cc")
    for n in range(10):
        bits = font_glyph(assets["font"][str(n)])
        im = Image.new("RGB", (8, 8))
        for y, row in enumerate(bits):
            for x in range(8):
                if row & (128 >> x): im.putpixel((x, y), COLORS[1])
        canvas.paste(im.resize((72, 48), Image.Resampling.NEAREST), (28 + n * 104, 510))
    return canvas


def static_prg(output, patterns, colors, ca65, ld65):
    """Small standalone VIC display, independent of the Pac-Man executable."""
    atlas = sorted(set(patterns))
    assert len(atlas) <= 256
    codes = {pattern: n for n, pattern in enumerate(atlas)}
    (output / "charset.bin").write_bytes(b"".join(atlas).ljust(2048, b"\0"))
    (output / "screen.bin").write_bytes(bytes(codes[p] for p in patterns))
    (output / "colors.bin").write_bytes(bytes(colors))
    assembly = '''.setcpu "6502"
.segment "LOADADDR"
.word $1201
.segment "CODE"
.word basic_end
.word 10
.byte $9e,"4621",0
basic_end: .word 0
.export entry,display_ready
entry:
 sei
 cld
 lda #$7f
 sta $911e
 sta $912e
 lda #0
 sta $9002
 sta $900a
 sta $900b
 sta $900c
 sta $900d
 lda #$10
 sta $900e
 lda #$0e
 sta $900f
 ldx #0
copy:
.repeat 8,N
 lda character_data+N*256,x
 sta $1000+N*256,x
.endrepeat
 lda matrix_data,x
 sta $1800,x
 lda matrix_data+256,x
 sta $1900,x
 lda color_data,x
 sta $9400,x
 lda color_data+256,x
 sta $9500,x
 cpx #55
 bcs skip_tail
 lda matrix_data+512,x
 sta $1a00,x
 lda color_data+512,x
 sta $9600,x
skip_tail:
 inx
 bne copy
 lda #12
 sta $9000
 lda #18
 sta $9001
 lda #$ec
 sta $9005
 lda #54
 sta $9003
 lda #21
 sta $9002
display_ready:
 jmp display_ready
character_data: .incbin "charset.bin"
matrix_data: .incbin "screen.bin"
color_data: .incbin "colors.bin"
'''
    # Pad the PRG from its BASIC entry through the expansion-RAM code area.
    config = '''MEMORY { LOAD: start=$11ff,size=2,file=%O; BASIC: start=$1201,size=$dff,file=%O,fill=yes; RAM: start=$2000,size=$6000,file=%O; }
SEGMENTS { LOADADDR: load=LOAD,type=ro; CODE: load=RAM,type=ro; }
'''
    # The BASIC stub belongs at $1201; only the copy loop/data live at $2000.
    assembly = assembly.replace('.segment "CODE"\n.word basic_end', '.segment "BASIC"\n.word basic_end')
    assembly = assembly.replace('basic_end: .word 0\n.export', 'basic_end: .word 0\njmp entry\n.segment "CODE"\n.export')
    config = config.replace('CODE: load=RAM,type=ro;', 'BASIC: load=BASIC,type=ro; CODE: load=RAM,type=ro;')
    (output / "display.s").write_text(assembly)
    (output / "display.cfg").write_text(config)
    subprocess.run([str(ca65), "display.s", "-o", "display.o"], cwd=output, check=True)
    subprocess.run([str(ld65), "-C", "display.cfg", "-Ln", "display.lbl", "display.o", "-o", "display.prg"], cwd=output, check=True)
    return len(atlas)


def html(output):
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VIC-MAN multicolour artwork prototype</title><style>
body{background:#111820;color:#edf2f7;font:16px system-ui,sans-serif;margin:0;padding:28px;max-width:1816px;margin-inline:auto}
h1{font-size:clamp(24px,4vw,36px);margin:0 0 10px}p{line-height:1.6;color:#bac9d8;max-width:90ch}a{color:#88e4cc}
.controls{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin:24px 0}select{font:inherit;padding:6px;background:#202c38;color:white;border:1px solid #5c7285;border-radius:4px}
.pair{display:grid;grid-template-columns:2fr 3fr;gap:28px;align-items:start}.card h2{font-size:19px}.card:last-child h2{color:#88e4cc}
canvas{display:block;width:100%;height:auto;image-rendering:pixelated;background:#000}.art{width:min(100%,1104px);height:auto;image-rendering:pixelated}
.notes{margin-top:26px;padding-top:14px;border-top:1px solid #34404e}
@media(max-width:850px){body{padding:18px}.pair{grid-template-columns:1fr}}
</style><h1>Blue walls. White pellets. Custom VIC artwork.</h1>
<p>The same maze routes in a wider presentation, with six-pixel ghost faces and separate hires score digits.
The two panels use the same NTSC dot proportions.</p>
<div class="controls"><label>View <select id="view"><option value="normal">Original starting positions</option><option value="maze">Maze only</option>
<option value="frightened">Frightened artwork</option><option value="overlap">Actor colour-sharing example</option><option value="digits">Full-width score examples</option></select></label>
<label><input id="pellets" type="checkbox" checked> Pellets present</label><label><input id="grid" type="checkbox"> Character grid</label></div>
<div class="pair"><section class="card"><h2>Current artwork and geometry</h2><canvas id="current" width="672" height="864"></canvas></section>
<section class="card"><h2>Wider multicolour design</h2><canvas id="proposed" width="1008" height="864"></canvas></section></div>
<div class="notes"><p>This is a static artwork study. It does not demonstrate game speed or reduced flicker. Blue walls and white dots use shared colours;
two actors sharing a colour cell can still share their body colour. The frightened and overlap views illustrate artwork rather than simulated game states.</p>
<p><a href="../../MULTICOLOUR_PROTOTYPE.md">Read the memory budget and validation</a> · <a href="comparison.png">Save comparison</a>
 · <a href="../../MULTICOLOUR_MOTION.md">Moving renderer test</a></p></div>
<h2>Actor and numeral detail</h2><img class="art" src="actors-and-digits.png" alt="Custom directional ghost faces, Pac-Man mouth frames and digits zero through nine">
<script>
const cache={};for(const name of ['normal','maze','frightened','overlap','digits'])for(const suffix of ['','-empty']){
 const im=new Image();im.onload=draw;im.src=name+suffix+'.png';cache[name+suffix]=im;
}for(const name of ['current','current-empty']){const im=new Image();im.onload=draw;im.src=name+'.png';cache[name]=im}
function draw(){
 const suffix=document.querySelector('#pellets').checked?'':'-empty';
 for(const [id,key,cols,ch] of [['current','current'+suffix,14,16],['proposed',document.querySelector('#view').value+suffix,21,8]]){
  const c=document.getElementById(id),ctx=c.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,c.width,c.height);
  if(cache[key]?.complete)ctx.drawImage(cache[key],0,0,c.width,c.height);
  if(document.querySelector('#grid').checked){ctx.strokeStyle='rgba(80,220,200,.55)';ctx.lineWidth=1;ctx.beginPath();
   for(let x=0;x<=c.width;x+=48){ctx.moveTo(x+.5,0);ctx.lineTo(x+.5,c.height)}
   for(let y=0;y<=c.height;y+=ch*4){ctx.moveTo(0,y+.5);ctx.lineTo(c.width,y+.5)}ctx.stroke()}
 }
}document.querySelectorAll('input,select').forEach(el=>el.addEventListener('change',draw));
</script></html>'''
    (output / "index.html").write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/artwork/multicolour")
    parser.add_argument("--build", type=Path, default=ROOT / "build/multicolour")
    parser.add_argument("--fixture", type=Path, default=ROOT / "build/arcade/tests/game.ram")
    args = parser.parse_args()
    output, build = args.output.resolve(), args.build.resolve()
    output.mkdir(parents=True, exist_ok=True); build.mkdir(parents=True, exist_ok=True)
    fixture = args.fixture.read_bytes()
    definitions = json.loads((ROOT / "docs/artwork/maze-wall-tiles.json").read_text())["tiles"]
    assets = json.loads((ROOT / "docs/artwork/multicolour/actors-and-font.json").read_text())
    walls = tile_walls(definitions)
    (output / "maze-tiles.json").write_text(json.dumps({
        "description": "Derived custom tiles: three multicolour pixels by six scanlines; b=global blue, w=global white, .=black.",
        "tiles": [{"code": f"{code:02x}", "rows": ["".join(".baw"[value] for value in row) for row in walls[code]]}
                  for code in sorted(walls)],
    }, indent=2) + "\n")
    assert fixture[0x4000:0x4400].count(16) == 240 and fixture[0x4000:0x4400].count(20) == 4
    frames = {}
    for kind in ("normal", "maze", "frightened", "overlap", "digits"):
        for pellets in (True, False):
            patterns, colors, info, glyphs, hud = frame(fixture, walls, assets, kind, pellets)
            assert len(patterns) == len(colors) == 567
            im = decode(patterns, colors)
            name = kind + ("" if pellets else "-empty")
            im.save(output / (name + ".png"))
            frames[name] = (patterns, colors, info)
    im = decode(*frames["normal"][:2])
    im.resize((1008, 864), Image.Resampling.NEAREST).save(output / "normal-ntsc.png")
    for suffix in ("", "-empty"):
        current = Image.open(ROOT / f"docs/artwork/maze-current{suffix}-actors.png").convert("RGB")
        current.save(output / f"current{suffix}.png")
    presentation(Image.open(output / "current.png"), im).save(output / "comparison.png")
    gallery(assets).save(output / "actors-and-digits.png")
    html(output)
    atlas, masks, domains = pellet_atlas(fixture, walls)
    all_fonts = {font_glyph(rows) for rows in assets["font"].values()}
    all_fonts |= {font_glyph(assets["life_icon"], 0), font_glyph(assets["cherry_icon"], 0)}
    permanent = atlas | all_fonts
    (build / "all-maze-pellet-states.bin").write_bytes(b"".join(sorted(atlas)))
    (build / "all-hud-glyphs.bin").write_bytes(b"".join(sorted(all_fonts)))
    bound = concurrent_pattern_bound(domains + [{p} for p in sorted(all_fonts)])
    ca65, ld65 = ROOT / "tools/cc65/usr/bin/ca65", ROOT / "tools/cc65/usr/bin/ld65"
    static_count = static_prg(build, *frames["normal"][:2], ca65, ld65)
    runner = build / "run.sh"
    runner.write_text('''#!/bin/sh
set -eu
vic_multicolour_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec xvic -model vic20ntsc -memory all -autostartprgmode 1 -autostart "$vic_multicolour_dir/display.prg"
''')
    runner.chmod(0o755)
    report = {
        "status": "isolated artwork and static display prototype; main game unchanged",
        "main_game_prg_sha256": hashlib.sha256((ROOT / "build/pacman.prg").read_bytes()).hexdigest(),
        "fixture_sha256": hashlib.sha256(fixture).hexdigest(),
        "art_sha256": hashlib.sha256((ROOT / "docs/artwork/multicolour/actors-and-font.json").read_bytes()).hexdigest(),
        "native_dots": [NATIVE_WIDTH, HEIGHT], "multicolour_pixels": [MULTI_WIDTH, HEIGHT],
        "hardware_cells": [COLS, ROWS], "character_dimensions": [8, 8], "matrix_bytes": COLS * ROWS,
        "palette_sources": {"00": "black background", "01": "blue border", "10": "per-cell actor accent", "11": "white auxiliary"},
        "regular_pellets": 240, "power_pellets": 4, "pellet_positions": "original logical tile centres; reauthored masks",
        "actor_multicolour_dimensions": [6, 14], "hires_font_dimensions": [5, 7],
        "maze_all_pellet_state_characters": len(atlas),
        "hires_font_and_status_characters": len(all_fonts),
        "combined_permanent_characters": len(permanent),
        "permanent_character_bytes": len(permanent) * 8,
        "remaining_work_characters": 256 - len(permanent),
        "remaining_work_bytes": (256 - len(permanent)) * 8,
        "demand_loaded_background_and_hud_bound": bound,
        "demand_loaded_work_characters": 256 - bound["matching_size"],
        "six_actors_old_and_new_9_cell_footprints": 6 * 2 * 9,
        "spare_characters_after_that_bound": 256 - bound["matching_size"] - 6 * 2 * 9,
        "static_demo_visible_characters": static_count,
        "normal_actor_accent_clash_cells": frames["normal"][2]["actor_accent_clash_cells"],
        "overlap_actor_accent_clash_cells": frames["overlap"][2]["actor_accent_clash_cells"],
        "regions": {"charset": [0x1000, 0x1800], "matrix": [0x1800, 0x1800 + 567],
                    "available_internal_gap": [0x1800 + 567, 0x1C40], "virtual_io_retained": [0x1C40, 0x1D40],
                    "software_stack_retained": [0x1D40, 0x2000], "colour_ram": [0x9400, 0x9400 + 567]},
        "static_prg_sha256": hashlib.sha256((build / "display.prg").read_bytes()).hexdigest(),
        "limitations": [
            "Static image and PRG: no game logic, sound, input, dynamic glyph allocator or moving-actor timing is implemented here.",
            "Actors have more horizontal detail than a same-width multicolour conversion, but fewer independent columns than today's eight-pixel hires masks.",
            "Each ghost is six multicolour pixels wide and fourteen scanlines tall; the graphic is one scanline taller above/below the current actor footprint.",
            "Normal actor accents remain per colour cell; overlapping accents can clash. Shared blue walls and white dots do not adopt actor colours.",
            "The permanent atlas covers this maze's every local present/absent pellet state and all defined HUD glyphs, not every attract, intermission or game-over screen.",
            "Work-character headroom is not a complete renderer budget. Simultaneously live old/new actor cells and fruit must fit, with cache ownership and colour updates.",
            "The demand-loaded bound requires a reference-counted background glyph cache; the static PRG does not implement that cache or actor buffering.",
            "Blue is also the border colour in this palette. A black outer border would need a separately measured raster technique.",
            "The white auxiliary colour occupies the high nibble of $900e; an integrated audio driver must preserve it while setting volume.",
        ],
    }
    (output / "analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
