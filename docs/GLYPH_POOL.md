# Accepted glyph-pool renderer

Implemented 2026-11-04 after the user requested trying idea 1 from
[IDEAS.md](IDEAS.md). The user subsequently played it live and accepted it:
“oh yes that is a massive difference. that's perfect.” The user also reports
noticeable slowdown at times and wants redraw-speed optimization next.
**The standard build uses this renderer with all five accepted speed
improvements**, now measured at 27.46 redraws/s. See the
[sprite composition improvement](POOL_STAMP_OPTIMIZATION.md) for the current
build and validation. The measurements below describe the original pool.

```sh
make run
```

Controls are the same: arrow keys, **5** for a coin, **1** to start.
`make run-glyph-pool` launches the original accepted pool before the speed
improvements. `make run-legacy` launches the previous underlay renderer.
All use the same NTSC +3K and
BLK1/2/3/5 configuration, artwork and 16,875-cycle arcade clock.

The [20-second comparison](../build/glyph-pool/evaluation/glyph-pool-comparison.mp4)
was recorded before acceptance and shows actual VICE raster frames: the former
underlay baseline on the left, the now-accepted pool renderer on the right.
Each side displays its executable hash, game tick and measured redraw
rate. The input sequence is identical per logical tick; rendering runs at its
natural cadence. Poses are not retimed. The video has no audio.

## Result

Two fresh captures each contain 1,200 consecutive VIC frames, covering 19.889
seconds between the first and last samples. The capture verifies all 33,792
depacked bytes against its own executable snapshot. No guest code is patched
and no PC gate, timer change or raster scheduling is used.

| Measurement | Previous underlay renderer | Accepted glyph pool |
| --- | ---: | ---: |
| Actual completed redraws/s | 32.88 | **22.07** |
| Completed redraws in capture interval | 654 | 439 |
| Mean redraw interval | 30.41 ms | 45.34 ms |
| 95th percentile interval | 51.08 ms | 68.07 ms |
| Longest interval | 65.81 ms | 83.82 ms |
| Native mean full refresh cost | 12,186 cycles | 18,966 cycles |
| Native maximum input-service gap | 38.51 ms | 45.72 ms |
| Native maximum audio-service gap | 35.18 ms | 41.16 ms |

The native replay checks 1,207 matching game states for each program. Native
throughput is 32.94 versus 22.13 redraws/s; these CPU measurements are separate
from the actual video rates above. The logical movement/audio sequence is
preserved, but lower presentation cadence and longer service gaps are costs.

| Actor | Previous: present / partial / absent / excluded | Pool: present / partial / absent / excluded |
| --- | --- | --- |
| Pac-Man | 781 / 70 / **171** / 178 | 1,005 / 20 / **0** / 175 |
| Blinky | 683 / 18 / **198** / 301 | 894 / 8 / **0** / 298 |
| Pinky | 619 / 30 / **201** / 350 | 834 / 17 / **0** / 349 |
| Inky | 753 / 31 / **157** / 259 | 926 / 16 / **0** / 258 |
| Clyde | 735 / 25 / **119** / 321 | 879 / 10 / **0** / 311 |

There are no fully absent actor samples among the classified pool cases on
this route. Partial poses remain. Clipping, shared colour cells, reward-slot
expansion and insufficient distinct ink remain excluded. Similar coverage
helps the comparison, but this is not a claim that all flicker or colour clash
is gone. A slower, held pose can be more continuously visible while motion
becomes less smooth. Fresh baseline counts differ slightly from the earlier
[display profile](DISPLAY_PROFILE.md) because raster phase varies.

The pool adapter passes 423 settled-picture oracles, classifies 1,695 settled
actors as present, and detects 1,695 deliberately absent plus 1,695 partial
offline controls. It reports no false disappearance on settled images. The
fresh baseline passes 616 settled-picture oracles and 4,978 controls.

**Decision after live play testing:** accept and promote the glyph pool.
The user finds the visible improvement worthwhile despite the slowdown. The
approximately 33 redraws/s target was missed; that measurement remains valid,
but the user's acceptance supersedes the earlier automatic-promotion gate.
Preserve this visible continuity while improving speed. An incremental pool
would need a separately costed design; do not assume a renderer rewrite is the
first or cheapest follow-up.

## Next speed optimization

Rebucket the retained `final-cpu/active.profile` by the existing assembler
routine boundaries. These are exclusive instruction costs divided by 441
completed native refreshes, not additional inclusive timings:

| Pool work | Mean cycles per refresh |
| --- | ---: |
| Cell lookup/allocation and clean-home copying | **6,493** |
| Generic shifted stamping | 4,350 |
| Pose/palette preparation | 2,297 |
| Publication and transaction control | 1,551 |
| Preshifted normal-ghost stamping | 778 |
| Four-cell pointer setup | 767 |

These categories do not include the remaining background/refresh code or IRQ
entry, so they need not sum to the full 18,966-cycle mean refresh cost.

**First candidate:** tighten address calculation and the fixed 16-byte home
copy in `pool_cell`, retaining both banks and finished-cell publication. Measure
the complete refresh on the same input replay, alongside the existing pixel
oracles and visibility capture. The 6,493 cycles are the cost of the whole
allocation/copy category, not a promise that all of it can be removed.
Only 49 resident bytes and 19 BLK5 bytes remain; prefer changes that also save
code space. Keep the full stack, safe-reuse guard, artwork and arcade clock.
No follow-up speed change was included in the acceptance checkpoint. The first
[address-calculation trial](POOL_ADDRESS_OPTIMIZATION.md) is now available with
`make run-pool-address`: about 3.5% more actual redraws/s than the original
pool, which remains available for comparison.

The second [empty-row trial](POOL_SKIP_EMPTY.md) adds a two-byte branch to the
generic stamper, avoiding pixel work for an empty source row. Built on the
address trial, it reaches **23.21 actual redraws/s**, another **1.8%** on the
saved route, with identical settled pixels. Try `make run-pool-skip-empty`.
Both changes are now included in the standard build, together with the
[sound-effect improvement](SOUND_EFFECT_OPTIMIZATION.md) and
[ghost tunnel lookup](TILE_ADDRESS_OPTIMIZATION.md) and
[generic sprite composition](POOL_STAMP_OPTIMIZATION.md), reaching 27.46
actual redraws/s on the saved route.

## What changes

The old renderer saves backgrounds, restores dirty actors from those underlays,
then repaints the actors into the live character canvas. The pool retains clean
home glyphs. It copies the needed home cells into an undisplayed bank, ORs all
six drawing slots into those cells in the existing priority order, then switches
the screen codes. Old-only cells return to their home codes afterwards.

The first prototype uses **one transaction for the whole six-slot picture**.
This avoids overlap-group discovery and deferred-pose bookkeeping. It also
recomposes unchanged actors, which is a substantial cost compared with the
accepted dirty-actor renderer. There is no full background shadow and no
underlay save/restore in this build.

Each first cell allocation copies all 16 clean bytes. Actors sharing that cell
find and stamp the same pending glyph. Final colour follows the existing actor
priority. Clean background colours live on an unused part of onboard colour
RAM; background edits update the physical colour only for unoccupied cells.
This is necessary pool background bookkeeping, not a continuation of the
stopped colour-publishing trial.

The assembler retains the existing mask/palette selection and normal-ghost
preshifted body path. Other frames use a shifted generic stamper, including
frightened bodies, eyes, revised Pac-Man masks and reward halves. A tagged
lookup in spare colour nibbles replaces a linear pending-cell search. Tags
are cleared before generation reuse, including wraparound.

Code and colour publication are separate stores. Several character cells
cannot change atomically. The captured partial poses are consistent with this
remaining limitation; the technique does not guarantee an atomic whole actor.

## Memory and capacity

This implements the candidate in [the memory audit](GLYPH_POOL_FEASIBILITY.md),
with the following concrete allocations. Expansion RAM remains invisible to
the VIC; only existing onboard RAM supplies the pool.

| Range | Use |
| --- | --- |
| $0200–$02C3 | Existing 196-cell matrix |
| $02C4–$02FB | Existing dirty/rebuild/bulk state |
| $0300–$0307 | Eight virtual output flags |
| $0314–$0319 | Preserved IRQ/BRK/NMI vectors |
| $0320–$0328 | Nine pool-state bytes |
| $0340–$037F | Sound registers plus the full 64-byte sound-reset footprint |
| $0380–$03DF | Two 48-byte lists: cell index and final colour |
| $03F8–$03F9 | Preserved random index |
| $0400–$0FFF | Existing game/background state; four pose arrays use $0F80–$0FB7 |
| $1000–$1C3F | 196 clean 8×16 home glyphs |
| $1C40–$1DBF | Bank A: codes 196–219 |
| $1DC0–$1F3F | Bank B: codes 220–243 |
| $1F40–$1FEF | Eleven unused pool glyphs |
| $1FF0–$1FFF | Clipped-column sink, never placed in the matrix |
| $2000–$7D0E | Resident code/data, leaving 49 bytes before the stack |
| $7D40–$7FFF | Full 704-byte C stack, top $8000 |
| $A000–$BFEC | BLK5 tables/code, leaving 19 bytes |
| $9400–$94C3 | 196 clean background colour nibbles |
| $94C4–$9587 | 196 lookup low nibbles |
| $9600–$96C3 | Existing live display colours |
| $96C4–$9787 | 196 lookup high/tag nibbles |

Six slots × at most four cells require **24 pending glyphs**. A separate bank
retains at most 24 displayed glyphs during composition. Thus the maximum is
48, plus the permanent clipped sink. The eleven other codes are not needed to
make this bound work. Teleports and appearances cannot enlarge a slot's pending
8×12 footprint; rewards already expand into the same six output slots. All
actors publish together, so there are no indefinitely deferred overlap groups.

All pending glyphs are complete before the first new matrix store. Old-only
references are removed before retiring the previous bank. Before the next
composition, a fixed guard executes at least 72 cycles, longer than a full
65-cycle scanline. The VIC-I fetches a matrix code and its character byte on
successive fetch cycles, repeating matrix fetches on each scanline; see
[VICE's VIC-I fetch implementation](https://raw.githubusercontent.com/VICE-Team/svn-mirror/main/vice/src/vic20/vic-cycle.c).
The guard conservatively outlasts a fetched old code before its bank can be
overwritten. It is not a wait for a chosen raster position. IRQs can lengthen
the guard. Consecutive direct renderer calls are covered too.

Pool state, lists, full stack reservation and resident limits have linker
assertions. The RNG stays at $03F8. Startup clears only the eight output flags
and 64 sound bytes, not the 256-byte C structure's padding. The assembly sound
copy follows the relocated sound range. No blanket clear touches the vectors.

## Validation and reproduction

- Initial **52 underlay-build checks**, **31 pool checks**, and **10 classifier checks**
  pass. The pool tests adapt fixture addresses and read pixels through the
  matrix; raw home glyphs are checked separately. Removed underlay-kernel tests
  are replaced by pool bounds and generation-reuse checks.
- Independent scene oracles cover frames, shifts/flips, clipping, overlapping
  actors, eyes, frightened states, reward priority, background edits and flashes.
  A full-bank test alternates 24-cell poses with disjoint old/new footprints
  over several lookup-generation wraps, without game-loop delays.
- Native smoke reaches all three intermissions and 7,193 logical ticks, with
  IRQ and stack guards intact. The relocated stack observer excludes loader
  padding and measures from $8000. Observed software use is 32 bytes; that
  observation is not a proof of maximum use or a reason to shrink the stack.
- Actual VICE screenshots and the comparison preview were visually inspected.
  No physical-hardware play test has been performed.
- Promotion extends the pool suite with loader/stack, font and ghost-state
  checks. The current `make test` also includes the later pool checks and
  sound-equivalence checks; see [validation](VALIDATION.md). `make test-glyph-pool`
  checks the original pool, and `make test-legacy` preserves the old underlay
  checks. Default PRG, labels, native image and profiler map select the accepted
  optimized build.

```sh
make test-glyph-pool
python3 tests/display_profile.py
python3 tools/arcade/profile_game.py --prg build/glyph-pool/pacman.prg --map build/glyph-pool/pacman.map --output build/glyph-pool/new-cpu
python3 tools/arcade/measure_display.py --prg build/glyph-pool/pacman.prg --output build/glyph-pool/new-vice --frames 1200
python3 tools/arcade/analyze_display.py --capture build/glyph-pool/new-vice
```

Use a fresh directory for each capture. The adapter recovers background ink
directly from clean home glyphs, reads the displayed bitmap through matrix
codes, and observes pending poses at `pool_publish` before any publication.
Old poses come from earlier render/complete snapshots. Settled oracles and
synthetic controls validate the adapter without guest timing overhead.

Frozen identities, metrics and checks are in
[baselines/glyph-pool.json](baselines/glyph-pool.json). Raw captures/profiles are
under `build/glyph-pool/evaluation/{baseline,final}-{cpu,vice}`. Recreate the
labelled video with:

```sh
python3 tools/arcade/compare_display.py --baseline build/glyph-pool/evaluation/baseline-vice --trial build/glyph-pool/evaluation/final-vice --output build/glyph-pool/evaluation
```

The former underlay PRG, reproducible with `make legacy`, has SHA-256
`9fb85cf61add5d729142183a48285041a47e55fa0f0fd16043f0d15b2aae35af`.
The original accepted pool PRG, retained as `build/glyph-pool/pacman.prg`, has SHA-256
`0d33d3747809a302d400ef530ac7abd599e46c267b9181f7e752fc6f1f778fe5`.
Live user play testing accepted this renderer on 2026-11-04. Further speed
work started from this checkpoint. The standard PRG now has SHA-256
`480fa052510ac687a9477e4da305d9e1accb6aaeb39d77c7d444e63a51d315c5`.
