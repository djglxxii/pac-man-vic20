#!/usr/bin/env python3
"""Build a separate moving-character renderer test, using recorded game poses."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from maze_mockup import ROOT
from multicolour_mockup import (
    ACCENT, TRANSPARENT, WHITE, font_glyph, frame, ghost, pacman, tile_walls,
)

BUILD = ROOT / "build/multicolour-motion"


def poses(assets):
    names, images = [], []
    for direction in range(4):
        for phase in range(2):
            names.append(f"ghost-{direction}-{phase}")
            images.append(ghost(assets, direction, phase))
    for phase in range(2):
        names.append(f"frightened-{phase}")
        images.append(ghost(assets, phase=phase, frightened=True))
    for direction in range(4):
        names.append(f"eyes-{direction}")
        images.append([[TRANSPARENT if value == ACCENT else value for value in row]
                       for row in ghost(assets, direction)])
    for direction in range(4):
        for phase in range(3):
            names.append(f"pacman-{direction}-{phase}")
            images.append(pacman(direction, phase))
    names.append("cherry")
    cherry = ["..b...", ".b.bb.", ".b...b", ".b...b", ".aa.aa", "aaaaaa", "awawaa", "aaaaaa", ".aa.aa", "..a.a."] + ["......"] * 4
    images.append([[{".": TRANSPARENT, "a": ACCENT, "b": 1, "w": WHITE}[v] for v in row] for row in cherry])
    return names, images


def capture_source(output, count):
    """Sample only stable render boundaries, avoiding ISR's temporary rotations."""
    sys.path.insert(0, str(ROOT / "tests"))
    from native import Sim
    from performance import start_game
    from record_playthrough import Bot
    bot, result = Bot(5), []
    sim = Sim()
    dump = output / "source.ram"
    try:
        start_game(sim)
        sim.cmd("until video_frame_begin 100")
        for _ in range(count):
            sim.cmd("dump " + str(dump.relative_to(ROOT)))
            memory = dump.read_bytes()
            action = bot.action(memory) if memory[0xE04] == 3 else "-"
            result.append({
                "tick": int.from_bytes(memory[sim.labels["arcade_ticks"]:sim.labels["arcade_ticks"] + 2], "little"),
                "cycle": int(sim.cmd("stats")[0].split()[1]),
                "attributes": list(memory[0xC20:0xC30]), "positions": list(memory[0xC30:0xC40]),
                "level_state": memory[0xE04], "pellets": memory[0xE0E], "input": action,
            })
            sim.cmd("joy " + action)
            sim.cmd("run 1")
            sim.cmd("until video_frame_begin 100")
    finally:
        sim.close()
    (output / "source-poses.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def pacman_direction(code, flip):
    # The ROM masks have already been rotated into screen coordinates:
    # 44/46 open to the right; 45/47 open downward. 48 is the closed circle.
    direction = 0 if code in (44, 46, 48) else 1
    if flip & 1 and direction & 1:
        direction ^= 2
    if flip & 2 and not direction & 1:
        direction ^= 2
    return direction


def recorded_pacman_directions(source):
    """Keep the custom eye facing along motion when the ROM mouth is closed.

    Closed-circle code 48 does not encode the vertical facing direction. The
    replay retains the latest unambiguous mouth direction or actual movement;
    this changes only custom pose selection, never the recorded coordinates.
    """
    result, previous, facing = [], None, None
    for record in source:
        actor = next((slot for slot in range(2, 14, 2) if record["attributes"][slot + 1] & 31 == 9), None)
        if actor is None:
            result.append(None); previous = None
            continue
        attr = record["attributes"][actor]
        code, flip = attr >> 2, attr & 3
        current = tuple(record["positions"][actor:actor + 2])
        if code in (44, 45, 46, 47):
            facing = pacman_direction(code, flip)
        elif previous is not None:
            dx, dy = ((old - new + 128) % 256 - 128 for old, new in zip(previous, current))
            if 0 < abs(dx) < 16 and abs(dx) > abs(dy):
                facing = 0 if dx > 0 else 2
            elif 0 < abs(dy) < 16 and abs(dy) > abs(dx):
                facing = 1 if dy > 0 else 3
        if facing is None:
            facing = pacman_direction(code, flip)
        result.append(facing)
        previous = current
    return result


def packet(record, lookup, closed_pacman_direction=None):
    result, fallback = bytearray(), []
    for slot in (12, 10, 8, 6, 4, 2):
        attr, pal = record["attributes"][slot:slot + 2]
        raw_x, raw_y = record["positions"][slot:slot + 2]
        code, flip, pal = attr >> 2, attr & 3, pal & 31
        x = ((239 - raw_x - (slot <= 4)) * 3) // 8
        y = ((272 - raw_y) * 3) // 4 - 1
        if not pal or x < -8 or x >= 84 or y < 0 or y >= 208:
            result.extend((0, 0, 255, 0)); continue
        accent = {1: 2, 3: 4, 5: 3, 7: 7, 9: 7}.get(pal, 2)
        if 32 <= code < 40:
            direction = (code - 32) // 2
            if flip & 1 and direction & 1: direction ^= 2
            if flip & 2 and not direction & 1: direction ^= 2
            name = f"eyes-{direction}" if pal == 25 else f"ghost-{direction}-{code & 1}"
        elif code in (28, 29):
            name = f"frightened-{code & 1}"
        elif pal == 9:
            direction = pacman_direction(code, flip)
            if code == 48 and closed_pacman_direction is not None:
                direction = closed_pacman_direction
            phase = 0 if code == 48 else 2 if code in (44, 45) else 1
            name = f"pacman-{direction}-{phase}"
            if code not in (44, 45, 46, 47, 48): fallback.append([slot, code, pal])
        elif slot == 12:
            name, accent = "cherry", 2
        else:
            name = "ghost-0-0"
            fallback.append([slot, code, pal])
        result.extend((x & 255, y, lookup[name], accent))
    return result, fallback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BUILD)
    parser.add_argument("--frames", type=int, default=480)
    parser.add_argument("--reuse-source", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    fixture = (ROOT / "build/arcade/tests/game.ram").read_bytes()
    assets = json.loads((ROOT / "docs/artwork/multicolour/actors-and-font.json").read_text())
    walls = tile_walls(json.loads((ROOT / "docs/artwork/maze-wall-tiles.json").read_text())["tiles"])
    patterns, colors, _, _, _ = frame(fixture, walls, assets, "maze")
    font_patterns = {font_glyph(rows) for rows in assets["font"].values()}
    font_patterns |= {font_glyph(assets["life_icon"], 0), font_glyph(assets["cherry_icon"], 0)}
    background = sorted(set(patterns) | font_patterns)
    assert len(background) <= 147
    codes = {pattern: code for code, pattern in enumerate(background)}
    charset = b"".join(background).ljust(147 * 8, b"\0")
    (output / "background-charset.bin").write_bytes(charset)
    # The VIC and pixel oracle use character-major bytes; the CPU copies each
    # scanline directly from a row-major encoding of those same 147 glyphs.
    (output / "background-rows.bin").write_bytes(bytes(charset[code * 8 + row]
                                                    for row in range(8) for code in range(147)))
    (output / "background-map.bin").write_bytes(bytes(codes[p] for p in patterns))
    (output / "background-colors.bin").write_bytes(bytes(colors))
    names, images = poses(assets)
    lookup = {name: i for i, name in enumerate(names)}
    records, record_codes, row_ids = [], {}, bytearray()
    for image in images:
        for phase in range(4):
            for row in image:
                value = sum((0 if v == TRANSPARENT else v) << (22 - 2 * (x + phase)) for x, v in enumerate(row))
                cover = sum((0 if v == TRANSPARENT else 3) << (22 - 2 * (x + phase)) for x, v in enumerate(row))
                data = tuple((value >> shift) & 255 for shift in (16, 8, 0))
                masks = tuple(((cover >> shift) & 255) ^ 255 for shift in (16, 8, 0))
                accent = sum(any((byte >> bit) & 3 == ACCENT for bit in (0, 2, 4, 6)) << column for column, byte in enumerate(data))
                record = data + masks + (accent,)
                if record not in record_codes:
                    record_codes[record] = len(records); records.append(record)
                row_ids.append(record_codes[record])
    assert len(records) <= 256
    (output / "pose-rows.bin").write_bytes(row_ids)
    (output / "row-records.bin").write_bytes(bytes(record[field] for field in range(7) for record in records))
    (output / "poses.json").write_text(json.dumps({"names": names, "images": images}, indent=2) + "\n")
    (output / "pose-accents.bin").write_bytes(bytes(any(ACCENT in row for row in im) for im in images))
    if args.reuse_source:
        source = json.loads((output / "source-poses.json").read_text())
    else:
        source = capture_source(output, args.frames)
    replay, fallbacks = bytearray(), []
    directions = recorded_pacman_directions(source)
    for index, record in enumerate(source):
        actors, fallback = packet(record, lookup, directions[index])
        fallbacks.extend((index, *item) for item in fallback)
        elapsed = source[index + 1]["cycle"] - record["cycle"] if index + 1 < len(source) else 16875
        hold = max(1, min(255, round(elapsed / 16875)))
        replay.extend(actors); replay.append(hold)
    (output / "replay.bin").write_bytes(replay)
    (output / "motion.inc").write_text(f"POSE_COUNT = {len(images)}\nROW_RECORDS = {len(records)}\nREPLAY_FRAMES = {len(source)}\n")
    (output / "motion.cfg").write_text('''MEMORY {
 LOAD: start=$11ff,size=2,file=%O;
 BASIC: start=$1201,size=$dff,file=%O,fill=yes;
 ZP: start=$02,size=$9e,type=rw,file="";
 STATE: start=$1a37,size=$209,type=rw,file="";
 RAM: start=$2000,size=$6000,type=rw,file=%O;
}
SEGMENTS {
 LOADADDR: load=LOAD,type=ro;
 BASIC: load=BASIC,type=ro;
 ZEROPAGE: load=ZP,type=zp;
 STATE: load=STATE,type=bss;
 CODE: load=RAM,type=ro;
 DATA: load=RAM,type=ro,align=$100;
 BSS: load=RAM,type=bss,align=$100;
}
''')
    shutil.copyfile(ROOT / "prototypes/multicolour-motion.S", output / "motion.s")
    subprocess.run([str(ROOT / "tools/cc65/usr/bin/ca65"), "motion.s", "-o", "motion.o"], cwd=output, check=True)
    subprocess.run([str(ROOT / "tools/cc65/usr/bin/ld65"), "-C", "motion.cfg", "-Ln", "motion.lbl", "-m", "motion.map", "motion.o", "-o", "motion.prg"], cwd=output, check=True)
    runner = output / "run.sh"
    runner.write_text('''#!/bin/sh
set -eu
vic_motion_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec xvic -model vic20ntsc -memory all -autostartprgmode 1 -autostart "$vic_motion_dir/motion.prg"
'''); runner.chmod(0o755)
    report = {"status": "moving compositor prototype; replay only, not an integrated game",
              "source_prg_sha256": hashlib.sha256((ROOT / "build/pacman.prg").read_bytes()).hexdigest(),
              "prototype_sha256": hashlib.sha256((output / "motion.prg").read_bytes()).hexdigest(),
              "frames": len(source), "source_boundary": "video_frame_begin",
              "source_ticks": [source[0]["tick"], source[-1]["tick"]],
              "background_characters_loaded": len(background), "background_slots_reserved": 147,
              "background_copy_layout": "eight 147-byte row planes; replaces character-major data in the PRG",
              "background_copy_bytes": 147 * 8,
              "work_banks": [[147, 200], [201, 254]], "actors_supported": 6,
              "pose_row_index_bytes": len(row_ids), "unique_shifted_row_records": len(records),
              "shifted_row_record_bytes": len(records) * 7,
              "pacman_facing": "screen-space arcade masks and flip bits; closed mouth follows recorded movement",
              "fallback_artwork_samples": fallbacks,
              "limitations": ["Frozen full-pellet maze and score; recorded actor positions only.",
                              "No background glyph cache, live game logic, audio or input is integrated in this executable."]}
    (output / "build.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
