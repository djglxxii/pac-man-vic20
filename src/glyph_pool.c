/* Whole-frame pool transaction. Six 8x12 slots occupy at most 24 cells.
   Two disjoint banks of 24 retain displayed and pending compositions. The
   final twelve glyphs are unused, except code 255 as a clipped-column sink.
   No dynamic allocation, deferral or logical-clock change is required. */
#include <stdint.h>
#include <string.h>
#define MATRIX ((uint8_t *)0x0200)
#define HOME_COLOURS ((uint8_t *)0x9400)
#define LIVE_COLOURS ((uint8_t *)0x9600)
uint8_t pool_cells[48] __attribute__((section(".pool_lists")));
uint8_t pool_colours[48] __attribute__((section(".pool_lists")));
uint8_t pool_count[2] __attribute__((section(".pool_state")));
uint8_t pool_bank __attribute__((section(".pool_state")));
uint8_t pool_epoch __attribute__((section(".pool_state")));
uint8_t pool_failed __attribute__((section(".pool_state")));
extern uint8_t v_cell, v_color, v_flags, v_shift, v_sy;
extern uint8_t *v_addr, *v_right, *v_save, *v_saved_right;
extern uint8_t full_dirty, rebuild_phase, maze_flash;
void pool_actors(void), pool_reuse_guard(void), bitmap_maze_flash(void);
void video_background(void);

__attribute__((section(".boot.text"))) void pool_init(void) {
    pool_count[0] = pool_count[1] = pool_bank = pool_failed = pool_epoch = 0;
    memset((void *)0x96c4, 0, 196);
}

const uint8_t home_codes[196] = {
    0,14,28,42,56,70,84,98,112,126,140,154,168,182,
    1,15,29,43,57,71,85,99,113,127,141,155,169,183,
    2,16,30,44,58,72,86,100,114,128,142,156,170,184,
    3,17,31,45,59,73,87,101,115,129,143,157,171,185,
    4,18,32,46,60,74,88,102,116,130,144,158,172,186,
    5,19,33,47,61,75,89,103,117,131,145,159,173,187,
    6,20,34,48,62,76,90,104,118,132,146,160,174,188,
    7,21,35,49,63,77,91,105,119,133,147,161,175,189,
    8,22,36,50,64,78,92,106,120,134,148,162,176,190,
    9,23,37,51,65,79,93,107,121,135,149,163,177,191,
    10,24,38,52,66,80,94,108,122,136,150,164,178,192,
    11,25,39,53,67,81,95,109,123,137,151,165,179,193,
    12,26,40,54,68,82,96,110,124,138,152,166,180,194,
    13,27,41,55,69,83,97,111,125,139,153,167,181,195
};
#define home_code(cell) home_codes[cell]

/* Assembly owns bounded allocation, copying, stamping and publication. */
void video_restore(void), video_update_begin(void), video_update_end(void);
void video_sprites(void);
uint8_t pool_start __attribute__((section(".pool_state")));
uint8_t pool_limit __attribute__((section(".pool_state")));
uint8_t pool_code_base __attribute__((section(".pool_state")));
uint8_t pool_code_end __attribute__((section(".pool_state")));
/* Separate entry/exit symbols preserve host-only capture/profile hooks. */
__attribute__((noinline)) void video_frame_end(void) { __asm__ volatile(""); }
__attribute__((noinline)) void video_frame_begin(void) {
    video_sprites();
    video_frame_end();
}
void video_refresh(void) {
    if (full_dirty) video_restore();
    video_background();
    if (full_dirty) return;
    video_frame_begin();
}
