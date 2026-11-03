#!/usr/bin/env python3
"""
Convert ASCII-art (or PNG) character graphics into VIC-20 character data.

ASCII-art input: one glyph per block of 8 (or 16 with --tall) lines, blocks separated
by blank lines or lines starting with ';' (an optional name after ';' becomes a label).
  Hires (8 px wide):       '.' or ' ' = 0 (background), anything else = 1 (foreground)
  Multicolour (--multi, 4 px wide, each char = one double-width pixel):
      '.' ' ' '0' = 00 background ($900F high nibble)
      'b' '1'     = 01 border colour ($900F bits 0-2)
      'f' '2' '#' = 10 character colour (colour RAM bits 0-2)
      'a' '3'     = 11 auxiliary colour ($900E high nibble)
  (Mapping per the Programmer's Reference Guide and VICE. VIC-I.txt swaps 01/10; it is wrong.)
  Multicolour cells need colour RAM value 8-15 (bit 3 set) to be shown in multicolour.

Wide glyphs: lines longer than 8 (hires) or 4 (multi) characters are split into several
chars left-to-right, then top-to-bottom (e.g. a 16x16 ASCII sprite -> 4 chars).

PNG input (--png, needs Pillow): image is cut into 8x8 (8x16 with --tall) cells,
row by row; a pixel is "on" if its luminance is below 50% (use --invert to flip).
Multicolour PNG: pixels are read in pairs; up to 4 distinct colours in order of
first appearance map to 00,01,10,11 unless --palette is given.

Output: --format ca65 (default) | acme | c | bin   (bin writes raw bytes to -o)

Examples:
  charconv.py sprites.txt                    # hires ASCII art -> ca65 .byte lines
  charconv.py --multi tiles.txt --format acme
  charconv.py --png font.png --format bin -o font.bin
  charconv.py --preview sprites.txt          # print what the bytes look like
"""
import argparse
import re
import sys

HI_OFF = set(". ")
MC_MAP = {".": 0, " ": 0, "0": 0, "b": 1, "1": 1, "f": 2, "2": 2, "#": 2, "a": 3, "3": 3}


def parse_ascii(text, multi, tall):
    height = 16 if tall else 8
    width = 4 if multi else 8
    glyphs = []  # (name, [rows of strings])
    cur, name = [], None

    def flush():
        nonlocal cur, name
        if cur:
            glyphs.append((name, cur))
        cur, name = [], None

    for line in text.splitlines():
        if line.strip() == "" or line.lstrip().startswith(";"):
            flush()
            if line.lstrip().startswith(";"):
                nm = line.lstrip()[1:].strip()
                name = re.sub(r"\W", "_", nm) if nm else None
            continue
        cur.append(line.rstrip("\n"))
    flush()

    out = []
    for name, rows in glyphs:
        if len(rows) % height:
            sys.exit(f"glyph {name or len(out)}: {len(rows)} rows, not a multiple of {height}")
        w = max(len(r) for r in rows)
        w = (w + width - 1) // width * width
        rows = [r.ljust(w, ".") for r in rows]
        idx = 0
        for by in range(0, len(rows), height):
            for bx in range(0, w, width):
                data = []
                for r in rows[by:by + height]:
                    cell = r[bx:bx + width]
                    data.append(encode(cell, multi))
                nm = name if (name and len(rows) == height and w == width) else (f"{name}_{idx}" if name else None)
                out.append((nm, data))
                idx += 1
    return out


def encode(cell, multi):
    b = 0
    if multi:
        for ch in cell:
            v = MC_MAP.get(ch.lower() if ch.isalpha() else ch)
            if v is None:
                sys.exit(f"unknown multicolour pixel {ch!r} (use . b f a or 0 1 2 3)")
            b = (b << 2) | v
    else:
        for ch in cell:
            b = (b << 1) | (0 if ch in HI_OFF else 1)
    return b


def parse_png(path, multi, tall, invert, palette):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("PNG input needs Pillow: pip install pillow")
    im = Image.open(path).convert("RGB")
    W, H = im.size
    height = 16 if tall else 8
    px = im.load()
    out = []
    pal = palette[:] if palette else []
    for cy in range(0, H - H % height, height):
        for cx in range(0, W - W % 8, 8):
            data = []
            for y in range(cy, cy + height):
                b = 0
                if multi:
                    for x in range(cx, cx + 8, 2):
                        c = px[x, y]
                        if c not in pal:
                            if len(pal) >= 4:
                                sys.exit(f"more than 4 colours in multicolour cell at {cx},{cy}")
                            pal.append(c)
                        b = (b << 2) | pal.index(c)
                else:
                    for x in range(cx, cx + 8):
                        r, g, bl = px[x, y]
                        on = (0.299 * r + 0.587 * g + 0.114 * bl) < 128
                        b = (b << 1) | (on ^ invert)
                data.append(b)
            out.append((None, data))
    return out


def preview(glyphs, multi):
    for i, (name, data) in enumerate(glyphs):
        print(f"; {name or 'char'} #{i}")
        for b in data:
            if multi:
                s = "".join(".bfa"[(b >> s) & 3] * 2 for s in (6, 4, 2, 0))
            else:
                s = "".join("#" if b & (0x80 >> k) else "." for k in range(8))
            print("  " + s)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("--multi", action="store_true")
    ap.add_argument("--tall", action="store_true", help="8x16 characters ($9003 bit 0)")
    ap.add_argument("--png", action="store_true")
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--palette", help="multicolour PNG: 4 hex RGB colours for 00,01,10,11 e.g. 000000,ffffff,ff0000,00ff00")
    ap.add_argument("--format", choices=["ca65", "acme", "c", "bin"], default="ca65")
    ap.add_argument("--label", default="chars")
    ap.add_argument("--first-code", type=int, default=0, help="screen code of the first glyph (for comments)")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("-o", "--output")
    a = ap.parse_args()

    if a.png:
        pal = None
        if a.palette:
            pal = [tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in a.palette.split(",")]
        glyphs = parse_png(a.input, a.multi, a.tall, a.invert, pal)
    else:
        with open(a.input) as f:
            glyphs = parse_ascii(f.read(), a.multi, a.tall)

    if a.preview:
        preview(glyphs, a.multi)
        return 0

    if a.format == "bin":
        if not a.output:
            sys.exit("--format bin needs -o FILE")
        with open(a.output, "wb") as f:
            for _, d in glyphs:
                f.write(bytes(d))
        print(f"wrote {sum(len(d) for _, d in glyphs)} bytes ({len(glyphs)} chars) to {a.output}")
        return 0

    lines = []
    size = 16 if a.tall else 8
    if a.format == "c":
        lines.append(f"/* {len(glyphs)} chars, {size} bytes each */")
        lines.append(f"const unsigned char {a.label}[{len(glyphs) * size}] = {{")
        for i, (name, d) in enumerate(glyphs):
            lines.append("    " + ", ".join(f"0x{b:02X}" for b in d) + f",  /* {a.first_code + i}: {name or ''} */")
        lines.append("};")
    else:
        directive = ".byte" if a.format == "ca65" else "!byte"
        lines.append(f"; {len(glyphs)} chars, {size} bytes each")
        lines.append(f"{a.label}:")
        for i, (name, d) in enumerate(glyphs):
            lines.append(f"        {directive} " + ", ".join(f"${b:02X}" for b in d) + f"    ; {a.first_code + i}: {name or ''}")
    text = "\n".join(lines) + "\n"
    if a.output:
        with open(a.output, "w") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
