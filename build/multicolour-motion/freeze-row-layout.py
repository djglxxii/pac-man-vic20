from pathlib import Path
import hashlib
import json
import re

b = Path("build/multicolour-motion")
old = b / "before-row-layout"
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def segments(folder):
    return {m[0]: {"start": int(m[1], 16), "end_inclusive": int(m[2], 16), "bytes": int(m[3], 16)}
            for m in re.findall(r"^(ZEROPAGE|STATE|CODE|DATA|BSS)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+[0-9A-F]+\s*$", (folder / "motion.map").read_text(), re.M)}
prev, curr = segments(old), segments(b)
assert len(prev) == 5 and prev == curr
assert (b / "motion.s").read_bytes() == Path("prototypes/multicolour-motion.S").read_bytes()
main = sha(Path("build/pacman.prg"))
assert main == read(Path("docs/baselines/multicolour-cell-allocation.json"))["main_game_sha256"]
assert len((b / "motion.prg").read_bytes()) == len((old / "motion.prg").read_bytes()) == 23077
asset_names = ("replay.bin", "source-poses.json", "poses.json", "background-charset.bin",
               "background-rows.bin", "background-map.bin", "background-colors.bin", "pose-accents.bin")
for name in asset_names:
    assert (old / name).read_bytes() == (b / name).read_bytes(), name
listing = (b / "row-layout.lst").read_text()
names = ("restore_page", "restore_page_ready", "publish_page", "publish_page_ready", "resolve_hi")
labels = {name: curr["CODE"]["start"] + int(re.search(r"^([0-9A-F]{6})r.*?\b" + name + r":", listing, re.M)[1], 16) for name in names}
for name in ("restore", "publish"):
    assert (labels[name + "_page"] + 4) >> 8 == labels[name + "_page_ready"] >> 8
assert labels["resolve_hi"] >> 8 == (labels["resolve_hi"] + 7) >> 8
analysis = read(b / "row-layout-analysis.json")
for field in ("row_data0", "row_data1", "row_mask1"):
    address = analysis["field_addresses"]["after"][field]
    assert address >> 8 == (address + 146) >> 8
record = {
    "date": "2026-11-03", "status": "retained-page-friendly-sprite-lookups",
    "changes": [
        "Order sprite-row IDs by frequency across all artwork poses and shifts, independently of recorded game positions.",
        "Remap pose IDs to preserve every decoded sprite row.",
        "Reorder existing field planes without padding; keep left/middle data and the middle mask entirely within pages.",
        "Add linker assertions for the three non-crossing field placements; preserve existing code-page assertions."
    ],
    "main_game_unchanged": True, "main_game_sha256": main,
    "before": {"prototype_sha256": sha(old / "motion.prg"), "native_validation": read(old / "validation.json"), "segments": prev},
    "after": {"build": read(b / "build.json"), "native_validation": read(b / "validation.json"), "segments": curr,
              "vice": read(b / "vice-validation.json"), "video": read(b / "row-layout-video.json")},
    "same_corpus_comparison": read(b / "row-layout-comparison.json"),
    "lookup_analysis": analysis,
    "unchanged_assets": {name: sha(b / name) for name in asset_names},
    "code_page_assertions": {"addresses": labels, "both_cached_branches_same_page": True, "resolution_high_lookup_same_page": True},
    "memory": {"code_byte_delta": 0, "state_byte_delta": 0, "zero_page_byte_delta": 0, "data_byte_delta": 0,
               "prg_bytes": 23077, "prg_length_unchanged": True, "all_segment_addresses_unchanged": True,
               "no_table_padding": True, "new_ram_configuration_required": False},
    "source_hashes": {str(p): sha(p) for p in map(Path, ["prototypes/multicolour-motion.S", "tools/arcade/build_multicolour_motion.py",
                      "tools/arcade/check_multicolour_motion.py", "tools/arcade/record_multicolour_motion.py", "docs/artwork/multicolour/actors-and-font.json"])},
    "diagnostic_artifact": {"path": str(b / "analyze-row-layout.py"), "sha256": sha(b / "analyze-row-layout.py")},
    "limits": [
        "Renderer-only replay: game logic, input, audio, live pellets/HUD and the background cache are not integrated.",
        "Original replay deadlines still yield 32.61 updates/s; CPU savings are not integrated game FPS.",
        "Other artwork or positions can have different page-crossing savings.",
        "No final full-game memory placement or physical hardware test.",
        "Completed pictures are identical; no new perceptual flicker result is claimed."
    ]
}
assert record["after"]["build"]["prototype_sha256"] == record["after"]["native_validation"]["prototype_sha256"] == record["after"]["vice"]["prototype_sha256"] == sha(b / "motion.prg")
p = Path("docs/baselines/multicolour-row-layout.json")
p.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"record": str(p), "prototype_sha256": sha(b / "motion.prg"), "segments": curr}, indent=2))
