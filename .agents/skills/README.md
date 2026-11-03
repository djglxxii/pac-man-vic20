# VIC-20 / 6502 coding-agent skills

Claude Code skills for 6502 assembly and Commodore VIC-20 development (NTSC 6560 focus). Built from the three
research reports in this folder, checked against primary sources (VIC-I.txt, the Programmer's Reference Guide,
the KERNAL ROM images, cc65 and VICE sources), and with code assets tested in VICE 3.7.1.

| Skill | Use for |
|---|---|
| `6502-assembly` | NMOS 6502 code: opcode/cycle tables, idioms, undocumented opcodes, `scripts/cycles.py` cycle counter |
| `vic20-system` | Memory map and RAM configs, startup/SYS stubs, KERNAL/IRQ/VIA, input, toolchains, VICE + headless tests (`scripts/vice-test.sh`), ca65 game template |
| `vic20-graphics` | VIC registers, charsets, multicolour, software sprites, 160×192 bitmap, raster effects, double buffering, scrolling; tested asm modules; `charconv.py`, `vicaddr.py` |
| `vic20-audio` | Voices, note tables (`notetable.py`), tested music + SFX driver, waveforms, digis |
| `vic20-optimization` | Frame budget, profiling, cycle-budget regression test, optimization playbook, case studies |
| `vic20-cc65` | C with cc65: configs, VIC RAM layout, pitfalls, performance rules, C↔asm, tested example |

They load automatically when Claude Code runs in this folder (`.claude/skills/`). To use them in every
project, copy the folders into `~/.claude/skills/`.

Tools assumed by the scripts and tests (optional): Python 3, cc65 (`cl65`), VICE (`xvic`). `charconv.py --png`
needs Pillow.

## Tested assets

| Asset | Test |
|---|---|
| `vic20-system/assets/template-ca65` | Boots, frame IRQ runs, `make test` exits PASS, screenshot checked |
| `vic20-system/assets/vic20-8k-split.cfg` | Program runs from BLK1 on +8K |
| `vic20-audio` driver (`references/music-driver.md`) | 7 register-level checks |
| `vic20-audio` NMI digi player | Rate, aux preservation, auto-stop |
| `vic20-graphics/assets/stable-raster-ntsc.s` | Pixel-identical screenshots across frames (control without the slide differs) |
| `vic20-graphics/assets/bitmap160.s` | Byte-level checks + screenshot on +8K |
| `vic20-graphics/assets/softsprite.s` | Byte-level checks over RAM and ROM chars + screenshot; cost measured |
| `vic20-optimization/assets/cycle-budget.s` | Calibrated: 3 NOPs measure exactly 6 cycles |
| `vic20-cc65/assets/c-example` | `__fastcall__`, `.interruptor`, frame wait, `make test` |

Anything not marked as tested (PAL constants for the stable raster, waveform loader timing, untested snippets)
is flagged as such in the skill text.
