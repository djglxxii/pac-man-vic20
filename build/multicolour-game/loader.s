
.setcpu "6502"
src=$02
dst=$04
ref=$06
count=$08
blocks=$09
offset=$0a
.segment "LOADADDR"
.word $1201
.segment "CODE"
.word basic_end
.word 10
.byte $9e,"4621",0
basic_end: .word 0
.export loader_start
loader_start:
 sei
 cld
 ldx #$ff
 txs
 lda #$7f
 sta $911e
 sta $912e
 lda #0
 sta $900e
 lda #8
 sta $900f
 lda #<(packed_end-1)
 sta src
 lda #>(packed_end-1)
 sta src+1
 lda #$ff
 sta dst
 lda #$bf
 sta dst+1
 lda #3
 sta blocks
next_command:
 jsr get_byte
 beq block_end
 bmi copy_match
 tax
literal:
 jsr get_byte
 ldy #0
 sta (dst),y
 jsr dec_dst
 dex
 bne literal
 jmp next_command
copy_match:
 and #$7f
 clc
 adc #3
 sta count
 jsr get_byte
 sta offset
 jsr get_byte
 sta offset+1
 clc
 lda dst
 adc offset
 sta ref
 lda dst+1
 adc offset+1
 sta ref+1
match_loop:
 ldy #0
 lda (ref),y
 sta (dst),y
 jsr dec_dst
 lda ref
 bne :+
 dec ref+1
: dec ref
 dec count
 bne match_loop
 jmp next_command
block_end:
 dec blocks
 beq complete
 lda #$ff
 sta dst
 ldx blocks
 cpx #2
 bne boot_block
 lda #$7f
 bne block_address
boot_block:
 lda #$0b
block_address:
 sta dst+1
 jmp next_command
complete:
 jmp $0400
get_byte:
 ldy #0
 lda (src),y
 pha
 lda src
 bne :+
 dec src+1
: dec src
 pla
 rts
dec_dst:
 lda dst
 bne :+
 dec dst+1
: dec dst
 rts
packed:
.incbin "packed.bin"
packed_end:
