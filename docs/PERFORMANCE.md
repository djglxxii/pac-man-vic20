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
The board-transition sample runs for 360 video frames. Reports include the
longest render and the longest interval between completed renders.

Representative results on 2026-11-01:

| Sample | Completed renders per second | Mean rendering time | Longest draw interval |
| --- | ---: | ---: | ---: |
| Early first-board play | 48.9 | 9.96 ms | 38.38 ms |
| Frightened movement | 53.0 | 8.47 ms | 50.35 ms |
| Attract chase | 44.5 | 10.43 ms | 51.28 ms |
| First intermission | 60.1 | 3.41 ms | 22.01 ms |
| Board transition | 42.0 | 7.33 ms | 1277.65 ms |

The [maze flash](MAZE_FLASH.md) now recolours existing pixels. All eight
phases appear about 198 ms apart, within 17 ms of their requests. The board
transition sample also includes drawing the next maze, which still stalls
separately.

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

The [optimization review](OPTIMIZATION_REVIEW.md) maps these changes to the
new guide and records experiments that did not improve the result.

Native parity traces, renderer comparisons and audio-register tests cover
these changes. The game clock and the number of gameplay updates are retained.

## Remaining budget

A 60.606 Hz update allows 16.50 ms, or 16,875 CPU cycles, for **all** work.
Rendering alone still averages roughly 10.0 ms in the gameplay sample,
leaving about 6.5 ms for input, game logic and sound. Their combined cost still
exceeds that budget, so gameplay has not reached sustained 60 FPS.

The full-screen rebuild remains a separate problem: one render in the
transition sample takes about 829 ms, with a visible draw gap of about
1.28 seconds. This occurs after the last flash, during the next-board work.
The completed maze's blue/white colour changes now have their own bounded
path and do not trigger those rebuilds. A bounded rebuild job that yields
between tile batches would address actual screen changes, but is outside
this flash-only revision. Hot game-state routines and the remaining generic
sprite paths also need work for sustained 60 FPS gameplay.

Increasing emulator speed would also increase game speed and would not
establish the target frame rate on an ordinary VIC-20.
