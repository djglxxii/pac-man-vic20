"""Local raster-capture comparison; joystick input only, no guest patches."""
import argparse
import json
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/arcade'))
from record_playthrough import Bot, FrameMonitor, FPS, ffmpeg_path


def capture(prg, out, count, replay=None):
    out.mkdir(parents=True, exist_ok=True)
    labels = {parts[2][1:]: int(parts[1], 16)
              for line in prg.with_suffix('.lbl').read_text().splitlines()
              if len(parts := line.split()) == 3}
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    log = (out / 'vice.log').open('w')
    vice = subprocess.Popen([
        'xvic', '-model', 'vic20ntsc', '-memory', 'all',
        '-autostartprgmode', '1', '-controlport1device', '37',
        '-binarymonitor', '-binarymonitoraddress', f'127.0.0.1:{port}',
        '-initbreak', 'reset', '-speed', '0', '+sound', '+saveres',
        '+autostart-warp', '-autostart', str(prg),
    ], stdout=log, stderr=subprocess.STDOUT)
    encoder = mon = None
    inputs, states = [], []
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                conn = socket.create_connection(('127.0.0.1', port), timeout=1)
                break
            except OSError:
                if vice.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('VICE launch failed')
                time.sleep(.05)
        conn.settimeout(20)
        mon = FrameMonitor(conn)
        mon.joystick('-')
        checkpoint = struct.unpack_from('<I', mon.cmd(
            0x12, struct.pack('<HHBBBBB', 0, 65535, 1, 1, 4, 0, 0)))[0]
        condition = b'(RL == $1) && (CY < $8)'
        mon.cmd(0x22, struct.pack('<IB', checkpoint, len(condition)) + condition)
        mon.run_until_stop()
        phase, since, direction, recorded = 'boot', 0, '-', 0
        palette = None
        bot = Bot(5)
        for frame in range(7000):
            mem = mon.memory(0, 4096)
            main, level = mem[0xE00], mem[0xE04]
            if phase == 'boot' and (mon.memory(0x9002, 1) == b'\x8e'
                    and main == 1 and not mem[labels['full_dirty']]
                    and not mem[labels['bulk_active']]):
                phase, since = 'attract', frame
            if phase == 'attract' and frame - since >= 60:
                phase, direction = 'coin', 'F'
            elif phase == 'coin' and mem[0xE6E]:
                phase, since, direction = 'release', frame, '-'
            elif phase == 'release' and frame - since >= 30:
                phase, direction = 'start', 'F'
            elif phase == 'start' and main == 3:
                phase, direction = 'ready', '-'
            elif phase == 'ready' and level == 3:
                phase, since = 'lead-in', frame
            elif phase == 'lead-in' and frame - since >= 30:
                phase = 'play'
            if phase == 'play':
                if encoder is None:
                    palette = mon.palette()
                    encoder = subprocess.Popen([
                        ffmpeg_path(None), '-y', '-hide_banner', '-loglevel', 'error',
                        '-f', 'rawvideo', '-pixel_format', 'rgb24',
                        '-video_size', '240x232', '-framerate', str(FPS), '-i', 'pipe:0',
                        '-vf', 'scale=360:464:flags=neighbor,setsar=1',
                        '-c:v', 'libx264', '-threads', '2', '-preset', 'fast',
                        '-crf', '16', '-pix_fmt', 'yuv420p', '-an',
                        str(out / 'gameplay.mp4'),
                    ], stdin=subprocess.PIPE)
                if replay is not None:
                    direction = replay[recorded]
                elif recorded % 2 == 0:
                    direction = bot.action(mem) if level == 3 else '-'
                inputs.append(direction)
                states.append({'tick': int.from_bytes(mon.memory(labels['arcade_ticks'], 2), 'little'),
                               'attributes': list(mem[0xC20:0xC30]),
                               'positions': list(mem[0xC30:0xC40]),
                               'pellets': mem[0xE0E]})
                encoder.stdin.write(mon.picture(palette).tobytes())
                recorded += 1
                if recorded >= count:
                    break
            mon.joystick(direction)
            mon.next_frame(checkpoint)
        else:
            raise RuntimeError('Capture timed out')
        mon.cmd(0xBB)
        vice.wait(timeout=10)
        encoder.stdin.close()
        if encoder.wait(timeout=30):
            raise RuntimeError('Encoding failed')
        encoder = None
        (out / 'inputs.json').write_text(json.dumps(inputs) + '\n')
        (out / 'states.json').write_text(json.dumps(states) + '\n')
        return inputs
    finally:
        if encoder:
            encoder.stdin.close()
            encoder.terminate()
            encoder.wait(timeout=10)
        if vice.poll() is None:
            vice.terminate()
            vice.wait(timeout=10)
        if mon:
            mon.s.close()
        log.close()


if __name__ == '__main__':
    inputs = capture(ROOT / 'build/flicker/before/pacman.prg',
                     ROOT / 'build/flicker/before/vice', 600)
    capture(ROOT / 'build/pacman.prg', ROOT / 'build/flicker/after/vice', 600, inputs)
