; =============================================================================
; Exact cycle measurement / performance regression test for VIC-20 code (ca65).
;
; Times one call of a routine with VIA1 Timer 2 (one-shot, counts phi2 cycles),
; then exits VICE through the debug cartridge: exit code 0 if the routine took
; <= BUDGET cycles, 1 if it was over. The measured value is also left at
; `cycles` (2 bytes) for inspection in the monitor.
;
; Build & run (example: budget 2000 cycles for spr_draw):
;   cl65 -t vic20 -C vic20-asm.cfg -u __EXEHDR__ \
;        --asm-define BUDGET=2000 -o perf.prg cycle-budget.s setup.s routine.s
;   vice-test.sh perf.prg          # PASS / FAIL (code 1)
; Tip: binary-search the budget, or temporarily `sta $910f` cycles/8, to read the
; number via the exit code (8-bit, so divide large values).
;
; Provide in another module:   perf_setup  (prepare inputs; may be an RTS)
;                              perf_target (the routine to time)
; Overhead of the measurement itself (JSR/RTS + timer reads) is subtracted.
; Runs with interrupts disabled so IRQs don't inflate the result.
; =============================================================================

.import perf_setup, perf_target
.ifndef BUDGET
BUDGET = 1000
.endif

.zeropage
cycles: .res 2
.exportzp cycles

.code
        sei
        lda #$7f
        sta $911e               ; no NMIs (RESTORE) during the measurement
        jsr perf_setup
        lda #$ff
        sta $9118               ; T2 latch low
        sta $9119               ; T2 high: load $FFFF and start one-shot count-down
        jsr perf_target
        lda $9118               ; read low first
        ldx $9119
        sta cycles
        stx cycles+1
        sec                     ; elapsed = $FFFF - count - overhead
        lda #<($ffff - OVERHEAD)
        sbc cycles
        sta cycles
        lda #>($ffff - OVERHEAD)
        sbc cycles+1
        sta cycles+1
        ; compare with BUDGET
        lda cycles+1
        cmp #>BUDGET
        bcc @pass
        bne @fail
        lda cycles
        cmp #<BUDGET
        bcc @pass
        beq @pass
@fail:  lda #1
        .byte $2c               ; skip next 2 bytes (BIT abs)
@pass:  lda #0
        sta $910f               ; VICE -debugcart exit
        jmp *

; Calibrated in VICE (xvic NTSC): an empty target (just RTS) measures 15
; cycles of JSR/RTS + timer-read overhead; 3 NOPs then measure exactly 6.
OVERHEAD = 15
