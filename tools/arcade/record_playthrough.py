#!/usr/bin/env python3
"""Drive the unchanged VIC PRG with joystick input and record VICE video/audio."""
import argparse
from collections import deque
from fractions import Fraction
import hashlib
import heapq
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import time
import wave

from PIL import Image
from vice_check import Monitor, ROOT

FPS = Fraction(1022727, 65 * 261)
DIRECTIONS = {"R": (-1, 0), "D": (0, 1), "L": (1, 0), "U": (0, -1)}
JOYSTICK = {"-": 0, "U": 1, "D": 2, "L": 4, "R": 8, "F": 16}


class Bot:
    """Seek remaining pellets along paths penalized for nearby dangerous ghosts."""

    def __init__(self, radius=5):
        self.radius = radius
        self.visits = {}
        self.last = None

    def action(self, mem):
        pacman = (mem[0xD09] // 8, mem[0xD08] // 8)
        screen = mem[0x400:0x800]
        # Game pixel coordinates map directly to screen[x*32+y]. Only the
        # tunnel row extends beyond the 28-column maze; its horizontal wrap
        # is represented as an ordinary graph edge.
        nodes = {
            (x, y) for x in range(32) for y in range(32)
            if (2 <= x <= 29 or y == 17) and screen[x * 32 + y] < 192
        }

        def edges(node):
            for direction, (dx, dy) in DIRECTIONS.items():
                neighbor = ((node[0] + dx) % 32, node[1] + dy)
                if neighbor in nodes:
                    yield direction, neighbor

        ghosts = [
            (mem[0xD01 + i * 2] // 8, mem[0xD00 + i * 2] // 8)
            for i in range(4) if not (mem[0xA7 + i] or mem[0xAC + i])
        ]
        hazard = {ghost: 0 for ghost in ghosts if ghost in nodes}
        queue = deque(hazard)
        while queue:
            node = queue.popleft()
            for _, neighbor in edges(node):
                if neighbor not in hazard:
                    hazard[neighbor] = hazard[node] + 1
                    queue.append(neighbor)
        if pacman != self.last:
            self.visits[pacman] = self.visits.get(pacman, 0) + 1
            self.last = pacman
        candidates = [(0, 0, pacman, "")]
        visited = set()
        tie = 0
        while candidates:
            cost, _, node, first = heapq.heappop(candidates)
            if node in visited:
                continue
            visited.add(node)
            if screen[node[0] * 32 + node[1]] in (16, 20) and node != pacman:
                return first
            for direction, neighbor in edges(node):
                if neighbor in visited:
                    continue
                penalty = max(0, self.radius - hazard.get(neighbor, 100)) ** 2 * 2
                if screen[neighbor[0] * 32 + neighbor[1]] == 20:
                    penalty = 0
                tie += 1
                heapq.heappush(candidates, (
                    cost + 1 + penalty + self.visits.get(neighbor, 0) * 0.02,
                    tie, neighbor, first or direction,
                ))
        return "L"


class FrameMonitor(Monitor):
    """Preserve asynchronous events and advance between fixed raster positions."""

    def response(self):
        stx, version, size, kind, error, request = struct.unpack(
            "<BBIBBI", self.read(12)
        )
        if stx != 2 or version != 2:
            raise RuntimeError("Invalid VICE binary-monitor response")
        return kind, error, request, self.read(size)

    def send(self, kind, body):
        self.req += 1
        self.s.sendall(struct.pack("<BBIIB", 2, 2, len(body), self.req, kind) + body)
        return self.req

    def cmd(self, kind, body=b""):
        request = self.send(kind, body)
        while True:
            _, error, actual, data = self.response()
            if actual == request:
                if error:
                    raise RuntimeError(f"VICE command {kind:02x}: error {error:02x}")
                return data

    def run_until_stop(self, kind=0xAA, body=b""):
        request = self.send(kind, body)
        acknowledged = running = stopped = False
        while not (acknowledged and running and stopped):
            event, error, actual, _ = self.response()
            if event == 0x63:
                running = True
            elif event == 0x62 and running:
                stopped = True
            if actual == request:
                if error:
                    raise RuntimeError(f"VICE run command {kind:02x}: error {error:02x}")
                acknowledged = True

    def next_frame(self, checkpoint):
        self.cmd(0x15, struct.pack("<IB", checkpoint, 0))
        # Step outside the eight-cycle capture window before re-enabling it,
        # preventing a second capture from the same scanline/frame.
        self.run_until_stop(0x71, struct.pack("<BH", 0, 12))
        self.cmd(0x15, struct.pack("<IB", checkpoint, 1))
        self.run_until_stop()

    def joystick(self, direction):
        # I/O simulation joystick, port 1. This is the only game input written;
        # no CPU memory, registers, pellets, lives or level counters are edited.
        self.cmd(0xA2, struct.pack("<HH", 0, 255 ^ JOYSTICK[direction]))

    def resource(self, name, value):
        name, value = name.encode(), str(value).encode()
        self.cmd(0x52, bytes((0, len(name))) + name + bytes((len(value),)) + value)

    def palette(self):
        data = self.cmd(0x91, b"\0")
        count = struct.unpack_from("<H", data)[0]
        colors = []
        offset = 2
        for _ in range(count):
            size = data[offset]
            colors.extend(data[offset + 1:offset + 4])
            offset += size + 1
        return colors + [0] * (768 - len(colors))

    def picture(self, palette):
        data = self.cmd(0x84, b"\0\0")
        width, height = struct.unpack_from("<HH", data, 4)
        pixels = data[21:]
        # VICE 3.7 omits four bytes from the far bottom-right border.
        if len(pixels) == width * height - 4:
            pixels += bytes(4)
        picture = Image.frombytes("P", (width, height), pixels)
        picture.putpalette(palette)
        # Include the full configured VIC display with a narrow black border.
        # The VIC monitor buffer doubles horizontal dots; scaling x1.5/y2
        # gives the same 3:2 pixel aspect as the existing VICE screenshots.
        return picture.crop((96, 0, 336, 232)).convert("RGB")


def ffmpeg_path(explicit):
    if explicit:
        return explicit
    if executable := shutil.which("ffmpeg"):
        return executable
    # Optional local dependency, deliberately outside the game/toolchain.
    sys.path.insert(0, str(ROOT / "build/capture/python"))
    try:
        import imageio_ffmpeg
    except ImportError as error:
        raise RuntimeError(
            "Install ffmpeg, pass --ffmpeg, or run: python3 -m pip install "
            "--target build/capture/python imageio-ffmpeg"
        ) from error
    return imageio_ffmpeg.get_ffmpeg_exe()


def record(args):
    out = (ROOT / args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_path(args.ffmpeg)
    labels = {
        p[2][1:]: int(p[1], 16)
        for line in (ROOT / "build/pacman.lbl").read_text().splitlines()
        if len(p := line.split()) == 3
    }
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    raw_audio = out / "vice-audio.wav"
    video_only = out / "video-only.mp4"
    final_video = out / "first-intermission.mp4"
    log = (out / "vice.log").open("w")
    encode_log = (out / "ffmpeg.log").open("w")
    vice = subprocess.Popen([
        args.vice, "-model", "vic20ntsc", "-memory", "all",
        "-autostartprgmode", "1", "-controlport1device", "37",
        "-binarymonitor", "-binarymonitoraddress", f"127.0.0.1:{port}",
        "-initbreak", "reset", "-speed", "0", "+saveres", "+autostart-warp",
        "-sounddev", "alsa", "-soundarg", "null", "-soundoutput", "1",
        "-autostart", str(ROOT / "build/pacman.prg"),
    ], stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    monitor = encoder = None
    report = {
        "emulator": "VICE NTSC VIC-20, full expansion",
        "prg_sha256": hashlib.sha256((ROOT / "build/pacman.prg").read_bytes()).hexdigest(),
        "joystick_only": True, "forced_board_completion": False,
        "capture_fps": str(FPS), "capture_raster_line": 1,
        "decision_interval_frames": 2, "hazard_radius": args.radius,
        "events": [], "completed_boards": [],
    }
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                connection = socket.create_connection(("127.0.0.1", port), timeout=1)
                break
            except OSError:
                if vice.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("VICE did not start; see " + str(out / "vice.log"))
                time.sleep(0.05)
        connection.settimeout(20)
        monitor = FrameMonitor(connection)
        monitor.joystick("-")
        checkpoint = struct.unpack_from("<I", monitor.cmd(
            0x12, struct.pack("<HHBBBBB", 0, 65535, 1, 1, 4, 0, 0)
        ))[0]
        # Parentheses are necessary for VICE's condition-expression precedence.
        condition = b"(RL == $1) && (CY < $8)"
        monitor.cmd(0x22, struct.pack("<IB", checkpoint, len(condition)) + condition)
        monitor.run_until_stop()
        bot = Bot(args.radius)
        phase = "boot"
        capture_start = phase_frame = None
        finish_frame = None
        recorded = 0
        direction = "-"
        palette = None
        started = time.monotonic()
        inputs = []
        last_state = None
        for frame in range(args.max_frames):
            mem = monitor.memory(0, 4096)
            main, level, board, lives, pills = (mem[a] for a in (0xE00, 0xE04, 0xE13, 0xE14, 0xE0E))
            ready = (
                monitor.memory(0x9002, 1) == b"\x8e"
                and main == 1 and not mem[labels["full_dirty"]]
                and not mem[labels["bulk_active"]]
            ) if phase == "boot" else False
            if ready:
                capture_start = phase_frame = frame
                phase = "attract"
                palette = monitor.palette()
                # Begin sound recording with the captured timeline. Autostart's
                # optional warp can omit earlier samples, so boot frame counts
                # are not a reliable audio offset.
                monitor.resource("SoundRecordDeviceArg", raw_audio)
                monitor.resource("SoundRecordDeviceName", "wav")
                encoder = subprocess.Popen([
                    ffmpeg, "-y", "-hide_banner", "-loglevel", "warning",
                    "-f", "rawvideo", "-pixel_format", "rgb24",
                    "-video_size", "240x232", "-framerate", str(FPS), "-i", "pipe:0",
                    "-vf", "scale=360:464:flags=neighbor,setsar=1",
                    "-c:v", "libx264", "-threads", "2", "-preset", "fast",
                    "-crf", "16", "-pix_fmt", "yuv420p", "-an", str(video_only),
                ], stdin=subprocess.PIPE, stdout=encode_log, stderr=encode_log)
            if phase == "attract" and frame - phase_frame >= 60:
                phase = "coin"
                direction = "F"
            elif phase == "coin" and mem[0xE6E]:
                phase, phase_frame, direction = "release", frame, "-"
            elif phase == "release" and frame - phase_frame >= 30:
                phase, direction = "start", "F"
            elif phase == "start" and main == 3:
                phase, direction = "ready", "-"
            elif phase == "ready" and level == 3:
                phase, phase_frame = "lead-in", frame
            elif phase == "lead-in" and frame - phase_frame >= 30:
                phase = "play"
            if phase == "play":
                if main != 3:
                    raise RuntimeError(f"Bot game over at board {board + 1}, {pills} pellets")
                if frame % 2 == 0:
                    direction = bot.action(mem) if level == 3 else "-"
                if pills == 244 and board < 2 and board + 1 not in report["completed_boards"]:
                    report["completed_boards"].append(board + 1)
                if board == 1 and mem[0xE06] and "intermission_start_frame" not in report:
                    report["intermission_start_frame"] = recorded
                    monitor.screenshot(out / "intermission.png")
                if board == 2 and level == 3 and finish_frame is None:
                    finish_frame = frame + 120
                    report["intermission_finished_frame"] = recorded
            if direction != (inputs[-1][1] if inputs else None):
                monitor.joystick(direction)
                inputs.append((frame, direction))
            if capture_start is not None:
                picture = monitor.picture(palette)
                encoder.stdin.write(picture.tobytes())
                if recorded == 0:
                    picture.resize((360, 464), Image.Resampling.NEAREST).save(out / "start.png")
                recorded += 1
            state = (phase, board, level, lives)
            if state != last_state:
                event = {"frame": recorded, "phase": phase, "board": board + 1,
                         "level_state": level, "lives": lives, "pellets_eaten": pills}
                report["events"].append(event)
                print(json.dumps(event), flush=True)
                last_state = state
            if frame % 600 == 0:
                print(f"frame={frame} recorded={recorded} host_seconds={time.monotonic()-started:.1f}", flush=True)
            if finish_frame is not None and frame >= finish_frame:
                monitor.screenshot(out / "after-intermission.png")
                report["remaining_lives"] = lives
                break
            monitor.next_frame(checkpoint)
        else:
            raise RuntimeError("Playthrough exceeded frame limit")
        monitor.cmd(0xBB)
        vice.wait(timeout=10)
        encoder.stdin.close()
        if encoder.wait(timeout=60):
            raise RuntimeError("Video encoder failed; see " + str(out / "ffmpeg.log"))
        encoder = None
        duration = recorded / float(FPS)
        with wave.open(str(raw_audio)) as audio:
            report["audio"] = {"sample_rate": audio.getframerate(), "channels": audio.getnchannels(),
                               "duration_seconds": audio.getnframes() / audio.getframerate()}
        audio_delta = report["audio"]["duration_seconds"] - duration
        if abs(audio_delta) > 0.1:
            raise RuntimeError(f"Audio/video capture duration differs by {audio_delta:.3f}s")
        report.update({"video_frames": recorded, "duration_seconds": duration,
                       "audio_trim_seconds": max(0, audio_delta),
                       "audio_duration_difference_seconds": audio_delta,
                       "host_seconds": time.monotonic() - started})
        subprocess.run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "warning", "-i", str(video_only),
            "-ss", str(report["audio_trim_seconds"]), "-i", str(raw_audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
            "-b:a", "128k", "-af", "apad", "-t", str(duration),
            "-movflags", "+faststart", str(final_video),
        ], check=True, stdout=encode_log, stderr=encode_log)
        report["video_sha256"] = hashlib.sha256(final_video.read_bytes()).hexdigest()
        (out / "inputs.json").write_text(json.dumps(inputs) + "\n")
        if report["completed_boards"] != [1, 2] or "intermission_finished_frame" not in report:
            raise RuntimeError("Recording did not complete both boards and the first intermission")
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(str(final_video), flush=True)
    finally:
        if encoder is not None:
            encoder.stdin.close()
            encoder.terminate()
            encoder.wait(timeout=10)
        if vice.poll() is None:
            vice.terminate()
            vice.wait(timeout=10)
        if monitor:
            monitor.s.close()
        log.close()
        encode_log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="build/playthrough")
    parser.add_argument("--vice", default="xvic")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--radius", type=int, default=5)
    parser.add_argument("--max-frames", type=int, default=24000)
    record(parser.parse_args())


if __name__ == "__main__":
    main()
