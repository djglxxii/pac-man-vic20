/* KERNAL/BASIC are no longer used once the loader jumps here. */
.section .init.0,"ax",@progbits
  sei
  cld
  ldx #$ff
  txs
  lda #$7f
  sta $911e
  sta $912e
  lda #<__stack
  sta __rc0
  lda #>__stack
  sta __rc1
  ldx #<__zp_data_size
  beq startup_done
startup_copy:
  dex
  lda __zp_data_load_start,x
  sta __zp_data_start,x
  cpx #0
  bne startup_copy
startup_done:
  jmp main
