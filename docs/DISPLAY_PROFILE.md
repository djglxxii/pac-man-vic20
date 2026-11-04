# CPU and display profile

Measured 2026-11-04, before another rendering change. **The accepted game really
does display missing actors, and its redraw timing is also uneven.** Both need
to be measured when judging the next experiment. The game executable, artwork,
logic clock and memory configuration were unchanged during this work.

This completes the outstanding objective diagnostic from
[the ideas follow-up](Response%20to%20IDEAS_REPLY.md.md). The earlier
[matched-cadence comparison](RATE_MATCH.md) is a separate completed diagnostic.
These baseline measurements do not establish how much any rejected experiment
would improve visible flicker at equal throughput.

## Workload and identity

- Accepted hires renderer, revised Pac-Man masks and current fonts.
- NTSC VIC-20, +3K and BLK1/2/3/5 enabled; existing period-correct hardware target.
- Same saved joystick route used for the active renderer comparisons, indexed
  by logical tick. No level, pellet, movement, timer or CPU-register patches.
- VICE 3.7.1 records **1,200 consecutive raster frames**, approximately 20 seconds,
  at its native 60.28 Hz. Every image is a lossless RGB PNG from the actual
  raster drawing buffer, sampled at line 1, cycle 0–7.
- All **33,792 depacked program bytes** match an independently executed loader.
  All 1,206 active VICE input/game-state observations match the saved trace.
- A separate native CPU replay checks 1,207 matching active states. Native timing
  and VICE frame results are reported separately; their raster phases differ.

PRG SHA-256:
`9fb85cf61add5d729142183a48285041a47e55fa0f0fd16043f0d15b2aae35af`.
Native image SHA-256:
`d138600dae9a681b612830a6ea58f1ed136f0afb144c18e7d60acc902d86ace8`.

## CPU cost

Host-only instruction counts and routine-entry/return observations add no guest
instructions. The active native sample lasts 19.916 seconds and completes
656 redraws, **32.94 calls/s**. Percentages below partition elapsed CPU cycles;
interrupt work is charged to the phase it interrupts.

| Phase | CPU time |
| --- | ---: |
| Game logic, tasks and loop work, including original sound generation | 53.02% |
| Rendering | 39.25% |
| VIC audio conversion | 5.73% |
| Waiting | 2.01% |

Original sound-channel processing accounts for **8.08%** of the total, within
the first row. The two ghost-state calls per logical tick account for **17.50%**,
including their callees, also within that row. These are overlapping breakdowns,
not additional costs to add to the table.

| Drawing phase | Mean cycles/call | Mean ms/call |
| --- | ---: | ---: |
| Mark actor changes and dependencies | 1,834 | 1.793 |
| Mark and restore old actors, including the preceding row | 4,203 | 4.109 |
| Apply queued background edits | 1,639 | 1.603 |
| Paint actors and assign colours | 6,307 | 6.167 |
| Entire refresh | 12,186 | 11.915 |

The generic paint kernel averages 1,148 cycles per actor call; the pre-shifted
ghost kernel averages 667; restoration averages 369. Kernel figures exclude
frontend setup, scanning and colour work. Inclusive routine figures must not
be added to their parents. Full per-section self costs, hottest instructions
and routine distributions are saved in the CPU summary.

For 2,737 matching actor updates, the CPU work window from erase entry to paint
return averages **7.731 ms**, reaches **14.353 ms at the 95th percentile**, and
peaks at **20.847 ms**. This is an exposure window, not a count of visible blinks.
It comes from this active route, not the less demanding opening benchmark.

Only 2% waiting time remains in this workload. Raster waiting therefore cannot
be treated as free time; the rejected trials already demonstrated its cost.

## Actual displayed frames

VICE completes **654 redraws over the 19.889-second counter interval**, or
**32.88 redraws/s**. These are completed renderer calls, not unique movement poses.

| Actor | Present | Partial or mixed | Absent | Excluded | Absent / classified frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pac-Man | 781 | 75 | 165 | 179 | 16.16% |
| Blinky | 656 | 17 | 227 | 300 | 25.22% |
| Pinky | 646 | 19 | 187 | 348 | 21.95% |
| Inky | 724 | 31 | 185 | 260 | 19.68% |
| Clyde | 718 | 39 | 122 | 321 | 13.88% |

Every row totals 1,200. Percentages use only the classified frames. The exclusions
are not random samples, so these percentages are **not estimates for every
actor in every situation**. They describe this route under the stated rules.

Pac-Man's 165 missing samples form 157 observed absence runs: 149 last one
captured frame, eight last two. That is 7.89 observed runs per second across the
whole counter interval. Excluded frames interrupt runs, so this is a descriptive
count rather than a precise perceptual blink rate. The machine-readable results
also provide rates per classified exposure time and counts for each ghost.

[Consecutive real frames and enlarged actor regions](../build/display-profile/current/vice/evidence.png)
show Pac-Man present in frame 10, absent in frame 11, and present in frame 12.
Frames 1–3 similarly bracket a partial sprite. Only the outlines and labels are
annotations; the game pixels come directly from the recording.

## Motion and cadence

Completed-redraw intervals in the VICE capture average **30.41 ms**, with a
**51.08 ms 95th percentile** and **65.81 ms maximum**.

| Logical ticks between completed redraws | Observed intervals |
| --- | ---: |
| 1 | 240 |
| 2 | 281 |
| 3 | 126 |
| 4 | 6 |

Displayed movement is measured separately, only when a complete actor mask gives
an unambiguous position. Missing, partial or excluded frames interrupt that
series; positions are never inferred across them.

For uninterrupted identifiable Pac-Man samples, movement-change intervals are
1, 2, 3 and 4 VIC frames, observed 36, 75, 32 and 7 times respectively. Measured
position changes are usually one VIC pixel, but include two-, three- and
four-pixel steps. These are selected visible sequences, not the entire route.
Ghost motion distributions include intended movement/pauses and coordinate
rounding as well as redraw cadence; they do not isolate performance judder alone.

## Classification and checks

The offline classifier reads the actual compiled sprite masks and records old
and new renderer caches, underlays, bitmap and colours at refresh entry, paint
entry and completion. The underlays recover clean backgrounds in reverse paint
order. Powered-up Pac-Man's slot swap is accounted for.

For each displayed frame it considers the last completed pose and all poses
prepared during that scan. Wall/dot pixels and other actors cannot supply
evidence that the actor is present. An exact identifiable old or new mask is
present, no identifiable ink is absent, and an incomplete or mixed mask is
partial. At least 12 distinctive pixels across four rows are required for
every candidate pose. This measures sprite ink independently of its hue.

Shared colour cells, clipped actors, hidden/empty masks and insufficient
distinctive ink are excluded. Horizontal reward pauses exclude the whole frame
because the expanded actor-slot mapping needs another classifier. Death,
rebuild and flash scenes would also be excluded. Colour mismatch counts cover
fully identified actors outside shared cells; they do not quantify all colour
clash, which is most likely in those excluded cells.

Checks completed:

- Nine host-tool tests cover full old/new poses, absence, partial/mixed masks,
  wall false positives, shared cells, clipping, hidden actors, motion gaps and
  non-overlapping CPU phase accounting, and rejection of missing/duplicate frames.
- All **616 eligible completed snapshots** exactly match background plus sprite
  masks. Another 58 completed snapshots are reward exclusions.
- On these settled snapshots, 2,489 identifiable actor cases produce **zero false
  absences or partials**. The 591 other actor cases are explicitly excluded.
- Offline controls deliberately remove all or half the distinctive actor ink:
  all **2,489 missing and 2,489 partial controls** are detected. These edits affect
  analysis sets only; the recorded game remains unmodified.
- PNG hashes, raster positions, one-frame capture spacing and game-state parity
  are checked. A pilot exposed a coincident-breakpoint capture omission; the
  capture tool now samples any breakpoint in the raster window and rejects
  missing-frame recordings during analysis. The authoritative run has no gaps.
- The actual missing/partial frame examples were inspected visually.
- Rebuilding leaves the accepted PRG and native-image hashes unchanged.

This is emulator evidence for one NTSC active-play route. It has not been
validated on physical hardware or PAL, and does not cover every game state.

## What the next change must demonstrate

There is evidence for both real disappearance and uneven motion. The baseline
does not prove one dominates the user's perception. Another optimization should
be tried individually on this same trace, with the same artwork and classifier,
and report missing/partial counts alongside natural redraw rate and intervals.

The drawing cost and the roughly 14% combined original sound-channel/VIC audio
work are concrete places to inspect. A finished-cell pool remains an option,
but still needs a cycle and memory budget before a renderer rewrite. No such
rewrite or audio change is included in this profiling task.

## Reproduction and artifacts

Use a new output directory for another capture; existing recordings are retained.

```sh
make all tools/vicsim/vicsim
python3 tests/display_profile.py
python3 tools/arcade/profile_game.py --output build/display-profile/new/cpu
python3 tools/arcade/measure_display.py --output build/display-profile/new/vice --frames 1200
python3 tools/arcade/analyze_display.py --capture build/display-profile/new/vice
```

Both replay tools accept `--input` to select a recording with per-tick inputs;
their default is the retained matched-cadence input trace. `--prg` selects a
program/label pair. CPU profiling also accepts its matching `--map` file.

The authoritative artifacts are under `build/display-profile/current/`:
`cpu/summary.json`, instruction profile and trace, frozen PRG/labels/map;
`vice/recording.json`, `memory.zip`, all 1,200 lossless frames, captured tables,
`actors.json`, `analysis.json`, and `evidence.png`. The separate `pilot/` and
`capture-with-drop/` directories are superseded diagnostic runs, not the results
above. The compact [baseline record](baselines/display-profile.json) preserves
metrics, checks and hashes in the repository.
