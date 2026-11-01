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
