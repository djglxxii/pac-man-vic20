.setcpu "6502"
.segment "LOADADDR"
.word $1201
.segment "BASIC"
.word basic_end
.word 10
.byte $9e,"4621",0
basic_end: .word 0
jmp entry
.segment "CODE"
.export entry,display_ready
entry:
 sei
 cld
 lda #$7f
 sta $911e
 sta $912e
 lda #0
 sta $9002
 sta $900a
 sta $900b
 sta $900c
 sta $900d
 lda #$10
 sta $900e
 lda #$0e
 sta $900f
 ldx #0
copy:
.repeat 8,N
 lda character_data+N*256,x
 sta $1000+N*256,x
.endrepeat
 lda matrix_data,x
 sta $1800,x
 lda matrix_data+256,x
 sta $1900,x
 lda color_data,x
 sta $9400,x
 lda color_data+256,x
 sta $9500,x
 cpx #55
 bcs skip_tail
 lda matrix_data+512,x
 sta $1a00,x
 lda color_data+512,x
 sta $9600,x
skip_tail:
 inx
 bne copy
 lda #12
 sta $9000
 lda #18
 sta $9001
 lda #$ec
 sta $9005
 lda #54
 sta $9003
 lda #21
 sta $9002
display_ready:
 jmp display_ready
character_data: .incbin "charset.bin"
matrix_data: .incbin "screen.bin"
color_data: .incbin "colors.bin"
