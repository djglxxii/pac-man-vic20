#!/usr/bin/env python3
"""Check the live multicolour game, arcade parity, cache ownership and pixels."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import unittest

from native import Sim, NativeParity, Runner, ROOT, WORK
from performance import start_game
sys.path.insert(0, str(ROOT / 'tools/arcade'))
from check_multicolour_motion import expected_scene, image_state
from maze_mockup import position
from multicolour_mockup import pack_grid
from build_multicolour_motion import packet, recorded_pacman_directions

PRG = ROOT / 'build/pacman-multicolour.prg'
BUILD = ROOT / 'build/multicolour-game'


class LiveParity(NativeParity):
    @classmethod
    def setUpClass(cls):
        cls.game = (WORK / 'game.ram').read_bytes()
        cls.ref = Runner('oracle')
        cls.ref.cmd('run 600')
        cls.sim = Sim(PRG)
        cls.sim.cmd('run 500')

    def test_03_build_memory_limits(self):
        sections = {}
        for line in (BUILD / 'pacman.map').read_text().splitlines():
            match = re.match(r'\s*([a-f0-9]+)\s+[a-f0-9]+\s+([a-f0-9]+)\s+\d+ (\.[a-z_.]+)$', line)
            if match:
                sections[match[3]] = (int(match[1], 16), int(match[2], 16))
        for section, limit in (('.text', 0x8000), ('.arcade_data', 0xc000),
                               ('.work', 0x400), ('.screen_work', 0x300),
                               ('.video_bits', 0x1000), ('.mc_state', 0x1c40),
                               ('.mc_under', 0x1d40), ('.mc_low_tables', 0x2c4),
                               ('.mc_shift_tables', 0x1f20)):
            start, size = sections[section]
            self.assertLessEqual(start + size, limit, section)
        self.assertEqual(self.sim.labels['__stack'], 0x2000)
        self.assertEqual(self.sim.labels['__stack_bottom'], 0x1f20)
        self.assertEqual(self.sim.labels['cell_work'] & 255, 0)
        # Both boot-load images are resident before main releases logical RAM.
        self.assertEqual(self.sim.peek(0x9000), b'\x06')
        shifted = ((BUILD / 'shifted-data.bin').read_bytes()
                   + (BUILD / 'shifted-tails.bin').read_bytes())
        self.assertEqual(self.sim.peek(0x1d40, len(shifted)), shifted)

    def test_06_audio_converter_registers(self):
        # Reuse all 160 independent divider/volume cases, while separately
        # requiring the auxiliary-colour nibble that the live display needs.
        test, original = self, self.sim
        class AudioView:
            def __getattr__(self, name): return getattr(original, name)
            def peek(self, address, size=1):
                value = original.peek(address, size)
                if address == 0x900a and size == 5:
                    test.assertEqual(value[4] & 0xf0, 0x10)
                    return value[:4] + bytes((value[4] & 15,))
                return value
        self.sim = AudioView()
        try:
            super().test_06_audio_converter_registers()
        finally:
            self.sim = original


def dump(sim):
    path = BUILD / 'check-live.ram'
    sim.cmd('dump ' + str(path.relative_to(ROOT)))
    return path.read_bytes()


def drain(sim):
    for _ in range(2000):
        if (sim.peek('full_dirty') == b'\0' and sim.peek('rebuild_phase') == b'\0'
                and sim.peek('dirty_count') == b'\0'): return
        sim.cmd('call video_background')
    raise AssertionError('Live background did not converge while game state was paused')


def backgrounds(memory, symbols):
    under = symbols['mc_backgrounds']
    codes = [c if c < 147 else memory[under + c - 147] for c in memory[0x1800:0x1a37]]
    patterns = [memory[0x1000 + c * 8:0x1008 + c * 8] for c in codes]
    return codes, patterns


def check_cache(memory, symbols):
    codes, _ = backgrounds(memory, symbols)
    expected = Counter(codes)
    actual = list(memory[symbols['mc_refs_lo']:symbols['mc_refs_lo'] + 147])
    for label in ('mc_overflow0', 'mc_overflow1'):
        owner = memory[symbols[label]]
        if owner != 255: actual[owner] += 256
    assert actual == [expected[i] for i in range(147)], 'Cache reference ownership differs'
    assert sum(actual) == 567
    for code, count in enumerate(actual):
        if not count: continue
        checksum = 0
        for value in reversed(memory[0x1000 + code * 8:0x1008 + code * 8]):
            checksum = ((checksum << 1) | (checksum >> 7)) & 255
            checksum ^= value
        assert checksum == memory[symbols['mc_hashes'] + code], ('cache hash', code)
    assert memory[symbols['mc_cache_errors']] == 0


def generated_array(name):
    source = (BUILD / 'assets.c').read_text()
    body = re.search(name + r'\[[^=]*= \{(.*?)\};', source, re.S)[1]
    return bytes(map(int, re.findall(r'\d+', body)))


def expected_playfield(memory):
    # Forward-stamp logical tiles into a grid. The guest instead gathers each
    # hardware character through the inverse coordinate transform.
    tiles, ids = generated_array('mc_tiles'), generated_array('mc_tile_ids')
    grid = [bytearray(84) for _ in range(216)]
    for offset, code in enumerate(memory[0x400:0x800]):
        xy = position(offset)
        if xy is None or not memory[0x800 + offset] & 31: continue
        x, y = xy
        for dy in range(6):
            row = tiles[ids[code] * 6 + dy]
            for dx in range(3): grid[y * 6 + dy][x * 3 + dx] = row >> (4 - dx * 2) & 3
    return pack_grid(grid)[42:546]


def live_updates():
    sim = Sim(PRG)
    try:
        start_game(sim)
        sim.cmd('until frame_wait 100')
        drain(sim)
        sim.cmd('call video_refresh')
        memory = dump(sim)
        assert backgrounds(memory, sim.labels)[1][42:546] == expected_playfield(memory)
        check_cache(memory, sim.labels)
        pellets = [i for i, code in enumerate(memory[0x400:0x800]) if code == 16][:32]
        pellets += [i for i, code in enumerate(memory[0x400:0x800]) if code in (18, 20)]
        for offset in pellets:
            sim.cmd(f'poke __rc2 {offset & 255}')
            sim.cmd(f'poke __rc3 {4 + (offset >> 8)}')
            sim.cmd('call video_store 64')
            drain(sim)
            sim.cmd('call video_refresh')
            memory = dump(sim)
            assert backgrounds(memory, sim.labels)[1][42:546] == expected_playfield(memory), offset
            check_cache(memory, sim.labels)
        # Blue/white completion changes the global wall source; the next full
        # rebuild must restore blue without changing the white auxiliary ink.
        for parameter, border in ((2, 1), (0, 6), (2, 1)):
            sim.cmd(f'call video_flash_palette {parameter}')
            assert sim.peek(0x900f)[0] & 7 == border
            assert sim.peek(0x900e)[0] >> 4 == 1
        sim.cmd('poke full_dirty 2'); drain(sim)
        assert sim.peek(0x900f)[0] & 7 == 6
        check_cache(dump(sim), sim.labels)
        return {'pellet_and_power_pellet_removals': len(pellets),
                'background_and_reference_checks': len(pellets) + 2,
                'completion_palette_and_next_board_blue': True}
    finally:
        sim.close()


def renderer_scenes():
    sim = Sim(PRG)
    poses = json.loads((BUILD / 'poses.json').read_text())['images']
    packet_path = BUILD / 'test-scene.bin'
    def load(packet):
        packet_path.write_bytes(packet)
        sim.cmd('load actors ' + str(packet_path.relative_to(ROOT)))
    checked, peak = 0, 0
    try:
        start_game(sim); sim.cmd('until frame_wait 100'); drain(sim)
        sim.cmd('call mc_update_hud')
        memory = dump(sim)
        _, background = backgrounds(memory, sim.labels)
        colors = bytearray(memory[0x9400:0x9637]); colors[42:546] = bytes([14]) * 504
        charset = memory[0x1000:0x1498]
        guard = bytes([0xa5]) * 20
        packet_path.write_bytes(guard)
        sim.cmd('load $1d2c ' + str(packet_path.relative_to(ROOT)))
        hidden = bytes((0, 0, 255, 0)) * 6
        def check(packet, incremental=False):
            nonlocal checked, peak
            before = image_state(dump(sim)); load(packet)
            if incremental:
                sim.cmd('call mc_prepare_begin')
                for actor in range(6):
                    sim.cmd('call mc_prepare_step')
                    prepared = dump(sim)
                    assert image_state(prepared) == before, ('hidden slice', actor)
                    assert sim.peek('mc_busy') == bytes((actor < 5,))
                    assert sim.peek('mc_pending') == bytes((actor == 5,))
            else:
                sim.cmd('call mc_prepare'); prepared = dump(sim)
            assert sim.peek('mc_status') == b'\0', ('status', checked)
            assert image_state(prepared) == before, ('hidden preparation', checked)
            assert prepared[0x1000:0x1498] == charset
            peak = max(peak, prepared[sim.labels['mc_new_count']])
            sim.cmd('call mc_commit'); memory = dump(sim)
            assert image_state(memory) == expected_scene(packet, poses, background, colors), ('pixels', checked)
            assert memory[sim.labels['cell_work']:sim.labels['cell_work'] + 567] == bytes([255]) * 567
            assert memory[0x1d2c:0x1d40] == guard
            checked += 1
        replay = (ROOT / 'build/multicolour-motion/replay.bin')
        # Fresh checkouts do not need the earlier recorded-pose prototype.
        recorded = 0
        if replay.exists():
            data = replay.read_bytes()
            for offset in range(0, len(data), 25): check(data[offset:offset + 24]); recorded += 1
        for pose in range(len(poses)):
            for x in range(4):
                for y in range(8): check(bytes((28+x, 80+y, pose, 2)) + hidden[4:])
        for x in (-8,-7,-5,-3,-1,0,79,81,83,84,87):
            for y in (0,11,15,16,194,201,207,208,250): check(bytes((x & 255,y,0,4)) + hidden[4:])
        for pose in range(len(poses)):
            for x in range(4):
                for y in (3,10,15,193,200,207): check(bytes((28+x,y,pose,2)) + hidden[4:])
        rng = random.Random(6502)
        for i in range(180):
            packet = bytearray()
            for _ in range(6):
                x = rng.randrange(28,38) if i & 1 else rng.randrange(-7,87)
                y = rng.randrange(75,88) if i & 1 else rng.randrange(10,207)
                packet.extend((x & 255,y,rng.randrange(len(poses)),rng.randrange(8)))
            check(packet)
        maximum = bytes(v for actor in range(6) for v in (3 + actor * 12,59,0,2 + actor % 6))
        check(maximum)
        # Aborting after any prefix must release every allocated working cell.
        # The VICE test separately checks slices across actual game ticks.
        for count in range(1,7):
            load(maximum); sim.cmd('call mc_prepare_begin')
            before = image_state(dump(sim))
            for _ in range(count): sim.cmd('call mc_prepare_step')
            assert image_state(dump(sim)) == before
            sim.cmd('call mc_abort'); sim.cmd('call mc_commit')
            assert image_state(dump(sim)) == before
            assert sim.peek('cell_work',567) == bytes([255]) * 567
        for pose in range(len(poses)):
            packet = bytes(v for actor in range(6) for v in
                           (3 + actor * 12,59,pose,(2+actor) & 7))
            check(packet, incremental=True)
        assert peak == 54
        before = image_state(dump(sim))
        for column in (18,17,16):
            load(maximum); sim.cmd('call mc_prepare')
            sim.cmd('poke current_band 7'); sim.cmd(f'poke actor_col {column}')
            sim.cmd('call resolve_row')
            assert sim.peek('mc_status') == b'\1'
            sim.cmd('call mc_abort'); sim.cmd('call mc_commit')
            assert image_state(dump(sim)) == before
        check(hidden); check(maximum)
        invalid = bytearray(maximum); invalid[22] = len(poses)
        before = image_state(dump(sim)); load(invalid)
        sim.cmd('call mc_prepare'); sim.cmd('call mc_commit')
        assert sim.peek('mc_status') == b'\1'
        assert image_state(dump(sim)) == before
        check_cache(dump(sim), sim.labels)
        return {'scenes': checked, 'optional_recorded_scenes': recorded, 'poses': len(poses),
                'maximum_work_cells': peak, 'capacity_failure_paths': 3,
                'incremental_scenes': len(poses), 'abort_prefixes': 6,
                'hidden_preparation_and_exact_pixels': True, 'cache_ownership_and_guards': True}
    finally:
        sim.close()


def actor_packets():
    sim = Sim(PRG)
    names = json.loads((BUILD / 'poses.json').read_text())['names']
    lookup = {name: i for i, name in enumerate(names)}
    source_path = BUILD / 'actor-source.bin'
    checks = 0
    def normalized(data):
        return [tuple(data[i:i+4]) if data[i+2] != 255 else (0,0,255,0) for i in range(0,24,4)]
    def check(record, hint=2):
        nonlocal checks
        source_path.write_bytes(bytes(record['attributes'] + record['positions']))
        sim.cmd('load $0c20 ' + str(source_path.relative_to(ROOT)))
        sim.cmd(f'poke facing {hint}')
        # No movement delta overrides the requested closed-mouth hint here.
        pac = next((s for s in range(2,14,2) if record['attributes'][s+1] == 9), 2)
        sim.cmd(f"poke previous_x {record['positions'][pac]}")
        sim.cmd(f"poke previous_y {record['positions'][pac+1]}")
        sim.cmd('call mc_live_actors')
        expected, _ = packet(record, lookup, hint)
        expected = bytearray(expected)
        for i, slot in enumerate((12,10,8,6,4,2)):
            code = record['attributes'][slot] >> 2
            if code in (30,31) and expected[i*4+2] != 255:
                expected[i*4+2] = 27 + (code & 1)
                pal = record['attributes'][slot+1] & 31
                expected[i*4+3] = {1:2,3:4,5:3,7:7,9:7}.get(pal,2)
        assert normalized(sim.peek('actors',24)) == normalized(expected), ('actor packet', checks)
        checks += 1
    try:
        sim.cmd('run 500'); sim.cmd('until frame_wait 100')
        for slot in (2,4,6,8,10,12):
            for axis in (0,1):
                for value in range(256):
                    record = {'attributes': [0]*16, 'positions': [120]*16}
                    record['attributes'][slot:slot+2] = [44*4,9]
                    record['positions'][slot+axis] = value
                    check(record)
            for code in range(28,40):
                for flip in range(4):
                    for pal in (1,3,5,7,25):
                        record = {'attributes': [0]*16, 'positions': [120]*16}
                        record['attributes'][slot:slot+2] = [code*4+flip,pal]
                        check(record)
            for code in (44,45,46,47,48):
                for flip in range(4):
                    record = {'attributes': [0]*16, 'positions': [120]*16}
                    record['attributes'][slot:slot+2] = [code*4+flip,9]
                    check(record)
        source = ROOT / 'build/multicolour-motion/source-poses.json'
        if source.exists():
            records = json.loads(source.read_text())
            for record, hint in zip(records, recorded_pacman_directions(records)):
                check(record, 2 if hint is None else hint)
        return {'packets': checks, 'all_raw_coordinate_bytes': True,
                'all_actor_slots_and_direction_flips': True, 'white_frightened_poses': True}
    finally:
        sim.close()


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LiveParity))
    if not result.wasSuccessful(): raise SystemExit(1)
    report = {'status': 'passed', 'prg_sha256': hashlib.sha256(PRG.read_bytes()).hexdigest(),
              'arcade_parity_and_audio_tests': result.testsRun,
              'live_updates': live_updates(), 'renderer': renderer_scenes(),
              'actor_packets': actor_packets()}
    (BUILD / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
