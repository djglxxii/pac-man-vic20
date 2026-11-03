---
name: vic20-audio
description: Commodore VIC-20 sound and music programming on the 6560/6561 VIC chip. Covers the three square-wave voices + noise ($900A-$900D), the shared volume/aux-colour register $900E, exact NTSC/PAL frequency formula and note tables, music driver design (tested ca65 driver with sound-effect voice stealing), software envelopes, arpeggios, vibrato, noise percussion, sound-effect recipes, viznut's extra waveforms, 4-bit sample (digi) playback via the volume register, and running audio alongside raster graphics. Includes a note-table generator. Use for any VIC-20 sound effect, music, tracker replay, note table, or audio timing task.
---

# VIC-20 Audio

The VIC chip gives you **3 square-wave voices an octave apart + 1 noise voice, one global 4-bit volume, and
nothing else**: no ADSR, no filter, no pulse width, no per-voice volume. Every articulation is CPU register
writes, usually once per frame.

## Bundled resources

| File | Use it for |
|---|---|
| `references/sound-hardware.md` | Registers, exact frequency formula, base clocks NTSC/PAL, usable note ranges, the PRG note table, how the voices work internally, output-level quirks, **aux-colour-safe volume writes** |
| `references/music-driver.md` | **Tested** compact ca65 music + SFX driver (4 channels, durations, gate/staccato, loops, SFX voice stealing with music restore), data format, IRQ hookup, extension ideas |
| `references/advanced-audio.md` | viznut's 15 extra waveforms + loader, 4-bit digis (busy loop and a **tested** VIA1-NMI player), noise behaviour, speech, coexisting with raster code |
| `scripts/notetable.py` | Note tables for NTSC/PAL with cent errors; per voice or best-voice; outputs Markdown, ca65, ACME, C; `--freq`/`--reg` lookups |

```bash
python3 .claude/skills/vic20-audio/scripts/notetable.py --format ca65 --voice alto --from C3 --to B4
python3 .claude/skills/vic20-audio/scripts/notetable.py --freq 440          # closest value on each voice
python3 .claude/skills/vic20-audio/scripts/notetable.py --pal               # PAL Markdown table
```

## Essentials

| Register | Voice | NTSC base (Hz) |
|---|---|---|
| `$900A` (36874) | bass | 3,995 |
| `$900B` (36875) | alto | 7,990 |
| `$900C` (36876) | soprano | 15,980 |
| `$900D` (36877) | noise | 31,960 |
| `$900E` (36878) | bits 0–3 volume, **bits 4–7 aux colour** | |

- `f = base / (127 − X)` for register value `128 + X` (X = 0…126). Values < 128 = voice off.
  Exact form: `f = φ2 / DIV / (128 − ((reg+1) & 127))`, φ2 = 1,022,727 Hz NTSC, 1,108,405 Hz PAL.
- **The same value is one octave higher on each successive voice.** Each voice is in tune (±35 cents) for about
  3 octaves: bass C1–C4, alto C2–C5, soprano C3–C6 (NTSC). The top of each range is badly out of tune.
- **NTSC and PAL need different note tables.** Generate them; never copy values between standards.
- Fixed voice roles fall out of the ranges: bass line on `$900A`, harmony/arpeggio on `$900B`, melody on `$900C`,
  drums on `$900D`.

## Rules

1. **Never write a bare volume to `$900E`.** Keep `aux_shadow = aux << 4` and write `ORA aux_shadow`.
   Graphics code that changes the aux colour must update the same shadow.
2. **Tick audio from one place at a fixed rate**: the frame IRQ (60 Hz NTSC, 50 Hz PAL; tempo differs!). Put
   the driver in assembly; a per-frame C driver costs a lot and jitters.
3. **Volume is global**: a volume envelope pulses the whole mix. Articulate notes with gate length (bit 7 off),
   pitch movement and arpeggios instead. Change volume only on the tick, in small steps (volume changes click).
4. **Sound effects steal a voice** (usually soprano or noise) and hand it back to the music afterwards (the bundled
   driver does this).
5. **Silence on exit/game over**: write 0 to `$900A–$900D` and set volume to 0 (aux-safe).
6. Cycle-exact audio (waveform loading, digis) must be assembly and must be scheduled against any raster code.

## Sound-effect recipes (one register value per frame)

Table-driven effects are small and easy to tune. Data for the bundled driver's `sfx_*` format (values < `$80`
are silent frames, `$01` ends):

```asm
sfx_laser:   .byte 250,246,242,238,234,230,226,222,218,214, $01          ; soprano, falling
sfx_jump:    .byte 200,204,208,212,216,220,224,228, $01                  ; alto, rising
sfx_pickup:  .byte 225,225,235,235,240,240,245,245, $01                  ; soprano, two-step chirp
sfx_hit:     .byte 160,150,140,135,130, $01                              ; bass, short thud
sfx_explode: .byte 250,248,246,244,240,236,232,228,224,220,216,212,208,204,200,196,192, $00, $01  ; noise
sfx_snare:   .byte 250,240,230, $00, $01                                 ; noise
sfx_hihat:   .byte 254, $00, $01                                         ; noise
sfx_step:    .byte 180, $00, $01                                         ; noise, footstep
sfx_alarm:   .byte 230,230,230,0,0,0,230,230,230,0,0,0, $01              ; alto, beeping
```

Kick drum: a quick pitch drop on the bass voice (`200,180,160,140`) plus one low noise frame. Engine hum: bass
voice alternating two adjacent low values every frame. Tune by ear in VICE: write the effect, play it in a
loop, adjust.

## Music workflow

1. Decide the tick rate and tempo (frames per row/beat). NTSC = 60 Hz.
2. Generate the note table for the target standard and the voices actually used (`notetable.py`), and give
   the values names.
3. Author the data: hand-written streams for the bundled driver, or a tracker (VIC-TRACKER: edit on a 16K
   machine, export a compact replay that runs unexpanded; Fisichella; Vicious Tracker). Use the tracker's own
   replay routine for its data.
4. Hook `sound_tick` into the frame IRQ, start with `music_init`, trigger effects with `sfx_play`.
5. Test headless in VICE (driver state checks) and by ear (`xvic` with sound).

## Verification

- Register-level logic (which value lands in `$900A–$900D` when) can be unit-tested headless:
  `vic20-system/scripts/vice-test.sh` with a harness that calls the tick N times and checks the registers
  (they read back in VICE). See how `references/music-driver.md` was tested.
- Pitch/tuning: compare with `notetable.py` output. Timbre and balance need listening, so tell the user what to listen for.
- Waveform tricks and digis: current VICE emulates them reasonably; older VICE did not. Real hardware is the
  final judge.
