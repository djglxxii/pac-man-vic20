# VIC-20 Memory Map and RAM Configurations

## Address space

| Range | Size | Contents | VIC can see it? |
|---|---|---|---|
| `$0000–$00FF` | 256 | Zero page (BASIC + KERNAL workspace) | yes |
| `$0100–$01FF` | 256 | 6502 stack (low part also used as a BASIC/tape buffer) | yes |
| `$0200–$03FF` | 512 | KERNAL/BASIC workspace, vectors at `$0314–$0333`, cassette buffer `$033C–$03FB` | yes |
| `$0400–$0FFF` | 3K | **BLK0**: optional 3K expansion | **no** |
| `$1000–$1FFF` | 4K | Internal RAM (BASIC program + screen) | **yes** |
| `$2000–$3FFF` | 8K | **BLK1** expansion | no |
| `$4000–$5FFF` | 8K | **BLK2** expansion | no |
| `$6000–$7FFF` | 8K | **BLK3** expansion | no |
| `$8000–$8FFF` | 4K | Character ROM | yes |
| `$9000–$900F` | | VIC (6560/6561) registers | — |
| `$9110–$911F` | | VIA1 (NMI: RESTORE, joystick, user port) | — |
| `$9120–$912F` | | VIA2 (IRQ: keyboard, jiffy timer) | — |
| `$9400–$97FF` | 1K × 4 bit | Colour RAM (nibbles; upper 4 bits of each byte read back as noise) | own bus |
| `$9800–$9BFF` | | I/O2 (expansion) | — |
| `$9C00–$9FFF` | | I/O3 (expansion) | — |
| `$A000–$BFFF` | 8K | **BLK5**: cartridge ROM or 8K RAM | no |
| `$C000–$DFFF` | 8K | BASIC ROM | no |
| `$E000–$FFFF` | 8K | KERNAL ROM (cannot be banked out) | no |

**The VIC chip sees only `$0000–$03FF`, `$1000–$1FFF` and the character ROM** (plus colour RAM on its own
nibble bus). VIC address bit 13 is wired to the inverse of CPU A15, so VIC `$0000–$1FFF` = CPU
`$8000–$9FFF` and VIC `$2000–$3FFF` = CPU `$0000–$1FFF`. Expansion RAM can never be displayed: use it for
code, tables, music, level data and off-screen buffers that get copied into `$1000–$1FFF`.

## Layout by RAM configuration

The KERNAL decides where BASIC and the screen go at power-on:

| Config | BASIC program area | Screen | Colour RAM | `$9005` / `$9002` bit 7 | `$0288` (HIBASE) | BASIC bytes free |
|---|---|---|---|---|---|---|
| Unexpanded | `$1001–$1DFF` | `$1E00` | `$9600` | `$F0` / 1 | `$1E` | 3,583 |
| +3K (BLK0) | `$0401–$1DFF` | `$1E00` | `$9600` | `$F0` / 1 | `$1E` | 6,655 |
| +8K (BLK1) | `$1201–$3FFF` | `$1000` | `$9400` | `$C0` / 0 | `$10` | 11,775 |
| +16K | `$1201–$5FFF` | `$1000` | `$9400` | `$C0` / 0 | `$10` | 19,967 |
| +24K | `$1201–$7FFF` | `$1000` | `$9400` | `$C0` / 0 | `$10` | 28,159 |
| +24K + BLK5 ("32K") | as +24K, **BASIC ignores BLK5** | `$1000` | `$9400` | `$C0` / 0 | `$10` | 28,159 |

Consequences:

- A program's **load address and SYS address depend on the configuration**: `$1001`/SYS 4109
  (unexpanded), `$0401`/SYS 1037 (+3K), `$1201`/SYS 4621 (+8K or more). A PRG built for one usually fails on
  the others.
- With 8K+ the screen sits at `$1000–$11FF`, which is where an unexpanded program's code would be.
- **Never hard-code the screen/colour address in code meant to run on several configs.** Either read `$0288`
  (screen page) at startup, or (better for games) commit to one configuration and program `$9005`/`$9002`
  yourself.
- Machine code can use any RAM BASIC isn't using. A pure-assembly program that never returns to BASIC can
  use the whole BASIC area.

## Zero page and system RAM (when the KERNAL stays active)

| Location | Use | Free for you? |
|---|---|---|
| `$00–$01` | BASIC USR jump | if no BASIC USR |
| `$02–$1B` | BASIC workspace (cc65's runtime uses `$02–$1B` too) | yes in pure asm (no BASIC calls); cc65 owns them in C |
| `$1C–$8F` | BASIC (FAC, pointers, etc.) | in pure asm if BASIC isn't used (don't return to BASIC afterwards) |
| `$90–$FA` | KERNAL (I/O status, tape, keyboard, screen editor, RS-232) | mostly no while KERNAL routines are used |
| `$A0–$A2` | Jiffy clock (`$A2` = low byte) | no (unless you replace the IRQ) |
| `$C5` / `$CB` | Previous / current key matrix code (`$40` = none) | no |
| `$C6` | Number of chars in the keyboard buffer | no |
| `$D1–$D6` | Screen editor: line pointer, cursor column/row | no while using CHROUT |
| `$F7–$FA` | RS-232 buffer pointers | if no RS-232 |
| `$FB–$FE` | **Free**: "operating system free zero page space" (no ROM references) | **yes, always** |
| `$FF` | BASIC | |
| `$0100–$01FF` | Stack | |
| `$0277–$0280` | Keyboard buffer (10 bytes) | |
| `$0281–$0284` | MEMBOT / MEMTOP pointers | |
| `$0286` | Current text colour | |
| `$0288` | HIBASE: screen page (`$1E` or `$10`) | read it |
| `$028D` | Shift flags: bit 0 SHIFT, bit 1 C=, bit 2 CTRL | |
| `$02A1–$02FF` | Mostly unused (some used by RS-232); small routines are often parked here | usually |
| `$0314–$0315` | IRQ vector (default `$EABF`) | hook it |
| `$0316–$0317` | BRK vector (default `$FED2`) | |
| `$0318–$0319` | NMI vector (default `$FEAD`) | hook it |
| `$031A–$0333` | KERNAL I/O vectors (OPEN, CLOSE, CHKIN, CHROUT, GETIN, LOAD, SAVE…) | |
| `$033C–$03FB` | Cassette buffer, 192 bytes | yes if no tape I/O |
| `$03FC–$03FF` | Free | yes |

Practical rules:
- In a pure-assembly game that takes over the machine (own IRQ, no BASIC), zero page `$02–$8F` and `$FB–$FE` are
  yours. Avoid `$90–$FA` if you still call KERNAL I/O (LOAD from disk, CHROUT).
- In cc65 C programs, `$02–$1B` belong to the runtime. Put assembly zero-page variables in the `ZEROPAGE`
  segment and let the linker allocate them, or use `$FB–$FE`.
- The cassette buffer (`$033C–$03FB`) and `$02A1–$02FF` are VIC-visible too, but they are mainly
  useful for small resident routines (IRQ handlers, loaders) and one-shot init code.

## Placing things (memory planning checklist)

1. Decide the target configuration (unexpanded / +3K / +8K / +16K / +24K / +32K). Write it in the README and
   the build files.
2. Reserve VIC-visible RAM first: screen matrix(es) 506 bytes each (more for bigger screens), character
   set(s) up to 2 KB (8×8) or 4 KB (8×16), bitmap modes ~3.8 KB.
3. Put everything else outside `$1000–$1FFF` when expansion exists: code in BLK1–3, data in BLK5.
4. Unexpanded: everything shares `$1000–$1DFF` (3.5 KB). Use `$1C00` for 64 custom characters (codes 0–63)
   while keeping the ROM font as codes 128–255 (the wrap trick, see the `vic20-graphics` skill). Place
   init-only code where runtime buffers will go, use the cassette buffer, and compress with Exomizer.
5. Check with the linker (`.assert` / memory areas in the cfg) that code never grows into the character set
   or screen.

## Cartridge images (BLK5 / `$A000`)

An autostart cartridge at `$A000` starts with:

| Address | Contents |
|---|---|
| `$A000–$A001` | Cold start vector (reset jumps through it) |
| `$A002–$A003` | Warm start vector (RESTORE/NMI jumps through it) |
| `$A004–$A008` | `$41 $30 $C3 $C2 $CD` ("A0" + "CBM" with bit 7 set) |

On reset the KERNAL checks the signature **before** initialising anything else, so the cartridge's cold start
code must do its own setup: `JSR $FD8D` (RAMTAS: test/clear RAM; **this clears zero page and pages 2–3**),
`JSR $FD52` (RESTOR: default vectors), `JSR $FDF9` (IOINIT: VIAs), `JSR $E518` (CINT: VIC + screen). Then
`CLI`. (The VIC-20 KERNAL doesn't have the C64's `$FF81–$FF87` jump-table entries for these; call the routines
directly.) Test with `xvic -cartA game.bin` (no load address) or a `.crt` file.
