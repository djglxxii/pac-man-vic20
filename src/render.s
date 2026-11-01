; =============================================================================
;  render.s -- soft-sprite compositor
;
;  Each frame, every visible actor is drawn into "dynamic" characters taken
;  from the pool that is NOT currently on screen.  For every screen cell an
;  actor touches, a dynamic char is allocated (once per cell per frame), the
;  background tile's bitmap is copied into it and the actor's pre-shifted
;  image is merged in with  (bg AND NOT mask) OR image.  At the bottom of the
;  next frame, flip() points the screen cells at the new chars, restores
;  cells that are no longer covered, and swaps pools.
;
;  Pre-shifted image layout: one 256-byte page per image; for shift s
;  (0..7) at offset s*32:  +0 left bytes[8], +8 right bytes[8],
;  +16 left and-mask[8], +24 right and-mask[8]
; =============================================================================

; ----------------------------------------------------------------- shifts
.proc gen_shifts
    lda #<sprite_src
    sta ptr0
    lda #>sprite_src
    sta ptr0+1
    lda #0
    sta g_img
@img:
    ldx g_img
    lda img_page,x
    sta ptrD+1
    lda #0
    sta ptrD
    sta g_s
@shift:
    lda #0
    sta g_r
@row:
    ; image data
    ldy g_r
    lda (ptr0),y
    sta g_hi
    lda #0
    sta g_lo
    ldx g_s
    beq @d0
@ds:
    lsr g_hi
    ror g_lo
    dex
    bne @ds
@d0:
    lda g_s
    asl
    asl
    asl
    asl
    asl
    clc
    adc g_r
    sta tmp2                ; offset of left data byte
    tay
    lda g_hi
    sta (ptrD),y
    tya
    clc
    adc #8
    tay
    lda g_lo
    sta (ptrD),y
    ; mask
    lda g_r
    clc
    adc #8
    tay
    lda (ptr0),y
    sta g_hi
    lda #0
    sta g_lo
    ldx g_s
    beq @m0
@ms:
    lsr g_hi
    ror g_lo
    dex
    bne @ms
@m0:
    lda tmp2
    clc
    adc #16
    tay
    lda g_hi
    eor #$FF
    sta (ptrD),y
    tya
    clc
    adc #8
    tay
    lda g_lo
    eor #$FF
    sta (ptrD),y
    inc g_r
    lda g_r
    cmp #8
    beq :+
    jmp @row
:   inc g_s
    lda g_s
    cmp #8
    beq :+
    jmp @shift
:
    lda ptr0
    clc
    adc #16
    sta ptr0
    bcc :+
    inc ptr0+1
:   inc g_img
    lda g_img
    cmp #NUM_IMAGES
    beq :+
    jmp @img
:   rts
.endproc

.proc clear_ovl
    lda #0
    tax
:   sta ovl,x
    sta ovl+256,x
    inx
    bne :-
    sta new_n
    sta old_n
    rts
.endproc

; ----------------------------------------------------------------- compose
.proc compose
    ldx #0
@l: lda act_img,x
    cmp #$FF
    beq @n
    stx r_act
    jsr draw_actor
    ldx r_act
@n: inx
    cpx #MAXACT
    bne @l
    rts
.endproc

; X = actor slot
.proc draw_actor
    lda act_col,x
    sta r_color
    lda act_img,x
    tay
    lda img_page,y
    sta r_srch
    lda act_x,x
    and #7
    sta r_sx
    asl
    asl
    asl
    asl
    asl
    sta r_srcl
    lda act_x,x
    lsr
    lsr
    lsr
    sta r_col0
    clc
    adc #1
    cmp #SCR_COLS
    bcc :+
    lda #0
:   sta r_col1
    lda act_y,x
    and #7
    sta r_sy
    lda act_y,x
    lsr
    lsr
    lsr
    clc
    adc #MAZE_ROW0
    sta r_row
    ; top-left
    lda r_col0
    jsr cell_get
    bcs :+
    lda #0
    jsr draw_top
:   lda r_sx
    beq @noright
    lda r_col1
    jsr cell_get
    bcs @noright
    lda #8
    jsr draw_top
@noright:
    lda r_sy
    beq @done
    inc r_row
    lda r_col0
    jsr cell_get
    bcs :+
    lda #0
    jsr draw_bot
:   lda r_sx
    beq @done
    lda r_col1
    jsr cell_get
    bcs @done
    lda #8
    jsr draw_bot
@done:
    rts
.endproc

; A = half offset (0 left / 8 right).  Sprite rows 0..7-sy -> char rows sy..7
.proc draw_top
    clc
    adc r_srcl
    sta ptrS
    clc
    adc #16
    sta ptrM
    lda r_srch
    sta ptrS+1
    sta ptrM+1
    lda ptrD
    clc
    adc r_sy
    sta ptrD
    lda #7
    sec
    sbc r_sy
    tay
@l: lda (ptrD),y
    and (ptrM),y
    ora (ptrS),y
    sta (ptrD),y
    dey
    bpl @l
    rts
.endproc

; A = half offset.  Sprite rows 8-sy..7 -> char rows 0..sy-1
.proc draw_bot
    clc
    adc r_srcl
    adc #8
    sec
    sbc r_sy
    sta ptrS
    clc
    adc #16
    sta ptrM
    lda r_srch
    sta ptrS+1
    sta ptrM+1
    ldy r_sy
    dey
@l: lda (ptrD),y
    and (ptrM),y
    ora (ptrS),y
    sta (ptrD),y
    dey
    bpl @l
    rts
.endproc

; A = screen column, r_row = screen row.
; Out: ptrD -> dynamic char bitmap for that cell (allocated + background
; copied on first use this frame), C=0.  C=1 if out of dynamic chars.
.proc cell_get
    ldy r_row
    clc
    adc srow_lo,y
    tax
    lda srow_hi,y
    adc #0
    bne @hi
    ; ---- cells 0..255
    lda ovl,x
    bne @have
    ldy new_n
    cpy #MAXDYN
    bcs @full
    txa
    sta new_lo,y
    lda #0
    sta new_hi,y
    iny
    tya
    sta ovl,x
    sty new_n
    dey
    lda bgmap,x
    jmp @alloc
@hi:
    ; ---- cells 256..
    lda ovl+256,x
    bne @have
    ldy new_n
    cpy #MAXDYN
    bcs @full
    txa
    sta new_lo,y
    lda #1
    sta new_hi,y
    iny
    tya
    sta ovl+256,x
    sty new_n
    dey
    lda bgmap+256,x
@alloc:
    ; A = background char, Y = dynamic index
    tax
    lda chlo,x
    sta ptr0
    lda chhi,x
    sta ptr0+1
    lda r_color
    sta new_col,y
    tya
    clc
    adc poolbase
    tax
    lda chlo,x
    sta ptrD
    lda chhi,x
    sta ptrD+1
    ldy #7
:   lda (ptr0),y
    sta (ptrD),y
    dey
    bpl :-
    clc
    rts
@have:
    tay
    dey
    lda r_color
    sta new_col,y
    tya
    clc
    adc poolbase
    tax
    lda chlo,x
    sta ptrD
    lda chhi,x
    sta ptrD+1
    clc
    rts
@full:
    sec
    rts
.endproc

; ----------------------------------------------------------------- flip
; Called right after the raster leaves the display.
.proc flip
    ; 1) restore cells shown last frame that are not covered now
    ldy old_n
    beq @new
@rl:
    dey
    ldx old_lo,y
    lda old_hi,y
    bne @rhi
    lda ovl,x
    bne @rn
    lda bgmap,x
    sta SCREEN,x
    lda colmap,x
    sta COLRAM,x
    jmp @rn
@rhi:
    lda ovl+256,x
    bne @rn
    lda bgmap+256,x
    sta SCREEN+256,x
    lda colmap+256,x
    sta COLRAM+256,x
@rn:
    tya
    bne @rl
@new:
    ; 2) show the new cells, clear the overlay map, keep list as "old"
    ldy #0
    cpy new_n
    beq @done
@nl:
    lda new_lo,y
    sta old_lo,y
    tax
    lda new_hi,y
    sta old_hi,y
    bne @nhi
    tya
    clc
    adc poolbase
    sta SCREEN,x
    lda new_col,y
    sta COLRAM,x
    lda #0
    sta ovl,x
    jmp @nn
@nhi:
    tya
    clc
    adc poolbase
    sta SCREEN+256,x
    lda new_col,y
    sta COLRAM+256,x
    lda #0
    sta ovl+256,x
@nn:
    iny
    cpy new_n
    bne @nl
@done:
    sty old_n
    lda #0
    sta new_n
    lda poolbase
    eor #(POOL_A ^ POOL_B)
    sta poolbase
    rts
.endproc

; ----------------------------------------------------------------- bg cells
; cptr -> bgmap cell.  A = char, X = colour.  Updates bgmap/colmap and the
; visible screen unless an actor currently covers the cell (flip restores it).
.proc put_bg
    sta pb_ch
    stx pb_col
    ldy #0
    sta (cptr),y
    lda cptr+1
    sta pb_hi
    clc
    adc #>(colmap-bgmap)
    sta cptr+1
    txa
    sta (cptr),y
    lda pb_hi
    clc
    adc #>(SCREEN-bgmap)
    sta cptr+1
    lda (cptr),y
    cmp #CH_DYN0
    bcs @skip
    lda pb_ch
    sta (cptr),y
    lda pb_hi
    clc
    adc #>(COLRAM-bgmap)
    sta cptr+1
    lda pb_col
    sta (cptr),y
@skip:
    lda pb_hi
    sta cptr+1
    rts
.endproc

; copy whole bgmap/colmap to the screen (drops any visible sprites)
.proc redraw
    ldx #0
:   lda bgmap,x
    sta SCREEN,x
    lda colmap,x
    sta COLRAM,x
    inx
    bne :-
:   lda bgmap+256,x
    sta SCREEN+256,x
    lda colmap+256,x
    sta COLRAM+256,x
    inx
    cpx #SCR_COLS*SCR_ROWS-256
    bne :-
    lda #0
    sta old_n
    rts
.endproc

.proc clear_bgmap
    ldx #0
:   lda #CH_BLANK
    sta bgmap,x
    sta bgmap+256,x
    lda #1
    sta colmap,x
    sta colmap+256,x
    inx
    bne :-
    rts
.endproc

; ptr0 -> .byte row, col, colour, "text", 0
.proc print
    ldy #0
    lda (ptr0),y
    tax
    iny
    lda (ptr0),y
    clc
    adc srow_lo,x
    sta cptr
    lda srow_hi,x
    adc #>bgmap
    sta cptr+1
    iny
    lda (ptr0),y
    sta p_color
    lda ptr0
    clc
    adc #3
    sta ptr0
    bcc @l
    inc ptr0+1
@l: ldy #0
    lda (ptr0),y
    beq @done
    ldx p_color
    jsr put_bg
    inc cptr
    bne :+
    inc cptr+1
:   inc ptr0
    bne @l
    inc ptr0+1
    jmp @l
@done:
    rts
.endproc
