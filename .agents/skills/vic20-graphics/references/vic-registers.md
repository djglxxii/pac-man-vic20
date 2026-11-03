# VIC-I (MOS 6560 NTSC / 6561 PAL) Register Reference

Sources: Marko Mäkelä's VIC-I.txt, the VIC-20 Programmer's Reference Guide (PRG), VICE source, and the
KERNAL ROM's init table at `$EDE4` (all cross-checked).

## Register map

```
$9000  ABBBBBBB   A = interlace (6560 only)        B = screen X origin (4-pixel units)
$9001  CCCCCCCC   C = screen Y origin (2-line units)
$9002  HDDDDDDD   H = address bit 9 of screen AND colour RAM   D = number of columns
$9003  GEEEEEEF   G = raster line bit 0   E = number of rows   F = 8x16 chars (1) / 8x8 (0)
$9004  GGGGGGGG   raster line bits 8-1 (read only)
$9005  HHHHIIII   H = screen address bits 13-10   I = character address bits 13-10
$9006  light pen X     $9007  light pen Y      (read only)
$9008  paddle X        $9009  paddle Y         (read only)
$900A  bass:    bit 7 on, bits 0-6 frequency
$900B  alto:    bit 7 on, bits 0-6 frequency
$900C  soprano: bit 7 on, bits 0-6 frequency
$900D  noise:   bit 7 on, bits 0-6 frequency
$900E  WWWWVVVV   W = auxiliary colour (0-15)   V = master volume (0-15)
$900F  XXXXYZZZ   X = background ("screen") colour (0-15)   Y = 1 normal / 0 reverse   Z = border colour (0-7)
```

### Power-on values

| Reg | NTSC | PAL | Notes |
|---|---|---|---|
| `$9000` | `$05` | `$0C` | X origin |
| `$9001` | `$19` (25) | `$26` (38) | Y origin |
| `$9002` | `$96` unexpanded / `$16` 8K+ | same | 22 columns; bit 7 set by CINT for the `$1E00` screen |
| `$9003` | `$2E` | `$2E` | 23 rows, 8×8 (bit 7 reads the raster) |
| `$9005` | `$F0` unexpanded / `$C0` 8K+ | same | screen `$1E00` or `$1000`, chars `$8000` ROM |
| `$900E` | `$00` | `$00` | |
| `$900F` | `$1B` | `$1B` | white background, normal, cyan border |

The KERNAL table at `$EDE4` (`$9000–$900F` defaults) is region-specific. Reading `$EDE4`/`$EDE5` gives the
correct centred origin on either NTSC or PAL machines, so `LDA $EDE4 / CLC / ADC #offset / STA $9000` is
portable.

## Geometry

| Field | NTSC 6560 | PAL 6561 |
|---|---|---|
| Columns (`$9002` D) | 0–26 sensible (default 22; >31 treated as 31) | see VIC-I.txt (wider: 71 cycles/line) |
| Rows (`$9003` E) | 0–29 practical (default 23) | more (312 lines); see VIC-I.txt |
| X origin (`$9000` B) | 1–8 for 22 columns. Keep `B + 2·D ≤ 61` (cycles/line − 4) or the picture scrambles | 5–19 |
| Y origin (`$9001` C) | 5–130, no wraparound | 5–155 |
| Visible screen (incl. border) | 201 × 252 (interlaced 253.5) | 229 × 303 |

- Rows of 8×16 characters: each row counts as 16 lines. Set `$9003` E to the number of 16-line rows and
  F = 1.
- **Screen bytes needed = columns × rows.** A bigger screen costs more VIC-visible RAM and more fetch time
  (no CPU cost), and the edges may fall outside a TV's visible area.
- `$9003` bit 7 is the read-only raster bit; just write `(rows << 1) | tall`.
- **1 CPU cycle = 4 pixels horizontally** (dot clock = 4 × φ2). Each 8-pixel cell is 2 cycles: the VIC fetches
  the screen code + colour nibble, then the pattern byte. **This never stalls the CPU.**

## Address selection

- `$9005` high nibble → screen base (bits 13–10). `$9002` bit 7 → address bit 9 of **both** screen and
  colour RAM. Colour RAM is at `$9400` (bit 7 = 0) or `$9600` (bit 7 = 1).
- `$9005` low nibble → character generator base (bits 13–10), 1 KB steps.
- VIC address bit 13 = NOT CPU A15, so:

| Nibble | Base (bit 9 = 0) | Screen with bit 9 = 1 | What is there |
|---|---|---|---|
| 0 | `$8000` | `$8200` | char ROM: upper case + graphics |
| 1 | `$8400` | `$8600` | char ROM: upper case reversed |
| 2 | `$8800` | `$8A00` | char ROM: lower/upper case |
| 3 | `$8C00` | `$8E00` | char ROM: lower/upper reversed |
| 4–7 | `$9000–$9C00` | | I/O: unusable |
| 8 | `$0000` | `$0200` | low RAM (zero page, stack, system!) |
| 9–B | `$0400–$0C00` | | 3K expansion: **not connected to the VIC** |
| C | `$1000` | `$1200` | internal RAM |
| D | `$1400` | `$1600` | internal RAM |
| E | `$1800` | `$1A00` | internal RAM |
| F | `$1C00` | `$1E00` | internal RAM |

`scripts/vicaddr.py --screen 0x1e00 --chars 0x1c00` computes the register values (and the reverse with
`--reg9005`).

Common settings:

| Want | `$9005` | `$9002` bit 7 |
|---|---|---|
| Unexpanded default: screen `$1E00`, ROM chars | `$F0` | 1 |
| Unexpanded, custom chars `$1C00` (+ ROM font as codes 128–255) | `$FF` | 1 |
| Unexpanded, custom chars `$1800` (256 chars, 2 KB, up to `$1FFF`: overlaps screen at `$1E00`!) | `$FE` | 1 |
| 8K+: screen `$1000`, ROM chars | `$C0` | 0 |
| 8K+: screen `$1000`, custom chars `$1800` | `$CE` | 0 |
| 8K+: screen `$1200`, custom chars `$1400` | `$CD` | 1 |
| 160×192 bitmap (MINIGRAFIK): screen + chars `$1000` | `$CC` | 0 |

## Colours

| # | Colour | # | Colour |
|---|---|---|---|
| 0 | black | 8 | orange |
| 1 | white | 9 | light orange |
| 2 | red | 10 | pink |
| 3 | cyan | 11 | light cyan |
| 4 | purple | 12 | light purple |
| 5 | green | 13 | light green |
| 6 | blue | 14 | light blue |
| 7 | yellow | 15 | light yellow |

- **Character (foreground) and border colours: 0–7 only.** Background and auxiliary: 0–15.
- Colour RAM nibble per cell: bits 0–2 = foreground colour, **bit 3 = multicolour mode for that cell**. Reading colour RAM returns garbage in the upper nibble. Always `AND #$0F`.
- `$900F` bit 3: **1 = normal, 0 = reverse** (swaps foreground and background in hires cells only).
  `$900F = (bg << 4) | 8 | border` for normal mode.

## Raster position

```asm
; current raster line (9 bits) = $9004 * 2 + ($9003 bit 7)
        lda $9003
        asl a              ; C = line bit 0
        lda $9004
        rol a              ; (8-bit view: low 8 bits of line; C = bit 8)
```

- NTSC: 261 lines (0–260) × 65 cycles. PAL: 312 × 71. Vertical blank: lines 0–27.
- `$9004` changes every 2 lines, so most code polls `$9004` alone (2-line resolution).
- **NTSC quirk:** on the 6560 the counter changes ~37 cycles earlier relative to the picture than on the 6561,
  i.e. mid-line. Measurements show the field starts with a partial line 0 (32 cycles) and ends with a partial
  line 261 (33 cycles). Code that assumes the counter flips at the start of a line is off by about half a line.
- Interlace (`$9000` bit 7, 6560 only): 525 interlaced lines. Stable-raster constants assume non-interlaced.

## Screen codes vs PETSCII

Screen memory holds **screen codes**, not PETSCII (`CHROUT` takes PETSCII):

| Characters | Screen code | PETSCII |
|---|---|---|
| `@ A–Z [ £ ] ↑ ←` | 0–31 | 64–95 |
| space `! " # … 0–9 … ?` | 32–63 | 32–63 |
| graphics (shifted letters) | 64–95 | 96–127 / 192–223 |
| graphics | 96–127 | 160–191 |
| reversed versions | +128 | — |

PETSCII → screen code: `$20–$3F` same; `$40–$5F` −`$40`; `$60–$7F` −`$20`; `$A0–$BF` −`$40`; `$C0–$FE` −`$80`.

Assembler help: ACME `!scr "TEXT"`, 64tass `.enc "screen"` + `.text`, ca65 `.charmap` (set up a mapping
once, e.g. `.repeat 26, i / .charmap 'A'+i, 1+i / .endrep`).

**With the `$1C00` wrap trick**, ROM characters appear at codes 128–255, so text is written as
`screen code + 128` (and reversed text isn't available).
