# VIC-20 Toolchain: Assemblers, cc65, VICE, Exomizer

Command lines here were tested with cc65 V2.19 (git), ACME 0.96.4, 64tass 1.60, DASM 2.20.16, exomizer
3.1.3 and VICE 3.7.1.

## cc65 / ca65 (recommended for mixed C + asm projects)

Linker configs shipped with cc65 (`cfg/`):

| Config | For | Load / code start | Top |
|---|---|---|---|
| `vic20.cfg` (default for `-t vic20`) | C, unexpanded | `$1001`, SYS stub, main `$100D` | `$1E00` − stack (`$100`) |
| `vic20-32k.cfg` | C, expanded | `$1201`, main `$120D` | `$8000` − stack (`$800`) |
| `vic20-tgi.cfg` | C + `vic20-hi.tgi` (160×192) | `$1201`, main `$2000` | `$4000` |
| `vic20-asm.cfg` | assembly, unexpanded | `$1001` | `$1E00` |
| `vic20-asm-3k.cfg` | assembly, +3K | `$0401` | `$1E00` |
| `vic20-asm-32k.cfg` | assembly, +8K and up | `$1201` | `$8000` |

```sh
# pure assembly, unexpanded, with a BASIC "SYS4109" stub (-u __EXEHDR__ pulls it in)
cl65 -t vic20 -C vic20-asm.cfg     -u __EXEHDR__ -g -Ln game.lbl -o game.prg game.s
# +3K (SYS1037) / +8K or more (SYS4621)
cl65 -t vic20 -C vic20-asm-3k.cfg  -u __EXEHDR__ -o game.prg game.s
cl65 -t vic20 -C vic20-asm-32k.cfg -u __EXEHDR__ -o game.prg game.s
# Without -u __EXEHDR__ you get a bare PRG (no BASIC line) loading at the start address; -S <addr> moves it.
# C programs
cl65 -t vic20 -O -o prog.prg main.c
cl65 -t vic20 -C vic20-32k.cfg -Osir -Cl -o prog.prg main.c helpers.s
```

- Code goes in `.segment "CODE"` (or `.code`). Zero-page variables in `.zeropage` (the asm configs give you
  `$02–$1B`). Variables in `.bss`, constants in `.rodata`.
- `-g` plus `-Ln file.lbl` writes a VICE label file (`al 00100D .start`) including local labels.
- The asm configs don't know about your custom charset or screen placement. Guard them yourself, e.g.
  `.assert __BSS_RUN__+__BSS_SIZE__ <= $1C00, lderror, "code hits charset"` (import the two symbols).
- `vic20-asm-32k.cfg` assumes RAM to `$7FFF`. On a +8K-only machine (top `$3FFF`) the linker won't catch an
  overflow. Write your own cfg for the exact target (copy one and edit `MEMORY`).
- C programs that need `$1000–$1FFF` for graphics on 8K+: link with `vic20-tgi.cfg` (start-up code relocates
  the program to `$2000`; tested). Raise `__HIMEM__` (`-Wl -D,__HIMEM__=0x8000`) for +24K.
- The cc65 runtime and C specifics are covered by the `vic20-cc65` skill.

Custom config for expanded machines: `assets/vic20-8k-split.cfg` (tested on +8K in VICE). It puts the BASIC
stub plus a `JMP` (segment `STARTUP`) at `$1201`, pads the file to `$2000`, and puts `CODE/RODATA/DATA/BSS`
in BLK1. A file-less `VICDATA` segment reserves `$1000–$1FFF` labels (charset, screens) without storing bytes
in the PRG. Change `MAIN` to `size = $6000` for +24K.

```asm
.segment "STARTUP"
        jmp main                ; SYS 4621 lands here
.segment "VICDATA"
charset: .res 2048              ; address reserved at $1000, filled at run time
.code
main:   ...
```

```sh
cl65 -t vic20 -C vic20-8k-split.cfg -u __EXEHDR__ -m game.map -o game.prg game.s
```

Padding `$1201–$1FFF` costs 3.5 KB of load time. Alternatives are a bare PRG loaded at `$2000` with
`LOAD"GAME",8,1` + `SYS 8192`, or Exomizer `sfx`, which unpacks anywhere.

## BASIC stub in other assemblers

Stub arithmetic: link (2) + line number (2) + `$9E` SYS token (1) + 4 digits + `$00` (1) + end-of-program
`$0000` (2) = 12 bytes, so code starts at load+12: `$100D` = 4109, `$040D` = 1037, `$120D` = 4621. A space
in `SYS 4109` shifts everything by one.

ACME (`acme game.asm`):

```asm
!to "game.prg", cbm
* = $1001                       ; $1201 for +8K
        !word next, 10
        !byte $9e
        !text "4109"            ; "4621" for +8K
        !byte 0
next    !word 0
start   ; code here
!if start != 4109 { !error "SYS address mismatch" }
```

64tass (`64tass --cbm-prg -o game.prg game.asm`):

```asm
        * = $1001
        .word next, 10
        .byte $9e
        .text format("%d", start)
        .byte 0
next    .word 0
start   ; code here
```

DASM (`dasm game.asm -ogame.prg`; the default format writes the load address):

```asm
        processor 6502
        org $1001
        .word next, 10
        .byte $9e, [start]d, 0  ; [expr]d emits decimal digits
next    .word 0
start   ; code here
```

## VICE (xvic)

```sh
xvic -model vic20ntsc -memory none -autostart game.prg      # unexpanded NTSC
xvic -model vic20ntsc -memory 8k   -autostart game.prg      # +8K (BLK1)
xvic -model vic20ntsc -memory all  -autostart game.prg      # +3K +24K +BLK5
xvic -model vic20pal  -memory 3k   -autostart game.prg
xvic -cartA game-a000.bin                                    # 8K cartridge image at $A000
xvic -moncommands game.lbl -autostart game.prg               # load labels into the monitor
```

- `-model vic20ntsc|vic20pal` switches the whole machine (use it rather than `-ntsc`/`-pal`, which only
  change the video sync).
- `-memory`: `none`, `3k` (BLK0), `8k` (BLK1), `16k` (BLK1–2), `24k` (BLK1–3), `all`, or a block list such as
  `1,2,3,5` / `0,1`. There is no `32k` keyword; use `all` or `24k,5`.
- Cartridges: `-cart2`/`-cart4`/`-cart6` (ROM at `$2000/$4000/$6000`), `-cartA` (`$A000`), `-cartB` (`$B000`),
  `-cartgeneric`, `-cartfe` (Final Expansion), `-cartmega`, `-ultimem`.
- Speed: `-warp`. Remote control: `-remotemonitor` (text, port 6510), `-binarymonitor` (port 6502).

### Headless automated tests (use these to verify your code!)

```sh
xvic -default -model vic20ntsc -memory none -console -sounddev dummy \
     -debugcart -limitcycles 30000000 -exitscreenshot shot.png -autostart test.prg
echo $?
```

- `-debugcart`: **writing a byte to `$910F` exits VICE with that byte as the exit status**. Write 0 for pass and a
  check number for failure.
- `-limitcycles N`: quit after N cycles (exit status 1). Booting and autostarting takes about 6 M cycles.
  One NTSC frame is 16,965 cycles.
- `-exitscreenshot file.png` saves the final screen (view it to check graphics output).
- `scripts/vice-test.sh` wraps all of this: `vice-test.sh [--mem 8k] [--pal] [--shot out.png] test.prg`.

Test-harness pattern: a small program that calls the routine under test, checks results in RAM or registers
(in VICE the sound registers `$900A–$900E` read back what was written), and writes 0 / a failure code to `$910F`. Use
memory counters for harness loops, because the code under test may clobber X/Y.

### VICE monitor essentials (Alt-H / `-moncommands`)

| Command | Meaning |
|---|---|
| `break [exec\|load\|store] addr [if cond]` | Breakpoint / watchpoint (`watch` for memory) |
| `m 1000 10ff` / `d 100d` | Memory dump / disassemble |
| `r` / `r A=$00` | Show / set registers |
| `z` / `n` / `ret` | Step into / step over / run to RTS |
| `g addr` / `x` | Go / exit monitor |
| `chis` | CPU history (what just executed: invaluable after a crash) |
| `ll "game.lbl"` | Load labels (ca65 `-Ln` output or ACME labels) |
| `l "file" 0 addr` | Load a host file into memory |
| `scrsh "f.png" 2` | Screenshot |

## Exomizer (compression)

| `-t` | Target |
|---|---|
| 20 | VIC-20 unexpanded (`$1001`) |
| 23 | VIC-20 +3K (`$0401`) |
| 52 | VIC-20 +8K…+32K (`$1201`) |
| 55 | VIC-20 +3K +32K |

```sh
exomizer sfx sys -t20 -o game-packed.prg game.prg       # self-extracting, jumps to the stub's SYS address
exomizer sfx sys -t52 -o game-packed.prg game.prg
exomizer sfx 0x100d -t20 -n -o out.prg game.prg         # explicit start address, -n = no border flashing
exomizer mem -l none -o level1.exo level1.bin           # raw stream; decrunch at run time with exodecrunch.s
```

`exomizer mem` + the bundled 6502 decruncher is the usual way to keep levels/graphics compressed in
expansion RAM and unpack them into `$1000–$1FFF` when needed.

## Other utilities

```sh
petcat -w2 -l 1001 -o prog.prg -- prog.bas      # tokenize BASIC (default load $0801 is C64! use -l 1001 / 1201)
petcat -2 -- prog.prg                           # list a BASIC PRG
c1541 -format "mygame,01" d64 game.d64 -write game.prg "game" -list
```

## Other toolchains

- **llvm-mos** (`mos-vic20-clang`): modern C/C++ compiler for 6502, with a VIC-20 target.
- **Oscar64**: optimizing C compiler with VIC-20 support (used by the Baguel tennis game).
- **xa65**: simple assembler (`xa -o game.prg game.a65`, load address via `.word $1001` at `*=$0fff`).
- **KickAssembler**: C64-oriented but usable with a hand-written stub.

## Resources

- cc65 VIC-20 docs: https://cc65.github.io/doc/vic20.html · configs: https://github.com/cc65/cc65/tree/master/cfg
- VICE manual: https://vice-emu.sourceforge.io/vice_toc.html
- Denial (VIC-20 forum + wiki): https://www.sleepingelephant.com/denial/
- Zimmers VIC-20 archive (ROMs, docs, VIC-I.txt): https://www.zimmers.net/anonftp/pub/cbm/vic20/
- VIC-SSS software sprite stack: https://github.com/theflyingape/vic-sss
- Pulse (smooth-scrolling shooter, source): https://github.com/SvenMichaelKlose/pulse
- Exomizer: https://bitbucket.org/magli143/exomizer
