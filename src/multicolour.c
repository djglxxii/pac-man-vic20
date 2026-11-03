/* Live display adapter. Game RAM and the arcade clock remain authoritative. */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "arcade/memmap.h"
#include "video.h"
#include "assets.h"

#define HW(a) (*(volatile uint8_t *)(a))
#define CHARSET ((uint8_t *)0x1000)
#define MATRIX ((uint8_t *)0x1800)
#define COLORS ((uint8_t *)0x9400)
#define CELLS 567
#define BACKGROUNDS 147

uint8_t dirty_bits[128] __attribute__((section(".video_bits")));
uint8_t physical_dirty[71] __attribute__((section(".video_bits")));
uint8_t dirty_count __attribute__((section(".zp.bss")));
uint8_t full_dirty __attribute__((section(".zp.bss")));
uint8_t rebuild_phase __attribute__((section(".screen_work")));
uint16_t rebuild_cursor __attribute__((section(".screen_work")));
uint8_t rebuild_again __attribute__((section(".screen_work")));
extern uint8_t bulk_active;
extern uint8_t mc_refs_lo[147];
extern uint8_t mc_backgrounds[108], cell_work[CELLS], actors[24], mc_status;
extern const uint8_t bit_masks[8];
static uint8_t hud_codes[63] __attribute__((section(".work")));
uint8_t mc_pattern[8] __attribute__((section(".work")));
extern uint8_t previous_x, previous_y, facing;
uint8_t mc_cache_errors __attribute__((used, section(".mc_state")));
uint16_t mc_frames __attribute__((section(".mc_state")));
__attribute__((leaf)) void mc_init(void), mc_prepare(void), mc_commit(void);

__attribute__((section(".boot.text"))) void video_init(void) {
    extern uint8_t __mc_low_load[], __mc_low_size[];
    extern uint8_t __mc_shift_load[], __mc_shift_size[];
    memcpy((void *)0x0200, __mc_low_load, (uint16_t)__mc_low_size);
    memcpy((void *)0x1d40, __mc_shift_load, (uint16_t)__mc_shift_size);
    memset(CHARSET, 0, 2048);
    memset(MATRIX, 0, CELLS);
    memset(COLORS, 14, CELLS);
    memset((void *)0x1a37, 0, 521);
    memset(mc_refs_lo, 0, 147);
    memset(mc_backgrounds, 0, 108);
    memset(cell_work, 255, CELLS);
    memset(hud_codes, 255, sizeof hud_codes);
    mc_refs_lo[0] = CELLS & 255;
    mc_cache_errors = mc_frames = 0;
    previous_x = previous_y = facing = 0;
    dirty_count = rebuild_phase = rebuild_again = bulk_active = bulk_drain = 0;
    full_dirty = 2;
    mc_init();
    HW(0x9002) = 21;
}

void video_fill(uint8_t *p, uint8_t value, uint16_t count) {
    memset(p, value, count);
    full_dirty = 2;
    dirty_count = 0;
}

/* A scene replacement releases the previous picture before building the new
   one. Keeping both scenes' glyphs live can exhaust the 147-slot cache. */
void mc_reset_background(void) {
    extern uint8_t mc_old_count, mc_new_count, mc_pending;
    extern uint8_t mc_overflow0, mc_overflow1, mc_hashes[147];
    memset(MATRIX, 0, CELLS);
    memset(COLORS, 14, CELLS);
    memset(CHARSET, 0, 8);
    memset(mc_refs_lo, 0, 147);
    memset(hud_codes, 255, sizeof hud_codes);
    mc_refs_lo[0] = CELLS & 255;
    mc_overflow0 = mc_overflow1 = mc_hashes[0] = 0;
    mc_old_count = mc_new_count = mc_pending = 0;
}

/* Screen codes and actor underlays own the background references. Only
   unreferenced permanent character slots can be overwritten. */
__attribute__((leaf)) void mc_replace_cell(uint16_t cell);
extern uint8_t v_flags;
static void replace_cell(uint16_t cell, uint8_t color) {
    v_flags = color;
    mc_replace_cell(cell);
}

__attribute__((leaf)) uint8_t hud_glyph(uint8_t cell);

void mc_update_hud(void) {
    /* The label row is constant until the next scene reset. */
    for (uint8_t i = hud_codes[0] == 255 ? 0 : 21; i < 63; i++) {
        uint8_t code = hud_glyph(i);
        if (hud_codes[i] == code) continue;
        hud_codes[i] = code;
        memcpy(mc_pattern, mc_font + (uint16_t)(code & 31) * 8, 8);
        replace_cell(i < 42 ? i : 546 + i - 42, code >> 5 ? code >> 5 : 1);
    }
}
