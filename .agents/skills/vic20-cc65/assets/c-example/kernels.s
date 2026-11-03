        .export _fill_screen, _ticks
        .interruptor tick_irq           ; called from cc65's IRQ handler chain

.bss
_ticks: .res 1

.code
; void __fastcall__ fill_screen(unsigned char code) -- code arrives in A
_fill_screen:
        ldx #253
:       sta $1e00-1,x
        sta $1e00+253-1,x
        dex
        bne :-
        rts

tick_irq:
        inc _ticks
        clc                             ; not "handled": let the KERNAL IRQ run too
        rts
