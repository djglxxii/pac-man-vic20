#include <vic20.h>
#include <cbm.h>   /* waitvsync() is declared here, not in vic20.h */

/* assembly kernels (kernels.s) */
void __fastcall__ fill_screen(unsigned char code);   /* A = code */
extern volatile unsigned char ticks;                  /* incremented by the .interruptor */

#define POKE(a, v)  (*(volatile unsigned char*)(a) = (v))
#define PEEK(a)     (*(volatile unsigned char*)(a))
#define DEBUG_EXIT  (*(volatile unsigned char*)0x910F)

/* cc65's waitvsync() only spins until $9004 == 0 and that lasts two raster lines,
   so back-to-back calls can return twice in one frame. This waits for a new frame. */
static void wait_frame(void)
{
    while (VIC.rasterline == 0) ;     /* leave line 0/1 if we're still on it */
    while (VIC.rasterline != 0) ;     /* wait for the next frame's top */
}

static unsigned char i;          /* globals instead of locals/params (-Cl also helps) */
static unsigned char start;

int main(void)
{
    VIC.bg_border_color = 0x08 | (COLOR_BLACK << 4) | COLOR_BLUE;
    fill_screen(1);              /* screen code 1 = 'A' everywhere */
    if (PEEK(0x1E00) != 1 || PEEK(0x1E00 + 505) != 1) { DEBUG_EXIT = 1; }

    start = ticks;
    for (i = 0; i < 10; ++i) {
        wait_frame();
    }
    /* the interruptor runs on every KERNAL IRQ (~60 Hz): about 10 ticks in 10 frames */
    i = ticks - start;
    if (i < 8 || i > 12) { DEBUG_EXIT = 2; }
    DEBUG_EXIT = 0;
    return 0;
}
