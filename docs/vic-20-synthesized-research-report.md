# Commodore VIC-20 (NTSC 6560): Synthesized Research Report for Graphics, Audio, and Performance Optimization

> **Purpose.** This is a single reference for a coding agent asked to optimize a VIC-20 program. It merges two independent research reports:
>
> - **Report A:** *Commodore VIC-20 NTSC Graphics and Audio: Hardware Limits and Advanced Programming Techniques*
> - **Report B:** *Commodore VIC-20 Architecture, Graphics, Audio, and Extreme Optimization* (`vic-20-deep-research-report.md`)
>
> Each report had material the other lacked. Report A was stronger on register-level detail, NTSC timing quirks, cc65 flags, audio internals, and named demo-scene techniques. Report B was stronger on the *Jetpac* case study, XOR sprites, C↔assembly interfacing (`__fastcall__`, linker configs), modern sprite libraries (Vixel, LBM8), scheduling work across frames, and the practical limits of sample playback. Where the two disagree, or seem to, §11 explains how the conflict was resolved.
>
> **Target:** NTSC VIC-20 (MOS 6560-101). PAL (6561) differences are noted only where they matter.

---

## Table of contents

0. [How a coding agent should use this report](#0-how-a-coding-agent-should-use-this-report)
1. [Quick-reference constants and registers](#1-quick-reference-constants-and-registers)
2. [Architecture, memory map, and NTSC timing](#2-architecture-memory-map-and-ntsc-timing)
3. [Graphics: capabilities and hard limits](#3-graphics-capabilities-and-hard-limits)
4. [Advanced graphics techniques](#4-advanced-graphics-techniques)
5. [Audio: capabilities and hard limits](#5-audio-capabilities-and-hard-limits)
6. [Advanced audio techniques](#6-advanced-audio-techniques)
7. [Cross-cutting optimization and resource management](#7-cross-cutting-optimization-and-resource-management)
8. [C (cc65) and assembly strategy](#8-c-cc65-and-assembly-strategy)
9. [Reference implementations and case studies](#9-reference-implementations-and-case-studies)
10. [Optimization playbook: a prioritized checklist for an existing project](#10-optimization-playbook-a-prioritized-checklist-for-an-existing-project)
11. [Source discrepancies and how they were resolved](#11-source-discrepancies-and-how-they-were-resolved)
12. [Caveats and verification requirements](#12-caveats-and-verification-requirements)
13. [Sources](#13-sources)

---

## 0. How a coding agent should use this report

1. **Find the project's memory target first** (unexpanded, +3K, +8K, +16K, +24K, "32K" with BLK5). Nearly every later decision depends on it (§2.2, §7.1).
2. **Measure before changing anything.** The VIC never stalls the CPU, so per-routine cost can be shown by changing the border colour at the start and end of each routine (§7.5).
3. **Work through the playbook in §10 in order.** It runs from cheap, safe, high-yield changes (replacing the KERNAL IRQ, removing int promotion in C, dirty-cell rendering) to expensive, risky ones (stable rasters, sample playback).
4. **Treat the "Verify" notes as real.** Several NTSC timing details and one colour bit mapping conflict between sources or rest on recent forum and emulator measurements (§11, §12). Cycle-exact code must be tested on an NTSC configuration of a current, cycle-accurate emulator, or on real hardware.
5. **Do not port PAL timing constants unchanged.** PAL demos and routines need re-timing for NTSC (65 cycles × 261 lines on NTSC, not PAL's values).

---

## 1. Quick-reference constants and registers

### 1.1 NTSC timing constants

| Quantity | Value | Notes |
|---|---|---|
| Master crystal | 14,318,181 Hz | |
| CPU clock (φ2) | 14,318,181 ÷ 14 = **1,022,727 Hz** | |
| Cycles per raster line | **65** | |
| Raster lines per (non-interlaced) frame | **261** | Older docs sometimes say 262; timing code uses 261×65 |
| Cycles per frame | 261 × 65 = **16,965** | ≈ 60 Hz |
| Frame-locked VIA timer latch | 261×65 − 2 = **16,963 = $4243** | The −2 covers the 6522's reload overhead |
| Vertical blank | Raster lines 0–27 | ≈ 28 × 65 ≈ **1,800 cycles** |
| KERNAL keyboard scan cost | ≥ ~10 raster lines ≈ **650+ cycles/frame** | ≈ 4% of the frame |
| VIA timer latch for an *R* Hz sample IRQ | `1022727 / R − 2` | e.g. 4 kHz → ~254 |
| Cycles between samples at 4 kHz | ≈ 256 | |

### 1.2 VIC-I (6560) registers, $9000–$900F

| Register | Function |
|---|---|
| `$9000` | Bit 7 = interlace (6560 only); bits 0–6 = screen X origin in 4-pixel steps (useful NTSC range ≈ 1–8) |
| `$9001` | Screen Y origin in 2-line steps |
| `$9002` | Bits 0–6 = number of columns (useful NTSC range ≈ 0–26); **bit 7 = address bit 9 for both screen matrix and colour RAM** |
| `$9003` | Bits 1–6 = number of rows; bit 0 = 8×16 (double-height) character mode; bit 7 = raster counter bit 0 |
| `$9004` | Raster counter bits 8–1 |
| `$9005` | High nibble = screen-matrix base; low nibble = character-generator base |
| `$9006/$9007` | Light pen X/Y |
| `$9008/$9009` | Paddle X/Y |
| `$900A` | Bass voice: bit 7 enable, bits 0–6 frequency |
| `$900B` | Alto voice: bit 7 enable, bits 0–6 frequency |
| `$900C` | Soprano voice: bit 7 enable, bits 0–6 frequency |
| `$900D` | Noise voice: bit 7 enable, bits 0–6 frequency |
| `$900E` | **High nibble = auxiliary colour; low nibble = master volume (0–15)**, shared by all voices |
| `$900F` | High nibble = background colour (16); bit 3 = reverse mode; bits 0–2 = border colour (8) |

### 1.3 Other fixed hardware

| Address | Function |
|---|---|
| `$9110–$911F` | VIA 1: RESTORE/NMI, user port, serial/cassette signals; joystick up/down/left/fire on port A (`$9111`) |
| `$9120–$912F` | VIA 2: keyboard matrix, joystick right (port B, `$9120`), serial/cassette, the **system ~60 Hz IRQ timer (T1)** |
| `$9124/$9125` | VIA 2 Timer 1 low/high. Reading `$9124` acknowledges the T1 interrupt |
| `$9400–$97FF` | Colour RAM: 1 KB of 4-bit nibbles |
| `$9800–$9FFF` | Expansion I/O |
| `$8000–$8FFF` | Character ROM |
| `$C000–$DFFF` | BASIC ROM |
| `$E000–$FFFF` | KERNAL ROM (cannot be banked out) |
| `$0314/$0315` | IRQ vector (RAM); default target `$EABF` |
| `$EABF` | Standard KERNAL IRQ handler: jiffy clock, cursor, full keyboard scan |
| `$EB15` | KERNAL IRQ exit: restore registers and `RTI` (skips the keyboard scan) |

---

## 2. Architecture, memory map, and NTSC timing

### 2.1 Processor, VIC, VIAs

The VIC-20 uses a 6502 clocked from the VIC-I's timing system. On NTSC the 14.31818 MHz master clock is divided by 14 to give a ~1.0227 MHz CPU clock. The 6560 generates video, sound, paddle conversion and the clocks for the rest of the machine. Two 6522 VIAs supply timers and I/O. VIA 2's Timer 1 drives the normal ~60 Hz system IRQ.

### 2.2 Memory map and expansion blocks

| Range | Contents |
|---|---|
| `$0000–$03FF` | 1 KB internal RAM: zero page, stack, KERNAL/BASIC workspace, cassette buffer at `$033C–$03FB`. **VIC-visible.** |
| `$0400–$0FFF` | BLK0: optional 3 KB expansion. **Not VIC-visible.** |
| `$1000–$1FFF` | 4 KB internal RAM. **VIC-visible.** Default screen sits near its top |
| `$2000–$3FFF` | BLK1: optional 8 KB |
| `$4000–$5FFF` | BLK2: optional 8 KB |
| `$6000–$7FFF` | BLK3: optional 8 KB |
| `$8000–$8FFF` | Character ROM (VIC-visible) |
| `$9000–$9FFF` | I/O: VIC, VIAs, colour RAM, expansion I/O |
| `$A000–$BFFF` | BLK5: cartridge ROM or 8 KB expansion RAM |
| `$C000–$FFFF` | BASIC and KERNAL ROMs |

**Layout by RAM configuration** (this explains why many titles need one exact configuration rather than a minimum):

| Config | BASIC area | Screen | Colour RAM | BASIC bytes free |
|---|---|---|---|---|
| Unexpanded | `$1000–$1DFF` (BASIC starts `$1001`) | `$1E00–$1FFF` | `$9600–$97FF` | 3,583 |
| +3K (BLK0) | `$0400–$1DFF` (starts `$0401`) | `$1E00` | `$9600` | 6,655 |
| +8K (BLK1) | `$1200–$3FFF` (starts `$1201`) | `$1000–$11FF` | `$9400–$95FF` | — |
| +16K (BLK1–2) | `$1200–$5FFF` | `$1000` | `$9400` | — |
| +24K (BLK1–3) | `$1200–$7FFF` | `$1000` | `$9400` | 28,159 |
| "32K" (BLK1–3 + BLK5) | as +24K; **BASIC does not use BLK5** | `$1000` | `$9400` | — |

When BLK1 is present, BASIC must start directly after the screen, so the screen moves down to `$1000`. **Never hard-code screen or colour addresses without considering the RAM configuration.** Either read the screen base from the VIC registers at startup, or commit to one configuration and set the VIC registers yourself.

**"Bank switching" warning.** Standard 3/8/16/24/32K cartridges decode *fixed* address blocks; there is no C64-style VIC banking. Some modern cartridges (GeoRAM-like devices) expose paged memory, and cc65 has extended-memory drivers for some of them. Code targeting a conventional 32K expansion should think in terms of placing things in BLK0/1/2/3/5, not swapping banks.

### 2.3 What the VIC can address (the single most important constraint)

- The 6560 has a 14-bit video address bus (16 KB space) and a 12-bit data bus. It fetches an 8-bit screen code and a 4-bit colour nibble at the same time.
- On the VIC-20, video address bit 13 is wired to the inverse of CPU A15. As a result the VIC sees **only the internal RAM (`$0000–$03FF`, `$1000–$1FFF`) and the character ROM (`$8000–$8FFF`)**, plus colour RAM on its own nibble bus.
- **Expansion RAM (BLK0 +3K, BLK1–3, BLK5) can never hold displayable graphics.** Its value is in relocating code, tables, compressed assets, level data and working buffers *out of* the ~4 KB of VIC-visible RAM. This is why cc65's hi-res driver uses `$1000–$1FFF` as its framebuffer but requires 8K+ expansion so the program can live elsewhere.
- **The `$1C00` character-base wrap trick:** with the character base set to `$1C00`, the address wraps so that the non-inverted ROM characters appear as screen codes 128–255. You get custom characters (codes 0–127 from RAM at `$1C00–$1FFF`) and the ROM font together, with no raster tricks. (Documented by "Mike" on the Denial forum.)
- The internal 1 KB at `$0000–$03FF` is also VIC-visible. Screen matrices have been placed in the `$0200` area (Denial thread "Using screen memory at location $200"), which frees `$1000–$1FFF` for character data.

### 2.4 Bus sharing: no "bad lines", deterministic timing

- The 6560 swaps the direction of its address pins with the clock phase. In one phase the CPU accesses memory or registers; in the other the VIC drives addresses for display fetches. **Video fetches never stall the CPU.**
- The dot clock is only 4× the bus clock, so the VIC reads exactly 2 bytes per 8 pixels: first the character code plus colour, then the pattern byte. It re-reads character codes on every raster line. In Mäkelä's words this makes "every line a 'bad line'" from the VIC's side, but at **zero CPU cost**.
- **Strength:** cycle counts are the same everywhere on screen. There is no badline or sprite-DMA jitter as on the C64's VIC-II, and a 65-cycle line stays 65 usable CPU cycles.
- **Weakness:** the fixed fetch bandwidth of 2 bytes per cell rules out sprites, bitmap modes and wide screens. It is the reason for 22 columns.
- Outside the text window the VIC idles, reading from `$001C`. Reads from unconnected space such as `$9100–$910F` return whatever the VIC fetched on the previous cycle. Timing-test programs use this.

### 2.5 NTSC frame details and quirks (important for raster code)

- 261 lines × 65 cycles per non-interlaced frame.
- **Partial lines:** measurements posted on Denial show a non-interlaced NTSC field starts with a partial line 0 of 32 cycles, runs lines 1–260 at 65 cycles each, and ends with a partial line 261 of 33 cycles. The total is still 261×65. VICE likewise treats the first and last partial intervals specially.
- **The raster register changes mid-line on NTSC.** Recent emulator work, checked against VICE and real-machine dumps, puts the 6560's counter change **37 cycles earlier** relative to the picture than on the PAL 6561. NTSC code that polls `$9004` and assumes the change happens at the start of the line will be off by about half a line.
- Vertical blank covers raster lines 0–27.
- Only the 6560 has the interlace bit (`$9000` bit 7), giving 525 interlaced lines. The PAL 6561 ignores it. Stable-raster NTSC constants usually assume non-interlaced output.
- **The KERNAL's 60 Hz VIA timer is not frame-locked.** On NTSC it drifts slowly against the frame, so it is useless for raster work until you reprogram it (§7.3).

---

## 3. Graphics: capabilities and hard limits

### 3.1 Display model

- Default: **22 × 23 cells of 8×8 pixels = 176 × 184 pixels; 506-byte screen matrix.**
- The registers allow other shapes: experimental NTSC limits are about 26 columns and about 29 rows with suitable origins. These are overscan and geometry tricks that are less portable across TVs. Bigger screens also cost more matrix bytes.
- Characters can be 8×8, or 8×16 with `$9003` bit 0. In 8×16 mode each code addresses 16 bytes, so a full 256-character set spans 4 KB.
- A 256-character 8×8 set is 2 KB.
- Whole-screen fine positioning is only in **4-pixel horizontal steps** (`$9000`) and **2-line vertical steps** (`$9001`). Per-pixel smooth scrolling has to be done by re-rendering character data.
- **No sprites, no bitmap mode, no raster interrupt.** "Programmable characters are the only way of creating graphics and animation on the VIC."

### 3.2 Colour rules

| Source | Range | Scope |
|---|---|---|
| Colour RAM bits 0–2 | 8 colours (0–7) | Per cell (foreground) |
| Colour RAM bit 3 | Multicolour flag | Per cell |
| Background (`$900F` high nibble) | 16 colours | Global |
| Border (`$900F` bits 0–2) | 8 colours | Global |
| Auxiliary (`$900E` high nibble) | 16 colours | Global |
| Reverse (`$900F` bit 3) | Swaps foreground/background roles in hires cells | Global |

- **Hires cell:** 8×8 one-bit pixels. Each pixel is background or the cell's foreground, which is limited to colours 0–7. Effectively two colours per cell.
- **Multicolour cell:** 4×8 double-width two-bit pixels. Values map to background, border, cell foreground and auxiliary. Per the Programmer's Reference Guide and most community sources: `00` = background, `01` = border, `10` = cell foreground, `11` = auxiliary. **Verify:** Mäkelä's VIC-I.txt lists `01` and `10` the other way round. Check in an emulator before hard-coding bit patterns.
- Three of the four multicolour sources (background, border, aux) are global. That is why changing them per raster line is the most valuable raster effect. For art design, treat background and aux as scene-wide palette resources and use per-cell colour for local contrast.
- The 16-colour palette does **not** mean 16 freely selectable colours per pixel or per cell.

### 3.3 The central resource trade

Characters are at the same time **glyph identities, animation storage, and pieces of your pseudo-framebuffer.** Every unique animation frame or sprite work cell uses a character slot plus 8 or 16 bytes of VIC-visible RAM that could otherwise hold terrain or font glyphs. Good designs split the character set into:

- static tiles;
- shared animation tiles, where one definition animates many cells;
- a small pool of "working" characters for moving objects.

---

## 4. Advanced graphics techniques

### 4.1 Character-definition animation (cheapest effect, 1982-era practice)

Change the **definition** of a character, not the screen cells. Rewriting the 8 bytes of a character that appears many times on screen animates every copy at the cost of 8 stores. Water, flames, spinning items, status icons and scrolling background patterns should all be shared animated tiles.

- *Gridrunner* (Jeff Minter, 1982) is "entirely character based" (every object is one character). It filled the unexpanded machine exactly: 3,585 bytes including the 2-byte load address. It was written in VICMON.
- *Matrix* (Minter) rolls its grid by rotating the grid character's bytes in place (`ROL charsetLocation-1,X`). It syncs by busy-waiting on the raster (`LDA $9004 / CMP #$7F / BNE`) rather than using an interrupt.
- General rule: **update only dirty cells, and prefer redefining characters to redrawing the screen.**

Basic animation copy:

```asm
; frame_ptr in zero page points to 8 bytes of the next frame
        ldy #7
copy:   lda (frame_ptr),y
        sta charset+CHAR_INDEX*8,y
        dey
        bpl copy
```

The fastest version replaces the loop with eight literal `LDA abs / STA abs` pairs, or with self-modified absolute addresses when the destination changes. That costs code size but removes the branches and indirect addressing, which is a good trade for anything that runs every frame.

### 4.2 Software sprites

**Option 1: character-aligned, pre-shifted tiles.** Change screen codes to pick pre-shifted object tiles. Smooth horizontal motion needs a separate graphic for each sub-cell offset: 8 phases in hires, fewer in multicolour. Larger objects use 2×2 or bigger groups, which multiplies the data and the update bandwidth.

**Option 2: character RAM as a local framebuffer (the standard engine pattern).**

1. Reserve a pool of "sprite" character codes.
2. For each object, work out the cells it covers. An 8×8 object at an arbitrary pixel offset covers up to 2×2 cells; a 16×16 object covers up to 3×3 ("a 16x16px sprite can also eat up 9 chars").
3. Copy the background characters for those cells into pool characters.
4. OR, or XOR, the pre-shifted (or shifted-on-the-fly) sprite bytes into the pool characters.
5. Poke the pool codes into the screen cells and set colour RAM if needed.
6. To restore, write the original screen codes back.

**XOR drawing (the *Jetpac* approach).** Applying the same XOR data twice restores the original pixels, so no background copy is needed:

```text
erase_old:  framebuffer_byte ^= old_sprite_byte
draw_new:   framebuffer_byte ^= new_sprite_byte
```

*Jetpac* uses this widely, including for its laser. It compares old and new positions, erases only the parts that will no longer be covered, and draws the new image byte by byte. It trades some visual limits (XOR artefacts where objects overlap) for large RAM savings and simpler overlap logic. VIC-SSS later added XOR "ghost" sprites, and *Lunar Leeper*'s author reportedly XORed sprites onto background characters (second-hand forum report).

**Hard limits:**

- Each sprite costs up to 4–9 characters plus save and restore work. **About 8–16 small sprites is the practical ceiling.** "Having 16 8x8px sprites around is already kind of over the edge on the VIC."
- **Colour clash is unavoidable.** A sprite takes the colour-RAM nibble of the cell it is in, unless you also rewrite colour RAM and accept the effect on background pixels in that cell. *Jetpac* updates colour separately, per tile.
- Measure cost in **bytes touched and cycles per visual object**, not in "number of sprites". An XOR sprite spanning several uniquely mapped cells can dominate the frame.

**Engines and libraries to reuse or study:**

| Engine | Target | Key facts |
|---|---|---|
| **VIC-SSS** (Robert Hurst) | 8K+ | ca65 library and API. On-the-fly character manipulation with **dual video buffers**; frame flips can be raster-timed; XOR ghost sprites; collision detection. Gives most of the internal 4 KB to the playfield. Used by *Berzerk MMX*, *Omega Fury*, *Quikman+*. A community C wrapper for cc65 exists. |
| **Pulse** (Sven "pixel" Klose) | Unexpanded | Horizontally smooth-scrolling shooter with **16 software sprites**, double-buffered, using **48 characters for 16 sprites**. When characters run out "it just picks the last character used" (visible glitch). Does not wait for the retrace. Sprites are never removed, only turned into background stars, to keep frame time constant. Built with Exomizer. |
| **Vixel** | Modern | Local-character-buffer sprites. Pixel-precise horizontal positioning through lookup tables. Its optional 1-pixel precision costs extra tables (RAM traded for CPU time and smoother motion). |
| **LBM8** | Modern | "Local bitmap" system: small sprites at arbitrary pixel positions over a normal character screen. Pre-shifted images, dirty-object updates, fixed-point movement, lookup-table acceleration. |
| **Baguel** (Oscar64 C) | Unexpanded | Software sprites from C. The author nearly ran out of space even with horizontal-only pixel movement. A warning about C on an unexpanded machine. |

### 4.3 Double buffering

Two different costs need to be kept apart:

- **Screen and colour page flip is cheap.** `$9002` bit 7 supplies address bit 9 for *both* the screen matrix and colour RAM. Toggling it (with the `$9005` screen nibble set to match) switches screen `$1000↔$1200` **and** colour `$9400↔$9600` in **one register write**. Draw into the hidden screen and colour page, then flip during vertical blank (raster lines 0–27, or the bottom border).
- **Character-set double buffering is expensive.** A second 2 KB set (through the `$9005` low nibble) usually doesn't fit. Within the 4 KB the VIC can see, a common split is about 2 KB of characters plus two 512-byte screens. That is why VIC-SSS and similar engines put code in 8K+ expansion and keep `$1000–$1FFF` purely for display.
- An analysis of an Elite port on Denial found that "clear screen, draw, wait VBL and flip buffer" beats erasing lines one at a time and gives "no flicker at all".

**Cheaper alternatives when a full flip doesn't fit:**

- Keep the screen matrix fixed and double-buffer only a small working set of characters.
- Keep old/new object state and redraw only touched cells.
- Use XOR-reversible sprites instead of saving background copies.
- On expanded machines, keep a logical off-screen representation in expansion RAM and convert only dirty regions into VIC-visible RAM.
- Keep two asset or character banks in expansion RAM and copy the needed definitions into the active charset during vertical blank or safe raster windows.

### 4.4 Bitmap emulation

A naive 22×23 unique-character bitmap needs 506 distinct glyphs, more than 256. Practical solutions use fewer cells, 8×16 characters, shared glyphs, raster-switched character banks, or code moved into expansion RAM.

**The canonical layout is Mike's MINIGRAFIK / MINIPAINT mode, 160×192:**

- Set the screen base and character base both to `$1000`, and turn on double-height (8×16) characters.
- Fill a **20 × 12** text matrix with codes `$10–$FF` in **column-major** order (240 bytes at `$1000–$10EF`).
- The **3,840-byte bitmap** sits at `$1100–$1FFF`.
- Arithmetic: each 8×16 tile needs 17 bytes (1 screen byte + 16 bitmap bytes), and 4096/17 ≈ 240.9, so 240 tiles = 160×192 pixels. That is "the biggest resolution that can be displayed on an unmodded VIC-20 without using the lower 1K RAM, or raster interrupts."
- **Pixel addressing:** byte = `$1100 + (x >> 3) * 192 + y`; bit mask = `$80 >> (x & 7)`. Use one 20-entry table of column base addresses (`$1100 + col*192`) and draw down a column with `INY`.
- Colour still comes from colour RAM, in 8×16 cells.
- **cc65's `vic20-hi.tgi` driver uses exactly this 160×192 two-colour mode at `$1000–$1FFF`** and needs 8K+ expansion. Programs linked with `vic20-tgi.cfg` relocate themselves into expansion RAM. It is the reference design for C authors.

**Beyond 160×192:** switching character sets or registers mid-screen with stable rasters gives larger and more colourful modes. Mike's "New Frontiers in VIC-Hires-Graphics" series and the Denial round-up of display modes cover these, including FLI-like modes up to 79,872 pixels. They mostly suit still images, because the CPU spends the frame babysitting the VIC.

**Example of a commercial unique-character layout:** *Jetpac* uses 23 columns × 11 rows of 8×16 RAM characters with character graphics at `$1000`. That is 253 unique cells, about 4 KB of definitions, so its screen matrix must live elsewhere in VIC-visible RAM (this is inferred from the arithmetic; check against the disassembly).

### 4.5 Raster effects without a raster interrupt

**Simple polling.** Wait for a chosen line on `$9004` (plus `$9003` bit 7 for bit 0), then write `$900F`, `$900E`, `$9005`, `$9000`/`$9001`. This is fine for a status-bar split but jitters by a few pixels, because the loop can notice the change at different points in its instruction sequence. On NTSC, allow for the raster counter changing mid-line (§2.5).

**Stable rasters (VIA timer locked to the beam).** This is the method from Marko Mäkelä's "Making stable raster routines (C64 and VIC-20)", mirrored on Codebase64. Mäkelä tested it on PAL but gives NTSC constants.

1. Busy-wait on `$9004`/`$9003` until the beam reaches a known line, then align to the exact cycle, for example with a double-read loop.
2. Start a VIA timer whose period is exactly one frame: `LINES*CYCLES − 2` = 261×65 − 2 = **16,963 ($4243)** on NTSC.
3. In the IRQ, read a free-running reference timer, or the IRQ timer's own low byte at `$9124`. Use the value to jump into a NOP or `CMP #$C9` slide that removes the 0–7-cycle interrupt-entry jitter.
4. From that point every cycle is known. Write `$900F` (border and background), `$900E` (aux colour), `$9005` (character set) or `$9000`/`$9001` at exact beam positions.

Conceptual setup:

```asm
; 1) synchronise once (simplified; real code needs cycle alignment, see Mike/Mäkelä)
wait:   lda $9004
        cmp #TARGET_LINE
        bne wait
; 2) VIA2 Timer 1 free-running, period = one NTSC frame
        lda #<$4243
        sta $9124        ; latch low
        lda #>$4243
        sta $9125        ; latch high -> counter loaded, timer starts
; IRQ: (a) acknowledge the timer (read $9124) (b) compensate entry jitter
;      (c) do the cycle-counted VIC register writes
```

- **Use proven code.** Mike's Denial thread "Stable rasters on the VIC-20" provides a version that builds for PAL or NTSC. It uses a single timer and reads `$9124` to drive a variable delay. Its NTSC constants assume non-interlaced output.
- **Budget:** an NTSC line has only 65 cycles. A few register writes plus IRQ overhead take a large share of a line, so CPU time, not DMA, is the limit.
- **Uses in the wild:**
  - *Robotic Liberation* (PWP, 2003): viznut's Brickshop pictures set "the three 'global' video colors … separately for each scanline".
  - *Realms of Quest 5*: a stable-raster window in the top left.
  - The *Pitfall!* port (Victragic): FLI-style raster tricks in a playable game.
  - *Demon Attack*: contemporary recollections describe per-scanline background changes that colour its enemies (not confirmed by disassembly).
- **Geometry tricks:** changing the row count or vertical origin mid-frame can show areas outside the normal 23 rows, or make bands read memory or colours differently. These are overscan effects, not extra raster lines; the NTSC timing is fixed.

### 4.6 Cycle-optimized drawing

Because there is no DMA to blur timings, standard 6502 practice pays off fully here:

- Keep pointers and hot counters in **zero page** and use `(zp),Y` addressing.
- Lay character data out so that **Y indexes rows**. Use `DEY/BPL` or `DEX/BNE` loops, and lay data out so loops can count downward. *Jetpac* arranges its graphics data for decrementing loops.
- **Unroll** 8-row (or 16-row) character copies.
- Use **pre-shifted sprite tables**: 4 or 8 shifted copies, trading RAM for cycles.
- Use **lookup tables instead of arithmetic**: row and column address lo/hi tables, multiply-by-192 column tables for MINIGRAFIK, shift tables, collision masks, frequency tables, sine/cosine, inverse-depth tables, colour-RAM address tables. A 2026 reconstruction of a late-1980s VIC-20 3D cube demo uses fixed-point maths, assembler-generated trig tables, inverse-depth tables and row-address tables to avoid runtime multiply and divide.
- **Align tables** so that indexing does not cross pages unpredictably (each page cross on an indexed read costs a cycle and makes timing vary).
- **Specialize routines** for common sprite widths instead of writing one general blitter.
- **Self-modifying code:** patch absolute addresses into `LDA abs,X / STA abs,X` instead of paying for indirect addressing:

```asm
; patch destination once per sprite/cell
        lda dst_lo
        sta store+1
        lda dst_hi
        sta store+2
        ldy #7
loop:   lda sprite,y
store:  sta $ffff,y      ; operand patched above
        dey
        bpl loop
```

The VIC-20 has no cache and program RAM is writable, so self-modifying code is straightforward. The costs are complexity and loss of reentrancy, which is usually acceptable for a single-threaded renderer, decompressor or sample player. Avoid it in code an IRQ can re-enter.

- **Culture benchmark:** viznut's waveform setter (§6.2) combines self-modifying code, illegal opcodes (`AXS`, `ASO`/`SLO`), exact cycle counting and code alignment chosen to avoid page-cross penalties.

---

## 5. Audio: capabilities and hard limits

### 5.1 Voices and pitch

| Register | Voice | NTSC base clock (Hz) | Derivation |
|---|---|---|---|
| `$900A` | Bass | 3,995 | φ2 / 256 |
| `$900B` | Alto | 7,990 | φ2 / 128 |
| `$900C` | Soprano | 15,980 | φ2 / 64 |
| `$900D` | Noise | 31,960 | φ2 / 32 |

- Bit 7 enables the voice; bits 0–6 hold the divider value.
- **Frequency:** `f = C / (127 − X)`, where X is the 7-bit value. This is the same as `f = C / (255 − N)` with N the full register byte including the enable bit, since N = 128 + X. (Report A gave the first form and Report B the second; they agree.)
- Pitch resolution is coarse and gets worse toward the top of the range, so upper notes are noticeably out of tune. This gives the "dusty, old piano" character.
- The three voices are fixed an octave apart. Each covers about 3 octaves and together they span about 5, with overlap. **Note tables should pick, for each note, whichever generator gives the smallest tuning error.** The overlap also helps with chord voicing.
- **Master volume:** `$900E` low nibble, 0–15, one value for all voices. **The high nibble is the aux colour, and sound code must preserve it.**

### 5.2 How a voice really works (viznut's 2003 reverse engineering)

- Each tone voice is an **8-bit shift register** driven by a **7-bit counter** clocked at CPU/16, /8 or /4 (bass, alto, soprano).
- On each counter overflow: `reg = (reg << 1) | (((reg >> 7) ^ 1) & voiceon)`. Bit 0 is the output.
- A free-running register gives a 16-step square wave. The register keeps shifting while the voice is off, which is what the waveform trick in §6.2 relies on.
- **Noise:** a 16-bit LFSR gating an 8-bit shift register. Lance Ewing reverse-engineered it, and VICE's corrected noise emulation (bug #1125, Petri Häkkinen's work) is based on that. "White noise" describes how it sounds, not what it is mathematically.

### 5.3 Compared with the SID

There is **no** ADSR, filter, pulse-width register, waveform selector, ring or sync modulation, or per-voice volume. There is one global 16-step volume and coarse 7-bit pitch. Every articulation beyond a steady tone and noise has to be made with CPU register writes.

**On "pulse-width" effects:** there is no PWM hardware. "Pulse-width-like" timbres can only be approximated in time: rapid gating, alternating nearby frequencies, or two voices at close pitches to create beating. Do not describe these as SID-style PWM. The real extra timbres come from §6.2.

### 5.4 Extra voice from the 6522

The VIA's free-running shift register on the user port's CB2 line (documented in the Programmer's Reference Guide) can act as an extra square-wave voice whose bit pattern sets the waveform. It **needs an external amplifier**, so it is irrelevant to most software projects.

---

## 6. Advanced audio techniques

### 6.1 Software envelopes, articulation, and safe `$900E` writes

- Drivers usually tick at the 60 Hz frame IRQ. A decay is done by stepping the `$900E` volume down each tick.
- Because volume is global, **a volume envelope affects the whole mix.** Per-voice "envelopes" are faked by:
  - gating voices on and off (bit 7);
  - detuning and pitch bends for vibrato and slides (alternating adjacent divider values);
  - **arpeggios**, cycling one voice through chord tones at 60 Hz to suggest polyphony.
- Prefer note gating and pitch animation to volume changes unless you want the whole mix to pulse.
- Update the volume only on the music tick, not continuously, unless you want amplitude modulation.

**Safe volume write.** Prefer a RAM shadow of the aux colour (no read-modify-write, a fixed cycle count, and correct even if raster code changes the aux colour mid-frame):

```asm
; A = desired volume 0..15, aux_shadow = aux colour << 4
        and #$0f
        ora aux_shadow
        sta $900e
```

Read-modify-write alternative (from Report B):

```asm
        and #$0f
        sta temp
        lda $900e
        and #$f0          ; keep the aux colour
        ora temp
        sta $900e
```

The *Vicious Tracker*'s volume control is "set up to not interfere with the vic's aux color". Do the same.

### 6.2 "Viznut waveforms": 15 extra timbres

Toggling a voice's enable bit at exact cycle times loads chosen bit patterns into its shift register. This gives **15 extra 16-step waveforms** ("10", "110", "100100", …). Example from viznut's original text:

```asm
; $900c held at $7e for a while first (voice off, max shift rate)
        ldx #$7e   ; off, max shift rate
        ldy #$fe   ; on,  max shift rate
        lda #152   ; desired note
        sei
        sty $900c  ; push 1
        sty $900c  ; push 1
        stx $900c  ; push 0
        sta $900c  ; free-run -> "110" waveform
        cli
```

- Viznut's generic `setwave` routine loads any 8-bit pattern in about **154 cycles**. It must run with **interrupts off**, and the voice must be silenced (`$7E`) first. (Source: VICMIDI `Docs/waveforms.txt` and the Denial "Viznut's waves?" thread.)
- Used in *Robotic Liberation* and *Robotic Warrior*.
- **Emulation warning:** in 2003 viznut said VICE "fails miserably" at these tricks, and cycle-exact oscillator emulation was not available then. Test on hardware or a current cycle-exact emulator.
- Schedule waveform reloads in vertical blank so they don't collide with raster code.

### 6.3 Noise percussion

- **Snare:** a short noise burst (`$900D` on, high value) with the frequency stepped down over 2–4 frames.
- **Kick:** a low noise value, often combined with a fast pitch drop on the bass voice and a volume decay.
- Very short bursts at different noise values give explosions, footsteps, gunfire and cymbals (as shown in 1980s VIC books).
- **Timbre consistency:** stopping and restarting noise subtly changes its timbre because of LFSR state (tlr's DATAPOP test, VICE bug #1125). Drivers that need consistent drums keep the noise running and gate it some other way, or accept the variation.

### 6.4 Music drivers, channel roles, and priority

- **Fixed roles** (largely forced by the octave ranges): bass voice for bass lines, alto for harmony or arpeggios, soprano for melody, noise for drums.
- **Effects steal a voice:** a sound effect takes a chosen music voice (usually soprano or noise) for its duration, then the driver restores the music state. Frame-level sharing, where a voice plays melody on some ticks and an effect on others, works if the interruption is short.
- **One IRQ entry point:** run music from the IRQ vector at `$0314/$0315` at 60 Hz. COMPUTE! #32's "VIC Sound Generator" (1983) put machine code in the cassette buffer, counted durations in jiffies and chained to `JMP $EABF`. In an optimized game, chain to `$EB15` instead (§7.3).
- **Commercial variety:**
  - *Gridrunner* calls `PlayBackgroundSounds` from its main loop, not from an IRQ.
  - *Jetpac* treats sound as another object type in its handler table. A `SOUND UPDATE` handler dispatches to deliberately cheap effect routines, leaving most CPU time for graphics.
  - *Ultima: Escape from Mt. Drash* is BASIC with assembly routines for the background music. Sources disagree on whether it uses 3 or 4 voices.
- **Tools and players:**
  - **VIC-TRACKER** (Daniel Kahlin): the editor needs 16K, but its compressor emits compact assembly data and code whose songs play on an **unexpanded** VIC. Use a big machine for authoring and a small replay for the target.
  - **Vicious Tracker** (rzo42): 4-voice pattern columns, a volume column, pitch-modulation patterns, and handles the aux colour safely.
  - **Fisichella** (Aleksi Eeben): runs unexpanded. Eeben's *Loop Arranger* used 4-bit samples.
  - viznut fitted self-contained demo players into "just over a hundred bytes".
  - *Veni vidi Vic!* includes Jonas Hultén's music code with its source release (§9).

### 6.5 Sample playback (4-bit DAC through the volume nibble)

Writing to the volume nibble moves the output level even with every voice off. One emulator measurement puts a full 0→15 swing at about **0.22 of a single voice's step**, which is why VIC digis are quiet.

- **Minimal loop** (Csabo's port of a Plus/4 player): `LDA sample,X / STA $900E / delay`.
- **Practical structure:**

```asm
sample_loop:
        lda samples,x
        and #$0f
        ora aux_shadow     ; or accept a flickering aux colour
        sta $900e
        ; cycle-counted delay to hit the target rate
        inx
        bne sample_loop
```

- **Variants:**
  - Pack two 4-bit samples per byte.
  - Drive playback from a VIA timer IRQ with latch `1022727/rate − 2` on NTSC, and **exit through `$EB15`, not `$EABF`**, so the keyboard isn't scanned thousands of times a second.
  - Turn off or minimize unrelated IRQ activity.
  - Use page-aligned sample storage and precomputed or filtered data to shorten the inner loop.
- **Practical ceiling:** one VIC-20 MOD-player project found **about 4 kHz at 4 bits** to be as far as its software mixing approach could go on the stock CPU. That leaves about **256 cycles per sample** on NTSC, and jitter in that interval is audible. Treat this as one implementation's result, not a hard theorem.
- **Streaming from storage:**
  - "One hour of digitized music" (boray, PAL, unexpanded) streams from an SD2IEC with a cycle-exact SEI/CLI transfer loop.
  - pixel's "Ohne Dich" streams 4-bit audio from **cassette** in real time by reading the VIA2 timer at each tape pulse edge and writing `LSR`-reduced values to `$900E`.
- Archive collections hold digitized speech and music that need several expansion blocks, so this was used in practice, not just in theory.

### 6.6 Coexisting with demanding graphics

- **Register-based music is cheap:** tens to a few hundred cycles per frame, ticked once per frame (or a small multiple) in vertical blank or a fixed timer slot. It fits easily.
- **Cycle-exact audio (waveform loading, PCM) clashes with cycle-exact video.** Options:
  - Schedule waveform reloads in vertical blank.
  - Run sample or speech output from the **same stable timer** as the raster code, so each IRQ does a fixed amount of video and audio work.
  - Lower the sample rate, or schedule graphics around the audio cadence.
  - Accept frames where an effect pauses.
- Viznut's singing speech synthesizer runs alongside raster graphics on an unexpanded VIC in *Robotic Warrior* and *Robotic Liberation*, so it can be done, but only with unified timing design.

---

## 7. Cross-cutting optimization and resource management

### 7.1 Memory conservation

- **Keep displayable data in `$1000–$1FFF`** (and `$0000–$03FF` if needed). Put everything else (code, tables, music, level data) in `$0400–$0FFF` (+3K), `$2000–$7FFF` (BLK1–3) or `$A000–$BFFF` (BLK5).
- **Separate memory use by phase (overlays):**
  - Init code unpacks graphics or builds lookup tables, then gets overwritten by runtime state.
  - Use the cassette buffer (`$033C–$03FB`) for one-shot or small resident routines.
  - cc65's `ONCE` segment holds init code that can be overlaid with runtime buffers.
  - Level loaders reuse one staging buffer. Title-screen graphics are dropped when play starts.
  - Setup-only routines share memory with play-only animation data.
- **Reuse RAM over time:** viznut's *Robotic Liberation* (about 17 KB of content on an unexpanded machine) used a trackloader to stream data into "unused and soon-to-be-freed portions of memory". He later automated this "loader-linking" for *The Next Level*.
- **Compress** with Exomizer (used by Pulse) or pucrunch.
- **Trade character slots for animation frames:** Pulse caps sprites at 48 characters, and Gridrunner animates by rewriting characters rather than storing frames.
- **Use the `$1C00` charset wrap** to get the ROM font for free (§2.3).
- **BLK5 (`$A000–$BFFF`)** suits assembly data, heap, cartridge-like code or overlays. BASIC ignores it. In cc65, add it to the heap with `_heapadd((void*)0xA000, 0x2000)`. cc65 also has an extended-memory driver for RAM there.

### 7.2 Zero page, lookup tables, self-modifying code

- **Zero page is premium space.** `LDA zp` is shorter and faster than absolute addressing, and `(zp),Y` is the 6502's natural pointer mechanism. Keep current object pointers, source and destination graphics pointers, frequently changed counters and 16-bit temporaries there. *Jetpac* uses many zero-page variables plus a helper that loads zero-page parameter pointers from inline data.
- **Check for clashes:** cc65's runtime reserves 26 zero-page bytes (`$02–$1B`), and the KERNAL and BASIC use much of the rest. If you keep the KERNAL, find out which locations are actually free in your configuration.
- **Lookup tables** replace multiply, divide and shifts (§4.6).
- **Self-modifying code** gives the biggest wins in renderers, decompressors and sample players, and the smallest in code that must be reentrant or relocatable.

### 7.3 IRQ, VIA, and KERNAL overhead (one of the largest easy wins)

- **The vector chain:** the KERNAL ROM cannot be mapped out, so every hardware IRQ passes through ROM, pushes the registers, and does `JMP ($0314)`. By default that points to `$EABF`, which updates the jiffy clock, handles the cursor and cassette, and performs a **full keyboard scan costing at least 10 raster lines (≈650+ cycles) every frame**.
- **Skip it:** games that read only the joystick (plus a few keys) can point `$0314/$0315` at their own handler and **exit via `$EB15`** (restore registers, `RTI`). **Acknowledge the VIA yourself**, for example by reading `$9124`. You then have to provide any services you still need (jiffy clock, keys).
- **Turn off unneeded VIA interrupt sources** and scan only the controls you use.
- **Frame-lock the timer:** reprogram VIA2 T1 to **16,963 cycles** for a frame-locked NTSC IRQ, started at a known raster line, and use the other VIA's timers for music or sample rates. This recovers about 4% of the frame and gives a stable time base for music.

Sketch of a frame-locked game IRQ (adapt and verify; for cycle-stable rasters use Mike's or Mäkelä's code):

```asm
        sei
        lda #<game_irq
        sta $0314
        lda #>game_irq
        sta $0315
        ; wait for a chosen raster line here (see §4.5)
        lda #<16963
        sta $9124            ; T1 latch low
        lda #>16963
        sta $9125            ; T1 latch high -> load + start (T1 already free-running under KERNAL)
        cli
        ...
game_irq:
        lda $9124            ; acknowledge VIA2 T1
        ; music tick, input read, frame counter, page flip, etc.
        jmp $eb15            ; restore Y/X/A and RTI (no keyboard scan)
```

- **Read the joystick directly:**
  - Up, down, left and fire are on **VIA1 port A (`$9111`)**: bit 2 up, bit 3 down, bit 4 left, bit 5 fire, all active-low.
  - Right is on **VIA2 port B (`$9120`) bit 7**, which shares lines with the keyboard matrix. Make that bit an input (VIA2 DDRB `$9122`) before reading, then restore it.
  - The bit positions are standard VIC-20 documentation rather than something either source report spelled out; confirm them in the target emulator.
- **Restricted keyboard scan:** VIA2 exposes the keyboard row and column lines directly, so scan only the few keys you need instead of running the KERNAL's translation and buffering.
- **The VIA timers are the VIC-20's best timing resource:** one for the frame or raster IRQ, another for phase measurement, short events, or serial and audio timing.

### 7.4 Budgeting and scheduling the frame (NTSC)

The frame is about **16,965 cycles**, and with no badline stalls the budget is very regular. Typical action-game split:

| Item | Typical cost |
|---|---|
| Vertical blank window (lines 0–27) | ~1,800 cycles available for flips, charset copies, waveform reloads |
| Music tick (register-based) | A few hundred cycles |
| Input (direct VIA read) | Well under 100 cycles |
| KERNAL keyboard scan (if kept) | ≈650+ cycles; remove it |
| Sprite erase, redraw and flip | The largest share, roughly sprites × cells × 8 (or 16) bytes |
| Game logic | Whatever is left |

**Spreading work across frames** (scheduling patterns):

- Animate only dirty characters.
- Process a subset of enemies each frame (round-robin). Update the player every frame and distant or minor objects less often.
- Run music at one fixed tick.
- Do colour and charset raster writes only in their narrow timing windows.
- **Give the player priority:** *Jetpac*'s VIA IRQ regulates object processing and puts Jetman first, so the game stays responsive under graphics load.
- **Keep frame time constant** where possible (Pulse never removes sprites; it turns them into stars) to avoid uneven slowdown.

### 7.5 Profiling technique

The VIC never halts the CPU, so profiling is easy. **Write a distinct border colour to `$900F` at the start of each routine and restore it at the end.** The height of each colour band on screen is that routine's cost in raster lines (65 cycles each). Bands that wrap past the bottom of the frame mean the frame is over budget.

---

## 8. C (cc65) and assembly strategy

### 8.1 Toolchain facts

- **Default target:** unexpanded machine. Usable RAM is `$1000–$1DFF`, the screen is at `$1E00`, and the C software stack grows down from `$1DFF`.
- **`vic20-32k.cfg`:** program starts at `$1201`. The default C stack is 2 KB; reduce it with `-D __STACKSIZE__=0x100` if that is enough. 26 zero-page bytes (`$02–$1B`) are reserved for the runtime.
- **`vic20-tgi.cfg`:** used with `vic20-hi.tgi` (160×192 at `$1000–$1FFF`). The program relocates into expansion RAM. The sample build gives its larger TGI demo more high memory by changing the linker's high-memory symbol.
- **`vic20.h`** provides the `VIC`, `VIA1`, `VIA2` and `COLOR_RAM` structures, KERNAL calls, and `waitvsync()`.
- **IRQ hooks** must be plain machine-language routines tagged `.INTERRUPTOR`.
- **BLK5 heap:** `_heapadd((void*)0xA000, 0x2000)`.
- **Oscar64** is an alternative C compiler (used by Baguel).

### 8.2 C performance rules

1. **Compile with `-Osir`**, and use **`-Cl`** (static locals) to avoid cc65's slow software stack. In ilmenit's "CC65-Advanced-Optimizations" benchmark (cc65 2.18), the compiler-options step alone gave a 34% speedup (392 ticks), and after all ten optimization steps the benchmark ran in 34 ticks.
2. **Use `unsigned char` wherever the value fits.** Promotion to int "lowers performance". Avoid 16-bit arithmetic, multiplication, division and general pointer arithmetic in hot code.
3. **Pass globals rather than parameters.** Parameters still go through the C stack, even with `-Cl`.
4. **Use `register` variables selectively.** cc65 places them in zero page (6 bytes), but saving and restoring a 2-byte register variable can cost **about 70 cycles**. Use them only for pointers or induction variables that are hit repeatedly inside a substantial loop. Blanket use can make code slower.
5. **Write fixed-address pokes so they compile to a single `STA abs`**, using `*(unsigned char*)0x900F = x;`, `volatile` macros, or the `VIC` struct.
6. **Index fixed tables instead of computing addresses.** Use direct pointers to screen and character RAM. Avoid repeatedly dereferencing nested pointers in inner loops.
7. **Keep `printf`, `conio` scrolling and TGI out of inner loops.**
8. **Plan memory with a custom linker config** (§8.4).

Example of thin, direct hardware access:

```c
#include <vic20.h>

#define VIC_VOL_AUX (*(volatile unsigned char*)0x900e)
#define VIC_VOICE2  (*(volatile unsigned char*)0x900b)

static unsigned char aux_shadow;          /* aux colour << 4 */

static void set_volume(unsigned char v)  { VIC_VOL_AUX = aux_shadow | (v & 0x0f); }
void tone(unsigned char pitch)           { VIC_VOICE2 = pitch; }
```

### 8.3 Assembly interfaces from C

- **Use C to orchestrate and assembly for the kernels.** C decides what to draw; assembly does the byte-level work.
- **`__fastcall__`** passes the rightmost argument in A/X (and pseudo-registers) instead of pushing it onto the C stack. It suits blitters, decompressors, joystick scanners, music ticks and raster setup:

```c
void __fastcall__ draw_sprite(const unsigned char* sprite,
                              unsigned char x, unsigned char y);
```

  The assembly side should move the arguments into its own zero-page scratch locations at once and enter a specialized loop.
- **Use separate `.s` files (ca65) for substantial routines.** They give direct control of segments, zero-page allocation, labels and conditional assembly. Keep **inline assembly** for a few register operations, `SEI/CLI`, a short delay, or a specific instruction the compiler won't produce.
- **Recommended split for sound:** an assembly player hooked in as an `.INTERRUPTOR`, with C only setting "play effect N" flags. A per-frame C music driver costs a noticeable share of the frame and adds jitter.
- **Sprites:** put the blitter, raster handler and music player in `.s` files, or link VIC-SSS (a C wrapper exists).

### 8.4 Custom linker layouts (expanded targets)

Expanded C programs should almost always use a custom linker config:

- code in BLK1/2/3;
- **`$1000–$1FFF` reserved for screen, colour page-flip and character or bitmap data**;
- large tables, music and level data in BLK5;
- explicit zero-page segments for the assembly kernels, kept clear of the cc65 runtime's `$02–$1B`;
- init-only code in `ONCE`, overlaid by runtime buffers.

### 8.5 When to use C and when to use assembly

| Task | C (cc65) | Assembly |
|---|---|---|
| Menus, turn-based, puzzle, adventure games | Fully viable | Not needed |
| Game state, collision logic, tables, loaders, decompression control | Viable | Optional |
| Character-cell games (whole-cell movement) at 20–30 fps | Viable with `-Osir -Cl`, `unsigned char`, globals | Better on unexpanded RAM |
| 160×192 monochrome graphics (expanded) | Viable via TGI (not in inner loops) | Faster plotting |
| Software sprites with pixel movement, smooth scrolling | Logic in C | **Required for the blitter** (or VIC-SSS) |
| Raster splits, IRQ-jitter compensation, mid-line writes | Not viable | **Required** |
| Viznut waveforms, digis, speech | Not viable | **Required** |
| Fitting in 3.5 KB (unexpanded) | Hard: runtime and stack overhead | Usually required |

**Why cycle-exact code must be assembly:** a compiler is free to change instruction sequences, temporaries and branch timing between versions and optimization settings. Stable rasters depend on the exact cycle at which the VIA count is read and the exact length of the compensation sequence. At 4 kHz PCM there are only about 256 cycles per sample, and a C call plus indexing plus nibble extraction uses much of that and adds variable latency. C can prepare the data; the replay loop belongs in assembly.

---

## 9. Reference implementations and case studies

| Title / project | Era | What to learn from it | Evidence quality |
|---|---|---|---|
| ***Jetpac*** (Ultimate) | 1983 commercial | **Best-documented commercial engine.** Needs 8K; main program at `$2000–$3FFF`; 23×11 screen of 8×16 RAM characters at `$1000` mapped as a pseudo-framebuffer; XOR drawing with partial erase and redraw; heavy zero-page use; lookup-table dispatch; separate per-tile colour updates; sound as an object type; a VIA IRQ that schedules objects with player priority | Strong: a reverse-engineering repository rebuilds the binary from commented disassembly |
| ***Gridrunner* / *Matrix*** (Minter) | 1982–83 commercial | Pure character games; animation by rewriting characters; raster busy-wait sync; main-loop sound | Good: disassembly with reconstructed labels ("Gridrunner: The Little Black Book") |
| ***Demon Attack*** | 1983 commercial | Per-scanline background-colour changes to colour enemies | Weak: recollection only |
| ***Ultima: Escape from Mt. Drash*** | 1983 commercial | BASIC plus assembly music routines | Mixed: sources disagree on voice count |
| ***Lunar Leeper*** | 1980s commercial | XOR sprites onto background characters | Weak: second-hand forum report |
| ***Robotic Liberation* / *Robotic Warrior*** (viznut/PWP) | 2003 demo | Per-scanline global colours, viznut waveforms, speech synthesis with rasters, trackloader streaming about 17 KB into an unexpanded machine | Strong: author's own write-ups. **PAL; re-time for NTSC** |
| ***Veni vidi Vic!*** | Demo | Separate **NTSC 6560** and PAL releases; 8K; first known VIC-20 trackmo (loads parts from disk while running); **full source released**, including Jonas Hultén's music code | Strong: source available. **A good NTSC reference** |
| ***Realms of Quest 5*** | Homebrew | Stable-raster window | Forum |
| ***Pitfall!* port** (Victragic) | Homebrew | FLI-style raster tricks in a playable game | Forum |
| **VIC-SSS** + *Berzerk MMX*, *Omega Fury*, *Quikman+* | Homebrew | Dual-buffer software sprite library (ca65; cc65 wrapper) | Strong: source on GitHub |
| **Pulse** | Homebrew | 16 sprites, smooth scrolling, unexpanded, Exomizer | Strong: source on GitHub plus author interview |
| **Vixel, LBM8** | Modern | Reusable local-bitmap sprite engines; lookup-table pixel positioning | Library documentation |
| **MINIGRAFIK / MINIPAINT** (Mike) | Modern | Canonical 160×192 layout | Strong: Denial threads |
| **cc65 `vic20-hi.tgi`** | Modern | 160×192 from C; memory arranged around what the VIC can see | Strong: official documentation |
| **VIC-TRACKER, Vicious Tracker, Fisichella** | Modern | Compact replay routines; separate authoring and runtime | Strong |
| **"One hour of digitized music", "Ohne Dich"** | Modern | Streaming 4-bit digis from SD2IEC and from tape | Forum, with code |
| **Late-1980s 3D cube demo (2026 reconstruction)** | Reconstruction | Fixed-point maths, trig, inverse-depth and row-address tables | Modern reconstruction |

**Historical summary:**

- **1980s commercial practice:** programmable characters, multicolour cells, direct VIC register sound, simple software envelopes, intercepting the KERNAL vector, VIA timer IRQs, specialized machine-code drawing.
- **Later demo-scene work:** stable timers, raster splits, trackmo infrastructure, trackers, aggressive timing.
- **Modern homebrew:** reusable sprite libraries, cross-development, reconstructed disassemblies, die-level sound knowledge, hybrid C and assembly toolchains.

Most high-end tricks (stable rasters, viznut waveforms, 160×192 bitmaps, volume-register digis) are **modern discoveries**, not period practice.

---

## 10. Optimization playbook: a prioritized checklist for an existing project

Work through this in order. Each step lists what to check, what to change, and the expected gain.

### Phase 1: Establish ground truth

1. **Identify the memory target and actual layout.** Find where code, screen, colour RAM, the character set, tables, the stack and zero-page variables live. Flag any displayable data outside `$0000–$03FF` / `$1000–$1FFF` (it cannot be shown). Flag hard-coded screen addresses that break under other RAM configurations.
2. **Add border-colour profiling** (§7.5) around the main loop's phases: input, logic, erase, draw, music, flip. Record the raster-line cost of each.
3. **Confirm NTSC timing assumptions.** Search for PAL constants (anything not built from 65 and 261, wrong frame latches) and for `$9004` polling that assumes the counter changes at the start of a line.

### Phase 2: Cheap, safe, high-yield

4. **Replace the KERNAL IRQ path** if the program doesn't need KERNAL keyboard input during play: own handler at `$0314`, acknowledge with `$9124`, exit `$EB15`, direct joystick reads (§7.3). Expected gain: ≈650+ cycles per frame (≈4%) plus less jitter.
5. **Frame-lock the IRQ** (VIA2 T1 = 16,963 on NTSC, started at a known raster line). This gives a stable music tick and a reliable point for page flips.
6. **C code hygiene** (if cc65):
   - `-Osir -Cl`;
   - `unsigned char` everywhere it fits;
   - globals in place of parameters;
   - `register` only on hot loop pointers;
   - direct `STA abs` register pokes;
   - no `printf`, `conio` or TGI in the frame loop;
   - `__fastcall__` on assembly kernels;
   - reduce `__STACKSIZE__` if the stack is oversized.
7. **Dirty-cell rendering.** Redraw only cells that changed. Turn repeated animated tiles into shared character-definition animation (§4.1).
8. **Make `$900E` writes preserve the aux nibble** using a shadow. Fix any sound code that clobbers the aux colour or reads and writes `$900E` mid-frame.

### Phase 3: Structural rendering improvements

9. **Move inner loops to assembly:** sprite blit, erase, character copy, colour updates, plotting. Apply zero-page pointers, `(zp),Y`, unrolling, downward-counting loops, page-aligned tables, lookup tables and self-modifying stores (§4.6).
10. **Pre-shifted sprite data** (4 or 8 phases) if shifting is done at runtime and RAM allows. Use XOR sprites where overlap artefacts are acceptable, to drop background-save buffers.
11. **Flicker-free flips:** use the `$9002` bit 7 screen and colour page flip during vertical blank instead of drawing on the visible screen (§4.3). If RAM is too tight, double-buffer only the working characters.
12. **Memory re-layout** (expanded targets): use a custom linker config with code in BLK1–3, data in BLK5, and `$1000–$1FFF` kept for display. Use a `ONCE` or init overlay. Compress assets with Exomizer.
13. **Unexpanded targets:** consider the `$1C00` wrap for the ROM font, a screen in the `$0200` area to free `$1000–$1FFF`, overlays in the cassette buffer, and Exomizer.

### Phase 4: Scheduling

14. **Spread work across frames:** round-robin enemy updates, player first, lower update rates for distant or minor objects, constant per-frame workload.
15. **Fixed-tick asm music driver** (as an `.INTERRUPTOR` in cc65) with explicit voice priority: effects take soprano or noise and then return it. Note tables should pick the generator with the least tuning error.

### Phase 5: Advanced (only if the design calls for it)

16. **Stable raster splits** for per-band colours or charset switches. Start from Mike's NTSC build or Mäkelä's routine; don't write your own from scratch.
17. **Bitmap mode:** the MINIGRAFIK 160×192 layout and its column-major address formula.
18. **Viznut waveforms** for timbre, reloaded in vertical blank with IRQs off.
19. **Digis:** a timer-driven 4-bit player (≤ about 4 kHz in practice, about 256 cycles per sample) sharing one stable timer with any raster code.

### Things not to do

- Don't put graphics in expansion RAM and expect the VIC to show them.
- Don't use the stock KERNAL 60 Hz timer for raster timing; it drifts.
- Don't write cycle-exact code in C.
- Don't overwrite the aux colour when writing volume.
- Don't stop and restart noise if drums need a consistent timbre.
- Don't trust old VICE builds for waveform tricks, noise, or digi DC levels.
- Don't use `register` on everything in cc65.
- Don't hard-code multicolour `01`/`10` meanings without checking them.

---

## 11. Source discrepancies and how they were resolved

| Topic | Report A | Report B | Resolution |
|---|---|---|---|
| Frequency formula | `f = clock/(127 − X)`, X = 7-bit value | `f = C/(255 − N)`, N = full register | **Equivalent** (N = 128 + X). Both are correct. |
| Double buffering cost | Cheap page flip via `$9002` bit 7 (screen and colour) | "Conventional full-screen double buffering is expensive" | **Both correct.** The screen and colour flip is cheap; double-buffering the character set (2 KB) is expensive. See §4.3. |
| Bitmap feasibility | 160×192 via 20×12 of 8×16 characters (MINIGRAFIK) | A unique 22×23 matrix needs 506 glyphs (> 256) | **Compatible.** Report B states the problem; Report A gives the standard solution. |
| `register` variables | "Use for hot pointers" | Save and restore costs about 70 cycles; use selectively | **Merged:** use them only for pointers or induction variables in substantial loops. |
| Safe volume write | `ORA` with stored aux colour | Read `$900E`, `AND #$F0`, `ORA` | Both work. **A shadow is recommended** (faster, deterministic, survives raster aux changes). |
| Line count | 261 lines | 261 counted; some docs say 262 | **261×65** for timing code; 262 is a nominal video figure. |
| Multicolour `01`/`10` | PRG: `01` = border, `10` = foreground; Mäkelä lists them swapped | Lists the order background, border, foreground, aux (matches the PRG) | **Unresolved in the sources.** Check empirically. |
| *Jetpac* geometry | — | Says "11×23" once and "23 columns × 11 rows" elsewhere | Used **23 columns × 11 rows** (the detailed statement). Confirm against the disassembly. |
| *Ultima: Mt. Drash* voices | Wikipedia "4-voice" vs others "3 voices" | — | Unresolved; it doesn't matter for optimization. |
| Citations | Numbered URLs | Inline citation tokens without resolvable URLs | Report A's URLs are kept in §13. Report B's sources are listed by name. |

---

## 12. Caveats and verification requirements

- **NTSC timing details are still being refined.** The raster-counter phase (37 cycles earlier than the 6561), the partial-line lengths (32/33 cycles) and the mid-line counter change come from forum measurements and 2025–26 emulator development (for example emu198x PR #1671). **Verify cycle-exact NTSC code on a real 6560 or a current cycle-accurate emulator in NTSC mode.** Mäkelä's original stable-raster article was tested on PAL only.
- **PAL-origin code needs re-timing** (*Robotic Liberation*, the "One hour" player, many demos). Prefer *Veni vidi Vic!*'s NTSC release and Mike's NTSC build as NTSC references.
- **Emulator fidelity for audio tricks** (waveform loading, noise LFSR, digi DC level) has improved only recently. Older VICE builds are known to be wrong here.
- **Attribution quality varies.** *Jetpac* (full disassembly) and *Gridrunner* (disassembly with reconstructed labels) are strong. *Demon Attack*, *Lunar Leeper* and *Skyhawk* scrolling rest on recollection and should be treated as indicative only.
- **The multicolour bit mapping conflicts between sources.** Confirm it empirically.
- **The 4 kHz digi ceiling** is one implementation's result, not a theoretical limit.
- **The joystick bit positions** (§7.3) and the KERNAL entry points (`$EABF`, `$EB15`) are standard values; confirm them against the ROM version in use.
- **Suggested test setup:** VICE `xvic` in NTSC mode with the exact memory configuration the project targets (see `xvic -help` for the memory and video-standard options), plus real NTSC hardware for anything cycle-exact.

---

## 13. Sources

### 13.1 Sources with URLs (from Report A)

1. [Commodore VIC20 specific information for cc65](https://cc65.github.io/doc/vic20.html)
2. [6502 Assembly programming for the Vic 20 (ChibiAkumas)](https://www.chibiakumas.com/6502/vic20.php?noui=1)
3. [Visiting The VIC-20 Video (COMPUTE! #36)](https://www.atarimagazines.com/compute/issue36/090_Part_I_Visiting_The_VIC-20_Video.php)
4. [VIC-20 – CPCWiki](https://www.cpcwiki.eu/index.php/VIC-20)
5. [How To Use The 6560 Video Interface Chip (COMPUTE! #26)](https://www.atarimagazines.com/compute/issue26/186_1_HOW_TO_USE_THE_6560_VIDEO_INTERFACE_CHIP.php)
6. [MOS 6560/6561 VIC-I documentation (Marko Mäkelä, VIC-I.txt)](https://www.zimmers.net/anonftp/pub/cbm/documents/chipdata/VIC-I.txt)
7. [Vic20 5k memory – Denial](http://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?t=7166)
8. [emu198x PR #1671: report the NTSC raster line when the 6560 does](https://github.com/emu198x/emu198x/pull/1671)
9. [MOS Technology VIC – DenialWIKI](http://sleepingelephant.com/denial/wiki/index.php/MOS_Technology_VIC)
10. [NTSC interlace detail info needed – Denial](https://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=10125)
11. [Background change at Raster Location – Denial](http://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?t=9679)
12. [VIC-20 – Retro Game Coders Docs](https://docs.retrogamecoders.com/platforms/vic20/)
13. [MOS Technology VIC – Wikipedia](https://en.wikipedia.org/wiki/MOS_Technology_VIC)
14. ["Soft" sprites – Denial](https://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=10090)
15. [A round-up of all known VIC-I display modes – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=7254)
16. [VIC-20 "smooth move" (Sub-Etha Software)](https://subethasoftware.com/2020/05/12/vic-20-smooth-move/)
17. [Super Mario Bros for VIC-20 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=6013)
18. [Pushing the Vic 20 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=590)
19. [Gridrunner: The Little Black Book (mwenge/llamaSource)](https://github.com/mwenge/llamaSource/blob/main/GridrunnerTheLittleBlackBook.md)
20. [Inside View: Jeff Minter (Compute!'s Gazette)](https://www.computesgazette.com/2026/07/24/inside-view-jeff-minter-the-programmer-behind-gridrunner-and-attack-of-the-mutant-camels/)
21. [VIC-SSS: Software Sprite Stack (theflyingape)](https://github.com/theflyingape/vic-sss)
22. [VIC-20 Software Releases of 2010 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=4140&start=5)
23. [Software sprites? – Page 11 – Denial](http://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?t=3252&start=150)
24. [Pulse (SvenMichaelKlose)](https://github.com/SvenMichaelKlose/pulse)
25. [Commodore Free Issue 80 (Pulse interview)](https://www.commodorefree.com/magazine/vol8/issue80.html)
26. [Software sprites? – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=3252)
27. [Let's bring ELITE to the VIC-20 – Page 3 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=10939&start=30)
28. [Using screen memory at location $200 – Denial](https://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=11074)
29. [New Frontiers in VIC-Hires-Graphics, Part 1 – Denial](https://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?t=4518)
30. [Does the Vic really support Hires graphics? – Denial](http://www.sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=5485)
31. [Making stable raster routines (C64 and VIC-20), Marko Mäkelä](https://commodore.software/downloads?catid=550&id=10552%3Amaking-stable-raster-routines&task=download.send)
32. [Making stable raster routines – Codebase64](https://codebase64.net/doku.php?id=interrupts%3Amaking_stable_raster_routines)
33. [Stable rasters on the VIC-20 – Denial](https://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=10739)
34. [Robotic Liberation (viznut)](http://viznut.fi/texts-en/robotic_liberation.html)
35. [The most impressive vic 20 demo? – Denial](http://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?t=8293)
36. [Viznut's waves? – Page 2 – Denial](http://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?p=113632)
37. [cc65 `cfg/vic20-32k.cfg`](https://github.com/cc65/cc65/blob/master/cfg/vic20-32k.cfg)
38. [cc65-devel: Targeting the VIC-20 with RAM expanders](https://sourceforge.net/p/cc65/mailman/cc65-devel/thread/b65b9a43-fe8e-7bda-2f30-c6d251de87c9@hugbox.org/)
39. [CC65-Advanced-Optimizations (ilmenit)](https://github.com/ilmenit/CC65-Advanced-Optimizations)
40. [cc65 coding hints](https://cc65.github.io/doc/coding.html)
41. [cc65 Users Guide](https://cc65.github.io/doc/cc65.html)
42. [C with cc65 – Retro Game Coders Docs](https://docs.retrogamecoders.com/c/cc65/)
43. [Baguel: unexpanded VIC-20 tennis game (MGProduction)](https://github.com/MGProduction/Baguel)
44. [VIC 20 – Battle of the Bits Lyceum](https://battleofthebits.com/lyceum/View/VIC+20)
45. [Fami2Vic (ThePhotoChemist)](https://github.com/ThePhotoChemist/Fami2Vic)
46. [Sound and Music – VIC-20 Programmer's Reference Manual, p. 110](https://www.manualslib.com/manual/1032653/Commodore-Vic-20.html?page=110)
47. [Viznut's waves? – Denial](https://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=10149)
48. [VICMIDI `Docs/waveforms.txt` (LeifBloomquist)](https://github.com/LeifBloomquist/VICMIDI/blob/master/Docs/waveforms.txt)
49. [VICE bug #1125: 6561 noise generator reverse engineered](https://sourceforge.net/p/vice-emu/bugs/1125/)
50. [Noise generator implementation in VICE – Page 3 – Denial](https://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=9330&start=30)
51. [soloud `soloud_vic.h`](https://docs.rs/crate/soloud-sys/latest/source/sys/soloud/include/soloud_vic.h)
52. [Vicious Tracker (rzo42)](https://github.com/rzo42/Vicious-Tracker)
53. [countercomplex: My first twenty years on the demoscene (viznut)](http://viznut.fi/texts-en/my_first_20_demoscene_years.html)
54. [Robotic Liberation – pouët.net NFO](https://www.pouet.net/prod_nfo.php?which=10626)
55. [Robotic Warrior – pouët.net](https://www.pouet.net/prod.php?which=8549)
56. [VIC Sound Generator (COMPUTE! #32)](https://www.atarimagazines.com/compute/issue32/024_1_VIC_SOUND_GENERATOR.php)
57. [VIC-20 demos (viznut)](http://viznut.fi/texts-en/demoscene_vic-20.html)
58. [VIC-20 Trackers? – ChipMusic.org](https://chipmusic.org/forums/topic/19184/vic20-trackers/)
59. [/pub/cbm/vic20/audio/ (zimmers.net)](https://www.zimmers.net/anonftp/pub/cbm/vic20/audio/index.html)
60. [badline PR #493: play the VIC-20's sound from the VIC-I's voices](https://github.com/elektronaut/badline/pull/493)
61. [Wave-player (digi) code for Vic-20 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=2975)
62. [One hour of digitized music for your Vic-20 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=6671)
63. ["Ohne Dich": Play digital audio from tape in real-time – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=7416)
64. [The VIC20 actually has 5 sound channels! – Lemon64](https://www.lemon64.com/forum/viewtopic.php?t=28481)
65. [countercomplex: The development process of a new VIC-20 demo](http://countercomplex.blogspot.com/2008/08/greetings-to-everyone-once-again-as-you.html)
66. [Custom Characters/Screens only at $1000–$1fff? – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=2873)
67. [Interrupts – wedged code – Denial](http://sleepingelephant.com/~sleeping/ipw-web/bulletin/bb/viewtopic.php?t=9956)
68. [New Frontiers in VIC-Hires-Graphics, Part 10 – Page 3 – Denial](http://sleepingelephant.com/ipw-web/bulletin/bb/viewtopic.php?t=4828&start=30)

### 13.2 Sources referenced by Report B (no resolvable URLs in that report)

Report B used inline citation tokens with no URLs. The sources it describes are:

- **Jetpac reverse-engineering repository:** commented disassembly that rebuilds the original binary (renderer, XOR drawing, IRQ scheduling, sound handler).
- **Vixel** and **LBM8:** modern VIC-20 software-sprite / local-bitmap libraries.
- **cc65 documentation:** VIC-20 target page, `vic20-tgi.cfg` / `vic20-hi.tgi`, `__fastcall__`, inline assembler, register-variable cost (~70 cycles), extended-memory driver for `$A000–$BFFF`, sample build files. (Overlaps sources 1, 37, 40, 41 above.)
- **Marko Mäkelä's VIC timing and stable-raster work** (overlaps sources 6, 31, 32).
- **VICE source and documentation:** NTSC 1,022,727 Hz clock, 65-cycle lines, partial-interval handling, memory-block models, corrected noise emulation (overlaps 49, 50).
- **VIC-20 Programmer's Reference Guide:** programmable characters, sound registers, frequency tables.
- **Contemporary VIC books and magazines:** noise-effect examples, raster colour effects, *Demon Attack* recollections.
- **Veni vidi Vic!** release archive (NTSC and PAL versions, full source, Jonas Hultén's music code).
- **VIC-TRACKER** (Daniel Kahlin) documentation.
- **Aleksi Eeben's** VIC-20 music tools (*Loop Arranger*, 4-bit samples).
- **VIC-20 MOD-player project** (the ~4 kHz / 4-bit practical ceiling).
- **2026 reconstruction of a late-1980s VIC-20 3D cube demo** (fixed-point maths and lookup tables).
- **Digitized speech and music archives** for expanded VIC-20s (overlaps 59).
