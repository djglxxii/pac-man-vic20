/* Prototype: a sparse bitmap transaction in a temporary 512-byte software
   stack frame. No gameplay runs between allocation and publication. */
.section .bss,"aw",@nobits
.global compose_active
compose_active: .zero 1
compose_min: .zero 14
compose_max: .zero 14
compose_lo: .zero 14
compose_hi: .zero 14
.section .text.compose,"ax",@progbits
.global compose_prepare,compose_commit,compose_map
compose_prepare:
 lda full_dirty
 ora maze_flash
 ora dirty_count
 bne compose_no
 /* Keep intermissions on their existing clipped renderer. */
 lda $0e00
 cmp #3
 bne compose_mode_ok
 lda $0e04
 cmp #3
 bne compose_no
compose_mode_ok:
 /* Leave the lower canary plus 64 bytes for callees below the scratch frame. */
 lda __rc1
 cmp #$1f
 bcc compose_no
 bne compose_stack_ok
 lda __rc0
 cmp #$90
 bcc compose_no
 bcs compose_stack_ok
compose_no:
 rts
compose_stack_ok:
 ldx #13
 lda #255
compose_clear:
 sta compose_min,x
 lda #0
 sta compose_max,x
 lda #255
 dex
 bpl compose_clear
 lda #0
 sta v_actor
 ldy #12
compose_actor:
 sty v_off
 lda cache_dirty,y
 beq compose_next
 ldx v_actor
 lda under+3,x
 beq compose_new
 lda under+5,x
 cmp #3
 bne compose_no
 lda under+2,x
compose_old_column:
 cmp #14
 bcc compose_old_ready
 sbc #14
 bcs compose_old_column
compose_old_ready:
 tay
 lda under,x
 sec
 sbc column_lo,y
 /* compose_span takes A=top, Y=column. */
 jsr compose_span
compose_new:
 ldy v_off
 lda $0c21,y
 and #31
 beq compose_next
 lda new_x,y
 cmp #112
 bcc compose_visible
 cmp #249
 bcc compose_next
 bcs compose_no
compose_visible:
 cmp #104
 bcs compose_no
 lsr
 lsr
 lsr
 tax
 lda new_y,y
 sta v_temp
 txa
 tay
 lda v_temp
 jsr compose_span
compose_next:
 lda v_actor
 clc
 adc #36
 sta v_actor
 ldy v_off
 dey
 dey
 bne compose_actor
 /* The first 196 bytes shadow colour RAM; remaining bytes hold columns. */
 dec __rc1
 dec __rc1
 lda __rc0
 sta v_colors
 clc
 adc #196
 sta v_save
 lda __rc1
 sta v_colors+1
 adc #0
 sta v_save+1
 ldx #13
compose_snapshot:
 lda compose_min,x
 cmp #255
 beq compose_snapshot_next
 jsr compose_geometry
 /* Check capacity before writing any part of this column. */
 lda v_save
 clc
 adc v_row
 sta v_base
 lda v_save+1
 adc #0
 sta v_base+1
 lda __rc1
 clc
 adc #2
 cmp v_base+1
 bcc compose_abort
 bne compose_capacity_ok
 lda __rc0
 cmp v_base
 bcc compose_abort
compose_capacity_ok:
 lda v_save
 sec
 sbc compose_min,x
 sta compose_lo,x
 lda v_save+1
 sbc #0
 sta compose_hi,x
 ldy #0
compose_snapshot_row:
 lda (v_addr),y
 sta (v_save),y
 iny
 cpy v_row
 bne compose_snapshot_row
 lda v_base
 sta v_save
 lda v_base+1
 sta v_save+1
 jsr compose_colour_range
compose_snapshot_colour:
 lda $9600,y
 sta (v_colors),y
 jsr compose_colour_next
 bne compose_snapshot_colour
compose_snapshot_next:
 dex
 bpl compose_snapshot
 lda #1
 sta compose_active
 rts
compose_abort:
 inc __rc1
 inc __rc1
 lda #0
 sta v_colors
 lda #$96
 sta v_colors+1
 rts

compose_span:
 ldx #2
compose_span_column:
 cmp compose_min,y
 bcs compose_span_max
 sta compose_min,y
compose_span_max:
 clc
 adc #12
 cmp compose_max,y
 bcc compose_span_right
 sta compose_max,y
compose_span_right:
 sec
 sbc #12
 iny
 dex
 bne compose_span_column
 rts

/* X=column. Live pointer and byte count, without changing the copy cursor. */
compose_geometry:
 lda compose_min,x
 clc
 adc column_lo,x
 sta v_addr
 lda column_hi,x
 adc #0
 sta v_addr+1
 lda compose_max,x
 sec
 sbc compose_min,x
 sta v_row
 rts

/* Select the colour cells touched by this column interval. */
compose_colour_range:
 lda compose_max,x
 sec
 sbc #1
 lsr
 lsr
 lsr
 lsr
 sta v_temp
 lda compose_min,x
 lsr
 lsr
 lsr
 lsr
 tay
 eor #255
 sec
 adc v_temp
 sta v_temp
 inc v_temp
 lda row_times_14,y
 stx v_lo
 clc
 adc v_lo
 tay
 rts
compose_colour_next:
 tya
 clc
 adc #14
 tay
 dec v_temp
 rts

/* bitmap_setup supplies the two live pointers. Preserve its caller's X. */
compose_map:
 txa
 pha
 ldx #13
compose_find:
 lda v_addr+1
 cmp column_hi,x
 bcc compose_find_next
 bne compose_found
 lda v_addr
 cmp column_lo,x
 bcs compose_found
compose_find_next:
 dex
 bpl compose_find
compose_found:
 lda v_addr
 sec
 sbc column_lo,x
 clc
 adc compose_lo,x
 sta v_addr
 lda compose_hi,x
 adc #0
 sta v_addr+1
 inx
 lda v_right
 sec
 sbc column_lo,x
 clc
 adc compose_lo,x
 sta v_right
 lda compose_hi,x
 adc #0
 sta v_right+1
 pla
 tax
 rts

compose_commit:
 lda compose_active
 beq compose_commit_done
.global compose_publish_begin,compose_publish_done
compose_publish_begin:
 ldx #13
compose_publish_column:
 lda compose_min,x
 cmp #255
 beq compose_publish_next
 jsr compose_geometry
 lda compose_lo,x
 clc
 adc compose_min,x
 sta v_save
 lda compose_hi,x
 adc #0
 sta v_save+1
 ldy #0
compose_publish_row:
 lda (v_save),y
 sta (v_addr),y
 iny
 cpy v_row
 bne compose_publish_row
 jsr compose_colour_range
compose_publish_colour:
 lda (v_colors),y
 sta $9600,y
 jsr compose_colour_next
 bne compose_publish_colour
compose_publish_next:
 dex
 bpl compose_publish_column
compose_publish_done:
 jsr compose_abort
 lda #0
 sta compose_active
compose_commit_done:
 rts
