# Precomputed sprite preparation

**Accepted as the standard build, 2026-11-04.** Actual VICE throughput improves
**32.21 → 33.29 completed redraws/s**, about **3.3%**, on the saved route.
The user accepted live play testing and requested promotion.

```sh
make run
```

Press **5**, then **1**, and use the arrow keys. `make run-pool-setup-fast`
launches the same version. The default `build/pacman.prg` is copied from
`build/pool-setup-fast/pacman.prg`. `make run-tile-stamp-fast` preserves the
preceding build for comparison.

## Measurement and selected change

Rebucketing the accepted background-tile profile separates these exclusive
costs per completed native redraw:

| Work | Cycles/redraw | Share of total CPU |
| --- | ---: | ---: |
| Actor pose/palette/source preparation | 2,302.11 | 7.29% |
| Destination-pointer setup | 764.67 | 2.42% |
| Generic shifted composition | 3,439.52 | 10.89% |
| Copying clean home glyphs | 3,234.80 | 10.24% |

Within actor preparation, the packed-class decoder costs 330.38 cycles/redraw;
the region containing source-address arithmetic and draw-path dispatch costs
612.21. Those figures include surrounding instructions, rather than being
entirely removable work. The profile contains 3,352 regular-atlas selections
and 98 special-atlas selections across 645 redraws.

`POOL_SETUP_FAST` replaces the regular-atlas decoder and address calculation
with **64 precomputed two-byte descriptors**. Every artwork frame occupies
twelve bytes and starts on a four-byte boundary. Its pointer's bottom two bits
therefore store the dominant pixel class. The renderer loads the descriptor,
masks those bits off for the source address, and uses them for the original
palette lookup. Two loads replace the repeated two-bit unpacking and
sixteen-bit multiply/add work.

`mkrom.py` generates `build/arcade/sprite_setup.inc` from the same class data
as the original packed table. Ordinary word relocations resolve the addresses
at link time. `src/pool_setup.ld` asserts four-byte artwork alignment and all
64 entries. The original sixteen-byte class table remains available for the
independent actual-display observer; this build explicitly retains it.

Eyes and the right halves of ghost-reward scores retain their separate small
atlases and original address arithmetic. Their preparation moves ahead of the
shared palette lookup, adding five or six cycles in the checked transactions.
Regular frames no longer perform that arithmetic. Destination setup, cell
allocation/copying, drawing kernels, overlap/colour order and finished-cell
publication retain their existing behaviour. No writable storage is added.
The old preparation remains under the build conditional.

## Results

| Measurement | Previous background tiles | Accepted sprite preparation |
| --- | ---: | ---: |
| Actual VICE redraws/s | 32.21 | **33.29** |
| Actual completed redraws | 630 | **651** |
| Native replay redraws/s | 32.37 | **33.39** |
| Native completed redraws | 645 | **665** |
| Mean full native refresh, cycles | 16,088.46 | **15,579.88** |
| Native 95th-percentile refresh, cycles | 21,087 | **20,747** |
| Native maximum refresh, cycles | 25,819 | 26,119 |
| Actor preparation exclusive cycles/native redraw | 2,302.11 | **1,832.84** |
| Actual 95th-percentile redraw interval | 46.45 ms | **45.65 ms** |
| Actual maximum redraw interval | 55.74 ms | 61.28 ms |
| Maximum native input-service gap | 37.29 ms | **36.77 ms** |
| Maximum native audio-service gap | 37.32 ms | **35.61 ms** |
| Resident end / free before full stack | $7CB3 / 141 bytes | $7CB3 / 141 bytes |
| BLK5 free | 151 bytes | **23 bytes** |
| Packed PRG bytes | 26,701 | 26,814 |

Actor preparation costs about **20.4% less per native redraw** on this route.
Different redraw cadences sample different poses, so whole-program figures
include workload differences. The identical-scene benchmark below isolates
behaviour and transaction costs on equal inputs.

The preparation code shrinks by **nine bytes**, while alignment leaves overall
resident use unchanged. The descriptors consume **128 additional read-only
bytes in BLK5**. The full **704-byte software stack** at $7D40–$7FFF remains
reserved. Hardware stays NTSC with +3K and BLK1/2/3/5 expansion; the native
image remains 33,792 bytes. There is no new hardware requirement.

The larger maximum actual redraw gap and maximum native refresh are measured
tradeoffs. The average improvement does not establish a fixed refresh rate,
worst-case deadline or perceptible flicker reduction.

## Identical-scene and regression checks

`tools/arcade/pool_setup_timing.py` checks **8,768 complete sprite transactions
per build** with the existing independent pixel/colour model. It covers every
frame and palette, all flips and horizontal shifts, both tunnel edges,
destination-row offsets 0/4/5/15, bottom-of-display addressing, invisible and
clipped actors, special eyes/rewards and both alternating banks/epoch wraps.
Every scene also checks retained actor inputs and restored backgrounds/colours.
Linked descriptor addresses/classes are checked separately against the source
atlas layout and original packed class data.

| Identical-input complete transaction | Previous build | Accepted build |
| --- | ---: | ---: |
| Mean over all 8,768 cases, cycles | 2,642.05 | **2,575.77** |
| Maximum over all cases, cycles | 6,288 | **6,187** |
| Mean exclusive actor preparation per scene, cycles | 896.33 | **830.23** |

All **7,372 regular-atlas cases save 18–123 cycles**, averaging 79.09. The 248
eyes cases cost 5–6 extra cycles; the 124 right-score cases cost 5 extra.
The 64 zero-palette cases and 960 fully clipped cases are unchanged.
Destination-setup exclusive cycles match exactly. Output digests match.
These timings mask IRQs, include RTS and exclude the caller's JSR and host
fixture loading. Static cycle annotations are saved alongside the measurements.

`make test-pool-setup-fast` passes:

- 15 original-ROM comparisons and 41 pooled logic/render/colour/font/memory
  checks, including overlap, full banks, allocation failure and epoch wraps.
- The 8,768-case comparison per build described above.
- Exact effect/song state and arcade/VIC register values on all **1,639 ticks**.
- 13 host display-classifier checks and smoke through all three intermissions,
  **7,182 logical ticks**, with boot handoff, IRQ vector and stack guard intact.

The native active replay matches all **1,207 game states** against both the
shared fixture and previous build. Native CPU shares become 46.64% logic/tasks,
50.87% rendering, 2.33% VIC audio translation and 0.16% waiting. Observed
software/hardware stack writes reach 30/24 bytes; these are observations,
rather than worst-case bounds. Sound write timestamps may differ; no PCM
comparison or physical-hardware validation is claimed.

## Actual display validation

Both captures contain **1,180 consecutive raster frames** over the same
19.557-second window, using the same input per logical tick. All **33,792
depacked bytes** match each executable's native image. The previous capture
is reused only after verifying its PRG/native hashes against the preserved
background-tile build. There are no guest patches, render gates, changed clocks or retimed
poses.

The accepted build passes **628 settled-picture checks** and **5,090 synthetic
absent/partial controls**, with zero false absent/partial results on settled
images. Neither capture contains a fully absent actor among eligible cases:

| Actor | Previous present / partial / excluded | Accepted present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 982 / 17 / 181 | 990 / 17 / 173 |
| Blinky | 886 / 16 / 278 | 889 / 10 / 281 |
| Pinky | 843 / 8 / 329 | 838 / 13 / 329 |
| Inky | 928 / 11 / 241 | 923 / 18 / 239 |
| Clyde | 863 / 13 / 304 | 869 / 10 / 301 |

Partial poses remain and vary in both directions. Shared-colour cells, reward
expansion, clipping, hidden actors and insufficient distinct ink remain
exclusions. Alignment remains x=8, y=4 at two output dots per VIC dot, with
zero initial alignment mismatches and 3,576 at the next distinct alignment.

The [consecutive-frame evidence](../build/pool-setup-fast/evaluation/trial-vice/evidence.png)
and [comparison preview](../build/pool-setup-fast/evaluation/comparison.png)
were inspected. The [comparison video](../build/pool-setup-fast/evaluation/glyph-pool-comparison.mp4)
labels executable hashes and preserves natural cadence without audio.

## Reproduction and decision

```sh
make test-pool-setup-fast
python3 tools/arcade/profile_game.py --prg build/pool-setup-fast/pacman.prg --map build/pool-setup-fast/pacman.map --input tests/fixtures/active-replay.json --output build/pool-setup-fast/new-cpu
python3 tools/arcade/pool_profile.py --capture build/pool-setup-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-setup-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/pool-setup-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/pool-setup-fast/new-vice
```

Run native fixture tools sequentially and use fresh capture/profile directories.
Raw results are in `build/pool-setup-fast/evaluation/`, tests in
`build/pool-setup-fast/tests.log`, and smoke in `build/pool-setup-fast/smoke/`.
The [frozen record](baselines/pool-setup-fast.json) retains measurements,
binary/source identities and checks. Early development results, including the
discarded byte-relocation attempt and missing-observer-table capture, are
separate from the final executable's evidence.

This candidate-2 improvement is accepted and included in the standard in the
[optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates).
`make run-pool-setup-fast` preserves this intermediate version; `make run`
launches the latest standard described in the [README](../README.md). Persistent
caching and pacing changes remain deferred. The frozen record preserves its
pre-promotion status as historical evidence; the
[promotion record](baselines/pool-setup-promotion.json) identifies that historical
default and its regression checks.

Promotion verification passes the full `make test` target against the default:
86 unit checks, the retained exhaustive audio/ghost/allocator/tile/sprite
comparisons, the new 8,768-scene preparation comparison per build, exact sound
replay and all three intermissions. The default PRG, labels, native image,
ELF and map match the accepted explicit build byte for byte. Its measured
PRG/native/label identities are unchanged, so the captured results above
apply to the promoted default without another runtime change.

The older tile benchmark assumed that source-page-crossing cases were the
same in both executables. The new table relocates the artwork, making that
classification address-dependent. Promotion updates the benchmark to retain
each build's crossing groups and report baseline-only/trial-only crossings
separately. Identical fixture inputs, destination groups, per-case independent
pixels/guards and complete output digests remain checked. All 17,408 cases
per build pass; no game code changed during promotion.
