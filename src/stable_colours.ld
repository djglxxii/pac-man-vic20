INCLUDE src/pacman.ld
/* The VIC displays $9600-$96C3. Its other colour page is ordinary onboard
   nibble RAM; compose there, then copy nibbles to the displayed page. Upper
   read bits are unspecified, but ignored by both colour-RAM destinations. */
colour_work = 0x9400;
/* BASIC's vectors are unused after boot. Keep the live IRQ vector at $0314
   and every address above it untouched. No KERNAL calls except IRQ dispatch. */
MEMORY { colour_queue (rw) : ORIGIN = 0x0300, LENGTH = 0x10 }
SECTIONS { .colour_queue (NOLOAD) : { *(.colour_queue) } >colour_queue }
