# Bitmap Emulation, Screen Layouts and Scrolling

## Why a full bitmap is hard

A 22×23 screen has 506 cells, but only 256 character codes exist, and 506 unique 8×8 glyphs would need
4 KB+ of VIC-visible RAM. Practical bitmaps use fewer, taller cells.

## 160×192 "MINIGRAFIK" bitmap (`assets/bitmap160.s`, tested on +8K)

Mike's canonical layout, also used by cc65's `vic20-hi.tgi` driver:

| Item | Value |
|---|---|
| Screen matrix | `$1000–$10EF`: 20 × 12 cells, codes `$10–$FF`, **column-major** (`$10 + col*12 + row`) |
| Characters | 8×16 (`$9003` bit 0), base `$1000` (`$9005 = $CC`); code `$10` → `$1100` |
| Bitmap | `$1100–$1FFF` (3,840 bytes) |
| Pixel address | `$1100 + (x >> 3) * 192 + y`, mask `$80 >> (x & 7)` |
| Colour | colour RAM `$9400` (`$9002` bit 7 = 0), one colour per 8×16 cell |
| Registers (NTSC) | `$9000 = $EDE4+2 (7)`, `$9001 = $EDE5−2 (23)`, `$9002 = 20`, `$9003 = $19`, `$9005 = $CC` |
| Needs | +8K or more: code can't live in `$1000–$1FFF` |

Each 8×16 tile needs 17 bytes (1 matrix + 16 pattern), and 4096 / 17 ≈ 240 tiles = 160×192. That is the largest
resolution an unmodded VIC-20 can show without the low 1 KB or raster tricks.

Column-major layout means **a column of the bitmap is 192 consecutive bytes**: vertical lines and sprite
columns are `INY` loops through one pointer. Use a 20-entry column base table (`col_lo/col_hi`).

API in the asset: `bmp_init` (A = colour), `bmp_clear`, `bmp_colour`, `bmp_plot` / `bmp_unplot` (X = x,
Y = y). Line drawing: Bresenham over `bmp_plot`, or specialised horizontal (byte fills) and vertical (`INY`
down a column) routines.

Multicolour version: set colour RAM to 8–15 for 80×192 with 4 colours (2-px wide pixels; the pixel mask
changes to 2 bits).

## Other screen layouts

- **Unique-char framebuffer with 8×16 chars** (*Jetpac*): 23 columns × 11 rows = 253 unique 8×16 chars at
  `$1000` ≈ 4 KB of definitions. Its screen matrix has to live elsewhere in VIC-visible RAM (the low 1 KB).
- **Screen matrix in low RAM (`$0200` area)** frees all of `$1000–$1FFF` for character data (Denial thread
  "Using screen memory at location $200"). Mind the KERNAL workspace there (take over the machine first).
- **Bigger screens:** NTSC allows up to ~26 columns × ~29 rows by moving the origin. Overscan isn't visible on all TVs and
  costs matrix RAM.
- **Raster-switched character sets:** change `$9005` mid-screen with a stable raster so each band has its own
  256 glyphs. That gives larger bitmaps and more colour, at the cost of CPU time every frame.

## Scrolling

Hardware support is minimal:
- `$9000` moves the whole picture horizontally in **4-pixel steps** (half a character).
- `$9001` moves it vertically in **2-line steps**.
- Changing the origin moves the edges too (ragged edges), unless the screen is narrowed so the edges sit in
  the overscan or border.

Techniques (cheapest first):

| Technique | Smoothness | Cost |
|---|---|---|
| **Coarse scroll**: shift the screen matrix by one cell (and colour RAM if not uniform) | 8 px jumps | ~506 bytes moved; spread it, or use the page flip and draw the shifted screen into the hidden page |
| **Half-character steps**: alternate `$9000` between X and X+1, then coarse-shift and reset | 4 px | coarse shift every other step |
| **Tile-pair characters**: pre-render every combination of adjacent tiles at each pixel offset; every 8 px recompute which pair-chars to use | 1–2 px | character slots: tiles² × phases; works for small tile sets (Kweepa's method) |
| **Shift character definitions**: scroll the bitmap of unique characters (unique-char framebuffer) with `ROL`/`ROR` chains | 1 px | very expensive for a whole screen; OK for a narrow band (a scrolling message line) |
| **Character-definition animation**: scroll the *texture* inside repeated chars (background patterns, starfields) | 1 px | 8 stores per char type |

- Do coarse shifts and `$9000`/`$9001` writes during vblank (or at a stable raster point) to avoid tearing.
- Combine: page flip + coarse scroll into the hidden page + `$9000` half-step gives smooth-looking 4-px
  scrolling at low cost. Many VIC-20 scrollers (e.g. streetuff/TRSI's demo) use 4-px steps.
- *Pulse* achieves horizontally smooth scrolling on an unexpanded VIC. Its source is a good study.

Vertical smooth scroll: `$9001` 2-line steps + coarse row shifts, or shifting the bytes of the characters
in a band.
