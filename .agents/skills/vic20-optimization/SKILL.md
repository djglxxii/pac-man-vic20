---
name: vic20-optimization
description: Performance and memory optimization for Commodore VIC-20 programs (NTSC focus). Use when a VIC-20 game or demo is too slow, flickers, misses frames, runs out of RAM, or when asked to review, profile, speed up or shrink VIC-20 code (assembly or cc65 C). Provides the frame budget, border-colour profiling, exact cycle measurement with a VIA timer and VICE regression tests, a prioritized optimization playbook (KERNAL IRQ removal, frame-locked timer, dirty-cell rendering, table-driven drawing, double buffering, scheduling across frames), memory-conservation tactics, and lessons from Jetpac, Gridrunner, Pulse and VIC-SSS.
---

# VIC-20 Optimization

The VIC-20 gives you **16,965 CPU cycles per NTSC frame** (65 cycles × 261 lines, 60 Hz), never stolen by
video. RAM the VIC can display is ~4 KB. Optimizing means spending those two budgets deliberately.

Related skills: `6502-assembly` (instruction-level speedups, cycle counter script), `vic20-graphics` (drawing
techniques), `vic20-audio`, `vic20-system` (IRQ/memory details), `vic20-cc65` (C-specific rules).

## Bundled resources

| File | Use it for |
|---|---|
| `references/playbook.md` | The ordered checklist for optimizing an existing project, with expected gains and "don'ts" |
| `references/case-studies.md` | What Jetpac, Gridrunner/Matrix, Pulse, VIC-SSS, Robotic Liberation and others did, and which lessons transfer |
| `assets/cycle-budget.s` | **Tested** exact cycle measurement of one routine (VIA1 T2) that passes/fails a `BUDGET` in VICE headless: a performance regression test |

## Step 0: establish ground truth (always)

1. **Memory target and layout**: which RAM config, where code / screen / colour / charset / tables / stack /
   zero page live. Get it from the linker map (`-m file.map`) or the source.
2. **Measure before changing anything.**
   - *Border profiling* (whole frame, visual): write a distinct colour to `$900F` at the start of each phase
     and restore at the end. Band height = cost in raster lines (× 65 cycles). Bands wrapping past the bottom
     = over budget.
   - *Exact cycles* (one routine): `assets/cycle-budget.s` + `vic20-system/scripts/vice-test.sh`.
   - *Static count*: `6502-assembly/scripts/cycles.py file.s --from label --to label`.
3. **Check NTSC assumptions**: constants built from 65/261 (not PAL 71/312), `$4243` frame latch, raster
   polling that assumes the counter flips at line start.

```asm
.macro PROFILE colour           ; border-colour profiling; remove for release
.ifdef PROFILING
        lda #(C_BLACK << 4) | 8 | colour
        sta $900f
.endif
.endmacro

main_loop:
        jsr wait_frame
        PROFILE C_RED
        jsr update_logic
        PROFILE C_GREEN
        jsr erase_sprites
        PROFILE C_BLUE
        jsr draw_sprites
        PROFILE C_BLACK         ; idle time shows as the normal border
        jmp main_loop
```

## Frame budget (NTSC, typical action game)

| Item | Typical cost | Note |
|---|---|---|
| Whole frame | 16,965 cycles | 261 lines |
| Bottom border + vertical blank | ~3,000 cycles | safe window for flips/charset changes (IRQ just below the text area) |
| KERNAL IRQ incl. keyboard scan | ≈650+ cycles | **remove it** (own IRQ, exit `$EB15`) |
| Music driver tick | 100–400 cycles | assembly, once per frame |
| Joystick read (direct VIA) | < 50 cycles | |
| One 8×8 software sprite (unoptimised copy+OR) | ~1,850–2,750 cycles | measured; optimised ~700–1,000 (est.) |
| Coarse scroll (506-byte screen copy) | ~4,500 (unrolled) – 7,500 (`LDA/STA abs,X` loop) cycles, double with colour RAM | split across frames or draw into the hidden page |
| Game logic | whatever is left | |

## The playbook (summary; details in `references/playbook.md`)

**Cheap, safe, high yield first:**
1. Replace the KERNAL IRQ with your own (`$0314`), exit via `JMP $EB15`, read the joystick directly: ~4% of the frame
   back, less jitter.
2. Frame-lock VIA2 T1 (`$4243`) from a known raster line: stable tick, predictable flip point.
3. cc65 hygiene: `-Osir -Cl`, `unsigned char`, globals instead of parameters, no printf/conio in the loop
   (`vic20-cc65` skill).
4. **Dirty-cell rendering**: redraw only what changed; animate shared tiles by redefining characters.
5. Fix `$900E` writes to preserve aux colour (correctness, not speed, but found in the same pass).

**Structural:**
6. Move inner loops to assembly with zero-page pointers, lookup tables (row addresses, multiplies, shifts),
   unrolled 8-byte copies, downward loops, page-aligned tables, self-modified absolute addresses.
7. Pre-shifted sprite data; XOR sprites where overlap artefacts are acceptable.
8. Flicker-free output with the `$9002` bit 7 screen+colour page flip in vertical blank.
9. Memory re-layout: code out of `$1000–$1FFF` on expanded machines (custom linker cfg), compressed assets
   (Exomizer), init code overlaid by runtime buffers.

**Scheduling:**
10. Round-robin enemy updates, player first every frame, distant/minor objects at lower rates.
11. Constant per-frame workload (avoid frames that suddenly double in cost).

**Advanced (only when the design needs it):** stable rasters, bitmap mode, waveform tricks, digis.

## Memory conservation (unexpanded: ~3.5 KB for everything)

- Assembly over C on unexpanded machines (cc65 runtime + stack cost hundreds of bytes to KB).
- `$1C00` charset wrap: 64 custom chars + full ROM font for 512 bytes.
- Overlays: init code and title graphics live where runtime buffers go later; cassette buffer `$033C–$03FB`
  and `$02A1–$02FF` for small resident routines.
- Table generation at init time instead of storing tables (when the table is bigger than its generator).
- Exomizer `sfx` for the whole program; `exomizer mem` streams for levels and graphics.
- Data packing: nibbles, run lengths, shared animation frames (redefine characters instead of storing frames).
- Expanded: keep `$1000–$1FFF` for display only; code in BLK1–3; big tables/music/levels in BLK5.

## Things not to do

- Optimize without measuring, or measure under the wrong RAM config / video standard.
- Keep the KERNAL keyboard scan running during gameplay "just in case".
- Put graphics in expansion RAM (invisible to the VIC).
- Use the stock 60 Hz timer for raster timing (it drifts).
- Write cycle-exact code in C.
- Clobber the aux colour when setting volume.
- Use `register` on everything in cc65 (save/restore costs ~70 cycles each).
- Trust old VICE builds for waveform tricks, noise behaviour or digi levels.
- Port PAL timing constants unchanged to NTSC.

## Reporting results

When you optimize, report **before/after numbers** (cycles per routine or raster lines per phase), the RAM
config and video standard measured, and anything you couldn't verify (e.g. "tested in VICE NTSC only").
