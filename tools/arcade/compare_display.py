#!/usr/bin/env python3
"""Label two real raster captures at their natural cadence; never retime poses."""
import argparse
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont
from analyze_display import validate_frame_spacing
from rate_match import digest, write_json
from record_playthrough import FPS, ffmpeg_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--trial', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    paths = [args.baseline, args.trial]
    recordings = [json.loads((p/'recording.json').read_text()) for p in paths]
    summaries = [json.loads((p/'analysis.json').read_text()) for p in paths]
    for p, recording in zip(paths, recordings):
        validate_frame_spacing(recording['frames'])
        assert recording['loaded_program']['all_depacked_regions_match']
        assert digest((p/'captured-program.prg').read_bytes()) == recording['prg_sha256']
    assert recordings[0]['prg_sha256'] != recordings[1]['prg_sha256']
    assert recordings[0]['input_trace_sha256'] == recordings[1]['input_trace_sha256']
    assert recordings[0]['frame_rate'] == recordings[1]['frame_rate'] == str(FPS)
    count = min(len(r['frames']) for r in recordings)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
    small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
    target = args.output/'glyph-pool-comparison.mp4'
    encoder = subprocess.Popen([
        ffmpeg_path(None), '-y', '-hide_banner', '-loglevel', 'error',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '960x560',
        '-framerate', str(FPS), '-i', '-', '-an', '-c:v', 'libx264',
        '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target)
    ], stdin=subprocess.PIPE)
    try:
        for i in range(count):
            canvas = Image.new('RGB', (960, 560), '#202020')
            draw = ImageDraw.Draw(canvas)
            for side, (p, recording, summary) in enumerate(zip(paths, recordings, summaries)):
                frame = recording['frames'][i]
                with Image.open(p/frame['image']) as source:
                    source = source.convert('RGB')
                    assert digest(source.tobytes()) == frame['raw_sha256']
                    assert source.size == (240, 232)
                    canvas.paste(source.resize((480, 464), Image.Resampling.NEAREST), (side*480, 64))
                label = 'Accepted baseline' if side == 0 else 'Glyph pool trial'
                rate = summary['completed_renders_per_second']
                draw.text((side*480+10, 8), f'{label}: {rate:.2f} redraws/s', fill='white', font=font)
                draw.text((side*480+10, 32), f"PRG {recording['prg_sha256'][:12]} / tick {frame['tick']}", fill='white', font=small)
            draw.text((10, 536), 'Same joystick input per game tick; natural cadence. Actual VICE frames; no audio.', fill='white', font=small)
            encoder.stdin.write(canvas.tobytes())
            if i == min(600, count-1):
                canvas.save(args.output/'comparison.png')
        encoder.stdin.close()
        assert encoder.wait(timeout=30) == 0
    finally:
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()
    write_json(args.output/'comparison.json', dict(
        frames=count, frame_rate=str(FPS), audio=False, poses_retimed=False,
        sources=[dict(path=str(p.resolve()), prg_sha256=r['prg_sha256'])
                 for p, r in zip(paths, recordings)],
        video_sha256=digest(target.read_bytes())))
    print(target)


if __name__ == '__main__':
    main()
