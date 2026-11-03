# Frame-rate measurements

The game runs compiled 6502 code on the VIC. There is no Z80 interpreter or
runtime translation on the machine. The separate Z80 runner is a PC test tool.

The initial native-core build maintained the arcade logic clock but drew
only about 9–10 FPS in the first gameplay sample. Its catch-up loop correctly
prioritized logic, which concealed a large visual performance gap in the
earlier timer-only validation. Those results did not establish 60 FPS.

## Current measurements

Scope clarification from the [capture audit](CAPTURE_AUDIT.md): the opening
sample supplies no continuing joystick turns after startup. Its rates do not
describe the computer-controlled comparison videos. A fresh active VICE
capture counts 33.42 renderer calls/s for the accepted original and 23.51 for
the beam experiment. Completed calls also need not produce unique motion poses.

Run `make performance` to save instruction profiles, render timestamps and
`build/performance/current/summary.json`. Samples use the NTSC VIC-20 CPU
clock of 1,022,727 Hz and count **completed** renders over 180 video frames.
They measure emulated CPU time, independently of the host's execution speed.
The board-transition sample runs for at least 360 video frames and extends
until pending rebuild/setup work settles. Reports include the longest refresh
and coherent draw interval, individual batch durations and input/audio gaps.
Bounded-refresh elapsed time includes yields to other work.

Representative results on 2026-11-02 after the
[ghost-state pass](GHOST_STATE.md), retaining the generic sprite-kernel,
startup memory reuse and first sprite-flicker changes:

| Sample | Completed renders per second | Mean refresh elapsed | Longest coherent draw interval |
| --- | ---: | ---: | ---: |
| Early first-board play | 51.93 | 9.29 ms | 36.70 ms |
| Frightened movement | 54.61 | 8.04 ms | 46.06 ms |
| Attract chase | 43.65 | 8.68 ms | 52.02 ms |
| First intermission | 60.03 | 3.39 ms | 22.60 ms |
| Board transition | 41.86 | 9.98 ms | 1843.16 ms |

The separate [beam-scheduled experiment](BEAM_FOLLOW.md) measures
32.57/34.55 FPS in the opening/frightened benchmarks. User review found no
perceptible benefit. Its active capture rate above is lower; it remains a
separate diagnostic target. The accepted default is unchanged.

The [maze flash](MAZE_FLASH.md) now recolours existing pixels. All eight
phases appear about 198 ms apart, within 17 ms of their requests. The board
transition sample also includes [bounded next-maze drawing](BOUNDED_REBUILD.md).
Its background calls take at most 6.38 ms, with input and audio gaps of at
most 27.94 and 27.59 ms. The board draws progressively; the longest coherent
refresh spans 1737.75 ms across many calls. The longer coherent draw interval
is a visible tradeoff for continued service.

The previous [bounded-rebuild revision](baselines/bounded-board-rebuild.json)
measured 49.74 FPS in normal play and a 1800.99 ms coherent transition gap.
The intermediate [pellet-priority experiment](COLOR_PRIORITIES.md) measured
45.58 FPS and a 2073.70 ms transition gap because it inspected neighboring
logical tiles. The [all-white maze](WHITE_MAZE.md) removes those checks and
recovers most of that cost. A coverage-map check keeps background art sharing
wall cells white. Earlier baseline records remain unchanged.

The preceding white-maze build measured 48.10/53.81 FPS in normal/frightened
play and a 1843.77 ms transition gap. The first flicker change keeps stationary actors
visible for background updates in unrelated vertical bands. Normal-play mean
erase-to-paint time falls from 6.641 to 6.065 ms and its 95th percentile from
13.412 to 11.605 ms. Attract's actor erase count falls from 555 to 333 in the
standard sample. This is a partial flicker reduction with a roughly 96 ms
longer transition in this sample; it does not improve every scene or worst-case
interval. See [the frozen results](baselines/sprite-flicker.json).

The memory-reuse change reclaims 358 resident bytes, bringing BLK1–3 free space
to 371 bytes. Its average frame rates remain similar to the flicker checkpoint,
and its sampled normal-play maximum draw interval is higher. This pass creates
room for future rendering work; it does not establish steadier presentation.
See [the frozen memory results](baselines/memory-reuse.json).

The generic sprite-kernel pass then reduces per-row loop/dispatch work,
preserves empty rows without redundant writes and handles clipping once per
actor. Its equally weighted 13,824-input kernel mean uses 21.2% fewer cycles;
some clipped cases still cost up to 41 more cycles. Normal play improves from
49.64 to 51.38 renders/s, and the mean actor window from 6.069 to 5.738 ms.
Resident headroom grows another 20 bytes, to 391 in BLK1–3. Flicker remains;
see [the frozen kernel results](baselines/sprite-kernels.json).

The [raster-aware experiment](RASTER_SYNC.md) was rejected after visual review
found no perceptible improvement. Its frightened/attract samples fell to
52.02/42.60 renders/s. Reverting it restored the generic sprite-kernel build
and recovered its 317 resident bytes, returning BLK1–3 headroom to 391 bytes.

The ghost-state pass then avoids redundant temporary shifts when testing
movement masks. Across 528 identical-input fixtures, the complete routine's
equally weighted mean falls 6.44%; active scenarios average 7.62–8.24% fewer
cycles. Every active case improves, while in-house cases cost two more cycles.
Normal/frightened samples become 51.93/54.61 renders/s. Short attract throughput
falls to 43.65, and frightened play's maximum draw interval increases. Longer
1,800-frame mixed workloads improve from 51.93/50.21/37.98 to
52.38/52.95/38.76 renders/s from play/frightened/attract setups respectively;
these include deaths and screen construction. Cadence does not improve in
every scene. The change frees another 325 resident bytes, leaving 716 bytes in
BLK1–3 and 15 in BLK5; see [the frozen results](baselines/ghost-state.json).

A broader [ghost-precomposition preview](GHOST_PRECOMPOSITION.md) keeps actors
visible while composing shared scratch columns, including overlaps. It moves
59.8% of sampled normal-play actor erases off screen, but reduces throughput
to 29.28 FPS normally and 34.32 when frightened. Size limits recover speed by
excluding most updates. The user saw no significant difference in the flicker
itself, so the experiment is rejected. Its preview remains archived; the faster
ghost-state build above is restored and byte-identical to its baseline.
No precomposition runtime code is enabled in main.

The timer still schedules 60.606 logic ticks per second. Short measurement
windows round tick counts at their boundaries. The frightened and intermission
benchmarks inject their setup state; they are not natural playthroughs.

These are sample averages, not a guaranteed minimum. Frame intervals remain
uneven during busy gameplay; transitions that rebuild the screen can also
stall. VICE raster captures support visual review; physical hardware has not
been tested.

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
- Render maze walls and standing pellets white; retain the wall coverage map
  for shared background cells and completion flashing. Remove the experimental
  pellet-neighbor scans/cache. Avoid recoloring an aligned sprite's empty right
  column. Completion flashes blue/white against the white maze.
- Keep stationary actors visible when queued background changes occupy
  unrelated 32-pixel bands. Preserve colour-cell and sprite-overlap propagation,
  and continue to invalidate every actor for rebuilds and maze flashing.
- Execute one-time platform setup from temporary logical screen RAM, then
  release that area to the game. Retain stack reservations and the hardware target.
- Tighten the generic sprite loop, save transparent rows without pixel writes,
  and redirect clipped columns into their unused underlay halves during setup.
- Read the stored ghost movement decision directly after rotating its speed
  mask, avoiding redundant temporary shifts without changing movement timing.

The [optimization review](OPTIMIZATION_REVIEW.md) maps these changes to the
new guide and records experiments that did not improve the result.

Native parity traces, renderer comparisons and audio-register tests cover
these changes. The game clock and the number of gameplay updates are retained.

## Remaining budget

A 60.606 Hz update allows 16.50 ms, or 16,875 CPU cycles, for **all** work.
Rendering alone still averages roughly 9.3 ms in the gameplay sample,
leaving about 7.2 ms for input, game logic and sound. Their combined cost still
exceeds that budget, so gameplay has not reached sustained 60 FPS.

The previous full rebuild took about 829 ms in one call, with a 1.28-second
draw gap. Bounded work removes that input/audio blockage but takes about
1.84 seconds between coherent refreshes while drawing progressively. Reducing
total construction time remains useful. The flash retains its color-only
path. Hot game-state routines and the generic sprite paths also need work
for sustained 60 FPS gameplay.

Increasing emulator speed would also increase game speed and would not
establish the target frame rate on an ordinary VIC-20.
