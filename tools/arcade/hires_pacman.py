"""Hand-authored Pac-Man masks for the existing 8x12 hires compositor."""
import json
from pathlib import Path

ARTWORK = Path(__file__).resolve().parents[2] / "docs/artwork/hires-pacman.json"


def apply_pacman(sprites, path=ARTWORK):
    """Replace five walking masks and eleven death masks without adding frames."""
    spec = json.loads(Path(path).read_text())
    if (spec["width"], spec["height"]) != (8, 12):
        raise ValueError("Pac-Man masks must fit the existing 8x12 footprint")
    frames = {int(code, 16): bytes.fromhex(frame["rows"])
              for code, frame in spec["frames"].items()}
    if set(frames) != {*range(0x2c, 0x31), *range(0x34, 0x3f)}:
        raise ValueError("Pac-Man masks must use the existing walk/death codes")
    if any(len(rows) != 12 for rows in frames.values()):
        raise ValueError("Each Pac-Man mask must contain exactly twelve rows")
    closed = frames[0x30]
    if closed != closed[::-1] or any(row != int(f"{row:08b}"[::-1], 2)
                                   for row in closed):
        raise ValueError("The shared closed-mouth mask must be symmetric")
    for direction in ("right", "left", "down", "up"):
        if spec["views"][f"{direction}-closed"]["sprite"] != "30":
            raise ValueError("All closed-mouth views must share sprite $30")
    for code, rows in frames.items():
        sprites[code * 12:(code + 1) * 12] = rows
