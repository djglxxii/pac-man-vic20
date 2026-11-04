#!/usr/bin/env python3
"""Capture natural actor-commit rendering with current graphics and one input trace."""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

from rate_match import ROOT, capture, write_json
from record_playthrough import FPS, ffmpeg_path


def comparison(out, recordings, left, right, title, filename):
    label = Image.new('RGB', (720, 80), '#111111')
    draw = ImageDraw.Draw(label)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
    names = {'reference': 'Before: actor-commit', 'fast': 'After: optimized actor-commit',
             'baseline': 'Normal game'}
    for x, side in ((10, left), (370, right)):
        draw.text((x, 5), names[side], fill='white', font=font)
        draw.text((x, 31), recordings[side]['prg_sha256'][:12], fill='#aaaaaa', font=small)
    draw.text((10, 55), title, fill='#cccccc', font=small)
    header = out/(filename+'.png')
    label.save(header)
    result = out/(filename+'.mp4')
    subprocess.run([ffmpeg_path(None), '-y', '-hide_banner', '-loglevel', 'error',
                    '-i', str(out/left/'gameplay.mp4'), '-i', str(out/right/'gameplay.mp4'),
                    '-i', str(header), '-filter_complex',
                    '[0:v][1:v]hstack[games];[games]pad=720:544:0:80[pad];[pad][2:v]overlay=0:0',
                    '-c:v', 'libx264', '-threads', '2', '-crf', '16', '-pix_fmt', 'yuv420p',
                    str(result)], check=True)
    return str(result.relative_to(ROOT))


def summarize(recordings):
    report = {'mode': 'natural rendering; no PC gate or guest code patches',
              'same_logical_tick_joystick_trace': True, 'programs': {}}
    reference = recordings['reference']
    expected = {x['tick']: x for x in reference['inputs']}
    completed = {x['tick']: x for x in reference['renders']}
    for name, recording in recordings.items():
        states = [x for x in recording['inputs'] if x['phase'] == 'play' and x['tick'] in expected]
        matched = all((x['direction'], x['state_sha256']) ==
                      (expected[x['tick']]['direction'], expected[x['tick']]['state_sha256']) for x in states)
        common = [x for x in recording['renders'] if x['tick'] in completed]
        same_pictures = all(x['picture_sha256'] == completed[x['tick']]['picture_sha256'] for x in common)
        frames = recording['frames']
        seconds = (len(frames)-1)/float(FPS)
        calls = frames[-1]['completed_renders']-frames[0]['completed_renders']
        assert states and matched and common and same_pictures, (name, 'state/picture mismatch')
        assert not recording['mismatches'], (name, recording['mismatches'][:5])
        assert not recording['pc_render_gate'] and not recording['code_bytes_patched']
        assert all(x['line'] == 1 and x['cycle'] < 8 for x in frames)
        report['programs'][name] = {
            'prg_sha256': recording['prg_sha256'], 'loaded_program': recording['loaded_program'],
            'video_frames': len(frames), 'counter_interval_seconds': seconds,
            'completed_render_calls': calls, 'render_calls_per_second': calls/seconds,
            'matched_active_input_states': len(states), 'same_active_inputs_and_states': matched,
            'common_completed_render_ticks': len(common), 'same_completed_pictures_at_common_ticks': same_pictures,
            'first_tick': frames[0]['tick'], 'last_tick': frames[-1]['tick']}
    before, after = [report['programs'][n]['render_calls_per_second'] for n in ('reference', 'fast')]
    report['render_rate_gain_percent'] = (after/before-1)*100
    report['limits'] = ['Render cadence and raster phase vary naturally across builds.',
                        'Capture is silent; visual review is still required.',
                        'Common-tick completed pictures match; intermediate raster pixels may differ.']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=ROOT/'build/actor-speed/reference/pacman.prg')
    parser.add_argument('--fast', type=Path, default=ROOT/'build/actor-speed/fast/pacman.prg')
    parser.add_argument('--baseline', type=Path, default=ROOT/'build/actor-speed/current-baseline/pacman.prg')
    parser.add_argument('--input', type=Path, default=ROOT/'build/rate-match/active-1200/trial/recording.json')
    parser.add_argument('--output', type=Path, default=ROOT/'build/actor-speed/vice')
    parser.add_argument('--frames', type=int, default=1200)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    if args.frames < 60:
        parser.error('--frames must be at least 60')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.reuse:
        recordings = {name: json.loads((out/name/'recording.json').read_text())
                      for name in ('reference', 'fast', 'baseline')}
    else:
        inputs = json.loads(args.input.read_text())
        print('Recording current-font actor-commit reference...', flush=True)
        reference = capture(args.reference.resolve(), out/'reference', args.frames,
                            inputs, gate=False, compare_pictures=False)
        print('Recording optimized actor-commit...', flush=True)
        fast = capture(args.fast.resolve(), out/'fast', args.frames, reference, gate=False)
        print('Recording unchanged normal game...', flush=True)
        baseline = capture(args.baseline.resolve(), out/'baseline', args.frames, reference, gate=False)
        recordings = {'reference': reference, 'fast': fast, 'baseline': baseline}
    report = summarize(recordings)
    suffix = recordings['fast']['prg_sha256'][:8]
    reference_suffix = recordings['reference']['prg_sha256'][:8]
    baseline_suffix = recordings['baseline']['prg_sha256'][:8]
    report['before_after_video'] = comparison(out, recordings, 'reference', 'fast',
        'Same input trace; natural render rates; current graphics.',
        f'vic20-actor-speed-{reference_suffix}-vs-{suffix}')
    report['normal_comparison_video'] = comparison(out, recordings, 'baseline', 'fast',
        'Same input trace; natural render rates; current graphics.',
        f'vic20-normal-{baseline_suffix}-vs-actor-speed-{suffix}')
    write_json(out/'summary.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
