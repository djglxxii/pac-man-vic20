/* Original hires layout, with 24 temporary display glyphs below the C stack. */
INCLUDE src/pacman.ld
__shadow_glyphs = 0x1d40;
__shadow_capacity = 24;
__stack_bottom = __shadow_glyphs + __shadow_capacity * 16;
ASSERT(__shadow_glyphs == 0x1000 + 212 * 16, "Wrong shadow character base")
ASSERT(__stack - __stack_bottom >= 320, "Shadow pool overlaps software stack")
