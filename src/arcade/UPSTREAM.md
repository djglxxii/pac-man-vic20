# Native arcade core provenance

The game routines and memory-map definitions are adapted from Mark Burkley's
MIT-licensed C translation of Pac-Man's Z80 program:

- Repository: https://github.com/mburkley/pacman-c
- Pinned commit: `3277e56d24df82882fd99712464fed6786706e68`
- Original source: https://github.com/mburkley/pacman-c/blob/3277e56d24df82882fd99712464fed6786706e68/pacman.c

The original MIT notices are retained. Function names preserve ROM addresses
so comparisons and investigation can follow the original code. Disassembly
comments and development printf calls were removed from this native copy.
The local ROM set supplies the game data; this C source is compiled to 6502,
not used as a Z80 emulator on the VIC.

The conversion repairs translation errors found by executing the original
ROM: random-counter multiplication, packed-coordinate upward carry, sprite
complements and priority indexing, animation periods and death-state frames,
second fruit release, fruit-history indexing and wraparound, reserve-life
clearing, Elroy's second threshold, BCD scoring and credit subtraction,
queued coin-counter pulses, and high-score comparison. Native decimal ADC/SBC
supplies the original decimal carry behavior on the VIC.

VIC-specific adaptations include the memory map, task-loop entry points,
byte-sized selectors, read-only dispatch tables, equivalent square lookup,
bounded exact frightened-random data, and native display/audio interfaces.
The test suite compares these routines against a separate runner executing
the unmodified original Z80 program.

`tools/arcade/z80.h` is Andre Weissflog's chips Z80 core, retrieved from
https://github.com/floooh/chips/blob/master/chips/z80.h. Its embedded zlib
license is retained. It is used only by the local reference runner.
