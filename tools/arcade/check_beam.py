#!/usr/bin/env python3
"""Check real VICE raster positions through complete actor erase/draw groups."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from check_multicolour import breakpoint
from record_shadow import ROOT, launch, verify_loaded_program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prg', type=Path, default=ROOT / 'build/pacman-beam.prg')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/beam-follow/vice/validation')
    args = parser.parse_args()
    prg, out = args.prg.resolve(), args.output.resolve()
    labels = {p[2][1:]: int(p[1], 16) for line in prg.with_suffix('.lbl').read_text().splitlines()
              if len(p := line.split()) == 3}
    vice, mon, log = launch(prg, out)

    def enabled(number, value):
        mon.cmd(0x15, struct.pack('<IB', number, int(value)))

    def registers():
        data = mon.cmd(0x31, b'\0')
        result, offset = {}, 2
        for _ in range(int.from_bytes(data[:2], 'little')):
            result[data[offset+1]] = int.from_bytes(data[offset+2:offset+4], 'little')
            offset += data[offset] + 1
        return result

    try:
        identity = verify_loaded_program(mon, prg, labels)
        # Resolve LIN/CYC identifiers from the emulator rather than hardcoding
        # register IDs which can differ between machine types or VICE versions.
        data = mon.cmd(0x83, b'\0')
        names, offset = {}, 2
        for _ in range(int.from_bytes(data[:2], 'little')):
            names[data[offset+4:offset+4+data[offset+3]].decode()] = data[offset+1]
            offset += data[offset] + 1
        mon.joystick('-')
        raster = breakpoint(mon, 0, 65535, '(RL == $1) && (CY < $8)')
        mon.run_until_stop()
        phase, released = 'boot', 0
        for frame in range(3000):
            memory = mon.memory(0, 4096)
            if phase == 'boot' and memory[0xe00] == 1 and not memory[labels['full_dirty']]:
                mon.joystick('F'); phase = 'coin'
            elif phase == 'coin' and memory[0xe6e]:
                mon.joystick('-'); phase, released = 'release', frame
            elif phase == 'release' and frame - released >= 30:
                mon.joystick('F'); phase = 'start'
            elif phase == 'start' and memory[0xe00] == 3:
                mon.joystick('-'); phase = 'ready'
            elif phase == 'ready' and memory[0xe04] == 3 and not memory[labels['full_dirty']]:
                break
            mon.next_frame(raster)
        else:
            raise AssertionError('No playable scene')
        enabled(raster, False)
        begin = breakpoint(mon, 0, 65535, f"PC == ${labels['beam_group_begin']:x}")
        end = breakpoint(mon, 0, 65535, f"PC == ${labels['beam_group_end']:x}")
        enabled(begin, False); enabled(end, False)
        samples = []
        for _ in range(64):
            enabled(begin, True); mon.run_until_stop(); enabled(begin, False)
            index = mon.memory(labels['beam_group'], 1)[0]
            early, top, bottom, budget = [mon.memory(labels[name]+index, 1)[0]
                                        for name in ('beam_early', 'beam_tops', 'beam_ends', 'beam_budgets')]
            mask = mon.memory(labels['beam_mask'], 1)[0]
            before = registers()
            enabled(end, True); mon.run_until_stop(); enabled(end, False)
            after = registers()
            first, last = before[names['LIN']], after[names['LIN']]
            # NTSC noninterlace numbers 0..261; the first and last lines are
            # partial. Enumerating line numbers avoids an assumed cycle phase.
            elapsed_lines = (last - first) % 262
            scanned = [(first + i) % 262 for i in range(elapsed_lines + 1)]
            if early != 255:
                assert not any(top * 2 <= line < bottom * 2 - 2 for line in scanned), (first, last, top, bottom)
                upper_cycles = elapsed_lines * 65 + after[names['CYC']] - before[names['CYC']]
                assert upper_cycles <= budget * 130, (upper_cycles, budget)
            sample = {'mask': mask, 'early': early, 'top': top, 'end': bottom,
                            'budget': budget, 'start_line': first, 'end_line': last,
                            'start_cycle': before[names['CYC']], 'end_cycle': after[names['CYC']]}
            if 'beam_player' in labels:
                player = mon.memory(labels['beam_player'], 1)[0]
                focus_group = mon.memory(labels['beam_focus_group'], 1)[0]
                sample.update(player_mask=player,
                              focus_mask=mon.memory(labels['beam_focus'], 1)[0],
                              player_group=bool(mask & player))
                # Before the player retires, no other group may be processed.
                assert focus_group == 255 or index == focus_group
            samples.append(sample)
        protected = [s for s in samples if s['early'] != 255]
        if 'beam_player' in labels:
            assert any(s['player_group'] for s in protected), 'No protected Pac-Man group'
        else:
            assert len(protected) >= 32
            assert all(any(s['mask'] & (1 << ghost) for s in protected) for ghost in range(4))
        mon.screenshot(out / 'live-game.png')
        report = {'prg_sha256': hashlib.sha256(prg.read_bytes()).hexdigest(),
                  'loaded_program': identity,
                  'groups_checked': len(samples), 'protected_groups_checked': len(protected),
                  'protected_player_groups_checked': sum(s.get('player_group', False) for s in protected),
                  'all_four_ghost_slots_observed': all(any(s['mask'] & (1 << ghost) for s in protected) for ghost in range(4)),
                  'no_protected_group_crossed_its_colour_rows': True,
                  'all_protected_groups_within_budget': True,
                  'guest_patches': False, 'samples': samples}
        (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({k:v for k,v in report.items() if k != 'samples'}, indent=2))
    finally:
        if vice.poll() is None: vice.terminate(); vice.wait(timeout=10)
        mon.s.close(); log.close()


if __name__ == '__main__':
    main()
