# Research optimization plan

**Current direction, 2026-11-04:** live play testing accepted the
[glyph-pool renderer](GLYPH_POOL.md) as a large visible improvement. The user
reports occasional slowdown and accepts the speed tradeoff. The twelve speed
improvements below are now accepted as the standard build: `make run` launches
the pool with faster addressing, empty-row skipping and optimized sound-effect
processing, plus faster ghost tunnel lookups, sprite composition and
precomputed VIC pitches, the compact audio adapter and a common-state ghost
dispatch fast path, cheaper pool cell allocation, faster background-tile
drawing, precomputed sprite preparation and cheaper destination setup, measured
at **33.64 actual redraws/s**.
Preserve the accepted appearance and sound in
further work. The stopped colour investigation remains stopped.

The [remaining optimization candidates](#remaining-optimization-candidates)
below are the current work queue. Its first [ghost-state experiment](TILE_ADDRESS_OPTIMIZATION.md)
is accepted after live review, as is the first
[glyph-composition experiment](POOL_STAMP_OPTIMIZATION.md). Both are included
in the standard build. The [unchanged-display opportunity measurement](POOL_REUSE_MEASUREMENT.md)
is complete; persistent reuse is deferred pending a costed design. VIC audio
translation is now profiled, and the [exact pitch lookup](AUDIO_DIVIDER_OPTIMIZATION.md)
is accepted after live review and included in the standard build. The earlier investigations and
implementation lists are historical context.

The [background-tile drawing follow-up](TILE_STAMP_OPTIMIZATION.md) is accepted
and promoted to the standard: **32.21 actual redraws/s**, about **2.1%** above
the preceding cell-allocation build. It saves 143–147 cycles per visible tile
with no additional memory allocation. `make run-tile-stamp-fast` preserves
this intermediate version. Its improved actual redraw/audio gaps, slightly larger
maximum input gap and remaining partial poses are documented in the report.

**Latest accepted build:** [cheaper destination setup](POOL_DEST_OPTIMIZATION.md)
is accepted and promoted at the user's request. `make run` and
`make run-pool-dest-fast` select the same version: **33.64 actual redraws/s**,
about **1.1%** above sprite preparation alone. It avoids redundant pointer
initialization and adds no tables or state. Headroom remains 141 resident /
23 BLK5 bytes with the full stack. Maximum captured redraw gap grows slightly,
61.28 → 61.51 ms, and partial poses remain. See the
[promotion evidence](baselines/pool-dest-promotion.json).
`make run-pool-setup-fast` preserves the preceding 33.29 build.

**Next experiment:** reduce the first shift in five generic sprite kernels
from a zero-page read/modify/write to an accumulator shift. The baseline
profile puts generic composition at 11.33% of CPU time and its shift kernels
at 3.06%. Expected isolated saving is three cycles per nonempty row in shifts
1, 2, 3, 6 and 7, with five fewer code bytes and no new RAM. Keep this behind
`POOL_SHIFT_FAST`, measure exact kernel outputs/cycles and whole-game throughput,
and provide a separate runnable trial before promotion. Persistent caching
and redraw pacing remain deferred.

| Original idea | Current disposition |
| --- | --- |
| 1. Finished-cell glyph pool | [Accepted after live play testing](GLYPH_POOL.md) and promoted to default. Initially 22.07 versus 32.88 underlay redraws/s; the twelve accepted speed improvements below now reach 33.64. No fully absent actors among classified capture cases. Same hardware and full stack. |
| 2. Write-once compositing with a full background shadow | No assigned home for the 3,136-byte shadow under the current memory target; the other agent withdrew this fallback. |
| 3. Raster lock / beam scheduling | Several trials rejected after user review and throughput loss. Preserve the 16,875-cycle arcade clock. |
| 4. Pacing / partial updates | Measured uneven cadence remains relevant; partial updates need coherent displayed poses and shared-cell handling. No fixed-rate or IRQ-renderer rewrite is started. |

The [glyph-pool result](GLYPH_POOL.md) and [frozen measurements](baselines/glyph-pool.json)
record the original accepted baseline and its cost. Its cell
allocation/addressing/home-copy work, measured at about 6,493 cycles per native
redraw, motivated the first speed improvement. Incremental pool allocation
remains a larger design question.

**First speed follow-up:** the [pool address trial](POOL_ADDRESS_OPTIMIZATION.md)
now saves 36 cycles per fresh allocation and improves actual capture throughput
from 22.04 to 22.80 redraws/s (about 3.5%). It retains the accepted visibility
behaviour and passes image/gameplay/long-run checks. `make run-pool-address`
preserves this intermediate build; its changes are included in the standard
build. See the report and
[frozen measurements](baselines/pool-address.json) before choosing another step.

**Second speed follow-up:** the [empty-row trial](POOL_SKIP_EMPTY.md) builds on
the address trial and reaches **23.21 actual redraws/s**, about **1.8%** more,
or **5.3%** above the accepted pool on the saved route. One two-byte branch
avoids mirroring, shifting and destination writes for an empty source row.
Per-half checks were measured and dropped because their overhead lost time on
the live route. Image/gameplay/long-run checks pass; `make run-pool-skip-empty`
preserves this intermediate build; its changes are included in the standard
build. See the report
and [frozen measurements](baselines/pool-skip-empty.json) for limits and costs.

**Third speed follow-up:** the [sound-effect trial](SOUND_EFFECT_OPTIMIZATION.md)
replaces the profiled effect interpreter with assembly, retaining its shared
frequency/volume tail and the existing VIC converter. Actual capture improves
from **23.21 to 25.67 redraws/s**, about **10.6%**. All 7,748 identical-input
effect cases and all 1,639 tick-indexed sound-state/VIC-register comparisons
match the predecessor. It reclaims 376 resident bytes. The user accepted this
version, which remains available through `make run-sound-effect-fast`; its
changes are included in the current standard build. Profiling, image/gameplay
checks and all intermissions pass. See the report and
[frozen results](baselines/sound-effect-fast.json), including
remaining partial poses and an increased maximum input-service gap on this
sample. The user's current sound is the reference for further work.

**Fourth speed follow-up:** the [ghost tunnel lookup](TILE_ADDRESS_OPTIMIZATION.md)
replaces repeated maze-metadata addressing with a bounded assembly lookup and
64 bytes of column tables. Actual capture improves **25.67 → 26.44 redraws/s**,
about **3.0%**, while all 528 ghost fixtures, 1,207 active replay states and
1,639 sound-register ticks match the predecessor. It reclaims 73 resident
bytes and retains the full stack and existing hardware. The user accepted
the live result and requested promotion. Its changes remain in the standard;
`make run-tile-address-fast` retains this intermediate binary. See the
report and [frozen evidence](baselines/tile-address-fast.json), including
remaining partial poses and the slightly larger maximum audio-service gap.

**Fifth speed follow-up:** [generic sprite composition](POOL_STAMP_OPTIMIZATION.md)
reduces shifts, temporary byte transfers and row-counter work without new
graphics tables or writable scratch. All 10,496 identical-input sprite cases
match the independent pixel oracle and use fewer cycles. Actual capture
improves **26.44 → 27.46 redraws/s**, about **3.9%**, at a cost of 64 resident
bytes. Gameplay, sound and all intermissions pass. The user accepted the live
result and requested promotion; its changes remain in the standard build.
`make run-pool-stamp-fast` retains this intermediate version. Its longest captured redraw interval grows
68.54 → 74.87 ms and partial poses remain. See the report and
[frozen evidence](baselines/pool-stamp-fast.json) for the complete tradeoffs.

**Sixth speed follow-up:** the [exact VIC pitch lookup](AUDIO_DIVIDER_OPTIMIZATION.md)
precomputes the nearest divider for the common frequency grid, retaining the
original calculation for all other inputs. Actual capture improves
**27.46 → 28.84 redraws/s**, about **5.0%**. All 65,536 frequency inputs and
1,639 replayed sound ticks match. Mean audio translation falls from 968 to
646 cycles per tick. The user accepted the live result and requested promotion;
its changes remain included in the standard. `make run-audio-divider-fast`
retains this intermediate version.
The 256-byte resident increase leaves **141 bytes** before the full stack.
See the report and [frozen evidence](baselines/audio-divider-fast.json).

**Seventh speed follow-up:** the [compact audio adapter](AUDIO_UPDATE_OPTIMIZATION.md)
replaces C register unpacking, saturating pitch scaling and output bookkeeping
with assembly using existing caller scratch. Actual capture improves
**28.84 → 29.81 redraws/s**, about **3.4%**, and mean audio cost falls
**646 → 393 cycles per tick**. All 524,288 frequency/shift pairs per build,
1,639 sound ticks and 1,207 game states match. The user accepted the live result
and requested promotion; `make run-audio-update-fast` retains this intermediate version.
Resident headroom stays 141 bytes; BLK5 free space grows to 151 bytes. The
longest captured redraw gap grows **58.53 → 61.04 ms** and partial poses remain.
See the report and [frozen evidence](baselines/audio-update-fast.json).

**Eighth speed follow-up:** the [common-state ghost dispatch fast path](GHOST_UPDATE_OPTIMIZATION.md)
bypasses no-op death/returning-state handlers when all six relevant state bytes
are zero. Movement and state-transition order remain unchanged. Actual capture
improves **29.81 → 30.78 redraws/s**, about **3.3%**, and mean ghost processing
falls **1,376 → 1,249 cycles/call**. All 2,458 identical-input fixtures match
the original Z80 and predecessor; gameplay, sound and intermissions pass.
The user accepted the result and requested promotion. `make run-ghost-update-fast`
retains this intermediate version, whose changes are included in the standard.
It left resident headroom at **109 bytes**;
BLK5 retains **151 bytes** and the full 704-byte stack remains intact.
The longest redraw gap grows **61.04 → 63.43 ms** and partial poses remain.
See the report, [frozen measurements](baselines/ghost-update-fast.json) and
[promotion evidence](baselines/ghost-update-promotion.json).

**Ninth speed follow-up:** [cheaper cell allocation](POOL_ALLOC_OPTIMIZATION.md)
removes repeated relative/absolute slot conversions and the cell save/reload.
Every identical-input allocation saves 24–25 cycles and each overlap hit saves
3 cycles. Actual capture improves **30.78 → 31.55 redraws/s**, about **2.5%**,
while alignment recovers 32 resident bytes. Gameplay, sound and intermissions
pass. The user accepted live play testing and requested promotion;
`make run-pool-alloc-fast` retains this intermediate version, whose changes
remain included in the standard. Resident/bank headroom is **141/151
bytes**, with the full stack and existing hardware retained. See the report,
[frozen measurements](baselines/pool-alloc-fast.json) and
[promotion evidence](baselines/pool-alloc-promotion.json).

**Tenth speed follow-up:** [faster background-tile drawing](TILE_STAMP_OPTIMIZATION.md)
replaces six per-row calls and pointer increments with an indexed walk. Every
visible identical-input tile saves 143–147 cycles. Actual capture improves
**31.55 → 32.21 redraws/s**, about **2.1%**, with the same 141/151-byte
resident/bank headroom and full stack. Gameplay, pixels, sound and intermissions
pass. The user accepted live play testing and requested promotion;
`make run-tile-stamp-fast` preserves this intermediate build. See the report,
[frozen measurements](baselines/tile-stamp-fast.json) and
[promotion evidence](baselines/tile-stamp-promotion.json).

**Eleventh speed follow-up:** [precomputed sprite preparation](POOL_SETUP_OPTIMIZATION.md)
packs regular-atlas source pointers and classes into 64 two-byte descriptors.
Actual capture improves **32.21 → 33.29 redraws/s**, about **3.3%**. The
128-byte read-only table leaves **141/23 bytes** resident/BLK5 headroom with
the full stack. The maximum captured redraw gap grows **55.74 → 61.28 ms**.
Gameplay, pixels, sound and intermissions pass. The user accepted live testing
and requested promotion: `make run-pool-setup-fast` preserves this intermediate build.
See the report, [frozen measurements](baselines/pool-setup-fast.json) and
[promotion evidence](baselines/pool-setup-promotion.json).

## Remaining optimization candidates

Recorded on **2026-11-04**, after promotion of the sound-effect build. These
five candidates preserve the discussion's proposed order. Candidate 1's first
experiment, the [tunnel lookup](TILE_ADDRESS_OPTIMIZATION.md), is accepted and
included in the standard build. Candidate 2's first
[composition experiment](POOL_STAMP_OPTIMIZATION.md) is also accepted and
promoted. Candidate 3's [opportunity measurement](POOL_REUSE_MEASUREMENT.md)
is complete, with implementation deferred; candidate 4's pitch lookup is
accepted and included in the standard build, and candidate
4's unpacking/scaling follow-up is also accepted and standard. Candidate 5 remains
deferred. Candidate 1's second experiment, a
[common-state dispatch fast path](GHOST_UPDATE_OPTIMIZATION.md), is also
accepted and included in the standard. Candidate 2's
[cell-allocation follow-up](POOL_ALLOC_OPTIMIZATION.md) is also accepted and
included. Candidate 2's [background-tile follow-up](TILE_STAMP_OPTIMIZATION.md)
is accepted and included. Candidate 2's
[sprite-preparation follow-up](POOL_SETUP_OPTIMIZATION.md) is accepted and
included. Candidate 2's [destination-setup follow-up](POOL_DEST_OPTIMIZATION.md)
is also accepted and standard at **33.64 actual redraws/s**.
The next bounded experiment targets accumulator-first generic shift kernels.
Update this queue after each experiment
with its result, evidence link and accepted, rejected or deferred status.

### Current measurement baseline

Use the accepted [destination-setup build](POOL_DEST_OPTIMIZATION.md) and its
[frozen measurements](baselines/pool-dest-fast.json). The `native.trial`
and `actual_vice.trial` entries describe the standard `build/pacman.prg`:

- Actual VICE throughput: **33.64 redraws/s**, with **45.44 ms** at the 95th
  percentile and **61.51 ms** maximum between completed redraws on this route.
- Native replay: **46.59%** logic/tasks, **50.92%** rendering, **2.32%** VIC
  audio translation and **0.16%** waiting. These phase percentages are separate
  from the actual VICE throughput measurement.
- Generic stamping uses **11.33%** of native CPU time, including **3.06%**
  in shift kernels and **2.24%** in row control. The normal-ghost stamper is
  separate at **2.51%**.
- Resident headroom is **141 bytes** before the full **704-byte stack**.
  BLK5 has **23 bytes free**. Hardware remains NTSC with +3K and BLK1/2/3/5.

These are one saved workload's measurements, not worst-case guarantees.
Raw native evidence is under `build/pool-dest-fast/evaluation/trial-cpu/`.
The generated files are ignored by Git; the frozen record retains compact
measurements and their identities.

| Order | Candidate | Status | First investigation |
| --- | --- | --- | --- |
| 1 | Ghost-state and movement processing | Tunnel lookup and common-state fast path accepted; included in standard | [Faster tunnel lookup](TILE_ADDRESS_OPTIMIZATION.md): 25.67 → 26.44. [Common-state fast path](GHOST_UPDATE_OPTIMIZATION.md): 29.81 → 30.78 actual redraws/s, about 3.3%; now standard. |
| 2 | Faster glyph composition and background drawing | Generic stamping, allocation, background tiles and sprite preparation and destination setup accepted; accumulator shifts next | [Faster generic stamping](POOL_STAMP_OPTIMIZATION.md): 26.44 → 27.46. [Cheaper allocation](POOL_ALLOC_OPTIMIZATION.md): 30.78 → 31.55. [Background tiles](TILE_STAMP_OPTIMIZATION.md): 31.55 → 32.21. [Sprite preparation](POOL_SETUP_OPTIMIZATION.md): 32.21 → 33.29. [Destination setup](POOL_DEST_OPTIMIZATION.md): 33.29 → 33.64 standard, same headroom, slightly longer maximum gap. |
| 3 | Reuse unchanged display content | [Measured; persistent cache deferred](POOL_REUSE_MEASUREMENT.md) | 25.51% of fresh cells repeat previous pixels/colour; conservative same-hidden-slot reuse covers 14.64%, or 8.99% in redraws with changing coordinates. Copy-only ceiling 1.28% total CPU before checks. |
| 4 | Cheaper VIC audio translation | [Pitch lookup](AUDIO_DIVIDER_OPTIMIZATION.md) and [adapter follow-up](AUDIO_UPDATE_OPTIMIZATION.md) accepted; both included in standard | Standalone audio adapter reaches 29.81 actual redraws/s, about 3.4% above the pitch lookup alone; later ghost/rendering work reaches 33.64. All 524,288 frequency/shift pairs per build and 1,639 sound ticks match. Current resident/bank headroom: 141/23 bytes. |
| 5 | More consistent redraw pacing | Deferred until processing headroom is demonstrated | Measure redraw deadlines and held poses before considering a scheduling change. |

**Previous accepted experiment:** candidate 2's [background-tile writer](TILE_STAMP_OPTIMIZATION.md)
removes six per-row calls and pointer increments. All 17,408 identical-input
cases per build match; visible tiles save 143–147 cycles. Actual VICE throughput
improves **31.55 → 32.21 redraws/s** with the same 141/151-byte resident/BLK5
headroom and full stack. Gameplay, sound, settled images and intermissions pass.
The maximum input gap grows slightly; partial poses remain. The user accepted
live review and requested promotion; `make run-tile-stamp-fast`
preserves this intermediate version. Persistent caching and pacing rewrites remain deferred.

**Latest accepted experiment:** candidate 2's
[sprite preparation](POOL_SETUP_OPTIMIZATION.md) replaces regular-atlas class
unpacking and source-pointer arithmetic with 64 two-byte descriptors. All
8,768 identical-scene cases per build match; regular-atlas scenes save 18–123
cycles, while eyes/reward halves cost 5–6 more. Actual throughput improves
**32.21 → 33.29 redraws/s**. The 95th-percentile redraw interval and native
input/audio gaps improve; maximum actual gap grows **55.74 → 61.28 ms**.
The code shrinks nine bytes but the table consumes 128 BLK5 bytes: 141 resident
and 23 BLK5 bytes remain, with the full stack. All 1,207 game states, 1,639
sound ticks, pooled checks and intermissions pass. The user accepted live
review and requested promotion: `make run` and `make run-pool-setup-fast`
launch the same version. The [promotion record](baselines/pool-setup-promotion.json)
identifies the default artifacts and regression checks.

### 1. Ghost-state and movement processing

Before the tunnel lookup, `updateGhostStates_1017` and its callees used
3,566,603 of 20,371,620 native cycles across 2,414 calls, averaging 1,477 cycles
per call. The tunnel build uses 3,326,515 of 20,360,911 cycles across the same
2,414 calls, averaging 1,378 cycles per call. This includes
movement, collision checks and state handling; it is not all ghost steering.
The [earlier ghost optimization](GHOST_STATE.md) already simplified speed-mask
rotation/testing. Inspect the remaining repeated calculations, pointer work,
dispatch and compiler overhead rather than repeating that completed change.

First isolate the expensive operations, then compare identical-input results
and cycles for a single proposed change. Preserve update count/order, speed
patterns, collision decisions, RNG, house/death transitions and arcade timing.
Use the existing original-ROM ghost comparisons and active gameplay replay;
reducing how often ghosts update is outside this candidate.

**Second experiment accepted and standard:** a fresh baseline profile measures
ghost updates at **16.31%** of native CPU time, or **1,376 cycles/call** including
callees/IRQs. The [common-state fast path](GHOST_UPDATE_OPTIMIZATION.md) bypasses
no-op death/ghost-state dispatch only when all six relevant states are zero.
All movement, collisions, house-release work and nonzero transitions retain
their original ordering. The predicate succeeds on 2,210 of 2,414 native calls.

Actual VICE throughput becomes **29.81 → 30.78 redraws/s**, about **3.3%**;
native throughput becomes 29.93 → 30.94. Mean ghost processing falls to
**1,249 cycles/call**, a **9.27%** reduction, with the same call count.
All 2,458 identical-input fixtures match both the original Z80 and predecessor;
1,207 active replay states, 1,639 sound ticks and all intermissions pass.
The guard saves 139–142 cycles on zero-state fixtures but adds 21–23 on
nonzero-state fixtures. Resident headroom falls **141 → 109 bytes**, with
151 bytes still free in BLK5 and the full 704-byte stack retained.

Both fresh captures contain 1,180 consecutive VICE raster frames and verified
PRGs. The 95th-percentile redraw interval improves 50.24 → 48.65 ms, while
the maximum grows 61.04 → 63.43 ms and maximum native input gap grows
38.31 → 41.72 ms. Partial poses remain and vary in both directions. This does
not prove fixed 30 Hz pacing or perceptible flicker reduction. The user accepted
the result and requested promotion; `make run-ghost-update-fast` retains it,
and its changes remain included in the latest standard. See the report,
[frozen evidence](baselines/ghost-update-fast.json)
and [promotion checks](baselines/ghost-update-promotion.json).

**First experiment accepted:** the [tunnel lookup](TILE_ADDRESS_OPTIMIZATION.md)
replaces repeated maze-metadata addressing with a bounded assembly lookup and
64 bytes of column tables. All 528 identical-input ghost fixtures match the
ROM, all 1,207 active replay states match, and all 1,639 sound-register ticks
match the predecessor. Actual capture improves **25.67 → 26.44 redraws/s**, with
the full stack and existing hardware retained. Live review accepted the result;
its changes remain included in the standard, and `make run-tile-address-fast`
retains the measured intermediate version. See the
[frozen evidence](baselines/tile-address-fast.json), including remaining partial
poses and the slightly larger maximum audio-service gap on this route.

### 2. Faster glyph composition and background drawing

Rendering remains a large cost at 50.92% of native CPU time. Investigate the
remaining clean-background copies, cell/pointer setup and generic shifted
stamping used by Pac-Man, frightened ghosts, returning eyes and rewards.
The address optimization, empty-row skip and first composition improvement
are already included; their old before/after costs must not be counted as
remaining savings.

Rebucket the current profile and benchmark a bounded kernel before adding
special cases or tables. Retain both pool banks, finished-cell publication,
safe glyph reuse, overlap composition, colour priority and accepted artwork.
Compare complete refresh cost as well as kernel cycles: setup and code-size
costs can erase an inner-loop saving.

**First experiment accepted:** [generic sprite composition](POOL_STAMP_OPTIMIZATION.md)
uses direct shift dispatch, fewer temporary byte transfers and the source
index as the row counter. Rebucketed baseline costs identify generic stamping
at 4,019 cycles per redraw, home copying at 3,246 and cell lookup/allocation at
2,466. The unchanged copy is already unrolled. All 10,496 identical-input
sprite cases pass and are faster, averaging 13.8% fewer cycles; generic work
per native redraw falls to 3,435 cycles. Actual capture improves **26.44 →
27.46 redraws/s**, about **3.9%**, at a cost of 64 resident bytes. Gameplay,
sound and all intermissions pass. The maximum captured redraw interval grows
68.54 → 74.87 ms and partial poses remain. Live review accepted the result;
its changes remain included in the standard, and `make run-pool-stamp-fast`
retains this intermediate version. See the report and
[frozen evidence](baselines/pool-stamp-fast.json) before selecting another
change; candidate 3's measurement is documented below.

**Second experiment accepted and standard:** [cheaper cell allocation](POOL_ALLOC_OPTIMIZATION.md)
keeps the relative slot for its lookup nibbles and adds the bank offset only
once. All 392 identical-input allocations save 24–25 cycles, and all 392
existing-cell hits save 3 cycles. Background copying remains unchanged at 209
exclusive cycles per fresh cell. The allocator shrinks by 16 code bytes;
alignment recovers 32 resident bytes, raising headroom from 109 to 141 with
the full stack retained and no new storage.

Actual VICE throughput improves **30.78 → 31.55 redraws/s**, about **2.5%**.
The 95th-percentile and maximum actual redraw intervals improve 48.65 → 47.21
and 63.43 → 56.02 ms. Maximum native input gap improves 41.72 → 37.07 ms,
but the audio gap grows 36.85 → 38.67 ms and maximum native refresh grows
28,783 → 30,307 cycles. All 1,207 active game states, 1,639 sound ticks, 41
pooled checks and all intermissions pass. Partial poses remain and vary in
both directions; this is not a fixed 30 Hz or perceptible flicker claim.
The report and [frozen evidence](baselines/pool-alloc-fast.json) retain the
comparison. The user accepted live review and requested promotion;
`make run-pool-alloc-fast` retains this intermediate version, whose changes
remain in the standard. The
[promotion checks](baselines/pool-alloc-promotion.json) identify the then-default
artifacts and validation; the frozen trial status remains historical evidence.

**Third experiment accepted and standard:** the
[background-tile writer](TILE_STAMP_OPTIMIZATION.md) targets the accepted build's
1,129 tile calls, whose own instructions use 4.41% of native CPU time. The
already-unrolled clean-home copy stays unchanged. One indexed loop now writes
the six tile rows, replacing per-row calls and pointer increments. All 17,392
visible cases save 143–147 cycles; the sixteen clipped corners are unchanged.
Independent pixels/guards and accumulated colour/wall outputs match across
17,408 cases per build. The routine shrinks by one byte, while alignment leaves
resident and BLK5 headroom at 141/151 bytes with the full stack intact.

Actual throughput improves **31.55 → 32.21 redraws/s**, about **2.1%**; native
throughput improves 31.80 → 32.37. Actual 95th-percentile/maximum redraw gaps
improve 47.21 → 46.45 and 56.02 → 55.74 ms. Maximum native audio gap improves
38.67 → 37.32 ms, but maximum input gap grows 37.07 → 37.29 ms. All 1,207 game
states, 1,639 sound ticks, 41 pooled checks and all intermissions pass. The
actual capture verifies 1,180 consecutive frames and 607 settled snapshots;
partial poses remain, with no fixed-rate or perceptible flicker claim.
The report and [frozen evidence](baselines/tile-stamp-fast.json) retain the
comparison. The user accepted live review and requested promotion;
`make run-tile-stamp-fast` preserves this intermediate version. The
[promotion checks](baselines/tile-stamp-promotion.json) identify the default
artifacts and regression results; the frozen trial status remains historical.

**Fourth experiment accepted and standard:** the
[sprite-preparation improvement](POOL_SETUP_OPTIMIZATION.md) isolates the preceding build's
7.29% actor-preparation and 2.42% destination-setup costs. It changes only
regular-atlas metadata preparation. Each relocated two-byte descriptor packs
the source pointer and class into the pointer's unused low bits. The packed
original class table is retained for the independent actual-display observer;
separate eyes and score-half source calculations remain intact.

Mean actor preparation falls **2,302 → 1,833 cycles/native redraw**, about
20.4%; destination setup remains unchanged on identical inputs. Full native
throughput becomes 32.37 → 33.39, and actual VICE becomes 32.21 → 33.29.
All 8,768 independent scene oracles per build pass, along with the 41 pooled
checks, exact game/sound replays and three intermissions. Both real captures
contain 1,180 consecutive frames with verified executable images. The trial
passes 628 settled-picture oracles and 5,090 synthetic absent/partial controls;
partial poses remain, with no eligible fully absent actor. Maximum captured
redraw gap grows to 61.28 ms, so the average gain is not a fixed-rate claim.

The 128-byte descriptor table leaves only 23 bytes in BLK5, versus 151 in the
previous build. Resident headroom stays 141 and the full 704-byte stack is preserved.
See the report and [frozen evidence](baselines/pool-setup-fast.json) before
considering another table. The user accepted live review and requested promotion;
`make run-pool-setup-fast` preserves this intermediate version. The
[promotion checks](baselines/pool-setup-promotion.json) identify the default
artifacts and regression results. Persistent caching and pacing remain deferred.

**Fifth experiment accepted and standard:** the
[destination-setup trial](POOL_DEST_OPTIMIZATION.md) targets the latest
standard's 2.50% exclusive setup cost. It assigns real pointers directly,
uses sinks for clipped columns, and leaves unreachable bottom-pointer scratch
alone at row offsets 0–4. Allocation/publication order and both stampers stay
unchanged. All 8,768 complete-scene oracles per build match; 5,634 save 1–30
cycles and 3,134 are unchanged. Another 10,496 generic-kernel cases per build
point unused bottom pointers at guards and pass with identical kernel timing.

Native destination setup falls **765.41 → 629.64 cycles/redraw**; actual VICE
throughput becomes **33.29 → 33.64 redraws/s**. Resident code grows eight
bytes within alignment slack, leaving the same 141 resident / 23 BLK5 bytes
and full stack. The first 16-byte-growth draft was slower because two loops
crossed pages; it was rejected, and the smaller final version keeps both loops
within pages without padding. Exact game/sound replays, pooled checks, settled
images and all intermissions pass. Maximum actual redraw and native input gaps
grow slightly, and several partial-pose counts increase. See the
[frozen evidence](baselines/pool-dest-fast.json). `make run-pool-dest-fast`
and `make run` select the accepted version at the user's request. The
[promotion record](baselines/pool-dest-promotion.json) identifies the default
artifacts and checks. The next experiment targets generic shift kernels;
persistent caching and pacing remain deferred.

### 3. Reuse unchanged display content

Explore avoiding composition when a cell's final pixels and colour would be
unchanged. The [opportunity measurement](POOL_REUSE_MEASUREMENT.md) is complete;
no runtime cache or performance gain has been demonstrated. The persistent
cache is deferred; candidate 4's bounded pitch lookup is now accepted and standard.

Unchanged actor position alone is insufficient: animation masks, colour,
other actors sharing the cell, pellets, score/background edits and maze
flashes can all require recomposition. Moving actors still require their
affected cells to update. Define old/new footprints, displayed poses,
invalidation and pool-capacity/reuse rules before implementation. Do not
recompose a displayed glyph in place without proving visibility is preserved.

**Measurement result:** 2,136 of 8,374 fresh cells (25.51%) repeat their previous
displayed pixels and colour. Only 1,226 (14.64%) also match conservative
pose/home/shared-cell dependencies at the same physical hidden slot. That
falls to 703 of 7,816 cells (8.99%) in redraws with changing actor coordinates.
Their copy-only ceiling is 477 cycles per redraw, 1.28% of sample CPU time,
before checks; moving-redraw copy opportunity is about 296 cycles per redraw.
Whole-stamp savings remain unmeasured. Only 31 entire pictures repeat, 30
while a reward score is visible; eight other unchanged-pose redraws still
have background changes. A whole-picture early exit mainly helps pauses on
this route. Preserve the [frozen evidence](baselines/pool-reuse.json) and design
requirements before revisiting implementation. That measurement used a 397-byte
resident budget; the current accepted cell-allocation build leaves 141 bytes.

### 4. Cheaper VIC audio translation

The [audio profiling and pitch-table report](AUDIO_DIVIDER_OPTIMIZATION.md)
separates the preceding converter's costs: divider search uses 372 cycles per
tick, saturating scaling 276, unpacking 93 and other work the remainder of
968 total cycles including IRQs, or 5.74% of native CPU time. This is separate
from the already-optimized effect interpreter. All 1,893 active-play divider
inputs are multiples of 128; a per-voice last-pitch cache gets zero active-play
hits on this route.

**First experiment accepted and included in standard:** the pitch lookup
uses a 256-byte table for that full input grid and retains the exact original calculation for
other pitches, with a five-cycle fallback overhead. All 65,536 input values
match. Mean audio cost falls **968 → 646 cycles per tick**, and actual capture
improves **27.46 → 28.84 redraws/s**, about **5.0%**. All 1,639 replayed sound
ticks match, gameplay/image checks and intermissions pass, and the full stack
and hardware target remain intact. Resident headroom falls from 397 to
**141 bytes**. `make run-audio-divider-fast` retains this intermediate version.
Preserve the [frozen evidence](baselines/audio-divider-fast.json) and
[promotion checks](baselines/audio-divider-promotion.json).

**Follow-up accepted and standard after live review:** the [assembly adapter](AUDIO_UPDATE_OPTIMIZATION.md)
replaces register unpacking, saturating scaling and output bookkeeping with
compact code using existing caller scratch. `make run-audio-update-fast`
retains this intermediate version. Mean complete audio cost
falls **646 → 393 cycles/tick** and actual capture improves
**28.84 → 29.81 redraws/s**, about **3.4%**.
All **524,288 frequency/shift pairs per build** match, as do 1,639 sound-replay
ticks and 1,207 game states. Gameplay, settled-picture and intermission checks
pass. Resident headroom stays **141 bytes**, while BLK5 free space grows from
24 to **151 bytes**. The longest redraw gap increases **58.53 → 61.04 ms**,
maximum input-service gap increases **37.55 → 38.31 ms**, and partial poses
remain. The current default includes this adapter and the later ghost-update,
cell-allocation, background-tile and sprite-preparation improvements. The audio promotion record also distinguishes a subsequent concurrent
death-frame artwork rebuild. Preserve the
[frozen evidence](baselines/audio-update-fast.json) and
[promotion checks](baselines/audio-update-promotion.json). Another table or cache
requires a new cost/memory measurement.

The accepted sound is the reference. Preserve channel mapping, waveform
approximation, pitch rounding/saturation, volume, enable/disable behaviour
and sequencing. Reuse the tick-indexed sound-state/VIC-register replay to
check exact values; this work must not change timbre or reduce audio service
frequency. Register equivalence does not prove identical write timestamps
or replace a listening check.

### 5. More consistent redraw pacing

Investigate scheduling only after measuring enough headroom for the desired
deadlines. A 33.64 redraws/s average does not establish a sustainable fixed
30 Hz display. Compare held poses, movement intervals, longest redraw gaps
and input/audio service delays as well as average throughput.

Partial updates would need coherent displayed poses and complete shared-cell
composition. Snapshots or IRQ rendering require explicit background-state
and scratch/reentrancy ownership. Preserve the 16,875-cycle arcade logic
clock; this candidate does not reopen rejected raster-wait/beam-priority
trials or authorize moving drawing into an IRQ.

### Evaluation and decisions

Complete one experiment at a time. Record the baseline/trial binary hashes,
identical-input routine cycles, full-program native profile, actual VICE
redraw rate and interval distribution, input/audio service gaps, memory cost
and relevant gameplay/sound equivalence results. Rendering changes also need
settled-pixel and present/partial/absent actor checks. Keep partial-pose and
classifier exclusions visible when reporting results.

Preserve the accepted visuals and sound, period-correct hardware, full stack
and arcade behaviour. Prefer bounded changes before a renderer redesign.
Provide a separate runnable build for live review and document the decision
before promoting it. Rejected colour/raster work and the paused multicolour
redesign remain outside this queue.

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
