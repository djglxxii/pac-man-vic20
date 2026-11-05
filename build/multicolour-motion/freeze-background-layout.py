from pathlib import Path
import hashlib
import json
import re

b = Path('build/multicolour-motion')
old = b / 'before-background-layout'
def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def segments(folder):
    return {m[0]: {'start': int(m[1], 16), 'end_inclusive': int(m[2], 16), 'bytes': int(m[3], 16)}
            for m in re.findall(r'^(ZEROPAGE|STATE|CODE|DATA|BSS)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+([0-9A-F]+)\s+[0-9A-F]+\s*$', (folder / 'motion.map').read_text(), re.M)}
previous, current = segments(old), segments(b)
assert len(current) == 5 and previous == current
assert (old / 'motion.s').read_bytes() == (b / 'motion.s').read_bytes() == Path('prototypes/multicolour-motion.S').read_bytes()
assert (old / 'motion.map').read_bytes() == (b / 'motion.map').read_bytes()
assert len((b / 'motion.prg').read_bytes()) == len((old / 'motion.prg').read_bytes()) == 23077
main = sha(Path('build/pacman.prg'))
assert main == read(Path('docs/baselines/multicolour-row-layout.json'))['main_game_sha256']
unchanged = ('replay.bin', 'source-poses.json', 'poses.json', 'background-colors.bin',
             'pose-accents.bin', 'pose-rows.bin', 'row-records.bin')
for name in unchanged:
    assert (old / name).read_bytes() == (b / name).read_bytes(), name
# No executable byte changed: only the background row planes and map differ.
start = 2 + current['CODE']['start'] - 0x1201
stop = start + current['CODE']['bytes']
assert (old / 'motion.prg').read_bytes()[start:stop] == (b / 'motion.prg').read_bytes()[start:stop]
record = {
    'date': '2026-11-03', 'status': 'retained-background-glyph-ordering',
    'changes': [
        'Assign background glyph codes by frequency across the entire static playfield, excluding HUD rows.',
        'Use pattern bytes as a deterministic tie breaker; do not use actor positions or replay frequencies.',
        'Remap the background map and both charset encodings together; preserve all decoded glyphs and cells.',
        'No assembly instructions, addresses, padding, memory allocations or runtime sorting changed.'
    ],
    'main_game_unchanged': True, 'main_game_sha256': main,
    'before': {'prototype_sha256': sha(old / 'motion.prg'), 'native_validation': read(old / 'validation.json'), 'segments': previous},
    'after': {'build': read(b / 'build.json'), 'native_validation': read(b / 'validation.json'), 'segments': current,
              'vice': read(b / 'vice-validation.json'), 'video': read(b / 'background-layout-video.json')},
    'same_corpus_comparison': read(b / 'background-layout-comparison.json'),
    'background_lookup_analysis': read(b / 'background-layout-analysis.json'),
    'unchanged_asset_hashes': {name: sha(b / name) for name in unchanged},
    'remapped_asset_hashes': {name: {'before': sha(old / name), 'after': sha(b / name)}
                            for name in ('background-map.bin', 'background-charset.bin', 'background-rows.bin')},
    'memory': {'code_byte_delta': 0, 'data_byte_delta': 0, 'state_byte_delta': 0, 'zero_page_byte_delta': 0,
               'prg_bytes': 23077, 'all_segment_addresses_unchanged': True, 'assembly_byte_identical': True,
               'no_padding_added': True, 'new_ram_configuration_required': False},
    'source_hashes': {str(path): sha(path) for path in map(Path, [
        'prototypes/multicolour-motion.S', 'tools/arcade/build_multicolour_motion.py',
        'tools/arcade/check_multicolour_motion.py', 'tools/arcade/record_multicolour_motion.py',
        'docs/artwork/multicolour/actors-and-font.json'])},
    'diagnostic_artifact': {'path': str(b / 'analyze-background-layout.py'), 'sha256': sha(b / 'analyze-background-layout.py')},
    'limits': [
        'Only 0.05% mean renderer CPU saving; two recorded scenes cost two additional cycles.',
        'The ordering uses the static maze; another maze or dynamic cache can have different savings.',
        'Replay only: no game logic, input, audio, live pellets/HUD or background cache integrated.',
        'Replay pacing remains 32.61 updates/s; this is not a game FPS or perceptual flicker improvement.',
        'Full-game memory placement and physical hardware validation remain pending.'
    ]
}
assert record['after']['build']['prototype_sha256'] == record['after']['native_validation']['prototype_sha256'] == record['after']['vice']['prototype_sha256'] == sha(b / 'motion.prg')
p = Path('docs/baselines/multicolour-background-layout.json')
p.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'record': str(p), 'prototype_sha256': sha(b / 'motion.prg'), 'segments': current}, indent=2))
