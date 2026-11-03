; =============================================================================
; VIC-20 game skeleton (ca65) - unexpanded NTSC machine
;
; Build:  cl65 -t vic20 -C vic20-asm.cfg -u __EXEHDR__ -g -Ln main.lbl -o main.prg main.s
; Run:    xvic -model vic20ntsc -memory none -autostart main.prg
; Smoke test (headless, exits with code 0 after TEST_FRAMES frames):
;         cl65 ... --asm-define TEST_FRAMES=120 ...
;         xvic -default -model vic20ntsc -memory none -console -sounddev dummy \
;              -debugcart -limitcycles 20000000 -exitscreenshot shot.png -autostart main.prg
;
; Memory layout (unexpanded):
;   $1001-$1BFF  BASIC stub + this program (must stay below $1C00, asserted at link time)
;   $1C00-$1DFF  custom characters, codes 0-63 (64 x 8 bytes)
;   $1E00-$1FF9  screen matrix (22 x 23)
;   codes 128-255 display the ROM upper-case/graphics font ("$1C00 wrap" trick)
;   $9600-$97F9  colour RAM
; =============================================================================

.import __BSS_RUN__, __BSS_SIZE__

SCREEN      = $1e00
COLOUR      = $9600
CHARSET     = $1c00
COLS        = 22
ROWS        = 23

VIC_CR5     = $9005             ; screen / charset base
VIC_RASTER  = $9004             ; raster line bits 8-1
VIC_VOLAUX  = $900e             ; aux colour (hi) / volume (lo)
VIC_BGBORD  = $900f             ; background (hi) / reverse (bit 3) / border (0-2)
VOICE_SOP   = $900c

VIA1_PA_NH  = $911f             ; VIA1 port A, no handshake (joystick up/down/left/fire)
VIA1_IER    = $911e
VIA2_PB     = $9120             ; VIA2 port B (keyboard columns, joystick right on bit 7)
VIA2_DDRB   = $9122
VIA2_T1CH   = $9125
VIA2_T1LL   = $9126
VIA2_ACR    = $912b
VIA2_IER    = $912e

IRQ_VECTOR  = $0314
KERNAL_IRQ_EXIT = $eb15         ; BIT $9124 (ack VIA2 T1), restore Y/X/A, RTI

FRAME_CYCLES = 261*65 - 2       ; NTSC frame-locked VIA timer latch ($4243)
IRQ_RASTER  = 118               ; $9004 value (line 236): just below the text window

JOY_UP      = $01
JOY_DOWN    = $02
JOY_LEFT    = $04
JOY_FIRE    = $08
JOY_RIGHT   = $80

C_BLACK = 0
C_WHITE = 1
C_RED = 2
C_CYAN = 3
C_PURPLE = 4
C_GREEN = 5
C_BLUE = 6
C_YELLOW = 7

CH_PLAYER   = 1                 ; custom character codes
CH_SPACE    = 128+32            ; ROM space via the wrap (screen code 32 + 128)

; -----------------------------------------------------------------------------
.zeropage
frame_flag: .res 1
frame_count:.res 1
joy:        .res 1
joy_tmp:    .res 1
ptr:        .res 2
aux_shadow: .res 1              ; aux colour << 4, shared by every $900E writer
px:         .res 1
py:         .res 1
sfx_timer:  .res 1

; -----------------------------------------------------------------------------
.code
start:
        sei
        cld
        lda #$7f
        sta VIA1_IER            ; disable VIA1 interrupts: RESTORE/NMI off
        sta VIA2_IER            ; disable VIA2 interrupts until the IRQ is ready

        lda #$ff                ; screen nibble $F (+$9002 bit 7 => $1E00), chars $1C00
        sta VIC_CR5
        lda #(C_BLACK << 4) | $08 | C_BLUE
        sta VIC_BGBORD          ; black background, normal mode, blue border
        lda #(C_RED << 4)
        sta aux_shadow
        lda #15
        jsr set_volume

        jsr copy_charset
        jsr clear_screen

        lda #COLS/2
        sta px
        lda #ROWS/2
        sta py
        jsr draw_player

        jsr install_irq
        cli

main_loop:
        lda frame_flag          ; wait for the frame IRQ
        beq main_loop
        lda #0
        sta frame_flag

        jsr read_joystick
        jsr update_player
        jsr update_sound

.ifdef TEST_FRAMES
        lda frame_count
        cmp #TEST_FRAMES
        bne :+
        lda #0
        sta $910f               ; VICE -debugcart: exit emulator with code 0
:
.endif
        jmp main_loop

; -----------------------------------------------------------------------------
; Frame-locked IRQ: VIA2 T1 reprogrammed to exactly one NTSC frame, started on
; a known raster line so the IRQ always fires at the same screen position.
install_irq:
        lda #<irq
        sta IRQ_VECTOR
        lda #>irq
        sta IRQ_VECTOR+1
        lda #$40
        sta VIA2_ACR            ; T1 free-running (continuous interrupts)
        lda #<FRAME_CYCLES
        sta VIA2_T1LL
:       lda VIC_RASTER          ; wait for the target line (+/- a few cycles)
        cmp #IRQ_RASTER
        bne :-
        lda #>FRAME_CYCLES
        sta VIA2_T1CH           ; latch high -> counter loaded, timer restarted
        lda #$c0
        sta VIA2_IER            ; enable VIA2 T1 interrupt only
        rts

irq:                            ; KERNAL has already pushed A, X, Y
        inc frame_count
        lda #1
        sta frame_flag
        jmp KERNAL_IRQ_EXIT     ; ack T1, pull registers, RTI (no keyboard scan)

; -----------------------------------------------------------------------------
; joy = bitmask of pressed directions (1 = pressed), see JOY_* constants
read_joystick:
        lda #$7f
        sta VIA2_DDRB           ; bit 7 input for joystick right
        lda VIA2_PB
        ldx #$ff
        stx VIA2_DDRB           ; restore (KERNAL keyboard scan expects outputs)
        and #$80
        sta joy_tmp
        lda VIA1_PA_NH
        and #%00111100          ; up, down, left, fire
        lsr a
        lsr a
        ora joy_tmp
        eor #%10001111          ; active-low -> 1 = pressed
        sta joy
        rts

; -----------------------------------------------------------------------------
update_player:
        lda frame_count
        and #3                  ; move every 4th frame
        bne @done
        lda joy
        and #JOY_UP|JOY_DOWN|JOY_LEFT|JOY_RIGHT
        beq @fire
        jsr erase_player
        lda joy
        and #JOY_UP
        beq :+
        lda py
        beq :+
        dec py
:       lda joy
        and #JOY_DOWN
        beq :+
        lda py
        cmp #ROWS-1
        bcs :+
        inc py
:       lda joy
        and #JOY_LEFT
        beq :+
        lda px
        beq :+
        dec px
:       lda joy
        and #JOY_RIGHT
        beq :+
        lda px
        cmp #COLS-1
        bcs :+
        inc px
:       jsr draw_player
@fire:  lda joy
        and #JOY_FIRE
        beq @done
        lda #12
        sta sfx_timer
@done:  rts

; ptr = SCREEN + py*22 + px  (row table lookup, no multiply)
calc_cell:
        ldy py
        lda row_lo,y
        clc
        adc px
        sta ptr
        lda row_hi,y
        adc #0
        sta ptr+1
        rts

draw_player:
        jsr calc_cell
        ldy #0
        lda #CH_PLAYER
        sta (ptr),y
        lda ptr+1               ; colour RAM: same offset, base $9600
        clc
        adc #>(COLOUR-SCREEN)
        sta ptr+1
        lda #C_YELLOW
        sta (ptr),y
        rts

erase_player:
        jsr calc_cell
        ldy #0
        lda #CH_SPACE
        sta (ptr),y
        rts

; -----------------------------------------------------------------------------
update_sound:                   ; tiny descending "zap" while sfx_timer runs
        lda sfx_timer
        beq @off
        dec sfx_timer
        asl a
        asl a
        ora #$c0
        sta VOICE_SOP
        rts
@off:   sta VOICE_SOP           ; A = 0 -> voice off
        rts

set_volume:                     ; A = 0..15, preserves the aux colour
        and #$0f
        ora aux_shadow
        sta VIC_VOLAUX
        rts

; -----------------------------------------------------------------------------
clear_screen:                   ; 506 cells = 2 x 253
        ldx #253
:       lda #CH_SPACE
        sta SCREEN-1,x
        sta SCREEN+253-1,x
        lda #C_WHITE
        sta COLOUR-1,x
        sta COLOUR+253-1,x
        dex
        bne :-
        rts

copy_charset:                   ; copy charset_data (64 chars max) to $1C00
        ldx #0
:       lda charset_data,x
        sta CHARSET,x
        inx
        cpx #charset_end-charset_data
        bne :-
        rts

; -----------------------------------------------------------------------------
.rodata
row_lo:
.repeat ROWS, i
        .byte <(SCREEN + i*COLS)
.endrep
row_hi:
.repeat ROWS, i
        .byte >(SCREEN + i*COLS)
.endrep

charset_data:
        .byte 0,0,0,0,0,0,0,0                   ; 0: blank
        .byte %00011000                         ; 1: player
        .byte %00111100
        .byte %01111110
        .byte %11011011
        .byte %11111111
        .byte %00100100
        .byte %01011010
        .byte %10100101
charset_end:

; The program (and its BSS) must end below the custom character set.
.assert __BSS_RUN__ + __BSS_SIZE__ <= CHARSET, lderror, "program overlaps CHARSET at $1C00"
