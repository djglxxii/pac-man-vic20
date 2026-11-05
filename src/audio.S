/* Exact nearest VIC divider. A/X contain a positive scaled Namco phase step.
   D >= k iff f <= floor(2*43636/(2*k-1)); seven comparisons replace a divide. */
.section .zp.bss,"aw",@nobits
a_freq: .zero 2
a_div: .zero 1
a_bit: .zero 1
.section .text.audio_divider,"ax",@progbits
.global audio_divider
audio_divider:
 sta a_freq
 stx a_freq+1
#ifdef AUDIO_DIVIDER_FAST
 /* Exact precomputed results for multiples of 128. Active-play pitches use
    this grid; other inputs retain the original nearest-divider search.
    Input: A/X = positive unsigned frequency, low/high. Output: A = pitch.
    Clobbers A/X, flags and existing a_* scratch; preserves Y and C ABI state.
    Main-thread only, binary mode. The IRQ does not use these scratch bytes. */
 and #127
 bne divider_general
 txa
 bmi divider_top
 /* X < 128. Form (frequency >> 7) using carry from the low byte. */
 asl a_freq
 rol
 tax
 lda audio_pitch_lookup,x
 rts
divider_top:
 /* Every frequency >= 32768 rounds to divider one. */
 lda #254
 rts
divider_general:
#endif
 lda #0
 sta a_div
 lda #64
 sta a_bit
divider_bit:
 ora a_div
 tax
 lda a_freq+1
 cmp divider_hi,x
 bcc divider_accept
 bne divider_next
 lda divider_lo,x
 cmp a_freq
 bcc divider_next
divider_accept:
 stx a_div
divider_next:
 lsr a_bit
 lda a_bit
 bne divider_bit
 lda a_div
 eor #255
 rts
.section .rodata.audio_dividers,"a",@progbits
divider_lo:
.set k,0
.rept 128
.if k < 2
 .byte 255
.else
 .byte (87272/(2*k-1)) & 255
.endif
.set k,k+1
.endr
#ifdef AUDIO_DIVIDER_FAST
/* No alignment padding: a possible indexed page-cross costs one cycle.
   Entry zero preserves the old kernel's result for zero, though its public
   contract and audio_update only call it with positive frequencies. */
.global audio_pitch_lookup
audio_pitch_lookup:
.set k,0
.rept 256
.if k == 0
 .byte 128
.elseif ((43636+64*k)/(128*k)) > 127
 .byte 128
.else
 .byte 255-((43636+64*k)/(128*k))
.endif
.set k,k+1
.endr
#endif
divider_hi:
.set k,0
.rept 128
.if k < 2
 .byte 255
.else
 .byte (87272/(2*k-1)) >> 8
.endif
.set k,k+1
.endr
