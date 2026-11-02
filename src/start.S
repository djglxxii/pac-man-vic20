/* Loaded temporarily into logical screen RAM. The final jump transfers all
   execution to resident code before main clears/reuses this boot image. */
.section .boot.start,"ax",@progbits
.global boot_start
boot_start:
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
  jsr platform_init
  jmp main
