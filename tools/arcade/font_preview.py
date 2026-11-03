#!/usr/bin/env python3
"""Show the generated lettering at integer NTSC pixel proportions."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from PIL import Image, ImageColor, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]


def table(source, name):
    body = re.search(r"\b" + name + r"\[.*?= \{(.*?)\};", source, re.S)[1]
    return bytes(int(value, 16) for value in re.findall(r"0x[0-9a-f]+", body))


def specimen(source):
    tiles, sprites = table(source, "arcade_tiles"), table(source, "arcade_sprites")
    right = table(source, "arcade_score_right") if "arcade_score_right[" in source else None
    data = table(source, "rom_32f9")
    image = Image.new("RGB", (112, 216))

    def tile(code, x, y, color="white"):
        for dy in range(6):
            row = (tiles[code * 3 + dy // 2] >> (0 if dy & 1 else 4)) & 15
            for dx in range(4):
                if row & (8 >> dx):
                    image.putpixel((x + dx, y + dy), ImageColor.getrgb(color))

    def text(value, x, y, color="white"):
        codes = {" ": 0x40, "!": 0x5b, "-": 0x3b, ":": 0x3a}
        for char in value:
            tile(codes.get(char, ord(char)), x, y, color)
            x += 4

    text("HIGH SCORE 123456", 4, 4)
    text("0123456789", 4, 18)
    text("35 89 56 3689", 4, 30)
    text("ABCDEFGHIJKLM", 4, 44)
    text("NOPQRSTUVWXYZ", 4, 54)
    text("READY! GAME OVER", 4, 68, "#dcd71b")
    text("PUSH START BUTTON", 4, 80, "#4df0ff")
    for index, code in enumerate(range(40, 44)):
        x, y = (6 if right is not None else 10) + index * 26, 100
        for dy, row in enumerate(sprites[code * 12:code * 12 + 12]):
            if right is not None:
                row = row << 8 | right[index * 12 + dy]
            width = 16 if right is not None else 8
            for dx in range(width):
                if row & (1 << (width - 1 - dx)):
                    image.putpixel((x + dx, y + dy), (77, 240, 255))
    for index, message in enumerate(range(0x1b, 0x23)):
        pointer = 0x36a5 + message * 2 - 0x32f9
        address = int.from_bytes(data[pointer:pointer + 2], "little") - 0x32f9
        end = data.index(0x2f, address + 2)
        codes = data[address + 2:end]
        x, y = (index % 2) * 56 + (56 - len(codes) * 4) // 2, 132 + (index // 2) * 18
        for code in codes:
            tile(code, x, y, "#b43fff")
            x += 4
    text("10000 PTS", 4, 208)
    return image


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/" + name, size)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "build/arcade/rom.c")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/artwork/fonts")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        subprocess.run([sys.executable, str(ROOT / "tools/arcade/mkrom.py"),
                        "--roms", str(ROOT / "pacman.zip"), "--output", temporary,
                        "--arcade-font"], check=True)
        original = specimen((Path(temporary) / "rom.c").read_text())
    proposed = specimen(args.source.read_text())
    canvas = Image.new("RGB", (1464, 1072), "#111820")
    draw = ImageDraw.Draw(canvas)
    draw.text((36, 24), "VIC-MAN / LETTERS AND SCORES", font=font(28, True), fill="white")
    draw.text((36, 66), "Generated game assets, shown with 3:2 NTSC pixels and no smoothing.",
              font=font(18), fill="#b7c5d3")
    for x, label, image in ((36, "SCALED ARCADE", original), (756, "VIC FONT DRAFT", proposed)):
        draw.text((x, 110), label, font=font(22, True), fill="#88e4cc")
        canvas.paste(image.resize((672, 864), Image.Resampling.NEAREST), (x, 152))
    draw.text((36, 1036), "Cyan: ghost scores 200 / 400 / 800 / 1600. Purple: all eight fruit scores.",
              font=font(18), fill="#b7c5d3")
    canvas.save(args.output / "font-comparison.png")
    proposed.resize((672, 864), Image.Resampling.NEAREST).save(args.output / "font-specimen.png")


if __name__ == "__main__":
    main()
