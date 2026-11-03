# Software Sprites on the VIC-20

There is no sprite hardware. "Sprites" are characters you redefine or swap every frame.

## Choosing an approach

| Approach | How | Pros | Cons | Use for |
|---|---|---|---|---|
| **Character-cell objects** | Poke an object's char code into the screen; move in 8-px steps | Trivial, ~10 cycles | Jerky movement | Gridrunner-style games, puzzle, maze |
| **Pre-shifted tiles** | For each sub-cell offset keep a pre-drawn tile set (8 phases hires, 4 in multicolour); pick codes | Fast, no runtime shifting | Character slots × phases; doesn't merge with background | Objects on plain backgrounds, bullets |
| **Local framebuffer (copy + OR)** | Copy the background chars under the object into pool chars, OR/mask the (shifted) sprite in, put pool codes on screen, restore later | Pixel positioning over any background | 4 chars per 8×8 (9 per 16×16), ~0.7–2.7k cycles each depending on optimisation | The standard engine (VIC-SSS, Pulse, Vixel, LBM8) |
| **XOR drawing** | XOR sprite bytes into character RAM; XOR again to erase | No background save, simple overlap | XOR artefacts where objects overlap | *Jetpac* (on a unique-char "framebuffer") |
| **Unique-char framebuffer** | Map every cell to its own char (e.g. 23×11 of 8×16 = 253 chars), then draw pixels into char RAM directly | True bitmap-style drawing | Uses ~4 KB of VIC RAM; screen size limited | Jetpac, bitmap-mode games |

## Tested module: `assets/softsprite.s`

8×8 sprite at any pixel position over RAM characters **and** ROM characters (via the `$1C00` wrap), using
4 pool chars and the copy + OR method. Tested in VICE with pixel-level checks. Written for clarity:
optimise it (below) before using many sprites.

```asm
.import spr_draw, spr_erase
.importzp spr_x, spr_y, spr_data
        lda #<ship
        sta spr_data
        lda #>ship
        sta spr_data+1
        lda px
        sta spr_x
        lda py
        sta spr_y
        jsr spr_draw            ; ... next frame: jsr spr_erase, move, jsr spr_draw
```

Extending it:
- **More sprites:** duplicate the save area and pool per sprite (parameterise by sprite index, or assemble
  the module several times with different `POOL` values). Draw sprites in order and **erase in reverse order**,
  so overlapping sprites restore the right background (a later sprite saves an earlier sprite's pool code as its
  background and copies its pixels).
- **Masking:** for sprites with "holes" over busy backgrounds, AND a mask before ORing the image
  (`pool = (pool AND mask) OR image`). It doubles the data.
- **Pre-shifting:** store 8 shifted copies (16 bits wide) to remove the shift loop. That trades 8× data for
  roughly half the cycles. With multicolour you need only 4 phases (2-px steps).
- **16×16 sprites:** 3×3 cells = 9 pool characters; same algorithm with 3 columns of 24 bytes.
- **Colour:** set colour RAM for the 4 cells if the sprite needs its own colour. Save and restore the old
  nibbles too.

## Cost model and limits

Budget in **bytes touched per frame**, not "number of sprites":

```
per 8x8 sprite = erase (4 stores) + 32-byte copy + 8 rows × shift + 16 ORs + 4 code stores
measured (assets/softsprite.s, VICE NTSC): ~1,850 cycles byte-aligned, ~2,750 at a 7-px shift
                                            = 11–16% of a 16,965-cycle frame
optimised (pre-shifted data, unrolled copies, self-modified addresses): est. 700–1,000 (not measured)
```

- About **8–16 small sprites** is the practical ceiling on a VIC-20. "Having 16 8x8px sprites around is
  already kind of over the edge."
- *Pulse* (unexpanded): 16 sprites with 48 characters for the pool, double-buffered. It doesn't wait for
  retrace, and turns dead sprites into background stars instead of removing them, to keep frame time
  constant.
- The character pool limits the sprite count as much as CPU time does.

## Flicker and tearing

The pool characters are modified while they are displayed. Fixes, cheapest first:

1. Draw while the beam is elsewhere: do sprite updates right after the frame IRQ (bottom border /
   vertical blank), top-of-screen sprites first.
2. **Double-buffer the pool:** alternate between two pool sets each frame (the hidden set is drawn, then
   screen codes switch over). This costs twice the characters.
3. **Double-buffer the screen** with the `$9002` bit 7 flip (see `raster-and-buffering.md`): draw into the
   hidden screen + colour page, flip in vblank. Needs two screen matrices plus pools for both.

## XOR sprites (Jetpac method)

```text
erase_old:  char_byte ^= old_sprite_byte   ; same data again restores the original
draw_new:   char_byte ^= new_sprite_byte
```

*Jetpac* (Ultimate, 1983, 8K) maps a 23×11 screen of 8×16 RAM characters as a pseudo-framebuffer at `$1000`,
compares old and new positions, erases only what will no longer be covered, and XORs objects in. It updates
colour separately per tile. Its documented disassembly is the best commercial reference for a VIC-20 engine.

## Libraries to reuse or study

| Library | Notes |
|---|---|
| **VIC-SSS** (Robert Hurst) — https://github.com/theflyingape/vic-sss | ca65 software sprite stack for 8K+: dual video buffers, raster-timed flips, XOR "ghost" sprites, collision detection; cc65 wrapper exists. Used by *Berzerk MMX*, *Omega Fury*, *Quikman+* |
| **Pulse** (Sven Michael Klose) — https://github.com/SvenMichaelKlose/pulse | Unexpanded smooth-scrolling shooter, 16 double-buffered sprites in 48 chars, Exomizer |
| **Vixel**, **LBM8** | Modern local-bitmap sprite engines with lookup-table pixel positioning and dirty-object updates |
| **Baguel** (Oscar64 C) | Software sprites from C on an unexpanded VIC: shows how tight it gets |

## Collision detection

- **Cell-based:** check the screen code under the sprite's cells against "solid" code ranges (cheap; organise
  the charset so solids are a contiguous range).
- **Bounding boxes** between objects in pixel coordinates (cheap, usually enough).
- **Pixel-exact:** AND the sprite's shifted bytes with the background bytes while composing (free while you're
  already in the OR loop: accumulate `ORA` of `(bg AND sprite)` into a flag).
