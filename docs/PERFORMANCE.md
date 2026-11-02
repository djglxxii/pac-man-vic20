# Frame-rate measurements

The game runs compiled 6502 code on the VIC. There is no Z80 interpreter or
runtime translation on the machine. The separate Z80 runner is a PC test tool.

The initial native-core build maintained the arcade logic clock but drew
only about 9–10 FPS in the first gameplay sample. Its catch-up loop correctly
prioritized logic, which concealed a large visual performance gap in the
earlier timer-only validation. Those results did not establish 60 FPS.

## Current measurements

Run `make performance` to save instruction profiles, render timestamps and
`build/performance/current/summary.json`. Samples use the NTSC VIC-20 CPU
clock of 1,022,727 Hz and count **completed** renders over 180 video frames.
They measure emulated CPU time, independently of the host's execution speed.
The board-transition sample runs for at least 360 video frames and extends
until pending rebuild/setup work settles. Reports include the longest refresh
and coherent draw interval, individual batch durations and input/audio gaps.
Bounded-refresh elapsed time includes yields to other work.

Representative results on 2026-11-01 with white-pellet color priorities:

| Sample | Completed renders per second | Mean refresh elapsed | Longest coherent draw interval |
| --- | ---: | ---: | ---: |
| Early first-board play | 45.58 | 10.66 ms | 37.74 ms |
| Frightened movement | 51.61 | 9.22 ms | 43.92 ms |
| Attract chase | 43.56 | 10.89 ms | 62.88 ms |
| First intermission | 60.08 | 3.44 ms | 22.21 ms |
| Board transition | 39.30 | 11.30 ms | 2073.70 ms |

The [maze flash](MAZE_FLASH.md) now recolours existing pixels. All eight
phases appear about 198 ms apart, within 17 ms of their requests. The board
transition sample also includes [bounded next-maze drawing](BOUNDED_REBUILD.md).
Its background calls take at most 7.52 ms, with input and audio gaps of at
most 28.80 and 26.04 ms. The board draws progressively; the longest coherent
refresh spans 1852.34 ms across many calls. The longer coherent draw interval
is a visible tradeoff for continued service.

The previous [bounded-rebuild revision](baselines/bounded-board-rebuild.json)
measured 49.74 FPS in normal play and a 1800.99 ms coherent transition gap.
Keeping stationary pellets white requires inspecting neighboring logical tiles;
the added work reduces throughput and increases construction time. See
[the color-priority measurements](COLOR_PRIORITIES.md) for the visual benefit,
memory cost and focused checks. The older baseline remains unchanged.

The timer still schedules 60.606 logic ticks per second. Short measurement
windows round tick counts at their boundaries. The frightened and intermission
benchmarks inject their setup state; they are not natural playthroughs.

These are sample averages, not a guaranteed minimum. Frame intervals remain
uneven during busy gameplay; transitions that rebuild the screen can also
stall. Full-raster presentation and physical hardware have not been measured.

## Changes made

- Replaced the per-frame generic memory copies with fixed 6502 loops.
- Reduced task-timer scanning to byte indices and avoided expensive sound
  calls for idle channels. Removed recursive effect handoff while preserving
  its state changes and priorities.
- Replaced the C sprite frontend with assembly, including coordinate scaling,
  palette selection, clipping, underlay handling and color-cell restoration.
- Configured flip, shift and clipping paths once per sprite. Large right
  shifts use the equivalent shorter left shift across the two output bytes.
- Kept unchanged actors on screen, with old/new footprint propagation to
  preserve overlapping sprites and shared cell colors.
- Put frequently accessed game flags in zero page, moving the dirty bitset
  and sprite cache to unused low RAM.
- Specialized the three sound voices and replaced integer division with an
  exact threshold search. This preserves divider values and sound sequencing.
- Precomputed all eight shifts for four shared ghost masks: six normal frames
  and two frightened frames. Transparent edge rows preserve their underlays
  without mask reads or redundant pixel writes.
- Aligned the square and bit-reversal tables to pages, unrolled sprite restore
  loops by two rows, and moved large background rebuilds into a separate function.
- Split background conversion and bulk board tasks into bounded calls, using
  idle cycles between ticks. Preserved task order and replayed writes behind
  the cursor; retained the separate maze-flash path.
- Give visible standing pellets white background priority, rechecking neighboring
  logical tiles after erases and palette changes. Cache adjacent lookups and
  avoid recoloring an aligned sprite's empty right-hand column.

The [optimization review](OPTIMIZATION_REVIEW.md) maps these changes to the
new guide and records experiments that did not improve the result.

Native parity traces, renderer comparisons and audio-register tests cover
these changes. The game clock and the number of gameplay updates are retained.

## Remaining budget

A 60.606 Hz update allows 16.50 ms, or 16,875 CPU cycles, for **all** work.
Rendering alone still averages roughly 10.7 ms in the gameplay sample,
leaving about 5.8 ms for input, game logic and sound. Their combined cost still
exceeds that budget, so gameplay has not reached sustained 60 FPS.

The previous full rebuild took about 829 ms in one call, with a 1.28-second
draw gap. Bounded work removes that input/audio blockage but takes about
2.1 seconds between coherent refreshes while drawing progressively. Reducing
total construction time remains useful. The flash retains its color-only
path. Hot game-state routines and the generic sprite paths also need work
for sustained 60 FPS gameplay.

Increasing emulator speed would also increase game speed and would not
establish the target frame rate on an ordinary VIC-20.
