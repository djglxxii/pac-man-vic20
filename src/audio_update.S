/* Exact replacement for the pooled hires audio_update C adapter.
   No arguments or return value. Reads virtual Namco registers $0340-$035f
   and enable $0301; conditionally writes pitch ports bass/soprano/alto in
   that order, then noise=0 and the enabled maximum of all three volumes.
   Sound sequencing and the 16875-cycle arcade clock are unchanged.

   llvm-mos ABI: clobbers A/X/Y, flags, __rc2..4 and audio_divider's existing
   a_* scratch. Preserves __rc0/1, __rc5..31 and all renderer state. No new
   writable allocation. Main thread, binary mode; IRQ only changes the clock
   and preserves A/X/Y. Inline voices avoid wrapper saves and extra calls. */
#if !defined(GLYPH_POOL) || defined(MULTICOLOUR)
#error "audio_update.S requires the pooled hires memory layout"
#endif
.zeropage __rc2,__rc3,__rc4
/* rc2 = low frequency byte, rc3 = maximum volume, rc4 = nibble pair. */

.section .cold,"ax",@progbits
.global audio_update,audio_fast_end

.macro VOICE number,offset,wave,port,bias
audio_fast_voice_\number\()_gate:
 .if \number == 0
  lda $0340+\offset+5
  and #15
  sta __rc3
 .else
  lda $0340+\offset+4
  and #15
  cmp __rc3
  bcc audio_fast_voice_\number\()_volume_ready
  sta __rc3
audio_fast_voice_\number\()_volume_ready:
  cmp #0
 .endif
 beq audio_fast_voice_\number\()_silent
 lda $0301
 beq audio_fast_voice_\number\()_silent

audio_fast_voice_\number\()_unpack:
 .if \number == 0
  lda $0340+\offset+4
  and #15
  bne audio_fast_voice_\number\()_saturated
 .endif
 /* Shifting the upper nibble four places discards its unused high bits. */
 lda $0340+\offset+1
 asl
 asl
 asl
 asl
 sta __rc2
 lda $0340+\offset
 and #15
 ora __rc2
 sta __rc2
 lda $0340+\offset+3
 asl
 asl
 asl
 asl
 sta __rc4
 lda $0340+\offset+2
 and #15
 ora __rc4
 tay

audio_fast_voice_\number\()_scale:
 lda $0340+\wave
 and #7
 tax
 lda audio_fast_shifts,x
 .if \bias != 0
  clc
  adc #\bias
 .endif
 tax
 tya
 cpx #0
 beq audio_fast_voice_\number\()_pitch
audio_fast_voice_\number\()_shift:
 /* Carry flows from the low-byte shift into the high byte; overflow
    saturates exactly as C's pre-shift high-bit test. */
 asl __rc2
 rol
 bcs audio_fast_voice_\number\()_saturated
 dex
 bne audio_fast_voice_\number\()_shift

audio_fast_voice_\number\()_pitch:
 tax
 ora __rc2
 beq audio_fast_voice_\number\()_silent
 lda __rc2
 jsr audio_divider
 jmp audio_fast_voice_\number\()_write
audio_fast_voice_\number\()_saturated:
 /* Exact existing divider result for the saturated phase step $ffff. */
 lda #254
 bne audio_fast_voice_\number\()_write
audio_fast_voice_\number\()_silent:
 lda #0
audio_fast_voice_\number\()_write:
 cmp $900a+\port
 beq audio_fast_voice_\number\()_end
 sta $900a+\port
audio_fast_voice_\number\()_end:
.endm

audio_update:
 VOICE 0,16,5,0,0
 VOICE 1,22,10,2,2
 VOICE 2,27,15,1,3
audio_fast_volume:
 lda #0
 sta $900d
 ldx $0301
 beq audio_fast_volume_ready
 lda __rc3
audio_fast_volume_ready:
 sta $900e
 rts
audio_fast_end:
audio_fast_shifts:
 .byte 0,0,1,0,3,4,0,1
