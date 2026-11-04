/* Experimental dependency helper; initializer shares the temporary boot image.
   Retain the same 320-byte C stack used by the temporary-glyph trial. */
MEMORY {
 actor_code (rw) : ORIGIN = 0x1d40, LENGTH = 0x180
}
INCLUDE src/pacman.ld
SECTIONS {
 .actor_code : {
  __actor_code_start = .;
  *(.actor_code)
 } >actor_code AT>boot
 __actor_code_load = LOADADDR(.actor_code);
 __actor_code_size = SIZEOF(.actor_code);
}
__stack_bottom = 0x1ec0;
ASSERT(__actor_code_load + __actor_code_size <= __boot_limit, "Actor helper initializer exceeds boot RAM")
ASSERT(ORIGIN(actor_code) + LENGTH(actor_code) <= __stack_bottom, "Actor helper overlaps C stack")
ASSERT(__stack - __stack_bottom >= 320, "Actor renderer needs a 320-byte C stack")
