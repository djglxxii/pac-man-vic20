# VIC-20 Optimization Playbook (prioritized)

Work through the phases in order. Each step: what to check → what to change → expected gain.

## Phase 1: Ground truth

1. **Memory target and actual layout.**
   - Check: load address, linker cfg/map, `$9005`/`$9002` writes, where charset/screens/tables/stack/zp live.
   - Flag: displayable data outside `$0000–$03FF` / `$1000–$1FFF` (can never show); hard-coded screen
     addresses that break on other RAM configs; code that can grow into charset/screen.
2. **Profile** each main-loop phase (input, logic, erase, draw, music, flip) with border colours; record lines
   per phase. For hot routines, record exact cycles with `assets/cycle-budget.s`.
3. **NTSC correctness.** Look for PAL constants (71, 312, `$5686`, 22150), copied PAL demo routines, and raster
   polling that ignores the 6560's mid-line counter change.

## Phase 2: Cheap, safe, high yield

4. **Replace the KERNAL IRQ** (if gameplay doesn't need KERNAL keyboard input):
   ```asm
           sei
           lda #<game_irq
           sta $0314
           lda #>game_irq
           sta $0315
           cli
           ...
   game_irq:                   ; A/X/Y already saved by the ROM
           ...                 ; frame work
           jmp $eb15           ; acks VIA2 T1, restores A/X/Y, RTI
   ```
   Gain ≈ 650+ cycles/frame (~4%) and less jitter. Replace with direct joystick reads and targeted key checks.
   Keep or restore the KERNAL IRQ around disk loads and text-entry screens.
5. **Frame-lock the IRQ**: VIA2 T1 latch `$4243` (NTSC), started on a known raster line; IER `$C0`. Stable music
   tick, reliable flip point, raster-locked HUD splits.
6. **C hygiene (cc65)**: `-Osir -Cl`; `unsigned char` everywhere it fits; globals instead of parameters;
   `register` only for hot pointers in substantial loops; fixed-address pokes as single `STA abs`; no
   printf/conio/TGI in the frame loop; `__fastcall__` assembly kernels; shrink `__STACKSIZE__`.
7. **Dirty-cell rendering**: track changed cells/objects and redraw only those. Convert repeated animated tiles
   into character-definition animation (8 stores animate every copy).
8. **Aux-safe `$900E` writes** via a shared shadow variable (fixes flickering/black multicolour as a side effect).

## Phase 3: Structural rendering improvements

9. **Inner loops in assembly** (blit, erase, char copy, colour updates, plot):
   - zero-page pointers and `(zp),Y`, or better, self-modified `abs,Y` operands;
   - row/column address lo/hi tables (no multiply by 22 or 192);
   - unrolled 8/16-row character copies;
   - loops counting down, data laid out to match;
   - page-aligned tables (no +1 page-cross cycles, deterministic timing);
   - specialized routines per sprite width instead of one general blitter.
10. **Pre-shifted sprites** (8 phases hires, 4 multicolour) if shifting at runtime and RAM allows. XOR sprites
    to drop background-save buffers where artefacts are acceptable.
11. **Flicker-free flips**: draw into the hidden screen+colour page, flip `$9002` bit 7 in vblank. If RAM is too
    tight for two screens, double-buffer only the sprite pool characters.
12. **Memory re-layout (expanded)**: custom linker config (code BLK1–3, data BLK5, `$1000–$1FFF` display only),
    `ONCE`/init segments overlaid by buffers, Exomizer-compressed assets.
13. **Unexpanded**: `$1C00` wrap for the ROM font, screen in the `$0200` area to free `$1000–$1FFF` (advanced),
    cassette-buffer overlays, Exomizer sfx.

## Phase 4: Scheduling

14. **Spread work across frames**: round-robin enemy AI (e.g. 1/4 of enemies per frame), player updated every
    frame first (Jetpac prioritises Jetman), slower update rates for distant/minor objects, collision checks
    every other frame for slow objects.
15. **Constant per-frame workload**: precompute, cap the object count, recycle objects instead of
    creating/destroying (Pulse turns dead sprites into background stars).
16. **Fixed-tick assembly music driver** (`.interruptor` in cc65) with explicit voice priority: effects borrow
    soprano/noise and return it.

## Phase 5: Advanced (only if the design calls for it)

17. Stable raster splits (start from `vic20-graphics/assets/stable-raster-ntsc.s`; never write one from scratch).
18. 160×192 bitmap (`vic20-graphics/assets/bitmap160.s`).
19. viznut waveforms (reload in vblank, interrupts off).
20. Digis: timer-driven 4-bit player (≤ ~4 kHz, ~256 cycles/sample NTSC), sharing timing with any raster code.

## Micro-optimization quick reference (6502)

| Instead of | Use | Saves |
|---|---|---|
| `JSR x / RTS` | `JMP x` | 6 cycles, 1 byte |
| `LDA (zp),Y` in a fixed-target loop | self-modified `LDA abs,Y` | 1 cycle/iter (+ no zp pointer) |
| `CPX #0 / BNE` after `DEX` | `DEX / BNE` | 2 cycles |
| multiply by 22/192 | lo/hi row tables | 50–150 cycles |
| 8-iteration copy loop | unrolled 8× LDA/STA | ~40 cycles |
| 16-bit counters in hot loops | 8-bit counters, split loops | several cycles/iter |
| table straddling a page | page-aligned table | 1 cycle per access + determinism |
| `LDA #0 / STA x` repeated | keep 0 in X or Y, `STX`/`STY` | 2 cycles each |
| runtime shifts of sprite data | pre-shifted copies | ~10–15 cycles per shifted byte |

## Verification after each change

- Re-run the profile and the cycle-budget tests. Report before/after.
- Re-test on the exact RAM config and video standard (`vice-test.sh --mem … [--pal]`).
- Look at screenshots for tearing and colour regressions; listen to the music for tempo changes (IRQ changes alter
  the tick).
