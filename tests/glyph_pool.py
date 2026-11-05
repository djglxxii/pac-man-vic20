#!/usr/bin/env python3
"""Run existing independent scene/logic oracles against the pooled display.

Only host fixture addresses and host bitmap readback are adapted. Guest code
runs normally; raw snapshots remain available for pool-specific invariants.
"""
import unittest
import native
import render
import colors
import flash
import rebuild
import ghosts
import memory
import fonts
from native import ROOT, WORK, DEFAULT_PRG

PRG = DEFAULT_PRG
NativeSim = native.Sim


def displayed_bitmap(data):
    result = bytearray(3136)
    for row in range(14):
        for col in range(14):
            code = data[0x200 + row * 14 + col]
            source = 0x1000 + code * 16
            target = col * 224 + row * 16
            result[target:target + 16] = data[source:source + 16]
    return result


class PoolSim(NativeSim):
    def __init__(self, prg=None):
        super().__init__(prg or PRG)
        self.fixture_colour_tail = bytes(60)

    def cmd(self, command):
        parts = command.split()
        # The pooled renderer has no erase kernel; the existing background
        # oracle's obsolete watch can observe no erasures.
        if parts[:2] == ['watch', 'bitmap_erase']:
            return []
        if len(parts) == 3 and parts[0] == 'load' and parts[1] == '$1c40':
            from pathlib import Path
            io = Path(parts[2]).read_bytes()
            path = WORK / 'pio.bin'
            path.write_bytes(io[:8])
            super().cmd(f'load $0300 {path}')
            path.write_bytes(io[0x40:0x80])
            return super().cmd(f'load $0340 {path}')
        if len(parts) == 3 and parts[:2] == ['load', '$1c80']:
            return super().cmd('load $0340 ' + parts[2])
        if len(parts) == 3 and parts[:2] == ['poke', '$1c41']:
            return super().cmd('poke $0301 ' + parts[2])
        if len(parts) == 3 and parts[:2] == ['load', '$9600']:
            from pathlib import Path
            colours = Path(parts[2]).read_bytes()
            self.fixture_colour_tail = colours[196:256].ljust(60, b'\0')
            path = WORK / 'pc.bin'
            path.write_bytes(colours[:196])
            result = super().cmd(f'load $9600 {path}')
            super().cmd(f'load $9400 {path}')
            return result
        result = super().cmd(command)
        return result

    def raw_dump(self):
        return super().dump()

    def dump(self):
        data = bytearray(self.raw_dump())
        data[0x1000:0x1c40] = displayed_bitmap(data)
        data[0x1c80:0x1ca0] = data[0x0340:0x0360]
        data[0x96c4:0x9700] = self.fixture_colour_tail
        return data


class PoolNativeParity(native.NativeParity):
    def test_03_build_memory_limits(self):
        labels = self.sim.labels
        self.assertLessEqual(labels['__bss_end'], 0x7d40)
        self.assertEqual(labels['__stack'] - labels['__stack_bottom'], 704)
        self.assertEqual(labels['__pool_base'], 0x1c40)
        self.assertEqual(labels['__pool_capacity'], 60)
        self.assertEqual(len(self.sim.native_binary.read_bytes()), 33792)


class PoolRenderer(render.Renderer):
    # These two tests explicitly exercise the removed underlay kernels.
    test_04_preshifted_ghost_path = None
    test_06_clipped_kernel_memory_boundaries = None

    def test_09_clean_home_glyphs_and_bounded_banks(self):
        actors = [[32, 0, p, 175 - i*8, 158 + i*12]
                  for i, p in enumerate((1, 3, 5, 7, 9, 25))]
        for frame in range(40):
            for actor in actors:
                actor[3] = (actor[3] - 2) & 255
            self.check_scene(actors, retain=True)
            data = self.sim.raw_dump()
            self.assertEqual(data[0x1000:0x1c40], self.background)
            bank = data[self.sim.labels['pool_bank']]
            counts = data[self.sim.labels['pool_count']:self.sim.labels['pool_count']+2]
            self.assertLessEqual(max(counts), 24)
            self.assertEqual(data[self.sim.labels['pool_failed']], 0)
            codes = [c for c in data[0x200:0x2c4] if c >= 196]
            self.assertEqual(len(codes), counts[bank])
            self.assertTrue(all(196+24*bank <= c < 196+24*(bank+1) for c in codes))
            self.assertEqual(len(set(codes)), len(codes))
        self.sim.cmd('call video_restore')

    def test_10_full_banks_teleports_and_epoch_wrap(self):
        # Six disjoint 2x2 footprints require the full 24 entries. Alternate
        # distant positions over several lookup-generation wraps, with no
        # game-loop delays between transactions.
        previous_cells = set()
        for frame in range(24):
            actors = []
            for i, (off, pal) in enumerate(zip(range(12, 0, -2), (1, 3, 5, 7, 9, 25))):
                x = 1 + i*16
                y = (15 + i*32 + (48 if frame & 1 else 0)) % 192
                raw_y = next(raw for raw in range(256) if (272-raw)*3//4 == y)
                actors.append([32+(frame & 1), frame % 4, pal,
                               239-(off <= 4)-2*x, raw_y])
            self.check_scene(actors, retain=True)
            data = self.sim.raw_dump()
            bank = data[self.sim.labels['pool_bank']]
            self.assertEqual(data[self.sim.labels['pool_count']+bank], 24)
            cells = {i for i, code in enumerate(data[0x200:0x2c4]) if code >= 196}
            self.assertEqual(len(cells), 24)
            if previous_cells:
                self.assertEqual(len(cells | previous_cells), 48)
            previous_cells = cells
            self.assertEqual(data[0x1000:0x1c40], self.background)
            self.assertEqual(data[self.sim.labels['pool_failed']], 0)
        self.sim.cmd('call video_restore')

    def test_11_all_home_addresses_overlap_hits_and_cursor_page_carries(self):
        # Direct allocator checks complement full scene oracles: every home
        # glyph, both banks, slot/page boundaries, and reuse without advancing
        # the sequential destination cursor. No matrix publication is needed.
        sim = self.sim
        for cell in range(196):
            if cell % 24 == 0:
                sim.cmd('call video_update_begin')
            bank = sim.peek('pool_bank')[0]
            before = sim.peek(sim.labels['pool_count'] + bank)[0]
            sim.cmd('poke v_color 3')
            sim.cmd(f'call pool_cell {cell}')
            address = int.from_bytes(sim.peek('v_base', 2), 'little')
            self.assertEqual(address, 0x1c40 + (bank * 24 + before) * 16)
            row, col = divmod(cell, 14)
            self.assertEqual(sim.peek(address, 16),
                             self.background[col*224+row*16:col*224+row*16+16])
            count = sim.peek(sim.labels['pool_count'] + bank)
            self.assertEqual(count, bytes([before + 1]))
            sim.cmd(f'call pool_cell {cell}')
            self.assertEqual(int.from_bytes(sim.peek('v_base', 2), 'little'), address)
            self.assertEqual(sim.peek(sim.labels['pool_count'] + bank), count)
            self.assertEqual(sim.peek('pool_failed'), b'\0')
        # Leave the fixture with empty banks; these calls deliberately did not
        # publish the temporary allocations into the matrix.
        for i in range(2):
            sim.cmd(f"poke ${sim.labels['pool_count']+i:x} 0")

    def test_12_packed_home_decode_all_bytes_and_incoming_carries(self):
        sim = self.sim
        if 'pool_unpack_home' not in sim.labels:
            self.skipTest('Accepted baseline uses unpacked home codes')
        # Exercise the actual built eight-byte arithmetic fragment, copied to
        # unused $0308-$0312 for a temporary callable stub. The expected result
        # comes from nibble exchange, independent of the instruction sequence.
        original = sim.peek(0x0308, 11)
        body = sim.peek('pool_unpack_home', 8)
        from pathlib import Path
        path = WORK / 'pd.bin'
        try:
            for carry in (0x18, 0x38):  # CLC / SEC; CLD makes binary mode explicit.
                path.write_bytes(bytes((0xd8, carry)) + body + b'\x60')
                sim.cmd(f'load $0308 {path}')
                for value in range(256):
                    line = sim.cmd(f'call $0308 {value}')[-1]
                    self.assertEqual(int(line.split()[1], 16),
                                     ((value << 4) | (value >> 4)) & 255)
        finally:
            path.write_bytes(original)
            sim.cmd(f'load $0308 {path}')

    def test_13_full_bank_hits_and_overflow_preserve_existing_cells(self):
        # A full bank must still accept overlap hits. A new 25th cell must
        # return the clipping sink without advancing the count or altering
        # any previously prepared glyph, lookup entry, list or colour.
        sim = self.sim
        path = WORK / 'pf.bin'
        for bank in (0, 1):
            path.write_bytes(bytes(196))
            sim.cmd(f'load $96c4 {path}')
            sim.cmd('poke pool_epoch 0')
            sim.cmd(f'poke pool_bank {bank ^ 1}')
            sim.cmd('call video_update_begin')
            for cell in range(24):
                sim.cmd(f'poke v_color {cell % 7 + 1}\ncall pool_cell {cell}')
            for cell in reversed(range(24)):
                colour = (cell + 3) % 7 + 1
                sim.cmd(f'poke v_color {colour}\ncall pool_cell {cell}')
                self.assertEqual(int.from_bytes(sim.peek('v_base', 2), 'little'),
                                 0x1c40 + (bank * 24 + cell) * 16)
                self.assertEqual(sim.peek(sim.labels['pool_colours'] + bank * 24 + cell),
                                 bytes([colour]))
            self.assertEqual(sim.peek(sim.labels['pool_count'] + bank), b'\x18')
            self.assertEqual(sim.peek('pool_failed'), b'\0')
            regions = ((0x200, 196), (0x1000, 4096), (0x94c4, 196),
                       (0x96c4, 196), (sim.labels['pool_cells'], 48),
                       (sim.labels['pool_colours'], 48), (sim.labels['pool_count'], 2))
            before = [sim.peek(a, n) for a, n in regions]
            sim.cmd('call pool_cell 24')
            self.assertEqual(sim.peek('v_base', 2), b'\xf0\x1f')
            self.assertEqual(sim.peek('pool_failed'), b'\1')
            self.assertEqual([sim.peek(a, n) for a, n in regions], before)
        # These direct calls deliberately did not publish the temporary bank.
        for bank in (0, 1):
            sim.cmd(f"poke ${sim.labels['pool_count'] + bank:x} 0")


class PoolColors(colors.Colors):
    pass


class PoolFlash(flash.MazeFlash):
    pass


class PoolRebuild(rebuild.Rebuild):
    pass


class PoolGhosts(ghosts.GhostParity):
    pass


class PoolMemory(memory.Memory):
    # These physical loader/stack checks use raw Sim, without bitmap readback.
    pass


class PoolFonts(fonts.FontMessages):
    pass


if __name__ == '__main__':
    native.Sim = render.Sim = colors.Sim = flash.Sim = rebuild.Sim = PoolSim
    ghosts.Sim = fonts.Sim = PoolSim
    unittest.main(verbosity=2)
