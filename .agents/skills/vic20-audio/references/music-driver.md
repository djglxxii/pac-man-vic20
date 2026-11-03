# A Compact VIC-20 Music + Sound-Effect Driver (ca65)

A complete, small (~250 bytes of code) driver suitable for games. It is a starting point: adapt the data
format, add arpeggio/vibrato tables, or replace it with a tracker replay (VIC-TRACKER, Vicious Tracker,
Fisichella) when the music is authored in a tracker.

Tested: assembled with ca65 and checked in VICE xvic (NTSC) for note-on, gate-off, next note, SFX
steal/release, stream looping and end-of-stream.

Design:
- One `sound_tick` call per frame (60 Hz NTSC) from your IRQ handler, after the timer acknowledge.
- 4 channels (bass, alto, soprano, noise), each reading its own byte stream.
- Sound effects **steal** a voice: while `ch_lock,x` is set, the music keeps advancing silently on that channel; when the effect ends, the music's current note is restored.
- Volume is global, so the driver never changes volume (set it once, through the aux-colour-safe routine).

## Stream format (per channel)

| Byte | Meaning |
|---|---|
| `$80`–`$FE` | Note: raw register value (bit 7 = voice on). Plays for the current duration |
| `$00` | Rest for the current duration |
| `$01`–`$3F` | Set duration (ticks) for the following notes/rests |
| `$40`–`$7E` | Set gate = value − `$40`: ticks the voice stays on within each note (0 = whole note). Gives staccato and separates repeated notes |
| `$7F lo hi` | Jump to address (loop) |
| `$FF` | End: silence and stop the channel |

Use `scripts/notetable.py --format ca65 --voice alto` to get note register values, then name them with
constants so the data stays readable (for example `A3 = $B6`).

## Code

All entry points (`music_init`, `music_stop`, `sound_tick`, `music_tick`, `sfx_play`) clobber A, X and Y.
Inside the KERNAL IRQ path that's fine (registers are restored on exit). Called from the main loop, save
what you need first.

```asm
; ---------------- zero page ----------------
.zeropage
mptr:   .res 2
mtmp:   .res 1

; ---------------- state (4 channels) ----------------
.bss
ch_on:       .res 4
ch_ptr_lo:   .res 4
ch_ptr_hi:   .res 4
ch_timer:    .res 4
ch_dur:      .res 4
ch_gate:     .res 4
ch_gateoff:  .res 4
ch_last:     .res 4     ; last value the music wrote (restored after an SFX)
ch_lock:     .res 4     ; non-zero = an SFX owns this voice
sfx_ptr_lo:  .res 4
sfx_ptr_hi:  .res 4

VOICE = $900a           ; $900A + X, X = 0 bass, 1 alto, 2 soprano, 3 noise

.code
; ---------------- start a song ----------------
; song_lo/song_hi: 4-entry tables of channel stream addresses
music_init:
        ldx #3
@l:     lda song_lo,x
        sta ch_ptr_lo,x
        lda song_hi,x
        sta ch_ptr_hi,x
        lda #1
        sta ch_on,x
        sta ch_timer,x          ; first tick fetches the first event
        lda #8
        sta ch_dur,x
        lda #0
        sta ch_gate,x
        sta ch_lock,x
        sta ch_last,x
        sta VOICE,x
        dex
        bpl @l
        rts

music_stop:
        ldx #3
        lda #0
@l:     sta ch_on,x
        sta VOICE,x
        dex
        bpl @l
        rts

; ---------------- per-frame entry point ----------------
sound_tick:
        jsr sfx_tick
        ; fall through
music_tick:
        ldx #3
@ch:    lda ch_on,x
        beq @next
        dec ch_timer,x
        bne @gate
        jsr read_events
        jmp @next
@gate:  lda ch_timer,x
        cmp ch_gateoff,x
        bne @next
        lda #0                  ; gate closes: voice off
        sta ch_last,x
        ldy ch_lock,x
        bne @next
        sta VOICE,x
@next:  dex
        bpl @ch
        rts

; X = channel. Consumes commands until a note/rest/end. Preserves X.
read_events:
        lda ch_ptr_lo,x
        sta mptr
        lda ch_ptr_hi,x
        sta mptr+1
        ldy #0
@rd:    lda (mptr),y
        iny
        cmp #$80
        bcs @note               ; $80-$FF
        cmp #$40
        bcs @cmd                ; $40-$7F
        cmp #0
        beq @note               ; $00 rest
        sta ch_dur,x            ; $01-$3F duration
        bpl @rd                 ; always
@cmd:   cmp #$7f
        beq @jump
        and #$3f                ; $40-$7E gate
        sta ch_gate,x
        bpl @rd                 ; always
@jump:  lda (mptr),y
        pha
        iny
        lda (mptr),y
        sta mptr+1
        pla
        sta mptr
        ldy #0
        beq @rd                 ; always
@note:  sta mtmp
        tya                     ; save advanced stream pointer
        clc
        adc mptr
        sta ch_ptr_lo,x
        lda #0
        adc mptr+1
        sta ch_ptr_hi,x
        lda ch_dur,x            ; restart note timer
        sta ch_timer,x
        sec
        sbc ch_gate,x           ; gate-off point = dur - gate
        bcs :+
        lda #0                  ; gate >= dur: never gate off
:       sta ch_gateoff,x
        lda mtmp
        cmp #$ff
        bne :+
        lda #0
        sta ch_on,x             ; end of stream
:       sta ch_last,x
        ldy ch_lock,x
        bne :+
        sta VOICE,x
:       rts

; ---------------- sound effects ----------------
; Effect data: one register value per frame; values < $80 are silent frames; $01 terminates.
; sfx_voice / sfx_lo / sfx_hi: tables indexed by effect number.
sfx_play:                       ; A = effect number. Safe to call from the main loop.
        tay
        php
        sei                     ; don't let the IRQ see a half-written pointer
        ldx sfx_voice,y
        lda sfx_lo,y
        sta sfx_ptr_lo,x
        lda sfx_hi,y
        sta sfx_ptr_hi,x
        lda #1
        sta ch_lock,x
        plp
        rts

sfx_tick:
        ldx #3
@ch:    lda ch_lock,x
        beq @next
        lda sfx_ptr_lo,x
        sta mptr
        lda sfx_ptr_hi,x
        sta mptr+1
        ldy #0
        lda (mptr),y
        cmp #$01
        beq @done
        sta VOICE,x
        inc sfx_ptr_lo,x
        bne @next
        inc sfx_ptr_hi,x
        bne @next               ; always
@done:  lda #0
        sta ch_lock,x
        lda ch_last,x           ; hand the voice back to the music
        sta VOICE,x
@next:  dex
        bpl @ch
        rts
```

## Example data

```asm
; NTSC alto values (from notetable.py --voice alto): name them
A2 = $B6
C3 = $C2
E3 = $CF
G3 = $D6

song_lo: .byte <bass_ch, <alto_ch, <silent_ch, <drum_ch
song_hi: .byte >bass_ch, >alto_ch, >silent_ch, >drum_ch

alto_ch:
@loop:  .byte 12, $40+8         ; duration 12 ticks, gate 8 (staccato)
        .byte C3, E3, G3, E3
        .byte 24, $40           ; long note, full gate
        .byte A2
        .byte $7f
        .word @loop

bass_ch:
@loop:  .byte 24, $40+20
        .byte $C2, $C2, $B6, $B6 ; bass register values (generate with --voice bass)
        .byte $7f
        .word @loop

drum_ch:                        ; noise: short hits
@loop:  .byte 12, $40+2
        .byte $F0, $00, $D0, $00
        .byte $7f
        .word @loop

silent_ch:
        .byte $ff

; Sound effects
SFX_LASER = 0
SFX_EXPLODE = 1
sfx_voice: .byte 2, 3           ; soprano, noise
sfx_lo:    .byte <sfx_laser, <sfx_explode
sfx_hi:    .byte >sfx_laser, >sfx_explode
sfx_laser:   .byte 250,246,242,238,234,230,226,222,218,214, $01
sfx_explode: .byte 250,248,246,244,240,236,232,228,224,220,216,212,208,204,200,196,192, $00, $01
```

## Hooking into the frame IRQ

```asm
game_irq:                       ; installed at $0314/$0315 (see vic20-system skill)
        ; ... frame-critical work first (page flip, raster) ...
        jsr sound_tick
        jmp $eb15               ; acknowledges VIA2 T1 (BIT $9124) and restores A/X/Y, RTI
```

Set the volume once at startup through the aux-safe routine (`sound-hardware.md`). For a global
fade-out, step the volume down every N frames.

## Extensions (add only when the music needs them)

- **Arpeggio:** per-channel table of register offsets cycled every tick (`VOICE,x = base + arp[i]`). Suggests chords on one voice; the classic 60 Hz chiptune shimmer.
- **Vibrato / pitch slide:** add ±1 to the register value every N ticks. The step size in cents varies wildly across the range because of the 127−X divider.
- **Fine detune:** alternate between two adjacent register values each tick to land between pitches (PRG p.101 describes this "modulate between two values" approach).
- **Volume accent:** because volume is global, accenting one note accents everything. Use gate length and arpeggio for articulation instead.
- **Tempo:** change `ch_dur` values, or tick the music only every other frame for 30 Hz songs.
- **Size:** for an unexpanded machine, pack streams with run lengths, or let a tracker's compressor (VIC-TRACKER) generate the data and replay code.
