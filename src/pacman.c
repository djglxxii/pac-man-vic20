/* Pac-Man native VIC-20 platform. Arcade coordinates remain unscaled. */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include "arcade/memmap.h"
#include "arcade/protos.h"
#define HW(a) (*(volatile uint8_t *)(a))
uint8_t input0 = 255, input1 = 255, dipSwitches = 0xc9;
volatile uint16_t arcade_ticks;
void interruptEnable(void) {}
void interruptDisable(void) {}
void interruptMode(int m) {}
void interruptVector(void (*f)(void)) {}
void interruptHalt(void) {}
void kickWatchdog(void) {}
void showTarget(XYPOS a, XYPOS b, int col) {}
void arcade_tasks(void);
void controls(void), audio_update(void), clock_init(void);
extern volatile uint8_t clock_ticks;
void video_init(void), video_update_begin(void), video_background(void), video_update_end(void);
__attribute__((noinline)) void frame_wait(void) {
    extern uint8_t last_tick;
    while (clock_ticks == last_tick) {
    }
    last_tick++;
}
uint8_t last_tick;
int main(void) {
    HW(0x900f) = 8;
    HW(0x9002) = 14 | 128;
    HW(0x9003) = 29;
    HW(0x9005) = 0x8c;
    HW(0x9000) = 13;
    HW(0x9001) = 16;
    HW(0x9113) = 0;
    HW(0x9122) = 0x7f;
    HW(0x9123) = 0;
    arcade_ticks = 0;
    memset((void *)0x400, 0, 0xc00);
    memset((void *)0x1c40, 0, 0x100);
    video_init();
    mainTaskLoop_234b();
    last_tick = 0;
    clock_init();
    while (1) {
        frame_wait();
        controls();
        isr_008d();
        arcade_tasks();
        arcade_ticks++;
        audio_update();
        if (clock_ticks == last_tick) {
            __asm__ volatile(".global video_frame_begin\nvideo_frame_begin:");
            video_update_begin();
            video_background();
            video_update_end();
            __asm__ volatile(".global video_frame_end\nvideo_frame_end:");
        }
    }
    return 0;
}
