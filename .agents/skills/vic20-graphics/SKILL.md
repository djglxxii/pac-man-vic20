---
name: vic20-graphics
description: Commodore VIC-20 graphics programming with the MOS 6560 (NTSC) / 6561 (PAL) VIC-I chip. Covers VIC registers $9000-$900F, screen and character-set addressing ($9005/$9002), colour RAM and multicolour rules, custom/redefined characters, the $1C00 ROM-font wrap trick, 8x16 characters, software sprites, XOR sprites, the 160x192 MINIGRAFIK bitmap, scrolling, raster splits and cycle-stable raster IRQs, screen/colour double buffering, colour clash and character-set budgeting. Includes tested ca65 modules (software sprite, bitmap, NTSC stable raster) and converters for character art and VIC addresses. Use for any VIC-20 drawing, animation, sprite, display layout or screen-effect task.
---

# VIC-20 Graphics

The VIC-I has **no sprites, no bitmap mode and no raster interrupt**. Everything is built from programmable
characters, colour RAM, a handful of global colour registers and CPU timing. The good news: the VIC never
steals CPU cycles, so timing is fully predictable.

Load `vic20-system` for memory configuration and IRQ setup, `6502-assembly` for code-level optimisation, and
`vic20-optimization` for frame budgets.

## Bundled resources

| File | Use it for |
|---|---|
| `references/vic-registers.md` | Every register bit, power-on values (NTSC/PAL), geometry limits, `$9005` address table, common settings, colours, raster reading, NTSC raster quirks, screen codes vs PETSCII |
| `references/characters-and-colour.md` | Custom charsets, the `$1C00` wrap trick, hires vs multicolour (**01 = border, 10 = char colour**), 8×16 chars, colour clash strategies, character animation code, charset budgeting |
| `references/software-sprites.md` | Approach comparison, the tested sprite module, measured costs, multi-sprite rules, flicker fixes, XOR sprites (Jetpac), libraries (VIC-SSS, Pulse), collision detection |
| `references/raster-and-buffering.md` | Timing constants, polling splits, frame-locked IRQ, stable raster method and rules, what to write mid-frame, screen/colour page flip (verified), charset buffering alternatives |
| `references/display-modes-and-scrolling.md` | 160×192 bitmap layout and addressing, other layouts (Jetpac, low-RAM screen, overscan), scrolling techniques |
| `assets/softsprite.s` | **Tested** 8×8 software sprite (copy + OR into 4 pool chars), works over RAM and ROM chars |
| `assets/bitmap160.s` | **Tested** 160×192 bitmap: init (NTSC/PAL-portable origin), clear, colour, plot/unplot (+8K) |
| `assets/stable-raster-ntsc.s` | **Tested** cycle-exact NTSC raster IRQ (sync + timer + jitter slide) with an example mid-line effect |
| `scripts/charconv.py` | ASCII art / PNG → hires or multicolour char data (ca65/ACME/C/bin), `--preview`, `--tall` |
| `scripts/vicaddr.py` | Screen/charset address ↔ `$9005`/`$9002` values; `--table` lists every legal base |

## Hard limits to design around

- **VIC-visible RAM:** `$1000–$1FFF` (+ `$0000–$03FF`) and the char ROM. Screens, charsets and bitmaps
  must fit there. Expansion RAM can't be displayed.
- **Default screen 22×23 cells = 176×184 px**, 506-byte matrix. Up to ~26×29 on NTSC with overscan.
- **Colour per cell:** one foreground colour 0–7. Multicolour cells add 3 **global** colours (background,
  border, aux) at half horizontal resolution.
- **Characters: max 256 codes.** Each 8×8 costs 8 bytes (16 for 8×16). Glyphs, animation frames and sprite
  pools all compete for codes.
- **Hardware scroll:** 4-px horizontal, 2-line vertical steps of the whole picture only.
- **Frame:** 16,965 cycles NTSC (65 × 261). A software sprite costs ~2k cycles unoptimised.

## Decision guide

| Goal | Technique | Start from |
|---|---|---|
| Text + custom tiles, unexpanded | `$9005 = $FF`: 64 custom chars at `$1C00` + ROM font at codes 128–255 | `vic20-system/assets/template-ca65` |
| Animated water/lava/conveyors | Redefine shared characters (8 stores per char) | `characters-and-colour.md` |
| Smooth-moving objects | Local-framebuffer software sprites, double-buffered pool | `assets/softsprite.s` |
| Many bullets / simple objects | Pre-shifted tiles or cell-based objects | `software-sprites.md` |
| Line drawing, plotting, 3D | 160×192 bitmap (+8K) | `assets/bitmap160.s` |
| Flicker-free full redraw | `$9002` bit 7 screen + colour flip in vblank | `raster-and-buffering.md` |
| More colours on screen | Change `$900F`/`$900E` per band at a frame-locked or stable raster | `raster-and-buffering.md`, `assets/stable-raster-ntsc.s` |
| Status bar in another charset | Switch `$9005` at a raster line | same |
| Scrolling playfield | Page flip + coarse scroll + `$9000` half steps; tile-pair chars for 1–2 px | `display-modes-and-scrolling.md` |

## Rules that prevent the usual bugs

1. **Multicolour bit pairs:** `00` background, `01` border, `10` character colour, `11` aux (PRG + VICE).
   Mäkelä's VIC-I.txt has 01/10 swapped. Multicolour is enabled per cell by colour RAM **bit 3** (values 8–15),
   which leaves foreground colours 0–7.
2. **`$900F` bit 3 = 1 means normal** (0 = reverse). Write `(bg << 4) | 8 | border`.
3. **`$900E` high nibble is the aux colour; low nibble is the sound volume.** Keep one shadow variable for aux and
   OR the volume in. Never `STA $900E` a bare volume.
4. **Screen codes ≠ PETSCII.** Convert, or use ACME `!scr` / 64tass `.enc "screen"` / ca65 `.charmap`.
   With the `$1C00` wrap trick, text codes are screen code + 128.
5. **Colour RAM reads return garbage in the upper nibble**: `AND #$0F`.
6. **Screen/colour address depends on the RAM configuration** (`$1E00`/`$9600` vs `$1000`/`$9400`). Set the
   VIC registers yourself or read `$0288`.
7. **NTSC ≠ PAL timing.** 65 vs 71 cycles per line, 261 vs 312 lines, different origins (read `$EDE4/$EDE5` for
   portable centring). PAL raster code needs re-timing.
8. **Cycle-exact code**: keep each timed routine within one page (assert it), disable NMIs (`$911E = $7F`),
   and verify in VICE by comparing screenshots across frames.

## Workflow

1. Write down the VIC memory plan first: screen page(s), charset location and code allocation, colour scheme
   (background/border/aux are global).
2. Produce character data with `scripts/charconv.py` (keep the ASCII art in the repo as the source of truth).
3. Start from a tested asset or the system template; integrate one piece at a time.
4. Verify in VICE with `vic20-system/scripts/vice-test.sh --shot out.png` and **look at the screenshot**. For
   raster code, take screenshots at several different `--cycles` values: identical images mean a stable raster.
5. Profile with border colours, then optimise the hot drawing loops (`6502-assembly`, `vic20-optimization`).
