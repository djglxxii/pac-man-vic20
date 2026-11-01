; =============================================================================
;  sound.s -- tiny stream player for the VIC's three voices (+noise)
;
;  Voice 0 bass $900A, 1 alto $900B, 2 soprano $900C, 3 noise $900D.
;  Each voice plays a one-shot effect if one is active, otherwise its looping
;  background stream (siren, fright warble, ...).
;  Streams are (register value, frames) pairs ending with a zero count.
; =============================================================================

.proc sound_init
    ldx #3
:   lda #$FF
    sta bg_id,x
    lda #0
    sta fx_on,x
    sta bg_on,x
    dex
    bpl :-
    rts
.endproc

.proc sound_off
    jsr sound_init
    lda #0
    sta VIC_BASS
    sta VIC_ALTO
    sta VIC_SOPR
    sta VIC_NOISE
    rts
.endproc

; A = sound id, X = voice
.proc play_fx
    tay
    lda snd_lo,y
    sta fx_lo,x
    lda snd_hi,y
    sta fx_hi,x
    lda #0
    sta fx_cnt,x
    lda #1
    sta fx_on,x
    rts
.endproc

; A = sound id or $FF (off), X = voice
.proc set_bg
    cmp bg_id,x
    beq @same
    sta bg_id,x
    cmp #$FF
    beq @off
    tay
    lda snd_lo,y
    sta bg_lo,x
    sta bg_plo,x
    lda snd_hi,y
    sta bg_hi,x
    sta bg_phi,x
    lda #0
    sta bg_cnt,x
    lda #1
    sta bg_on,x
    rts
@off:
    lda #0
    sta bg_on,x
@same:
    rts
.endproc

.proc sound_update
    ldx #3
@v: lda fx_on,x
    beq @bg
    lda fx_cnt,x
    bne @fplay
    lda fx_lo,x
    sta sptr
    lda fx_hi,x
    sta sptr+1
    ldy #1
    lda (sptr),y
    beq @fend
    sta fx_cnt,x
    dey
    lda (sptr),y
    sta fx_val,x
    lda fx_lo,x
    clc
    adc #2
    sta fx_lo,x
    bcc @fplay
    inc fx_hi,x
@fplay:
    dec fx_cnt,x
    lda fx_val,x
    jmp @out
@fend:
    lda #0
    sta fx_on,x
@bg:
    lda bg_on,x
    beq @silent
    lda bg_cnt,x
    bne @bplay
@bfetch:
    lda bg_plo,x
    sta sptr
    lda bg_phi,x
    sta sptr+1
    ldy #1
    lda (sptr),y
    bne @bok
    lda bg_lo,x             ; loop
    sta bg_plo,x
    lda bg_hi,x
    sta bg_phi,x
    jmp @bfetch
@bok:
    sta bg_cnt,x
    dey
    lda (sptr),y
    sta bg_val,x
    lda bg_plo,x
    clc
    adc #2
    sta bg_plo,x
    bcc @bplay
    inc bg_phi,x
@bplay:
    dec bg_cnt,x
    lda bg_val,x
    jmp @out
@silent:
    lda #0
@out:
    sta VIC_BASS,x
    dex
    bmi :+
    jmp @v
:   rts
.endproc

; background sounds while playing
.proc play_sounds_bg
    ; Eyes > fright > normal siren. Special modes replace the siren.
    ldx #3
@e: lda estate,x
    cmp #ST_EYES
    bcs @eyes
    dex
    bpl @e
    lda ftimer
    ora ftimer+1
    beq @normal
    lda #SND_FRIGHT
    bne @special
@eyes:
    lda #SND_EYES
@special:
    sta tmp1
    lda #$FF
    ldx #0
    jsr set_bg
    lda tmp1
    ldx #2
    jmp set_bg
@normal:
    ldy #0
    lda dots_left
@stage:
    cmp siren_dots,y
    bcs @siren
    iny
    cpy #4
    bcc @stage
@siren:
    lda siren_sounds,y
    ldx #0
    jsr set_bg
    lda #$FF
    ldx #2
    jmp set_bg
.endproc
siren_dots: .byte TOTAL_DOTS*4/5, TOTAL_DOTS*3/5, TOTAL_DOTS*2/5, TOTAL_DOTS/5
siren_sounds: .byte SND_SIREN1, SND_SIREN2, SND_SIREN3, SND_SIREN4, SND_SIREN5

.proc chomp_sound
    lda chomp_alt
    eor #1
    sta chomp_alt
    clc
    adc #SND_CHOMP1
    ldx #1
    jmp play_fx
.endproc
