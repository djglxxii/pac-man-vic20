/* VIA2 T1 generates the original arcade's 60.606 Hz game clock.
   The VIC KERNAL's hardware IRQ entry saves A/X/Y and jumps through $0314. */
.section .zp.bss,"aw",@nobits
.global clock_ticks
clock_ticks: .zero 1
.section .text.clock,"ax",@progbits
.global clock_init
clock_init:
 sei
 lda #<clock_irq
 sta $0314
 lda #>clock_irq
 sta $0315
 lda #0
 sta clock_ticks
 lda #$40
 sta $912b
 /* NTSC Phi2 = 1022727 Hz; T1 period = latch + 2 = 16875 cycles. */
 lda #<$41e9
 sta $9124
 lda #>$41e9
 sta $9125
 lda #$c0
 sta $912e
 cli
 rts
clock_irq:
 lda $9124
 inc clock_ticks
 pla
 tay
 pla
 tax
 pla
 rti
