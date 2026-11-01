/* The queue head is retained until its bulk task completes. These routines
   touch only logical video RAM; the IRQ and game-state machines keep ticking.
   Results: 0 ordinary task, 1 unfinished bulk task, 2 completed bulk task. */
.section .screen_work,"aw",@nobits
.global bulk_active,bulk_drain
bulk_active: .zero 1
bulk_drain: .zero 1
bulk_task: .zero 1
bulk_param: .zero 1
bulk_cursor: .zero 2
bulk_source: .zero 2
bulk_index: .zero 1
bulk_bits: .zero 1
bulk_count: .zero 1
.zeropage __rc2,__rc3,v_addr,v_data,v_flags,v_hi,full_dirty,dirty_count
.section .text.bulk,"ax",@progbits
.global arcade_bulk_step
arcade_bulk_step:
 cmp #0
 beq bulk_fill_task
 cmp #6
 beq bulk_fill_task
 cmp #1
 bne bulk_not_palette
 /* Keep the existing bounded flash path and its original twelve-tick cadence. */
 cpx #1
 beq bulk_fill_task
 ldy $0e04
 cpy #15
 bcc bulk_fill_task
 cpy #30
 bcs bulk_fill_task
 lda #0
 rts
bulk_not_palette:
 cmp #2
 bne bulk_not_maze
 jmp bulk_maze
bulk_not_maze:
 cmp #3
 bne bulk_not_pills
 jmp bulk_pills
bulk_not_pills:
 cmp #19
 bne bulk_ordinary
 jmp bulk_clear_pills
bulk_ordinary:
 lda #0
 rts
/* Carry reports first entry. Scratch stays outside the compiler's frames. */
bulk_init:
 ldy bulk_active
 bne bulk_existing
 sta bulk_task
 stx bulk_param
 lda #1
 sta bulk_active
 sta bulk_drain
 lda #0
 sta bulk_cursor
 sta bulk_cursor+1
 sta bulk_index
 sec
 rts
bulk_existing:
 clc
 rts
bulk_fill_task:
 jsr bulk_init
 bcc bulk_fill_ready
 lda #2
 sta full_dirty
 lda #0
 sta dirty_count
 lda bulk_task
 cmp #6
 beq bulk_fill_ready
 cmp #1
 beq bulk_fill_offset
 lda bulk_param
 beq bulk_fill_ready
bulk_fill_offset:
 lda #64
 sta bulk_cursor
bulk_fill_ready:
 lda bulk_cursor
 sta v_addr
 lda bulk_cursor+1
 clc
 adc #4
 ldx bulk_task
 beq bulk_screen_fill
 clc
 adc #4
bulk_screen_fill:
 sta v_addr+1
 lda #$40
 cpx #0
 beq bulk_fill_value
 lda #0
 cpx #6
 beq bulk_fill_value
 lda #16
 ldx bulk_param
 cpx #2
 bne bulk_fill_hud
 lda #31
bulk_fill_hud:
 ldx bulk_cursor+1
 cpx #3
 bne bulk_fill_value
 ldx bulk_cursor
 cpx #$c0
 bcc bulk_fill_value
 lda #15
bulk_fill_value:
 sta v_flags
 lda #64
 sta bulk_count
bulk_fill_byte:
 lda v_addr
 sta __rc2
 lda v_addr+1
 sta __rc3
 lda v_flags
 jsr video_store
 inc v_addr
 bne bulk_fill_count
 inc v_addr+1
bulk_fill_count:
 dec bulk_count
 bne bulk_fill_byte
 jsr bulk_advance_64
 lda bulk_task
 bne bulk_fill_whole
 lda bulk_param
 beq bulk_fill_whole
 lda bulk_cursor
 cmp #$c0
 bne bulk_pending
 lda bulk_cursor+1
 cmp #3
 bne bulk_pending
 jmp bulk_done
bulk_fill_whole:
 lda bulk_cursor+1
 cmp #4
 bne bulk_pending
 lda bulk_task
 cmp #1
 bne bulk_done
 lda bulk_param
 cmp #1
 bne bulk_done
 /* Original ghost-house palette patches; a full invalidation already covers
    these direct writes, so no dirty-queue or underlay state can miss them. */
 ldx #0
 lda #26
bulk_house_colour:
 sta $09ac,x
 sta $09b8,x
 pha
 txa
 clc
 adc #32
 tax
 pla
 cpx #192
 bne bulk_house_colour
 ldx #128
 lda #27
bulk_house_door:
 sta $084e,x
 sta $084f,x
 sta $0850,x
 sta $0b2e,x
 sta $0b2f,x
 sta $0b30,x
 pha
 txa
 sec
 sbc #32
 tax
 pla
 bcs bulk_house_door
 lda #24
 sta $09ed
 sta $0a0d
 /* Include patches behind a running cursor without clearing the bitmap again.
    An unstarted full invalidation already includes every logical cell. */
 lda full_dirty
 cmp #2
 beq bulk_done
 lda #1
 sta full_dirty
 sta rebuild_again
 lda #255
 ldx #127
bulk_patch_bits:
 sta dirty_bits,x
 dex
 bpl bulk_patch_bits
bulk_done:
 lda #0
 sta bulk_active
 lda #2
 rts
bulk_pending:
 lda #1
 rts
bulk_advance_64:
 lda bulk_cursor
 clc
 adc #64
 sta bulk_cursor
 bcc bulk_advanced
 inc bulk_cursor+1
bulk_advanced:
 rts
bulk_maze:
 jsr bulk_init
 bcc bulk_maze_ready
 lda #<(rom_32f9+$13c)
 sta bulk_source
 lda #>(rom_32f9+$13c)
 sta bulk_source+1
bulk_maze_ready:
 lda bulk_source
 sta v_data
 lda bulk_source+1
 sta v_data+1
 lda #16
 sta bulk_count
bulk_maze_pair:
 ldy #0
 lda (v_data),y
 beq bulk_done
 bmi bulk_maze_literal
 sec
 sbc #1
 clc
 adc bulk_cursor
 sta bulk_cursor
 bcc bulk_maze_source
 inc bulk_cursor+1
bulk_maze_source:
 inc v_data
 bne bulk_maze_next_byte
 inc v_data+1
bulk_maze_next_byte:
 lda (v_data),y
bulk_maze_literal:
 sta v_flags
 inc bulk_cursor
 bne bulk_maze_store
 inc bulk_cursor+1
bulk_maze_store:
 lda bulk_cursor
 sta __rc2
 lda bulk_cursor+1
 clc
 adc #4
 sta __rc3
 lda v_flags
 jsr video_store
 lda bulk_cursor
 and #31
 asl
 clc
 adc #$e0
 tax
 lda #3
 adc #0
 tay
 txa
 sec
 sbc bulk_cursor
 sta __rc2
 tya
 sbc bulk_cursor+1
 clc
 adc #4
 sta __rc3
 lda v_flags
 eor #1
 jsr video_store
 inc v_data
 bne bulk_maze_count
 inc v_data+1
bulk_maze_count:
 dec bulk_count
 bne bulk_maze_pair
 lda v_data
 sta bulk_source
 lda v_data+1
 sta bulk_source+1
 jmp bulk_pending
bulk_pills:
 jsr bulk_init
 bcc bulk_pills_ready
 lda #128
 sta bulk_bits
bulk_pills_ready:
 lda #16
 sta bulk_count
bulk_pill:
 ldy bulk_index
 lda rom_32f9+$2bc,y
 clc
 adc bulk_cursor
 sta bulk_cursor
 bcc bulk_pill_bit
 inc bulk_cursor+1
bulk_pill_bit:
 tya
 lsr
 lsr
 lsr
 tax
 lda $0e16,x
 and bulk_bits
 beq bulk_pill_next
 lda bulk_cursor
 sta __rc2
 lda bulk_cursor+1
 clc
 adc #4
 sta __rc3
 lda #16
 jsr video_store
bulk_pill_next:
 lsr bulk_bits
 bne bulk_pill_index
 lda #128
 sta bulk_bits
bulk_pill_index:
 inc bulk_index
 lda bulk_index
 cmp #240
 beq bulk_powerups
 dec bulk_count
 bne bulk_pill
 jmp bulk_pending
bulk_powerups:
 ldx #3
bulk_powerup:
 stx bulk_count
 lda powerup_lo,x
 sta __rc2
 lda powerup_hi,x
 sta __rc3
 lda $0e34,x
 jsr video_store
 ldx bulk_count
 dex
 bpl bulk_powerup
 jmp bulk_done
powerup_lo: .byte $64,$78,$84,$98
powerup_hi: .byte $04,$04,$07,$07
bulk_clear_pills:
 jsr bulk_init
 bcc bulk_clear_ready
 lda #64
 sta bulk_cursor
bulk_clear_ready:
 lda bulk_cursor
 sta v_data
 lda bulk_cursor+1
 clc
 adc #4
 sta v_data+1
 lda #64
 sta bulk_count
bulk_clear_pill:
 ldy #0
 lda (v_data),y
 cmp #16
 beq bulk_erase_pill
 cmp #18
 beq bulk_erase_pill
 cmp #20
 bne bulk_clear_next
bulk_erase_pill:
 lda v_data
 sta __rc2
 lda v_data+1
 sta __rc3
 lda #64
 jsr video_store
bulk_clear_next:
 inc v_data
 bne bulk_clear_count
 inc v_data+1
bulk_clear_count:
 dec bulk_count
 bne bulk_clear_pill
 jsr bulk_advance_64
 lda bulk_cursor
 cmp #$c0
 bne bulk_clear_pending
 lda bulk_cursor+1
 cmp #3
 bne bulk_clear_pending
 jmp bulk_done
bulk_clear_pending:
 jmp bulk_pending
/* Synchronous entry points are retained for isolated routine comparisons.
   The live queue calls arcade_bulk_step directly and never drains these loops. */
.global drawMaze_2419,drawPills_2448,clearPillsScreen_2a35,mazeColours_full
drawMaze_2419:
 ldx #0
 lda #2
 jmp bulk_run
drawPills_2448:
 ldx #0
 lda #3
 jmp bulk_run
clearPillsScreen_2a35:
 ldx #0
 lda #19
 jmp bulk_run
mazeColours_full:
 tax
 lda #1
bulk_run:
 jsr arcade_bulk_step
 cmp #1
 bne bulk_run_done
 lda bulk_task
 ldx bulk_param
 jmp bulk_run
bulk_run_done:
 rts
.global clearGhostState_26a2
/* The arcade's contiguous state range straddles native RAM and zero page.
   Fixed loops avoid a 26 ms generic address translation loop during setup. */
clearGhostState_26a2:
 lda #0
 ldx #160
bulk_clear_state:
 dex
 sta $0d00,x
 bne bulk_clear_state
 ldx #96
bulk_clear_flags:
 dex
 sta $a0,x
 bne bulk_clear_flags
 rts
