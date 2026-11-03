#!/usr/bin/env python3
"""Verify hidden original-hires pixels and their real VIC character fetches."""
import hashlib
import json
import struct

from PIL import Image
from check_multicolour import breakpoint
from record_shadow import ROOT, launch


def main():
    prg = ROOT / 'build/pacman-shadow.prg'
    out = ROOT / 'build/ghost-shadow/vice/validation'
    labels = {p[2][1:]: int(p[1], 16) for line in prg.with_suffix('.lbl').read_text().splitlines()
              if len(p := line.split()) == 3}
    vice, mon, log = launch(prg, out)

    def enabled(number, value):
        mon.cmd(0x15, struct.pack('<IB', number, int(value)))

    def snapshot():
        return mon.memory(0x200, 196), mon.memory(0x1000, 4096), mon.memory(0x9600, 196)

    def displayed(state):
        codes, glyphs, _ = state
        return b''.join(glyphs[c*16:c*16+16] for c in codes)

    try:
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
            elif phase == 'ready' and memory[0xe04] == 3:
                break
            mon.next_frame(raster)
        else:
            raise AssertionError('No playable scene')
        enabled(raster, False)
        stops = [breakpoint(mon, 0, 65535, f'PC == ${labels[name]:x}')
                 for name in ('video_update_begin', 'restore_done', 'video_frame_end')]
        for number in stops: enabled(number, False)
        protected = 0
        fixed = bytes(col * 14 + row for row in range(14) for col in range(14))
        for scene in range(32):
            enabled(stops[0], True); mon.run_until_stop(); enabled(stops[0], False)
            before = snapshot()
            enabled(stops[1], True); mon.run_until_stop(); enabled(stops[1], False)
            hidden = snapshot()
            count = mon.memory(labels['shadow_count'], 1)[0]
            assert 0 <= count <= 24
            assert displayed(before) == displayed(hidden), ('old pixels erased', scene)
            protected += count
            if scene == 31:
                # Freeze only this verification process, after erasing the work
                # bitmap. The separately recorded gameplay has no guest patches.
                address = labels['restore_done']
                mon.store(address, bytes((0x4c, address & 255, address >> 8)))
                break
            enabled(stops[2], True); mon.run_until_stop(); enabled(stops[2], False)
            assert mon.memory(0x200, 196) == fixed
            assert mon.memory(labels['shadow_count'], 1) == b'\0'
        assert protected > 0 and count > 0
        enabled(raster, True)
        mon.run_until_stop()
        for _ in range(3): mon.next_frame(raster)
        palette = mon.palette()
        rgb = [tuple(palette[i:i+3]) for i in range(0, 48, 3)]
        expected = Image.new('RGB', (112, 224))
        codes, glyphs, colors = hidden
        for cell, code in enumerate(codes):
            row, column = divmod(cell, 14)
            for y, bits in enumerate(glyphs[code*16:code*16+16]):
                for x in range(8):
                    expected.putpixel((column*8+x, row*16+y), rgb[colors[cell] & 7] if bits & (128 >> x) else rgb[0])
        expected = expected.resize((224, 224), Image.Resampling.NEAREST)
        # The recorder's original-mode crop includes four native dots of border.
        actual = mon.picture(palette).crop((8, 4, 232, 228))
        assert actual.tobytes() == expected.tobytes(), 'VIC did not fetch the copied glyph pixels'
        actual.resize((672, 896), Image.Resampling.NEAREST).save(out / 'hidden-pixels.png')
        report = {'prg_sha256': hashlib.sha256(prg.read_bytes()).hexdigest(),
                  'live_restore_checks': 32, 'protected_cells': protected,
                  'old_character_bits_preserved': True,
                  'published_matrix_restored_checks': 31,
                  'all_50176_native_monitor_pixels_match': True,
                  'validation_scene_frozen_only_for_pixel_comparison': True,
                  'colours_update_live': True}
        (out / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    finally:
        if vice.poll() is None: vice.terminate(); vice.wait(timeout=10)
        mon.s.close(); log.close()


if __name__ == '__main__':
    main()
