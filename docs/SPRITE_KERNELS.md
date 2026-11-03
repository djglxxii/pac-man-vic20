# Faster generic sprite drawing

The generic painter now does less work per scanline. Normal play measures
**51.38 completed renders/s**, up from 49.64, while its mean actor
erase-to-paint window falls from 6.069 to 5.738 ms. This is a modest gain:
moving actors still flicker. The change also frees **20 resident bytes**.

The parent is `cf81d64`, after reverting the region-compositor experiment.
The white maze, actor masks and colours, overlap priority, gameplay clock,
logic ordering and period-correct +35 KB expansion target are preserved.
The [frozen measurement record](baselines/sprite-kernels.json) includes
executable/source hashes, comparable results and validation evidence.

## What changed

The normal-play profile reaches the generic painter 257 times and the
pre-shifted ghost painter 228 times in the standard sample. The generic
path covers Pac-Man, returning eyes and other masks or clipped actors.
Its old scanline loop repeatedly dispatched clipping and tested its row limit.

The revised generic painter:

- Walks the twelve destination rows from bottom to top, with the source
  direction still chosen by the vertical flip bit. A decrement and branch
  replace the increment, compare and extra loop jump.
- Places the common shift/paint operations next to each other, removing
  intermediate jumps. Existing shift and horizontal-mirror selection remain.
- Saves transparent rows' backgrounds without shifting their empty masks or
  writing unchanged bitmap pixels. Those saved rows remain necessary when
  restoring a later frame.
- Handles horizontal clipping once during setup. A clipped column's pointer
  is redirected into that actor's unused twelve-byte underlay half. The loop
  can then use the same two-column painter without touching adjacent bitmap
  RAM. The existing flags keep restoration from using that invisible half.

Only scratch bitmap pointers change; the frontend already saves the original
address in the actor's underlay record before calling the painter and reloads
it before erasing. No additional RAM, zero-page bytes or sprite tables are
allocated. The pre-shifted ghost painter and erase routines are unchanged.
Resident headroom grows from 371 to **391 bytes** in BLK1–3; BLK5 retains 15.
The compressed PRG shrinks from 26,857 to 26,848 bytes.

## Measurements and limits

The reproducible kernel benchmark calls both executables with the same
13,824 inputs: all 64 regular masks and eight eye masks, eight shifts, four
flips, three clipping flags and two address placements. Calls mask IRQs and
exclude the frontend. Cases are equally weighted, rather than weighted by
their frequency during play.

| Kernel CPU cycles | Before | After |
| --- | ---: | ---: |
| Mean, all cases | 1276.21 | 1005.67 |
| Mean, unclipped cases | 1339.54 | 990.34 |
| Mean, clipped cases | 1244.54 | 1013.34 |
| Maximum across cases | 1602 | 1468 |

The mean falls 21.2%. There are 448 clipped cases that take longer, by at
most 41 cycles; 13,376 cases get faster. This is not a universal per-mask
speedup or a prediction of a 21% whole-game improvement.

Standard whole-game samples last 180 NTSC video frames, or 360 for transition:

| Scene | Renders/s before | After | Mean actor window before → after |
| --- | ---: | ---: | ---: |
| Normal play | 49.64 | 51.38 | 6.069 → 5.738 ms |
| Frightened | 54.00 | 54.02 | 5.340 → 5.276 ms |
| Attract chase | 42.91 | 44.25 | 6.716 → 6.564 ms |
| First intermission | 60.15 | 60.15 | 3.126 → 3.037 ms |
| Board transition | 40.89 | 41.86 | Not sampled |

Normal play's 95th-percentile actor window falls from 11.666 to 10.830 ms.
Actor windows observe `bitmap_erase` entry through the matching painter's
return, not individual VIC pixel fetches or perceptual visibility. Rendering
cadence changes the updates selected by the fixed-duration scene samples.
The separate identical-input kernel benchmark establishes the routine's
cycle savings without that sampling difference.

The longest coherent transition interval falls from 1939.72 to 1843.18 ms
in the standard sample. A focused settled-board check completes in 1827.20 ms,
with input/audio gaps of 24.68/27.59 ms. These samples do not guarantee a
shorter interval or service gap in every scene. The longer 1800-frame workload
measures 51.15 → 51.93 renders/s; it includes rebuild work after deaths and
is not an isolated steady-movement sample.

## Validation and visual comparison

All **47 regression tests** pass, followed by a smoke run covering 7,192
logical ticks with the IRQ vector and stack guard intact. The independent
bitmap oracle still covers every frame, shift and flip, plus overlap,
returning eyes, incremental updates and colour restoration. A new 1,152-case
boundary check verifies clipped pixels, saved backgrounds, neighboring
underlay records and guards on both sides of the bitmap through draw/erase.

VICE verifies boot, coin/start, non-silent 48 kHz mono audio, all eight
blue/white completion phases and a settled next board. Physical hardware
has not been tested.

Two actual VICE captures use the same 600 joystick inputs, without guest
patches. Both run from tick 431 to 1033 and pellet count 3 to 73. The
side-by-side video preserves intermediate raster output; sampled frames
still show intermittent missing actors. The measured improvement should
not be presented as a dramatic visual change or a flicker fix.

Local artifacts are under ignored `build/sprite-kernel/`:

- `comparison.mp4`: before on the left, optimized painter on the right.
- `before/` and `after/`: executables, kernel timings, profiles, actor windows,
  longer workload measurements and raster captures/input records.
- `regression.log`, `vice-validation/` and `transition.json`: validation.
- `experiment-1/`, `experiment-2/`, `experiment-3/`: intermediate measurements.

```sh
make test
python3 tests/sprite_timing.py --output build/sprite-kernel/current-kernels.json
python3 tests/performance.py --output build/sprite-kernel/current-performance
python3 tests/flicker.py --output build/sprite-kernel/current-flicker
python3 tools/arcade/vice_check.py --maze-flash --output build/sprite-kernel/vice-validation
```

The timing tools accept `--prg PATH` with a sibling `.lbl` file for comparisons.
Further flicker work needs a separate profile and visual review. Score
readability remains queued.
