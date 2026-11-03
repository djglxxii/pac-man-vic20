# Programmable Characters, Multicolour and Colour Design

The VIC-I has no sprites and no bitmap mode. **Everything is programmable characters.** Screen matrix
entries pick a character (0–255), the character set supplies 8 (or 16) bytes of pixels, and colour RAM
supplies one colour nibble per cell.

## Setting up a custom character set

1. Choose a 1 KB-aligned location the VIC can see: `$1000`, `$1400`, `$1800` or `$1C00` (or `$0000` in low
   RAM, rarely). It must not overlap the screen matrix or your code.
2. Copy or decompress the character data there at startup. If you also want text, copy the needed ROM glyphs from
   `$8000` (each glyph = 8 bytes at `$8000 + screencode*8`).
3. Point `$9005` low nibble at it (`scripts/vicaddr.py`).

Capacity: 8×8 chars use 8 bytes each (64 per 512 bytes, 128 per KB, 256 = 2 KB). 8×16 chars use 16 bytes
(a full 256-char set = 4 KB = all the internal RAM).

### The `$1C00` wrap trick (unexpanded machines)

Set the char base to `$1C00` (`$9005` = `$FF` with the screen at `$1E00`). Codes 0–63 come from RAM
`$1C00–$1DFF`. Codes 64–127 would read `$1E00–$1FFF` (the screen itself, so don't use them). Codes
128–255 wrap around the VIC address space to the **character ROM at `$8000`**: the normal upper-case/graphics
font. You get 64 custom characters and a full text font at the cost of only 512 bytes. This is the standard
layout for unexpanded games (used by the skeleton in `vic20-system/assets/template-ca65`).

## Hires vs multicolour cells

| | Hires cell | Multicolour cell |
|---|---|---|
| Enabled by | colour RAM bit 3 = 0 (values 0–7) | colour RAM bit 3 = 1 (values 8–15) |
| Pixels | 8 × 8, 1 bit each | 4 × 8, 2 bits each (double width) |
| Colours | background (`$900F` hi) or cell colour (0–7) | 4: see below |

Multicolour bit pairs (**PRG and VICE; VIC-I.txt swaps 01/10 and is wrong**):

| Bits | Colour source | Scope |
|---|---|---|
| `00` | background (`$900F` bits 4–7) | global |
| `01` | border (`$900F` bits 0–2) | global |
| `10` | character colour (colour RAM bits 0–2) | per cell |
| `11` | auxiliary (`$900E` bits 4–7) | global |

- Three of the four multicolour sources are **global**. Design art around a shared background / border / aux
  palette and use the per-cell colour for local variety. Changing background/border/aux per raster band
  (`raster-and-buffering.md`) multiplies the palette.
- Hires and multicolour cells can be mixed freely on one screen (per-cell bit 3).
- **Never write `$900E` without preserving the aux nibble.** Sound code and graphics code must share an
  aux-colour shadow variable.
- Reverse mode (`$900F` bit 3 = 0) affects hires cells only.

`scripts/charconv.py` converts ASCII art to `.byte` data. Hires: `.`/space = off, anything else = on.
Multicolour: `.`=bg, `b`=border, `f`=char colour, `a`=aux. `--preview` shows decoded bytes, `--png` reads
images.

## Double-height (8×16) characters

`$9003` bit 0 = 1. Each code addresses 16 bytes; rows count in 16-line units. Uses:
- Bitmap emulation (160×192 = 20×12 tall cells covering 240 unique codes).
- Halving the screen matrix size (fewer cells to update).
- Taller sprites/tiles with one code.

Colour still applies per 8×16 cell.

## Colour clash

Each cell has one foreground colour (and multicolour cells share three global colours). A moving object takes
the colour of whatever cell it overlaps unless you also rewrite colour RAM, which recolours that cell's
background pixels too. Strategies:
- Design backgrounds in the same colour as the objects that cross them, or keep play areas mostly background colour.
- Use multicolour with border/aux reserved for sprites (global colours never clash).
- Rewrite colour RAM for sprite cells and accept the tint on background pixels (Jetpac does per-tile colour updates).
- Raster-split the global colours by band.

## Character-definition animation (cheapest effect)

Rewrite the 8 bytes of a character and **every cell showing it animates**: water, conveyor belts, flames,
blinking items, starfields, scrolling background textures. Cost: 8 stores (unrolled ≈ 64 cycles).

```asm
; rotate a texture char left by one pixel (wrapping) - conveyor/waves
        ldx #7
:       lda CHARSET+TILE*8,x
        asl a
        adc #0              ; carry (old bit 7) -> bit 0
        sta CHARSET+TILE*8,x
        dex
        bpl :-
; scroll a texture char down by one row (falling rain)
        lda CHARSET+TILE*8+7
        ldx #6
:       ldy CHARSET+TILE*8,x
        sty CHARSET+TILE*8+1,x
        dex
        bpl :-
        sta CHARSET+TILE*8
```

Jeff Minter's *Gridrunner* is entirely character based; *Matrix* scrolls its grid by `ROL`-ing a character's
bytes in place and syncs by polling `$9004`.

## Budgeting the character set

Characters are glyphs, animation frames and pseudo-framebuffer at the same time. Partition the 64/128/256
codes explicitly, and write the plan in a comment or the README:

```
codes   0-31   static background tiles
codes  32-39   shared animated tiles (water, lava)
codes  40-55   software-sprite pool (4 per 8x8 sprite, 9 per 16x16)
codes  56-63   HUD digits / icons
codes 128-255  ROM font (via $1C00 wrap)
```

Each unique sprite position costs pool characters. Running out is the usual failure of software-sprite
engines. *Pulse*, for example, reuses the last character when its pool runs out, causing a visible glitch.
