---
name: vic20-cc65
description: Writing, building and speeding up C programs for the Commodore VIC-20 with cc65 (cl65/ca65/ld65), plus notes on llvm-mos and Oscar64. Covers target linker configs and memory layouts per RAM expansion, keeping $1000-$1FFF free for graphics (vic20-tgi.cfg relocation), the vic20.h/cbm.h hardware structs and their pitfalls (COLOR_RAM fixed at $9600, waitvsync double-return), cc65 performance rules (-Osir -Cl, unsigned char, globals, register cost), __fastcall__ assembly kernels, .interruptor IRQ hooks, stack/heap sizing, BLK5 heap, TGI 160x192 graphics and joystick drivers. Use for any VIC-20 project written in C or mixing C with assembly.
---

# cc65 C on the VIC-20

C works well on the VIC-20 for game logic, menus, state machines, loaders and turn-based games. Inner
loops, raster code, sound drivers and anything cycle-exact belong in assembly (`.s` files, ca65) called from
C. Load `vic20-system` (memory/IRQ), `vic20-graphics`, `vic20-audio`, `vic20-optimization` and
`6502-assembly` as needed.

## Bundled resources

| File | Contents |
|---|---|
| `assets/c-example/` | **Tested** (VICE NTSC, unexpanded): C `main` + ca65 `__fastcall__` kernel + `.interruptor` IRQ hook + correct frame wait + debug-cart self-test, Makefile with `test`/`run` targets |

## Builds and memory layouts

| Target | Command | Code location | Notes |
|---|---|---|---|
| Unexpanded | `cl65 -t vic20 -Osir -Cl -o p.prg main.c k.s` | `$100D–$1DFF` minus stack (`$100`) | ~3.5 KB total. Runtime + stdlib eat much of it |
| +8K and up | `cl65 -t vic20 -C vic20-32k.cfg …` | `$120D–$7FFF` (24K assumed!) | Screen `$1000`; **your code occupies `$1200–$1FFF`**, so no room for custom charsets. Linker won't catch overflow on +8K/+16K |
| +8K and up, VIC RAM free | `cl65 -t vic20 -C vic20-tgi.cfg …` | relocated to `$2000` at start-up, up to `__HIMEM__` (default `$4000`) | **Tested:** `$1200–$1FFF` free for charsets/screens. For +16K/+24K add `-Wl -D,__HIMEM__=0x6000` / `0x8000` |
| 160×192 graphics | `cl65 -t vic20 -C vic20-tgi.cfg …` + TGI `vic20-hi.tgi` | as above | `tgi_install(tgi_static_stddrv)` (= `vic20_hi_tgi`, statically linked) |

Other knobs:
- Stack: `-Wl -D,__STACKSIZE__=0x200` (defaults: `$100` unexpanded, `$800` 32k cfg, `$200` tgi cfg). The C
  software stack holds locals/parameters; shrink it when you use `-Cl` and few locals.
- Zero page: the runtime owns `$02–$1B`. Declare assembly zero-page vars in `.zeropage` (`.segment
  "ZEROPAGE"`) and let ld65 allocate them, or use `$FB–$FE`.
- BLK5 RAM as heap: `_heapadd((void*)0xA000, 0x2000);` (check that RAM is present first). The EMD driver
  `vic20-rama.emd` exposes `$A000–$BFFF` as 32 × 256-byte pages; `vic20-georam.emd` for GeoRAM.
- `ONCE` segment: init-only code that can be overlaid by buffers later.
- Map file: `-m prog.map` (check sizes); VICE labels: `-g -Wl -Ln,prog.lbl`.

## Hardware access from C

```c
#include <vic20.h>     /* VIC, VIA1, VIA2 structs, COLOR_* constants, JOY_* masks */
#include <cbm.h>       /* waitvsync(), get_tv(), KERNAL wrappers */

VIC.bg_border_color = 0x08 | (COLOR_BLACK << 4) | COLOR_BLUE;   /* $900F */
VIC.volume_color    = aux_shadow | (vol & 0x0F);                /* $900E: keep aux! */
#define POKE(a, v) (*(volatile unsigned char*)(a) = (v))         /* compiles to one STA abs */
```

Pitfalls (verified):
- **`waitvsync()` is in `<cbm.h>`, not `<vic20.h>`.** It only spins until `VIC.rasterline` (`$9004`) is 0, and
  that lasts two raster lines, so calling it twice in quick succession **returns twice in the same frame** (in a
  test, 10 calls spanned 3 frames). Use:
  ```c
  static void wait_frame(void) {
      while (VIC.rasterline == 0) ;
      while (VIC.rasterline != 0) ;
  }
  ```
  Or better, wait for a flag set by your frame IRQ.
- **`COLOR_RAM` is hard-coded to `0x9600`**, correct only when `$9002` bit 7 = 1 (unexpanded/+3K default). On
  8K+ machines colour RAM is at `$9400`. Define your own pointer from the actual `$9002` setting.
- The screen address depends on the RAM configuration (`$1E00` vs `$1000`); read `*(unsigned char*)0x288 << 8` or
  set the VIC registers yourself.
- conio (`cputc`, `gotoxy`) works but is slow; fine for menus, never in the frame loop.
- Joystick driver: `vic20-stdjoy.joy` (static `joy_static_stddrv`), `JOY_UP_MASK`… are 1 = pressed. A direct
  asm read is faster (see `vic20-system/references/input.md`).

## Performance rules (in order of payoff)

1. **Compile with `-Osir -Cl`** (static locals avoid the slow C stack). In ilmenit's CC65-Advanced-Optimizations
   benchmark (cc65 2.18), the compiler-options step alone gave a ~34% speedup; all ten optimization steps
   together brought the benchmark down to 34 ticks.
2. **`unsigned char` wherever the value fits.** int promotion and 16-bit math are expensive; avoid multiply,
   divide and general pointer arithmetic in hot code.
3. **Globals instead of parameters** for hot functions (parameters go through the C stack even with `-Cl`).
4. **`register` only for hot pointers/induction variables in substantial loops.** cc65 keeps 6 bytes of
   register variables in zero page, but save/restore costs ~70 cycles per 2-byte variable.
5. **Fixed tables instead of computed addresses**: row-address arrays, precomputed offsets, direct pointers
   to screen/charset RAM.
6. **Hardware pokes compile to one `STA abs`** via `volatile` macros or the `VIC` struct. Check with `-S` or the listing.
7. **No printf/conio/TGI calls in inner loops.**
8. **Move the inner loop to assembly** and call it `__fastcall__` (below). C decides what to draw; assembly
   pushes the bytes.

## C ↔ assembly

```c
void __fastcall__ fill_screen(unsigned char code);    /* rightmost arg in A (A/X for 16-bit) */
extern volatile unsigned char ticks;                    /* asm symbol _ticks */
```

```asm
        .export _fill_screen, _ticks
        .interruptor tick_irq           ; hooked into cc65's IRQ chain (C-runtime cfgs only)
.bss
_ticks: .res 1
.code
_fill_screen:                           ; A = code
        ldx #253
:       sta $1e00-1,x
        sta $1e00+253-1,x
        dex
        bne :-
        rts
tick_irq:
        inc _ticks
        clc                             ; C=0: not handled, KERNAL IRQ still runs
        rts
```

- C names get a leading underscore in assembly (`fill_screen` ↔ `_fill_screen`).
- Multiple arguments: the rightmost is in A/X, the others are on the C stack (`popa`, `popax` from the
  runtime, `.import popa`). For hot kernels, pass one argument or set globals first.
- Preserve nothing except the runtime's zero-page conventions; A/X/Y and the `tmp1–4`/`ptr1–4` scratch
  locations (`.importzp ptr1`) are free to clobber in a leaf routine.
- `.interruptor name[, prio]` routines run inside cc65's IRQ handler; return with C clear to pass on. Keep
  them short; for a game IRQ that replaces the KERNAL scan, write the whole IRQ in assembly instead (see
  `vic20-system`).
- **Never write cycle-exact code in C.** Compiler output changes between versions and flags.
- Inline `asm("sei");` only for one-liners.

## When C is the wrong tool

| Task | Recommendation |
|---|---|
| Menus, turn-based, adventure, puzzle | C is fine |
| Character-cell action at 20–30 fps | C with the rules above; assembly helpers for drawing |
| Pixel-smooth software sprites, scrolling | Logic in C, blitter in assembly (or VIC-SSS with its C wrapper) |
| Raster splits, waveform tricks, digis | Assembly only |
| Fitting in 3.5 KB unexpanded | Usually assembly; C runtime overhead is large (Baguel nearly ran out of space) |

## Other C compilers

- **llvm-mos** (`mos-vic20-clang`, https://github.com/llvm-mos/llvm-mos-sdk): modern optimizer, often much
  faster code than cc65; different ABI and asm syntax.
- **Oscar64**: optimizing C compiler with VIC-20 support; used by Baguel.

## Verify

`cd assets/c-example && make test` builds and runs the example headless (needs `cl65` and `xvic` on PATH).
For your own code, use the same pattern: write `0` or a failure code to `*(volatile unsigned char*)0x910F`
and run `vic20-system/scripts/vice-test.sh`.
