/* Resident code in BLK1-3, tables in BLK5; startup borrows logical screen RAM. */
ENTRY(boot_start)
__rc0 = 0x02;
INCLUDE imag-regs.ld
MEMORY {
 zp : ORIGIN = __rc31 + 1, LENGTH = 0xa0 - (__rc31 + 1)
 ram (rw) : ORIGIN = 0x2000, LENGTH = 0x6000
 bank (r) : ORIGIN = 0xa000, LENGTH = 0x2000
 boot (rw) : ORIGIN = 0x0400, LENGTH = 0x400
 work (rw) : ORIGIN = 0x0320, LENGTH = 0xe0
 screen_work (rw) : ORIGIN = 0x02c4, LENGTH = 0x3c
 video_bits (rw) : ORIGIN = 0x0f00, LENGTH = 0x100
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
 .arcade_data : {
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
 } >bank
 .screen_work (NOLOAD) : { *(.screen_work) } >screen_work
 .video_bits (NOLOAD) : { *(.video_bits) *(.sprite_cache) *(.maze_cells) } >video_bits
 .work (NOLOAD) : { *(.work) } >work
 .scratch (NOLOAD) : { *(.noinit.*) } >work
 INCLUDE c.ld
}
/* c.ld defines _start at resident .text; the actual native entry is in boot. */
_start = boot_start;
__stack = 0x2000;
OUTPUT_FORMAT { FULL(ram) FULL(bank) FULL(boot) }
