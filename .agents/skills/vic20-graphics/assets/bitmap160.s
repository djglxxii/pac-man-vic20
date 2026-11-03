; =============================================================================
; 160x192 two-colour "bitmap" for the VIC-20 (Mike's MINIGRAFIK layout), ca65.
; Requires +8K or more: the whole of $1000-$1FFF becomes the display, so code
; must live in expansion RAM (use vic20-8k-split.cfg or vic20-asm-32k.cfg with
; code above $2000).
;
;   $1000-$10EF  screen matrix: 20 x 12 cells of 8x16 chars, codes $10-$FF in
;                COLUMN-MAJOR order (cell col,row holds $10 + col*12 + row)
;   $1100-$1FFF  bitmap = char definitions: byte = $1100 + (x>>3)*192 + y,
;                bit = $80 >> (x & 7)
;   $9400-$94EF  colour RAM (one colour per 8x16 cell)
;
; Tested in VICE 3.7.1 (xvic NTSC, +8K).
; =============================================================================

.export bmp_init, bmp_clear, bmp_plot, bmp_unplot, bmp_colour

BITMAP  = $1100
MATRIX  = $1000
COLRAM  = $9400

.zeropage
bmp_ptr:  .res 2
bmp_ytmp: .res 1

.code
; A = foreground colour (0-7) for every cell; sets up VIC registers, clears.
bmp_init:
        pha
        ; --- screen matrix, column-major codes ---
        lda #<MATRIX
        sta bmp_ptr
        lda #>MATRIX
        sta bmp_ptr+1
        ldx #0                  ; row
@row:   txa
        clc
        adc #$10                ; code of (col 0, row)
        ldy #0
@col:   sta (bmp_ptr),y
        clc
        adc #12                 ; next column = +12 codes
        iny
        cpy #20
        bne @col
        lda bmp_ptr
        clc
        adc #20
        sta bmp_ptr
        bcc :+
        inc bmp_ptr+1
:       inx
        cpx #12
        bne @row
        ; --- VIC registers: origin from the KERNAL's own NTSC/PAL table at $EDE4 ---
        lda $ede4
        clc
        adc #2                  ; X origin +2 (4-px units) centres 20 columns instead of 22
        sta $9000
        lda $ede5
        sec
        sbc #2                  ; Y origin -2 (2-line units): 192 lines instead of 184
        sta $9001
        lda #20                 ; 20 columns, bit 7 = 0 -> colour RAM $9400, screen bit 9 = 0
        sta $9002
        lda #(12 << 1) | 1      ; 12 rows, 8x16 characters
        sta $9003
        lda #$cc                ; screen $1000, characters $1000
        sta $9005
        pla
        jsr bmp_colour
        ; fall through
bmp_clear:                      ; clear $1100-$1FFF (15 pages)
        lda #<BITMAP
        sta bmp_ptr
        lda #>BITMAP
        sta bmp_ptr+1
        lda #0
        tay
        ldx #15
@pg:    sta (bmp_ptr),y
        iny
        bne @pg
        inc bmp_ptr+1
        dex
        bne @pg
        rts

bmp_colour:                     ; A = colour for all 240 cells
        ldx #240
:       sta COLRAM-1,x
        dex
        bne :-
        rts

; X = x (0-159), Y = y (0-191). Clobbers A, X, Y.
bmp_plot:
        jsr bmp_addr
        ora (bmp_ptr),y
        sta (bmp_ptr),y
        rts

bmp_unplot:
        jsr bmp_addr
        eor #$ff
        and (bmp_ptr),y
        sta (bmp_ptr),y
        rts

; -> bmp_ptr = column base, Y = y, A = bit mask
bmp_addr:
        sty bmp_ytmp
        txa
        lsr a
        lsr a
        lsr a
        tay
        lda col_lo,y
        sta bmp_ptr
        lda col_hi,y
        sta bmp_ptr+1
        txa
        and #7
        tax
        lda bit_mask,x
        ldy bmp_ytmp
        rts

.rodata
col_lo:
.repeat 20, i
        .byte <(BITMAP + i*192)
.endrep
col_hi:
.repeat 20, i
        .byte >(BITMAP + i*192)
.endrep
bit_mask:
        .byte $80, $40, $20, $10, $08, $04, $02, $01
