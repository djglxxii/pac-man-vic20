	.zeropage	__rc0
	.zeropage	__rc1
	.zeropage	__rc2
	.zeropage	__rc3
	.zeropage	__rc4
	.zeropage	__rc5
	.zeropage	__rc6
	.zeropage	__rc7
	.zeropage	__rc8
	.zeropage	__rc9
	.zeropage	__rc10
	.zeropage	__rc11
	.zeropage	__rc12
	.zeropage	__rc13
	.zeropage	__rc14
	.zeropage	__rc15
	.zeropage	__rc16
	.zeropage	__rc17
	.zeropage	__rc18
	.zeropage	__rc19
	.zeropage	__rc20
	.zeropage	__rc21
	.zeropage	__rc22
	.zeropage	__rc23
	.zeropage	__rc24
	.zeropage	__rc25
	.zeropage	__rc26
	.zeropage	__rc27
	.zeropage	__rc28
	.zeropage	__rc29
	.zeropage	__rc30
	.zeropage	__rc31
	.file	"offset-options.c"
	.section	.text.original,"ax",@progbits
	.globl	original                        ; -- Begin function original
	.type	original,@function
original:                               ; @original
; %bb.0:
	stx	__rc2
	clc
	adc	#224
	tax
	lsr	__rc2
	lda	#0
	ror
	lsr	__rc2
	ror
	lsr	__rc2
	ror
	sta	__rc3
	txa
	clc
	adc	__rc3
	tay
	lda	#0
	adc	__rc2
	tax
	clc
	tya
	adc	#64
	tay
	txa
	adc	#0
	and	#3
	tax
	tya
	rts
.Lfunc_end0:
	.size	original, .Lfunc_end0-original
                                        ; -- End function
	.section	.text.reduced,"ax",@progbits
	.globl	reduced                         ; -- Begin function reduced
	.type	reduced,@function
reduced:                                ; @reduced
; %bb.0:
	tay
	stx	__rc2
	lsr	__rc2
	lda	#0
	ror
	lsr	__rc2
	ror
	lsr	__rc2
	ror
	sta	__rc3
	clc
	tya
	adc	#224
	clc
	adc	__rc3
	tay
	lda	#0
	adc	__rc2
	tax
	clc
	tya
	adc	#64
	tay
	txa
	adc	#0
	and	#3
	tax
	tya
	rts
.Lfunc_end1:
	.size	reduced, .Lfunc_end1-reduced
                                        ; -- End function
	.section	.text.split,"ax",@progbits
	.globl	split                           ; -- Begin function split
	.type	split,@function
split:                                  ; @split
; %bb.0:
	clc
	adc	#224
	stx	__rc2
	asl	__rc2
	asl	__rc2
	asl	__rc2
	asl	__rc2
	asl	__rc2
	ldy	#0
	clc
	adc	__rc2
	sta	__rc2
	tya
	adc	#0
	sta	__rc3
	lda	__rc2
	clc
	adc	#64
	tay
	lda	__rc3
	adc	#0
	sta	__rc2
	txa
	lsr
	lsr
	lsr
	clc
	adc	__rc2
	and	#3
	tax
	tya
	rts
.Lfunc_end2:
	.size	split, .Lfunc_end2-split
                                        ; -- End function
	.section	.text.byte_add,"ax",@progbits
	.globl	byte_add                        ; -- Begin function byte_add
	.type	byte_add,@function
byte_add:                               ; @byte_add
; %bb.0:
	sta	__rc5
	stx	__rc4
	clc
	adc	#224
	sta	__rc3
	stx	__rc2
	asl	__rc2
	asl	__rc2
	asl	__rc2
	asl	__rc2
	asl	__rc2
	ldy	__rc2
	lsr	__rc4
	lsr	__rc4
	lsr	__rc4
	lda	__rc5
	clc
	adc	#32
	sta	__rc2
	cmp	__rc3
	bcc	.LBB3_2
; %bb.1:
	ldx	#0
	jmp	.LBB3_3
.LBB3_2:
	ldx	#1
.LBB3_3:
	stx	__rc3
	clc
	lda	__rc4
	adc	__rc3
	sta	__rc3
	clc
	tya
	adc	__rc2
	tay
	bcc	.LBB3_5
; %bb.4:
	ldx	#1
	jmp	.LBB3_6
.LBB3_5:
	ldx	#0
.LBB3_6:
	stx	__rc2
	clc
	lda	__rc3
	adc	__rc2
	and	#3
	tax
	tya
	rts
.Lfunc_end3:
	.size	byte_add, .Lfunc_end3-byte_add
                                        ; -- End function
	.ident	"clang version 24.0.0git (https://github.com/llvm-mos/llvm-mos a40207a371b60ff787ece46817d9c0f62eada719)"
	.section	".note.GNU-stack","",@progbits
	.addrsig
	;Declaring this symbol tells the CRT that the stack pointer needs to be initialized.
	.globl	__do_init_stack
