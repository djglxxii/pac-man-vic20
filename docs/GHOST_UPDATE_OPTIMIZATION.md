# Skip no-op ghost-state dispatch during ordinary play

**Accepted, 2026-11-04; included in the standard build.** This intermediate
version is retained; see the [README](../README.md) for the latest default.
This intermediate build's actual VICE throughput improves
**29.81 → 30.78 completed redraws/s**, about **3.3%**, on the saved route.

```sh
make run-ghost-update-fast
```

Press **5**, **1**, then use the arrow keys. Compare with `make run-audio-update-fast`.
`make run` launches the latest standard, which includes this change and the later
accepted improvements.

## Measured target and change

A fresh profile of the preceding audio-adapter build attributes **16.31%** of native CPU time
to `updateGhostStates_1017` and its callees: 3,322,230 cycles across 2,414 calls.
Its compiled body alone costs 1,314,171 cycles. The previous tunnel lookup and
movement-mask improvements are already included in this baseline.

Inspection found avoidable dispatch in ordinary play. The compiler calls the
empty death-animation handler at state zero and emits table jumps for some
alive ghost states, despite their handlers doing nothing. The new
`GHOST_UPDATE_FAST` option in `src/arcade/core.c` tests these six bytes together:

- Pac-Man's death-animation state;
- pending eaten-ghost selection;
- the four ghosts' returning/house states.

When all six are zero, the routine bypasses those no-op dispatches. Any nonzero
state takes the original path in its original order. The fast case occurs on
**2,210 of 2,414 calls**, or **91.55%**, in the native replay. Linked disassembly
shows six zero-page reads, a branch and a jump; no handwritten kernel or lookup
table is needed.

Reward pauses, collision tests, Pac-Man and ghost movement, power-up expiry and
house-release checks remain after the guard. Zero ghost state means alive;
it does not mean the ghost is stationary. No movement update is omitted.
The clock IRQ does not modify these state bytes, so the predicate remains
stable during this main-thread work. No new writable storage is allocated.

## Measurements and tradeoffs

| Measurement | Previous audio adapter | Accepted ghost update |
| --- | ---: | ---: |
| Actual VICE completed redraws/s | 29.81 | **30.78** |
| Completed redraws in capture window | 583 | **602** |
| Native completed redraws/s | 29.93 | **30.94** |
| Native completed redraws | 596 | **616** |
| Ghost update calls | 2,414 | 2,414 |
| Mean ghost update, cycles including IRQs | 1,376.23 | **1,248.68** |
| Total ghost update cycles including callees/IRQs | 3,322,230 | **3,014,314** |
| Actual 95th-percentile redraw interval | 50.24 ms | **48.65 ms** |
| Actual maximum redraw interval | 61.04 ms | **63.43 ms** |
| Maximum native input-service gap | 38.31 ms | **41.72 ms** |
| Maximum native audio-service gap | 37.56 ms | **36.85 ms** |
| Resident end / free before full stack | $7CB3 / 141 bytes | $7CD3 / **109 bytes** |
| BLK5 free | 151 bytes | 151 bytes |
| Packed PRG size | 26,701 bytes | 26,717 bytes |

Inclusive ghost-processing cost falls **9.27%** on this replay. Identical-input
routine tests save **139–142 cycles** when the guard succeeds. Nonzero-state
cases cost **21–23 extra cycles**. Death and returning-ghost processing are
therefore slightly slower individually. These are measured tradeoffs, not
an improvement in every case.

The function grows by 17 code bytes; alignment brings total resident growth
to 32 bytes. The full **704-byte software stack** remains at $7D40–$7FFF.
Hardware stays NTSC with +3K and BLK1/2/3/5 expansion.

Native CPU shares become 46.65% logic/tasks, 50.86% rendering, 2.33% audio and
0.16% waiting. Rendering occupies a larger share because more redraws fit into
the same logical-tick replay. Cadence also changes which poses are composed;
these figures are not an identical-input renderer benchmark.

This is an average above 30 redraws/s on one route, **not fixed 30 Hz pacing**.
The longest measured redraw and input-service gaps are worse. Partial poses
remain, and the measurements do not establish a perceptible flicker reduction.

## Equivalence and display validation

`tests/ghost_update.py` executes both actual 6502 routines against the original
Z80 entry at $1017 on **2,458 identical fixtures**:

- 528 movement-pattern fixtures covering normal, frightened, tunnel, Elroy,
  in-house, returning and death-pause cases;
- 720 combinations of all defined ghost states and pending selections;
- 10 house-transition boundaries, with assertions that transitions occur;
- 80 death-animation counter boundaries across all sixteen nonzero states;
- 96 reward pauses, including cocktail flag combinations;
- 1,024 tile/powered-pixel collision fixtures, including simultaneous ghosts
  and the original Clyde → Inky → Pinky → Blinky priority.

Logical screen, palette, game state and meaningful sound nibbles match the ROM.
Both 6502 builds also produce byte-identical mapped output. Calls mask IRQs;
timings include RTS and exclude the caller's JSR and fixture loading.

The 15 original-ROM tests, 40 pooled tests and 13 classifier tests pass. Both
native profiles check all **1,207 active game states**. A separate replay
matches effect/song state, frequency/volume state and arcade/VIC sound registers
on **1,639 logical ticks**. Sound write timestamps can differ; no PCM capture
or listening comparison is claimed.

Smoke passes attract, credits, maze, fruit and all three intermissions, with
**7,192 logical ticks**. IRQ vector, boot handoff and stack guard remain intact.
Observed maximum software/hardware stack writes are 30/24 bytes; the full
reservation remains and these observations are not worst-case bounds.

Fresh actual VICE captures verify **33,792 depacked bytes per build** against
their own PRGs. Each contains **1,180 consecutive raster frames**, without guest
patches, render gating or clock changes. Both use the current artwork, including
the final death-frame edit that followed the earlier audio promotion.

The first trial capture was rejected because the old eight-cycle observation
window missed three raster frames. The host tool now uses a sixteen-cycle
window in the top border and validates exact frame strides after accounting
for the sampled cycle. Missing/duplicate frames still fail. Fresh captures
of both builds use this method; the rejected capture supplies no results below.

The trial passes **580 settled-picture oracles** and **4,704 synthetic
absent/partial controls**, with zero false absent/partial settled results.
Neither build has fully absent actors among eligible cases. Partial results
vary in both directions:

| Actor | Previous present / partial / excluded | Accepted present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 984 / 19 / 177 | 989 / 14 / 177 |
| Blinky | 893 / 8 / 279 | 883 / 19 / 278 |
| Pinky | 841 / 10 / 329 | 838 / 16 / 326 |
| Inky | 928 / 12 / 240 | 926 / 18 / 236 |
| Clyde | 864 / 15 / 301 | 863 / 17 / 300 |

Shared colour cells, reward expansion, clipping, hidden actors and insufficient
distinct ink remain exclusions. The generated trial evidence image was inspected.
Physical hardware has not been tested.

## Reproduction and evidence

```sh
make test-ghost-update-fast
python3 tools/arcade/profile_game.py --ghosts --prg build/ghost-update-fast/pacman.prg --map build/ghost-update-fast/pacman.map --input tests/fixtures/active-replay.json --output build/ghost-update-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/ghost-update-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/ghost-update-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/ghost-update-fast/new-vice
```

The test target collects the checks run individually during this experiment.
Run fixture tools sequentially because they share temporary files. Use fresh
profile/capture directories. Repeat the profile/capture commands with
`build/audio-update-fast/` for a new baseline comparison.

Raw evidence is under `build/ghost-update-fast/evaluation/` and smoke results
under `build/ghost-update-fast/smoke/`. The [frozen record](baselines/ghost-update-fast.json)
retains compact measurements, identities, source hashes and validation results.
Native directories are `baseline-profile` and `trial-cpu`; accepted captures
for this comparison are `baseline-vice-16` and `trial-vice-16`.

The [optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates)
records this as accepted and included in the standard build. The frozen results
retain their pre-promotion status as historical evidence. The
[promotion record](baselines/ghost-update-promotion.json) identifies the then-default
artifacts and the regression checks run against them.

The original promotion passed the full `make test` target against its default.
The PRG, labels, native image, ELF and map matched the accepted explicit build
byte for byte. The later [cell-allocation promotion](baselines/pool-alloc-promotion.json)
preserves that predecessor and records the new standard separately.

The audio adapter's optional archived-input test now validates the capture
against its own saved PRG, native image, converter and output digest. It replays
all 1,639 archived inputs against both current adapters and the independent
host model. A later artwork edit no longer incorrectly requires the rebuilt
baseline to have the historical capture's whole-program hash. No historical
profile cycle costs are reused, and the frozen capture remains unchanged.
