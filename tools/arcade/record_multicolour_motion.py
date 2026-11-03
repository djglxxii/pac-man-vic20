#!/usr/bin/env python3
"""Verify and record the separate moving compositor in NTSC VICE."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import time

from PIL import Image

from check_multicolour import breakpoint
from check_multicolour_motion import expected_scene, image_state
from maze_mockup import ROOT
from multicolour_mockup import decode
from record_playthrough import FPS, FrameMonitor, ffmpeg_path


def launch(build, name):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
    log = (build / f"vice-{name}.log").open("w")
    process = subprocess.Popen([
        "xvic", "-model", "vic20ntsc", "-memory", "all", "-autostartprgmode", "1",
        "-binarymonitor", "-binarymonitoraddress", f"127.0.0.1:{port}",
        "-initbreak", "reset", "-speed", "0", "+sound", "+saveres", "+autostart-warp",
        "-autostart", str(build / "motion.prg"),
    ], stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 20
    try:
        while True:
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=1); break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f"VICE launch failed; see {log.name}")
                time.sleep(.05)
        connection.settimeout(20)
        return process, FrameMonitor(connection), log
    except BaseException:
        if process.poll() is None: process.terminate(); process.wait(timeout=10)
        log.close(); raise


def close(process, mon, log):
    if process.poll() is None: process.terminate(); process.wait(timeout=10)
    mon.s.close(); log.close()


def labels(build):
    return {p[2][1:]: int(p[1], 16) for line in (build / "motion.lbl").read_text().splitlines()
            if len(p := line.split()) == 3}


def memory_image(mon):
    result = bytearray(65536)
    result[0x1000:0x2000] = mon.memory(0x1000, 0x1000)
    result[0x9400:0x9637] = mon.memory(0x9400, 567)
    return result


def picture(mon, palette):
    data = mon.cmd(0x84, b"\0\0")
    width, height = struct.unpack_from("<HH", data, 4)
    pixels = data[21:]
    if len(pixels) == width * height - 4: pixels += bytes(4)
    im = Image.frombytes("P", (width, height), pixels)
    im.putpalette(palette)
    return im.crop((96, 8, 432, 224)).convert("RGB")


def verify(build, symbols):
    process, mon, log = launch(build, "validation")
    try:
        enter = breakpoint(mon, symbols["entry"])
        start = breakpoint(mon, symbols["mc_prepare"])
        end = breakpoint(mon, symbols["mc_prepare_end"])
        done = breakpoint(mon, symbols["demo_presented"])
        mon.run_until_stop()
        mon.store(0x1C40, bytes([0xA5]) * 960)
        mon.cmd(0x15, struct.pack("<IB", enter, 0))
        charset = (build / "background-charset.bin").read_bytes()
        background = [charset[c * 8:c * 8 + 8] for c in (build / "background-map.bin").read_bytes()]
        colors = (build / "background-colors.bin").read_bytes()
        poses = json.loads((build / "poses.json").read_text())["images"]
        restored, scenes = 0, 32
        for scene in range(scenes):
            mon.cmd(0x15, struct.pack("<IB", start, 1))
            mon.cmd(0x15, struct.pack("<IB", end, 1))
            mon.run_until_stop()
            before = memory_image(mon)
            mon.cmd(0x15, struct.pack("<IB", start, 0)); mon.run_until_stop()
            prepared = memory_image(mon)
            assert image_state(before) == image_state(prepared), f"hidden preparation changed VICE scene {scene}"
            assert before[0x1800:0x1A37] == prepared[0x1800:0x1A37]
            mon.cmd(0x15, struct.pack("<IB", end, 0)); mon.run_until_stop()
            current = memory_image(mon)
            actors = mon.memory(symbols["actors"], 24)
            patterns, expected_colors = expected_scene(actors, poses, background, colors)
            actual_patterns, actual_colors = image_state(current)
            assert actual_patterns == patterns and bytes(v & 15 for v in actual_colors) == expected_colors, f"VICE scene {scene} differs"
            assert current[0x1000:0x1498] == charset
            assert current[0x1C40:0x2000] == bytes([0xA5]) * 960
            restored += sum(147 <= old <= 254 and new < 147
                            for old, new in zip(before[0x1800:0x1A37], current[0x1800:0x1A37]))
        assert restored > 0, "VICE scenes did not exercise vacated-cell restoration"
        # Freeze this test scene for three rasters; video recording uses a fresh process.
        mon.store(symbols["demo_presented"], bytes((0x4C, symbols["demo_presented"] & 255, symbols["demo_presented"] >> 8)))
        mon.cmd(0x15, struct.pack("<IB", done, 0))
        raster = breakpoint(mon, 0, 65535, "(RL == $1) && (CY < $8)")
        mon.run_until_stop()
        for _ in range(3): mon.next_frame(raster)
        palette = mon.palette()
        rgb = [tuple(palette[i:i + 3]) for i in range(0, 48, 3)]
        expected = decode(patterns, list(expected_colors), rgb).resize((336, 216), Image.Resampling.NEAREST)
        actual = picture(mon, palette)
        assert actual.tobytes() == expected.tobytes(), "VICE pixels differ from independent compositor oracle"
        actual.resize((1008, 864), Image.Resampling.NEAREST).save(build / "vice-verified-frame.png")
        return {"hidden_preparation_verified_in_vice": True, "published_matrix_and_palette_match": True,
                "all_36288_native_pixels_match": True, "virtual_io_and_stack_guard_bytes_intact": 960,
                "successive_scenes_checked": scenes, "vacated_cell_restorations_verified": restored,
                "validation_scene_frozen_only_for_pixel_comparison": True}
    finally:
        close(process, mon, log)


def record(build, symbols, frames):
    process, mon, log = launch(build, "recording")
    encoder = None
    try:
        ready = breakpoint(mon, symbols["demo_presented"])
        mon.run_until_stop()
        mon.cmd(0x15, struct.pack("<IB", ready, 0))
        raster = breakpoint(mon, 0, 65535, "(RL == $1) && (CY < $8)")
        mon.run_until_stop()
        mon.next_frame(raster)
        palette = mon.palette()
        encoder = subprocess.Popen([
            ffmpeg_path(None), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "336x216",
            "-framerate", str(FPS), "-i", "pipe:0", "-vf", "scale=1008:864:flags=neighbor,setsar=1",
            "-c:v", "libx264", "-threads", "2", "-preset", "fast", "-crf", "16",
            "-pix_fmt", "yuv420p", "-an", str(build / "motion-preview.mp4"),
        ], stdin=subprocess.PIPE)
        states = []
        for index in range(frames):
            state = mon.memory(symbols["mc_status"], 1)[0]
            assert state == 0, f"renderer rejected replay frame {index}"
            states.append({"video_frame": index, "completed_updates": int.from_bytes(mon.memory(symbols["demo_frame"], 2), "little")})
            im = picture(mon, palette)
            encoder.stdin.write(im.tobytes())
            if index in (0, frames // 2, frames - 1):
                im.resize((1008, 864), Image.Resampling.NEAREST).save(build / f"vice-motion-{index}.png")
            mon.next_frame(raster)
        encoder.stdin.close()
        if encoder.wait(timeout=30): raise RuntimeError("video encoder failed")
        encoder = None
        (build / "video-states.json").write_text(json.dumps(states, indent=2) + "\n")
        seconds = (frames - 1) / float(FPS)
        return {"captured_video_frames": frames, "capture_fps": str(FPS),
                "completed_updates_during_capture": states[-1]["completed_updates"] - states[0]["completed_updates"],
                "observed_replay_updates_per_second": round((states[-1]["completed_updates"] - states[0]["completed_updates"]) / seconds, 2),
                "video": "motion-preview.mp4", "video_guest_memory_or_code_patched": False,
                "scope": "real VICE capture of recorded-pose demo; no game logic, audio, live pellets or live scores"}
    finally:
        if encoder:
            encoder.stdin.close(); encoder.terminate(); encoder.wait(timeout=10)
        close(process, mon, log)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build/multicolour-motion")
    parser.add_argument("--frames", type=int, default=600)
    args = parser.parse_args()
    build = args.build.resolve(); symbols = labels(build)
    report = {"prototype_sha256": hashlib.sha256((build / "motion.prg").read_bytes()).hexdigest(),
              "validation": verify(build, symbols), "recording": record(build, symbols, args.frames)}
    (build / "vice-validation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
