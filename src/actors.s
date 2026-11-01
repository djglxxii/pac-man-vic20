; =============================================================================
;  actors.s -- player and enemy logic
;
;  Positions are maze pixels (tile * 8), x wraps at 168 through the tunnel.
;  Speeds are 8.8 fixed point pixels per frame; the fraction accumulates in
;  pacc/eacc, so movement is fully deterministic: identical joystick input
;  always produces an identical game.
; =============================================================================

; ----------------------------------------------------------------- maze query
; tile_open: is the tile next to (q_c,q_r) in direction q_d walkable?
; Z=1 if open.  Preserves X.
.proc tile_open
    ldy q_d
    lda q_c
    clc
    adc dx_tab,y
    bpl :+
    lda #MAZE_W-1
:   cmp #MAZE_W
    bcc :+
    lda #0
:   sta tmp3
    lda q_r
    clc
    adc dy_tab,y
    tay
    lda arow_lo,y
    sta tptr
    lda arow_hi,y
    sta tptr+1
    ldy tmp3
    lda (tptr),y
    and #3
    rts
.endproc

; cptr -> bgmap cell of maze tile (A=col, Y=row)
.proc maze_cell
    clc
    adc bgrow_lo,y
    sta cptr
    lda bgrow_hi,y
    adc #0
    sta cptr+1
    rts
.endproc

; ----------------------------------------------------------------- player
.proc player_update
    lda ppause
    beq @go
    dec ppause
    rts
@go:
    ldx lvidx
    lda ftimer
    ora ftimer+1
    beq @norm
    lda plf_spd,x
    jmp @s
@norm:
    lda pl_spd,x
@s: clc
    adc pacc
    sta pacc
    bcc @r
    jmp player_step
@r: rts
.endproc

.proc player_step
    ; ---- steering
    lda pwant
    bmi @move
    cmp pdir
    beq @move
    eor #2
    cmp pdir
    bne @perp
    lda pwant               ; reverse: always allowed
    sta pdir
    jmp @move
@perp:
    lda pdir
    and #1
    bne @h
    lda py
    jmp @o
@h: lda px
@o: and #7
    cmp #4                  ; cannot corner exactly between tiles
    beq @move
    jsr player_tile_calc
    lda pt_c
    sta q_c
    lda pt_r
    sta q_r
    lda pwant
    sta q_d
    jsr tile_open
    bne @move
    lda pwant
    sta pdir
@move:
    ; ---- blocked?
    lda px
    ora py
    and #7
    bne @step
    lda px
    lsr
    lsr
    lsr
    sta q_c
    lda py
    lsr
    lsr
    lsr
    sta q_r
    lda pdir
    sta q_d
    jsr tile_open
    beq @step
    lda #0
    sta pmoving
    rts
@step:
    lda #1
    sta pmoving
    ldx pdir
    lda px
    clc
    adc dx_tab,x
    sta px
    lda py
    clc
    adc dy_tab,x
    sta py
    ; ---- pull the other axis toward the tile centre (cornering)
    txa
    and #1
    bne @cy
    lda px
    and #7
    beq @wrap
    cmp #4
    bcc :+
    inc px
    jmp @wrap
:   dec px
    jmp @wrap
@cy:
    lda py
    and #7
    beq @wrap
    cmp #4
    bcc :+
    inc py
    jmp @wrap
:   dec py
@wrap:
    lda px
    cmp #$FF
    bne :+
    lda #167
    sta px
    jmp @eat
:   cmp #168
    bne @eat
    lda #0
    sta px
@eat:
    inc panim
    jsr player_tile_calc
    lda pt_c
    ldy pt_r
    jsr maze_cell
    ldy #0
    lda (cptr),y
    cmp #CH_DOT
    beq @dot
    cmp #CH_HONEY
    beq @honey
    rts
@dot:
    lda #CH_BLANK
    ldx #1
    jsr put_bg
    lda #$10
    ldx #$00
    jsr add_points
    lda #1
    sta ppause
    jsr chomp_sound
    jmp ate_something
@honey:
    lda #CH_BLANK
    ldx #1
    jsr put_bg
    lda #$50
    ldx #$00
    jsr add_points
    lda #3
    sta ppause
    jsr start_fright
    jmp ate_something
.endproc

.proc ate_something
    dec dots_left
    inc dots_eaten
    inc reldots
    lda #0
    sta reltimer
    lda dots_eaten
    cmp #60
    beq @bonus
    cmp #140
    beq @bonus
    rts
@bonus:
    jmp bonus_show
.endproc

; pt_c/pt_r = tile under the player's centre
.proc player_tile_calc
    lda px
    clc
    adc #4
    lsr
    lsr
    lsr
    cmp #MAZE_W
    bcc :+
    lda #0
:   sta pt_c
    lda py
    clc
    adc #4
    lsr
    lsr
    lsr
    sta pt_r
    rts
.endproc

.proc trail_update
    lda frame
    and #15
    bne @r
    ldx trail_pos
    lda pt_c
    sta trail_c,x
    lda pt_r
    sta trail_r,x
    inx
    txa
    and #7
    sta trail_pos
@r: rts
.endproc

; ----------------------------------------------------------------- fright
.proc start_fright
    ldy lvidx
    lda fr_lo,y
    sta ftimer
    lda fr_hi,y
    sta ftimer+1
    lda #0
    sta fchain
    ldx #3
@l: lda estate,x
    cmp #ST_EYES
    bcs @n
    lda #1
    sta efright,x
    lda estate,x
    cmp #ST_ACTIVE
    bne @n
    lda #1
    sta erev,x
@n: dex
    bpl @l
    rts                        ; background switches to fright on this frame
.endproc

.proc fright_update
    lda ftimer
    ora ftimer+1
    beq @r
    lda ftimer
    bne :+
    dec ftimer+1
:   dec ftimer
    lda ftimer
    ora ftimer+1
    bne @r
    ldx #3
    lda #0
:   sta efright,x
    dex
    bpl :-
@r: rts
.endproc

; ----------------------------------------------------------------- release
.proc release_update
    ldx relidx
    cpx #4
    bcs @r
    lda estate,x
    cmp #ST_NEST
    beq @chk
    inc relidx
@r: rts
@chk:
    inc reltimer
    lda reltimer
    ldy lvidx
    cmp rel_time,y
    bcs @go
    ; dot threshold
    lda reldeath
    beq @lv
    lda rel_death-1,x
    jmp @cmp
@lv:
    txa
    clc
    adc rel_row,y
    tay
    lda rel_thr-1,y
@cmp:
    cmp reldots
    beq @go
    bcs @r2
@go:
    lda #ST_LEAVE
    sta estate,x
    lda #0
    sta reltimer
    inc relidx
@r2:
    rts
.endproc

; ----------------------------------------------------------------- enemies
.proc enemies_update
    ldx #3
@l: stx eidx
    jsr enemy_update
    ldx eidx
    dex
    bpl @l
    rts
.endproc

; X = enemy
.proc enemy_update
    lda estate,x
    cmp #ST_EYES
    bcs @fast
    cmp #ST_ACTIVE
    beq @act
    lda #$80                ; in the nest / leaving: half speed
    ldy #0
    jmp @spd
@fast:
    lda #0
    ldy #2
    jmp @spd
@act:
    ldy lvidx
    lda efright,x
    beq @nf
    lda enf_spd,y
    ldy #0
    jmp @spd
@nf:
    lda ey,x
    cmp #TUNNEL_ROW*8
    bne @nt
    lda ex,x
    cmp #4*8
    bcc @tun
    cmp #17*8
    bcc @nt
@tun:
    lda ent_spd,y
    ldy #0
    jmp @spd
@nt:
    lda en_spd,y
    ldy dots_left
    cpy #21
    bcs :+
    adc #$0D                ; C=0 here: hurry up near the end
:   ldy #0
@spd:
    clc
    adc eacc,x
    sta eacc,x
    tya
    adc #0
    beq @r
    sta esteps
@sl:
    jsr enemy_step
    ldx eidx
    dec esteps
    bne @sl
@r: rts
.endproc

; X = enemy, one pixel of movement
.proc enemy_step
    lda estate,x
    asl
    tay
    lda estep_tab+1,y
    pha
    lda estep_tab,y
    pha
    rts
.endproc
estep_tab:
    .word es_nest-1, es_leave-1, es_active-1, es_eyes-1, es_enter-1

.proc es_nest
    lda edir,x
    cmp #D_LEFT
    beq @left
    inc ex,x
    lda ex,x
    cmp nest_max,x
    bcc @r
    lda #D_LEFT
    sta edir,x
@r: rts
@left:
    dec ex,x
    lda nest_min,x
    cmp ex,x
    bcc @r
    lda #D_RIGHT
    sta edir,x
    rts
.endproc

.proc es_leave
    lda ex,x
    cmp #DOOR_PX
    beq @up
    bcc @inc
    dec ex,x
    lda #D_LEFT
    sta edir,x
    rts
@inc:
    inc ex,x
    lda #D_RIGHT
    sta edir,x
    rts
@up:
    lda #D_UP
    sta edir,x
    lda ey,x
    cmp #OUT_Y
    beq @out
    dec ey,x
    rts
@out:
    lda #ST_ACTIVE
    sta estate,x
    lda #D_LEFT
    sta edir,x
    lda #0
    sta erev,x
    rts
.endproc

.proc es_active
    lda erev,x
    beq @norev
    lda #0
    sta erev,x
    lda edir,x
    eor #2
    sta edir,x
    jmp enemy_move
@norev:
    lda ex,x
    ora ey,x
    and #7
    bne :+
    jsr enemy_decide
    ldx eidx
:   jmp enemy_move
.endproc

.proc es_eyes
    lda ex,x
    ora ey,x
    and #7
    bne @mv
    lda ex,x
    lsr
    lsr
    lsr
    sta ec
    lda ey,x
    lsr
    lsr
    lsr
    sta er
    cmp #HOME_Y
    bne @dir
    lda ec
    cmp #HOME_X
    bne @dir
    lda #ST_ENTER
    sta estate,x
    lda #D_DOWN
    sta edir,x
    rts
@dir:
    ldy er
    lda hrow_lo,y
    sta tptr
    lda hrow_hi,y
    sta tptr+1
    ldy ec
    lda (tptr),y
    sta edir,x
@mv:
    jmp enemy_move
.endproc

.proc es_enter
    lda ey,x
    cmp #NEST_Y
    bcs @in
    inc ey,x
    rts
@in:
    lda #ST_LEAVE
    sta estate,x
    lda #0
    sta efright,x
    rts
.endproc

.proc enemy_move
    ldy edir,x
    lda ex,x
    clc
    adc dx_tab,y
    cmp #$FF
    bne :+
    lda #167
:   cmp #168
    bne :+
    lda #0
:   sta ex,x
    lda ey,x
    clc
    adc dy_tab,y
    sta ey,x
    rts
.endproc

; ----------------------------------------------------------------- AI
; Enemy eidx is centred on a tile: choose its next direction.
.proc enemy_decide
    lda ex,x
    lsr
    lsr
    lsr
    sta ec
    sta q_c
    lda ey,x
    lsr
    lsr
    lsr
    sta er
    sta q_r
    lda edir,x
    eor #2
    sta erevd
    ; collect open, non-reverse exits
    lda #0
    sta eopts
    sta ecnt
    lda #3
    sta q_d
@o: lda q_d
    cmp erevd
    beq @on
    jsr tile_open
    bne @on
    ldy q_d
    lda bit_tab,y
    ora eopts
    sta eopts
    inc ecnt
@on:
    dec q_d
    bpl @o
    lda eopts
    bne @some
    lda erevd               ; dead end: turn back
    sta edir,x
    rts
@some:
    lda efright,x
    beq :+
    jmp ai_random
:   lda ai_tab_hi,x
    pha
    lda ai_tab_lo,x
    pha
    rts
.endproc
ai_tab_lo:  .byte <(ai_stalker-1), <(ai_prowler-1), <(ai_mirror-1), <(ai_tracker-1)
ai_tab_hi:  .byte >(ai_stalker-1), >(ai_prowler-1), >(ai_mirror-1), >(ai_tracker-1)

; STALKER: head straight for the player's tile
.proc ai_stalker
    lda pt_c
    sta tgt_c
    lda pt_r
    sta tgt_r
    jmp greedy
.endproc

; MIRROR: head for the player's position reflected through the maze centre
.proc ai_mirror
    lda #MAZE_W-1
    sec
    sbc pt_c
    sta tgt_c
    lda #MAZE_H-1
    sec
    sbc pt_r
    sta tgt_r
    jmp greedy
.endproc

; TRACKER: follow the player's scent -- where it was ~2 seconds ago
.proc ai_tracker
    ldy trail_pos
    lda trail_c,y
    sta tgt_c
    lda trail_r,y
    sta tgt_r
    jmp greedy
.endproc

; PROWLER: charges along a clear line of sight; otherwise patrols,
; alternating left-hand and right-hand turns at each junction.
.proc ai_prowler
    lda er
    cmp pt_r
    bne @vert
    lda ec
    cmp pt_c
    beq @patrol
    jsr los_row
    bcs @vert
    lda #D_LEFT
    ldy pt_c
    cpy ec
    bcc @want
    lda #D_RIGHT
    jmp @want
@vert:
    lda ec
    cmp pt_c
    bne @patrol
    lda er
    cmp pt_r
    beq @patrol
    jsr los_col
    bcs @patrol
    lda #D_UP
    ldy pt_r
    cpy er
    bcc @want
    lda #D_DOWN
@want:
    tay
    lda eopts
    and bit_tab,y
    beq @patrol
    sty tmp0
    ldx eidx
    lda tmp0
    sta edir,x
    rts
@patrol:
    ldx eidx
    lda ecnt
    cmp #2
    bcc :+
    lda eturn,x
    eor #1
    sta eturn,x
:   lda eturn,x
    beq @right
    ; left, straight, right
    lda edir,x
    clc
    adc #1
    jsr @try
    bcc @r
    lda edir,x
    jsr @try
    bcc @r
    lda edir,x
    clc
    adc #3
    jsr @try
@r: rts
@right:
    lda edir,x
    clc
    adc #3
    jsr @try
    bcc @r
    lda edir,x
    jsr @try
    bcc @r
    lda edir,x
    clc
    adc #1
    jmp @try
@try:                       ; A = dir (mod 4); C=0 and set if available
    and #3
    tay
    lda eopts
    and bit_tab,y
    beq @no
    tya
    sta edir,x
    clc
    rts
@no:
    sec
    rts
.endproc

; clear line of sight along row er between ec and pt_c?  C=0 if clear
.proc los_row
    ldy er
    lda arow_lo,y
    sta tptr
    lda arow_hi,y
    sta tptr+1
    lda ec
    ldy pt_c
    cmp pt_c
    bcc :+
    ldy ec                  ; Y = larger, A = smaller
    lda pt_c
:   sta tmp0
    sty tmp1
@l: inc tmp0
    ldy tmp0
    cpy tmp1
    bcs @clear
    lda (tptr),y
    and #3
    beq @l
    sec
    rts
@clear:
    clc
    rts
.endproc

.proc los_col
    lda er
    ldy pt_r
    cmp pt_r
    bcc :+
    ldy er
    lda pt_r
:   sta tmp0
    sty tmp1
@l: inc tmp0
    ldy tmp0
    cpy tmp1
    bcs @clear
    lda arow_lo,y
    sta tptr
    lda arow_hi,y
    sta tptr+1
    ldy ec
    lda (tptr),y
    and #3
    beq @l
    sec
    rts
@clear:
    clc
    rts
.endproc

; choose the exit (from eopts) whose neighbour tile is closest (Manhattan)
; to tgt_c/tgt_r.  Ties go up, left, down, right.
.proc greedy
    lda #$FF
    sta bestdist
    ldy #0
@g: lda eopts
    and bit_tab,y
    beq @gn
    lda ec
    clc
    adc dx_tab,y
    bpl :+
    lda #MAZE_W-1
:   cmp #MAZE_W
    bcc :+
    lda #0
:   sec
    sbc tgt_c
    bcs :+
    eor #$FF
    adc #1
:   sta tmp0
    lda er
    clc
    adc dy_tab,y
    sec
    sbc tgt_r
    bcs :+
    eor #$FF
    adc #1
:   clc
    adc tmp0
    cmp bestdist
    bcs @gn
    sta bestdist
    sty bestd
@gn:
    iny
    cpy #4
    bne @g
    ldx eidx
    lda bestd
    sta edir,x
    rts
.endproc

; frightened: pseudo-random exit
.proc ai_random
    jsr rnd
    and #3
    tay
    lda #4
    sta tmp0
@l: lda eopts
    and bit_tab,y
    bne @got
    iny
    tya
    and #3
    tay
    dec tmp0
    bne @l
@got:
    ldx eidx
    tya
    sta edir,x
    rts
.endproc

; ----------------------------------------------------------------- collisions
.proc collide
    ldx #3
@l: lda estate,x
    cmp #ST_ACTIVE
    beq @chk
    cmp #ST_LEAVE
    bne @n
@chk:
    lda ex,x
    sec
    sbc px
    bcs :+
    eor #$FF
    adc #1
:   cmp #84
    bcc :+
    eor #$FF                ; distance the other way round the tunnel
    sec
    adc #168
:   cmp #6
    bcs @n
    lda ey,x
    sec
    sbc py
    bcs :+
    eor #$FF
    adc #1
:   cmp #6
    bcs @n
    lda efright,x
    bne @eat
    jmp player_dies
@n: dex
    bpl @l
    rts
@eat:
    stx eat_idx
    lda #0
    sta efright,x
    lda #ST_EYES
    sta estate,x
    lda ex,x
    sta eat_x
    lda ey,x
    sta eat_y
    ldy fchain
    lda chain_img,y
    sta eat_img
    lda chain_pts,y
    tax
    lda #0
    jsr add_points
    lda fchain
    cmp #3
    bcs :+
    inc fchain
:   lda #M_EAT
    sta mode
    lda #60
    sta mtimer
    lda #0
    sta mtimer+1
    ldx #1
    lda #SND_EAT
    jmp play_fx
.endproc
chain_img:  .byte IMG_PTS200_L, IMG_PTS400_L, IMG_PTS800_L, IMG_PTS1600_L
chain_pts:  .byte $02, $04, $08, $16

.proc player_dies
    lda #M_DYING
    sta mode
    lda #60
    sta mtimer
    lda #0
    sta mtimer+1
    sta pmoving
    jsr restore_honey
    jmp sound_off
.endproc

; ----------------------------------------------------------------- bonus
.proc bonus_show
    lda #1
    sta bshown
    lda #<540
    sta btimer
    lda #>540
    sta btimer+1
    ldy lvidx
    lda item_cols,y
    tax
    tya
    clc
    adc #CH_ITEM0
    pha
    lda #BONUS_X
    ldy #BONUS_Y
    jsr maze_cell
    pla
    jmp put_bg
.endproc

.proc bonus_remove
    lda #0
    sta bshown
    lda #BONUS_X
    ldy #BONUS_Y
    jsr maze_cell
    lda #CH_BLANK
    ldx #1
    jmp put_bg
.endproc

.proc bonus_update
    jsr bonus_popup_tick
    lda bshown
    beq @r
    ; eaten?
    lda pt_c
    cmp #BONUS_X
    bne @t
    lda pt_r
    cmp #BONUS_Y
    bne @t
    jsr bonus_remove
    ldy lvidx
    ldx item_points_hi,y
    lda #0
    jsr add_points
    ; show the points
    lda lvidx
    asl
    asl
    clc
    adc #<item_text
    sta ptr0
    lda #>item_text
    adc #0
    sta ptr0+1
    lda #BONUS_X-1
    ldy #BONUS_Y
    jsr maze_cell
    ldy #0
@p: sty tmp2
    lda (ptr0),y
    ldx #7
    jsr put_bg
    inc cptr
    ldy tmp2
    iny
    cpy #4
    bne @p
    lda #120
    sta bpop
    ldx #1
    lda #SND_BONUS
    jmp play_fx
@t: lda btimer
    bne :+
    dec btimer+1
:   dec btimer
    lda btimer
    ora btimer+1
    bne @r
    jmp bonus_remove
@r: rts
.endproc

.proc bonus_popup_tick
    lda bpop
    beq @r
    dec bpop
    bne @r
    lda #BONUS_X-1
    ldy #BONUS_Y
    jsr maze_cell
    ldy #0
@p: sty tmp2
    lda #CH_BLANK
    ldx #1
    jsr put_bg
    inc cptr
    ldy tmp2
    iny
    cpy #4
    bne @p
@r: rts
.endproc
item_text:
    .byte "100 ", "300 ", "500 ", "700 ", "1000", "2000", "3000", "5000"
