# Faster background-tile drawing

**Accepted as the standard build, 2026-11-04.** Actual VICE throughput improves
**31.55 → 32.21 completed redraws/s**, about **2.1%**, on the saved route.
Its changes remain included in the current standard, which also includes
[precomputed sprite preparation](POOL_SETUP_OPTIMIZATION.md).

```sh
make run-tile-stamp-fast
```

Press **5**, then **1**, and use the arrow keys. This intermediate version is
`build/tile-stamp-fast/pacman.prg`; compare with `make run-pool-alloc-fast`.
`make run` launches the latest standard, including this change and all later
accepted improvements; see the [README](../README.md) for its current status.

## Measured target and change

The accepted allocator build's profile contains **1,129 background-tile calls**.
The tile routine's own instructions consume **898,324 cycles**, or **4.41%**
of native CPU time; colour helpers are counted separately. Background service
averages **1,723 cycles per redraw**, including dirty-queue handling and callees.

The clean-home copy is already unrolled and still costs 209 exclusive cycles
per fresh pool cell. This experiment leaves it alone and removes repeated work
from the six-row background-tile writer instead. This is a bounded renderer
follow-up under candidate 2, rather than the deferred persistent cache.

`TILE_STAMP_FAST` in `src/bitmap.S` replaces six per-row subroutine calls and
pointer increments with one indexed walk. X selects the three packed source
bytes; Y selects the six destination rows. A patched absolute source operand
keeps that source cursor independent of Y. Indirect indexed destination reads
and stores handle page crossings normally.

The existing nibble-preservation mask is $0F or $F0. `BIT` tests its high bit
to select the same nibble shifts while preserving both A and X. It uses legal
NMOS 6502 instructions. As with the existing sprite kernels, the patched
operand belongs exclusively to main-thread rendering: the timer IRQ preserves
A/X/Y and does not call the renderer. `v_addr` and `v_data` now remain at their
base addresses; their documented scratch contents are not outputs used by the
callers. The two production callers in `rebuild.S` retain the logical offset
in `v_save`, which is preserved.

Tile addressing, palette/class selection, white wall/pellet rules, occupied
cell colours, pool composition/publication, artwork, gameplay and sound retain
their existing behaviour. There are no new tables, writable allocations or
hardware requirements. The original routine remains under the build conditional.

## Results

| Measurement | Previous allocation | Accepted background tiles |
| --- | ---: | ---: |
| Actual VICE redraws/s | 31.55 | **32.21** |
| Actual completed redraws | 617 | **630** |
| Native replay redraws/s | 31.80 | **32.37** |
| Native completed redraws | 633 | **645** |
| Mean complete native refresh, cycles | 16,365.37 | **16,088.46** |
| Native 95th-percentile refresh, cycles | 21,804 | **21,087** |
| Native maximum refresh, cycles | 30,307 | **25,819** |
| Mean background service/native redraw, cycles | 1,722.59 | **1,438.23** |
| Exclusive tile-routine cycles, same 1,129 calls | 898,324 | **736,633** |
| Actual 95th-percentile redraw interval | 47.21 ms | **46.45 ms** |
| Actual maximum redraw interval | 56.02 ms | **55.74 ms** |
| Maximum native input-service gap | 37.07 ms | 37.29 ms |
| Maximum native audio-service gap | 38.67 ms | **37.32 ms** |
| Resident end / free before stack | $7CB3 / 141 bytes | $7CB3 / 141 bytes |
| BLK5 free | 151 bytes | 151 bytes |
| Packed PRG size | 26,702 bytes | **26,701 bytes** |

The tile routine shrinks by one byte; alignment keeps total resident use the
same. The full **704-byte software stack** at $7D40–$7FFF remains reserved.
Hardware stays NTSC with +3K and BLK1/2/3/5 expansion. Native image size remains
33,792 bytes.

The independent kernel comparison executes **17,408 cases per build**: all
1,024 logical tile offsets, then all 256 tile codes × 32 palettes × both nibble
positions. It also exercises high palette bits, the HUD strips, blanking,
nonzero neighbour ink, occupied-cell colour guards and both source/destination
page crossings. A separate pixel model checks every affected byte and adjacent
guards, then the entire home bitmap and its outer guards. Accumulated colour
and wall-bit outputs match the predecessor exactly, as do logical video inputs.

| Identical-input complete tile call | Previous allocation | Accepted background tiles |
| --- | ---: | ---: |
| Mean visible tile, cycles | 901.35 | **758.31** |
| Maximum visible tile, cycles | 1,085 | **942** |
| Mean clipped corner, cycles | 61 | 61 |

All **17,392 visible cases save 143–147 cycles**, about **15.9%** on average.
The sixteen clipped corners are unchanged. Timings mask IRQs, include RTS and
exclude the caller's JSR and host fixture loading. Static annotations are saved
alongside the measured built-kernel results.

The native profile checks all **1,207 active game states** against the shared
fixture and predecessor. Its CPU shares become 46.59% logic/tasks, 50.92%
rendering, 2.33% audio and 0.16% waiting. Faster redraw admission samples
different actor poses and changes render count, so whole-program percentages
and refresh costs are not identical-input kernel measurements.

The slightly larger maximum input gap is a measured tradeoff. These results
are one route's averages, not a fixed 30 Hz display or worst-case guarantee.

## Regression and actual display checks

`make test-tile-stamp-fast` passes:

- 15 original-ROM comparisons and 41 pooled logic/render/colour/font/memory
  checks, including changed backgrounds, maze flashes, overlaps and full banks.
- The 17,408-case tile comparison per build described above.
- Exact effect/song state and arcade/VIC sound-register values on all
  **1,639 logical ticks**. Write timestamps can differ; no PCM comparison or
  listening test is claimed for this graphics-only change.
- 13 host display-classifier checks and smoke through all three intermissions,
  **7,192 logical ticks**, with IRQ vector, boot handoff and stack guard intact.
  Observed software/hardware stack writes reach 30/24 bytes; the full reservation
  remains, and those observations are not worst-case bounds.

The actual accepted capture contains **1,180 consecutive VICE raster frames**.
All **33,792 depacked bytes** match its own native image. It uses the same
logical-tick inputs and capture method as the retained accepted capture, whose
PRG/native images still match the current accepted build exactly. There are no
guest code patches, PC render gates, clock changes or retimed poses.

The accepted build passes **607 settled-picture oracles** and **4,910 synthetic
absent/partial controls**, with zero false absent/partial settled results.
Neither capture contains a fully absent actor among eligible cases:

| Actor | Previous present / partial / excluded | Accepted present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 983 / 17 / 180 | 982 / 17 / 181 |
| Blinky | 882 / 17 / 281 | 886 / 16 / 278 |
| Pinky | 832 / 20 / 328 | 843 / 8 / 329 |
| Inky | 929 / 11 / 240 | 928 / 11 / 241 |
| Clyde | 863 / 14 / 303 | 863 / 13 / 304 |

Partial poses remain. Shared-colour cells, reward expansion, clipping, hidden
actors and insufficient distinct ink remain exclusions. Calibration stays
x=8, y=4 with two output dots per VIC dot; the accepted capture has zero initial binary
pixel mismatches. Settled snapshots independently match recomposed masks.

The [consecutive-frame evidence](../build/tile-stamp-fast/evaluation/trial-vice/evidence.png)
and [comparison preview](../build/tile-stamp-fast/evaluation/comparison.png)
were inspected. The [comparison video](../build/tile-stamp-fast/evaluation/glyph-pool-comparison.mp4)
labels distinct executable hashes, validates its source images and preserves
natural cadence without audio. No perceptible flicker improvement or physical
hardware validation is claimed.

## Reproduction and evidence

```sh
make test-tile-stamp-fast
python3 tools/arcade/profile_game.py --prg build/tile-stamp-fast/pacman.prg --map build/tile-stamp-fast/pacman.map --input tests/fixtures/active-replay.json --output build/tile-stamp-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/tile-stamp-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/tile-stamp-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/tile-stamp-fast/new-vice
```

Run native fixture tools sequentially and use fresh profile/capture directories.
Raw evidence is in `build/tile-stamp-fast/evaluation/`, test logs in
`build/tile-stamp-fast/tests.log`, and smoke in `build/tile-stamp-fast/smoke/`.
The [frozen record](baselines/tile-stamp-fast.json) retains measurements,
identities, source hashes and validation. The
[optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates)
tracks this candidate-2 follow-up as accepted and included in the standard.
The frozen record preserves its pre-promotion status as historical evidence.
The [promotion record](baselines/tile-stamp-promotion.json) identifies the then-default
artifacts and the regression checks run against them. Cache and pacing rewrites
remain deferred.

Promotion verification passed the full `make test` target against the then-default,
including the retained exhaustive audio, ghost, sprite, tunnel and allocator
checks and the new tile benchmark. That default PRG, labels, native image, ELF
and map matched the accepted explicit build byte for byte. The captured
PRG/native identities and measurements above remain tied to that version.
