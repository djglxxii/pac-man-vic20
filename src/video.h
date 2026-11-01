#ifndef PACMAN_VIDEO_H
#define PACMAN_VIDEO_H
#include <stdint.h>
#include <stddef.h>
#ifdef VIC20
void video_store(uint8_t *p, uint8_t value);
void video_fill(uint8_t *p, uint8_t value, uint16_t count);
void video_flash_palette(uint8_t param);
#else
#include <string.h>
static inline void video_store(uint8_t *p, uint8_t value) { *p = value; }
static inline void video_fill(uint8_t *p, uint8_t value, uint16_t count) {
    memset(p, value, count);
}
#endif
#endif
