/* Horizontal ghost rewards borrow the hidden Pac-Man actor slot. Expand
   only while building renderer caches, then restore all arcade outputs.
   Shift intervening ghost slots so both halves retain the eaten ghost's
   draw priority and reverse restoration order. No extra underlays or ZP.
   Main thread only; clobbers A/X/Y. */
.section .bss.score,"aw",@nobits
score_slot: .zero 1
score_hole: .zero 1
score_saved: .zero 20
.section .text.score,"ax",@progbits
.global score_expand,score_unexpand
score_expand:
 lda #0
 sta score_slot
 lda $0c2b
 and #31
 beq score_hole_high
 /* The arcade swaps the powered-up Pac-Man into output slot 2. */
 lda $0c23
 and #31
 bne score_expand_done
 lda #2
 bne score_hole_ready
score_hole_high:
 lda #10
score_hole_ready:
 sta score_hole
 ldx #10
score_find:
 lda $0c21,x
 and #31
 cmp #24
 bne score_find_next
 lda $0c20,x
 lsr
 lsr
 sec
 sbc #40
 cmp #4
 bcc score_found
score_find_next:
 dex
 dex
 bne score_find
score_expand_done:
 rts
score_found:
 stx score_slot
 ldx #9
score_backup:
 lda $0c22,x
 sta score_saved,x
 lda $0c32,x
 sta score_saved+10,x
 dex
 bpl score_backup
 ldx score_hole
 cpx score_slot
 bcc score_move_low_start
 dex
 dex
score_move:
 cpx score_slot
 beq score_split
 lda $0c20,x
 sta $0c22,x
 lda $0c21,x
 sta $0c23,x
 lda $0c31,x
 sta $0c33,x
 lda $0c30,x
 cpx #4
 bne score_move_x
 /* Slots 2/4 have the arcade's one-pixel horizontal origin adjustment. */
 clc
 adc #1
score_move_x:
 sta $0c32,x
 dex
 dex
 bne score_move
score_move_low_start:
 inx
 inx
score_move_low:
 cpx score_slot
 beq score_split
 lda $0c20,x
 sta $0c1e,x
 lda $0c21,x
 sta $0c1f,x
 lda $0c31,x
 sta $0c2f,x
 lda $0c30,x
 cpx #6
 bne score_move_low_x
 sec
 sbc #1
score_move_low_x:
 sta $0c2e,x
 inx
 inx
 bne score_move_low
score_split:
 txa
 tay
 cpx score_hole
 bcc score_split_high
 dey
 dey
 jmp score_split_ready
score_split_high:
 iny
 iny
score_split_ready:
 lda $0c20,x
 sta $0c20,y
 lda $0c31,x
 sta $0c31,y
 lda $0c30,x
 sec
 sbc #8
 cpx #4
 bne score_right_low
 cpy #6
 bne score_right_x
 clc
 adc #1
 jmp score_right_x
score_right_low:
 cpx #6
 bne score_right_x
 cpy #4
 bne score_right_x
 sec
 sbc #1
score_right_x:
 sta $0c30,y
 lda $0c30,x
 clc
 adc #8
 sta $0c30,x
 lda #24
 sta $0c21,x
 lda #31
 sta $0c21,y
 lda $0c20,x
 and #2
 bne score_mirror
 rts
score_mirror:
 /* Mirror the complete number by exchanging the two source halves. */
 lda #31
 sta $0c21,x
 lda #24
 sta $0c21,y
 rts
score_unexpand:
 lda score_slot
 beq score_unexpand_done
 ldx #9
score_restore:
 lda score_saved,x
 sta $0c22,x
 lda score_saved+10,x
 sta $0c32,x
 dex
 bpl score_restore
score_unexpand_done:
 rts
