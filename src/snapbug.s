; =============================================================================
;  SNAPBUG -- a maze-chase game for the Commodore VIC-20
;  NTSC, full memory expansion (3K + 24K + BLK5).
;
;  Rendering: the maze is ordinary characters.  Moving actors are drawn into
;  per-frame "dynamic" characters (64 chars, double buffered) which combine
;  the background tile with a pre-shifted, masked 8x8 sprite image.  This
;  gives pixel-smooth movement on a character-only display.
; =============================================================================
.setcpu "6502"
.include "vic.inc"
.include "consts.inc"

; ----------------------------------------------------------------- layout
bgmap       = $0400         ; screen-sized background tile map
colmap      = $0600         ; screen-sized background colour map
ovl         = $0800         ; per-cell: dynamic char index+1 for frame being built
SCR_COLS    = 21
SCR_ROWS    = 24
MAXDYN      = 32            ; dynamic chars per buffer
MAXACT      = 8             ; actor slots
POOL_A      = CH_DYN0
POOL_B      = CH_DYN0 + 32
BOTTOM_LINE = 120           ; raster/2 just below the display (NTSC)

D_UP        = 0
D_LEFT      = 1
D_DOWN      = 2
D_RIGHT     = 3
NO_DIR      = $FF

ST_NEST     = 0
ST_LEAVE    = 1
ST_ACTIVE   = 2
ST_EYES     = 3
ST_ENTER    = 4

M_TITLE     = 0
M_READY     = 1
M_PLAY      = 2
M_EAT       = 3
M_DYING     = 4
M_LEVEL     = 5
M_OVER      = 6

NEST_Y      = (DOOR_Y + 1) * 8
OUT_Y       = HOME_Y * 8
DOOR_PX     = DOOR_X * 8

; ----------------------------------------------------------------- zero page
.segment "ZEROPAGE"
ptr0:       .res 2
ptrD:       .res 2
ptrS:       .res 2
ptrM:       .res 2
tptr:       .res 2
cptr:       .res 2
sptr:       .res 2
tmp0:       .res 1
tmp1:       .res 1
tmp2:       .res 1
tmp3:       .res 1
frame:      .res 1
mode:       .res 1
mtimer:     .res 2
level:      .res 1
lvidx:      .res 1
lives:      .res 1
score:      .res 3          ; BCD, score+0 = lowest two digits
hiscore:    .res 3
extra_given:.res 1
dots_left:  .res 1
dots_eaten: .res 1
poolbase:   .res 1
new_n:      .res 1
old_n:      .res 1
joybits:    .res 1
joyprev:    .res 1
firstrun:   .res 1
; player
px:         .res 1
py:         .res 1
pdir:       .res 1
pwant:      .res 1
pacc:       .res 1
ppause:     .res 1
panim:      .res 1
pmoving:    .res 1
pt_c:       .res 1          ; player tile (rounded)
pt_r:       .res 1
; enemies
ex:         .res 4
ey:         .res 4
edir:       .res 4
estate:     .res 4
efright:    .res 4
erev:       .res 4
eacc:       .res 4
eturn:      .res 4
eidx:       .res 1
esteps:     .res 1
ec:         .res 1
er:         .res 1
erevd:      .res 1
eopts:      .res 1
ecnt:       .res 1
tgt_c:      .res 1
tgt_r:      .res 1
bestd:      .res 1
bestdist:   .res 1
q_c:        .res 1
q_r:        .res 1
q_d:        .res 1
; fright / release / bonus
ftimer:     .res 2
fchain:     .res 1
relidx:     .res 1
reldots:    .res 1
reltimer:   .res 1
reldeath:   .res 1
btimer:     .res 2
bshown:     .res 1
bpop:       .res 1
rng:        .res 1
eat_idx:    .res 1
eat_x:      .res 1
eat_y:      .res 1
eat_img:    .res 1
dtimer:     .res 1
; renderer
act_x:      .res MAXACT
act_y:      .res MAXACT
act_img:    .res MAXACT
act_col:    .res MAXACT
r_act:      .res 1
r_sx:       .res 1
r_sy:       .res 1
r_col0:     .res 1
r_col1:     .res 1
r_row:      .res 1
r_srcl:     .res 1
r_srch:     .res 1
r_color:    .res 1
pb_ch:      .res 1
pb_col:     .res 1
pb_hi:      .res 1
p_color:    .res 1

; ----------------------------------------------------------------- low RAM
.segment "BSS"
old_lo:     .res MAXDYN
old_hi:     .res MAXDYN
new_lo:     .res MAXDYN
new_hi:     .res MAXDYN
new_col:    .res MAXDYN
trail_c:    .res 8
trail_r:    .res 8
trail_pos:  .res 1
; sound
fx_on:      .res 4
fx_lo:      .res 4
fx_hi:      .res 4
fx_cnt:     .res 4
fx_val:     .res 4
bg_on:      .res 4
bg_id:      .res 4
bg_lo:      .res 4
bg_hi:      .res 4
bg_plo:     .res 4
bg_phi:     .res 4
bg_cnt:     .res 4
bg_val:     .res 4
g_img:      .res 1
g_s:        .res 1
g_r:        .res 1
g_hi:       .res 1
g_lo:       .res 1
chomp_alt:  .res 1

; ----------------------------------------------------------------- loader
.segment "LOADADDR"
    .word $1201
.segment "STUB"
    .word stub_end              ; 10 SYS8192
    .word 10
    .byte $9E, "8192", 0
stub_end:
    .word 0

.segment "CHARS"
    .incbin "charset.bin"

; =============================================================================
.segment "CODE"
start:                          ; must be first: $2000
    sei
    cld
    ldx #$FF
    txs
    lda #$7F
    sta VIA1_IER
    sta VIA2_IER
    lda #<nmi_handler
    sta $0318
    lda #>nmi_handler
    sta $0319
    ; clear zero page variables and BSS
    lda #0
    ldx #2
@zp:
    sta $00,x
    inx
    bne @zp
    ldx #0
@bss:
    sta $0A00,x
    sta $0B00,x
    inx
    bne @bss
    ; VIC setup: 21x24, screen $1000, charset $1800, black
    lda #6
    sta VIC_HORIZ
    lda #23
    sta VIC_VERT
    lda #SCR_COLS
    sta VIC_COLS
    lda #SCR_ROWS*2
    sta VIC_ROWS
    lda #$CE
    sta VIC_MEM
    lda #$08
    sta VIC_COLOR
    lda #$0C
    sta VIC_VOL
    lda #0
    sta VIC_BASS
    sta VIC_ALTO
    sta VIC_SOPR
    sta VIC_NOISE
    ; joystick
    lda #0
    sta VIA1_DDRA
    lda #$7F
    sta VIA2_DDRB
    ; renderer
    lda #POOL_A
    sta poolbase
    jsr clear_ovl
    jsr gen_shifts
    jsr sound_init
    ; hi score 0
    jsr enter_title

main_loop:
    jsr frame_wait
    jsr flip
    jsr sound_update
    jsr read_joy
    jsr update_mode
    jsr build_actors
    jsr compose
    inc frame
    jmp main_loop

nmi_handler:
    rti

; wait for the raster to reach the bottom of the display (once per frame)
frame_wait:
@a: lda VIC_RASTER
    cmp #BOTTOM_LINE
    bcs @a
@b: lda VIC_RASTER
    cmp #BOTTOM_LINE
    bcc @b
    rts

; ----------------------------------------------------------------- joystick
.proc read_joy
    lda joybits
    sta joyprev
    lda VIA1_PA
    eor #$FF
    sta tmp0
    lda VIA2_PB
    eor #$FF
    sta tmp1
    lda #0
    sta joybits
    lda tmp0
    and #$04
    beq :+
    lda #$01
    ora joybits
    sta joybits
:   lda tmp0
    and #$10
    beq :+
    lda #$02
    ora joybits
    sta joybits
:   lda tmp0
    and #$08
    beq :+
    lda #$04
    ora joybits
    sta joybits
:   lda tmp1
    and #$80
    beq :+
    lda #$08
    ora joybits
    sta joybits
:   lda tmp0
    and #$20
    beq :+
    lda #$10
    ora joybits
    sta joybits
:   rts
.endproc

; fire pressed this frame but not last frame -> C=1
.proc fire_edge
    lda joybits
    and #$10
    beq @no
    lda joyprev
    and #$10
    bne @no
    sec
    rts
@no:
    clc
    rts
.endproc

; ----------------------------------------------------------------- utilities
.proc rnd
    lda rng
    asl
    bcc :+
    eor #$1D
:   sta rng
    rts
.endproc

; 16-bit mtimer decrement; Z=1 when it reaches zero
.proc dec_mtimer
    lda mtimer
    bne :+
    dec mtimer+1
:   dec mtimer
    lda mtimer
    ora mtimer+1
    rts
.endproc

; =============================================================================
;  mode dispatch
; =============================================================================
.proc update_mode
    lda mode
    asl
    tax
    lda mode_tab+1,x
    pha
    lda mode_tab,x
    pha
    rts
.endproc

.proc build_actors
    ldx #MAXACT-1
    lda #$FF
:   sta act_img,x
    dex
    bpl :-
    lda mode
    asl
    tax
    lda build_tab+1,x
    pha
    lda build_tab,x
    pha
    rts
.endproc

mode_tab:
    .word mode_title-1, mode_ready-1, mode_play-1, mode_eat-1
    .word mode_dying-1, mode_level-1, mode_over-1
build_tab:
    .word build_title-1, build_game-1, build_game-1, build_eat-1
    .word build_dying-1, build_level-1, build_none-1

; ----------------------------------------------------------------- title
.proc enter_title
    lda #M_TITLE
    sta mode
    jsr sound_off
    jsr clear_bgmap
    jsr draw_labels
    jsr draw_score
    ldx #0
:   lda title_texts,x
    sta ptr0
    lda title_texts+1,x
    sta ptr0+1
    txa
    pha
    jsr print
    pla
    tax
    inx
    inx
    cpx #title_texts_end-title_texts
    bne :-
    ; seed / honey icons
    lda #COL_DOT
    sta p_color
    lda #16
    ldx #5
    ldy #CH_DOT
    jsr put_xy
    lda #COL_HONEY
    sta p_color
    lda #18
    ldx #5
    ldy #CH_HONEY
    jsr put_xy
    jsr restore_honey
    jsr redraw
    rts
.endproc

; put char Y at screen row A, col X with colour p_color
.proc put_xy
    stx tmp0
    tax
    lda srow_lo,x
    clc
    adc tmp0
    sta cptr
    lda srow_hi,x
    adc #>bgmap
    sta cptr+1
    tya
    ldx p_color
    jmp put_bg
.endproc

title_texts:
    .word t_title, t_cast, t_n0, t_n1, t_n2, t_n3, t_p10, t_p50, t_fire
title_texts_end:
t_title:  .byte 3, 7, 7, "SNAPBUG", 0
t_cast:   .byte 5, 6, 1, "- CAST -", 0
t_n0:     .byte 7, 7, 2, "STALKER", 0
t_n1:     .byte 9, 7, 4, "PROWLER", 0
t_n2:     .byte 11, 7, 3, "MIRROR", 0
t_n3:     .byte 13, 7, 7, "TRACKER", 0
t_p10:    .byte 16, 7, 1, "10 PTS", 0
t_p50:    .byte 18, 7, 1, "50 PTS", 0
t_fire:   .byte 21, 6, 7, "PUSH FIRE", 0
t_nofire: .byte 21, 6, 7, "         ", 0

.proc mode_title
    ; blink PUSH FIRE
    lda frame
    and #31
    bne @nob
    lda frame
    and #32
    beq @on
    lda #<t_nofire
    ldx #>t_nofire
    jmp @pr
@on:
    lda #<t_fire
    ldx #>t_fire
@pr:
    sta ptr0
    stx ptr0+1
    jsr print
@nob:
    jsr fire_edge
    bcc @r
    jmp start_game
@r: rts
.endproc

.proc build_title
    ldx #3
@l: lda title_ey,x
    sta act_y,x
    lda #32
    sta act_x,x
    lda frame
    lsr
    lsr
    lsr
    and #1
    clc
    adc #IMG_SPIDER_D3_F0
    sta act_img,x
    lda enemy_color,x
    sta act_col,x
    dex
    bpl @l
    rts
.endproc
title_ey:   .byte (7-2)*8, (9-2)*8, (11-2)*8, (13-2)*8

; ----------------------------------------------------------------- game start
.proc start_game
    lda #0
    sta score
    sta score+1
    sta score+2
    sta level
    sta extra_given
    lda #3
    sta lives
    lda #1
    sta firstrun
    jmp start_level
.endproc

.proc start_level
    lda level
    cmp #7
    bcc :+
    lda #7
:   sta lvidx
    jsr sound_off
    jsr clear_bgmap
    jsr draw_labels
    jsr init_maze
    lda #TOTAL_DOTS
    sta dots_left
    lda #0
    sta dots_eaten
    sta bshown
    sta bpop
    sta reldeath
    jsr restore_honey
    jsr draw_score
    jsr draw_status
    jsr redraw
    jmp start_life
.endproc

; (re)start after level start or lost life
.proc start_life
    jsr reset_actors
    lda #<t_ready
    sta ptr0
    lda #>t_ready
    sta ptr0+1
    jsr print
    lda #M_READY
    sta mode
    lda #120
    sta mtimer
    lda #0
    sta mtimer+1
    lda firstrun
    beq @r
    lda #0
    sta firstrun
    lda #<(JINGLE_FRAMES+10)
    sta mtimer
    lda #>(JINGLE_FRAMES+10)
    sta mtimer+1
    ldx #2
    lda #SND_JINGLE_S
    jsr play_fx
    ldx #0
    lda #SND_JINGLE_B
    jsr play_fx
@r: rts
.endproc

t_ready:  .byte MAZE_ROW0+BONUS_Y, 7, 7, "READY!", 0
t_unready:.byte MAZE_ROW0+BONUS_Y, 6, 1, "         ", 0
t_over:   .byte MAZE_ROW0+BONUS_Y, 6, 2, "GAME OVER", 0

.proc reset_actors
    lda #PSTART_X*8
    sta px
    lda #PSTART_Y*8
    sta py
    lda #D_LEFT
    sta pdir
    lda #NO_DIR
    sta pwant
    lda #0
    sta pacc
    sta ppause
    sta panim
    sta pmoving
    sta ftimer
    sta ftimer+1
    sta fchain
    sta reldots
    sta reltimer
    ldx #3
@e: lda start_ex,x
    sta ex,x
    lda start_ey,x
    sta ey,x
    lda start_st,x
    sta estate,x
    lda start_dir,x
    sta edir,x
    lda #0
    sta efright,x
    sta erev,x
    sta eacc,x
    sta eturn,x
    dex
    bpl @e
    lda #1
    sta relidx
    ldx #7
@t: lda #PSTART_X
    sta trail_c,x
    lda #PSTART_Y
    sta trail_r,x
    dex
    bpl @t
    lda #0
    sta trail_pos
    lda #$A5
    sta rng
    lda #PSTART_X
    sta pt_c
    lda #PSTART_Y
    sta pt_r
    ; remove any bonus item
    lda bshown
    beq :+
    jsr bonus_remove
:   lda bpop
    beq :+
    lda #1
    sta bpop
    jsr bonus_popup_tick
:   rts
.endproc

start_ex:   .byte DOOR_PX, DOOR_PX, DOOR_PX-16, DOOR_PX+16
start_ey:   .byte OUT_Y, NEST_Y, NEST_Y, NEST_Y
start_st:   .byte ST_ACTIVE, ST_NEST, ST_NEST, ST_NEST
start_dir:  .byte D_LEFT, D_RIGHT, D_RIGHT, D_LEFT
nest_min:   .byte DOOR_PX, DOOR_PX-3, DOOR_PX-16, DOOR_PX+13
nest_max:   .byte DOOR_PX, DOOR_PX+3, DOOR_PX-13, DOOR_PX+16
; Yellow approximates the arcade's orange within the hi-res VIC palette.
enemy_color:.byte 2, 4, 3, 7

; ----------------------------------------------------------------- READY
.proc mode_ready
    jsr dec_mtimer
    bne @r
    lda #<t_unready
    sta ptr0
    lda #>t_unready
    sta ptr0+1
    jsr print
    lda #M_PLAY
    sta mode
@r: rts
.endproc

; ----------------------------------------------------------------- PLAY
.proc mode_play
    jsr joy_to_want
    jsr honey_blink
    jsr player_update
    jsr player_tile_calc
    jsr trail_update
    jsr release_update
    jsr fright_update
    jsr enemies_update
    jsr bonus_update
    jsr play_sounds_bg
    jsr collide
    lda mode
    cmp #M_PLAY
    bne @r
    lda dots_left
    bne @r
    ; level cleared
    lda #M_LEVEL
    sta mode
    lda #156
    sta mtimer
    jsr sound_off
    jsr restore_honey
@r: rts
.endproc

.proc joy_to_want
    lda joybits
    and #$0F
    bne @some
    lda #NO_DIR
    sta pwant
    rts
@some:
    sta tmp0
    ; prefer a direction perpendicular to the current one
    ldx #0
@p: lda tmp0
    and bit_tab,x
    beq @pn
    txa
    eor pdir
    and #1
    beq @pn
    stx pwant
    rts
@pn:
    inx
    cpx #4
    bne @p
    ldx #0
@f: lda tmp0
    and bit_tab,x
    bne @got
    inx
    bne @f
@got:
    stx pwant
    rts
.endproc

.proc honey_blink
    lda frame
    and #15
    bne @r
    lda frame
    and #16
    beq restore_honey
    ldx #7
    lda #0
:   sta CHARSET+CH_HONEY*8,x
    dex
    bpl :-
@r: rts
.endproc

.proc restore_honey
    ldx #7
:   lda honey_glyph,x
    sta CHARSET+CH_HONEY*8,x
    dex
    bpl :-
    rts
.endproc
honey_glyph: .byte $00,$3C,$7E,$7E,$7E,$7E,$3C,$00

.proc build_game
    jsr build_enemies
    jmp build_player
.endproc

.proc build_player
    lda px
    sta act_x+4
    lda py
    sta act_y+4
    lda #7
    sta act_col+4
    lda pmoving
    beq @f0
    lda panim
    lsr
    and #3
    tax
    lda player_chomp,x
    cmp #IMG_BUG_CLOSED
    beq @image
    jmp @direction
@f0:
    lda #0
@direction:
    sta tmp0
    lda pdir
    asl
    ora tmp0
    clc
    adc #IMG_BUG_D0_F0
@image:
    sta act_img+4
    rts
.endproc
player_chomp: .byte 0, 1, IMG_BUG_CLOSED, 1

.proc build_enemies
    ldx #3
@l: lda ex,x
    sta act_x,x
    lda ey,x
    sta act_y,x
    lda estate,x
    cmp #ST_EYES
    bcc @body
    ; eyes
    lda edir,x
    clc
    adc #IMG_EYES_D0
    sta act_img,x
    lda #1
    sta act_col,x
    jmp @n
@body:
    lda frame
    lsr
    lsr
    lsr
    and #1
    sta tmp0
    lda efright,x
    beq @norm
    lda tmp0
    clc
    adc #IMG_FRIGHT_F0
    sta act_img,x
    lda #6
    sta act_col,x
    ; flash when running out
    lda ftimer+1
    bne @n
    lda ftimer
    cmp #120
    bcs @n
    lda frame
    and #8
    beq @n
    lda #1
    sta act_col,x
    jmp @n
@norm:
    lda edir,x
    asl
    ora tmp0
    clc
    adc #IMG_SPIDER_D0_F0
    sta act_img,x
    lda enemy_color,x
    sta act_col,x
@n: dex
    bpl @l
    rts
.endproc

; ----------------------------------------------------------------- EAT freeze
.proc mode_eat
    dec mtimer
    bne @r
    lda #M_PLAY
    sta mode
@r: rts
.endproc

.proc build_eat
    jsr build_enemies
    ldx eat_idx
    lda #$FF
    sta act_img,x
    lda eat_x
    sec
    sbc #4
    bcs :+
    adc #168
:   sta act_x+5
    lda eat_x
    clc
    adc #4
    cmp #168
    bcc :+
    sbc #168
:   sta act_x+6
    lda eat_y
    sta act_y+5
    sta act_y+6
    lda eat_img
    sta act_img+5
    clc
    adc #1
    sta act_img+6
    lda #3
    sta act_col+5
    sta act_col+6
    rts
.endproc

; ----------------------------------------------------------------- DYING
; mtimer: 60 frames freeze, then dtimer runs the death animation
.proc mode_dying
    lda mtimer
    beq @anim
    dec mtimer
    bne @r
    lda #0
    sta dtimer
    jsr sound_off
    ldx #2
    lda #SND_DEATH
    jsr play_fx
@r: rts
@anim:
    inc dtimer
    lda dtimer
    cmp #160
    bne @r
    ; animation finished
    dec lives
    beq @over
    lda #0
    sta reldots
    lda #1
    sta reldeath
    jsr draw_status
    jmp start_life
@over:
    lda #M_OVER
    sta mode
    lda #180
    sta mtimer
    lda #<t_over
    sta ptr0
    lda #>t_over
    sta ptr0+1
    jmp print
.endproc

.proc build_dying
    lda mtimer
    beq @anim
    jmp build_game
@anim:
    lda dtimer
    lsr
    lsr
    lsr
    tax
    cpx #16
    bcs @r
    lda death_seq,x
    bmi @r
    sta act_img+4
    lda px
    sta act_x+4
    lda py
    sta act_y+4
    lda #7
    sta act_col+4
@r: rts
.endproc
death_seq:
    .byte IMG_BUG_CLOSED, IMG_BUG_CLOSED, IMG_BUG_D0_F1, IMG_BUG_D0_F0
    .byte IMG_POP0, IMG_POP0, IMG_POP1, IMG_POP1
    .byte IMG_POP2, IMG_POP2, IMG_POP_SPARK, IMG_POP_SPARK, $FF, $FF, $FF, $FF

; ----------------------------------------------------------------- LEVEL done
.proc mode_level
    dec mtimer
    beq @next
    lda mtimer
    cmp #96
    bcs @r
    ; flash every 12 frames
    ldx #0
:   cmp flash_at,x
    beq @flash
    inx
    cpx #8
    bne :-
@r: rts
@flash:
    txa
    and #1
    beq :+
    lda #6
    .byte $2C
:   lda #1
    jmp wall_color
@next:
    lda #6
    jsr wall_color
    inc level
    jmp start_level
.endproc
flash_at:   .byte 95, 83, 71, 59, 47, 35, 23, 11

.proc build_level
    lda #0
    sta pmoving
    jmp build_player
.endproc

; set colour RAM of every wall cell to A
.proc wall_color
    sta tmp0
    ldx #0
@a: lda colmap,x
    cmp #COL_WALL
    bne :+
    lda bgmap,x
    cmp #CH_WALL0
    bcc :+
    cmp #CH_WALL0+16
    bcs :+
    lda tmp0
    sta COLRAM,x
:   inx
    bne @a
@b: lda colmap+256,x
    cmp #COL_WALL
    bne :+
    lda bgmap+256,x
    cmp #CH_WALL0
    bcc :+
    cmp #CH_WALL0+16
    bcs :+
    lda tmp0
    sta COLRAM+256,x
:   inx
    cpx #SCR_COLS*SCR_ROWS-256
    bne @b
    rts
.endproc

; ----------------------------------------------------------------- GAME OVER
.proc mode_over
    dec mtimer
    bne @r
    jmp enter_title
@r: rts
.endproc

build_none:
    rts

.include "render.s"
.include "actors.s"
.include "screen.s"
.include "sound.s"
.include "tables.s"
