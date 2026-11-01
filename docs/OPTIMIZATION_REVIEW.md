# Optimization guide review

Reviewed [VIC20_OPTIMIZATION_GUIDE.md](VIC20_OPTIMIZATION_GUIDE.md) against
the native port and its instruction profiles on 2026-11-01. The arcade C core
is unchanged by this pass. Graphics optimizations are checked against the
independent bitmap renderer, and all 25 regression tests and the VICE smoke
check pass.

This document records the earlier guide pass. The subsequent
[maze-flash revision](MAZE_FLASH.md) adds three tests and resolves repeated
rebuilds during flashing; [PERFORMANCE.md](PERFORMANCE.md) has current figures.
The later [bounded-rebuild implementation](BOUNDED_REBUILD.md) completes the
next scheduling step and records its service gain and presentation cost.

## Retained changes

| Guide section | Change | Cost or constraint |
| --- | --- | --- |
| §5, pre-shifted sprites | Eight shifts of two shared normal ghost masks and two frightened masks. Six normal source frames share the two masks. | 640 bytes across BLK5 and BLK1–3, plus address tables. Generic rendering remains for other images and clipping. |
| §6.3, transparent rows | Skip source reads and destination writes for the ghost masks' empty first/last rows. Save those underlays for exact restoration. | Generator assertions protect symmetry, shared frames and empty edges. |
| §4.3, page alignment | Page-align the square and bit-reversal tables. Place reversal data first in BLK5 to avoid wasting a large padding gap. | A small dispatch table moved to main RAM. |
| §6.1, unrolling | Restore two sprite rows per loop iteration. | Small code increase; no extra row-address patching. |
| §7.4, cold functions | Keep the large background-rebuild path separate from the ordinary dirty queue. | Background behavior and tile ordering remain the same. |
| §1–2, worst-case measurement | Add maximum render duration and a six-second forced board-transition sample. | Makes transition stalls visible alongside gameplay averages. |

## Measured effect

Same NTSC CPU-cycle benchmark, before and after the guide pass:

| Sample | Before | After |
| --- | ---: | ---: |
| Normal play | 43.00 FPS | 48.96 FPS |
| Frightened movement | 43.31 FPS | 52.99 FPS |
| Attract chase | 39.29 FPS | 45.26 FPS |
| First intermission | 60.05 FPS | 60.10 FPS |

The original logic clock remains 60.606 Hz. These are sample averages;
gameplay is not yet a sustained 60 FPS. `make performance` writes full
timing reports and profiles to `build/performance/current/`.

## Experiments discarded

- Replacing the three top-level dispatch tables with direct switches did
  not improve the profiles. Replacing all dispatch tables exceeded main RAM
  by about 1.1 KiB. The function-pointer advice is useful to test, but it
  did not give this build a practical win.
- A palette-only background path reduced average rendering work during
  transitions but increased the longest draw gap from about 1.64 to 2.61
  seconds. It also hurt ordinary gameplay throughput. It was removed.

## Further work

At the end of the guide pass, the transition sample exposed full rebuilds
of roughly 787 ms and draw gaps around 1.6 seconds. The later maze-flash
revision removes repeated rebuilds from flashing itself; actual next-board
drawing still stalls separately. The guide's bounded-work approach is the
next substantial change:
process a limited tile batch, yield to input/logic/audio, and finish a hidden
rebuild before presenting it. The dedicated maze-flash path now handles those
palette changes without reconstructing pixels.

The later [bounded implementation](BOUNDED_REBUILD.md) uses progressive drawing
in the visible bitmap. The earlier suggestion of finishing a hidden rebuild
does not fit this memory layout without a renderer redesign.

Combining erase and draw per cell could help further, but the 4×6 logical
tiles do not align with 8×16 display cells. A background bitmap cache would
need 3,136 extra bytes. The guide-pass link had only 159 bytes free across its
two code/data regions; the subsequent flash fix leaves 58 bytes. More extensive
pre-shifting and double-buffering therefore require a memory-layout or renderer
redesign.

Several guide recommendations are already in use: a column-major bitmap,
dirty tile writes, unchanged-actor caching, independent logic/render clocks,
zero-page hot data, assembly IRQ handling, BCD scores and lookup-based
distance arithmetic.

The following changes would conflict with the arcade target: rescheduling
ghost decisions across different ticks, replacing the ROM-backed random
sequence, or replacing the game timer with the VIC raster-rate timer. Beam
racing could address tearing later, but waiting for raster positions does
not by itself increase CPU throughput. The current IRQ uses no decimal-mode
ADC/SBC, so its increment-only clock handler does not require a new CLD for
correctness.
