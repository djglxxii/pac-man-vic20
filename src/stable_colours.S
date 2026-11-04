/* Deferred colour publication. Existing actor order resolves priority in the
   unused onboard colour page. Publish only old/new actor rectangles and queued
   background cells; repeated stores contain the same resolved colour.
   Main thread only. Clobbers A/X/Y and v_flags. No raster waits or actor rules.
   Underlay bytes 4/6 retain old cell/flags until publication; no pixel changes.
   Sixteen queued background cells cover ordinary edits; overflow, rebuild
   clears and maze flashes use a full copy. No entries beyond that bound. */
.section .colour_queue,"aw",@nobits
.global colour_cells,colour_count,colour_full
colour_cells: .zero 16
.section .bss.colours,"aw",@nobits
colour_count: .zero 1
colour_full: .zero 1
.zeropage v_flags
.section .text.colour_publish,"ax",@progbits
.global colour_publish
colour_publish:
 lda colour_full
 bne colour_publish_full
 ldx colour_count
 beq colour_publish_actors
colour_publish_background:
 dex
 ldy colour_cells,x
 lda colour_work,y
 sta $9600,y
 cpx #0
 bne colour_publish_background
colour_publish_actors:
 ldx #0
colour_publish_actor:
 /* Most moves stay within the same character cells. One publication covers
    both poses when their clipped rectangles are identical. */
 lda under+3,x
 beq colour_publish_old
 lda under+2,x
 cmp under+4,x
 bne colour_publish_old
 lda under+7,x
 cmp #5
 lda under+5,x
 bcc colour_publish_compare
 ora #4
colour_publish_compare:
 cmp under+6,x
 beq colour_publish_flags
colour_publish_old:
 lda under+6,x
 beq colour_publish_new
 sta v_flags
 ldy under+4,x
 jsr colour_publish_rect
colour_publish_new:
 lda under+3,x
 beq colour_publish_next
 lda under+7,x
 cmp #5
 lda under+5,x
 bcc colour_publish_flags
 ora #4
colour_publish_flags:
 sta v_flags
 ldy under+2,x
 jsr colour_publish_rect
colour_publish_next:
 lda #0
 sta under+6,x
 txa
 clc
 adc #36
 tax
 cpx #216
 bne colour_publish_actor
colour_publish_done:
 lda #0
 sta colour_count
 sta colour_full
 rts
colour_publish_full:
 ldx #48
colour_publish_full_loop:
 lda colour_work,x
 sta $9600,x
 lda colour_work+49,x
 sta $9631,x
 lda colour_work+98,x
 sta $9662,x
 lda colour_work+147,x
 sta $9693,x
 dex
 bpl colour_publish_full_loop
 /* The next restore resets old rectangles. Retaining them after a full copy
    can only cause redundant final-colour stores, including isolated callers. */
 jmp colour_publish_done

/* Y=top-left cell, v_flags=left/right/lower bits. Preserve X. */
colour_publish_rect:
 lda v_flags
 and #3
 cmp #3
 bne colour_publish_edges
 /* Fully visible two-column actors are the ordinary case. */
 lda colour_work,y
 sta $9600,y
 iny
 lda colour_work,y
 sta $9600,y
 dey
 lda v_flags
 and #4
 beq colour_publish_return
 tya
 clc
 adc #14
 tay
 lda colour_work,y
 sta $9600,y
 iny
 lda colour_work,y
 sta $9600,y
 rts
colour_publish_edges:
 jsr colour_publish_row
 lda v_flags
 and #4
 beq colour_publish_return
 tya
 clc
 adc #14
 tay
colour_publish_row:
 lda v_flags
 and #1
 beq colour_publish_right
 lda colour_work,y
 sta $9600,y
colour_publish_right:
 lda v_flags
 and #2
 beq colour_publish_return
 iny
 lda colour_work,y
 sta $9600,y
 dey
colour_publish_return:
 rts
