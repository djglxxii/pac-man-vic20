# Finished-cell publishing: feasibility and benchmark plan

**Acceptance update, 2026-11-04:** the user played and accepted the pool as a
large improvement, acknowledging occasional slowdown. The
[whole-frame, two-bank renderer](GLYPH_POOL.md) now fits the memory
layout and passes the pixel, capacity, reuse, gameplay and long-run checks.
Its real capture has no fully absent classified actors, but only 22.07 versus
32.88 previous redraws/s. The user accepts that tradeoff; the glyph pool is now
the default. The initial throughput target remains a future objective.
The next bounded candidate is allocation/addressing/home-copy work, not an
automatic full renderer rewrite. The initial proposal below is design history.

Prepared 2026-11-04 after the CPU/display profiling discussion. This document
preserves the proposed next experiment and the qualifications from the earlier
ideas review. The original plan is retained below as design history. The
focused [stable-colour trial](STABLE_COLOURS.md) is now implemented separately;
the user reports no perceptible improvement despite the throughput cost. It is
not accepted. It has not been combined with the accepted pool renderer.

**Current scope:** the user has stopped the colour investigation and requested
trying idea 1. The whole-frame renderer is complete and accepted after live
play testing despite its speed cost. The colour preflight below is historical evidence, not
an active task. Neither an incremental colour-ownership rewrite nor further
fruit diagnosis is scheduled.

## Objective and current decision

Reduce visible actor disappearance while retaining the original conversion's
arcade behaviour, responsiveness and accepted artwork. The user likes the
original game and accepts much of its colour clash; excessive flicker is the
main reason for this investigation.

The recommended next experiment is a **small, separate finished-cell publishing
benchmark**. Compose an entire 8×16 character in a glyph that is not displayed,
then publish its screen code. Measure memory and complete transaction cost before
attempting live-game integration. A full renderer replacement is not the first
deliverable.

A focused review from the other agent would be useful. The question proposed
in conversation was:

> Can this fit the existing VIC-visible RAM and reduce missing frames without
> lowering throughput?

The profiling supplies an actionable target, not evidence that this particular
renderer design will succeed. Another agent's review is useful input; it has
not occurred for these findings and is not a prerequisite to writing this plan.

## Historical preflight: stable colour ownership — stopped

The user reports stationary red fruit and the surrounding white walls appearing
to alternate between red and white. This investigation preceded the larger
renderer experiment and has now been stopped at the user's request. The report
was reproduced and measured independently in
the [stable-colour trial](STABLE_COLOURS.md): the focused colour metric improves,
but actual redraw throughput falls from 32.88 to 29.77/s. User review finds no
perceptible improvement and reports continued flashing. The follow-up in that
report records the unresolved case and a possible incremental ownership design;
neither a new design nor a CPU saving is established. Steps below record scope.

The current source provides a plausible mechanism: `restore_actor` restores saved
cell colours, and `sprite_drawn` later writes the actor's colour to those cells
again. Stationary actors can still be marked dirty through conservative
background-band invalidation or another actor's overlapping old/new footprint.
The final painted result already gives an actor its colour ahead of background
walls. Reordering that final priority alone would not eliminate a transient
white-to-red restoration/repaint cycle.

The user's clarification is to use a general, inexpensive rule rather than
fruit/wall exceptions: **background colour has the lowest priority; actors use
the existing actor drawing order**. White is the normal maze/pellet fallback,
not an intrinsically low-priority palette value. A white actor, such as returning
ghost eyes, must still participate in actor priority. Other background artwork
keeps its own fallback colour, and completion flashing keeps its accepted rule.

First examine whether colour restoration can be separated from pixel restoration
so that an affected cell receives its resolved final colour without intermediate
background or lower-priority actor colours. Reuse the existing draw order and
affected actor footprints; avoid a new fruit classifier, per-pixel colour tests,
full-screen scan or elaborate priority table. Any needed temporary cell state,
underlay bookkeeping and extra cycles still need an explicit budget. The last
actor leaving a cell must restore its background; simply refusing white writes
would leave stale actor tints and mishandle white actors.

The first investigation should:

1. Capture fruit with no nearby actor, then with Pac-Man/ghosts passing nearby.
   Trace the affected physical colour cells, their writes and raster phases,
   actor dirty reasons, and the actual displayed frames. Distinguish temporary
   restoration from a genuinely changing final colour owner. Fruit is one
   diagnostic case; also capture ghost-only sharing and white returning eyes.
2. Evaluate retaining the resolved cell colour while its owner remains present,
   including through bitmap refreshes. Preserve existing actor overlap priority
   initially. Use background colour only when no actor claims the cell, and
   change actor colour when ownership legitimately changes. Walls/pellets sharing
   an actor-owned cell take that actor's colour while it owns the cell. One hires
   8x16 cell cannot display both foreground colours simultaneously.
3. Preserve white standing pellets wherever no actor shares their hardware cell,
   and the accepted blue/white completion flash. Check fruit appearance/removal,
   pellet edits, frightened/eyes states, borrowed reward slots and rebuilds.
4. Account for saved-underlay colour correctness: retaining live colours must
   not cause an actor to save its own colour as the background or leave a tint
   behind. Merely skipping stores equal to the current colour would not prevent
   a white-then-red cycle when both stores change it.
5. Compare actual colour transitions and throughput against the unchanged game.
   The existing visibility classifier excludes shared-colour cells and cannot
   by itself validate this improvement. Colour stability and missing actor
   pixels need separate measurements; improving one does not prove the other.

The focused trial is playable but user review reports no perceptible benefit.
It preserves final priority and removes measured intermediate colour pulses,
at a cost of roughly 3.1 actual redraws/s. It establishes no significant
reduction in actor disappearance. Preserve this negative review alongside the
numeric result; do not promote it or assume another colour rewrite will help.

## Baseline to preserve

Commit **`ae55528`**, “Checkpoint revised sprites, renderer trials and display
profiling,” contains the accepted source, research history and profiling tools.
Its working tree was clean after the commit. This plan is subsequent work.

| Identity | Value |
| --- | --- |
| Branch at checkpoint | `optimization/sprite-kernels` |
| Default program | `build/pacman.prg`, launched by `make run` |
| PRG SHA-256 | `9fb85cf61add5d729142183a48285041a47e55fa0f0fd16043f0d15b2aae35af` |
| Native image SHA-256 | `d138600dae9a681b612830a6ea58f1ed136f0afb144c18e7d60acc902d86ace8` |
| Hardware target | NTSC VIC-20, +3K and BLK1/2/3/5: +35 KiB expansion |
| Logical clock | 16,875 CPU cycles per arcade tick |
| VIC frame | 16,965 CPU cycles: 65 cycles × 261 lines |

The authoritative findings are in [DISPLAY_PROFILE.md](DISPLAY_PROFILE.md) and
[baselines/display-profile.json](baselines/display-profile.json). Local raw
artifacts are under `build/display-profile/current/`; `build/` is ignored by Git.
Preserve these files when starting another run. `pilot/` and `capture-with-drop/`
are superseded runs; use `cpu/` and `vice/` for the recorded baseline.

### Actual VICE output

The 1,200-frame active joystick replay completes **654 redraws over 19.889
seconds: 32.88 completed redraws/s**. The capture cadence is approximately
60.28 VIC frames/s. Completed redraws are not unique movement poses.

| Actor | Present | Partial/mixed | Absent | Excluded | Absent / classified |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pac-Man | 781 | 75 | 165 | 179 | 16.16% |
| Blinky | 656 | 17 | 227 | 300 | 25.22% |
| Pinky | 646 | 19 | 187 | 348 | 21.95% |
| Inky | 724 | 31 | 185 | 260 | 19.68% |
| Clyde | 718 | 39 | 122 | 321 | 13.88% |

Pac-Man has 157 observed absence runs: 149 of one captured frame and eight
of two frames. Exclusions interrupt runs, so this is not a precise count of
human-perceived blinks. Percentages apply to classified samples on this route;
excluded cases are not a random sample of the game.

Completed-redraw intervals average **30.41 ms**, reach **51.08 ms at the 95th
percentile**, and peak at **65.81 ms**. Intervals span one, two, three and four
logical ticks, observed 240, 281, 126 and six times respectively.

[The frame evidence](../build/display-profile/current/vice/evidence.png) shows
Pac-Man present → absent → present in consecutive actual raster frames. Both
real disappearance and uneven cadence are established. Their relative
contribution to the user's perception has not been established.

### Separate native CPU profile

| Phase | Share of elapsed cycles |
| --- | ---: |
| Logic/tasks/loop, including original sound generation | 53.02% |
| Rendering | 39.25% |
| VIC audio conversion | 5.73% |
| Waiting | 2.01% |

Within logic/tasks, original sound-channel processing uses 8.08% of the total
and ghost-state calls use 17.50%, including callees. These are subdivisions of
the first row, not additional CPU time.

Mean complete refresh cost is **12,186 cycles / 11.915 ms**. Marking and restoring
actors uses 4,203 cycles, including 1,834 for marking; background edits use
1,639; painting and colour work use 6,307. These are means, not guaranteed
per-frame budgets. The native replay completes 32.94 redraws/s; its timings
must remain separate from the actual VICE capture rate above.

The native erase-entry-to-paint-return window averages **7.731 ms**, with
**14.353 ms p95** and **20.847 ms maximum**. This is CPU exposure time, not
direct visibility measurement. Only 2% idle time remains on this workload,
so additional raster waiting cannot be assumed to be free.

## Constraints carried forward

- Preserve arcade movement, ghost rules/patterns, collisions, RNG, scoring,
  input service, sound sequencing and the 16,875-cycle logical clock.
- Keep the current 112×216 hires presentation, maze topology, revised Pac-Man
  walking/death masks, shared closed-mouth frame, and approved fonts/rewards.
- Keep standing pellets white where possible. The accepted maze is white;
  completion flashes blue/white. A return to blue walls is a separate visual
  proposal, not part of this benchmark.
- Use the existing period-correct RAM configuration. Extra expansion RAM does
  not create extra VIC-visible glyph RAM. Any future hardware change needs
  contemporary hardware evidence and a separate decision.
- Keep the original renderer available for comparison (`make run-legacy`).
  The user-accepted glyph pool is now the default; future speed trials should
  preserve that accepted version while under evaluation.
- Work on one experiment at a time. Audio/gameplay improvements remain future
  work; this proposal must not become another open-ended graphics rewrite.

The user previously considered results **above 30 FPS worth a play test**.
For this experiment, report actual completed redraws and displayed motion
separately. The target is to preserve approximately **33 redraws/s on the active
trace**. The play-test preference does not make a throughput regression an
accepted improvement. Record any tradeoff and let play testing determine its value.

## Lessons from previous experiments

The [temporary-character trial](GHOST_SHADOW.md),
[independent actor commits](ACTOR_COMMIT.md),
[actor-speed trial](ACTOR_SPEED.md) and
[raster-priority revisit](BEAM_PRIORITY.md) remain important reference points.
Preserving character bits or shortening CPU erase windows has repeatedly
failed to produce a worthwhile visible improvement at the resulting speed.
Raster-priority work was explicitly dropped after user review.

The [matched-cadence comparison](RATE_MATCH.md) did look better to the user;
the later natural-speed actor trial was less convincing. These results support
measuring throughput and visibility together. They do not prove which mechanism
accounts for the improvement or guarantee that a pool will be faster.

The proposed pool differs from wrapping the existing renderer in temporary
copies: clean home glyphs could replace underlay save/restore. The benchmark
must identify the work actually removed as well as the new work introduced.

## Proposed model and unresolved rules

Each screen cell has a clean **home glyph**, while actor-covered cells refer
to composed glyphs from a pool. The home mapping is column-major:
screen index `r * 14 + c` maps to glyph code `c * 14 + r`. Restoration must use
that mapping, not assume that screen index equals glyph code.

Maintain distinct logical target poses and currently displayed poses. When an
update is deferred, the displayed pose remains the composition source for other
cells and actors. Actors sharing old/new character cells form an overlap group;
dependencies must include shared colour ownership and background edits.

The earlier [ideas follow-up](Response%20to%20IDEAS_REPLY.md.md) proposed this
transaction sequence, which still requires implementation and verification:

1. Determine the whole group's old/new cell set and reserve enough capacity
   before changing the display. Include every displayed actor needed to compose
   those cells, in the existing priority order.
2. Prepare a complete new-footprint cell in an undisplayed glyph. Publish its
   screen code, then its foreground colour. Retire its previous pool glyph
   according to the verified hardware reuse rule.
3. Settle old-only cells after the new footprint is published. If an actor
   remains there, compose its displayed pose; otherwise restore the home code
   and home colour. Release resources only when safe.
4. If capacity is insufficient, defer the whole group and keep its old pose
   visible. Track deferrals and displayed-pose age. Prove forward progress so
   insufficient capacity cannot cause indefinite deferral.

Screen code and colour are separate live writes. Code-first publication was
proposed to avoid recolouring an empty cell before actor bits appear. Verify
all colour transitions, including an old foreground colour of black. A glyph
containing an actor can still be visually invisible with the wrong colour.

Publishing several cells is not an atomic actor update. Mixed old/new parts,
trails, colour mismatches or tearing may remain. **Do not promise blink-free
output from a single screen-code store.**

Also establish when a retired glyph can safely be overwritten. A screen matrix
that no longer references it may not be sufficient proof if the VIC has already
fetched or latched its old code. Check the hardware fetch behaviour and actual
VICE raster output. Any required retirement delay or quarantine must be counted
in the pool capacity and cycle budget. This is an open question, not a claim
that immediate reuse is safe or unsafe.

Background edits must update both home data and any displayed composition that
depends on it, with a coherent colour rule. Start by preserving the accepted
progressive-rebuild behaviour: actors may remain absent until the rebuild
finishes. Keeping them visible through rebuilds is additional work outside the
first benchmark.

## Stage 1: prove a complete memory layout

The [initial memory audit](GLYPH_POOL_FEASIBILITY.md) now identifies a candidate
with 60 pool glyphs, the full 704-byte stack relocated into BLK3, sparse low-RAM
virtual outputs and a 1,233-byte replacement renderer/data budget. It is not a
completed feasibility proof: metadata, retirement and capacity/progress remain
open. No pool code or new linker configuration has been implemented.

Produce an address-level table from the current linker map before allocating
the pool or implementing a new rendering path.

| Current range/resource | Constraint |
| --- | --- |
| `$0200–$02C3` | 196-byte screen matrix |
| `$0320–$03F7` | Six 36-byte underlays; 216 bytes reclaimed only if replaced |
| `$0400–$07FF` | Live logical screen after startup |
| `$0800–$0BFF` | Live logical colour attributes |
| `$0C00–$0EFF` | Arcade state and actor outputs |
| `$0F00–$0FFF` | Dirty bits, caches and maze/flash metadata |
| `$1000–$1C3F` | 196 home glyphs × 16 bytes = 3,136 bytes |
| `$1C40–$1D3F` | 256-byte virtual I/O image |
| `$1D40–$1FFF` | Existing non-graphics software-stack area |
| Resident headroom | 315 bytes in BLK1–3; another 15 in BLK5 |

The CPU's stack, zero page, IRQ vectors and other low-RAM allocations also stay
accounted for. The startup clear does not make `$0400–$0FFF` spare RAM.

The shadow trial proved a layout with 24 glyphs at `$1D40–$1EBF` and a 320-byte
software stack above them. Observing only 32 bytes of stack writes in smoke
tests did not prove a safe maximum for a new renderer.

Moving virtual I/O could expose another 16 glyphs. Removing underlays plus the
315 resident bytes gives 531 bytes in separate regions before replacement code
and metadata; it is a candidate resource, not an approved relocation. Audit
every fixed-address I/O access, code-size change and runtime lifetime.

Six 8×12 drawing slots can cover up to 24 cells for one pose. Retaining old and
new footprints can require up to 48 cells before additional scratch or retired
glyph requirements. A smaller bound needs a proof tied to the actual transaction
order. The follow-up's incremental proposal counts displayed cells, newly
pool-backed cells for the current group, and a transient glyph; account for
any additional hardware reuse delay before relying on that bound.

Deliverables: pool bounds, allocation/release algorithm, code and metadata
bytes, stack reservation, initialization/overlay lifetimes, linker assertions,
and explicit handling of allocation failure. If no safe layout fits, record
that result before attempting live integration.

## Stage 2: benchmark complete transactions

Build an isolated prototype with the current hires art and a settled-picture
oracle. Compare it with equivalent existing-renderer work on the same inputs.
Measure discovery/grouping, allocation, copying home cells, stamping every
overlapping actor, colour selection, publication, retirement and background
maintenance. Report full-path costs; a 16-byte copy timing alone is insufficient.

Start with isolated actor motion within a footprint and across a cell boundary,
then add overlap and a background edit to test the proposed cost savings. The
fixture matrix to complete across the benchmark and later integration is:

- One actor moving within a footprint and crossing horizontal/vertical cell
  boundaries; every shift, flip and relevant animation frame.
- Several independent moving actors and all six drawing slots occupied.
- Shared cells, crossings, transitive overlap groups, mixed dirty/unchanged
  actors, and old-only cells still occupied by another displayed actor.
- Pellets/HUD edits, actor visibility changes, tunnel clipping, frightened
  ghosts, returning eyes and priority changes.
- Horizontal reward halves and borrowed slots, including powered-up Pac-Man's
  output-slot swap; fruit, death/intermission masks and rebuild/flash entry/exit.
- Capacity exhaustion, repeated deferrals, rapid reuse and relevant raster
  phases, including code/colour and retirement boundaries.

Initial limited fixtures may establish feasibility, but their coverage must be
stated. Report average, tail and worst costs; identify both work saved and work
added. Isolated timings with IRQs masked are useful kernel data and must not be
presented as live-game FPS. Logic/audio consume the same CPU budget in play.

Deliverable: a feasibility report with measured cycles and memory, plus a clear
recommendation to proceed, revise or stop. Only a feasible result justifies
connecting a separate trial to the live game.

## Stage 3: live trial and comparable measurement

For a subsequent live trial, preserve the accepted default and use the same
saved per-logical-tick joystick trace, artwork, clock and game-state checks.
Run naturally; PC gating belongs only to explicitly labelled diagnostics.

The existing tools are:

- [profile_game.py](../tools/arcade/profile_game.py): native cycle profile.
- [measure_display.py](../tools/arcade/measure_display.py): actual lossless VICE
  frames and external state snapshots.
- [analyze_display.py](../tools/arcade/analyze_display.py): visibility and motion
  classification, including exclusions and synthetic controls.
- [display_profile.py](../tests/display_profile.py): host-tool regression checks.

**These tools need a renderer adapter before they can measure a pool correctly.**
Current background recovery reads the six underlays and assumes fixed home
mapping; pose extraction and observation hooks also depend on existing caches
and entry points. A pool changes those assumptions. Export or externally read
equivalent clean backgrounds, displayed poses, pending poses and commit events,
without adding guest timing overhead. Keep the visibility rules comparable.

Require the adapter to pass settled-picture and deliberate absent/partial
controls before using its numbers to claim improvement. Record old/new poses
through intermediate publication and deferral; latest logical positions alone
do not identify the displayed actors.

Repeat the original program's loaded-image verification, lossless PNG hashes,
line-1 sampling and consecutive-frame checks. The earlier capture omission from
coincident breakpoints is fixed; retain the missing/duplicate-frame rejection.
Use unique immutable PRG/label snapshots and clearly labelled artifacts.

## Acceptance and stopping criteria

| Area | Required evidence |
| --- | --- |
| Memory | Complete safe layout; bounded pool, retirement and stack lifetimes; no exotic expansion |
| Correctness | Exact settled pixels/colours and priority; original-ROM/native game-state parity |
| Flicker | Fewer absent/partial samples and shorter absence runs on comparable classified cases |
| Coverage | Report exclusions and comparable actor situations; reduced classifier coverage is not an improvement |
| Throughput | Target the current approximately 33 redraws/s on the active trace; report any loss explicitly |
| Cadence | Compare displayed movement and redraw distributions, including p95/worst gaps against 51.08/65.81 ms |
| Service | Compare input/audio service gaps and tick delivery; derive the baseline gaps from retained traces before judging a trial |
| Whole game | Rewards, clipping, rebuilds, fruit, death and all intermissions; stack/IRQ guards and helper integrity |
| User review | The user plays the distinct trial and finds the benefit worthwhile before default promotion |

Compare fresh baseline/trial runs and repeat when natural raster-phase variation
could explain a small difference. The current snapshot supplies a baseline,
not a variance estimate or a guaranteed minimum frame rate. Raw counts from
different excluded situations cannot establish a win.

Reject or revise a candidate that needs unavailable glyphs, cannot bound reuse,
stalls groups indefinitely, corrupts colour/priority/gameplay, or trades visible
continuity for distracting slower motion. Avoid repeating an experiment based
only on preserved character bits or optimistic cycle estimates. If this avenue
fails its feasibility or visual test, record the result and revisit a measured,
bounded CPU optimization or the planned audio/gameplay work.

## Review handoff and next action

Share this plan, the [profile](DISPLAY_PROFILE.md), [ideas reply](IDEAS_REPLY.md),
[follow-up](Response%20to%20IDEAS_REPLY.md.md), linker map and relevant renderer
sources with the other agent if a review is requested. Ask for:

1. A concrete memory layout and a pool-capacity proof for the commit sequence.
2. A check of foreground-colour publication and safe glyph reuse timing.
3. A complete cost model against the 12,186-cycle mean refresh baseline.
4. Hidden assumptions in overlapping actors, background edits, rewards,
   deferrals and measurement compatibility.

The **stable-colour-ownership preflight is stopped** at the user's request.
The first pool prototype is now complete: [report and play-test command](GLYPH_POOL.md).
Its memory/capacity implementation and visibility improvement are established.
The user accepted its 22.07 redraws/s versus the previous 32.88 after live play
testing; promotion is authorized and complete. Commit the full checkpoint,
then target the 6,493-cycle allocation/addressing/home-copy category first.
A future
incremental-pool proposal must account for retained allocations, displayed poses,
overlap dependencies, retirement and full transaction costs again.
No other agent has been contacted. The hardware target remains unchanged;
the old fruit question does not block this work.
