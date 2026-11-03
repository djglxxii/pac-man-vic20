/* The original bitmap/I/O layout, with renderer state and a small code overlay
   in unused lower stack reservation. Initializer bytes travel in the boot image. */
MEMORY {
 beam_state (rw) : ORIGIN = 0x1d40, LENGTH = 0x80
 beam_code (rw) : ORIGIN = 0x1dc0, LENGTH = 0x140
}
INCLUDE src/pacman.ld
SECTIONS {
 .beam_state (NOLOAD) : { *(.beam_state) } >beam_state
 .beam_code : {
  __beam_code_start = .;
  *(.beam_code)
 } >beam_code AT>boot
 __beam_code_load = LOADADDR(.beam_code);
 __beam_code_size = SIZEOF(.beam_code);
}
__stack_bottom = 0x1f00;
ASSERT(__beam_code_load + __beam_code_size <= __boot_limit, "Beam initializer exceeds boot RAM")
ASSERT(ORIGIN(beam_code) + LENGTH(beam_code) <= __stack_bottom, "Beam code overlaps stack")
ASSERT(__stack - __stack_bottom >= 256, "Beam renderer needs a 256-byte C stack")
