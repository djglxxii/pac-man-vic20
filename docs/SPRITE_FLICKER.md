# First sprite-flicker reduction

The first retained change avoids erasing stationary actors for unrelated
background updates. It keeps the accepted white maze, 112×216 hires display,
original sprite priority, arcade clock and period-correct +35 KB expansion.
Moving actors still use the visible erase/background/redraw sequence; this is
a partial reduction, and further flicker work remains.

## Finding and implementation

Previously, any queued tile or palette change marked all six actor slots
dirty. A changing score or blinking pellet could erase and redraw stationary
ghosts elsewhere on the screen. Their cache already checked position, frame,
flip and palette, but the background flag bypassed those checks.

The renderer now builds a seven-bit map of dirty background bands before
erasing anything. Each band is 32 pixels high and contains two complete 8×16
colour rows. Both ends of a six-pixel tile and a twelve-pixel actor are covered,
including crossings between bands. The arcade's rotated HUD addressing is
included. A stationary actor outside those bands remains visible.

The bands deliberately ignore horizontal separation, so they can cause extra
redraws. They cannot miss a shared colour cell. Existing overlap propagation
still pulls neighbouring actors into a required redraw; reverse restoration
and forward drawing retain the original underlay and colour priorities.
Full rebuilds and maze flashes still invalidate every actor.

The map uses index zero of the existing position cache, which the six even
actor slots do not use. No additional RAM or zero-page storage is allocated.
The extra native code leaves 13 bytes in BLK1–3 and 15 in BLK5. Memory reuse
is a prerequisite for substantially larger rendering changes.

## Measurements

The frozen [measurement record](baselines/sprite-flicker.json) compares the
preceding white-maze executable with this build. Standard samples last 180
NTSC video frames, with 360 for the board transition. Setup and presentation
timing can shift the particular frames sampled.

| Measurement | Before | After |
| --- | ---: | ---: |
| Normal-play completed renders/s | 48.10 | 49.61 |
| Normal-play mean erase-to-paint window | 6.641 ms | 6.065 ms |
| Normal-play 95th-percentile erase-to-paint window | 13.412 ms | 11.605 ms |
| Normal-play actor erases | 515 | 485 |
| Attract-chase actor erases | 555 | 333 |
| Frightened completed renders/s | 53.81 | 53.96 |
| Attract-chase completed renders/s | 44.00 | 43.43 |
| Intermission completed renders/s | 60.32 | 60.06 |
| Longest coherent board-transition interval | 1843.77 ms | 1939.77 ms |

Fewer erases do not establish flicker-free display. The host-only trace times
`bitmap_erase` entry through the matching generic/ghost painter's return and
records raster positions. That is a CPU work window, not a measurement of
individual VIC pixel fetches or perceptual flicker. Some moving-actor windows
still exceed a video frame. Attract's mean remaining window also increases:
avoiding some updates does not make every remaining update shorter.

The transition is about 96 ms slower in this sample. Its focused settled-board
check completes in 1923.81 ms, within the existing 2000 ms limit; maximum input
and audio service gaps are 23.10 and 26.36 ms. The original game timer remains
unchanged. Longer normal-play samples are retained in the measurement record;
longer attract/intermission runs advance into other scenes and are not isolated
measurements of those animations.

## Validation and review

All 43 regression tests pass, followed by the frontend smoke run through all
three intermissions and over 7,000 logical ticks. The new compositor check
compares 100 queued background edits against fresh full redraws with overlapping
ghosts. It covers both HUD orientations, palette writes and colour sharing
without pixel overlap; an unrelated HUD edit must leave the actors unerased.
The whole-background fixture now declares a full invalidation instead of
pretending the replacement bitmap is one dirty tile.

VICE checks cover boot, coin/start, sound, all eight blue/white maze-flash
phases and the next board. Separate ten-second captures use actual VICE
raster output and the same joystick sequence for both builds. They preserve
intermediate drawing, unlike screenshots taken at renderer completion.
Physical hardware has not been tested.

Local review artifacts are under ignored `build/flicker/`:

- `comparison.mp4`: before on the left, after on the right; no audio.
- `before/vice/` and `after/vice/`: individual captures and input/state records.
- `before/gaps/` and `after/gaps/`: actor traces and timing summaries.
- `before/performance/` and `after/performance/`: CPU profiles and refresh timings.
- `regression.log` and `vice-validation/`: verification results.

```sh
make test
python3 tests/flicker.py --output build/flicker/current
python3 tests/performance.py --output build/performance/flicker
python3 tools/arcade/vice_check.py --maze-flash --output build/flicker/vice-validation
```

Both measurement commands accept `--prg PATH` to compare a saved executable
with its sibling `.lbl` file using the same host tools.

## Experiments and next step

General independent-actor grouping reduced the mean normal-play window to
about 5.46 ms but reduced rendering to 41.58 FPS. A cheaper isolation variant
still cost too much, and preparing sprite metadata before erasing gave only
small window savings at about 43.27 FPS. These variants were discarded.

The next step is to reclaim memory, then revisit composing complete affected
regions or smaller independent actor groups with a lower bookkeeping cost.
The retained change does not make those later renderer changes unnecessary.
