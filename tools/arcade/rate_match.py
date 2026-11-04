#!/usr/bin/env python3
"""Compare archived renderers at matched logical render ticks in real VICE.

Diagnostic only: the baseline's PC is redirected after audio service to skip
extra main-loop refreshes or admit a reference refresh. No PRG/code bytes are
patched. Inputs are applied before controls, indexed by logical tick. Raster
phase and completion times are observed, not forced to match.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

from record_playthrough import Bot, FPS, FrameMonitor, ffmpeg_path
from record_shadow import ROOT, launch, verify_loaded_program


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


class Observer(FrameMonitor):
    def response(self):
        result = super().response()
        kind, error, request, data = result
        if kind == 0x11 and len(data) >= 23 and data[4]:
            self.last_hit = struct.unpack_from('<I', data)[0]
        return result

    def checkpoint(self, address=0, end=None, condition=None):
        # Use PC conditions on the same address range as the raster observers.
        # Exact-address checkpoints were missed with that combination in the
        # installed VICE 3.7.1; the pilot checks these hooks actually execute.
        if end is None and condition is None:
            condition = f'PC == ${address:x}'
            address, end = 0, 65535
        data = self.cmd(0x12, struct.pack('<HHBBBBB', address,
                        address if end is None else end, 1, 1, 4, 0, 0))
        number = struct.unpack_from('<I', data)[0]
        if condition:
            text = condition.encode()
            self.cmd(0x22, struct.pack('<IB', number, len(text)) + text)
        return number

    def enable(self, number, enabled):
        self.cmd(0x15, struct.pack('<IB', number, int(enabled)))

    def register_names(self):
        data = self.cmd(0x83, b'\0')
        result, offset = {}, 2
        for _ in range(int.from_bytes(data[:2], 'little')):
            result[data[offset+4:offset+4+data[offset+3]].decode()] = data[offset+1]
            offset += data[offset] + 1
        return result

    def registers(self):
        data = self.cmd(0x31, b'\0')
        result, offset = {}, 2
        for _ in range(int.from_bytes(data[:2], 'little')):
            result[data[offset+1]] = int.from_bytes(data[offset+2:offset+4], 'little')
            offset += data[offset] + 1
        return result

    def pc(self, names, address):
        self.cmd(0x32, struct.pack('<BHBBH', 0, 1, 3, names['PC'], address))


def call_sites(prg):
    sys.path.insert(0, str(ROOT / 'tests'))
    from native import Sim
    sim = Sim(prg)
    try:
        sim.cmd('until boot_start 300')
        start = sim.labels['main']
        code = sim.peek(start, 4096)
        result = {}
        for name in ('frame_wait', 'audio_update', 'video_refresh'):
            needle = b'\x20' + sim.labels[name].to_bytes(2, 'little')
            hits = [start+i for i in range(len(code)) if code.startswith(needle, i)]
            if len(hits) != 1:
                raise RuntimeError(f'Expected one main call to {name}: {hits}')
            result[name] = hits[0]
        tail = sim.peek(result['video_refresh']+3, 3)
        assert tail[0] == 0x4c, 'Expected loop jump after refresh'
        result['loop_jump'] = result['video_refresh']+3
        return result
    finally:
        sim.close()


def game_state(mem):
    # Logical arcade RAM and its relocated flags; exclude compiler registers,
    # renderer metadata, saved underlays, and the physical VIC bitmap.
    return digest(mem[0xa0:0x100] + mem[0x400:0xf00] + mem[0x3f8:0x3fa])


def capture(source, out, frames, reference=None, gate=True, compare_pictures=True):
    out.mkdir(parents=True, exist_ok=True)
    prg = out / 'captured-program.prg'
    shutil.copy2(source, prg)
    shutil.copy2(source.with_suffix('.lbl'), prg.with_suffix('.lbl'))
    labels = {p[2][1:]: int(p[1], 16)
              for line in prg.with_suffix('.lbl').read_text().splitlines()
              if len(p := line.split()) == 3}
    sites = call_sites(prg)
    vice, original, log = launch(prg, out)
    mon = Observer(original.s)
    mon.req = original.req
    mon.last_hit = None
    encoder = None
    inputs, renders, pictures, gates = [], [], [], []
    ref_inputs = {x['tick']: x for x in reference['inputs']} if reference else {}
    ref_renders = {x['tick']: x for x in reference['renders']} if reference else {}
    bot, direction, phase, since = Bot(5), '-', 'boot', 0
    active, pending_tick, last_tick = False, None, -1
    mismatches = []
    try:
        mon.joystick('-')
        identity = verify_loaded_program(mon, prg, labels)
        names = mon.register_names()
        raster = mon.checkpoint(0, 65535, '(RL == $1) && (CY < $8)')
        rearm = mon.checkpoint(0, 65535, '(RL != $1) || (CY >= $8)')
        mon.enable(rearm, False)
        controls = mon.checkpoint(sites['frame_wait']+3)
        admission = mon.checkpoint(sites['audio_update']+3)
        render = mon.checkpoint(sites['video_refresh'])
        complete = mon.checkpoint(labels['video_frame_end'])
        palette = mon.palette()
        for event in range(100000):
            if event % 2000 == 0:
                print(f'{out.name}: tick {last_tick}, phase {phase}, frames {len(pictures)}', flush=True)
            mon.last_hit = None
            mon.run_until_stop()
            hit = mon.last_hit
            if hit == rearm:
                mon.enable(rearm, False)
                mon.enable(raster, True)
                continue
            if hit == raster:
                mon.enable(raster, False)
                mon.enable(rearm, True)
                if not active:
                    continue
                regs = mon.registers()
                tick = int.from_bytes(mon.memory(labels['arcade_ticks'], 2), 'little')
                if encoder is None:
                    encoder = subprocess.Popen([
                        ffmpeg_path(None), '-y', '-hide_banner', '-loglevel', 'error',
                        '-f', 'rawvideo', '-pixel_format', 'rgb24',
                        '-video_size', '240x232', '-framerate', str(FPS), '-i', 'pipe:0',
                        '-vf', 'scale=360:464:flags=neighbor,setsar=1',
                        '-c:v', 'libx264', '-threads', '2', '-preset', 'fast',
                        '-crf', '16', '-pix_fmt', 'yuv420p', '-an',
                        str(out / 'gameplay.mp4')], stdin=subprocess.PIPE)
                image = mon.picture(palette)
                encoder.stdin.write(image.tobytes())
                pictures.append({'frame': len(pictures), 'tick': tick,
                                 'completed_renders': len(renders),
                                 'raw_sha256': digest(image.tobytes()),
                                 'line': regs[names['LIN']], 'cycle': regs[names['CYC']]})
                if len(pictures) in (1, frames//2, frames):
                    image.save(out / f'frame-{len(pictures)-1}.png')
                if len(pictures) >= frames:
                    break
            elif hit == controls:
                mem = mon.memory(0, 4096)
                tick = int.from_bytes(mem[labels['arcade_ticks']:labels['arcade_ticks']+2], 'little')
                if tick <= last_tick:
                    raise AssertionError(('Non-increasing logic tick', tick, last_tick))
                last_tick = tick
                state = game_state(mem)
                previous_phase = phase
                if reference:
                    expected = ref_inputs.get(tick)
                    if expected is None:
                        # A faster baseline may begin the next logic iteration
                        # just before the final sampled raster. Finish capture
                        # without inventing another input or rendering a new pose.
                        direction = '-'
                    else:
                        direction, phase = expected['direction'], expected['phase']
                        if phase == 'play' and state != expected['state_sha256']:
                            mismatches.append({'kind': 'logic', 'tick': tick})
                else:
                    main, level = mem[0xe00], mem[0xe04]
                    if phase == 'boot' and main == 1 and not mem[labels['full_dirty']] and not mem[labels['bulk_active']]:
                        phase, since = 'attract', tick
                    if phase == 'attract' and tick-since >= 60:
                        phase, direction = 'coin', 'F'
                    elif phase == 'coin' and mem[0xe6e]:
                        phase, since, direction = 'release', tick, '-'
                    elif phase == 'release' and tick-since >= 30:
                        phase, direction = 'start', 'F'
                    elif phase == 'start' and main == 3:
                        phase, direction = 'ready', '-'
                    elif phase == 'ready' and level == 3:
                        phase, since = 'lead-in', tick
                    elif phase == 'lead-in' and tick-since >= 30:
                        phase = 'play'
                    if phase == 'play' and tick % 2 == 0:
                        direction = bot.action(mem) if level == 3 else '-'
                if phase == 'play':
                    active = True
                if phase != previous_phase:
                    print(f'{out.name}: tick {tick}, phase {phase}', flush=True)
                if tick > 10000 and not active:
                    raise RuntimeError(f'No play by tick {tick}: {phase}')
                inputs.append({'tick': tick, 'phase': phase, 'direction': direction,
                               'state_sha256': state})
                mon.joystick(direction)
            elif hit == admission:
                if reference and active and gate:
                    tick = int.from_bytes(mon.memory(labels['arcade_ticks'], 2), 'little')
                    allow = tick in ref_renders
                    mon.pc(names, sites['video_refresh'] if allow else sites['loop_jump'])
                    gates.append({'tick': tick, 'allow': allow})
            elif hit == render:
                tick = int.from_bytes(mon.memory(labels['arcade_ticks'], 2), 'little')
                if active:
                    regs = mon.registers()
                    pending_tick = {'tick': tick, 'line': regs[names['LIN']],
                                    'cycle': regs[names['CYC']]}
            elif hit == complete:
                if pending_tick is not None:
                    image = mon.memory(0x1000, 3136) + bytes(x & 15 for x in mon.memory(0x9600, 196))
                    pending_tick['picture_sha256'] = digest(image)
                    if reference and compare_pictures:
                        expected = ref_renders.get(pending_tick['tick'])
                        if (expected is None and gate) or (expected is not None and
                                expected['picture_sha256'] != pending_tick['picture_sha256']):
                            mismatches.append({'kind': 'picture', 'tick': pending_tick['tick']})
                    renders.append(pending_tick)
                    pending_tick = None
            else:
                raise AssertionError(f'Unexpected monitor stop: {hit}')
        else:
            raise RuntimeError('Diagnostic did not reach its frame count')
        mon.cmd(0xbb)
        vice.wait(timeout=10)
        encoder.stdin.close()
        if encoder.wait(timeout=30):
            raise RuntimeError('Video encoding failed')
        encoder = None
        result = {'source_prg': str(source.relative_to(ROOT)),
                  'prg_sha256': digest(prg.read_bytes()), 'loaded_program': identity,
                  'frame_rate': str(FPS), 'video_frames': frames,
                  'code_bytes_patched': False, 'pc_render_gate': reference is not None and gate,
                  'completed_picture_checks': reference is not None and compare_pictures,
                  'inputs': inputs, 'renders': renders, 'frames': pictures,
                  'gate_decisions': gates, 'mismatches': mismatches}
        write_json(out / 'recording.json', result)
        return result
    finally:
        if encoder:
            encoder.stdin.close()
            encoder.terminate()
            encoder.wait(timeout=10)
        if vice.poll() is None:
            vice.terminate()
            vice.wait(timeout=10)
        mon.s.close()
        log.close()


def compare(baseline, trial):
    br = {x['tick']: x for x in baseline['renders']}
    tr = {x['tick']: x for x in trial['renders']}
    common = sorted(br.keys() & tr.keys())
    if len(common) < 10:
        raise AssertionError('Too few common renders')
    low, high = common[0], common[-1]
    b_ticks = sorted(t for t in br if low <= t <= high)
    t_ticks = sorted(t for t in tr if low <= t <= high)
    reference_inputs = {x['tick']: x for x in trial['inputs']}
    matched_inputs = [x for x in baseline['inputs']
                      if x['phase'] == 'play' and x['tick'] in reference_inputs]
    same_inputs = all(x['direction'] == reference_inputs[x['tick']]['direction']
                      and x['state_sha256'] == reference_inputs[x['tick']]['state_sha256']
                      for x in matched_inputs)
    sampled_at_raster = all(x['line'] == 1 and x['cycle'] < 8
                           for data in (baseline, trial) for x in data['frames'])
    delta = Counter(b-a for a, b in zip(common, common[1:]))
    rates = {}
    for name, data in (('baseline', baseline), ('trial', trial)):
        count = data['frames'][-1]['completed_renders'] - data['frames'][0]['completed_renders']
        rates[name] = {'completed_calls_in_counter_interval': count,
                       'seconds': round((len(data['frames'])-1)/float(FPS), 6),
                       'render_calls_per_second': round(count*float(FPS)/(len(data['frames'])-1), 3),
                       'first_tick': data['frames'][0]['tick'],
                       'last_tick': data['frames'][-1]['tick']}
    return {'comparison': 'archived baseline versus archived actor-commit trial',
            'common_tick_range': [low, high], 'matched_completed_renders': len(common),
            'same_render_tick_sequence': b_ticks == t_ticks,
            'same_completed_pictures': all(br[t]['picture_sha256'] == tr[t]['picture_sha256'] for t in common),
            'matched_active_input_states': len(matched_inputs),
            'same_active_inputs_and_states': bool(matched_inputs) and same_inputs,
            'all_frames_sampled_in_raster_window': sampled_at_raster,
            'logic_mismatches': sum(x['kind'] == 'logic' for x in baseline['mismatches']),
            'picture_mismatches': sum(x['kind'] == 'picture' for x in baseline['mismatches']),
            'render_tick_intervals': dict(sorted(delta.items())),
            'baseline_pc_gate_decisions': len(baseline['gate_decisions']),
            'baseline_frames': len(baseline['frames']), 'trial_frames': len(trial['frames']),
            'actual_capture_rates': rates,
            'raster_phase_matched': False,
            'limits': ['Render admissions match logical ticks; raster phase and completion times are not matched.',
                       'Baseline admission is controlled through VICE PC redirection; this is not an unmodified gameplay benchmark.',
                       'Archived programs predate the accepted font changes.',
                       'Visual review is required; no automatic absence classifier or H1/H2 conclusion is supplied.']}


def video(out, baseline, trial):
    width, height = 720, 80
    label = Image.new('RGB', (width, height), '#111111')
    draw = ImageDraw.Draw(label)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
    draw.text((10, 5), 'Baseline: matched render ticks', fill='white', font=font)
    draw.text((370, 5), 'Actor-commit trial', fill='white', font=font)
    draw.text((10, 31), baseline['prg_sha256'][:12], fill='#aaaaaa', font=small)
    draw.text((370, 31), trial['prg_sha256'][:12], fill='#aaaaaa', font=small)
    draw.text((10, 55), 'Diagnostic: same render ticks; raster phase varies; archived graphics.',
              fill='#cccccc', font=small)
    label.save(out / 'labels.png')
    target = out / 'vic20-rate-matched-actor-commit.mp4'
    subprocess.run([ffmpeg_path(None), '-y', '-hide_banner', '-loglevel', 'error',
                    '-i', str(out/'baseline/gameplay.mp4'), '-i', str(out/'trial/gameplay.mp4'),
                    '-i', str(out/'labels.png'), '-filter_complex',
                    f'[0:v][1:v]hstack[games];[games]pad=720:{464+height}:0:{height}[pad];[pad][2:v]overlay=0:0',
                    '-c:v', 'libx264', '-threads', '2', '-crf', '16', '-pix_fmt', 'yuv420p',
                    str(target)], check=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT/'build/actor-commit/before/pacman.prg')
    parser.add_argument('--trial', type=Path, default=ROOT/'build/actor-commit/after/pacman.prg')
    parser.add_argument('--output', type=Path, default=ROOT/'build/rate-match')
    parser.add_argument('--frames', type=int, default=600)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    if args.frames < 60:
        parser.error('--frames must be at least 60')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.reuse:
        trial = json.loads((out/'trial/recording.json').read_text())
        baseline = json.loads((out/'baseline/recording.json').read_text())
    else:
        print('Recording actor-commit reference...', flush=True)
        trial = capture(args.trial.resolve(), out/'trial', args.frames)
        print('Recording baseline with matched logical render admissions...', flush=True)
        baseline = capture(args.baseline.resolve(), out/'baseline', args.frames, trial)
    summary = compare(baseline, trial)
    write_json(out/'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)
    print(video(out, baseline, trial), flush=True)
    if not (summary['same_render_tick_sequence'] and summary['same_completed_pictures']
            and summary['same_active_inputs_and_states'] and summary['all_frames_sampled_in_raster_window']
            and not summary['logic_mismatches'] and not summary['picture_mismatches']):
        raise SystemExit('Comparison failed its matching checks; do not interpret visually as a controlled A/B.')


if __name__ == '__main__':
    main()
