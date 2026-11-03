"""Record original/temporary-character previews using identical joystick input."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/arcade'))
from record_playthrough import Bot, FrameMonitor, FPS, ffmpeg_path


def verify_loaded_program(mon, prg, labels):
    """Compare actual VICE RAM with an independently executed PRG depacker."""
    sys.path.insert(0, str(ROOT / 'tests'))
    from native import Sim
    sim = Sim(prg)
    try:
        sim.cmd('until boot_start 300')
        regions = [(0x2000, 0x6000), (0xa000, 0x2000),
                   (0x400, labels['__boot_limit'] - 0x400)]
        expected = [sim.peek(start, size) for start, size in regions]
    finally:
        sim.close()
    number = struct.unpack_from('<I', mon.cmd(
        0x12, struct.pack('<HHBBBBB', 0, 65535, 1, 1, 4, 0, 0)))[0]
    condition = f"PC == ${labels['boot_start']:x}".encode()
    mon.cmd(0x22, struct.pack('<IB', number, len(condition)) + condition)
    mon.run_until_stop()
    actual = [mon.memory(start, size) for start, size in regions]
    assert actual == expected, 'VICE loaded a different program image'
    mon.cmd(0x13, struct.pack('<I', number))
    return {'all_depacked_regions_match': True,
            'bytes_checked': sum(size for _, size in regions),
            'loaded_image_sha256': hashlib.sha256(b''.join(actual)).hexdigest()}


def trace_checkpoint(mon, address):
    """A non-stopping execution checkpoint counts completed render calls."""
    number = struct.unpack_from('<I', mon.cmd(
        0x12, struct.pack('<HHBBBBB', 0, 65535, 0, 1, 4, 0, 0)))[0]
    condition = f'PC == ${address:x}'.encode()
    mon.cmd(0x22, struct.pack('<IB', number, len(condition)) + condition)
    return number


def checkpoint_hits(mon, number):
    return struct.unpack_from('<I', mon.cmd(0x11, struct.pack('<I', number)), 13)[0]


def launch(prg, out):
    out.mkdir(parents=True, exist_ok=True)
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
        return vice, FrameMonitor(conn), log
    except BaseException:
        vice.terminate()
        vice.wait(timeout=10)
        log.close()
        raise


def capture(prg, out, count, replay=None, audit=False):
    source_prg = prg
    if audit:
        out.mkdir(parents=True, exist_ok=True)
        snapshot = out / 'captured-program.prg'
        shutil.copy2(prg, snapshot)
        shutil.copy2(prg.with_suffix('.lbl'), snapshot.with_suffix('.lbl'))
        prg = snapshot
    labels = {parts[2][1:]: int(parts[1], 16)
              for line in prg.with_suffix('.lbl').read_text().splitlines()
              if len(parts := line.split()) == 3}
    vice, mon, log = launch(prg, out)
    encoder = None
    inputs, states = [], []
    identity = None
    render_checkpoint = None
    feature_checkpoints = {}
    try:
        mon.joystick('-')
        if audit:
            identity = verify_loaded_program(mon, prg, labels)
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
                    if audit:
                        render_checkpoint = trace_checkpoint(mon, labels['video_frame_end'])
                        feature_checkpoints = {name: trace_checkpoint(mon, labels[name])
                                               for name in ('shadow_begin', 'beam_group_begin', 'commit_group') if name in labels}
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
                picture = mon.picture(palette)
                pixels = picture.tobytes()
                encoder.stdin.write(pixels)
                if audit:
                    states[-1]['raw_frame_sha256'] = hashlib.sha256(pixels).hexdigest()
                    states[-1]['completed_render_calls'] = checkpoint_hits(mon, render_checkpoint)
                    states[-1]['feature_calls'] = {name: checkpoint_hits(mon, number)
                                                   for name, number in feature_checkpoints.items()}
                    for name in ('beam_frames', 'beam_protected', 'beam_fallback'):
                        if name in labels:
                            states[-1][name] = int.from_bytes(mon.memory(labels[name], 2), 'little')
                if recorded in (0, count // 2, count - 1):
                    picture.save(out / f'frame-{recorded}.png')
                recorded += 1
                if recorded >= count:
                    break
            mon.joystick(direction)
            mon.next_frame(checkpoint)
        else:
            raise RuntimeError('Capture timed out')
        control = None
        if audit:
            # A clearly synthetic control AFTER the unmodified recording tests
            # that this capture source sees changes to actual VIC output.
            normal = mon.picture(palette)
            normal.save(out / 'control-before.png')
            old_colour = mon.memory(0x900f, 1)
            mon.store(0x900f, b'\x4b')
            for _ in range(3): mon.next_frame(checkpoint)
            forced = mon.picture(palette)
            forced.save(out / 'control-purple.png')
            purple = tuple(palette[12:15])
            normal_purple = dict((colour, n) for n, colour in normal.getcolors(normal.width * normal.height)).get(purple, 0)
            forced_purple = dict((colour, n) for n, colour in forced.getcolors(forced.width * forced.height)).get(purple, 0)
            assert forced_purple - normal_purple > forced.width * forced.height // 4, 'Synthetic purple display control was not captured'
            mon.store(0x900f, old_colour)
            control = {'after_recording': True, 'VIC_register_900f': '4b',
                       'normal_sha256': hashlib.sha256(normal.tobytes()).hexdigest(),
                       'forced_sha256': hashlib.sha256(forced.tobytes()).hexdigest(),
                       'normal_purple_pixels': normal_purple,
                       'forced_purple_pixels': forced_purple,
                       'different_raw_frames': True}
        mon.cmd(0xBB)
        vice.wait(timeout=10)
        encoder.stdin.close()
        if encoder.wait(timeout=30):
            raise RuntimeError('Encoding failed')
        encoder = None
        (out / 'inputs.json').write_text(json.dumps(inputs) + '\n')
        (out / 'states.json').write_text(json.dumps(states) + '\n')
        report = {'prg': str(source_prg.relative_to(ROOT)),
                  'prg_sha256': hashlib.sha256(prg.read_bytes()).hexdigest(),
                  'video_frames': count, 'fps': str(FPS),
                  'joystick_only': True, 'guest_patches': False,
                  'first': states[0], 'last': states[-1]}
        if audit:
            renders = states[-1]['completed_render_calls'] - states[0]['completed_render_calls']
            report['audit'] = {'snapshot_prg': str(prg.relative_to(ROOT)),
                               'loaded_program': identity,
                               'completed_render_calls': renders,
                               'render_calls_per_second': round(renders * float(FPS) / (count-1), 2),
                               'executed_features': {name: states[-1]['feature_calls'][name] - states[0]['feature_calls'][name]
                                                     for name in feature_checkpoints},
                               'synthetic_control_after_recording': control}
        (out / 'recording.json').write_text(json.dumps(report, indent=2) + '\n')
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, default=ROOT / 'build/pacman.prg')
    parser.add_argument('--after', type=Path, default=ROOT / 'build/pacman-shadow.prg')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/ghost-shadow/vice')
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--reuse-captures', action='store_true',
                        help='Only rebuild the comparison from existing recordings')
    parser.add_argument('--audit', action='store_true',
                        help='Verify loaded RAM, count renders and test an obvious display change')
    args = parser.parse_args()
    if args.frames < 60: parser.error('--frames must be at least 60')
    out = args.output.resolve()
    if not args.reuse_captures:
        inputs = capture(args.before.resolve(), out / 'before', args.frames, audit=args.audit)
        capture(args.after.resolve(), out / 'after', args.frames, inputs, audit=args.audit)
    subprocess.run([
        ffmpeg_path(None), '-y', '-hide_banner', '-loglevel', 'error',
        '-i', str(out / 'before/gameplay.mp4'), '-i', str(out / 'after/gameplay.mp4'),
        '-filter_complex', '[0:v][1:v]hstack',
        '-c:v', 'libx264', '-threads', '2', '-crf', '16', '-pix_fmt', 'yuv420p',
        str(out / 'comparison.mp4'),
    ], check=True)
    print(out / 'comparison.mp4')
