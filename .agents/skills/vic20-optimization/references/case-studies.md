# VIC-20 Case Studies: What Real Programs Did

| Title | Era | Technique | Lesson | Evidence |
|---|---|---|---|---|
| ***Jetpac*** (Ultimate) | 1983, 8K | Main program at `$2000–$3FFF`; 23 × 11 screen of 8×16 RAM characters at `$1000` used as a pseudo-framebuffer; XOR drawing with partial erase/redraw (only the parts no longer covered); heavy zero-page use; lookup-table dispatch; per-tile colour updates; sound handled as another object type with cheap handlers; VIA IRQ schedules objects with the player first | The best-documented commercial engine. Code out of VIC RAM, XOR to avoid background buffers, prioritise the player under load | Strong: reverse-engineering repo rebuilds the binary from commented disassembly |
| ***Gridrunner*** / ***Matrix*** (Jeff Minter) | 1982–83, unexpanded | Entirely character-based (every object one char); animation by rewriting characters; Matrix rolls its grid with `ROL` on character bytes; raster busy-wait sync (`LDA $9004 / CMP #$7F / BNE`); sound called from the main loop | Character-cell games run fast and fit in 3.5 KB (Gridrunner is exactly 3,585 bytes incl. load address) | Good: disassembly with reconstructed labels ("Gridrunner: The Little Black Book") |
| ***Pulse*** (Sven Michael Klose) | Modern, unexpanded | Horizontally smooth-scrolling shooter, 16 double-buffered software sprites in 48 characters; reuses the last char when the pool runs out (visible glitch); doesn't wait for retrace; dead sprites become background stars (constant frame time); Exomizer | Pool size is a hard limit; keep workload constant; compression makes unexpanded games feasible | Strong: source on GitHub + author interview |
| **VIC-SSS** (Robert Hurst) | Modern, 8K+ | ca65 software sprite stack: dual video buffers, raster-timed flips, XOR ghost sprites, collision detection; gives most of the internal 4 KB to the playfield; cc65 wrapper | Reuse a proven engine instead of writing one; code in expansion RAM | Strong: source on GitHub; used by *Berzerk MMX*, *Omega Fury*, *Quikman+* |
| ***Robotic Liberation*** / ***Robotic Warrior*** (viznut / PWP) | 2003, unexpanded, **PAL** | Per-scanline global colours, viznut waveforms, speech synthesis alongside rasters, trackloader streaming ~17 KB of content into an unexpanded machine ("loader-linking") | The ceiling of the hardware. Needs unified timing design; PAL constants need re-timing for NTSC | Strong: author write-ups |
| ***Veni vidi Vic!*** | Demo, 8K | Separate **NTSC** and PAL releases; first known VIC-20 trackmo; full source released incl. Jonas Hultén's music code | **A good NTSC reference** for raster and music code | Strong: source available |
| **MINIGRAFIK / MINIPAINT** (Mike) | Modern | Canonical 160×192 layout | Use it rather than inventing a bitmap layout | Strong: Denial threads |
| **cc65 `vic20-hi.tgi`** | Modern | 160×192 from C, memory arranged around VIC-visible RAM | C programs can do bitmap graphics on 8K+ | Strong: official docs |
| **Elite port analysis** (Denial) | Modern | Clear screen → draw → wait VBL → flip beats erasing line by line | Page flipping removes flicker for full redraws | Forum |
| ***Realms of Quest 5***, ***Pitfall!*** port | Homebrew | Stable-raster window; FLI-style raster tricks in a playable game | Raster tricks are viable in games if budgeted | Forum |
| **Baguel** (Oscar64 C) | Modern, unexpanded | Software sprites from C; nearly ran out of space even with horizontal-only movement | C on an unexpanded VIC is very tight | Source on GitHub |
| **VIC-TRACKER** (Daniel Kahlin) | Modern | Editor needs 16K; compressor emits compact replay that runs unexpanded | Author on a big machine, ship a small replay | Strong |
| **Late-1980s 3D cube demo** (2026 reconstruction) | Reconstruction | Fixed-point math, assembler-generated trig tables, inverse-depth tables, row-address tables | Tables instead of multiply/divide | Reconstruction |
| ***Demon Attack***, ***Lunar Leeper*** | 1980s | Per-scanline background colours (recollection); XOR sprites onto background chars (second-hand) | Indicative only | Weak |

## Historical summary

- **1980s commercial practice:** programmable characters, multicolour cells, direct register sound, simple
  software envelopes, KERNAL vector interception, VIA timer IRQs, specialized machine-code drawing.
- **Demo scene (2000s):** stable timers, raster splits, trackmos, trackers, waveform tricks, aggressive timing.
- **Modern homebrew:** reusable sprite libraries, cross-development (cc65, VICE), reconstructed disassemblies,
  hybrid C + assembly.

Most high-end tricks (stable rasters, viznut waveforms, 160×192 bitmaps, volume-register digis) are **modern
discoveries**, not period practice. Don't claim a 1983 game "used" them without evidence.
