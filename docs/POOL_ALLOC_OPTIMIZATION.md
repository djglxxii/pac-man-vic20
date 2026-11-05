# Cheaper glyph-pool cell allocation

**Accepted, 2026-11-04; included in the standard build.** This intermediate
version is retained; see the [README](../README.md) for the latest default.
This intermediate build's actual VICE throughput improves
**30.78 → 31.55 completed redraws/s**, about **2.5%**, on the saved route.

```sh
make run-pool-alloc-fast
```

Press **5**, **1**, then use the arrow keys. Compare with `make run-ghost-update-fast`.
`make run` launches the latest standard, which includes this allocation change
and all later accepted improvements.

## Measurement and selected change

Rebucketing the accepted ghost-update profile identifies these exclusive
costs per completed native redraw:

| Work | Cycles/redraw | Share of total CPU |
| --- | ---: | ---: |
| Generic shifted stamping | 3,438.28 | 10.40% |
| Copying clean home glyphs | 3,241.88 | 9.81% |
| Cell lookup/allocation, excluding copy | 2,459.41 | 7.44% |
| Actor pose/palette/source setup | 2,302.45 | 6.96% |
| Restore/control/publication | 1,555.99 | 4.71% |

The profile contains 9,987 allocator calls, of which 9,555 allocate a fresh
cell and 432 find a cell already prepared for another actor. The sixteen-byte
background copy is already unrolled and costs 209 exclusive cycles per fresh
cell, including its final jump. This experiment leaves that copy unchanged.

The old fresh-cell path converts a relative slot to an absolute bank index,
reloads/increments the count, then subtracts the bank offset to recover the
relative slot for its lookup nibbles. `POOL_ALLOC_FAST` in `src/glyph_pool.S`
instead keeps the cell in Y and the relative slot in X, writes the same lookup
nibbles, then adds the bank offset once for the cell/colour lists. It also avoids
saving and reloading the cell through `v_col`.

`INC pool_count,X` increments ordinary RAM before X becomes the relative slot.
The NMOS 6502's intermediate write is safe here: this is neither I/O nor
IRQ-owned state. The clock IRQ only acknowledges its timer and increments its
tick byte while preserving A/X/Y. The routine still checks capacity before
incrementing and still checks existing-cell hits before capacity.

This is one allocator replacement. Pool sizes, both banks, source masks,
overlap/colour order, clean backgrounds, finished-cell publication, clipping,
epoch clearing and the arcade clock retain their existing behaviour. It adds
no writable storage or lookup table and uses legal NMOS 6502 instructions.

## Results

| Measurement | Previous ghost update | Accepted cell allocation |
| --- | ---: | ---: |
| Actual VICE redraws/s | 30.78 | **31.55** |
| Actual completed redraws | 602 | **617** |
| Native replay redraws/s | 30.94 | **31.80** |
| Native completed redraws | 616 | **633** |
| Mean full native refresh, cycles | 16,814.12 | **16,365.37** |
| Native 95th-percentile refresh, cycles | 22,960 | **21,804** |
| Native maximum refresh, cycles | 28,783 | 30,307 |
| Cell bookkeeping exclusive cycles/native redraw | 2,459.41 | **2,078.81** |
| Actual 95th-percentile redraw interval | 48.65 ms | **47.21 ms** |
| Actual maximum redraw interval | 63.43 ms | **56.02 ms** |
| Maximum native input-service gap | 41.72 ms | **37.07 ms** |
| Maximum native audio-service gap | 36.85 ms | 38.67 ms |
| Resident end / free before full stack | $7CD3 / 109 bytes | $7CB3 / **141 bytes** |
| BLK5 free | 151 bytes | 151 bytes |
| Packed PRG size | 26,717 bytes | 26,702 bytes |

The allocator code shrinks by **16 bytes**; alignment recovers **32 resident
bytes**. The full **704-byte software stack**, NTSC video, +3K and BLK1/2/3/5
expansion remain intact. The native image remains 33,792 bytes.

The independent allocator benchmark executes 392 fresh allocations and 392
existing-cell hits per PRG, covering all 196 homes, both banks, slot/page
boundaries and epoch wraps. Home bytes and destination addresses match the
independent expected layout; restoration returns every home matrix code.

| Identical-input complete allocator call | Previous ghost update | Accepted cell allocation |
| --- | ---: | ---: |
| Mean fresh allocation, cycles | 378.41 | **354.25** |
| Maximum fresh allocation, cycles | 379 | **355** |
| Mean existing-cell hit, cycles | 119.08 | **116.08** |

Every fresh case saves **24–25 cycles**, about **6.4%** of the complete call;
every hit saves **3 cycles**. Calls mask IRQs, include RTS and exclude the
caller's JSR and host fixture loading. Address/page crossings contribute to
the one-cycle variation. Static cycle annotations are also saved, but the
actual built kernels provide these measurements.

Faster redraws sample different poses and backgrounds. Per-redraw profile
changes therefore include workload and placement effects; they are not all
an identical-input saving. Native CPU shares become 46.63% logic/tasks,
50.88% rendering, 2.33% audio and 0.16% waiting.

The larger maximum native refresh and audio gap are measured tradeoffs,
despite the improved actual redraw intervals. This is one route's average,
not a fixed 30 Hz display or a worst-case deadline guarantee.

## Equivalence and actual display checks

`make test-pool-alloc-fast` passes:

- 15 original-ROM comparisons and 41 pooled logic/render/colour/font/memory
  checks, including all shifts/flips, overlaps, teleports and epoch wraps.
- A new full-bank boundary test: all 24 existing cells remain reusable and
  accept colour changes; a new 25th cell returns the clipping sink without
  changing counts, maps, glyphs or lists. This also passes on the predecessor.
- The 392-case allocator comparison per build described above.
- Exact effect/song state and arcade/VIC sound-register values on all
  **1,639 logical ticks**. Write timestamps may differ; no PCM comparison is claimed.
- 13 host display-classifier checks and smoke through all three intermissions,
  **7,183 logical ticks**, with IRQ vector, boot handoff and stack guard intact.

The native replay verifies all **1,207 active game states** against the shared
fixture. Observed software/hardware stack writes reach 30/24 bytes, without
reducing the reservation; these observations are not worst-case bounds.

The actual accepted capture contains **1,180 consecutive raster frames**, with
all **33,792 depacked bytes** matching its own native image. It uses the same
logical-tick inputs as the accepted ghost-update capture reused for comparison.
The captured predecessor PRG matches the retained ghost-update build byte for byte.
There are no guest code patches, PC render gates, clock changes or retimed poses.

The accepted build passes **595 settled-picture oracles** and **4,828 synthetic
absent/partial controls**, with zero false settled absent/partial results.
Neither capture contains a fully absent actor among eligible cases:

| Actor | Previous present / partial / excluded | Accepted present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 989 / 14 / 177 | 983 / 17 / 180 |
| Blinky | 883 / 19 / 278 | 882 / 17 / 281 |
| Pinky | 838 / 16 / 326 | 832 / 20 / 328 |
| Inky | 926 / 18 / 236 | 929 / 11 / 240 |
| Clyde | 863 / 17 / 300 | 863 / 14 / 303 |

Partial poses remain and vary in both directions. Shared-colour cells, rewards,
clipping, hidden actors and insufficient distinct ink remain exclusions.
Alignment remains x=8, y=4 at two output dots per VIC dot. The first raster
differs from its nearest RAM snapshot by 118 binary pixels; the next distinct
alignment has 3,540 mismatches, so the origin remains unambiguous. The settled
snapshot checks above independently match the recomposed pixel masks exactly.

The [consecutive-frame evidence](../build/pool-alloc-fast/evaluation/trial-vice/evidence.png)
and [comparison preview](../build/pool-alloc-fast/evaluation/comparison.png)
were inspected. The [comparison video](../build/pool-alloc-fast/evaluation/glyph-pool-comparison.mp4)
labels both executable hashes and preserves natural cadence without audio.
Physical hardware has not been tested. No perceptible flicker improvement is
claimed; this is a speed/size optimization of the accepted renderer.

## Reproduction and evidence

```sh
make test-pool-alloc-fast
python3 tools/arcade/pool_profile.py --capture build/ghost-update-fast/evaluation/trial-cpu
python3 tools/arcade/profile_game.py --prg build/pool-alloc-fast/pacman.prg --map build/pool-alloc-fast/pacman.map --input tests/fixtures/active-replay.json --output build/pool-alloc-fast/new-cpu
python3 tools/arcade/pool_profile.py --capture build/pool-alloc-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-alloc-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/pool-alloc-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/pool-alloc-fast/new-vice
```

Run native fixture tools sequentially and use fresh capture/profile directories.
The [frozen record](baselines/pool-alloc-fast.json) retains measurements, binary
identities, source hashes and checks. Raw results are in
`build/pool-alloc-fast/evaluation/`, with smoke at `build/pool-alloc-fast/smoke/`.
The [optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates)
tracks this second candidate-2 experiment as accepted and included in the
standard build. The frozen record preserves its pre-promotion status as
historical evidence. The [promotion record](baselines/pool-alloc-promotion.json)
identifies the then-default artifacts and the regression checks run against them.
The larger persistent cache and redraw-pacing rewrite remain deferred.

The original promotion passed the full `make test` target against its default,
including the retained exhaustive audio, ghost, sprite and tunnel checks and
the allocator benchmark. The default PRG, labels, native image, ELF and map
matched the accepted explicit build byte for byte. The later
[background-tile promotion](baselines/tile-stamp-promotion.json) preserves that
predecessor and records the new standard separately.
