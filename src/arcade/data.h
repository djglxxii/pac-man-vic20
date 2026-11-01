/*
 * Copyright (c) 2024 Mark Burkley.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#ifndef __DATA_H
#define __DATA_H

#include "memmap.h"

#define DATA_0219 (rom_ptr(0x0219))
#define DATA_0796 (rom_ptr(0x0796))
#define DATA_0843 (rom_ptr(0x0843))
#define DATA_084f (rom_ptr(0x084f))
#define DATA_0861 (rom_ptr(0x0861))
#define DATA_0873 (rom_ptr(0x0873))
#define FRUIT_DATA_0efd (rom_ptr(0x0efd))
#define BONUS_LIFE_DATA (rom_ptr(0x2728))
#define DIFFICULTY_DATA ((uint16_t *)(rom_ptr(0x272c)))
#define MOVE_VECTOR_DATA ((XYPOS *)(rom_ptr(0x32ff)))
#define MOVE_VECTOR_RIGHT ((XYPOS *)(rom_ptr(0x32ff)))
#define MOVE_VECTOR_DOWN ((XYPOS *)(rom_ptr(0x3301)))
#define MOVE_VECTOR_LEFT ((XYPOS *)(rom_ptr(0x3303)))
#define MOVE_VECTOR_UP ((XYPOS *)(rom_ptr(0x3305)))
#define MOVE_DATA_330f (rom_ptr(0x330f))
#define DATA_3435 rom_ptr(0x3435)
#define DATA_35b5 (rom_ptr(0x35b5))
#define EFFECT_TABLE_CH3_3b80 (rom_ptr(0x3b80))
#define EFFECT_TABLE_CH1_3b30 (rom_ptr(0x3b30))
#define EFFECT_TABLE_CH2_3b40 (rom_ptr(0x3b40))
#define FRUIT_TABLE (rom_ptr(0x3b08))
#define DATA_MSG_TABLE_36a5 (rom_ptr(0x36a5))
#define SONG_TABLE_CH1_3bc8 (rom_ptr(0x3bc8))
#define POWER_OF_2_3bb0 (rom_ptr(0x3bb0))
#define FREQ_TABLE_3bb8 (rom_ptr(0x3bb8))
#define SONG_TABLE_CH2_3bcc (rom_ptr(0x3bcc))
#define SONG_TABLE_CH3_3bd0 (rom_ptr(0x3bd0))
#define DATA_3154 ((uint16_t *)(rom_ptr(0x3154)))
#define BAD_ROM_316c (rom_ptr(0x316c))
#define BAD_W_RAM_316e (rom_ptr(0x316e))
#define BAD_V_RAM_3170 (rom_ptr(0x3170))
#define BAD_C_RAM_3172 (rom_ptr(0x3172))
#define DATA_32f9 (rom_ptr(0x32f9))
#define DATA_3ae2 ((uint16_t *)(rom_ptr(0x3ae2)))

#endif
