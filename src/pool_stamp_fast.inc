/* Generic hidden-glyph stamper. Entry: v_data=12 source rows, v_shift=0..7,
   v_flip bit 0 reverses rows and bit 1 mirrors bits, v_sy selects glyph row;
   v_addr/v_right/v_save/v_saved_right are the four prepared destinations.
   Clobbers A/X/Y and existing v_* scratch; no extra RAM or IRQ work.
   Self-modified operands belong only to this main-thread renderer.

   Dispatch directly to a shift kernel, retain one half in A for merging,
   and use the source index as the row counter. Four/five-pixel phases split
   with accumulator shifts rather than rotating a two-byte value repeatedly.
   Cell allocation, clipping sinks and publication are unchanged. */
 lda v_data
 sta pool_fetch+1
 lda v_data+1
 sta pool_fetch+2
 lda v_shift
 asl
 tax
 lda pool_shifts,x
 sta pool_mirror+1
 sta pool_reverse_done+1
 lda pool_shifts+1,x
 sta pool_mirror+2
 sta pool_reverse_done+2
 lda v_flip
 and #2
 beq pool_mirror_ready
 lda #<pool_reverse
 sta pool_mirror+1
 lda #>pool_reverse
 sta pool_mirror+2
pool_mirror_ready:
 ldx #0
 ldy #12
 lda #$e8
 lsr v_flip
 bcc pool_source_ready
 ldx #11
 ldy #255
 lda #$ca
pool_source_ready:
 sta pool_step
 sty pool_row_end+1
 lda v_sy
 and #15
 tay
pool_row:
pool_fetch:
 lda $ffff,x
 beq pool_step
pool_mirror:
 jmp pool_shift_0
/* A=right half; v_hi=left half. OR is commutative even if both clipped
   pointers name the sink. No intermediate right-half store/reload. */
pool_merge_low:
 ora (v_right),y
 sta (v_right),y
 lda v_hi
 ora (v_addr),y
 sta (v_addr),y
pool_step:
 inx
pool_row_end:
 cpx #12
 beq pool_draw_done
 iny
 cpy #16
 bne pool_row
 lda v_save
 sta v_addr
 lda v_save+1
 sta v_addr+1
 lda v_saved_right
 sta v_right
 lda v_saved_right+1
 sta v_right+1
 ldy #0
 beq pool_row
pool_draw_done:
 rts
/* A=left half; v_lo=right half. */
pool_merge_high:
 ora (v_addr),y
 sta (v_addr),y
 lda v_lo
 ora (v_right),y
 sta (v_right),y
 jmp pool_step
pool_reverse:
 sty v_row
 tay
 lda bit_reverse,y
 ldy v_row
pool_reverse_done:
 jmp pool_shift_0
pool_shift_0:
 ora (v_addr),y
 sta (v_addr),y
 jmp pool_step
pool_shift_1:
#ifdef POOL_SHIFT_FAST
 /* First shift in A: preserve its carry while storing the shifted half.
    Same halves as the zero-page RMW path, three cycles and one byte less. */
 lsr
 sta v_hi
 lda #0
#else
 sta v_hi
 lda #0
 lsr v_hi
#endif
 ror
 jmp pool_merge_low
pool_shift_2:
#ifdef POOL_SHIFT_FAST
 /* First shift in A: preserve its carry while storing the shifted half.
    Same halves as the zero-page RMW path, three cycles and one byte less. */
 lsr
 sta v_hi
 lda #0
#else
 sta v_hi
 lda #0
 lsr v_hi
#endif
 ror
 lsr v_hi
 ror
 jmp pool_merge_low
pool_shift_3:
#ifdef POOL_SHIFT_FAST
 /* First shift in A: preserve its carry while storing the shifted half.
    Same halves as the zero-page RMW path, three cycles and one byte less. */
 lsr
 sta v_hi
 lda #0
#else
 sta v_hi
 lda #0
 lsr v_hi
#endif
 ror
 lsr v_hi
 ror
 lsr v_hi
 ror
 jmp pool_merge_low
pool_shift_4:
 sta v_hi
 asl
 asl
 asl
 asl
 sta v_lo
 lda v_hi
 lsr
 lsr
 lsr
 lsr
 jmp pool_merge_high
pool_left_3:
 sta v_lo
 lsr
 lsr
 lsr
 lsr
 lsr
 sta v_hi
 lda v_lo
 asl
 asl
 asl
 jmp pool_merge_low
pool_left_2:
#ifdef POOL_SHIFT_FAST
 /* First shift in A: preserve its carry while storing the shifted half.
    Same halves as the zero-page RMW path, three cycles and one byte less. */
 asl
 sta v_lo
 lda #0
#else
 sta v_lo
 lda #0
 asl v_lo
#endif
 rol
 asl v_lo
 rol
 jmp pool_merge_high
pool_left_1:
#ifdef POOL_SHIFT_FAST
 /* First shift in A: preserve its carry while storing the shifted half.
    Same halves as the zero-page RMW path, three cycles and one byte less. */
 asl
 sta v_lo
 lda #0
#else
 sta v_lo
 lda #0
 asl v_lo
#endif
 rol
 jmp pool_merge_high
pool_shifts:
.word pool_shift_0,pool_shift_1,pool_shift_2,pool_shift_3
.word pool_shift_4,pool_left_3,pool_left_2,pool_left_1
