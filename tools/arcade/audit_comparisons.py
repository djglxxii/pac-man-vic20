#!/usr/bin/env python3
"""Audit saved comparison halves against their independently saved sources.

Differences establish different footage, not reduced flicker or better motion.
--output defaults to a build artifact; this never changes game executables.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageChops, ImageStat
from record_playthrough import ROOT, ffmpeg_path

PAIRS = {
    'first-flicker': ('build/flicker', 'before/vice', 'after/vice'),
    'region-compositor': ('build/region-compositor', 'before/vice', 'after/vice'),
    'sprite-kernels': ('build/sprite-kernel', 'before/vice', 'after/vice'),
    'raster-sync': ('build/raster-sync', '../sprite-kernel/after/vice', 'after/vice'),
    'precomposition': ('build/precompose', 'before/vice', 'prototype-2/vice'),
    'temporary-characters': ('build/ghost-shadow/vice', 'before', 'after'),
    'beam-follow': ('build/beam-follow/vice', 'before', 'after'),
}


def audit(files):
    # The same local ffmpeg package used by the recorder also decodes frames.
    ffmpeg_path(None)
    import imageio_ffmpeg
    streams = [imageio_ffmpeg.read_frames(str(p), pix_fmt='rgb24') for p in files]
    try:
        metadata = [next(g) for g in streams]
        width, height = metadata[0]['size']
        side_width, side_height = metadata[1]['size']
        padding = height - side_height
        assert width == side_width * 2 and metadata[2]['size'] == (side_width, side_height)
        count, identical, changed = 0, 0, []
        errors, swapped = [[], []], [[], []]
        for frame, before, after in zip(*streams):
            combined = Image.frombytes('RGB', (width, height), frame)
            halves = [combined.crop((i*side_width, padding, (i+1)*side_width, height)) for i in range(2)]
            difference = ImageChops.difference(*halves)
            identical += difference.getbbox() is None
            red, green, blue = difference.split()
            histogram = ImageChops.lighter(ImageChops.lighter(red, green), blue).histogram()
            changed.append(sum(histogram[25:]))
            sources = [Image.frombytes('RGB', (side_width, side_height), data) for data in (before, after)]
            for i, picture in enumerate(halves):
                errors[i].append(sum(ImageStat.Stat(ImageChops.difference(picture, sources[i])).mean) / 3)
                swapped[i].append(sum(ImageStat.Stat(ImageChops.difference(picture, sources[1-i])).mean) / 3)
            count += 1
        return {
            'comparison': str(files[0].relative_to(ROOT)),
            'sha256': hashlib.sha256(files[0].read_bytes()).hexdigest(),
            'decoded_frames': count, 'identical_left_and_right_frames': identical,
            'frames_with_at_least_100_pixels_different_by_more_than_24': sum(n >= 100 for n in changed),
            'mean_changed_pixel_percent': round(sum(changed) / count / side_width / side_height * 100, 3),
            'mean_RGB_error_to_expected_sources': [round(sum(v) / len(v), 4) for v in errors],
            'mean_RGB_error_to_swapped_sources': [round(sum(v) / len(v), 4) for v in swapped],
            'left_source': str(files[1].relative_to(ROOT)),
            'right_source': str(files[2].relative_to(ROOT)),
        }
    finally:
        for stream in streams: stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/capture-audit/existing-videos.json')
    args = parser.parse_args()
    reports = {}
    for name, (base, before, after) in PAIRS.items():
        base = ROOT / base
        files = [base / 'comparison.mp4', base / before / 'gameplay.mp4', base / after / 'gameplay.mp4']
        if not all(p.exists() for p in files):
            reports[name] = {'status': 'source artifacts missing'}
        else:
            reports[name] = audit(files)
        print(name, reports[name], flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(reports, indent=2) + '\n')


if __name__ == '__main__':
    main()
