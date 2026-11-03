#!/usr/bin/env python3
"""Render an offline maze artwork study and count exact 8x16 character patterns.

Uses the original full-board fixture made by tests/arcade.py and the existing
generated tile masks. Does not write game sources, ROM tables or executables.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WIDTH, HEIGHT, STORAGE_HEIGHT = 112, 216, 224
WHITE = (255, 255, 255)
COLORS = ((0, 0, 0), WHITE, (182, 31, 33), (77, 240, 255),
          (180, 63, 255), (68, 226, 55), (26, 52, 255), (220, 215, 27))


def table(source, name):
    body = re.search(r"\b" + name + r"\[.*?= \{(.*?)\};", source, re.S)[1]
    return bytes(int(v, 16) for v in re.findall(r"0x[0-9a-f]+", body))


def position(offset):
    col, row = divmod(offset, 32)
    if 2 <= col < 30:
        return 29 - col, row + 2
    if 2 <= row < 30:
        return 29 - row, col + 34 if col < 2 else col - 30
    return None


def stamp(bitmap, x, y, rows):
    for dy, bits in enumerate(rows):
        bitmap[(x // 2) * STORAGE_HEIGHT + y * 6 + dy] |= bits << (0 if x & 1 else 4)


def background_colors(fixture, tiles, source):
    classes, palette = table(source, "arcade_tile_class"), table(source, "arcade_colors")
    colors, walls = [0] * 196, set()
    for offset, code in enumerate(fixture[0x4000:0x4400]):
        xy = position(offset)
        pal = fixture[0x4400 + offset] & 31
        if xy is None or not pal or not any(tiles[code]):
            continue
        x, y = xy
        if code >= 192 or code in (16, 18, 20):
            color = 1
        else:
            pixel_class = (classes[code // 4] >> ((code & 3) * 2)) & 3
            color = palette[pal * 4 + pixel_class]
        for row in range(y * 6 // 16, (y * 6 + 5) // 16 + 1):
            cell = row * 14 + x // 2
            if code >= 192:
                walls.add(cell)
            colors[cell] = 1 if cell in walls else color
    return colors


def image_from_bitmap(bitmap, cell_colors=None):
    im = Image.new("RGB", (WIDTH, HEIGHT))
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if bitmap[(x // 8) * STORAGE_HEIGHT + y] & (128 >> (x & 7)):
                color = COLORS[cell_colors[(y // 16) * 14 + x // 8]] if cell_colors is not None else WHITE
                im.putpixel((x, y), color)
    return im


def characters(bitmap):
    return [bytes(bitmap[x * STORAGE_HEIGHT + y * 16:x * STORAGE_HEIGHT + (y + 1) * 16])
            for y in range(14) for x in range(14)]


def with_actors(image, fixture, source):
    """Use the existing six-slot ordering and per-cell colour ownership."""
    sprites = table(source, "arcade_sprites")
    classes = table(source, "arcade_sprite_class")
    palette = table(source, "arcade_colors")
    im = image.copy()
    for off in range(12, 0, -2):
        attr, pal = fixture[0x4C20 + off:0x4C22 + off]
        if not pal & 31:
            continue
        raw_x, raw_y = fixture[0x4C30 + off:0x4C32 + off]
        x, y = (239 - raw_x - (off <= 4)) // 2, (272 - raw_y) * 3 // 4
        code, flip = attr >> 2, attr & 3
        color = COLORS[palette[(pal & 31) * 4 + ((classes[code // 4] >> ((code & 3) * 2)) & 3)]]
        for row in range(12):
            bits = sprites[code * 12 + (11 - row if flip & 1 else row)]
            if flip & 2:
                bits = int(f"{bits:08b}"[::-1], 2)
            for col in range(8):
                px, py = x + col, y + row
                if 0 <= px < WIDTH and 0 <= py < HEIGHT and bits & (128 >> col):
                    im.putpixel((px, py), WHITE)
        if not color or x <= -8 or x >= WIDTH:
            continue
        left, right = x // 8, x // 8 + bool(x & 7)
        top, bottom = y // 16, (y + 11) // 16
        for py in range(max(0, top * 16), min(HEIGHT, (bottom + 1) * 16)):
            for px in range(max(0, left * 8), min(WIDTH, (right + 1) * 8)):
                if im.getpixel((px, py)) != COLORS[0]:
                    im.putpixel((px, py), color)
    return im


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)


def compare_image(
    current, proposed, *,
    heading="VIC-MAN / MAZE ARTWORK STUDY",
    description="Same maze, pellet positions and display scale. Custom wall tiles only.",
    labels=(("CURRENT", "Scaled arcade wall artwork"),
            ("SIMPLIFIED", "Single outlines and square corners")),
    footer="NTSC proportions: each native pixel is shown 6 wide x 4 high. Static concept; no performance claim.",
):
    canvas = Image.new("RGB", (1512, 1112), "#111820")
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 26), heading, font=font(30, True), fill="white")
    draw.text((40, 75), description, font=font(19), fill="#b7c5d3")
    for x, (title, subtitle), im in zip((40, 800), labels, (current, proposed)):
        draw.text((x, 124), title, font=font(23, True), fill="#88e4cc" if x == 800 else "#d3dce6")
        draw.text((x, 157), subtitle, font=font(17), fill="#b7c5d3")
        canvas.paste(im.resize((672, 864), Image.Resampling.NEAREST), (x, 194))
    draw.text((40, 1076), footer, font=font(16), fill="#b7c5d3")
    return canvas


def blue_maze_study(fixture, source, tiles, bitmap, output):
    """Show legal hires colour choices from actual wall/pellet pixel support."""
    wall_mask, pellet_mask = bytearray(3136), bytearray(3136)
    pellet_fragments = []
    for offset, code in enumerate(fixture[0x4000:0x4400]):
        xy = position(offset)
        if xy is None or not fixture[0x4400 + offset] & 31:
            continue
        if code >= 192:
            stamp(wall_mask, *xy, tiles[code])
        elif code in (16, 20):
            stamp(pellet_mask, *xy, tiles[code])
            fragment = bytearray(3136)
            stamp(fragment, *xy, tiles[code])
            pellet_fragments.append((code, {i for i, c in enumerate(characters(fragment)) if any(c)}))
    walls = {i for i, c in enumerate(characters(wall_mask)) if any(c)}
    pellets = {i for i, c in enumerate(characters(pellet_mask)) if any(c)}
    blue_priority = background_colors(fixture, tiles, source)
    for cell in walls:
        blue_priority[cell] = 6
    white_priority = list(blue_priority)
    for cell in pellets:
        white_priority[cell] = 1
    white_view = image_from_bitmap(bitmap, white_priority)
    blue_view = image_from_bitmap(bitmap, blue_priority)
    for name, im in (("white-pellet-priority", white_view), ("wall-priority", blue_view)):
        im.save(output / f"maze-blue-{name}.png")
        im.resize((672, 864), Image.Resampling.NEAREST).save(output / f"maze-blue-{name}-ntsc.png")
    affected = sum(bool(cells & walls) for _, cells in pellet_fragments)
    compare_image(
        white_view, blue_view,
        heading="VIC-MAN / BLUE MAZE COLOUR STUDY",
        description="Actual 8 x 16 hires colour cells. Each cell has one foreground colour. Actors omitted.",
        labels=(("WHITE PELLETS", "Shared walls stay white; other walls blue"),
                ("BLUE WALLS", f"All {affected} standing pellets also turn blue")),
        footer="Hardware-valid palette choices at the current resolution. Artwork study only; playable build unchanged.",
    ).save(output / "maze-blue-comparison.png")
    return {
        "scope": "simplified full board, hires, current geometry, no actors",
        "wall_pixel_cells": len(walls),
        "pellet_pixel_cells": len(pellets),
        "shared_wall_and_pellet_cells": len(walls & pellets),
        "wall_only_cells": len(walls - pellets),
        "pellet_only_cells": len(pellets - walls),
        "regular_pellets_affected_by_blue_wall_priority": sum(code == 16 and bool(cells & walls) for code, cells in pellet_fragments),
        "power_pellets_affected_by_blue_wall_priority": sum(code == 20 and bool(cells & walls) for code, cells in pellet_fragments),
        "wall_pixels": sum(b.bit_count() for b in wall_mask),
        "wall_pixels_that_can_be_blue_with_white_pellets": sum(
            sum(b.bit_count() for b in pattern)
            for i, pattern in enumerate(characters(wall_mask)) if i not in pellets
        ),
        "all_blue_walls_and_white_pellets_possible_in_current_hires_geometry": not bool(walls & pellets),
        "runtime_changes_enabled": False,
    }


def analyze(base, empty, pellets, hud_cells):
    full_chars, empty_chars = characters(base), characters(empty)
    pieces = [[] for _ in range(196)]
    for pellet in pellets:
        mask = bytearray(3136)
        stamp(mask, pellet["x"], pellet["y"], pellet["rows"])
        for cell, pattern in enumerate(characters(mask)):
            if any(pattern):
                pieces[cell].append(pattern)
    variants = set()
    for cell, masks in enumerate(pieces):
        states = {empty_chars[cell]}
        for mask in masks:
            states |= {bytes(a | b for a, b in zip(pattern, mask)) for pattern in states}
        variants.update(states)
        assert full_chars[cell] in states, f"full pellet cell {cell} missing from variants"
    mutable = {i for i, p in enumerate(pieces) if p} | hud_cells
    shared = {pattern for i, pattern in enumerate(empty_chars) if i not in mutable}
    conservative = len(mutable) + len(shared)
    return {
        "full_board_unique_8x16": len(set(full_chars)),
        "full_board_pattern_bytes": len(set(full_chars)) * 16,
        "empty_board_unique_8x16": len(set(empty_chars)),
        "all_local_pellet_variants_unique_8x16": len(variants),
        "pellet_mutable_cells": sum(bool(p) for p in pieces),
        "hud_reserved_cells": len(hud_cells),
        "pellet_or_hud_mutable_cells": len(mutable),
        "shared_fixed_patterns_outside_mutable_cells": len(shared),
        "conservative_background_slots": conservative,
        "conservative_background_bytes": conservative * 16,
        "potential_bytes_released_from_3136_byte_bitmap": (196 - conservative) * 16,
        "max_pellet_fragments_per_cell": max(map(len, pieces)),
    }


def write_html(output, images):
    # Each model's four images are: pellets, empty, actors+pellets, actors+empty.
    payload = {name: [str(p.relative_to(output)) for p in paths] for name, paths in images.items()}
    page = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VIC-MAN maze artwork study</title>
<style>
body{background:#111820;color:#edf2f7;font:16px system-ui,sans-serif;margin:0;padding:28px;max-width:1440px;margin-inline:auto}
h1{font-size:clamp(24px,4vw,36px);margin:0 0 10px}p{line-height:1.6;color:#bac9d8;max-width:82ch}
.controls{display:flex;gap:22px;flex-wrap:wrap;margin:24px 0}label{cursor:pointer}input{accent-color:#88e4cc}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px}.card h2{font-size:19px}.card:last-child h2{color:#88e4cc}
canvas{display:block;width:100%;height:auto;image-rendering:pixelated;background:#000}small{color:#bac9d8}
a{color:#88e4cc}.notes{margin-top:26px;padding-top:14px;border-top:1px solid #34404e}
@media(max-width:700px){body{padding:18px}.pair{grid-template-columns:1fr}}
</style>
<h1>Same maze. Simpler wall artwork.</h1>
<p>Original corridor layout and pellet positions, at the current NTSC display proportions.
The proposed maze uses single outlines and square corners. Scores and actor graphics use the existing artwork.</p>
<div class="controls"><label><input id="pellets" type="checkbox" checked> Pellets present</label>
<label><input id="actors" type="checkbox"> Current actors</label>
<label><input id="grid" type="checkbox"> 8 × 16 character grid</label></div>
<div class="pair"><section class="card"><h2>Current maze</h2><canvas id="current" width="672" height="864"></canvas></section>
<section class="card"><h2>Simplified maze</h2><canvas id="simplified" width="672" height="864"></canvas></section></div>
<div class="notes"><p>Artwork mockup only. The actor view includes the current colour-cell sharing;
it does not promise a colour-clash or flicker fix. No gameplay or renderer changes are enabled.</p>
<p><a href="../MAZE_MOCKUP.md">Read the character-memory findings</a> · <a href="maze-comparison.png">Save comparison image</a>
 · <a href="maze-blue-comparison.png">Blue maze colour study</a></p></div>
<script>
const paths = PAYLOAD;
const art = Object.fromEntries(Object.entries(paths).map(([name,paths]) => [name,paths.map(path => {
  const im = new Image(); im.src = path; im.onload = draw; return im;
})]));
function draw(){
  const index = (document.querySelector('#pellets').checked ? 0 : 1) + (document.querySelector('#actors').checked ? 2 : 0);
  for(const name of ['current','simplified']){
    const canvas = document.getElementById(name), ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;ctx.clearRect(0,0,672,864);
    if(art[name][index].complete)ctx.drawImage(art[name][index],0,0,672,864);
    if(document.querySelector('#grid').checked){
      ctx.strokeStyle = 'rgba(70,210,190,.5)';ctx.lineWidth = 1;
      ctx.beginPath();for(let x=0;x<=672;x+=48){ctx.moveTo(x+.5,0);ctx.lineTo(x+.5,864)}
      for(let y=0;y<=864;y+=64){ctx.moveTo(0,y+.5);ctx.lineTo(672,y+.5)}ctx.stroke();
    }
  }
}
document.querySelectorAll('input').forEach(input=>input.addEventListener('change',draw));
</script></html>
""".replace("PAYLOAD", json.dumps(payload))
    (output / "maze-mockup.html").write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=ROOT / "build/arcade/tests/game.ram")
    parser.add_argument("--rom-source", type=Path, default=ROOT / "build/arcade/rom.c")
    parser.add_argument("--art", type=Path, default=ROOT / "docs/artwork/maze-wall-tiles.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/artwork")
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    fixture, source = args.fixture.read_bytes(), args.rom_source.read_text()
    if len(fixture) != 65536:
        parser.error("fixture must be a 64 KB original-arcade RAM dump")
    screen, palettes = fixture[0x4000:0x4400], fixture[0x4400:0x4800]
    assert screen.count(16) == 240 and screen.count(20) == 4, "need a complete uneaten board"
    packed = table(source, "arcade_tiles")
    original = [[row for b in packed[i:i + 3] for row in (b >> 4, b & 15)]
                for i in range(0, len(packed), 3)]
    proposed = [list(rows) for rows in original]
    definitions = json.loads(args.art.read_text())["tiles"]
    covered = set()
    for item in definitions:
        assert len(item["rows"]) == 6 and all(len(row) == 4 and set(row) <= {".", "#"} for row in item["rows"])
        rows = [sum((v == "#") << (3 - x) for x, v in enumerate(row)) for row in item["rows"]]
        for value in item["codes"]:
            code = int(value, 16)
            assert code >= 192 and code not in covered
            covered.add(code)
            proposed[code] = rows
    assert {v for v in screen if v >= 192} <= covered, "wall artwork must cover every maze code"
    bitmaps = {name: bytearray(3136) for name in ("current", "simplified")}
    empty = {name: bytearray(3136) for name in bitmaps}
    pellets, cells, hud_cells = [], [], set()
    for offset, code in enumerate(screen):
        xy = position(offset)
        if xy is None:
            continue
        x, y = xy
        cells.append({"x": x, "y": y, "offset": offset, "code": code})
        if y in (0, 1, 34, 35):
            hud_cells.update((r // 16) * 14 + x // 2 for r in range(y * 6, y * 6 + 6))
        if code in (16, 20):
            pellets.append({"x": x, "y": y, "code": code, "rows": original[code]})
            assert proposed[code] == original[code], "pellet masks must stay identical"
        for name, tiles in (("current", original), ("simplified", proposed)):
            rows = tiles[code] if palettes[offset] & 31 else tiles[64]
            stamp(bitmaps[name], x, y, rows)
            if code not in (16, 20):
                stamp(empty[name], x, y, rows)
    # Wall changes cannot add a mark to a logical corridor, HUD or pellet tile.
    for cell in cells:
        if cell["code"] < 192:
            assert original[cell["code"]] == proposed[cell["code"]]
    images, full_views = {}, {}
    for name in bitmaps:
        tiles = original if name == "current" else proposed
        cell_colors = background_colors(fixture, tiles, source)
        full = image_from_bitmap(bitmaps[name], cell_colors)
        no_dots = image_from_bitmap(empty[name], cell_colors)
        full_views[name] = full
        views = (full, no_dots, with_actors(full, fixture, source), with_actors(no_dots, fixture, source))
        suffixes = ("", "-empty", "-actors", "-empty-actors")
        images[name] = []
        for suffix, im in zip(suffixes, views):
            path = output / f"maze-{name}{suffix}.png"
            im.save(path)
            images[name].append(path)
        full.resize((672, 864), Image.Resampling.NEAREST).save(output / f"maze-{name}-ntsc.png")
    compare_image(full_views["current"], full_views["simplified"]).save(output / "maze-comparison.png")
    # Show the real hardware patterns rather than just the 4x6 authoring tiles.
    unique = sorted(set(characters(bitmaps["simplified"])))
    sheet = Image.new("RGB", (16 * 60 + 32, ((len(unique) + 15) // 16) * 90 + 70), "#111820")
    draw = ImageDraw.Draw(sheet)
    draw.text((16, 13), "Simplified full-board 8 x 16 character patterns", font=font(20, True), fill="white")
    for n, pattern in enumerate(unique):
        tile = Image.new("RGB", (8, 16))
        for y, row in enumerate(pattern):
            for x in range(8):
                if row & (128 >> x): tile.putpixel((x, y), WHITE)
        x, y = 16 + (n % 16) * 60, 54 + (n // 16) * 90
        sheet.paste(tile.resize((48, 64), Image.Resampling.NEAREST), (x, y))
        draw.text((x, y + 65), str(n), font=font(13), fill="#88e4cc")
    sheet.save(output / "maze-character-patterns.png")
    report = {
        "status": "offline artwork study; no runtime changes or measured speed/flicker gain",
        "fixture_sha256": hashlib.sha256(fixture).hexdigest(),
        "generated_rom_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "art_sha256": hashlib.sha256(args.art.read_bytes()).hexdigest(),
        "native_visible_size": [WIDTH, HEIGHT], "hardware_cell": [8, 16],
        "native_bitmap_allocation_bytes": 3136, "hardware_cells": 196,
        "preview_scale": [6, 4], "standing_pellet_rgb": list(WHITE),
        "regular_pellets_unchanged": 240, "power_pellets_unchanged": 4,
        "logical_tile_codes_unchanged": True,
        "changed_wall_codes": sum(original[c] != proposed[c] for c in covered),
        "original_unique_wall_4x6_masks": len({tuple(original[c]) for c in covered}),
        "simplified_unique_wall_4x6_masks": len({tuple(proposed[c]) for c in covered}),
        "models": {name: analyze(bitmaps[name], empty[name], pellets, hud_cells) for name in bitmaps},
        "blue_maze_feasibility": blue_maze_study(fixture, source, proposed, bitmaps["simplified"], output),
        "limits": [
            "Full-board counts include the current fixed HUD and eight blank storage scanlines; they exclude actors.",
            "Pellet variants exhaust every independent present/absent combination in each hardware cell; masks that cross a cell contribute to both cells.",
            "The conservative bound reserves one writable glyph per pellet/HUD cell and shares only the remaining fixed patterns; it excludes actors, messages, intermissions and renderer bookkeeping.",
            "The all-variants count fixes the HUD to this fixture and is not a complete game character budget.",
            "No allocation changes are enabled. Potential released bytes require a new character-based renderer, screen maps, overlap handling and complete memory accounting.",
            "Actor previews use the current art and colour-cell ownership at the fixture positions; they are not emulator screenshots or evidence of less flicker.",
            "The blue wall-priority image deliberately shows the rejected pellet-colour tradeoff for comparison; the main mockup and playable build retain white standing pellets."
        ],
    }
    (output / "maze-character-analysis.json").write_text(json.dumps(report, indent=2) + "\n")
    write_html(output, images)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
