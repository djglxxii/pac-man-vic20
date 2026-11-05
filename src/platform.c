#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "arcade/memmap.h"
#define HW(a) (*(volatile uint8_t *)(a))
static uint8_t last_fire, fire_action;
void controls(void) {
    uint8_t joy = HW(0x9111), right = HW(0x9120);
    input0 = 0xf0 | (joy & 8) | ((joy & 4) >> 2) | ((joy & 16) >> 3) | ((right & 128) >> 5);
    input1 = 255;
    uint8_t fire = !(joy & 32);
    if (fire && !last_fire)
        fire_action = (!CREDITS || !(joy & 8)) ? 1 : !(joy & 4) ? 3 : 2;
    if (fire) {
        if (fire_action == 1)
            input0 &= ~32;
        else if (fire_action == 2)
            input1 &= ~32;
        else
            input1 &= ~64;
    }
    last_fire = fire;
    /* The original VIC keyboard matrix: 5=coin, 1/2=start. */
    HW(0x9122) = 255;
    HW(0x9120) = 254;
    uint8_t keys = HW(0x9121);
    if (!(keys & 1))
        input1 &= ~32;
    if (!(keys & 128))
        input1 &= ~64;
    HW(0x9120) = 251;
    if (!(HW(0x9121) & 1))
        input0 &= ~32;
    HW(0x9120) = 255;
    HW(0x9122) = 127;
}
#ifndef AUDIO_UPDATE_FAST
/* Read the actual arcade output registers. Sound selection, envelopes, song
 * sequencing and interruptions all remain in the original game routines. */
static inline __attribute__((always_inline)) uint8_t audio_voice(uint8_t o, uint8_t wave,
                                                                 uint8_t port, uint8_t bias,
                                                                 bool first) {
    static const uint8_t shifts[8] = {0, 0, 1, 0, 3, 4, 0, 1};
    uint8_t vol = SOUND[o + (first ? 5 : 4)] & 15;
    uint8_t value = 0;
    if (vol && SOUNDENABLE) {
        uint16_t f = (SOUND[o] & 15) | ((SOUND[o + 1] & 15) << 4) |
                     ((uint16_t)(SOUND[o + 2] & 15) << 8) | ((uint16_t)(SOUND[o + 3] & 15) << 12);
        if (first && (SOUND[o + 4] & 15))
            f = 65535;
        uint8_t shift = shifts[SOUND[wave] & 7] + bias;
        while (shift--) {
            if (f & 0x8000) {
                f = 65535;
                break;
            }
            f <<= 1;
        }
        if (f) {
            extern uint8_t audio_divider(uint16_t frequency);
            value = audio_divider(f);
        }
    }
    if (HW(0x900a + port) != value)
        HW(0x900a + port) = value;
    return vol;
}
__attribute__((noinline, section(".cold"))) void audio_update(void) {
    uint8_t volume = audio_voice(16, 5, 0, 0, true);
    uint8_t second = audio_voice(22, 10, 2, 2, false);
    if (second > volume)
        volume = second;
    uint8_t third = audio_voice(27, 15, 1, 3, false);
    if (third > volume)
        volume = third;
    HW(0x900d) = 0;
    HW(0x900e) =
#ifdef MULTICOLOUR
        0x10 |
#endif
        (SOUNDENABLE ? volume : 0);
}
#endif
