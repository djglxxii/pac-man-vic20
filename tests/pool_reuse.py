#!/usr/bin/env python3
"""Check the offline opportunity counter against misleading reuse cases."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools/arcade'))
from pool_reuse import actor_footprints, compare_cells, displayed, home, pending

SYM = dict(pool_bank=0x322, pool_count=0x323, pool_failed=0x321,
           pool_cells=0x380, pool_colours=0x3b0,
           cache_x=0xf80, cache_y=0xf8e, cache_attr=0xf9c, cache_pal=0xfaa)
TABLES = dict(arcade_sprite_class=[0]*16, arcade_colors=[1]*128)


def memory():
    data = bytearray(8192+196)
    for cell in range(196):
        data[0x200+cell] = (cell % 14)*14+cell//14
    return data


def put_actor(data, slot, x, y, attr=0, pal=9):
    for name, value in (('cache_x', x & 255), ('cache_y', y),
                        ('cache_attr', attr), ('cache_pal', pal)):
        data[SYM[name]+slot] = value


def entry(slot=0, bits=b'\x80'*16, colour=2, pose=(10, 8, 16, 0, 9), bg=b'\x00'*16):
    return dict(slot=slot, code=196+slot, value=(bits, colour),
                key=(bg, (pose,), colour))


def compare(now, old, hidden=None):
    current = dict(cells={0: now}, actors=[dict(cells=[0])])
    previous = dict(cells={0: old})
    bank = dict(cells={0: hidden}) if hidden else None
    data = memory()
    data[0x1000+now['code']*16:0x1010+now['code']*16] = old['value'][0]
    return compare_cells(current, previous, bank, data, [old['value']])


class ReuseOpportunities(unittest.TestCase):
    def test_home_and_display_use_distinct_code_orders(self):
        data = memory()
        data[0x1000+73*16] = 0x80
        data[0x200+47] = 196
        data[0x1c40] = 0xc0
        data[8192+47] = 3
        self.assertEqual(home(data, 47), b'\x80'+bytes(15))
        self.assertEqual(displayed(data)[47], (b'\xc0'+bytes(15), 3))

    def test_animation_and_palette_invalidate_held_position(self):
        old = entry()
        animated = entry(bits=b'\xc0'*16, pose=(10, 8, 16, 4, 9))
        self.assertEqual(compare(animated, old)['same_previous_pixels_and_colour'], 0)
        self.assertEqual(compare(animated, old)['same_previous_dependencies'], 0)
        recoloured = entry(colour=3, pose=(10, 8, 16, 0, 10))
        result = compare(recoloured, old)
        self.assertEqual(result['same_previous_pixels'], 1)
        self.assertEqual(result['same_previous_pixels_and_colour'], 0)

    def test_equivalent_masks_are_output_hits_but_not_dependency_hits(self):
        old = entry()
        equivalent = entry(pose=(10, 8, 16, 4, 9))
        result = compare(equivalent, old)
        self.assertEqual(result['same_previous_pixels_and_colour'], 1)
        self.assertEqual(result['same_previous_dependencies'], 0)

    def test_background_and_sharing_invalidate_even_if_or_result_is_equal(self):
        old = entry()
        changed = entry(bg=b'\x80'+bytes(15))
        result = compare(changed, old, old)
        self.assertEqual(result['same_previous_pixels_and_colour'], 1)
        self.assertEqual(result['same_previous_dependencies'], 0)
        self.assertEqual(result['hidden_same_slot_cell_dependencies'], 0)
        shared = entry()
        shared['key'] = (bytes(16), old['key'][1]+((2, 8, 16, 0, 1),), 2)
        self.assertEqual(compare(shared, old)['same_previous_dependencies'], 0)

    def test_dependency_hit_requires_exact_output(self):
        with self.assertRaisesRegex(AssertionError, 'False dependency hit'):
            compare(entry(bits=b'\xc0'*16), entry())
        old = entry(pose=(2, 8, 16, 4, 1))
        with self.assertRaisesRegex(AssertionError, 'False hidden-bank'):
            compare(entry(bits=b'\xc0'*16), old, entry())

    def test_hidden_reuse_must_have_the_same_physical_slot(self):
        old = entry()
        moved_slot = entry(slot=1)
        result = compare(old, old, moved_slot)
        self.assertEqual(result['hidden_same_cell_pixels_any_slot'], 1)
        self.assertEqual(result['hidden_same_slot_cell_pixels'], 0)
        self.assertEqual(result['whole_actor_stamps_with_all_cells_reusable'], 0)
        result = compare(old, old, old)
        self.assertEqual(result['hidden_same_slot_cell_dependencies'], 1)
        self.assertEqual(result['whole_actor_stamps_with_all_cells_reusable'], 1)

    def test_footprints_cover_alignment_vertical_boundary_and_clipping(self):
        for x, y, expected in ((8, 20, [15]), (9, 20, [15, 16]),
                                (9, 21, [15, 29, 16, 30]),
                                (-1, 21, [14, 28]), (111, 21, [27, 41])):
            with self.subTest(x=x, y=y):
                data = memory()
                put_actor(data, 10, x, y)
                self.assertEqual(actor_footprints(data, SYM, TABLES)[0]['cells'], expected)

    def test_shared_cells_follow_allocation_order_and_last_colour(self):
        data = memory()
        tables = dict(TABLES, arcade_colors=list(TABLES['arcade_colors']))
        tables['arcade_colors'][9*4] = 7
        tables['arcade_colors'][1*4] = 2
        put_actor(data, 10, 8, 16, pal=9)
        put_actor(data, 2, 8, 16, pal=1)
        data[SYM['pool_count']] = 1
        data[SYM['pool_cells']] = 15
        data[SYM['pool_colours']] = 2
        result = pending(data, SYM, tables)
        self.assertEqual(result['cells'][15]['value'][1], 2)
        self.assertEqual([p[0] for p in result['cells'][15]['key'][1]], [10, 2])
        data[SYM['pool_cells']] = 16
        with self.assertRaisesRegex(AssertionError, 'allocation footprint mismatch'):
            pending(data, SYM, tables)

    def test_hidden_outside_and_black_actors_do_not_allocate(self):
        data = memory()
        put_actor(data, 12, 8, 16, pal=0)
        put_actor(data, 10, 112, 16)
        put_actor(data, 8, 8, 16, pal=2)
        tables = dict(TABLES, arcade_colors=list(TABLES['arcade_colors']))
        tables['arcade_colors'][2*4] = 0
        self.assertEqual(actor_footprints(data, SYM, tables), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
