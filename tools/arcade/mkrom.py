#!/usr/bin/env python3
"""Extract the local ROM set; retain virtual ROM addresses in the native core."""
import argparse, hashlib, json, zipfile
from pathlib import Path
from PIL import Image, ImageDraw
from hires_font import apply_ghost_scores, apply_tiles, fruit_messages, load_glyphs
from hires_pacman import apply_pacman
from hires_intermission import apply_intermission

BLOCKS = (
    (0x68, 0x8D),
    (0x219, 0x221),
    (0x796, 0x814),
    (0x843, 0x879),
    (0xEFD, 0xF3C),
    (0x2728, 0x2730),
    (0x3154, 0x3174),
    (0x32F9, 0x3E5C),
)


def array(name, data, section=None):
    attr = f' __attribute__((section("{section}")))' if section else ""
    return (
        f"const unsigned char {name}[{len(data)}]{attr} = {{\n"
        + "".join(
            " " + ",".join(f"0x{v:02x}" for v in data[i : i + 24]) + ",\n"
            for i in range(0, len(data), 24)
        )
        + "};\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roms", default="pacman.zip")
    ap.add_argument("--output", default="build/arcade")
    ap.add_argument("--arcade-font", action="store_true",
                    help="Keep scaled arcade lettering for artwork comparisons")
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.roms) as z:
        names = z.namelist()
        data = {n: z.read(n) for n in names}
        rom = b"".join(data[f"pacman.6{x}"] for x in "efhj")
    (out / "program-rom.bin").write_bytes(rom)
    (out / "rom-manifest.json").write_text(
        json.dumps(
            {n: hashlib.sha256(v).hexdigest() for n, v in data.items()}, indent=2
        )
        + "\n"
    )
    hdr = ["#ifndef ARCADE_ROM_H\n#define ARCADE_ROM_H\n#include <stdint.h>\n"]
    src = ['#include "rom.h"\n']
    native_rom = rom if args.arcade_font else fruit_messages(rom)
    for lo, hi in BLOCKS:
        name = f"rom_{lo:04x}"
        hdr.append(f"extern const uint8_t {name}[{hi-lo}];\n")
        src.append(array(name, native_rom[lo:hi], ".arcade_data"))
    hdr.append("static inline const uint8_t *arcade_rom_ptr(uint16_t a) {\n")
    for lo, hi in BLOCKS:
        hdr.append(
            f' if (a>=0x{lo:04x} && a<0x{hi:04x}) return {f"rom_{lo:04x}"}+(a-0x{lo:04x});\n'
        )
    hdr.append(" return rom_32f9;\n}\nextern const uint8_t rom_random[384];\n")
    # Four six-second energizers, four ghosts, at most two pixel steps/tick
    # and one random decision/eight pixels: <=1440+16 calls before reseeding.
    random = []
    address = 0
    for i in range(1536):
        address = (address * 5 + 1) & 8191
        random.append(rom[address] & 3)
    src.append(
        array(
            "rom_random",
            bytes(
                sum(random[i + j] << (j * 2) for j in range(4))
                for i in range(0, 1536, 4)
            ),
            ".arcade_data",
        )
    )
    # Squaring tables replace the original eight-step multiply without changing
    # its 16-bit result or steering tie order.
    hdr.append("extern const uint16_t arcade_squares[128];\n")
    src.append(
        'const uint16_t arcade_squares[128] __attribute__((section(".arcade_data"), aligned(256))) = {'
        + ",".join(str(i * i) for i in range(128))
        + "};\n"
    )

    def decode(blob, code, size):
        xo = (
            [64, 65, 66, 67, 0, 1, 2, 3]
            if size == 8
            else [64, 65, 66, 67, 128, 129, 130, 131, 192, 193, 194, 195, 0, 1, 2, 3]
        )
        yo = list(range(8)) if size == 8 else list(range(8)) + list(range(32, 40))
        im = Image.new("L", (size, size))
        for y in range(size):
            for x in range(size):
                bit = code * size * size * 2 + xo[x] + yo[y] * 8

                def get(b):
                    return (blob[b >> 3] >> (7 - (b & 7))) & 1

                im.putpixel((x, y), get(bit) * 2 + get(bit + 4))
        return im.transpose(Image.Transpose.ROTATE_270)

    tiles = bytearray()
    sprites = bytearray()
    eyes = bytearray()
    tile_classes = []
    sprite_classes = []
    for code in range(256):
        raw_tile = decode(data["pacman.5e"], code, 8)
        allowed = (
            (1, 3) if code >= 0xC0 else (2, 3) if 0xB0 <= code < 0xB6 else (1, 2, 3)
        )
        tile_classes.append(
            3
            if 0xB0 <= code < 0xB6
            else (
                max(allowed, key=lambda p: list(raw_tile.getdata()).count(p))
                if any(raw_tile.getdata())
                else 0
            )
        )
        im = raw_tile.point(
            lambda p: (
                255
                if (
                    p in (1, 3)
                    if code >= 0xC0
                    else p in (2, 3) if 0xB0 <= code < 0xB6 else p != 0
                )
                else 0
            )
        ).resize((4, 6), Image.Resampling.BOX)
        rows = [
            sum((im.getpixel((x, y)) >= 64) << (3 - x) for x in range(4))
            for y in range(6)
        ]
        tiles.extend(rows[y] << 4 | rows[y + 1] for y in range(0, 6, 2))
    glyphs = load_glyphs()
    if not args.arcade_font:
        apply_tiles(tiles, glyphs)
    sheet = Image.new("RGB", (16 * 32, 4 * 48), "black")
    draw = ImageDraw.Draw(sheet)
    colors = [(0, 0, 0), (255, 255, 255), (0, 0, 255), (255, 0, 0)]
    for code in range(64):
        raw = decode(data["pacman.5f"], code, 16)
        sprite_classes.append(
            max((1, 2, 3), key=lambda p: list(raw.getdata()).count(p))
            if any(raw.getdata())
            else 0
        )
        rgb = Image.new("RGB", (16, 16))
        rgb.putdata([colors[p] for p in raw.getdata()])
        sheet.paste(rgb.resize((32, 32)), ((code % 16) * 32, (code // 16) * 48))
        draw.text(((code % 16) * 32, (code // 16) * 48 + 32), str(code), fill="white")

        def mask(test):
            im = raw.point(lambda p: 255 if test(p) else 0).resize(
                (8, 12), Image.Resampling.BOX
            )
            return bytes(
                sum((im.getpixel((x, y)) >= 96) << (7 - x) for x in range(8))
                for y in range(12)
            )

        sprites.extend(
            mask(
                lambda p: (
                    p == 2
                    if 28 <= code < 30
                    else p in (2, 3) if 32 <= code < 40 else p != 0
                )
            )
        )
        if 32 <= code < 40:
            eyes.extend(mask(lambda p: p == 1))
    sheet.save(out / "sprite-reference.png")
    # Authored at the displayed size; the four closed views already share $30.
    # Preserve the original sprite codes, dominant pixel classes and palettes.
    apply_pacman(sprites)
    # Clear bits are the eye holes. The snag, tear and robe keep their silhouettes.
    apply_intermission(sprites)
    if not args.arcade_font:
        score_right = apply_ghost_scores(sprites, glyphs)
        # The main graphics bank is full; these four extra half-masks fit
        # in resident RAM without changing the expansion configuration.
        hdr.append("extern const uint8_t arcade_score_right[48];\n")
        src.append(array("arcade_score_right", score_right))
    # Right/down/left ghost frames share two horizontally symmetric masks.
    # The transparent first/last rows need no mask data. Six normal frames
    # therefore need just 2 * 8 * 20 = 320 pre-shifted bytes.
    ghost_shifted = bytearray()
    for phase in range(2):
        body = sprites[(32 + phase) * 12 : (33 + phase) * 12]
        assert all(
            sprites[(code + phase) * 12 : (code + phase + 1) * 12] == body
            for code in (32, 34, 36)
        )
        assert all(v == int(f"{v:08b}"[::-1], 2) for v in body)
        assert body[0] == body[-1] == 0
        for shift in range(8):
            ghost_shifted.extend(v >> shift for v in body[1:11])
            ghost_shifted.extend((v << (8 - shift)) & 255 for v in body[1:11])
    # The scaled pen-2 body fills the eyes and mouth. Cut symmetric holes
    # through both frames; each frame keeps its own skirt.
    solid = bytes((0x00, 0x3C, 0x7E, 0x7E, 0x7E, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF))
    face = bytes((0x00, 0x3C, 0x7E, 0x5A, 0x5A, 0xFF, 0xDB, 0xA5, 0xFF, 0xFF))
    for code, skirt in ((28, 0xBD), (29, 0x5A)):
        start = code * 12
        body = sprites[start : start + 12]
        assert body[:10] == solid and body[10] == skirt and body[11] == 0
        sprites[start : start + 10] = face
    frightened_shifted = bytearray()
    for code in (28, 29):
        body = sprites[code * 12 : (code + 1) * 12]
        assert body[0] == body[-1] == 0
        assert all(v == int(f"{v:08b}"[::-1], 2) for v in body)
        for shift in range(8):
            frightened_shifted.extend(v >> shift for v in body[1:11])
            frightened_shifted.extend((v << (8 - shift)) & 255 for v in body[1:11])
    for name, values in (
        ("arcade_tiles", tiles),
        ("arcade_sprites", sprites),
        ("arcade_eyes", eyes),
        ("arcade_ghost_shifted", ghost_shifted),
    ):
        hdr.append(f"extern const uint8_t {name}[{len(values)}];\n")
        src.append(array(name, values, ".graphics"))
    # Keep the second cache in BLK1-3; BLK5 is almost full.
    hdr.append(
        f"extern const uint8_t arcade_fright_shifted[{len(frightened_shifted)}];\n"
    )
    src.append(array("arcade_fright_shifted", frightened_shifted))
    # Keep the original palette selection for each sprite's dominant pixel class.
    # Packed two-bit class tables also let the HUD fruit tiles choose their own
    # body color instead of using one generic color for every palette.
    for name, classes in (
        ("arcade_tile_class", tile_classes),
        ("arcade_sprite_class", sprite_classes),
    ):
        values = bytes(
            sum(classes[i + j] << (j * 2) for j in range(4))
            for i in range(0, len(classes), 4)
        )
        hdr.append(f"extern const uint8_t {name}[{len(values)}];\n")
        src.append(array(name, values, ".graphics"))
    prom = data["82s123.7f"]
    lookup = data["82s126.4a"]
    vic = [
        (0, 0, 0),
        (255, 255, 255),
        (182, 31, 33),
        (77, 240, 255),
        (180, 63, 255),
        (68, 226, 55),
        (26, 52, 255),
        (220, 215, 27),
    ]

    def rgb(v):
        return (
            sum(w for b, w in enumerate((33, 71, 151)) if v & (1 << b)),
            sum(w for b, w in enumerate((33, 71, 151)) if v & (1 << (b + 3))),
            sum(w for b, w in enumerate((71, 151)) if v & (1 << (b + 6))),
        )

    palette = []
    for c in range(32):
        for p in range(4):
            color = rgb(prom[lookup[c * 4 + p] & 15])
            palette.append(
                min(
                    range(8),
                    key=lambda i: sum((color[k] - vic[i][k]) ** 2 for k in range(3)),
                )
            )
    # Preserve the identity of all four ghosts within the VIC's eight foregrounds.
    palette[1 * 4 + 3] = 2
    palette[3 * 4 + 3] = 4
    palette[5 * 4 + 3] = 3
    palette[7 * 4 + 3] = 7
    hdr.append("extern const uint8_t arcade_colors[128];\n")
    src.append(array("arcade_colors", palette, ".graphics"))
    # The generated declarations follow the virtual ROM accessor.
    hdr.append("#endif\n")
    (out / "rom.h").write_text("".join(hdr))
    (out / "rom.c").write_text("".join(src))


if __name__ == "__main__":
    main()
