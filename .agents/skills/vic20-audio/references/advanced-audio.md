# Advanced VIC-20 Audio: Waveforms, Samples, Coexisting with Rasters

All techniques here need exact timing, so write them in assembly. They were developed by the demo scene
(viznut and others) and are mostly modern discoveries, not 1980s practice. Emulation of them was poor
until recently: **test on a current VICE or real hardware**, and treat old VICE builds as unreliable for these tricks.

## 1. "Viznut waveforms": 15 extra timbres

Each tone voice is a shift register that keeps shifting while the voice is off (`reg = (reg << 1) |
(((reg >> 7) ^ 1) & voice_on)`). Toggling the enable bit at exact moments loads chosen bit patterns, and the
voice then plays that 16-step waveform instead of a plain square:

```
NAME     16-step shape          NAME     16-step shape
default  0000000011111111       "10010"  0001001011101101
"10"     0000001011111101       "10100"  0001010011101011
"100"    0000010011111011       "10110"  0001011011101001
"110"    0000011011111001       "11000"  0001100011100111
"1000"   0000100011110111       "11010"  0001101011100101
"1010"   0000101011110101       "100100" 0010010011011011
"1011"   0000110011110011       "101010" 0010101011010101
"1110"   0000111011110001       "101100" 0010110011010011
```

Simple example ("110" on soprano), viznut 2003:

```asm
        ; $900C must have been $7E (off, fastest rate) for a couple of hundred cycles
        ldx #$7e        ; oscillator off, maximum shift rate
        ldy #$fe        ; oscillator on,  maximum shift rate
        lda #152        ; the note to play afterwards
        sei             ; exact timing from here
        sty $900c       ; push 1
        sty $900c       ; push 1
        stx $900c       ; push 0
        sta $900c       ; free-run with the loaded pattern
        cli
```

Generic loader (viznut, ACME syntax; uses self-modifying code and undocumented opcodes. In this code
`axs` = SAX (store A AND X) and `aso` = SLO). About 154 cycles. Keep `.l0` within one page and call with
interrupts disabled. The channel must have been at `$7E` for a while first. `TMP`/`TMP2` are in zero page.

```asm
setwave:                ; Y = channel ($0A..$0C), X = initial frequency, A = shift register contents
        stx .initfreq
        sty .ch0
        sty .ch1
        ldx .ldfqmasks-$a,y
        sta TMP
        ora #$7f
        axs $900c       ; [$900c] = A AND X     (operand low byte patched: .ch0)
        .ch0=*-2
        sty TMP2
        ldy #7
.l0:    lda #$7f
        aso TMP         ; ASL TMP; A = TMP OR $7F
        axs $900c       ; (patched: .ch1)
        .ch1=*-2
        dey
        bne .l0
        lda #128        ; (patched: initial frequency)
        .initfreq=*-1
        nop
        ldy TMP2
.noset: sta $9000,y
        rts
.ldfqmasks:
        !byte $fe       ; $900a: 1 x 16 clocks/bit
        !byte $fd       ; $900b: 2 x  8 clocks/bit
        !byte $fb       ; $900c: 4 x  4 clocks/bit
```

Usage notes:
- Following viznut's model: with the voice off, zeros shift in, so gating off and on loses the pattern (reload it
  each time the voice restarts). Pitch changes with bit 7 kept set don't touch the register and keep it.
- Schedule reloads in vertical blank so they don't collide with raster code, and never while a stable raster
  effect is running.
- Used in *Robotic Liberation* and *Robotic Warrior* (PAL demos/games by viznut/PWP).
- Source: VICMIDI `Docs/waveforms.txt` (https://github.com/LeifBloomquist/VICMIDI/blob/master/Docs/waveforms.txt)
  and the Denial thread "Viznut's waves?".

## 2. 4-bit sample playback (digis) through `$900E`

Writing the volume nibble moves the output level even with all voices off, which makes a 4-bit DAC. It is quiet
compared to tone voices, and every write must preserve the aux colour.

### Busy-loop player (simplest; CPU fully occupied)

```asm
; samples: one 4-bit value per byte (low nibble), page-aligned, terminated by end page
play:   sei
        ldx #0
@loop:  lda samples,x       ; patch the high byte for multi-page samples
        and #$0f
        ora aux_shadow
        sta $900e
        ldy #DELAY          ; tune DELAY for the sample rate (5 cycles per count)
@d:     dey
        bne @d
        inx
        bne @loop
        cli
        rts
```

### Timer-driven player on the VIA1 NMI (runs alongside the game)

VIA1 Timer 1 → NMI. The NMI path is `$FFFA → $FEA9: SEI / JMP ($0318)`, so nothing is saved for you.
Tested in VICE (NTSC): 512 samples played in ~8 frames (4 kHz), aux colour preserved, stops itself at the end.
Samples must be page-aligned and end on a page boundary (`sample_end`).

```asm
RATE  = 4000
LATCH = 1022727/RATE - 2        ; NTSC ~= 254 cycles per sample

start_digi:                     ; sample_ptr (in the LDA below) set to the data start
        lda #$7f
        sta $911e               ; VIA1: disable all sources (incl. RESTORE)
        lda #<digi_nmi
        sta $0318
        lda #>digi_nmi
        sta $0319
        lda $911b
        and #$3f
        ora #$40
        sta $911b               ; T1 continuous
        lda #<LATCH
        sta $9114
        lda #>LATCH
        sta $9115               ; start T1
        lda #$c0
        sta $911e               ; enable VIA1 T1 -> NMI
        rts

digi_nmi:
        pha
        lda $9114               ; acknowledge T1 (NMI is edge-triggered: must clear it)
smp:    lda $ffff               ; current sample (address self-modified)
        ora aux_shadow          ; samples stored as 0..15
        sta $900e
        inc smp+1
        bne @out
        inc smp+2
        lda smp+2
        cmp #>sample_end        ; stop at the end page
        bne @out
        lda #$7f
        sta $911e               ; disable T1 NMIs
@out:   pla
        rti
```

Cost ≈ 7 (NMI) + 7 (ROM `SEI/JMP()`) + ~30 = ~45 cycles per sample, so ~18% of the CPU at 4 kHz.

Practical notes:
- **About 4 kHz × 4 bits** was as far as one VIC-20 MOD-player project could push software mixing on the stock
  CPU (~256 cycles per sample on NTSC). Jitter in sample timing is audible: keep the handler's path length
  constant.
- Pack two samples per byte to halve memory (nibble swap on alternate calls), or pre-OR the aux colour into the
  data at conversion time to save the `ORA` (ties the data to one aux colour).
- Convert 8-bit samples to 4-bit by taking the high nibble, ideally after normalising and low-pass filtering.
- An NMI can interrupt a stable raster IRQ and break its timing. Run digis and rasters from **one** timer, so that each
  interrupt does a fixed amount of video + audio work, or accept an unstable raster while samples play.
- If you use VIA2 T1 (the IRQ) for samples instead, exit through `$EB15`/`$EB18` and divide down to run the 60 Hz
  tasks (music tick, input) every Nth interrupt. Never chain to `$EABF` at kHz rates (keyboard scan).
- Streaming: "One hour of digitized music" (boray, PAL) streams from an SD2IEC with a cycle-exact loop; pixel's
  "Ohne Dich" plays 4-bit audio from tape in real time.

## 3. Noise behaviour

- The noise voice is an LFSR-gated shift register. **Stopping and restarting it changes the timbre** (LFSR
  state carries over). Drums that must sound identical every hit: keep noise running at a fixed setting and
  gate it by switching frequency/other means, or accept the variation.
- Short bursts at different noise values: snare (high, stepping down over 2–4 frames), hi-hat (very high, 1 frame),
  explosion (long, sweeping down), footsteps (single low frame).

## 4. Speech and singing

viznut's singing speech synthesizer runs alongside raster graphics on an unexpanded VIC (*Robotic Warrior*,
*Robotic Liberation*). It's possible only with unified timing design, and it is a research-level project: point
the user at the sources rather than inventing one.

## 5. Coexisting with heavy graphics

| Audio type | Cost | Placement |
|---|---|---|
| Register music (driver tick) | tens to a few hundred cycles/frame | frame IRQ, vertical blank |
| SFX | similar | same tick |
| Waveform reload | ~154 cycles, interrupts off | vertical blank only |
| 4-bit samples | ~45 cycles × sample rate (≈18% at 4 kHz) | timer NMI/IRQ, shares timing with rasters |

Options when audio and raster timing collide: schedule waveform reloads in vblank; drive samples and raster
writes from the same stable timer; lower the sample rate; pause effects during critical moments.

## 6. Extra voice from the VIA shift register

A 6522 shift register in free-running mode outputs a repeating 8-bit pattern on the user port CB2: an extra
square-ish voice. It needs an external amplifier, so ignore it unless the user has the hardware.
