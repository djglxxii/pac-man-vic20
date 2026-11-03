; =============================================================================
; Stable (cycle-exact) raster IRQ for the NTSC VIC-20 (MOS 6560-101), ca65.
; Ported from Mike's selectable NTSC/PAL routine ("Stable rasters on the VIC-20",
; Denial forum t=10739), which follows Marko Makela's VIA-timer method.
;
; Tested in VICE 3.7.1 (xvic, NTSC): screenshots of a mid-line colour change
; are pixel-identical across frames; the same code without the jitter slide
; is not.
;
; How it works
;  1. Sync: poll $9004 several times with shrinking uncertainty (7 -> 3 -> 1 -> 0
;     cycles) until the CPU is at a known cycle relative to the raster.
;  2. Start VIA2 T1 with a one-frame period (261*65-2 = $4243). The IRQ then
;     fires at the same beam position every frame.
;  3. In the IRQ, read the T1 low byte ($9124) to learn the 0-8 cycles of
;     interrupt latency, and branch into a chain of LDA #$A9 opcodes at a
;     matching offset (self-modified BCC) so that every path exits on the
;     same cycle.
;
; Rules (from Mike):
;  * No IRQ/NMI may occur during sync (SEI; disable RESTORE: $911E = $7F).
;  * The sync code and the server must each stay inside one page (a taken branch
;    across a page costs an extra cycle). The asserts below enforce it; if
;    one fires, move the code or pad before it.
;  * Keep the first $9004 check: it avoids a race condition.
;  * Adjust horizontal position with POS (init), not after the slide.
;
; PAL 6561 values (untested here): FRAME = 312*71-2 ($5686), LINE = 30,
; PHASE = 88, DELAY = 23, POS = 1; drop the two NTSC-only NOPs after the
; POS loop and add a NOP before the RTS in the delay subroutine.
; =============================================================================

FRAME   = 261*65-2      ; $4243 NTSC frame period for the VIA (-2 = reload overhead)
LINE    = 17            ; sync on $9004 = 17 (raster line 34); the IRQ fires here each frame
PHASE   = 21            ; latency calibration for the slide
DELAY   = 21            ; sync helper delay
POS     = 5             ; horizontal fine position of the IRQ

.export init_raster

.code
; Call with interrupts in any state; returns with interrupts enabled.
init_raster:
        sei
        lda #<raster_irq
        sta $0314
        lda #>raster_irq
        sta $0315
        lda #<FRAME
        sta $9124               ; T1 latch low
        ldy #LINE
@i0:    cpy $9004
        bne @i0
        iny
        iny
@i1:    cpy $9004
        bne @i1
        jsr @wait
        iny
        cpy $9004
        beq @i2
        nop
        nop
@i2:    jsr @wait
        nop
        iny
        cpy $9004
        beq @i3
        bit $24
@i3:    jsr @wait
        nop
        iny
        cpy $9004
        bne @i4
@i4:    ldx #POS
@i5:    dex
        bne @i5
        nop                     ; NTSC only
        nop                     ; NTSC only
        lda #>FRAME
        sta $9125               ; load + start T1, synchronised to the beam
        cli
        rts
@wait:  ldx #DELAY
@w:     dex
        bne @w
        rts
init_end:
.assert >init_raster = >(init_end-1), error, "stable raster sync code crosses a page"

raster_irq:                     ; entered via $FF72 -> JMP ($0314); A/X/Y already saved
        cld
        sec
        lda #PHASE
        sbc $9124               ; also acknowledges the T1 interrupt
        cmp #10
        bcc @ok
        jmp $eabf               ; not ours / out of range: normal IRQ
@ok:    sta @slide+1            ; self-modify the branch offset
@slide: bcc @slide              ; always taken (C=0)
        lda #$a9
        lda #$a9
        lda #$a9
        lda #$a9
        lda #$a5
        nop
slide_end:
.assert >raster_irq = >(slide_end-1), error, "raster server crosses a page"

        ; ---------------- cycle-exact from here ----------------
        ; Example effect: switch $900F (background/border) mid-line, hold it for
        ; about 30 raster lines, then restore it. Replace with your own
        ; cycle-counted register writes (65 cycles per NTSC line).
        lda $900f
        tax
        lda #$2a                ; red background + red border
        sta $900f
        ldy #30
@d:     lda #12
        sec
@dl:    sbc #1
        bne @dl
        dey
        bne @d
        stx $900f
        ; Chain to the KERNAL (keyboard scan, jiffy clock, exit via $EB15).
        ; In a game use your own work here and exit with JMP $EB18 instead:
        ; reading $9124 above already acknowledged the timer.
        jmp $eabf
