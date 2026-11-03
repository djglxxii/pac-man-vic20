#!/usr/bin/env python3
"""Verify and record real multicolour gameplay in VICE using joystick input."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import struct
import subprocess
import time
import wave

from PIL import Image
from check_multicolour import breakpoint
from check_multicolour_motion import expected_scene, image_state
from maze_mockup import ROOT
from multicolour_mockup import decode
from record_multicolour_motion import memory_image, close
from record_playthrough import Bot, FPS, FrameMonitor, ffmpeg_path

PRG = ROOT / 'build/pacman-multicolour.prg'
OUT = ROOT / 'build/multicolour-game/vice'
SYMBOLS = {}


def picture(mon, palette):
    """Use the live NTSC origin; include a separate uncropped centring shot."""
    data = mon.cmd(0x84, b'\0\0')
    width, height = struct.unpack_from('<HH', data, 4)
    pixels = data[21:]
    if len(pixels) == width * height - 4: pixels += bytes(4)
    im = Image.frombytes('P', (width, height), pixels)
    im.putpalette(palette)
    x, y = mon.memory(0x9000, 2)
    # Monitor pixels double native horizontal dots. Its top is raster line 28.
    x, y = (x & 127) * 8, y * 2 - 28
    return im.crop((x, y, x + 336, y + 216)).convert('RGB')


def launch(name, sound=False):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    log = (OUT / f'{name}.log').open('w')
    command = ['xvic', '-model', 'vic20ntsc', '-memory', 'all', '-autostartprgmode', '1',
               '-controlport1device', '37', '-binarymonitor', '-binarymonitoraddress', f'127.0.0.1:{port}',
               '-initbreak', 'reset', '-speed', '0', '+saveres', '+autostart-warp']
    command += ['-sounddev', 'alsa', '-soundarg', 'null', '-soundoutput', '1'] if sound else ['+sound']
    process = subprocess.Popen(command + ['-autostart', str(PRG)], stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 20
    try:
        while True:
            try:
                connection = socket.create_connection(('127.0.0.1', port), timeout=1); break
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f'VICE launch failed: {log.name}')
                time.sleep(.05)
        connection.settimeout(20)
        return process, FrameMonitor(connection), log
    except BaseException:
        process.terminate(); process.wait(timeout=10); log.close(); raise


def playable(mon):
    """Boot, coin and start through the real input interface, then seek pellets."""
    mon.joystick('-')
    raster = breakpoint(mon, 0, 65535, '(RL == $1) && (CY < $8)')
    mon.run_until_stop()
    phase, released, started_updates = 'boot', 0, 0
    bot = Bot(5)
    for frame in range(4000):
        memory = mon.memory(0, 4096)
        main, level = memory[0xe00], memory[0xe04]
        updates = int.from_bytes(mon.memory(SYMBOLS['mc_frames'], 2), 'little')
        if phase == 'boot' and main == 1 and updates:
            mon.joystick('F'); phase = 'coin'
        elif phase == 'coin' and memory[0xe6e]:
            mon.joystick('-'); released, phase = frame, 'release'
        elif phase == 'release' and frame - released >= 30:
            mon.joystick('F'); phase = 'start'
        elif phase == 'start' and main == 3:
            mon.joystick('-'); phase, started_updates = 'play', updates
        if phase == 'play':
            if frame % 2 == 0: mon.joystick(bot.action(memory) if level == 3 else '-')
            rebuild = mon.memory(SYMBOLS['rebuild_phase'], 1)[0]
            if level == 3 and rebuild != 2 and updates > started_updates:
                return raster, bot, frame
        mon.next_frame(raster)
    raise RuntimeError('VICE did not reach the first completed playable picture')


def bg_patterns(memory):
    under = SYMBOLS['mc_backgrounds']
    codes = [c if c < 147 else memory[under+c-147] for c in memory[0x1800:0x1a37]]
    return [memory[0x1000+c*8:0x1008+c*8] for c in codes]


def validate():
    process, mon, log = launch('validation')
    try:
        raster, _, warmup = playable(mon)
        mon.cmd(0x15, struct.pack('<IB', raster, 0))
        front = mon.memory(SYMBOLS['video_refresh'],160)
        def return_point(name):
            address = SYMBOLS[name]
            offset = front.index(bytes((0x20,address & 255,address >> 8)))
            return SYMBOLS['video_refresh'] + offset + 3
        prepared_address, done_address = SYMBOLS['mc_front_prepared'], return_point('mc_commit')
        begin = breakpoint(mon, 0, 65535, f"PC == ${SYMBOLS['mc_prepare_begin']:x}")
        prepared = breakpoint(mon, 0, 65535, f'PC == ${prepared_address:x}')
        done = breakpoint(mon, 0, 65535, f'PC == ${done_address:x}')
        mon.cmd(0x15, struct.pack('<IB', prepared, 0))
        mon.cmd(0x15, struct.pack('<IB', done, 0))
        poses = json.loads((ROOT / 'build/multicolour-game/poses.json').read_text())['images']
        restored, slices = 0, 0
        for scene in range(32):
            mon.cmd(0x15, struct.pack('<IB', done, 0))
            mon.cmd(0x15, struct.pack('<IB', begin, 1))
            mon.run_until_stop()
            before = memory_image(mon)
            background = bg_patterns(before)
            colors = bytearray(v & 15 for v in before[0x9400:0x9637]); colors[42:546] = bytes([14]) * 504
            actors = mon.memory(SYMBOLS['actors'], 24)
            mon.cmd(0x15, struct.pack('<IB', prepared, 1))
            mon.cmd(0x15, struct.pack('<IB', begin, 0))
            while True:
                mon.run_until_stop()
                hidden = memory_image(mon)
                slices += 1
                assert image_state(before) == image_state(hidden), ('hidden preparation', scene)
                assert before[0x1000:0x1498] == hidden[0x1000:0x1498]
                if mon.memory(SYMBOLS['mc_pending'],1) == b'\1': break
            assert mon.memory(SYMBOLS['mc_pending'],1) == b'\1', ('prepare did not complete',scene)
            mon.cmd(0x15, struct.pack('<IB', done, 1))
            mon.cmd(0x15, struct.pack('<IB', prepared, 0)); mon.run_until_stop()
            current = memory_image(mon)
            patterns, expected_colors = expected_scene(actors, poses, background, colors)
            actual_patterns, actual_colors = image_state(current)
            assert actual_patterns == patterns and bytes(v & 15 for v in actual_colors) == expected_colors, ('published picture', scene)
            restored += sum(a >= 147 and b < 147 for a,b in zip(before[0x1800:0x1a37],current[0x1800:0x1a37]))
        # Only this verification process freezes a scene for the raster oracle.
        address = done_address
        mon.store(address, bytes((0x4c,address & 255,address >> 8)))
        mon.cmd(0x15, struct.pack('<IB', done, 0))
        mon.cmd(0x15, struct.pack('<IB', raster, 1)); mon.run_until_stop()
        for _ in range(3): mon.next_frame(raster)
        palette = mon.palette(); rgb = [tuple(palette[i:i+3]) for i in range(0,48,3)]
        expected = decode(patterns,list(expected_colors),rgb).resize((336,216),Image.Resampling.NEAREST)
        actual = picture(mon,palette)
        assert actual.tobytes() == expected.tobytes(), 'Actual VICE pixels differ'
        actual.resize((1008,864),Image.Resampling.NEAREST).save(OUT / 'verified-game.png')
        assert mon.memory(0x9000,2) == bytes((6,18)), 'NTSC origin differs'
        mon.screenshot(OUT / 'full-screen.png')
        return {'boot_coin_start_via_joystick': True, 'warmup_video_frames': warmup,
                'successive_live_scenes': 32, 'hidden_preparation_and_published_pixels': True,
                'hidden_actor_slices': slices, 'ntsc_origin': [6,18],
                'vacated_cells_restored': restored, 'all_36288_native_pixels_match': True,
                'validation_scene_frozen_only_for_pixel_comparison': True}
    finally:
        close(process, mon, log)


def record(frames):
    process, mon, log = launch('recording', True)
    encoder = None
    ffmpeg = ffmpeg_path(None)
    raw_audio, video = OUT / 'game-audio.wav', OUT / 'game-video.mp4'
    try:
        raster, bot, _ = playable(mon)
        palette = mon.palette()
        mon.resource('SoundRecordDeviceArg', raw_audio)
        mon.resource('SoundRecordDeviceName', 'wav')
        encoder = subprocess.Popen([ffmpeg,'-y','-hide_banner','-loglevel','error',
            '-f','rawvideo','-pixel_format','rgb24','-video_size','336x216',
            '-framerate',str(FPS),'-i','pipe:0','-vf','scale=1008:864:flags=neighbor,setsar=1',
            '-c:v','libx264','-threads','2','-preset','fast','-crf','16','-pix_fmt','yuv420p','-an',str(video)],stdin=subprocess.PIPE)
        states = []
        for frame in range(frames):
            memory = mon.memory(0,4096)
            if frame % 2 == 0: mon.joystick(bot.action(memory) if memory[0xe04] == 3 else '-')
            assert mon.memory(SYMBOLS['mc_cache_errors'],1) == b'\0'
            assert mon.memory(SYMBOLS['mc_status'],1) == b'\0'
            assert mon.memory(0x900e,1)[0] >> 4 == 1
            states.append({'frame':frame,'ticks':int.from_bytes(mon.memory(SYMBOLS['arcade_ticks'],2),'little'),
                           'updates':int.from_bytes(mon.memory(SYMBOLS['mc_frames'],2),'little'),
                           'pellets':memory[0xe0e],'score':list(memory[0xe80:0xe83]),'lives':memory[0xe14]})
            im = picture(mon,palette); encoder.stdin.write(im.tobytes())
            if frame in (0,frames//2,frames-1):
                im.resize((1008,864),Image.Resampling.NEAREST).save(OUT / f'game-{frame}.png')
            if frame + 1 < frames: mon.next_frame(raster)
        mon.cmd(0xbb); process.wait(timeout=10)
        encoder.stdin.close()
        if encoder.wait(timeout=30): raise RuntimeError('Video encoder failed')
        encoder = None
        with wave.open(str(raw_audio)) as audio:
            rate, channels, width = audio.getframerate(),audio.getnchannels(),audio.getsampwidth()
            samples = audio.readframes(audio.getnframes())
        assert width == 2
        values = struct.unpack('<' + 'h' * (len(samples)//2),samples)
        nonzero = sum(v != 0 for v in values)
        span = max(values) - min(values)
        assert nonzero > 100 and span > 64, 'VICE sound recording is silent'
        final = OUT / 'playable-preview.mp4'; duration = frames / float(FPS)
        subprocess.run([ffmpeg,'-y','-hide_banner','-loglevel','error','-i',str(video),'-i',str(raw_audio),
                        '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-af','apad','-t',str(duration),
                        '-movflags','+faststart',str(final)],check=True)
        (OUT / 'states.json').write_text(json.dumps(states,indent=2)+'\n')
        updates = (states[-1]['updates'] - states[0]['updates']) & 65535
        return {'frames':frames,'capture_fps':str(FPS),'completed_updates':updates,
                'observed_updates_per_second':round(updates / ((frames-1)/float(FPS)),2),
                'first':states[0],'last':states[-1],
                'audio':{'sample_rate':rate,'channels':channels,'nonzero_samples':nonzero,'sample_span':span},
                'video':str(final.relative_to(ROOT)),'sha256':hashlib.sha256(final.read_bytes()).hexdigest(),
                'joystick_only':True,'guest_memory_or_code_patched':False}
    finally:
        if encoder is not None:
            encoder.stdin.close(); encoder.terminate(); encoder.wait(timeout=10)
        close(process, mon, log)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames',type=int,default=600)
    args = parser.parse_args(); OUT.mkdir(parents=True,exist_ok=True)
    SYMBOLS = {p[2][1:]:int(p[1],16) for line in PRG.with_suffix('.lbl').read_text().splitlines() if len(p:=line.split()) == 3}
    report = {'prg_sha256':hashlib.sha256(PRG.read_bytes()).hexdigest(),
              'validation':validate(),'recording':record(args.frames)}
    (OUT / 'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
