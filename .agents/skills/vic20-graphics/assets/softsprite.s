; =============================================================================
; Software sprite on a character screen ("local framebuffer" method), ca65.
; One 8x8 sprite at any pixel position, built from 4 pool characters (2x2 cells).
;
;   draw:  save the 4 screen codes under the sprite, copy their 8-byte
;          definitions into the pool characters, OR the pixel-shifted sprite in,
;          put the pool codes on screen.
;   erase: put the saved codes back.
;
; Works over RAM characters and, with the $1C00 wrap layout, over ROM characters
; (codes >= 128 read from $8000). Sprite pixels take the colour of the cell they
; are in (colour clash); colour RAM is not touched.
; Several sprites: give each its own pool and save area, draw in order, and
; erase in REVERSE order so overlapping sprites restore correctly.
; Cost (measured in VICE, NTSC): ~1,850 cycles per draw when x is a multiple of
; 8, ~2,750 at a 7-pixel shift (11-16% of a frame). This version favours
; clarity: pre-shifted data removes the shift loop (up to ~900 cycles), and
; unrolled/self-modified copies roughly halve the rest. Draw during vblank or
; double-buffer the pool to avoid tearing.
;
; Tested in VICE 3.7.1 (xvic NTSC, unexpanded, screen $1E00, chars $1C00).
; Callers:  .import spr_draw, spr_erase
;           .importzp spr_x, spr_y, spr_data     ; zero-page inputs
;           set spr_x/spr_y/spr_data, jsr spr_draw ... jsr spr_erase
; Limits: x 0-168, y 0-168 (the 2x2 block must stay on the 22x23 screen).
; =============================================================================

.export spr_draw, spr_erase, spr_x, spr_y, spr_data

SCREEN  = $1e00
CHARSET = $1c00
COLS    = 22
POOL    = 60            ; pool character codes POOL..POOL+3 (must be < 64 here)
POOLMEM = CHARSET + POOL*8
; pool layout: left column = TL (POOL), BL (POOL+1); right = TR (POOL+2), BR (POOL+3)

.zeropage
spr_x:     .res 1       ; inputs
spr_y:     .res 1
spr_data:  .res 2       ; pointer to 8 bytes of sprite pixels
scr_ptr:   .res 2
src_ptr:   .res 2
shift:     .res 1
row:       .res 1
tmp_hi:    .res 1
tmp_lo:    .res 1

.bss
saved:     .res 4       ; screen codes under TL, TR, BL, BR

.code
spr_draw:
        ; --- cell pointer: SCREEN + (y>>3)*22 + (x>>3) ---
        lda spr_y
        lsr a
        lsr a
        lsr a
        tay
        lda spr_x
        lsr a
        lsr a
        lsr a
        clc
        adc row_lo,y
        sta scr_ptr
        lda row_hi,y
        adc #0
        sta scr_ptr+1
        ; --- save codes and copy their definitions into the pool ---
        ldx #3
@cell:  ldy cell_off,x
        lda (scr_ptr),y
        sta saved,x
        jsr char_addr           ; A = code -> src_ptr
        ldy #7
        lda pool_off,x
        clc
        adc #7
        sta row                 ; destination index (pool_off + 7)
@cp:    lda (src_ptr),y
        sty tmp_lo
        ldy row
        sta POOLMEM,y
        dec row
        ldy tmp_lo
        dey
        bpl @cp
        dex
        bpl @cell
        ; --- OR the shifted sprite in ---
        lda spr_x
        and #7
        sta shift
        lda spr_y
        and #7
        tax                     ; X = destination row in the left column (0-15)
        ldy #0
@row:   lda (spr_data),y
        sta tmp_hi
        lda #0
        sta tmp_lo
        lda shift
        beq @noshift
        sty row
        tay
@sh:    lsr tmp_hi
        ror tmp_lo
        dey
        bne @sh
        ldy row
@noshift:
        lda tmp_hi
        ora POOLMEM,x
        sta POOLMEM,x
        lda tmp_lo
        ora POOLMEM+16,x
        sta POOLMEM+16,x
        inx
        iny
        cpy #8
        bne @row
        ; --- show the pool characters ---
        ldx #3
@show:  ldy cell_off,x
        lda pool_code,x
        sta (scr_ptr),y
        dex
        bpl @show
        rts

spr_erase:                      ; restore the 4 cells saved by the last spr_draw
        ldx #3
@r:     ldy cell_off,x
        lda saved,x
        sta (scr_ptr),y
        dex
        bpl @r
        rts

; A = character code -> src_ptr = address of its definition (clobbers A)
char_addr:
        ldy #0
        sty tmp_hi
        cmp #128
        bcc @ram
        and #$7f                ; codes 128-255: ROM font via the $1C00 wrap
        ldy #>$8000
        bne @mul                ; always
@ram:   ldy #>CHARSET
@mul:   asl a
        rol tmp_hi
        asl a
        rol tmp_hi
        asl a
        rol tmp_hi
        sta src_ptr
        tya
        clc
        adc tmp_hi
        sta src_ptr+1
        rts

.rodata
cell_off:  .byte 0, 1, COLS, COLS+1                 ; TL, TR, BL, BR
pool_off:  .byte 0, 16, 8, 24                       ; their bytes inside the pool
pool_code: .byte POOL, POOL+2, POOL+1, POOL+3
row_lo:
.repeat 23, i
        .byte <(SCREEN + i*COLS)
.endrep
row_hi:
.repeat 23, i
        .byte >(SCREEN + i*COLS)
.endrep
