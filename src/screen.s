; =============================================================================
;  screen.s -- score, status line, maze setup
; =============================================================================

ROW1 = SCR_COLS                 ; offset of screen row 1
ROW23 = SCR_COLS*23             ; offset of screen row 23

t_1up:    .byte 0, 2, 1, "1UP", 0
t_hi:     .byte 0, 11, 1, "HI-SCORE", 0

.proc draw_labels
    lda #<t_1up
    sta ptr0
    lda #>t_1up
    sta ptr0+1
    jsr print
    lda #<t_hi
    sta ptr0
    lda #>t_hi
    sta ptr0+1
    jmp print
.endproc

; copy the maze into bgmap/colmap rows 2..22
.proc init_maze
    ldx #0
:   lda maze_chars,x
    sta bgmap+MAZE_ROW0*SCR_COLS,x
    lda maze_cols,x
    sta colmap+MAZE_ROW0*SCR_COLS,x
    inx
    bne :-
:   lda maze_chars+256,x
    sta bgmap+MAZE_ROW0*SCR_COLS+256,x
    lda maze_cols+256,x
    sta colmap+MAZE_ROW0*SCR_COLS+256,x
    inx
    cpx #MAZE_W*MAZE_H-256
    bne :-
    rts
.endproc

; A = low BCD byte, X = high BCD byte
.proc add_points
    sed
    clc
    adc score
    sta score
    txa
    adc score+1
    sta score+1
    lda score+2
    adc #0
    sta score+2
    cld
    lda extra_given
    bne @s
    lda score+2
    beq @s
    inc extra_given
    inc lives
    jsr draw_status
    ldx #2
    lda #SND_EXTRA
    jsr play_fx
@s: jmp draw_score
.endproc

.proc draw_score
    ; keep the high score up to date
    lda score+2
    cmp hiscore+2
    bcc @show
    bne @new
    lda score+1
    cmp hiscore+1
    bcc @show
    bne @new
    lda score
    cmp hiscore
    bcc @show
    beq @show
@new:
    lda score
    sta hiscore
    lda score+1
    sta hiscore+1
    lda score+2
    sta hiscore+2
@show:
    ldx #score+2
    ldy #1
    jsr draw_num
    ldx #hiscore+2
    ldy #12
    jmp draw_num
.endproc

; X = zero page address of the number's top BCD byte, Y = column on row 1
.proc draw_num
    sty tmp1
    lda #1
    sta tmp2                ; still blanking leading zeros
    lda #3
    sta tmp3
@b: lda $00,x
    lsr
    lsr
    lsr
    lsr
    jsr @digit
    lda $00,x
    and #$0F
    jsr @digit
    dex
    dec tmp3
    bne @b
    rts
@digit:
    bne @nz
    lda tmp2
    beq @zero
    lda tmp3
    cmp #1
    beq @zero
    lda #CH_BLANK
    jmp @put
@zero:
    lda #0
@nz:
    pha
    lda #0
    sta tmp2
    pla
    ora #$30
@put:
    ldy tmp1
    sta bgmap+ROW1,y
    sta SCREEN+ROW1,y
    inc tmp1
    rts
.endproc

; spare lives (left) and level items (right) on row 23
.proc draw_status
    ldy #1
@l: tya
    cmp lives
    bcs @blank
    cpy #6
    bcs @blank
    lda #CH_LIFE
    ldx #7
    jmp @put
@blank:
    lda #CH_BLANK
    ldx #1
@put:
    sta bgmap+ROW23,y
    sta SCREEN+ROW23,y
    txa
    sta colmap+ROW23,y
    sta COLRAM+ROW23,y
    iny
    cpy #8
    bne @l
    ; items: newest at column 19, going left
    lda level
    sta tmp0
    ldy #19
@i: lda tmp0
    bmi @iblank
    cmp #7
    bcc :+
    lda #7
:   tax
    lda item_cols,x
    sta tmp1
    txa
    clc
    adc #CH_ITEM0
    ldx tmp1
    jmp @iput
@iblank:
    lda #CH_BLANK
    ldx #1
@iput:
    sta bgmap+ROW23,y
    sta SCREEN+ROW23,y
    txa
    sta colmap+ROW23,y
    sta COLRAM+ROW23,y
    dec tmp0
    dey
    cpy #12
    bne @i
    rts
.endproc
