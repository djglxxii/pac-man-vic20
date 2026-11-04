"""Hand-authored intermission ghost masks for the existing 8x12 hires compositor."""
import json
from pathlib import Path

ARTWORK = Path(__file__).resolve().parents[2] / "docs/artwork/hires-intermission.json"
CODES = {0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x32, 0x33}


def apply_intermission(sprites, path=ARTWORK):
    """Replace the nail, tear and robe masks without adding frames."""
    spec = json.loads(Path(path).read_text())
    if (spec["width"], spec["height"]) != (8, 12):
        raise ValueError("Intermission masks must fit the existing 8x12 footprint")
    frames = {int(code, 16): bytes.fromhex(frame["rows"])
              for code, frame in spec["frames"].items()}
    if set(frames) != CODES:
        raise ValueError("Intermission masks must use the existing cutscene codes")
    if any(len(rows) != 12 for rows in frames.values()):
        raise ValueError("Each intermission mask must contain exactly twelve rows")
    for code, rows in frames.items():
        sprites[code * 12:(code + 1) * 12] = rows
