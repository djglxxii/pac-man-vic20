# Research optimization plan

**Current direction, 2026-11-04:** live play testing accepted the
[glyph-pool renderer](GLYPH_POOL.md) as a large visible improvement. The user
reports occasional slowdown and explicitly accepts the speed tradeoff for now.
`make run` now launches this renderer. Commit the complete work as a checkpoint;
the next priority is measured redraw-speed improvement while preserving the
accepted appearance. The stopped colour investigation remains stopped.

| Original idea | Current disposition |
| --- | --- |
| 1. Finished-cell glyph pool | [Accepted after live play testing](GLYPH_POOL.md) and promoted to default. No fully absent actors among classified capture cases; 22.07 versus 32.88 previous redraws/s. Same hardware and full stack. User accepts the slowdown; optimize redraw speed next. |
| 2. Write-once compositing with a full background shadow | No assigned home for the 3,136-byte shadow under the current memory target; the other agent withdrew this fallback. |
| 3. Raster lock / beam scheduling | Several trials rejected after user review and throughput loss. Preserve the 16,875-cycle arcade clock. |
| 4. Pacing / partial updates | Measured uneven cadence remains relevant; partial updates need coherent displayed poses and shared-cell handling. No fixed-rate or IRQ-renderer rewrite is started. |

The [glyph-pool result](GLYPH_POOL.md) and [frozen measurements](baselines/glyph-pool.json)
record the accepted baseline and its cost. First target the existing pool's
cell allocation/addressing/home-copy work, measured at about 6,493 cycles per
native redraw. Tighten that bounded path before considering incremental pool
allocation, which remains a larger design question. No new speed change is
part of this acceptance checkpoint.

**First speed follow-up:** the [pool address trial](POOL_ADDRESS_OPTIMIZATION.md)
now saves 36 cycles per fresh allocation and improves actual capture throughput
from 22.04 to 22.80 redraws/s (about 3.5%). It retains the accepted visibility
behaviour and passes image/gameplay/long-run checks. Use `make run-pool-address`
for live review; the accepted default remains unchanged. See the report and
[frozen measurements](baselines/pool-address.json) before choosing another step.

**Second speed follow-up:** the [empty-row trial](POOL_SKIP_EMPTY.md) builds on
the address trial and reaches **23.21 actual redraws/s**, about **1.8%** more,
or **5.3%** above the accepted pool on the saved route. One two-byte branch
avoids mirroring, shifting and destination writes for an empty source row.
Per-half checks were measured and dropped because their overhead lost time on
the live route. Image/gameplay/long-run checks pass; `make run-pool-skip-empty`
is available for live review. The default remains unchanged. See the report
and [frozen measurements](baselines/pool-skip-empty.json) for limits and costs.

## Earlier investigations (historical)

The current acceptance decision above supersedes older instructions below that
kept the underlay renderer as the default. Retain their measurements and
negative trial reviews as history.

The other agent's [follow-up](Response%20to%20IDEAS_REPLY.md.md) called for two
diagnostics before a renderer replacement. The [matched-cadence comparison](RATE_MATCH.md)
and [CPU/display profile](DISPLAY_PROFILE.md) are complete. Their findings support
a bounded feasibility check; they do not establish that the pool will be faster
or produce a worthwhile visible improvement. The corrected memory assumptions
in [IDEAS_REPLY.md](IDEAS_REPLY.md) still apply.

**Next experiment plan, 2026-11-04:** the
[finished-cell publishing plan](FINISHED_CELL_PUBLISHING_PLAN.md) preserves the
profiling findings, memory and transaction questions, proposed small benchmark,
measurement-adapter requirements, optional review handoff, and acceptance tests.
It also records the historical stationary-fruit white/red flashing observation
and colour investigation. That investigation is complete: the
[stable-colour trial](STABLE_COLOURS.md) removes the measured white pulses but
falls from 32.88 to 29.77 actual redraws/s. User play testing finds no perceptible
improvement and reports continued wall/fruit flashing. The trial is not accepted;
further colour work was subsequently stopped by the user. The default remains
unchanged. The new pool trial's concrete memory/capacity budget and complete
transaction measurements are recorded in its report.

**2026-11-04 update:** the user rejected the playable
[raster-priority revisit](BEAM_PRIORITY.md), reporting no noticeable
improvement and a performance hit. Work on this scheduling approach stops;
the accepted default remains the original renderer. The trials remain
available for reproduction. The [CPU and display profile](DISPLAY_PROFILE.md)
now completes the objective per-frame measurement proposed in
[Response to IDEAS_REPLY.md.md](Response%20to%20IDEAS_REPLY.md.md). It classifies
displayed actors as present, absent or partial, counts disappearance events,
and measures displayed motion intervals. It finds actual missing actors
as well as uneven redraw timing: 32.88 completed redraws/s, a 51.08 ms
95th-percentile redraw interval, and Pac-Man absent in 165 of 1,200 sampled
frames (179 ambiguous frames excluded). Rendering uses 39.25% of the native
replay's CPU time; only 2.01% is waiting. The next experiment must demonstrate
fewer missing/partial frames while preserving throughput on this workload.
No renderer optimization was made during profiling. Finished-cell publishing
remains a candidate requiring a measured cost budget, rather than an automatic
next implementation. The pause and decisions below describe the preceding review.

Current direction, 2026-11-03: preserve the original playable hires game and
pause further flicker work at the user's request. Review of the
[independent-actor trial](ACTOR_COMMIT.md) found that flicker shifts between
sides with no meaningful overall improvement. This hold includes precise
background invalidation and finished-cell publishing. The slow multicolour
integration also remains on hold. The [temporary-character experiment](GHOST_SHADOW.md)
was rejected after user play testing found no perceptible flicker improvement.
Its normal/frightened samples fall from 51.93/54.61 to 33.51/38.20 FPS.
The user considers results above 30 FPS worth a play test, provided the visual
benefit warrants the tradeoff. The renderer remains unchanged. The current
[approved font](FONTS.md) adds custom lettering and horizontal bonus scores at the user's request.

The [beam-scheduled trial](BEAM_FOLLOW.md) also showed no perceptible benefit
in user review and is not accepted. The [capture audit](CAPTURE_AUDIT.md)
confirms different programs and footage, but corrects a reporting problem:
the native benchmark rates were not the rates in the comparison videos.
Fresh active capture measures 33.42 renderer calls/s for the original and
23.51 for the beam build. The original remains the baseline.

The experiment set recorded on 2026-11-03 in the
[improvement audit](IMPROVEMENT_AUDIT.md#agreed-next-experiments), are:

1. Commit independent actors before erasing the next. The
   [trial](ACTOR_COMMIT.md) was rejected after user review found no meaningful
   visual benefit; it also fails the throughput budget. Establish independence from old/new byte
   footprints and saved-underlay dependencies, and preserve shared-cell colour priority;
   disjoint visible pixel boxes alone are insufficient.
2. Make background invalidation more precise, so distant same-row tile
   changes leave unrelated stationary actors visible. On hold with further
   flicker work.
3. Draw clearer 4×6 digits. The user expanded this to letters and all bonus
   scores; the [VIC-native font](FONTS.md) is implemented and approved after visual review.
4. Re-profile the retained renderer, then optimize selected sound routines
   only where measurements justify it. Further ghost work requires fresh
   profiling evidence and arcade parity checks.

Item 1 is rejected and item 2 is on hold. Item 3's font is implemented and approved.
Item 4's retained-renderer profiling is now complete; sound optimization has
not started. Original sound-channel processing uses 8.08% of the active native
sample, within logic/tasks, while VIC audio conversion uses another 5.73%.
Resume flicker work only when the user asks. If resumed, evaluate rendering
changes with the same active joystick trace, visible
erase-to-paint windows and actual-capture throughput, alongside the separate
opening benchmark. The implementation history and broader research items
below remain reference material, subject to the hold above.

Prepared on 2026-11-01 from the
[synthesized research report](vic-20-synthesized-research-report.md), the
[earlier guide review](OPTIMIZATION_REVIEW.md), the current source, linker map
and CPU-cycle profiles. This document selects useful techniques for this
conversion; the report is a reference, not a checklist to apply wholesale.

Preparation and the first implementation are complete on
`optimization/bounded-board-rebuild`. See [the implementation and measured
tradeoff](BOUNDED_REBUILD.md). Further work is tracked below.
The separate [color-priority experiment](COLOR_PRIORITIES.md) followed the
user's request to preserve white pellets. The subsequent
[all-white maze](WHITE_MAZE.md) removes its neighbor scans/cache and recovers
resident headroom. The [memory-lifetime audit](MEMORY_REUSE.md) now reclaims
another 358 resident bytes by reusing startup storage.

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

Sprite-flicker work remains the immediate presentation priority. The
[first retained change](SPRITE_FLICKER.md) avoids erasing stationary actors
for unrelated background changes; shorter moving-actor update gaps remain.
The [region-compositor experiment](REGION_COMPOSITOR.md) was rejected after
visual review found little improvement. Its code, tests and observer additions
were reverted. The [generic sprite-kernel pass](SPRITE_KERNELS.md) now shortens
moving-actor windows, raises normal play from 49.64 to 51.38 renders/s and
recovers another 20 resident bytes. Visible flicker remains.
The [raster-aware experiment](RASTER_SYNC.md) was also rejected: the user saw
no perceptible improvement, while frightened and attract samples lost
throughput. Its code, tests and observer changes were reverted, recovering
317 resident bytes. The accepted generic sprite-kernel improvement remains.
The first [ghost-state pass](GHOST_STATE.md) now removes redundant movement-mask
work: active identical-input scenarios average 7.62–8.24% fewer routine cycles,
normal play rises to 51.93 renders/s and another 325 resident bytes are freed.
Short attract throughput regresses slightly; longer mixed workloads improve.
The broader [ghost-precomposition experiment](GHOST_PRECOMPOSITION.md) was
rejected after user review found no significant difference in the flicker
itself. Its throughput loss is not justified; the faster main build remains.
A separate [maze artwork mockup](MAZE_MOCKUP.md) now explores simpler wall
graphics with the same logical layout and pellet positions. Full-board pattern
count falls from 118 to 109, but allowing private pellet/HUD cells saves only
three additional characters over sharing today's artwork. This is a visual
study; a buffered renderer still needs a complete memory plan.
The user would also prefer blue walls if feasible. The mockup's colour-cell
audit finds that every standing pellet shares a cell with wall pixels, so
fully blue walls and white pellets require a further graphics-layout/colour
mode study. No palette or artwork changes are enabled in the playable build.
A [multicolour artwork prototype](MULTICOLOUR_PROTOTYPE.md) now demonstrates
that palette on a wider screen with custom actors and hires score digits.
Its standalone static PRG matches all picture pixels in VICE. A complete
preloaded maze/HUD atlas leaves 93 work characters; a proven demand-loaded
background bound leaves 109, against 108 for six old/new nine-cell actor
footprints. This supports a future moving-actor experiment; runtime cache
cost, full-game coverage and flicker benefit remain unmeasured.
The user has selected that visual direction. The first
[moving-character compositor](MULTICOLOUR_MOTION.md) passes 2,274 native scenes
and VICE pixel checks, keeping all preparation off screen. It is a standalone
replay. A retained [character-band optimization](MULTICOLOUR_PREPARATION.md)
reduces mean preparation time by 17.39% and full redraw from 29.421 to 25.181 ms
before game logic/audio. The later [reuse/cell-setup pass](MULTICOLOUR_REUSE.md)
rejects unchanged-group reuse after a CPU regression and retains smaller cell
setup, bringing the mean to 24.466 ms. Retained
[background row tables](MULTICOLOUR_BACKGROUND_ROWS.md) reduce it further to
23.780 ms without extra data space. A retained
[publication page cache](MULTICOLOUR_PUBLICATION.md) reduces commit time by
11.17% and total rendering to 23.203 ms, adding seven code bytes. Retained
[colour-write paths](MULTICOLOUR_COLOURS.md) cut colour handling by 27.3% and
total rendering to 22.737 ms, while freeing three metadata bytes. Retained
[loop operands](MULTICOLOUR_LOOP_OPERANDS.md) reduce it further to 22.344 ms,
shrinking code by seven bytes and metadata by five. A retained
[shared map-address byte](MULTICOLOUR_MAP_POINTER.md) reduces it to 21.990 ms,
freeing eight code bytes and one zero-page byte. Retained
[band setup](MULTICOLOUR_BAND_SETUP.md) reduces it to 21.766 ms, freeing three
code bytes and one metadata byte. Retained
[direct background lookup](MULTICOLOUR_BACKGROUND_LOOKUP.md) reduces it to
21.398 ms, freeing seven code bytes and two zero-page bytes. Retained
[direct work-cell setup](MULTICOLOUR_CELL_SETUP.md) reduces it to 20.579 ms,
adding nine code bytes while freeing two zero-page bytes and one metadata byte.
A retained [register-held list cursor pass](MULTICOLOUR_LIST_CURSORS.md) cuts
commit time by 9.85% and total rendering to 20.152 ms, freeing 22 code bytes and
one metadata byte.
A retained [cached restoration pass](MULTICOLOUR_RESTORATION.md) cuts commit
time by another 19.76% and total rendering to 19.380 ms, freeing eight code
bytes and four zero-page bytes. VICE now checks 32 consecutive scenes to
exercise restoration as well as the first image.
A retained [allocation cleanup](MULTICOLOUR_CELL_ALLOCATION.md) removes
redundant register and flag work, cutting preparation time by another 1.78%
and total rendering to 19.091 ms while freeing 18 code bytes. Injected capacity
failures verify the caller's carry-based failure path in all three columns.
A retained [sprite lookup layout](MULTICOLOUR_ROW_LAYOUT.md) reduces rendering
to 19.029 ms by avoiding indexed-read page crossings. All 480 scenes improve,
with identical pictures and no memory growth.
A retained [background glyph ordering](MULTICOLOUR_BACKGROUND_LAYOUT.md)
reduces it to 19.019 ms with no assembly or memory changes. This is a small
0.05% mean saving: 474 scenes improve, four tie and two cost two extra cycles.
A 496-frame native check also exercises the actual packet loader, IRQ and
replay wraparound. A first [live integration](MULTICOLOUR_GAME.md) now connects
the actual game, controls, dynamic pellets/scores and audio. It fits the same
RAM target and passes native/VICE checks. The first capture managed 5.03 actor
updates/s. A targeted playability correction now centres the NTSC display,
uses a pre-shifted shared row dictionary, combines background tile rows and
splits actor preparation across logic/audio service points. The current VICE
sample reaches 8.96 updates/s; the native sample's longest audio-service gap
falls from 102.17 to 31.37 ms. It remains visibly choppy, and several game-state
graphics still use fallbacks. The same conventional RAM target is retained;
a tested 224-byte software stack releases room for graphics tables.
Further standalone micro-optimizations are on hold; integration and missing
state coverage take priority. The CPU-budget gap must be resolved before a
default-renderer switch. The accepted game binary remains unchanged.
Score readability is also queued from user feedback: the current numbers are
difficult to read. The score work below preserves the current hires resolution
and period-correct hardware target.

| Order | Useful research | Application and expected benefit | Status |
| --- | --- | --- | --- |
| 1 | Bounded work and scheduling, sections 7.4 and 10 | Service input/logic/audio during progressive next-board construction. Coherent completion takes longer; see the measured tradeoff. | Implemented |
| 2 | Sprite-flicker reduction | Avoid unrelated actor erases; measure visible update windows and evaluate complete-region composition within the memory budget. | First increment implemented; further work on hold at user request |
| 3 | Lifetime-based memory reuse, section 7.1 | Audit initialization routines and data lifetimes; reclaim space for faster kernels and tables. Measure stack use before considering spare-looking RAM. | Implemented: startup overlay reclaims 358 bytes; stack allocation retained |
| 4 | Specialized blitters, pre-shifting and self-modifying addressing, section 4.6 | Optimize common Pac-Man, returning-eye and clipping cases that still use the generic path. Compare setup overhead and code size against cycles saved. | First increment implemented: generic scanline/clipping work reduced; further specialization requires profiling |
| 5 | Profile-guided C/assembly work, sections 7.2 and 8 | Optimize hot native logic and sound routines while preserving results, update count and ordering. | First increment implemented: ghost movement-mask rotation/test; further work requires profiling |
| 6 | Score readability, user feedback | Evaluate purpose-drawn numeral glyphs and spacing for player scores and the high score; make digits easier to distinguish at the current display size. | Queued |
| 7 | VIC shift-register waveforms, section 6.2 | Explore closer timbres using offline comparison and listening tests; preserve original effect sequencing. | Deferred until performance work is stable |

For score readability, compare the existing scaled ROM digits with hand-tuned
numerals at the actual NTSC display proportions. Check all ten digits in
single-digit and full-width scores, including similar shapes such as 3/8/9
and 5/6. Preserve score values, formatting, alignment and update behavior;
evaluate any glyph or spacing changes visually before retaining them.

Item 1 may require a small space-saving prerequisite because the current link
is nearly full. Keep that prerequisite narrow and separately reviewable;
extensive overlays and additional sprite tables belong to later items.

The saved normal-play instruction profile attributes about 6.7% of total
cycles directly to `updateGhostStates_1017()`, excluding callees, and 3.8%
directly to `soundEffectOneChannel_2dee()`. These are candidates for item 5,
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

- Keep the hardware target period-correct. The current configuration uses
  +35 KB of conventional expansion RAM: +3K at `$0400` and 8K each at
  `$2000`, `$4000`, `$6000` and `$A000`. A contemporary capacity reference is
  *Softline*, September/October 1983 (PDF page 5): its
  [Compuscope Supermother announcement](https://mirrors.apple2.org.za/ftp.apple.asimov.net/documentation/magazines/softline/Softline_1983_09_10.pdf#page=5)
  specifies support for up to 35K of add-on memory. This establishes period
  availability of the capacity, not a physical-hardware test of this build.
  Prefer reclaiming space within the current target. Any proposed hardware
  change must have contemporary product, manual or circuit evidence showing
  that the required capacity and memory mapping were available in the
  original VIC-20 era; modern-only expansion features are outside scope.
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
| 2026-11-02 | Avoid unrelated actor erases and measure actor update windows. | First flicker reduction; normal play 49.61 FPS, with moving-actor flicker remaining. See [measurements](SPRITE_FLICKER.md). |
| 2026-11-02 | Reuse logical screen RAM for startup code and audit buffer/stack lifetimes. | Reclaims 358 resident bytes: BLK1–3 free space grows from 13 to 371 bytes; BLK5 retains 15. Stack reservations unchanged; 46 regression tests and VICE pass. See [audit](MEMORY_REUSE.md). |
| 2026-11-02 | Test and revert direct composition in Pac-Man's usual actor slot. | User saw little difference. Only 12 of 478 normal-play paint entries composed; attract slowed from 42.91 to 41.65 FPS. Reverted the experiment and recovered its 230 resident bytes. See [findings](REGION_COMPOSITOR.md). |
| 2026-11-02 | Tighten the generic sprite loop, skip empty-row writes and handle clipping once. | Identical-input kernel mean uses 21.2% fewer cycles; normal play 49.64 → 51.38 FPS and mean actor window 6.069 → 5.738 ms. Frees 20 bytes; 47 tests and VICE pass. Flicker remains. See [measurements](SPRITE_KERNELS.md). |
| 2026-11-02 | Test and revert raster-aware deferred updates in Pac-Man's usual slot. | User saw no perceptible improvement. Frightened/attract throughput fell from 54.02/44.25 to 52.02/42.60 FPS. Reverted code, four tests and observer changes; recovered 317 resident bytes while retaining the faster generic sprite kernel. See [findings](RASTER_SYNC.md). |
| 2026-11-02 | Avoid redundant temporary shifts when testing ghost movement masks. | Active identical-input scenarios average 7.62–8.24% fewer routine cycles. Normal/frightened throughput becomes 51.93/54.61 FPS; short attract loses 0.60 FPS, while longer mixed workloads improve. Frees 325 resident bytes; 48 tests and VICE pass. See [measurements](GHOST_STATE.md). |
| 2026-11-02 | Prototype shared-column ghost precomposition, including overlapping actors and colours. | Rejected after user review found no significant difference in the flicker itself. Normal/frightened throughput falls to 29.28/34.32 FPS. Preserve the experiment for reference; the faster main binaries were already restored. See [findings](GHOST_PRECOMPOSITION.md). |
