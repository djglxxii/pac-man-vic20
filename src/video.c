#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "arcade/memmap.h"
#include "video.h"
#include "rom.h"
#define BITMAP ((uint8_t *)0x1000)
#define COLORS ((uint8_t *)0x9600)
#define COLS 14
#define ACTORS 6
/* Keep the infrequent dirty-tile bitset out of the CPU's scarce zero page. */
static uint8_t dirty_bits[128] __attribute__((section(".video_bits")));
static uint16_t dirty_queue[20] __attribute__((section(".screen_work")));
uint8_t dirty_count, full_dirty;
uint8_t maze_flash __attribute__((section(".maze_cells")));
extern uint8_t maze_cells[25];
extern uint8_t under[216];
extern uint8_t *v_addr, *v_save;
extern const uint8_t *v_data;
extern uint8_t v_flags, v_shift, v_flip;
void bitmap_erase(void), bitmap_draw(void);
uint8_t bit_masks[8] = {1, 2, 4, 8, 16, 32, 64, 128};
void video_init(void) {
    memset(BITMAP, 0, 0xc40);
    memset(COLORS, 0, 196);
    for (uint8_t c = 0; c < 14; c++)
        for (uint8_t r = 0; r < 14; r++)
            ((uint8_t *)0x200)[r * 14 + c] = c * 14 + r;
    memset(under, 0, sizeof under);
    memset(dirty_bits, 0, sizeof dirty_bits);
    maze_flash = 0;
    full_dirty = 2;
    dirty_count = 0;
}
void video_store(uint8_t *p, uint8_t value) {
    if (*p == value)
        return;
    *p = value;
    uint16_t a = (uint16_t)p;
    if (a < 0x400 || a >= 0xc00 || full_dirty == 2)
        return;
    uint16_t i = a & 0x3ff;
    uint8_t mask = bit_masks[i & 7];
    if (dirty_bits[i >> 3] & mask)
        return;
    dirty_bits[i >> 3] |= mask;
    if (full_dirty == 1)
        return;
    if (dirty_count == 20) {
        full_dirty = 1;
        dirty_count = 0;
        return;
    }
    dirty_queue[dirty_count++] = i;
}
__attribute__((noinline)) void video_fill(uint8_t *p, uint8_t value, uint16_t count) {
    memset(p, value, count);
    full_dirty = 2;
    dirty_count = 0;
}
void bitmap_tile(void);
static void tile(uint16_t i) {
    v_save = (uint8_t *)i;
    bitmap_tile();
}
static __attribute__((noinline)) void video_rebuild(void) {
    if (full_dirty == 2) {
        memset(BITMAP, 0, 0xc40);
        memset(COLORS, 0, 196);
        memset(maze_cells, 0, 25);
        for (uint16_t i = 0; i < 1024; i++) {
            uint8_t t = SCREEN[i];
            if ((COLOUR[i] & 31) && t != 0x40 && t != 0xfc && t != 0xfd)
                tile(i);
        }
    } else {
        for (uint16_t i = 0; i < 1024; i++)
            if (dirty_bits[i >> 3] & bit_masks[i & 7])
                tile(i);
    }
    memset(dirty_bits, 0, sizeof dirty_bits);
    full_dirty = 0;
    dirty_count = 0;
}
void video_background(void) {
    if (full_dirty) {
        video_rebuild();
    } else {
        for (uint8_t q = 0; q < dirty_count; q++) {
            uint16_t i = dirty_queue[q];
            tile(i);
            dirty_bits[i >> 3] &= ~bit_masks[i & 7];
        }
        dirty_count = 0;
    }
}
