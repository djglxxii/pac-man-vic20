import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'tools/arcade'))
from native import Sim
from check_multicolour_motion import image_state

build = ROOT / 'build/multicolour-motion'
old = build / 'before-row-pass'
assets = ['replay.bin', 'source-poses.json', 'poses.json', 'background-charset.bin', 'background-map.bin', 'background-colors.bin']
asset_hashes = {}
for name in assets:
    before = (old / name).read_bytes()
    assert before == (build / name).read_bytes(), name
    asset_hashes[name] = hashlib.sha256(before).hexdigest()
replay = (build / 'replay.bin').read_bytes()
packet_path = build / 'compare.bin'
dump_path = build / 'compare.ram'
results = {}
for name, folder in [('before', old), ('after', build)]:
    sim = Sim(folder / 'motion.prg')
    costs, pictures = [], []
    trace_path = build / f'row-copy-{name}.trace'
    try:
        sim.cmd('until demo_ready 100')
        for symbol in ('get_work_cell', 'resolve_row', 'mc_publish'):
            sim.cmd(f'watch {symbol} {symbol}')
        sim.cmd('trace ' + str(trace_path.relative_to(ROOT)))
        for offset in range(0, len(replay), 25):
            packet_path.write_bytes(replay[offset:offset + 24])
            sim.cmd('load actors ' + str(packet_path.relative_to(ROOT)))
            prepare = int(sim.cmd('call mc_prepare')[-1].split('cycles=')[1])
            commit = int(sim.cmd('call mc_commit')[-1].split('cycles=')[1])
            costs.append({'scene': offset // 25, 'prepare': prepare, 'commit': commit, 'total': prepare + commit})
            sim.cmd('dump ' + str(dump_path.relative_to(ROOT)))
            glyphs, colors = image_state(dump_path.read_bytes())
            pictures.append(hashlib.sha256(b''.join(glyphs) + colors).hexdigest())
        sim.cmd('trace off')
    finally:
        sim.close()
    stacks, samples = {}, {}
    for line in trace_path.read_text().splitlines():
        cycle, event = line.split()
        symbol, kind = event.rsplit('-', 1)
        if kind == 'begin':
            stacks.setdefault(symbol, []).append(int(cycle))
        elif kind == 'end':
            samples.setdefault(symbol, []).append(int(cycle) - stacks[symbol].pop())
    profile = {symbol: {'mean_cycles_per_frame': round(sum(values) / len(costs), 2),
                        'calls_per_frame': round(len(values) / len(costs), 2),
                        'cycles_per_call': round(statistics.mean(values), 2)}
               for symbol, values in samples.items()}
    results[name] = {'frames': costs, 'picture_hashes': pictures, 'profile': profile}
assert results['before']['picture_hashes'] == results['after']['picture_hashes']
summary = {'recorded_scenes': len(results['after']['frames']), 'all_published_pictures_identical': True,
           'unchanged_asset_hashes': asset_hashes, 'before_profile': results['before']['profile'],
           'after_profile': results['after']['profile']}
for field in ('prepare', 'commit', 'total'):
    before = [row[field] for row in results['before']['frames']]
    after = [row[field] for row in results['after']['frames']]
    summary[field] = {'before_mean_cycles': round(statistics.mean(before), 2),
                      'after_mean_cycles': round(statistics.mean(after), 2),
                      'reduction_percent': round((1 - statistics.mean(after) / statistics.mean(before)) * 100, 2),
                      'faster_scenes': sum(a < b for a, b in zip(after, before)),
                      'equal_scenes': sum(a == b for a, b in zip(after, before)),
                      'slower_scenes': sum(a > b for a, b in zip(after, before)),
                      'minimum_cycles_saved': min(b - a for b, a in zip(before, after)),
                      'maximum_cycles_saved': max(b - a for b, a in zip(before, after))}
(build / 'row-copy-comparison-scenes.json').write_text(json.dumps(results, indent=2) + '\n')
(build / 'row-copy-comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
