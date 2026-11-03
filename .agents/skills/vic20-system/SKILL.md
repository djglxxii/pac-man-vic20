---
name: vic20-system
description: Commodore VIC-20 platform knowledge for writing or fixing VIC-20 programs. Covers the memory map and RAM expansion configurations (unexpanded/+3K/+8K/+16K/+24K/BLK5), which RAM the VIC chip can see, BASIC SYS stubs and load addresses, autostart cartridges, KERNAL routines and vectors, taking over the IRQ, frame-locked VIA timers, 6522 VIA registers, joystick and keyboard reading, toolchains (cc65/ca65, ACME, 64tass, DASM, Exomizer) and testing in the VICE emulator (xvic), including headless automated tests. Use for any VIC-20 project setup, build, memory-layout, startup, input, interrupt or debugging question.
---

# VIC-20 System Programming

Pair with `6502-assembly` for CPU-level work, `vic20-graphics` for the display, `vic20-audio` for sound,
`vic20-optimization` for performance, and `vic20-cc65` for C projects.

## Bundled resources

| File | Contents |
|---|---|
| `references/memory-map.md` | Full memory map, VIC-visible RAM, per-configuration layouts (screen/colour/BASIC start), zero-page usage and free locations, memory-planning checklist, autostart cartridge header and init sequence |
| `references/kernal-irq-via.md` | IRQ/NMI/BRK flow through the ROM, `$EABF`/`$EB15`/`$EB18` exits, frame-locked VIA timer setup (NTSC/PAL latches), disabling RESTORE, full 6522 register map and VIC-20 wiring, KERNAL jump table, loading files from machine code |
| `references/input.md` | Joystick bits and a tested read routine, edge detection, keyboard matrix table, direct key checks, paddles and light pen |
| `references/toolchain.md` | cc65 configs and command lines, BASIC stubs for ACME/64tass/DASM, a custom split linker config, VICE options and monitor commands, **headless testing with `-debugcart`**, Exomizer targets, petcat/c1541 |
| `assets/template-ca65/` | Tested game skeleton (unexpanded NTSC): BASIC stub, custom charset at `$1C00` + ROM font via wrap, frame-locked IRQ exiting via `$EB15`, joystick, aux-safe volume, row tables, link-time overlap assert, Makefile with `run` and headless `test` targets |
| `assets/vic20-8k-split.cfg` | ld65 config for +8K+: stub at `$1201`, code in BLK1, `$1000–$1FFF` reserved for the VIC |
| `scripts/vice-test.sh` | Runs a PRG headless in xvic. The program writes a result byte to `$910F` (0 = pass); the script returns it, or 124 on timeout. Optional screenshot |

## First questions for any VIC-20 task

1. **Which RAM configuration?** Unexpanded, +3K, +8K, +16K, +24K, with or without BLK5? It decides the load
   address, SYS address, screen and colour RAM location, and how much room there is. If the user doesn't say,
   look for clues (load address of the PRG: `$1001` unexpanded, `$0401` +3K, `$1201` +8K+;
   `vic20-32k.cfg`; `-memory` flags in scripts). If there are none, ask.
2. **NTSC or PAL?** Timing constants differ (65×261 vs 71×312 cycles per frame), screen origins differ, and
   note tables differ. This user's references target **NTSC (6560)**.
3. **Which assembler or compiler?** Match the existing project. Default to ca65 for new projects that might
   mix in C, ACME/64tass for pure assembly if the user prefers.
4. **Does the program return to BASIC or own the machine?** That decides which zero page you can use and
   whether the KERNAL IRQ must keep running.

## Core facts to keep in mind

- **The VIC can only display data in `$0000–$03FF`, `$1000–$1FFF` and the character ROM.** Expansion RAM
  holds code and data, never displayed graphics. Screen, character sets and bitmaps all compete for those
  4 KB (+1 KB low RAM).
- Default screen: `$1E00` (colour `$9600`) unexpanded/+3K; `$1000` (colour `$9400`) with 8K+.
- BASIC stub SYS addresses: **4109** (`$1001` load), **1037** (`$0401`), **4621** (`$1201`).
- Free zero page while the KERNAL runs: `$FB–$FE` always. A takeover program that never returns to BASIC can also use `$02–$8F`.
- KERNAL ROM can't be switched out. Every IRQ goes through `$FF72` → `JMP ($0314)`.
- The stock IRQ (`$EABF`) scans the keyboard each jiffy (~650+ cycles). Games replace it and exit with
  `JMP $EB15` (acknowledges VIA2 T1 + restores registers).
- The stock jiffy timer (`$4289` latch) isn't frame-locked. Reprogram VIA2 T1 to **`$4243` (NTSC)** /
  `$5686` (PAL), started on a known raster line, for a stable 60/50 Hz tick.
- `$900E` is shared: **high nibble = multicolour aux colour, low nibble = volume.** Never write a bare volume.
- Disable RESTORE in games: `LDA #$7F / STA $911E`.
- Joystick: `$911F` bits 2–5 (up/down/left/fire) + `$9120` bit 7 (right, needs DDRB `$9122` bit 7 cleared
  temporarily). All active-low.

## Standard program startup (takeover game)

```asm
start:  sei
        cld
        lda #$7f
        sta $911e               ; no NMIs (RESTORE)
        sta $912e               ; no VIA2 IRQs while we set up
        ; set VIC registers: $9005 screen/charset, $900F colours, $9002 bit 7 colour/screen page
        ; copy/decompress charset into VIC-visible RAM, clear screen + colour RAM
        ; install IRQ at $0314/$0315, frame-lock VIA2 T1, enable with $912E = $C0
        cli
main:   ; wait for the frame flag set by the IRQ, then input -> logic -> draw
```

The template in `assets/template-ca65/main.s` implements exactly this and is tested.

## Verify your work

Prefer evidence over assumptions. When VICE is available (`which xvic`):

1. Build (`cl65 …`, `acme …`). Fix all warnings about range, zero page and segment overlap.
2. Write or reuse a self-test that writes 0 (pass) or a failure code to **`$910F`**, and run
   `scripts/vice-test.sh [--mem 8k] [--pal] --shot out.png test.prg`.
3. **Look at the screenshot** to confirm graphics output.
4. For timing, measure with border-colour profiling (see `vic20-optimization`) or cycle counts
   (`6502-assembly/scripts/cycles.py`).

If VICE isn't installed, say so and give the user the exact `xvic` command to run.

## Common pitfalls

- Using C64 addresses (`$D000` VIC-II, `$D400` SID, `$0400` screen, `$D800` colour, `$DC00` CIA, `$EA31` IRQ,
  `$0801` BASIC start). The VIC-20 equivalents are `$9000`, VIC voices `$900A–$900E`, `$1E00`/`$1000`,
  `$9600`/`$9400`, VIAs `$9110`/`$9120`, `$EABF`, `$1001`.
- Calling `$FF81`/`$FF84`/`$FF87` (C64-only jump-table entries). Use `$E518`/`$FDF9`/`$FD8D`.
- Putting a custom charset or second screen in expansion RAM (invisible to the VIC).
- Code growing over the charset/screen in `$1000–$1FFF`. Add link-time asserts.
- Exiting a custom IRQ with `JMP $EB18` without acknowledging VIA2 T1, which locks the machine up in the IRQ.
- Writing `$900E` with only the volume, which blacks out the multicolour aux colour.
- Reading joystick-right without making `$9122` bit 7 an input; or leaving it an input and breaking the KERNAL
  keyboard scan.
- Assuming PAL timing (71 cycles/line, 312 lines, `$5686`) on an NTSC target, or the reverse.
- Building a PRG for one RAM configuration and testing it under another.
