"""Hand-drawn lettering for the existing hires tile format."""
import json
from pathlib import Path

ARTWORK = Path(__file__).resolve().parents[2] / "docs/artwork/hires-font.json"
FRUIT_SCORES = (100, 300, 500, 700, 1000, 2000, 3000, 5000)
GHOST_SCORES = (200, 400, 800, 1600)


def load_glyphs(path=ARTWORK):
    glyphs = json.loads(Path(path).read_text())["glyphs"]
    for char, rows in glyphs.items():
        width = 4 if char == "©" else 3
        if len(rows) != 5 or any(len(row) != width or set(row) - {".", "#"}
                                 for row in rows):
            raise ValueError(f"Invalid {width}x5 glyph: {char!r}")
    return glyphs


def tile_codes():
    codes = {i: char for i, char in enumerate("0123456789ABCDEF")}
    codes.update({ord(char): char for char in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"})
    codes.update({0x25: ".", 0x26: '"', 0x3a: ":", 0x3b: "-", 0x40: " ",
                  0x5b: "!", 0x5c: "©", 0x5d: "P", 0x5e: "T", 0x5f: "S"})
    return codes


def apply_tiles(tiles, glyphs):
    """Replace artwork in place; retain the three packed bytes per tile."""
    for code, char in tile_codes().items():
        rows = [sum((pixel == "#") << (3 - x) for x, pixel in enumerate(row))
                for row in glyphs[char]] + [0]
        tiles[code * 3:code * 3 + 3] = bytes(
            rows[y] << 4 | rows[y + 1] for y in range(0, 6, 2))


def apply_ghost_scores(sprites, glyphs):
    """Split horizontal 16x12 reward masks into two existing actor slots."""
    right = bytearray()
    for code, score in enumerate(GHOST_SCORES, 40):
        rows = [0] * 12
        text = str(score)
        left = (16 - (len(text) * 4 - 1)) // 2
        for column, char in enumerate(text):
            for dy, line in enumerate(glyphs[char]):
                for dx, pixel in enumerate(line):
                    if pixel == "#":
                        rows[3 + dy] |= 0x8000 >> (left + column * 4 + dx)
        sprites[code * 12:code * 12 + 12] = bytes(row >> 8 for row in rows)
        right.extend(row & 255 for row in rows)
    return right


def fruit_messages(rom):
    """Use ordinary digit/space tiles in the native display messages.

    Reuse the original message-data range, including its pointer table. The
    input ROM and the independently executed Z80 reference stay untouched.
    These are presentation bytes only: scores, tasks and delays are unchanged.
    """
    result = bytearray(rom)
    address, limit = 0x38bc, 0x390a
    for message, score in enumerate(FRUIT_SCORES, 0x1b):
        pointer = 0x36a5 + message * 2
        result[pointer:pointer + 2] = address.to_bytes(2, "little")
        # Keep the 100-point erase message four tiles wide: the arcade uses
        # it as one of its two popup removal paths. The other three-digit
        # messages need only three tiles, which keeps all eight records in
        # the original allocation, including their erase-palette bytes.
        text = str(score).rjust(4) if score == 100 else str(score)
        codes = bytes(0x40 if char == " " else int(char) for char in text)
        # Horizontal arcade message at x=12..15, y=20 (native pixels 48..63,
        # 120..125). Preserve palette 3 and the original erase terminator.
        location = 0x232 if len(text) == 4 else 0x212
        data = location.to_bytes(2, "little") + codes + b"\x2f\x83\x2f\x90"
        result[address:address + len(data)] = data
        address += len(data)
    if address > limit:
        raise ValueError("Fruit lettering exceeds its existing ROM data range")
    return result
