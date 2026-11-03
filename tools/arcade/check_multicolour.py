#!/usr/bin/env python3
"""Verify the isolated multicolour static PRG against actual VICE pixels."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import time

from PIL import Image

from maze_mockup import ROOT
from multicolour_mockup import decode
from record_playthrough import FrameMonitor


def breakpoint(mon, start, end=None, condition=None):
    number = struct.unpack_from("<I", mon.cmd(
        0x12, struct.pack("<HHBBBBB", start, start if end is None else end, 1, 1, 4, 0, 0)
    ))[0]
    if condition:
        encoded = condition.encode()
        mon.cmd(0x22, struct.pack("<IB", number, len(encoded)) + encoded)
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, default=ROOT / "build/multicolour")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/artwork/multicolour")
    args = parser.parse_args()
    build = args.build.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    labels = {parts[2][1:]: int(parts[1], 16)
              for line in (build / "display.lbl").read_text().splitlines()
              if len(parts := line.split()) == 3}
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    log = (build / "vice.log").open("w")
    vice = subprocess.Popen([
        "xvic", "-model", "vic20ntsc", "-memory", "all", "-autostartprgmode", "1",
        "-binarymonitor", "-binarymonitoraddress", f"127.0.0.1:{port}",
        "-initbreak", "reset", "-speed", "0", "+sound", "+saveres", "+autostart-warp",
        "-autostart", str(build / "display.prg"),
    ], stdout=log, stderr=subprocess.STDOUT)
    mon = None
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=1)
                break
            except OSError:
                if vice.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("VICE did not launch; see " + str(build / "vice.log"))
                time.sleep(0.05)
        connection.settimeout(20)
        mon = FrameMonitor(connection)
        entry = breakpoint(mon, labels["entry"])
        ready = breakpoint(mon, labels["display_ready"])
        mon.run_until_stop()
        canary = bytes([0xA5]) * (0x2000 - 0x1C40)
        mon.store(0x1C40, canary)
        mon.cmd(0x15, struct.pack("<IB", entry, 0))
        mon.run_until_stop()
        assert mon.memory(0x1C40, len(canary)) == canary, "static display crossed into virtual I/O or C stack"
        mon.cmd(0x15, struct.pack("<IB", ready, 0))
        raster = breakpoint(mon, 0, 65535, "(RL == $1) && (CY < $8)")
        mon.run_until_stop()
        for _ in range(3):
            mon.next_frame(raster)
        assert mon.memory(0x1800, 567) == (build / "screen.bin").read_bytes()
        assert bytes(c & 15 for c in mon.memory(0x9400, 567)) == (build / "colors.bin").read_bytes()
        palette = mon.palette()
        rgb = [tuple(palette[i:i + 3]) for i in range(0, 48, 3)]
        charset = (build / "charset.bin").read_bytes()
        patterns = [charset[code * 8:code * 8 + 8] for code in (build / "screen.bin").read_bytes()]
        expected = decode(patterns, list((build / "colors.bin").read_bytes()), rgb)
        data = mon.cmd(0x84, b"\0\0")
        width, height = struct.unpack_from("<HH", data, 4)
        pixels = data[21:]
        if len(pixels) == width * height - 4:
            pixels += bytes(4)
        picture = Image.frombytes("P", (width, height), pixels)
        picture.putpalette(palette)
        picture = picture.convert("RGB")
        picture.save(build / "vice-full.png")
        expected = expected.resize((336, 216), Image.Resampling.NEAREST)
        expected.save(build / "expected-vice-raster.png")
        target = expected.tobytes()
        first = target[:336 * 3]
        raw = picture.tobytes()
        match = None
        for y in range(height - 216 + 1):
            row = raw[y * width * 3:(y + 1) * width * 3]
            offset = row.find(first)
            if offset >= 0 and offset % 3 == 0:
                x = offset // 3
                if picture.crop((x, y, x + 336, y + 216)).tobytes() == target:
                    match = [x, y, 336, 216]
                    break
        if match is None:
            raise AssertionError(f"VICE raster differs from predicted artwork; debug={width}x{height}, see vice-full.png")
        x, y, w, h = match
        artwork = picture.crop((x, y, x + w, y + h)).resize((1008, 864), Image.Resampling.NEAREST)
        artwork.save(build / "vice-artwork-ntsc.png")
        artwork.save(output / "vice-artwork-ntsc.png")
        picture.resize((width * 3 // 2, height * 2), Image.Resampling.NEAREST).save(output / "vice-screen.png")
        report = {
            "emulator": "VICE NTSC VIC-20 with conventional expansion blocks",
            "static_prg_sha256": hashlib.sha256((build / "display.prg").read_bytes()).hexdigest(),
            "all_36288_native_pixels_match": True,
            "matrix_bytes_match": 567, "colour_bytes_match": 567,
            "virtual_io_and_stack_canary_bytes_intact": len(canary),
            "monitor_raster_rectangle": match,
            "palette_sources_verified": {"00": "black background", "01": "blue border", "10": "cell accent", "11": "white auxiliary"},
            "scope": "static artwork/mode validation; no moving-actor timing or game performance claim",
        }
        (build / "vice-validation.json").write_text(json.dumps(report, indent=2) + "\n")
        (output / "vice-validation.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        mon.cmd(0xBB)
        vice.wait(timeout=10)
    finally:
        if vice.poll() is None:
            vice.terminate()
            vice.wait(timeout=10)
        if mon:
            mon.s.close()
        log.close()


if __name__ == "__main__":
    main()
