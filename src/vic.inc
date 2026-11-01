; VIC-20 hardware registers
VIC_HORIZ   = $9000     ; horizontal origin (bit 7 interlace)
VIC_VERT    = $9001     ; vertical origin
VIC_COLS    = $9002     ; columns (bit 7 = screen address bit 9)
VIC_ROWS    = $9003     ; rows*2 (bit 0 = 8x16 chars, bit 7 = raster bit 0)
VIC_RASTER  = $9004     ; raster line / 2
VIC_MEM     = $9005     ; screen + character memory location
VIC_BASS    = $900A
VIC_ALTO    = $900B
VIC_SOPR    = $900C
VIC_NOISE   = $900D
VIC_VOL     = $900E     ; aux colour (hi) + volume (lo)
VIC_COLOR   = $900F     ; background (hi), reverse, border (lo)

VIA1_PA     = $9111     ; joystick: bit2 up, bit3 down, bit4 left, bit5 fire
VIA1_DDRA   = $9113
VIA1_IER    = $911E
VIA2_PB     = $9120     ; bit7 joystick right
VIA2_PA     = $9121
VIA2_DDRB   = $9122
VIA2_IER    = $912E

SCREEN      = $1000
COLRAM      = $9400
CHARSET     = $1800
