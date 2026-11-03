/* Hold the previous actor pixels on screen while the original bitmap renderer
   restores and repaints. Screen codes return to their fixed bitmap mapping at
   the end of the update. Colours retain the original renderer's live writes.
   Main thread only; clobbers A/X/Y and v_addr/v_save/v_lo/v_hi. */
.section .bss.shadow,"aw",@nobits
.global shadow_count,shadow_cells,shadow_codes
shadow_count: .zero 1
shadow_cells: .zero 24
shadow_codes: .zero 24
.zeropage v_addr,v_save,v_lo,v_hi
.section .text.shadow,"ax",@progbits
.global shadow_begin,shadow_end,shadow_ready
shadow_begin:
 lda full_dirty
 ora maze_flash
 bne shadow_ready
 lda #2
 sta v_hi
 ldx #180
shadow_actor:
 stx shadow_actor_index+1
 ldy v_hi
 lda cache_dirty,y
 beq shadow_next_actor
 lda under+3,x
 beq shadow_next_actor
 lda under+5,x
 and #1
 beq shadow_right
 ldy under+2,x
 jsr shadow_cell
shadow_right:
 ldx shadow_actor_index+1
 lda under+5,x
 and #2
 beq shadow_lower
 ldy under+2,x
 iny
 jsr shadow_cell
shadow_lower:
 ldx shadow_actor_index+1
 lda under+7,x
 cmp #5
 bcc shadow_next_actor
 lda under+2,x
 clc
 adc #14
 tay
 lda under+5,x
 and #1
 beq shadow_lower_right
 jsr shadow_cell
shadow_lower_right:
 ldx shadow_actor_index+1
 lda under+5,x
 and #2
 beq shadow_next_actor
 lda under+2,x
 clc
 adc #15
 tay
 jsr shadow_cell
shadow_next_actor:
 inc v_hi
 inc v_hi
shadow_actor_index:
 ldx #180
 txa
 sec
 sbc #36
 tax
 bcs shadow_actor
shadow_ready:
 rts

/* Y = hardware cell. A code >=196 is already hidden or outside the bitmap.
   Six actors occupy at most four cells each, including clipped footprints. */
shadow_cell:
 cpy #196
 bcc shadow_cell_in_range
 rts
shadow_cell_in_range:
 lda $0200,y
 cmp #196
 bcc shadow_cell_copy
 rts
shadow_cell_copy:
 ldx shadow_count
 sta shadow_codes,x
 sta v_lo
 tya
 sta shadow_cells,x
 lda v_lo
 asl
 asl
 asl
 asl
 sta v_addr
 lda v_lo
 lsr
 lsr
 lsr
 lsr
 ora #$10
 sta v_addr+1
 txa
 clc
 adc #212
 sta v_lo
 asl
 asl
 asl
 asl
 sta v_save
 lda v_lo
 lsr
 lsr
 lsr
 lsr
 ora #$10
 sta v_save+1
 ldy #15
 .rept 16
 lda (v_addr),y
 sta (v_save),y
 dey
 .endr
 ldy shadow_cells,x
 lda v_lo
 sta $0200,y
 inc shadow_count
shadow_cell_done:
 rts

shadow_end:
 ldx shadow_count
 beq shadow_end_done
shadow_publish:
 dex
 ldy shadow_cells,x
 lda shadow_codes,x
 sta $0200,y
 cpx #0
 bne shadow_publish
 stx shadow_count
shadow_end_done:
 rts
