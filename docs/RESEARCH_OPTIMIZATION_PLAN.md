# Research optimization plan

Prepared on 2026-11-01 from the
[synthesized research report](vic-20-synthesized-research-report.md), the
[earlier guide review](OPTIMIZATION_REVIEW.md), the current source, linker map
and CPU-cycle profiles. This document selects useful techniques for this
conversion; the report is a reference, not a checklist to apply wholesale.

Preparation and the first implementation are complete on
`optimization/bounded-board-rebuild`. See [the implementation and measured
tradeoff](BOUNDED_REBUILD.md). The remaining items are still queued.
The separate [color-priority experiment](COLOR_PRIORITIES.md) followed the
user's request to preserve white pellets. The subsequent
[all-white maze](WHITE_MAZE.md) removes its neighbor scans/cache and recovers
resident headroom. The queued memory-lifetime audit remains useful.

## Baseline

Commit `4c5f726d74acfde959baca587558655c3a802fcb` checkpoints all preceding
maze-flash changes, their tests and documentation, and the research report.
The user confirmed that the maze flash works as expected.

Fresh verification at that commit passed all 28 tests (15 ROM comparisons,
six native checks, four renderer checks and three flash checks), followed
by the frontend smoke run. The smoke run covered 7,185 logical ticks with
the IRQ vector and stack guard intact. VICE was not rerun during preparation;
the existing VICE evidence is described in [MAZE_FLASH.md](MAZE_FLASH.md).

The fresh performance run reproduced these measurements:

| Sample | Completed renders/s | Mean render, ms | Longest render, ms | Longest draw interval, ms |
| --- | ---: | ---: | ---: | ---: |
| Normal play | 48.94 | 9.96 | 16.90 | 38.38 |
| Frightened | 52.97 | 8.47 | 17.39 | 50.35 |
| Attract chase | 44.54 | 10.43 | 13.78 | 51.28 |
| First intermission | 60.07 | 3.41 | 12.41 | 22.01 |
| Board transition | 42.05 | 7.33 | 828.87 | 1277.65 |

These are CPU-cycle samples, not guaranteed minimum rates. The transition
sample forces board completion and lasts 360 video frames; the others last
180. Logic-rate estimates in these short windows include boundary rounding.
An IRQ counter continuing to advance does not prove that input, game logic
or sound conversion were serviced on time.

The [frozen baseline JSON](baselines/research-optimization.json) records the
full measurements, validation results, artifact hashes and memory headroom.
Raw profiles and traces remain locally in the ignored directory
`build/performance/research-baseline/`. The executable has 31 bytes free in
BLK1-3 and 27 in BLK5. Those 58 bytes are not one contiguous allocation.

## Implementation order

Complete and validate one item before moving to the next. Keep changes in
separate commits, retain measured improvements, and record rejected experiments
so later work does not repeat them.

| Order | Useful research | Application and expected benefit | Status |
| --- | --- | --- | --- |
| 1 | Bounded work and scheduling, sections 7.4 and 10 | Service input/logic/audio during progressive next-board construction. Coherent completion takes longer; see the measured tradeoff. | Implemented |
| 2 | Lifetime-based memory reuse, section 7.1 | Audit initialization routines and data lifetimes; reclaim space for faster kernels and tables. Measure stack use before considering spare-looking RAM. | Queued |
| 3 | Specialized blitters, pre-shifting and self-modifying addressing, section 4.6 | Optimize common Pac-Man, returning-eye and clipping cases that still use the generic path. Compare setup overhead and code size against cycles saved. | Queued |
| 4 | Profile-guided C/assembly work, sections 7.2 and 8 | Optimize hot native logic and sound routines while preserving results, update count and ordering. | Queued |
| 5 | VIC shift-register waveforms, section 6.2 | Explore closer timbres using offline comparison and listening tests; preserve original effect sequencing. | Deferred until performance work is stable |

Item 1 may require a small space-saving prerequisite because the current link
is nearly full. Keep that prerequisite narrow and separately reviewable;
extensive overlays and additional sprite tables belong to later items.

The saved normal-play instruction profile attributes about 6.7% of total
cycles directly to `updateGhostStates_1017()`, excluding callees, and 3.8%
directly to `soundEffectOneChannel_2dee()`. These are candidates for item 4,
not predicted speedups. Re-profile after each retained rendering change.

## First item: bounded next-board work

The target is the next-board pause after the already-correct four blue/white
flash pairs. `video_rebuild()` in `src/video.c` clears display state and scans
up to 1,024 arcade tiles in one call. `arcade_tasks()` in `src/arcade/core.c`
also drains queued work synchronously before presentation. The 828.87 ms
render and 1277.65 ms draw gap measure different spans; splitting the renderer
alone must not be described as fixing all transition work.

Implement this in small steps:

1. Measure transition phase costs, logical tick spacing, audio-update gaps
   and the time until a coherent next board is visible. Separate bulk arcade
   tasks from bitmap clearing, tile conversion and sprite work. Preserve the
   existing whole-render measurements for comparison.
2. Establish a memory layout for the continuation state and a worst-case
   per-call cycle budget. Include clearing the bitmap, colors and maze-wall
   coverage in that budget. Leave time for input, logic, audio and IRQ overhead;
   the entire arcade tick allows only 16,875 cycles, about 16.50 ms.
3. Turn rebuild work into resumable phases with a persistent cursor. Preserve
   dirtied tiles already visited by an unfinished rebuild, handle a new full
   invalidation, and prevent lost writes or indefinite restart loops.
4. Define how partial work is presented before changing the main loop. The
   current display has one mutable character bitmap: a hidden second bitmap
   is not available. Evaluate progressive drawing or temporary blanking against
   the original transition, and record the chosen behavior. Do not count an
   unfinished batch as a completed frame or leave the display blank indefinitely.
5. Preserve sprite priority, reverse-order underlay restoration, cell colors,
   HUD contents and maze-wall coverage through partial work and completion.
   Exercise full rebuilds in attract, credit and intermission screens too.
6. If bulk arcade tasks still cause a long service gap, address their execution
   with continuations only after verifying original task dependencies and
   ordering against the Z80 reference. Do not reschedule ghost decisions or
   alter state-machine delays to mask a rendering stall.

Acceptance requires bounded rebuild calls within the chosen cycle budget,
correct final pixels/colors and underlay restoration, and no lost dirty writes
when another change arrives during a rebuild. Measure and report the longest
input/logic/audio service gap across the entire transition, along with total
transition duration and time spent blank or incomplete. A lower batch duration
or a higher batch count alone is not success. Keep the existing renderer and
flash timing checks passing and avoid a normal-play performance regression.

Add focused checks for interrupted/restarted rebuilding and the full
transition. Existing tests deliberately sample some scenes after setup tasks
finish, so they do not by themselves prove correctness of intermediate
transition states. Do not change their oracle expectations merely to make a
new scheduling scheme pass.

## Constraints and recommendations to adapt

- Preserve the arcade timer: VIA2 T1 latch `$41E9`, period 16,875 CPU cycles,
  approximately 60.606 Hz. The report's raster-locked latch `$4243` gives
  approximately 60.285 Hz on this NTSC target. Use separate presentation timing
  if needed; changing the gameplay clock would slow arcade behavior.
- Preserve movement, ghost updates, random sequence, task dependencies, score
  behavior, sound sequencing and all existing arcade quirks. Round-robin enemy
  updates from the report conflict with this conversion's parity target.
- Adapt compiler advice to LLVM-MOS. The native build uses `-Oz`, a custom
  linker script and explicit zero-page allocation; cc65 flags, `__fastcall__`
  and its stack conventions do not apply to this executable.
- Keep display data in VIC-visible RAM. Expansion RAM can hold CPU-side
  buffers and tables, but the VIC cannot display them directly. A second
  3,136-byte bitmap does not fit the current layout. Flipping screen codes and
  color RAM does not hide writes to shared character definitions.
- Prefer the existing underlay compositor over XOR drawing: overlap artifacts
  would change the rendered actors and background restoration.
- Preserve `$900E`'s auxiliary-color nibble if a future mode starts using it.
  The present hires renderer does not use that color, so its volume-only write
  is not a current visible defect. Multicolor or raster changes need a fresh
  palette, resolution and CPU-budget evaluation.
- Defer PCM playback and elaborate raster effects. Their CPU and timing costs
  do not address the current stalls or gameplay throughput.
- File compression reduces load size; it does not by itself create runtime
  space for extra tables or a second framebuffer.

Dirty updates, unchanged-actor caching, a column-major bitmap, assembly
sprite kernels, pre-shifted ghost masks, transparent-row handling, selected
page alignment, zero-page hot state, table-based arithmetic and the minimal
IRQ are already in use. The maze flash already changes colors without
reconstructing pixels. Preserve those gains rather than reimplementing them.

## Verification and change record

Use the pinned toolchain and ordinary NTSC CPU speed. For each implementation,
record its parent revision, hypothesis, memory cost, validation results and
before/after timings here or in a linked focused note. Run:

```sh
make test
python3 tests/performance.py --output build/performance/bounded-board-rebuild
make vice-test
python3 tools/arcade/vice_check.py --maze-flash --output build/maze-flash/vice-bounded-rebuild
```

Use focused checks while iterating, then the complete relevant checks before
retaining an implementation. VICE should verify presentation and sound after
the simulator checks; physical NTSC hardware is needed before claiming
hardware validation. Keep large raw captures and profiles under `build/`,
and commit compact findings and comparable measurement summaries.

| Date | Change | Result |
| --- | --- | --- |
| 2026-11-01 | Checkpoint existing work; freeze baseline; document priorities and item 1 acceptance criteria. | Preparation only; no new game, test or build code. |
| 2026-11-01 | Implement bounded background/bulk slices, cursor replay and idle-time servicing. | Input/audio gaps below 30 ms in the transition sample; coherent draw gap increases from 1.28 to 1.80 seconds. See [validation](BOUNDED_REBUILD.md). |
| 2026-11-01 | Prioritize white standing pellets and avoid an aligned sprite's empty right color column. | All 113 pellet cells in a fixed snapshot become white, versus 41. Shared walls also become white. Normal play measures 45.58 FPS and the coherent transition gap 2.07 seconds. See [measurements](COLOR_PRIORITIES.md). |
| 2026-11-01 | Make the maze white and completion flash blue/white; remove pellet-neighbor scans/cache. | Normal play measures 48.10 FPS, frightened 53.81 and the coherent transition gap 1.84 seconds. Reclaims two zero-page bytes and 191 resident bytes. See [measurements](WHITE_MAZE.md). |
