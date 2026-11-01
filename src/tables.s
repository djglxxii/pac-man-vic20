; =============================================================================
;  tables.s -- lookup tables and generated data
; =============================================================================
.segment "RODATA"

dx_tab:     .byte 0, $FF, 0, 1      ; up, left, down, right
dy_tab:     .byte $FF, 0, 1, 0
bit_tab:    .byte 1, 2, 4, 8

; screen row offsets (row * 21)
srow_lo:
.repeat SCR_ROWS, I
    .byte <(I*SCR_COLS)
.endrep
srow_hi:
.repeat SCR_ROWS, I
    .byte >(I*SCR_COLS)
.endrep

; maze row -> bgmap address
bgrow_lo:
.repeat MAZE_H, I
    .byte <(bgmap + (I+MAZE_ROW0)*SCR_COLS)
.endrep
bgrow_hi:
.repeat MAZE_H, I
    .byte >(bgmap + (I+MAZE_ROW0)*SCR_COLS)
.endrep

; maze row -> attribute / home direction rows
arow_lo:
.repeat MAZE_H, I
    .byte <(maze_attr + I*MAZE_W)
.endrep
arow_hi:
.repeat MAZE_H, I
    .byte >(maze_attr + I*MAZE_W)
.endrep
hrow_lo:
.repeat MAZE_H, I
    .byte <(home_dir + I*MAZE_W)
.endrep
hrow_hi:
.repeat MAZE_H, I
    .byte >(home_dir + I*MAZE_W)
.endrep

; character bitmap addresses
chlo:
.repeat 256, I
    .byte <(CHARSET + I*8)
.endrep
chhi:
.repeat 256, I
    .byte >(CHARSET + I*8)
.endrep

; page of each pre-shifted sprite image: BLK5 first, then $7000
img_page:
.repeat NUM_IMAGES, I
  .if I < 32
    .byte $A0 + I
  .else
    .byte $70 + I - 32
  .endif
.endrep

; ---- per-level tuning (index = min(level, 7)), speeds in 1/256 px/frame
pl_spd:     .byte $CD, $D9, $E1, $E6, $EB, $F0, $F3, $F3
plf_spd:    .byte $E6, $EB, $F0, $F3, $F3, $F8, $F8, $F8
en_spd:     .byte $B8, $C8, $D4, $DC, $E1, $E6, $EB, $EB
enf_spd:    .byte $73, $7B, $80, $85, $85, $85, $8A, $8A
ent_spd:    .byte $66, $6B, $73, $7B, $7B, $80, $80, $80
fr_lo:      .byte <360, <300, <240, <180, <150, <120, <90, <60
fr_hi:      .byte >360, >300, >240, >180, >150, >120, >90, >60
; release: frames without eating before the next enemy is let out
rel_time:   .byte 240, 240, 210, 210, 180, 180, 180, 180
; seeds eaten before PROWLER, MIRROR, TRACKER leave (per level)
rel_row:    .byte 0, 3, 6, 9, 12, 15, 18, 21
rel_thr:    .byte 0, 15, 40
            .byte 0, 0, 20
            .byte 0, 0, 0
            .byte 0, 0, 0
            .byte 0, 0, 0
            .byte 0, 0, 0
            .byte 0, 0, 0
            .byte 0, 0, 0
rel_death:  .byte 3, 12, 24

.include "data.inc"
.include "sound.inc"
