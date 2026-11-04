/* Original arcade effect interpreter, main thread only, binary mode.
   llvm-mos C ABI: effect = __rc2/3, frequency = __rc4/5, table = __rc6/7.
   The unused channel argument has no effect. Returns volume in A. Uses
   __rc8/10/11 as scratch; the C tail may clobber A/X/Y and __rc2..19 under
   the normal ABI. Preserves __rc0/1, __rc20..31 and renderer scratch.
   The shared C frequency/volume tail keeps song and effect envelopes identical.
   Field offsets are checked against SOUND_EFFECT by the C build below. */
.zeropage __rc2,__rc3,__rc4,__rc5,__rc6,__rc7
.zeropage __rc8,__rc10,__rc11
.set effect,__rc2
.set frequency,__rc4
.set table,__rc6
.set selected_mask,__rc8
.set source,__rc10

.section .text.sound_effect,"ax",@progbits
.global soundEffectOneChannel_2dee
soundEffectOneChannel_2dee:
 ldy #0
 lda (effect),y
 bne sfx_active
 /* Cancellation only clears fields when an effect was actually current. */
 ldy #2
 lda (effect),y
 beq sfx_zero
 lda #0
 sta (effect),y
 ldy #13
 sta (effect),y
 iny
 sta (effect),y
 iny
 sta (effect),y
 ldy #3
sfx_clear_frequency:
 sta (frequency),y
 dey
 bpl sfx_clear_frequency
sfx_zero:
 rts

sfx_active:
 /* The highest requested bit wins, as in highestSoundBit(). */
 ldx #7
sfx_priority:
 asl
 bcs sfx_selected
 dex
 bpl sfx_priority
sfx_selected:
 lda rom_32f9+($3bb0-$32f9),x
 sta selected_mask
 ldy #2
 and (effect),y
 bne sfx_duration
 lda selected_mask
 sta (effect),y
 /* Preserve the original local table-pointer advance, including a second
    selection after a repeat expires in this same call. */
 txa
 asl
 asl
 asl
 clc
 adc table
 sta table
 bcc sfx_table_ready
 inc table+1
sfx_table_ready:
 lda table
 sec
 sbc #3
 sta source
 lda table+1
 sbc #0
 sta source+1
 ldy #10
sfx_copy_definition:
 lda (source),y
 sta (effect),y
 dey
 cpy #2
 bne sfx_copy_definition
 ldy #6
 lda (effect),y
 and #127
 ldy #12
 sta (effect),y
 ldy #4
 lda (effect),y
 ldy #14
 sta (effect),y
 ldy #9
 lda (effect),y
 tax
 lsr
 lsr
 lsr
 lsr
 ldy #11
 sta (effect),y
 txa
 bmi sfx_duration
 ldy #15
 sta (effect),y
 lda #0
 ldy #13
 sta (effect),y
sfx_duration:
 ldy #12
 lda (effect),y
 sec
 sbc #1
 sta (effect),y
 beq sfx_expired
 jmp sfx_pitch
sfx_expired:
 ldy #8
 lda (effect),y
 beq sfx_reload
 sec
 sbc #1
 sta (effect),y
 bne sfx_reload
 lda selected_mask
 eor #255
 ldy #0
 and (effect),y
 sta (effect),y
 jmp soundEffectOneChannel_2dee
sfx_reload:
 ldy #6
 lda (effect),y
 and #127
 ldy #12
 sta (effect),y
 ldy #6
 lda (effect),y
 bpl sfx_envelope
 ldy #5
 lda #0
 sec
 sbc (effect),y
 sta (effect),y
 ldy #13
 lda (effect),y
 eor #1
 sta (effect),y
 and #1
 bne sfx_pitch
sfx_envelope:
 ldy #7
 lda (effect),y
 clc
 ldy #4
 adc (effect),y
 sta (effect),y
 ldy #14
 sta (effect),y
 ldy #10
 lda (effect),y
 clc
 dey
 adc (effect),y
 sta (effect),y
 tax
 ldy #11
 lda (effect),y
 and #8
 bne sfx_pitch
 txa
 ldy #15
 sta (effect),y
sfx_pitch:
 ldy #14
 lda (effect),y
 clc
 ldy #5
 adc (effect),y
 ldy #14
 sta (effect),y
 /* Frequency accumulation wraps at eight bits before the 0..7-bit scale. */
 sta source
 ldy #3
 lda (effect),y
 and #$70
 lsr
 lsr
 lsr
 lsr
 tax
 ldy #0
 sty source+1
 lda source
 cpx #0
 beq sfx_frequency_ready
sfx_scale:
 asl
 rol source+1
 dex
 bne sfx_scale
sfx_frequency_ready:
 ldx source+1
 jmp frequencyWithVolume_2ee8
