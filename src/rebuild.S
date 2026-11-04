#include "colour_target.h"
/* One bounded background slice. State lives in unused screen-work RAM;
   v_* scratch belongs to the main-thread renderer and is not IRQ-visible.
   Phases: 0 idle, 1 clear bitmap, 2 full tile pass, 3 dirty tile pass. */
.section .screen_work,"aw",@nobits
rebuild_budget: .zero 1
.zeropage __rc2,__rc3,v_addr,v_save,v_lo,v_hi,dirty_count,full_dirty
.section .text.rebuild,"ax",@progbits
.global video_store
/* LLVM-MOS: A is the byte, __rc2/__rc3 the pointer. This saves enough resident
   code for the continuation and keeps ordinary dirty writes inexpensive. */
video_store:
 ldy #0
 cmp (__rc2),y
 beq store_done
 sta (__rc2),y
 lda __rc3
 cmp #4
 bcc store_done
 cmp #12
 bcs store_done
 ldx full_dirty
 cpx #2
 beq store_done
 and #3
 sta v_save+1
 lda __rc2
 sta v_save
 and #7
 tax
 lda bit_masks,x
 sta v_lo
 lda v_save+1
 asl
 asl
 asl
 asl
 asl
 sta v_hi
 lda v_save
 lsr
 lsr
 lsr
 ora v_hi
 tax
 lda dirty_bits,x
 and v_lo
 bne store_done
 lda dirty_bits,x
 ora v_lo
 sta dirty_bits,x
 lda full_dirty
 beq store_queue
 /* Ahead-of-cursor writes are read in this pass; revisit earlier writes. */
 lda rebuild_phase
 cmp #2
 bcc store_done
 lda v_save
 sec
 sbc rebuild_cursor
 lda v_save+1
 sbc rebuild_cursor+1
 bcs store_done
 lda #1
 sta rebuild_again
store_done:
 rts
store_queue:
 ldx dirty_count
 cpx #20
 beq store_overflow
 txa
 asl
 tax
 lda v_save
 sta dirty_queue,x
 lda v_save+1
 sta dirty_queue+1,x
 inc dirty_count
 rts
store_overflow:
 lda #1
 sta full_dirty
 lda #0
 sta dirty_count
 rts
.global video_background
video_background:
 lda full_dirty
 beq background_queue
 jmp video_rebuild
background_queue:
 ldx #0
background_tile:
 txa
 lsr
 cmp dirty_count
 bcs background_done
 stx rebuild_budget
 lda dirty_queue,x
 sta v_save
 lda dirty_queue+1,x
 sta v_save+1
 jsr bitmap_tile
 lda v_save+1
 asl
 asl
 asl
 asl
 asl
 sta v_hi
 lda v_save
 lsr
 lsr
 lsr
 ora v_hi
 tax
 lda v_save
 and #7
 tay
 lda bit_masks,y
 eor #255
 and dirty_bits,x
 sta dirty_bits,x
 ldx rebuild_budget
 inx
 inx
 jmp background_tile
background_done:
 lda #0
 sta dirty_count
 rts
.global video_rebuild
video_rebuild:
 lda full_dirty
 cmp #2
 bne rebuild_resume
#ifdef STABLE_COLOURS
 lda #1
 sta colour_full
#endif
 lda #0
 sta rebuild_cursor
 sta rebuild_cursor+1
 sta rebuild_again
 ldx #196
rebuild_colours:
 dex
 sta VIDEO_COLOURS,x
#ifdef GLYPH_POOL
 sta $9600,x
#endif
 bne rebuild_colours
 ldx #127
rebuild_bits:
 sta dirty_bits,x
 dex
 bpl rebuild_bits
 ldx #24
rebuild_walls:
 sta maze_cells,x
 dex
 bpl rebuild_walls
 lda #1
 sta full_dirty
 sta rebuild_phase
 rts
rebuild_resume:
 lda rebuild_phase
 bne rebuild_started
 lda #0
 sta rebuild_cursor
 sta rebuild_cursor+1
 sta rebuild_again
 lda #3
 sta rebuild_phase
rebuild_started:
 cmp #1
 bne rebuild_tiles
 lda rebuild_cursor
 sta v_addr
 lda rebuild_cursor+1
 clc
 adc #$10
 sta v_addr+1
 cmp #$1c
 beq rebuild_clear_tail
 ldy #0
 lda #0
rebuild_clear_page:
 sta (v_addr),y
 iny
 bne rebuild_clear_page
 inc rebuild_cursor+1
 rts
rebuild_clear_tail:
 ldy #63
rebuild_clear:
 lda #0
rebuild_clear_byte:
 sta (v_addr),y
 dey
 bpl rebuild_clear_byte
rebuild_cleared:
 lda #0
 sta rebuild_cursor
 sta rebuild_cursor+1
 lda #2
 sta rebuild_phase
 rts
rebuild_tiles:
 lda #6
 ldx rebuild_phase
 cpx #3
 bne rebuild_set_budget
 lda #4
rebuild_set_budget:
 sta rebuild_budget
rebuild_tile:
 lda rebuild_cursor+1
 asl
 asl
 asl
 asl
 asl
 sta v_hi
 lda rebuild_cursor
 lsr
 lsr
 lsr
 ora v_hi
 tax
 lda rebuild_phase
 cmp #3
 bne rebuild_nonempty
 lda dirty_bits,x
 bne rebuild_nonempty
 /* Scan empty bytes directly: even a complete empty bitset costs little.
    A sparse pass must finish between repeated credit/score text writes. */
rebuild_find_group:
 inx
 cpx #128
 bne rebuild_group_ready
 jmp rebuild_pass_done
rebuild_group_ready:
 lda dirty_bits,x
 beq rebuild_find_group
 txa
 asl
 asl
 asl
 sta rebuild_cursor
 txa
 lsr
 lsr
 lsr
 lsr
 lsr
 sta rebuild_cursor+1
rebuild_nonempty:
 lda rebuild_cursor
 and #7
 tay
 lda bit_masks,y
 sta v_lo
 eor #255
 and dirty_bits,x
 sta v_hi
 lda dirty_bits,x
 and v_lo
 sta v_lo
 lda v_hi
 sta dirty_bits,x
 lda rebuild_cursor
 sta v_save
 sta v_addr
 lda rebuild_cursor+1
 sta v_save+1
 ldx rebuild_phase
 cpx #2
 bne rebuild_dirty
 clc
 adc #8
 sta v_addr+1
 ldy #0
 lda (v_addr),y
 and #31
 beq rebuild_advance
 lda v_addr+1
 sec
 sbc #4
 sta v_addr+1
 lda (v_addr),y
 cmp #$40
 beq rebuild_advance
 cmp #$fc
 beq rebuild_advance
 cmp #$fd
 beq rebuild_advance
 bne rebuild_paint
rebuild_dirty:
 lda v_lo
 beq rebuild_advance
rebuild_paint:
 jsr bitmap_tile
rebuild_advance:
 inc rebuild_cursor
 bne rebuild_next
 inc rebuild_cursor+1
 lda rebuild_cursor+1
 cmp #4
 bne rebuild_next
rebuild_pass_done:
 lda #0
 sta rebuild_cursor
 sta rebuild_cursor+1
 lda rebuild_again
 beq rebuild_done
 lda #0
 sta rebuild_again
 lda #3
 sta rebuild_phase
 jmp rebuild_next
rebuild_done:
 sta rebuild_phase
 sta full_dirty
 sta dirty_count
 rts
rebuild_next:
 dec rebuild_budget
 beq rebuild_slice_done
 jmp rebuild_tile
rebuild_slice_done:
 rts
