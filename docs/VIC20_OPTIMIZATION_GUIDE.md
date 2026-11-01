# VIC-20 Frame-Rate Optimization Guide

A general reference for making 6502 games run faster on an NTSC VIC-20. It is
not an audit of any particular codebase. Each section describes a technique,
what it costs and when it pays off. Use it as a checklist against your own
profiles.

---

## 1. Know the budget

| Quantity (NTSC 6560 VIC) | Value |
| --- | --- |
| CPU clock | 1,022,727 Hz |
| Cycles per raster line | 65 |
| Raster lines per frame | 261 |
| Cycles per frame | 16,965 (~60 Hz) |
| Cycles for a 30 Hz frame | ~33,930 |

The VIC-I and the 6502 share the bus on opposite clock phases. Unlike the
C64, the VIC-20 has **no cycle stealing**, so every cycle in the table is
available to the CPU. Your real budget is 16,965 minus the IRQ handler's
cost (music, timers and input) minus game logic. Write down that number and
budget rendering against it.

**Use the worst frame, not the average.** A game that averages 45 FPS but
stalls on a few heavy frames feels worse than one locked at 30. Measure:

- the longest single frame in a sample, not just the mean
- frames where the most actors are on screen at once
- level transitions, screen rebuilds and score/text updates

---

## 2. Measure before changing anything

1. **Emulated cycle counts.** Profile in a cycle-exact emulator and measure
   emulated cycles, not wall-clock time. Group counts by routine using the
   linker map or symbol table so you can rank hot spots. (`make performance`
   in this repo saves instruction profiles.)
2. **Border-color timing.** This classic trick works on real hardware and in
   VICE. Write a color to `$900F` (border color in bits 0–2) on entry to a
   routine and restore it on exit. The colored band's height shows how many
   raster lines the routine took.
   ```asm
   lda #$1A        ; white screen, normal mode, red border
   sta $900F
   jsr render
   lda #$1B        ; restore default white screen, cyan border
   sta $900F
   ```
3. **VICE monitor stopwatch.** `sw reset`, run to a breakpoint, then `sw`
   prints the elapsed cycles.
4. **Change one thing at a time** and record the before and after cycle
   counts. Many “obvious” wins turn out to be noise, while hidden costs
   (helper calls, page crossings, soft-stack frames) often dominate.

---

## 3. The biggest wins are usually architectural

Instruction tweaks typically gain 10–30%. Doing less work often gains 2–5×.
Check these first.

### 3.1 Dirty-cell rendering
Redraw only the character cells whose contents changed. For each moving
object, mark the cells it covered last frame and the cells it covers now.
Rebuild only that union. A static maze costs nothing per frame.

- Keep a **source-of-truth tile map** and rebuild erased cells from it.
  That avoids saving and restoring background bytes under each sprite.
- If an object didn't move and its animation frame didn't change, skip it
  entirely.
- Merge overlapping dirty cells so a cell under two sprites is composed once.

### 3.2 Combine erase and draw
Erasing everything and then drawing everything touches each pixel twice and
flickers. Instead, compose each dirty cell once:

```
dest = (background AND sprite_mask) OR sprite_data
```

When two sprites overlap a cell, apply both masks and data before storing.

### 3.3 Separate logic rate and render rate
Run game logic on a fixed tick from a timer IRQ or tick counter. Render as
often as the remaining budget allows. When rendering falls behind, skip
frames: draw only the latest state and never queue renders. Keep the logic
tick cheap, because it runs whether or not you draw.

### 3.4 Spread work across frames
Work that needn't happen every frame should be spread out:

- AI and path decisions: update one or two actors per frame in rotation,
  or only at tile boundaries.
- Score and status text: redraw only when the value changes, and draw one
  digit per frame if needed.
- Palette or color flashing: change color RAM on a schedule, not every frame.
- Rebuilding big screen regions (level start, maze reset): spread the work
  over several frames with the display blanked or hidden, so no single frame
  carries all of it.

### 3.5 Race the beam
Read the raster line from `$9004` (bits 8–1) and `$9003` bit 7 (bit 0).
Update a region right after the beam has passed it. For example, draw
objects in the top half while the beam is in the bottom half. This removes
tearing without double-buffering. That matters because VIC-visible RAM is
too scarce for two full bitmaps.

### 3.6 Keep the IRQ handler lean
The IRQ handler's cycles are paid every frame whether or not you draw.

- Write sound registers only when values change.
- Avoid calling C from the IRQ if the compiler must save its imaginary
  registers or soft stack. Write the handler in assembly.
- **NMOS 6502 does not clear the decimal flag on interrupt.** If the main
  program ever runs with `SED` (BCD scores), the IRQ handler must `CLD`
  before any arithmetic.

---

## 4. Memory layout for speed

### 4.1 What the VIC can see
The VIC chip can only fetch from internal RAM (`$0000–$03FF`, `$1000–$1FFF`),
the character ROM and color RAM (`$9400`). Expansion RAM (the 3K block and
BLK1–3/5) is **CPU-only**. Character sets, screen memory and pseudo-bitmap
data must live in the 4K at `$1000–$1FFF`. Put code, lookup tables and
pre-shifted graphics in expansion RAM, which you have plenty of.

### 4.2 Lay out the pseudo-bitmap column-major
The VIC-20 has no bitmap mode. A full-screen bitmap is emulated by filling
the screen with unique character codes. Number the characters **down each
column** (code 0 at top-left, code 1 below it, and so on), not across rows.
Then each pixel column is one contiguous run of bytes:

```
addr(x_byte, y) = column_base[x_byte] + y
```

A sprite's vertical strip becomes a single loop indexed by Y, with no
character-boundary arithmetic. In row-major layout, every 8 or 16 lines of a
sprite cross into a different character, which costs extra address work.

### 4.3 Page alignment
- `abs,X`, `abs,Y` and `(zp),Y` loads cost **+1 cycle** when the effective
  address crosses a page boundary. Align hot tables to `$xx00` so the index
  never crosses one.
- A taken branch to another page costs **+1 cycle**. Keep tight loops within
  a single page.
- Stores (`STA abs,X` = 5, `STA (zp),Y` = 6) always take the slow path, so
  alignment doesn't help them.

### 4.4 Zero page is a register file
Zero-page operands are one cycle faster and one byte shorter than absolute
ones, and `(zp),Y` indirection requires zero page. Give zero page to:
- sprite source and destination pointers
- loop counters and temporaries used inside inner loops
- the hottest game-state bytes read every frame

---

## 5. Lookup tables over arithmetic

The 6502 has no multiply, no barrel shifter and only 1-bit shifts, so trade
memory for cycles:

| Instead of | Use |
| --- | --- |
| `y * 40`, `col * 16` | separate lo-byte and hi-byte address tables indexed by row or column |
| shifting sprite data `n` times | **pre-shifted** graphics, one copy per sub-byte offset |
| `x / 8`, `x & 7` | tables, or keep coordinates pre-split into cell and offset |
| bit masks `1 << n` | an 8-byte table |
| direction → dx/dy | small tables indexed by direction |
| `abs(a-b)`, distance squared | square table for 8-bit values, sum the parts |

Row-address lookup:

```asm
ldx row
lda row_lo,x    ; 4
sta ptr         ; 3
lda row_hi,x    ; 4
sta ptr+1       ; 3     -> 14 cycles, no multiply
```

### Pre-shifted sprites
For a sprite 1 byte wide that can sit at any pixel offset, store 8 versions
(or 4 in multicolor mode, where pixels are 2 bits wide). Each version is 2
bytes wide, with a matching mask. Drawing becomes a straight masked copy with
no `LSR`/`ROR` per byte. In multicolor mode, if an object only ever moves in
2-pixel steps, you need half as many shifts.

---

## 6. Inner-loop techniques

Cycle costs below are for the NMOS 6502.

### 6.1 Unroll
Loop overhead (`DEY` 2 + `BPL` 3) often costs as much as the body.

```asm
; 16-byte glyph copy, looped: ~16 cycles/byte -> ~256 cycles
        ldy #15
loop:   lda (src),y     ; 5
        sta (dst),y     ; 6
        dey             ; 2
        bpl loop        ; 3
```

### 6.2 Self-modifying absolute addresses
Code in RAM can patch its own operands. Absolute,X loads (4) and stores (5)
are cheaper than `(zp),Y` (5 and 6). Write the source and destination
addresses into the instructions once, then run an unrolled body:

```asm
; ~8-9 cycles/byte -> ~135 cycles for 16 bytes
        lda src_lo : sta s0+1 : sta s1+1 ...   ; patch once
s0:     lda $FFFF       ; 4
d0:     sta $FFFF       ; 4
s1:     lda $FFFF+1
d1:     sta $FFFF+1
        ...
```

For many uses of the same shape, consider **speed code**: generate the
unrolled routine once (at startup or build time) and call it with patched
bases.

### 6.3 Masked compose in one pass

```asm
        ldy #height-1
loop:   lda (bg),y      ; 5   background
        and (mask),y    ; 5
        ora (spr),y     ; 5
        sta (dst),y     ; 6
        dey             ; 2
        bpl loop        ; 3   -> 26 cycles/row
```
Variants:
- Store mask and data **interleaved**, or index both from one pointer with
  a fixed offset, to save pointer setup.
- Where the mask is all ones (fully transparent), skip the store.
- Where it is all zeros (fully opaque), skip the background read.
- Pre-classify each sprite row at build time and branch once per row, not
  per byte.

### 6.4 Smaller wins
- Count loops **down** so `DEX`/`DEY` sets the flags; you don't need `CPX`.
- Avoid `JSR`/`RTS` (12 cycles) inside inner loops. Inline with macros.
- Prefer register transfers (`TAX`, 2) to stack pushes (`PHA` 3 + `PLA` 4).
- Use `BIT` to test bit 7 or bit 6 without loading.
- Use `INC zp` (5) rather than `LDA/CLC/ADC/STA` (10) for counters.
- Leave the carry flag in a known state at a loop's end to drop
  `CLC`/`SEC` from the next iteration.
- Jump tables: push the address and `RTS`, or use `JMP (vector)` patched
  per state. That's cheaper than a long compare chain.

---

## 7. Writing fast C for llvm-mos (or any 6502 compiler)

These are general patterns. Confirm every change in the generated assembly
(`llvm-objdump -d`) and in a profile.

### 7.1 Types
- Use `uint8_t` wherever the range allows. Every `int` is two bytes of work.
- Avoid signed types unless you need them; signed compares and shifts cost
  more on the 6502.
- Watch for integer promotion: `(uint8_t)(a + b)` may still compute in
  16 bits until the optimizer proves otherwise.

### 7.2 Data layout: struct of arrays
```c
/* Array of structs: index * sizeof(struct) needs multiply or shift */
struct actor { uint8_t x, y, dir, frame; } actors[4];
actors[i].x;

/* Struct of arrays: compiles to LDA actor_x,X */
uint8_t actor_x[4], actor_y[4], actor_dir[4], actor_frame[4];
actor_x[i];
```
Prefer global arrays indexed by a `uint8_t` over pointer arithmetic.
`base[i]` maps to `abs,X`, while `*p++` needs zero-page pointer updates.

### 7.3 Avoid hidden helper calls
Multiply, divide and modulo by non-powers of two, 16/32-bit shifts by
variable counts, and `memcpy`/`memset` with variable sizes may all become
library calls. Find them in the profile or disassembly and replace them with
tables, constants or fixed-size loops.

### 7.4 Call-graph friendliness
- llvm-mos gives non-recursive functions **static stack frames**, which are
  much cheaper than its soft stack. Recursion forces the soft stack, and
  function pointers can make call-graph analysis conservative. Prefer
  `switch` dispatch over function pointers in hot paths when you can.
- Mark helpers `static` so LTO can inline them. Use
  `__attribute__((noinline))` on cold paths so they don't bloat hot ones.
- More zero page for the compiler (`-mlto-zp=N`) generally helps. Free zero
  page from rarely used data first.

### 7.5 Optimization level
`-Oz` minimizes size, often at the cost of inlining and unrolling. If memory
allows, try `-Os` or `-O2` and measure. A common split is to keep the C code
at `-Oz` and hand-write the 2–3 hottest routines in assembly.

### 7.6 `volatile` and aliasing
Use `volatile` only for hardware registers and data shared with the IRQ
handler. Using it on ordinary state stops the compiler from keeping values
in registers. Writes through `uint8_t *` can alias anything, so copy hot
values into locals before loops.

---

## 8. VIC-20 display specifics

- **Character-based sprites as an alternative to a full bitmap.** Keep the
  maze in a normal character set. For each moving object, allocate a few
  spare character codes and compose background, mask and sprite into them.
  Point the screen cells at those codes. Only about 4–9 characters per
  object are touched per frame.
- **Color RAM** (`$9400`, one nybble per cell): write only when a cell's
  color actually changes. Multicolor is chosen per cell by bit 3.
- **Double-buffering by register flip.** `$9005` selects the screen and
  character base, so swapping it during vertical blank flips buffers in one
  write. It needs two copies of VIC-visible data, which rarely fits. Racing
  the beam (§3.5) is usually the better trade.
- **Double-height characters** (8×16, bit 0 of `$9003`) halve the number of
  screen cells. This lets a 160×192 pseudo-bitmap fit in 240 characters.

---

## 9. Classic VIC-20 tricks

Techniques the VIC-20 scene has relied on for decades. Register addresses
are for the NTSC machine. Check each one against a memory map before
relying on it.

### 9.1 Take the interrupts over from the KERNAL
- The default IRQ handler (`$EABF`) scans the keyboard, blinks the cursor
  and updates the jiffy clock. That costs hundreds of cycles per interrupt,
  which a game rarely needs. Point the vector at `$0314/$0315` to your own
  handler.
- End your handler with `PLA / TAY / PLA / TAX / PLA / RTI` instead of
  jumping on to `$EABF`.
- Your handler must acknowledge the interrupt itself, for example by
  reading `$9124` to clear VIA2 timer 1's flag. Otherwise the IRQ fires
  again immediately.
- The KERNAL's own entry code still runs before your vector is reached
  (about 30 cycles). Budget for it.
- The RESTORE key raises an NMI through VIA1. Point `$0318/$0319` at an
  `RTI` so a stray keypress can't wreck a frame.

### 9.2 Make a raster interrupt from a VIA timer
The VIC-I has no raster interrupt, so build one:

1. Wait for a chosen raster line by polling `$9004`.
2. Start VIA2 timer 1 (`$9124/$9125`) in free-running mode (`ACR` at
   `$912B`).
3. Set the latch to **cycles per frame − 2**. On NTSC that is
   16,965 − 2 = 16,963 = `$4243`.

The timer then fires at the same raster position every frame. This gives
you a fixed vertical-blank slot for music and input, and an anchor for
racing the beam.

For cycle-exact effects, read the timer's low byte on entry. Use it to jump
into a chain of `NOP`s that absorbs the 0–7 cycles of interrupt jitter. VIA1
timers raise **NMIs**, which can't be masked. Some programs use a VIA1 timer
for precise raster work and keep VIA2's IRQ for music.

### 9.3 Mid-screen register changes (raster splits)
Rewrite VIC registers while the screen is being drawn:

- **`$9005` mid-screen:** switch character sets between screen regions.
  This lets you show more than 256 unique characters, for example a
  separate character set for the status bar.
- **`$900F` and `$900E`:** change background, border and auxiliary colors
  per band. This gives more colors than the global registers allow, at a
  cost of a few cycles per split.

### 9.4 Flip screens and color RAM with one bit
Bit 7 of `$9002` supplies bit 9 of the screen-matrix address. It also
selects which half of color RAM is used (`$9400` or `$9600`). Keep two
screen matrices 512 bytes apart and two color maps. Build the next frame's
character codes and colors in the hidden pair, then toggle the bit during
vertical blank.

This double-buffers the **screen matrix** cheaply. It suits
character-based sprites, where only the code layout changes. It does not
buffer character definitions.

### 9.5 Animate characters, not cells
Every cell that shows a given character code changes as soon as you
redefine that character. Flashing items, water or conveyor tiles, and
blinking power-ups need only a few bytes written to one glyph per frame,
however many cells use it. The same idea applies to colors: one write to
`$900F` or `$900E` recolors the whole screen. Toggling bit 3 of `$900F`
inverts the whole display for a flash effect with a single store.

### 9.6 Borrow the ROM font for text
In 8×8 mode, put the character set at `$1C00` (`$9005` low nibble `$F`).
Codes 0–127 come from RAM. Character addresses wrap around the VIC's 16K
address space, so codes 128–255 come from the uppercase character ROM.
You get custom graphics plus a full ROM font for scores and messages
without copying or storing the font. You can also read digit glyphs
straight from the character ROM at `$8000` when composing text into a
bitmap.

### 9.7 Hardware screen position for shakes and centering
`$9000` bits 0–6 set the horizontal origin in 4-pixel steps. `$9001` sets
the vertical origin in 2-line steps. Changing them moves the whole screen at
no cost. Use them for screen shake and for centering an enlarged screen.
`$9002` and `$9003` set the column and row counts. A smaller visible area
means fewer cells to manage and less VIC-visible RAM used.

### 9.8 Free RAM once you own the machine
With BASIC and the KERNAL services no longer in use, much of low RAM is
free:

- most of zero page, for the compiler and your hot pointers
- the cassette buffer at `$033C–$03FB`
- the bottom of the stack page, since the stack rarely gets deep

Low RAM is also **VIC-visible**, which matters when `$1000–$1FFF` is full.

### 9.9 BCD scores
Keep scores in packed BCD and add with `SED`/`ADC`/`CLD`. Each digit is
then one nibble, displayed with a shift or mask and no binary-to-decimal
division. Remember `CLD` in the IRQ handler (§3.6).

### 9.10 Quarter-square multiply
When you really need a multiply, use this identity:

```
a*b = f(a+b) − f(a−b),   where f(x) = ⌊x²/4⌋
```

With page-aligned tables of `f` for 0–510 (low and high bytes), an 8×8→16
multiply costs a few dozen cycles instead of a shift-and-add loop of
roughly 150–250 cycles.

### 9.11 Stable undocumented opcodes
The VIC-20's NMOS 6502 runs the stable undocumented opcodes reliably. Many
demos and games use them:

| Opcode | Effect | Typical use |
| --- | --- | --- |
| `LAX` | load A and X together | index and value in one fetch |
| `SAX` | store A AND X, flags unchanged | masked store without disturbing A |
| `DCP` | DEC memory, then CMP | decrement a counter and test it in one instruction |
| `ISC` | INC memory, then SBC | combined counter arithmetic |
| `SBX` (`AXS`) | X = (A AND X) − immediate | fast stepping of an index |
| `SLO`/`RLA`/`SRE`/`RRA` | shift memory, then OR/AND/EOR/ADC | combined shift-and-merge in blitters |

They won't run on 65C02 or 65816 accelerator boards, and some assemblers
need a flag to accept them. Keep a plain fallback if that matters.

### 9.12 Stack blasting
`PLA` (4 cycles) reads the next byte with an automatic increment and no
index register. `PHA` (3 cycles) writes and decrements. For bulk copies or
clears of data staged in page `$01`:

1. Disable interrupts.
2. Save S.
3. Point S into the data with `TXS`.
4. Run an unrolled run of `PLA`/`STA abs` or `PHA`.
5. Restore S.

It only works within page `$01`, so it's a niche tool. When it fits, it is
one of the fastest ways to move bytes on a 6502.

### 9.13 Joystick and timing gotchas
- **Joystick:** up, down, left and fire are on VIA1 `$9111` (bits 2–5).
  Right is on VIA2 `$9120` bit 7, which the keyboard also uses. Clear bit 7
  of `$9122` (DDR) before reading and restore it afterwards. Read once per
  frame and cache the result.
- **Cheap randomness:** the VIA timer low bytes and `$9004` change
  constantly. Mixing one into an LFSR costs a couple of cycles and avoids a
  heavier generator.
- **`JMP ($xxFF)` bug:** on NMOS parts it fetches the high byte from
  `$xx00`, not the next page. Keep jump vectors off page-end addresses.

---

## 10. Checklist

1. [ ] Measured worst-frame cycles and know the per-frame budget left after
       IRQ and logic.
2. [ ] Ranked routines by emulated cycles; working on the top one only.
3. [ ] Rendering only dirty cells; unchanged objects skipped.
4. [ ] Erase and draw combined into one compose pass per cell.
5. [ ] Non-urgent work (AI, text, colors, rebuilds) spread across frames.
6. [ ] IRQ handler lean, writes only changes, `CLD` if BCD is used.
7. [ ] Hot tables page-aligned in expansion RAM; hot pointers in zero page.
8. [ ] No multiply, divide or variable shift in per-frame paths; tables
       instead.
9. [ ] Sprites pre-shifted; masks precomputed and classified.
10. [ ] Inner loops unrolled; self-modifying absolute addressing where
        `(zp),Y` dominates.
11. [ ] C hot paths use `uint8_t`, struct-of-arrays, no hidden helper calls
        and no recursion.
12. [ ] KERNAL IRQ bypassed; handler acknowledges VIA itself; RESTORE NMI
        neutralized.
13. [ ] Frame timing anchored by a VIA timer set to cycles-per-frame − 2.
14. [ ] Animated tiles done by redefining glyphs or color registers, not
        rewriting screen cells.
15. [ ] Undocumented opcodes / stack blasting considered for the hottest
        blitter (if no 65C02 compatibility is required).
16. [ ] Every change verified with before/after numbers and a correctness
        check (screenshot or state comparison).
