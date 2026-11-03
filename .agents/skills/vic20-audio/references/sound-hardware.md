# VIC-20 Sound Hardware Reference (MOS 6560 / 6561)

## Registers

| Address | Dec | Name | Bits |
|---|---|---|---|
| `$900A` | 36874 | Bass (voice 1) | bit 7 = on, bits 0–6 = frequency value |
| `$900B` | 36875 | Alto (voice 2) | bit 7 = on, bits 0–6 = frequency value |
| `$900C` | 36876 | Soprano (voice 3) | bit 7 = on, bits 0–6 = frequency value |
| `$900D` | 36877 | Noise (voice 4) | bit 7 = on, bits 0–6 = frequency value |
| `$900E` | 36878 | Volume + aux colour | **bits 4–7 = auxiliary colour (graphics!)**, bits 0–3 = master volume 0–15 |

- Any register value below 128 silences that voice. The register stays writable, and the internal shift register keeps clocking (this is what the waveform trick relies on).
- The KERNAL init table zeroes `$900A–$900E` at reset. Nothing in the KERNAL touches sound after that.
- **Volume is global.** There is no per-voice volume, no ADSR, no filter, no pulse width, no ring/sync modulation.

## Frequency formula

From Marko Mäkelä's VIC-I.txt (and matching VICE's implementation):

```
f = Phi2 / DIV / (128 − ((reg + 1) AND 127))

DIV:  bass 256, alto 128, soprano 64, noise 32
Phi2: NTSC 14318181/14 = 1,022,727 Hz    PAL 4433618/4 = 1,108,405 Hz
```

For `reg = 128 + X` with X in 0..126 this simplifies to `f = (Phi2/DIV) / (127 − X)`:

| Voice | NTSC base clock Phi2/DIV | PAL base clock |
|---|---|---|
| Bass | 3,995 Hz | 4,330 Hz |
| Alto | 7,990 Hz | 8,659 Hz |
| Soprano | 15,980 Hz | 17,319 Hz |
| Noise | 31,960 Hz | 34,638 Hz |

The same register value plays **one octave higher on each successive voice**. Resolution is poor at the top
of each voice's range (adjacent values become a semitone or more apart), so high notes go out of tune: the
"dusty piano" sound. A NTSC table and a PAL table are different; regenerate with `scripts/notetable.py --pal`.

Usable note ranges on NTSC (computed with `scripts/notetable.py`, A4 = 440 Hz):

| Voice | Every note within ±20 cents | Every note within ±35 cents |
|---|---|---|
| Bass `$900A` | C1 – G2 | C1 – C4 |
| Alto `$900B` | C2 – G3 | C2 – C5 |
| Soprano `$900C` | C3 – G4 | C3 – C6 |

So each voice is in tune for about 1.5 octaves, acceptable for 3, and badly out of tune above that. Keep
melodies in the lower part of a voice's range, or move them to the next voice down (`--best`). PAL ranges
are shifted by about a semitone (C#1–A3 on bass at ±35 cents).

Run `python3 scripts/notetable.py` for the exact per-note values and cent errors. `--best` picks, for each
note, the voice with the least tuning error (useful for chords and arpeggios that can move between voices).

## Programmer's Reference Guide note values (approximate, NTSC)

The PRG's table (Appendix C). The same value is an octave higher on each successive voice. Useful for BASIC
programs and for checking generated tables:

| Note | Value | Note | Value |
|---|---|---|---|
| C | 135 | G | 215 |
| C# | 143 | G# | 217 |
| D | 147 | A | 219 |
| D# | 151 | A# | 221 |
| E | 159 | B | 223 |
| F | 163 | C | 225 |
| F# | 167 | C# | 227 |
| G | 175 | D | 228 |
| G# | 179 | D# | 229 |
| A | 183 | E | 231 |
| A# | 187 | F | 232 |
| B | 191 | F# | 233 |
| C | 195 | G | 235 |
| C# | 199 | G# | 236 |
| D | 201 | A | 237 |
| D# | 203 | A# | 238 |
| E | 207 | B | 239 |
| F | 209 | C | 240 |
| F# | 212 | C# | 241 |

(Read the left column top to bottom, then the right column.) Prefer the generated table for anything that
needs to sound in tune; the PRG values have several large errors.

## How a voice really works (viznut's reverse engineering, 2003)

- Each tone voice = 7-bit counter + 8-bit shift register. The counter is clocked at Phi2/16 (bass), /8 (alto) or /4 (soprano).
  When it reaches `$7F` it reloads from the frequency value and the shift register shifts once.
- Shift rule: `reg = (reg << 1) | (((reg >> 7) ^ 1) & voice_on)`. Output = bit 0.
- A free-running register therefore produces a 16-step square wave (8 high, 8 low): `0000000011111111`.
- The register shifts even while the voice is off. Toggling bit 7 at exact moments injects 1s and 0s,
  giving 15 extra waveforms. See `advanced-audio.md`.
- **Noise:** an LFSR gating a shift register (reverse-engineered by Lance Ewing; VICE bug #1125 implements it).
  Stopping and restarting the noise voice changes its timbre slightly, because the LFSR state carries over.

## Output level details

- Writing the volume nibble changes the DC output level even with every voice off. That is how 4-bit
  sample playback works, and also why **volume changes click**. Ramp volume in small steps, or change it
  only while voices are at a quiet point.
- A full 0→15 swing of the volume nibble is small compared with a voice's amplitude (one emulator
  measurement: ~0.22 of one voice step), so digitized sound is quiet next to tone voices.

## Extra square-wave voice via the 6522 (rarely useful)

The VIA's shift register in free-running mode outputs a programmable bit pattern on the user port's CB2.
It needs an external amplifier or speaker, so normal software can't rely on it.

## Safe `$900E` writes

The high nibble of `$900E` is the **multicolour auxiliary colour**. Sound code that writes `STA $900E` with
only a volume value turns the aux colour black and breaks multicolour graphics. Always merge:

```asm
; preferred: keep a shadow of the aux colour (aux << 4) in zero page
set_volume:                 ; A = 0..15
        and #$0f
        ora aux_shadow
        sta $900e
        rts

; alternative: read-modify-write (slower, and wrong if raster code changes aux mid-frame)
        and #$0f
        sta tmp
        lda $900e
        and #$f0
        ora tmp
        sta $900e
```

Every module that writes `$900E` (graphics code that changes the aux colour, music, digis) must use the
same shadow variable.
