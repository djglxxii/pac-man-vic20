/* Resident code in BLK1-3, tables in BLK5; startup borrows logical screen RAM. */
ENTRY(boot_start)
__rc0 = 0x02;
INCLUDE imag-regs.ld
MEMORY {
 zp : ORIGIN = __rc31 + 1, LENGTH = 0xa0 - (__rc31 + 1)
 ram (rw) : ORIGIN = 0x2000, LENGTH = 0x6000
 bank (r) : ORIGIN = 0xa000, LENGTH = 0x2000
 boot (rw) : ORIGIN = 0x0400, LENGTH = 0x800
 work (rw) : ORIGIN = 0x0320, LENGTH = 0xe0
 low_tables (rw) : ORIGIN = 0x0200, LENGTH = 0xc4
 screen_work (rw) : ORIGIN = 0x02c4, LENGTH = 0x3c
 mc_under (rw) : ORIGIN = 0x1cc0, LENGTH = 0x80
 mc_state (rw) : ORIGIN = 0x1a37, LENGTH = 0x209
 video_bits (rw) : ORIGIN = 0x0f00, LENGTH = 0x100
 mc_shift (rw) : ORIGIN = 0x1d40, LENGTH = 0x1e0
}
REGION_ALIAS("c_readonly", ram)
REGION_ALIAS("c_writeable", ram)
SECTIONS {
 .boot : {
  __boot_start = .;
  KEEP(*(.boot.start))
  *(.boot.text)
  __boot_end = .;
 } >boot
 __boot_limit = ORIGIN(boot) + LENGTH(boot);
 ASSERT(boot_start == ORIGIN(boot), "Boot entry must begin in temporary screen RAM")
 .mc_low_tables : { *(.mc_low_tables) } >low_tables AT>boot
 __mc_low_load = LOADADDR(.mc_low_tables);
 __mc_low_size = SIZEOF(.mc_low_tables);
 .mc_shift_tables : { *(.mc_shift_tables) } >mc_shift AT>boot
 __mc_shift_load = LOADADDR(.mc_shift_tables);
 __mc_shift_size = SIZEOF(.mc_shift_tables);
 __stack_bottom = ORIGIN(mc_shift) + LENGTH(mc_shift);
 ASSERT(__stack - __stack_bottom >= 224, "Software stack reservation too small")
 .arcade_data : {
  *(.arcade_data)
  *(.text.mc_store) *(.text.mc_outputs) *(.text.video_fill) *(.text.mc_abort) *(.text.mc_init) *(.text.mc_cache_increment)
  *(.text.fruitHistoryLevelCheck_2bea) *(.text.frame_wait)
  *(.rodata.mc_art) *(.rodata.audio_dividers)
  *(.rodata.bit_reverse)
  *(.arcade_data) *(.graphics) *(.cold)
  *(.rodata.playGameStateMachine_06be.func)
  *(.rodata.nextLevelStateMachine_0a2c.func)
  *(.rodata.arcade_tasks.func)
  *(.rodata.introStateMachine_03fe.func)
  *(.rodata.pacmanDeadAnimState_1291.func)
  *(.rodata.scene1StateMachine_2108)
  *(.rodata.scene2StateMachine_219e.func)
  *(.rodata.scene3StateMachine_2297)
  *(.rodata.scoreTable_2b17)
  *(.rodata.bitmap_columns)
  *(.rodata.main)
  *(.song_dispatch)
  *(.rodata.updateGhostStates_1017)
  *(.rodata*)
 } >bank
 .mc_state (NOLOAD) : { *(.mc_state) } >mc_state
 .mc_under (NOLOAD) : { *(.mc_under) } >mc_under
 .mc_maps (NOLOAD) : { *(.mc_maps) } >ram
 .screen_work (NOLOAD) : { *(.screen_work) } >screen_work
 .video_bits (NOLOAD) : { *(.video_bits) *(.sprite_cache) *(.maze_cells) } >video_bits
 .work (NOLOAD) : { *(.work) } >work
 .scratch (NOLOAD) : { *(.noinit.*) } >work
 /* Zero-page initializers are needed only before the boot handoff. */
 .zp.data : { INCLUDE zp-data-sections.ld } >zp AT>boot
 INCLUDE zp-data-symbols.ld
 INCLUDE zp-bss.ld
 INCLUDE zp-noinit.ld
 INCLUDE text.ld
 INCLUDE rodata.ld
 INCLUDE data.ld
 INCLUDE bss.ld
 INCLUDE noinit.ld
 ASSERT(SIZEOF(.mc_state) <= 0x209, "Renderer metadata overlaps virtual I/O")
 ASSERT((cells_a_lo & 0xff00) == (cells_b_lo & 0xff00), "List low-byte banks must share a page")
 ASSERT((cells_a_hi & 0xff00) == (cells_b_hi & 0xff00), "List high-byte banks must share a page")
 ASSERT((cells_a_lo & 0xff00) == (cells_a_hi & 0xff00), "Cell-list pointer pages differ")
 ASSERT((colors_a & 0xff00) == (colors_b & 0xff00), "Colour-bank pointer pages differ")
 ASSERT((mc_backgrounds & 0xff00) == ((mc_backgrounds+54) & 0xff00), "Underlay-bank pointer pages differ")
 ASSERT((cell_work & 255) == 0, "Working-cell map must be page aligned")
 ASSERT(__zp_data_load_start + __zp_data_size <= __boot_limit, "Boot initializer exceeds temporary RAM")
 ASSERT(__boot_limit <= 0x1000, "Boot image exceeds released logical video RAM")
}
/* c.ld defines _start at resident .text; the actual native entry is in boot. */
_start = boot_start;
__stack = 0x2000;
OUTPUT_FORMAT { FULL(ram) FULL(bank) FULL(boot) }
