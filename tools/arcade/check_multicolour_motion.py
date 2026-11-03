#!/usr/bin/env python3
"""Check the prototype's actual 6502 pixels, hidden preparation and cycle costs."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

from maze_mockup import ROOT


def check_pacman_directions(build, poses):
    """Check source-to-pose semantics independently of the pixel compositor."""
    from build_multicolour_motion import packet
    names = json.loads((build / "poses.json").read_text())["names"]
    lookup = {name: i for i, name in enumerate(names)}
    table_cases = 0
    for slot in range(2, 14, 2):
        for code, expected in ((44, (0, 0, 2, 2)), (46, (0, 0, 2, 2)),
                               (45, (1, 3, 1, 3)), (47, (1, 3, 1, 3))):
            for flip, direction in enumerate(expected):
                record = {"attributes": [0] * 16, "positions": [0] * 16}
                record["attributes"][slot:slot + 2] = [code * 4 + flip, 9]
                record["positions"][slot:slot + 2] = [120, 148]
                actors, fallback = packet(record, lookup)
                pose = actors[(12 - slot) * 2 + 2]
                phase = 2 if code in (44, 45) else 1
                assert names[pose] == f"pacman-{direction}-{phase}", (slot, code, flip, names[pose])
                # Check the drawn opening, not only the name given to the pose.
                front, back = (((5, 6), (0, 6)), ((2, 13), (2, 0)),
                               ((0, 6), (5, 6)), ((2, 0), (2, 13)))[direction]
                assert poses[pose][front[1]][front[0]] == -1
                assert poses[pose][back[1]][back[0]] == 2
                assert not fallback
                table_cases += 1
        for direction in range(4):
            for flip in range(4):
                record = {"attributes": [0] * 16, "positions": [0] * 16}
                record["attributes"][slot:slot + 2] = [48 * 4 + flip, 9]
                record["positions"][slot:slot + 2] = [120, 148]
                actors, _ = packet(record, lookup, direction)
                assert names[actors[(12 - slot) * 2 + 2]] == f"pacman-{direction}-0"
                table_cases += 1

    source = json.loads((build / "source-poses.json").read_text())
    replay = (build / "replay.bin").read_bytes()

    def pacman(record):
        slot = next((s for s in range(2, 14, 2) if record["attributes"][s + 1] & 31 == 9), None)
        return None if slot is None else (slot, record["attributes"][slot] >> 2, *record["positions"][slot:slot + 2])

    def movement(before, after):
        if before is None or after is None:
            return None
        dx, dy = ((a - b + 128) % 256 - 128 for a, b in zip(before[2:], after[2:]))
        if dy == 0 and 0 < abs(dx) <= 8:
            return 0 if dx > 0 else 2
        if dx == 0 and 0 < abs(dy) <= 8:
            return 1 if dy > 0 else 3
        return None

    actors = [pacman(record) for record in source]
    open_checks, closed_checks, directions = 0, 0, set()
    for i, (actor, following) in enumerate(zip(actors, actors[1:])):
        direction = movement(actor, following)
        if direction is None:
            continue
        slot, code = actor[:2]
        if code in (44, 45, 46, 47):
            open_checks += 1
        elif code == 48 and i > 0 and movement(actors[i - 1], actor) == direction:
            closed_checks += 1
        else:
            continue
        pose = replay[i * 25 + (12 - slot) * 2 + 2]
        assert names[pose].startswith(f"pacman-{direction}-"), (i, direction, names[pose])
        directions.add(direction)
    assert open_checks > 0 and closed_checks > 0 and directions == {0, 1, 2, 3}
    return {"table_and_closed_hint_cases": table_cases, "recorded_open_mouth_motion_checks": open_checks,
            "recorded_closed_mouth_motion_checks": closed_checks, "all_four_directions_verified": True}


def expected_scene(packet, poses, background, colors):
    pixels = [bytearray(p) for p in background]
    palette = list(colors)
    for offset in range(0, 24, 4):
        x, y, pose, accent = packet[offset:offset + 4]
        if pose == 255:
            continue
        x = x - 256 if x >= 128 else x
        for dy, row in enumerate(poses[pose]):
            for dx, value in enumerate(row):
                px, py = x + dx, y + dy
                if value < 0 or not (0 <= px < 84 and 16 <= py < 208):
                    continue
                cell, shift = (py // 8) * 21 + px // 4, 6 - 2 * (px & 3)
                pixels[cell][py & 7] = (pixels[cell][py & 7] & ~(3 << shift)) | (value << shift)
                if value == 2:
                    palette[cell] = 8 | (accent & 7)
    return [bytes(p) for p in pixels], bytes(palette)


def image_state(memory):
    codes = memory[0x1800:0x1800 + 567]
    return [memory[0x1000 + code * 8:0x1008 + code * 8] for code in codes], memory[0x9400:0x9400 + 567]


def check_demo_replay(build, poses, background, colors):
    """Exercise the real packet loader, timer IRQ and replay wrap together."""
    from native import Sim
    replay = (build / "replay.bin").read_bytes()
    source_frames = len(replay) // 25
    guard_path, dump_path = build / "demo-guard.bin", build / "demo-stream.ram"
    guard = bytes([0xA5]) * 960
    guard_path.write_bytes(guard)
    sim = Sim(build / "motion.prg")
    count = source_frames + 16
    charset = (build / "background-charset.bin").read_bytes()
    try:
        sim.cmd("until demo_ready 100")
        sim.cmd("load $1c40 " + str(guard_path.relative_to(ROOT)))
        for index in range(count):
            sim.cmd("until demo_presented 512")
            sim.cmd("dump " + str(dump_path.relative_to(ROOT)))
            memory = dump_path.read_bytes()
            offset = (index % source_frames) * 25
            packet = replay[offset:offset + 24]
            assert int.from_bytes(memory[sim.labels["demo_frame"]:sim.labels["demo_frame"] + 2], "little") == index
            assert memory[sim.labels["actors"]:sim.labels["actors"] + 24] == packet, f"demo packet {index} changed"
            assert memory[sim.labels["mc_status"]] == 0, f"demo rejected packet {index}"
            assert image_state(memory) == expected_scene(packet, poses, background, colors), f"demo image {index} differs"
            assert memory[0x1000:0x1498] == charset
            assert memory[0x1C40:0x2000] == guard
            sim.cmd("until demo_ready 100")
        return {"scenes_checked": count, "source_packets": source_frames,
                "wraparound_scenes": 16, "real_packet_loader_and_timer_irq": True,
                "actors_and_published_pixels_match": True,
                "source_packets_or_control_state_patched": False,
                "guard_pattern_only": True}
    finally:
        sim.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build/multicolour-motion")
    args = parser.parse_args()
    build = args.build.resolve()
    sys.path.insert(0, str(ROOT / "tests"))
    from native import Sim
    poses = json.loads((build / "poses.json").read_text())["images"]
    direction_checks = check_pacman_directions(build, poses)
    charset = (build / "background-charset.bin").read_bytes()
    background = [charset[code * 8:code * 8 + 8] for code in (build / "background-map.bin").read_bytes()]
    colors = (build / "background-colors.bin").read_bytes()
    replay = (build / "replay.bin").read_bytes()
    packet_path, dump_path = build / "test.bin", build / "check.ram"
    sim = Sim(build / "motion.prg")
    costs, checked, peak_cells = [], 0, 0

    def dump():
        sim.cmd("dump " + str(dump_path.relative_to(ROOT)))
        return dump_path.read_bytes()

    def load(packet):
        packet_path.write_bytes(packet)
        sim.cmd("load actors " + str(packet_path.relative_to(ROOT)))

    def call(name):
        output = sim.cmd("call " + name)[-1]
        return int(output.split("cycles=")[1])

    def check(packet, timed=False):
        nonlocal checked, peak_cells
        load(packet)
        before = dump()
        prepare = call("mc_prepare")
        prepared = dump()
        assert prepared[sim.labels["mc_status"]] == 0, f"prepare rejected scene {checked}"
        assert image_state(prepared) == image_state(before), f"live image changed during preparation {checked}"
        assert prepared[0x1800:0x1A37] == before[0x1800:0x1A37]
        assert prepared[0x1000:0x1498] == charset, "permanent background glyph modified"
        assert prepared[0x1C40:0x2000] == bytes([0xA5]) * 960, "I/O/stack reservation overwritten"
        peak_cells = max(peak_cells, prepared[sim.labels["mc_new_count"]])
        assert prepared[sim.labels["mc_new_count"]] <= 54
        commit = call("mc_commit")
        after = dump()
        expected_pixels, expected_colors = expected_scene(packet, poses, background, colors)
        pixels, palette = image_state(after)
        assert pixels == expected_pixels, f"published pixels differ in scene {checked}"
        assert palette == expected_colors, f"published palette differs in scene {checked}"
        assert after[sim.labels["cell_work"]:sim.labels["cell_work"] + 567] == bytes([255]) * 567
        assert after[sim.labels["mc_pending"]] == 0
        assert after[0x1C40:0x2000] == bytes([0xA5]) * 960
        if timed:
            costs.append((prepare, commit))
        checked += 1

    try:
        sim.cmd("until demo_ready 100")
        packet_path.write_bytes(bytes([0xA5]) * 960)
        sim.cmd("load $1c40 " + str(packet_path.relative_to(ROOT)))
        sim.cmd("watch mc_publish publish")
        trace = build / "publication.trace"
        sim.cmd("trace " + str(trace.relative_to(ROOT)))
        for offset in range(0, len(replay), 25):
            check(replay[offset:offset + 24], timed=True)
        sim.cmd("trace off")
        replay_checks = checked
        hidden = bytes((0, 0, 255, 0)) * 6
        # Every pose, sub-character x phase, and y phase in isolation.
        for pose in range(len(poses)):
            for x_phase in range(4):
                for y_phase in range(8):
                    check(bytes((28 + x_phase, 80 + y_phase, pose, 2)) + hidden[4:])
        # Both edges, top/bottom HUD boundaries, and fully clipped actors.
        for x in (-8, -7, -5, -3, -1, 0, 79, 81, 83, 84, 87):
            for y in (0, 11, 15, 16, 194, 201, 207, 208, 250):
                check(bytes((x & 255, y, 0, 4)) + hidden[4:])
        # Partial first/last character bands must use the right source rows
        # for every pose and horizontal phase, including a single visible row.
        for pose in range(len(poses)):
            for x_phase in range(4):
                for y in (3, 10, 15, 193, 200, 207):
                    check(bytes((28 + x_phase, y, pose, 2)) + hidden[4:])
        rng = random.Random(6560)
        for i in range(180):
            packet = bytearray()
            for actor in range(6):
                x = rng.randrange(28, 38) if i & 1 else rng.randrange(-7, 87)
                y = rng.randrange(75, 88) if i & 1 else rng.randrange(10, 207)
                packet.extend((x & 255, y, rng.randrange(len(poses)), rng.randrange(8)))
            check(packet)
        # Six separate maximum-size footprints consume exactly all 54 cells.
        maximum = bytes(value for actor in range(6) for value in (3 + actor * 12, 59, 0, 2 + actor % 6))
        check(maximum)
        assert sim.peek("mc_old_count")[0] == 54
        # With 54 valid scratch records, reject one additional allocation in
        # each column path. The six footprints fill columns 0..17 in band 7:
        # starting at 18, 17 or 16 exhausts capacity on left, middle or right.
        # Normal six-actor inputs cannot exceed this bound on their own.
        before = image_state(dump())
        for column in (18, 17, 16):
            load(maximum); call("mc_prepare")
            sim.cmd("poke current_band 7")
            sim.cmd(f"poke actor_col {column}")
            call("resolve_row")
            assert sim.peek("mc_status")[0] == 1, f"capacity accepted column {column}"
            assert sim.peek("mc_new_count")[0] == 54
            assert image_state(dump()) == before
            call("mc_abort"); call("mc_commit")
            assert image_state(dump()) == before
        # A discarded prepared image and a replaced preparation must stay hidden.
        before = image_state(dump())
        load(replay[:24]); call("mc_prepare"); call("mc_abort"); call("mc_commit")
        assert image_state(dump()) == before
        load(replay[25:49]); call("mc_prepare")
        load(replay[50:74]); call("mc_prepare"); call("mc_commit")
        assert image_state(dump()) == expected_scene(replay[50:74], poses, background, colors)
        # Reject invalid input after partially filling scratch, preserving old image.
        before = image_state(dump())
        invalid = bytearray(replay[:24]); invalid[22] = len(poses)
        load(invalid); call("mc_prepare"); call("mc_commit")
        assert sim.peek("mc_status")[0] == 1
        assert image_state(dump()) == before
        check(hidden)
        check(replay[:24])
        events = [line.split() for line in trace.read_text().splitlines()]
        starts, published = [], []
        for cycle, event in events:
            if event == "publish-begin": starts.append(int(cycle))
            elif event == "publish-end": published.append(int(cycle) - starts.pop())
        hz = 1022727

        def summarize(values):
            values = sorted(values)
            return {"mean_cycles": round(statistics.mean(values), 2), "max_cycles": max(values),
                    "mean_ms": round(statistics.mean(values) * 1000 / hz, 3),
                    "p95_ms": round(values[int((len(values) - 1) * .95)] * 1000 / hz, 3),
                    "max_ms": round(max(values) * 1000 / hz, 3)}

        report = {
            "status": "passed", "prototype_sha256": hashlib.sha256((build / "motion.prg").read_bytes()).hexdigest(),
            "scenes_checked": checked, "recorded_pose_scenes": replay_checks,
            "all_pose_shift_phase_cases": len(poses) * 4 * 8,
            "edge_and_hud_cases": 99, "random_and_overlap_cases": 180,
            "partial_character_band_cases": len(poses) * 4 * 6,
            "maximum_live_work_cells_per_image": peak_cells,
            "hidden_preparation_verified": True, "background_and_guards_unchanged": True,
            "discard_replace_invalid_input_recovery": True,
            "capacity_guard_and_recovery": True,
            "capacity_guard_column_paths": 3,
            "pacman_facing": direction_checks,
            "prepare": summarize([p for p, c in costs]),
            "commit_including_cleanup": summarize([c for p, c in costs]),
            "publication": summarize(published),
            "total_renderer": summarize([p + c for p, c in costs]),
            "scope": "renderer-only replay; no logic, audio, input or changing maze cost included",
        }
        report["native_demo_replay"] = check_demo_replay(build, poses, background, colors)
        (build / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        sim.close()


if __name__ == "__main__":
    main()
