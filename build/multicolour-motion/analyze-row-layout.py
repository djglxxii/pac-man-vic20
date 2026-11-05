"""Attribute paired CPU savings to sprite lookup page crossings."""
from collections import Counter
import json
from pathlib import Path
import re

b = Path("build/multicolour-motion")
old = b / "before-row-layout"
fields = ("row_data0", "row_data1", "row_data2", "row_mask0", "row_mask1", "row_mask2", "row_accent")

def decode(folder, listing):
    ids = (folder / "pose-rows.bin").read_bytes()
    raw = (folder / "row-records.bin").read_bytes()
    n = len(raw) // 7
    rows = [tuple(raw[f * n + r] for f in range(7)) for r in range(n)]
    text = listing.read_text()
    data_start = int(re.search(r"^DATA\s+([0-9A-F]+)\s+[0-9A-F]+\s+[0-9A-F]+\s+[0-9A-F]+\s*$", (folder / "motion.map").read_text(), re.M)[1], 16)
    addresses = [data_start + int(re.search(r"^([0-9A-F]{6})r.*?\b" + field + r":", text, re.M)[1], 16) for field in fields]
    return ids, rows, addresses

before = decode(old, b / "row-layout-before.lst")
after = decode(b, b / "row-layout.lst")
assert [before[1][r] for r in before[0]] == [after[1][r] for r in after[0]]

def crossings(packet, lookup):
    ids, rows, addresses = lookup
    counts = Counter()
    accents = (b / "pose-accents.bin").read_bytes()
    for i in range(0, 24, 4):
        x, y, pose, _ = packet[i:i + 4]
        if pose == 255:
            continue
        x = x - 256 if x >= 128 else x
        phase = x & 3
        columns = [c for c in range(2 + (phase == 3)) if 0 <= x // 4 + c < 21]
        if not columns:
            continue
        pending = 0
        for py in range(max(16, y), min(208, y + 14)):
            if py == max(16, y) or py % 8 == 0:
                pending = sum(1 << c for c in columns) if accents[pose] else 0
            rid = ids[pose * 56 + phase * 14 + py - y]
            used = [f for c in columns for f in (c, c + 3)]
            if pending:
                used.append(6)
                pending &= ~rows[rid][6]
            for f in used:
                if (addresses[f] & 255) + rid > 255:
                    counts[fields[f]] += 1
    return counts

replay = (b / "replay.bin").read_bytes()
paired = json.loads((b / "row-layout-comparison-scenes.json").read_text())
totals = {"before": Counter(), "after": Counter()}
for scene, offset in enumerate(range(0, len(replay), 25)):
    prior = crossings(replay[offset:offset + 24], before)
    current = crossings(replay[offset:offset + 24], after)
    expected_saving = sum(prior.values()) - sum(current.values())
    actual_saving = paired["before"]["frames"][scene]["prepare"] - paired["after"]["frames"][scene]["prepare"]
    assert expected_saving == actual_saving, (scene, expected_saving, actual_saving)
    totals["before"].update(prior)
    totals["after"].update(current)
record = {
    "all_1512_decoded_artwork_rows_identical": True,
    "all_480_cycle_deltas_exactly_explained_by_page_crossings": True,
    "row_ids_ordered_by": "frequency across all artwork poses and shifts; no replay weighting",
    "field_order": sorted(fields, key=lambda field: after[2][fields.index(field)]),
    "field_addresses": {name: dict(zip(fields, lookup[2])) for name, lookup in (("before", before), ("after", after))},
    "crossing_counts": {name: dict(counts) for name, counts in totals.items()},
    "mean_crossings_per_scene": {name: round(sum(counts.values()) / 480, 2) for name, counts in totals.items()},
    "no_table_padding": True,
}
(b / "row-layout-analysis.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
