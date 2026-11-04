/* Original ghost tunnel-colour lookup, main thread only, binary mode.
   llvm-mos ABI: XYPOS.y in A, XYPOS.x in X; aux pointer in __rc2/3.
   Store 1 at aux iff logical COLOUR[tile offset] is $1b, otherwise 0.
   Offset = (((uint8_t)(x-32) << 5) + (uint8_t)(y-32) + 64) & 1023.
   Subtracting 32 from x changes the unmasked result by a multiple of 1024.
   Fold +64 into two 32-byte column tables. Keep y's byte wrap and the carry
   from the row addition before the final ten-bit wrap.
   Logical COLOUR RAM is at physical $0800 under the VIC arcade mapping.
   Clobbers A/X/Y and caller scratch __rc4/5. Preserves __rc2/3, software
   stack, callee-saved registers and renderer scratch. No new writable RAM. */
.zeropage __rc2,__rc3,__rc4,__rc5
.section .text.tile_address,"ax",@progbits
.global checkGhostEnterTunnel_205a
checkGhostEnterTunnel_205a:
 clc
 adc #224
 sta __rc4
 txa
 and #31
 tax
 lda ghost_tile_low,x
 clc
 adc __rc4
 sta __rc4
 lda ghost_tile_high,x
 adc #0
 and #3
 ora #8
 sta __rc5
 ldy #0
 lda (__rc4),y
 cmp #$1b
 bne ghost_tunnel_false
 lda #1
 bne ghost_tunnel_store
ghost_tunnel_false:
 lda #0
ghost_tunnel_store:
 sta (__rc2),y
 rts

/* Each 32-byte table stays within one page for every index 0..31. */
.section .rodata.ghost_tile_columns,"a",@progbits
.p2align 5
ghost_tile_low:
.set column,0
.rept 32
 .byte (column*32+64)&255
 .set column,column+1
.endr
ghost_tile_high:
.set column,0
.rept 32
 .byte ((column*32+64)>>8)&3
 .set column,column+1
.endr
