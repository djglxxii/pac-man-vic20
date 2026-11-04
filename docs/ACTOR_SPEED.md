# Actor-commit throughput trial

Separate NTSC trial on 2026-11-03, requested after the user found the
[matched-cadence actor-commit comparison](RATE_MATCH.md) noticeably better.
It retains independent actor commits and the accepted lettering and reward
layouts while reducing dependency bookkeeping. The normal build remains
unchanged. User review at its natural rendering rate found a possible
improvement, less noticeable than in the initial matched-cadence trial.
The overall benefit remains inconclusive, and this stays a separate trial.

**User visual review (2026-11-03):** "it might be better, honestly not super
noticeable as I thought in the initial trial."

```sh
make run-actor-speed
```

[Before/after: actor-commit reference versus optimized trial](../build/actor-speed/vice/vic20-actor-speed-98929418-vs-b5fa71ca.mp4).
[Normal game versus optimized trial](../build/actor-speed/vice/vic20-normal-eb6b2981-vs-actor-speed-b5fa71ca.mp4).
Each video is 1,200 VIC frames, approximately 20 seconds, with program hashes
in the labels. They are silent and use the current graphics on both sides.

## Measured result

Natural VICE rendering with the same joystick inputs indexed by logical tick:

| Program | Completed renders in the counter interval | Completed renders/s |
| --- | ---: | ---: |
| Current-font actor-commit reference | 525 | 26.40 |
| Optimized actor-commit trial | 548 | 27.55 |
| Unchanged normal game | 659 | 33.13 |

The counter interval is 19.889 seconds. The optimized trial gains **4.38%**
over the actor-commit reference and still trails the normal renderer. This
is partial throughput recovery, not restoration of the normal game's rate.
These figures count completed renderer calls, not unique motion poses.

All three runs have 1,207 matching active-play input/game-state observations.
For the optimized trial, 329 completed render ticks coincide with the
reference, and every corresponding bitmap/foreground-colour hash matches.
For the normal game, all 352 corresponding completed pictures also match.

These captures run naturally: **no program-counter gate or guest code patch**
is applied. Raster phase, render cadence, and completion times vary. The
first sampled logical ticks are 432 for both actor-commit programs and 433
for the normal game, so the videos also have a small initial
pose offset. Compare them as natural playthroughs with the same per-tick
inputs, rather than as identical game-state frames. The subsequent user
review above does not establish that the possible visual benefit outweighs
the remaining throughput penalty. Matching cadence in the earlier comparison
removed that rate difference; it does not establish why the user's
impression changed between trials.

Short native CPU-cycle benchmarks, using the same scene setup for both
current-font actor-commit programs:

| Scene | Reference renders/s | Optimized renders/s |
| --- | ---: | ---: |
| Opening play | 43.99 | 47.28 |
| Frightened | 48.35 | 52.98 |
| Attract chase | 37.18 | 39.31 |
| First intermission | 60.05 | 60.06 |
| Board transition | 42.01 | 41.90 |

Those scene rates are separate from the VICE playthrough rates. The
transition sample includes progressive background construction.

## Profile and retained changes

The active native replay uses the same 1,207 logical ticks as the capture
input trace. Every observed game-state hash matches. Average dependency
bookkeeping falls from **2,385 to 1,770 cycles per completed refresh**, a
25.8% reduction. The reference builds groups on all 526 completed calls;
the optimized replay builds them on 503 of 555 calls, skipping 52 refreshes
with no actor changes. Group construction itself averages 1,953 cycles when
needed, down from 2,385. Native replay rates are 26.43 and 27.88 calls/s;
they are not the VICE capture counts above.

The same replay's mean actor erase-to-paint window stays similar:
**3.672 → 3.638 ms**, with the 95th percentile **10.803 → 10.758 ms**.
Those measure CPU work windows, not exact pixel-fetch timing or perceptual
flicker. The implementation preserves the independent-commit ordering that
motivated this trial.

Changes under `ACTOR_COMMIT_FAST` in [sprites.S](../src/sprites.S):

- Accumulate whether any actor needs repainting during the existing mark
  pass. Skip dependency construction when none does, while still applying
  unrelated queued background edits.
- Initialize bounds directly from valid saved underlays, then extend them
  for the new footprint. Avoid repeated default initialization and writes.
- Skip background-band calculations when there are no dirty bands, and
  exclude actors with neither a new footprint nor an old underlay.
- Walk component membership bits directly when merging. Collect the
  background transaction's membership as groups form, removing a final
  six-actor scan.
- Continue the commit scan after the previous component. Singletons use a
  direct record lookup, and background-only transactions avoid actor scans.

The existing conservative dependency rules, shared-colour priority, old/new
crossings, saved-byte footprints, clipping, and full-rebuild fallback remain
in effect. Main-thread rendering and the 16,875-cycle arcade timer remain
in place.

Both current-font actor-commit programs also classify new footprints from
the expanded renderer cache. The arcade output bytes have already been
restored after cache preparation, so they can mark a newly borrowed reward
slot as hidden. Using those bytes missed a dependency in the reference and
could suppress the new half entirely in the optimized invisible-slot
shortcut. A 64-case regression exercises live reward appearance with an
empty borrowed underlay, both hidden-slot positions, every reward value,
and two horizontal alignments. The normal renderer is unaffected.

## Memory and validation

The accepted font build leaves 315 resident bytes, too little for the old
actor-commit code to remain entirely resident. Both comparison programs
therefore use [actor_commit.ld](../src/actor_commit.ld) to load the grouping
helper through temporary boot RAM and copy it into `$1D40` at startup.
This follows the existing boot-loaded helper approach. Both keep the same
**320-byte software-stack reservation** at `$1EC0–$1FFF`, so the reference
and optimized program share that memory arrangement.

The optimized helper is 361 bytes, ending at `$1EA9` exclusive. Resident
allocation ends at `$7F9B`, leaving 101 bytes in BLK1–3; BLK5 retains 15.
No new metadata region is allocated; the cursor uses an unused cache byte
and the helper reuses renderer scratch. The +3K and BLK1/2/3/5 hardware
configuration is unchanged. Linker assertions bound the helper, its boot
initializer, and the stack reservation.

Validation completed:

- All 15 original-ROM reference checks and all 18 actor-commit checks pass.
  The latter include the current horizontal rewards, frame/shift/flip
  oracle, clipping, incremental redraw, colour dependencies, crossings,
  transitive clusters, and loaded-image checks.
- The smoke run covers 7,179 logical ticks, fruit, and all three
  intermissions. The lower stack guard and IRQ vector remain intact, and
  every scene retains the exact copied helper bytes. Observed software
  stack writes use 32 bytes; this is an observation rather than a maximum
  stack-depth proof.
- VICE verifies all 33,792 depacked program bytes before each recording.
  All 3,600 raster samples are taken at line 1, cycle less than 8. Completed
  pictures at common ticks and game states pass the comparisons described
  above. Both labelled videos contain all 1,200 frames.
- Python syntax checks pass. The preprocessed group helper was also run
  through the assembly cycle counter; full costs above come from measured
  CPU execution, including loops.
- Rebuilding the normal game produces its original SHA-256:
  `eb6b29810453418818a1ffb83f8b0057464a903682c20970cc6019617067a4e9`.

## Reproduction

```sh
make actor-speed-reference actor-speed
make test-actor-speed
python3 tools/arcade/profile_actor_commit.py --prg build/actor-speed/reference/pacman.prg --output build/actor-speed/reference/active
python3 tools/arcade/profile_actor_commit.py --prg build/actor-speed/fast/pacman.prg --state-reference build/actor-speed/reference/active/summary.json --output build/actor-speed/fast/active
python3 tools/arcade/record_actor_speed.py
```

The replay/capture tools use the retained matched-cadence input recording by
default; `--input` can select another recording. The capture also uses the
saved normal-game PRG/label pair under `build/actor-speed/current-baseline/`.
Artifacts, program snapshots, profiles, checks, native reports, and VICE
records remain under `build/actor-speed/`. A compact result and source hashes
are frozen in [the baseline record](baselines/actor-speed.json).
