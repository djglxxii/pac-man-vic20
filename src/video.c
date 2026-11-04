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
uint8_t dirty_bits[128] __attribute__((section(".video_bits")));
uint16_t dirty_queue[20] __attribute__((section(".screen_work")));
uint8_t rebuild_phase __attribute__((section(".screen_work")));
uint16_t rebuild_cursor __attribute__((section(".screen_work")));
uint8_t rebuild_again __attribute__((section(".screen_work")));
uint8_t dirty_count __attribute__((section(".zp.bss")));
uint8_t full_dirty __attribute__((section(".zp.bss")));
uint8_t maze_flash __attribute__((section(".maze_cells")));
extern uint8_t maze_cells[25];
extern uint8_t bulk_active;
extern uint8_t under[216];
extern uint8_t *v_addr, *v_save;
extern const uint8_t *v_data;
extern uint8_t v_flags, v_shift, v_flip;
void bitmap_erase(void), bitmap_draw(void);
__attribute__((section(".boot.text"))) void video_init(void) {
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
    rebuild_phase = 0;
    bulk_active = 0;
    bulk_drain = 0;
#ifdef ACTOR_COMMIT_OVERLAY
    extern uint8_t __actor_code_load[], __actor_code_size[], __actor_code_start[];
    memcpy(__actor_code_start, __actor_code_load, (uint16_t)__actor_code_size);
#endif
#ifdef BEAM_FOLLOW
    extern uint8_t __beam_code_load[], __beam_code_size[], __beam_code_start[];
    extern void beam_init(void);
    memcpy(__beam_code_start, __beam_code_load, (uint16_t)__beam_code_size);
    beam_init();
#endif
}
__attribute__((noinline)) void video_fill(uint8_t *p, uint8_t value, uint16_t count) {
    memset(p, value, count);
    full_dirty = 2;
    dirty_count = 0;
}
