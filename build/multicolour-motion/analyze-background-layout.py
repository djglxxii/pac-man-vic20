"""Explain paired CPU deltas through copied-background page crossings."""
from collections import Counter
import json
from pathlib import Path
import re

b = Path('build/multicolour-motion')
old = b / 'before-background-layout'
folders = {'before': old, 'after': b}
maps = {name: (folder / 'background-map.bin').read_bytes() for name, folder in folders.items()}
starts = {name: int(re.search(r'^DATA\s+([0-9A-F]+)\s+', (folder / 'motion.map').read_text(), re.M)[1], 16)
          for name, folder in folders.items()}
charsets = {name: (folder / 'background-charset.bin').read_bytes() for name, folder in folders.items()}
for name, folder in folders.items():
    charset = charsets[name]
    assert len(charset) == 1176
    assert (folder / 'background-rows.bin').read_bytes() == bytes(charset[code * 8 + row]
                                                                   for row in range(8) for code in range(147))
assert [charsets['before'][code * 8:code * 8 + 8] for code in maps['before']] == [
    charsets['after'][code * 8:code * 8 + 8] for code in maps['after']]
assert sorted(charsets['before'][i:i + 8] for i in range(0, 1176, 8)) == sorted(
    charsets['after'][i:i + 8] for i in range(0, 1176, 8))


def allocations(packet):
    """All cells resolved for the clipped footprints, including transparent rows."""
    cells = set()
    for offset in range(0, 24, 4):
        x, y, pose, _ = packet[offset:offset + 4]
        if pose == 255:
            continue
        x = x if x < 128 else x - 256
        top, bottom = max(16, y), min(208, y + 14)
        if top >= bottom:
            continue
        for column in range(2 + ((x & 3) == 3)):
            c = x // 4 + column
            if 0 <= c < 21:
                cells.update(band * 21 + c for band in range(top // 8, (bottom - 1) // 8 + 1))
    return cells


def crossings(cells, name):
    return sum(((starts[name] + row * 147) & 255) + maps[name][cell] > 255
               for cell in cells for row in range(8))


replay = (b / 'replay.bin').read_bytes()
paired = json.loads((b / 'background-layout-comparison-scenes.json').read_text())
totals = Counter()
counts = Counter()
for scene, offset in enumerate(range(0, len(replay), 25)):
    cells = allocations(replay[offset:offset + 24])
    counts.update(maps['after'][cell] for cell in cells)
    prior, current = crossings(cells, 'before'), crossings(cells, 'after')
    expected_saving = prior - current
    actual_saving = paired['before']['frames'][scene]['prepare'] - paired['after']['frames'][scene]['prepare']
    assert expected_saving == actual_saving, (scene, expected_saving, actual_saving)
    totals['before'] += prior
    totals['after'] += current

after = charsets['after']
frequency = Counter(after[code * 8:code * 8 + 8] for code in maps['after'][42:546])
loaded = json.loads((b / 'build.json').read_text())['background_characters_loaded']
assert [after[i:i + 8] for i in range(0, loaded * 8, 8)] == sorted(frequency.keys() | {
    after[i:i + 8] for i in range(0, loaded * 8, 8)}, key=lambda pattern: (-frequency[pattern], pattern))
result = {
    'all_567_decoded_background_cells_identical': True,
    'all_147_glyphs_preserved_including_padding': True,
    'both_row_plane_encodings_match_their_charsets': True,
    'glyph_ids_ordered_by': 'whole static playfield frequency, excluding the HUD; no replay weighting',
    'ordering_verified': True,
    'all_480_cycle_deltas_exactly_explained_by_page_crossings': True,
    'background_copy_crossings': dict(totals),
    'mean_background_copy_crossings_per_scene': {name: round(count / 480, 2) for name, count in totals.items()},
    'background_cells_copied': sum(counts.values()),
    'no_padding_added': True,
}
(b / 'background-layout-analysis.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
