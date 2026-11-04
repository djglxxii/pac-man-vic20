/* Current-artwork raster review. Reuse lower software-stack RAM for the
   bounds/group helpers; initializer bytes are released with startup RAM. */
MEMORY {
 beam_state (rw) : ORIGIN = 0x1d40, LENGTH = 0x50
 beam_code (rw) : ORIGIN = 0x1d90, LENGTH = 0x1f0
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
__stack_bottom = 0x1f80;
ASSERT(__beam_code_load + __beam_code_size <= __boot_limit, "Raster review initializer exceeds boot RAM")
ASSERT(ORIGIN(beam_code) + LENGTH(beam_code) <= __stack_bottom, "Raster review helper overlaps C stack")
ASSERT(__stack - __stack_bottom >= 128, "Raster review needs a 128-byte C stack")
