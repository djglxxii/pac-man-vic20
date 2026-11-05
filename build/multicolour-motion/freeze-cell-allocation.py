from pathlib import Path
import hashlib
import json
import re

b = Path("build/multicolour-motion")
old = b / "before-cell-allocation"
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def segments(folder):
    return {m[0]: {"start": int(m[1], 16), "end_inclusive": int(m[2], 16), "bytes": int(m[3], 16)}
            for m in re.findall(r"^(ZEROPAGE|STATE|CODE|DATA|BSS)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+[0-9A-F]+\s*$", (folder / "motion.map").read_text(), re.M)}
prev, curr = segments(old), segments(b)
assert len(prev) == len(curr) == 5
assert curr["CODE"]["bytes"] - prev["CODE"]["bytes"] == -18
for name in ("ZEROPAGE", "STATE", "DATA", "BSS"):
    assert curr[name] == prev[name]
def data_bytes(folder):
    raw = (folder / "motion.prg").read_bytes()
    a = 2 + curr["DATA"]["start"] - int.from_bytes(raw[:2], "little")
    return raw[a:a + curr["DATA"]["bytes"]]
assert data_bytes(old) == data_bytes(b)
assert (b / "motion.s").read_bytes() == Path("prototypes/multicolour-motion.S").read_bytes()
main = sha(Path("build/pacman.prg"))
assert main == read(Path("docs/baselines/multicolour-restoration.json"))["main_game_sha256"]
assert len((b / "motion.prg").read_bytes()) == len((old / "motion.prg").read_bytes()) == 23077
listing = (b / "cell-allocation.lst").read_text()
names = ("restore_page", "restore_page_ready", "publish_page", "publish_page_ready", "resolve_hi")
labels = {name: 0x2000 + int(re.search(r"^([0-9A-F]{6})r.*?\b" + name + r":", listing, re.M)[1], 16) for name in names}
for name in ("restore", "publish"):
    assert (labels[name + "_page"] + 4) >> 8 == labels[name + "_page_ready"] >> 8
assert labels["resolve_hi"] >> 8 == (labels["resolve_hi"] + 7) >> 8
record = {
    "date": "2026-11-03", "status": "retained-streamlined-work-cell-allocation",
    "changes": [
        "Load the allocation slot directly into Y with LDY/CPY; retain it through all three metadata writes.",
        "Use TYA instead of reloading the allocation slot, and reuse carry clear from the successful capacity comparison.",
        "Omit the final unused DEY in each unrolled eight-row background copy.",
        "Use the resolver carry result in the preparation caller while preserving mc_status and failure cleanup.",
        "Move the existing eight-byte resolution high lookup before publication; assert its page placement and preserve both cache-hit assertions."
    ],
    "main_game_unchanged": True, "main_game_sha256": main,
    "before": {"prototype_sha256": sha(old / "motion.prg"), "native_validation": read(old / "validation.json"), "segments": prev},
    "after": {"build": read(b / "build.json"), "native_validation": read(b / "validation.json"), "segments": curr,
              "vice": read(b / "vice-validation.json"), "video": read(b / "cell-allocation-video.json")},
    "same_corpus_comparison": read(b / "cell-allocation-comparison.json"),
    "capacity_failure_propagation": read(b / "cell-allocation-failure.json"),
    "instruction_savings": {"cycles_per_new_cell": 8, "cycles_per_resolved_band": 4, "all_three_column_paths": True},
    "code_page_assertions": {"addresses": labels, "both_cached_branches_same_page": True, "resolution_high_lookup_same_page": True},
    "memory": {"code_byte_delta": -18, "state_byte_delta": 0, "zero_page_byte_delta": 0, "data_byte_delta": 0,
               "prg_bytes": 23077, "prg_length_unchanged": True, "data_and_bss_addresses_unchanged": True,
               "all_data_bytes_unchanged": True, "new_ram_configuration_required": False},
    "source_hashes": {str(p): sha(p) for p in map(Path, ["prototypes/multicolour-motion.S", "tools/arcade/build_multicolour_motion.py",
                      "tools/arcade/check_multicolour_motion.py", "tools/arcade/record_multicolour_motion.py", "docs/artwork/multicolour/actors-and-font.json"])},
    "capacity_probe_artifact": {"path": str(b / "check-allocation-failure.py"), "sha256": sha(b / "check-allocation-failure.py")},
    "limits": [
        "Renderer-only replay: game logic, input, audio, live pellets/HUD and background cache are not integrated.",
        "Original replay deadlines still yield 32.61 updates/s; CPU savings are not integrated game FPS.",
        "Carry reuse depends on the successful CPY capacity check and only loads, stores and TYA before ADC.",
        "Both success and capacity failure paths preserve the resolver carry contract.",
        "Prototype remains within conventional VIC-20 RAM; no final full-game memory placement or physical hardware test.",
        "Completed pictures are identical; no new perceptual flicker result is claimed."
    ]
}
assert record["after"]["build"]["prototype_sha256"] == record["after"]["native_validation"]["prototype_sha256"] == record["after"]["vice"]["prototype_sha256"] == sha(b / "motion.prg")
p = Path("docs/baselines/multicolour-cell-allocation.json")
p.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"record": str(p), "sha256": sha(b / "motion.prg"), "segments": curr, "asserted_code_addresses": labels}, indent=2))
