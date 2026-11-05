# Unchanged-cell reuse: opportunity measurement

Measured on **2026-11-04**. This completes the first measurement for candidate
3 in the [optimization plan](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates).
No game code, renderer, sound, timing or memory allocation changes were made
for this investigation. A runtime cache has not been implemented. The subsequent
[audio pitch lookup](AUDIO_DIVIDER_OPTIMIZATION.md) and later
[ghost-update fast path](GHOST_UPDATE_OPTIMIZATION.md) are accepted and included
in the standard; the later cell-allocation improvement recovers headroom to
141 bytes, compared with 397 in this measurement.

There is redundant work, but the simplest reuse opportunities are much
smaller than the number of identical output cells suggests. This measurement
favoured deferring a persistent cell cache and profiling candidate 4,
VIC audio translation, which has since been completed. These measurements do
not prove that a more involved cache would lose time; its checking and
invalidation costs have not been benchmarked.

## Baseline and method

The source is the accepted [pool-stamp build](POOL_STAMP_OPTIMIZATION.md):

- PRG SHA-256: `480fa052510ac687a9477e4da305d9e1accb6aaeb39d77c7d444e63a51d315c5`.
- Loaded native image SHA-256: `35b362b12a0c064796f2fa931be4cd2f1f4632bd11db65414b356a611a7c83d0`.
- NTSC, +3K and BLK1/2/3/5, full 704-byte software stack.
- 397 bytes of resident headroom; 24 bytes free in BLK5.
- Saved VICE capture: 1,180 consecutive raster frames, 19.557 seconds,
  **537 completed redraws**, **8,374 fresh pool cells** and 2,885 actor stamps.
- This is the existing 27.46 redraws/s sample, not a new throughput result.

The analyser reads the existing RAM snapshots and instruction profile. It
does not run or modify the guest. Intermission-art edits made concurrently
in the workspace are outside this frozen measurement; it is tied to the
captured PRG above rather than whatever `build/pacman.prg` contains later.

For each redraw, compare each pending cell's 16 final glyph bytes and colour
with the previous completed display at that screen position. Separately,
check the actual hidden bank at refresh entry: a cell equal to the previous
display is not necessarily still available in that bank's assigned slot.

The stricter dependency key contains the clean home glyph, every contributing
actor's slot/position/attribute/palette in paint order, and the final colour.
It includes actors whose allocated footprint contributes no visible pixels.
Changing one participant invalidates a shared cell. Equivalent animation
masks can have different keys, so this is conservative.

Across all 555 saved render/paint/complete triplets, including the lead-in,
the analyser verifies allocation order, footprints, colour priority, exact
publication, hidden-bank retention and that the pending bank is not displayed
at entry or immediately before publication. Dependency matches must produce
identical bytes and colour. No false dependency matches were found.

## What can potentially be reused?

Percentages below use freshly allocated pool cells as their denominator,
not all 196 screen cells. Counting the mostly static screen would inflate
the apparent opportunity.

| Opportunity | Whole sample | Redraws where some actor coordinates changed |
| --- | ---: | ---: |
| Fresh pool cells | 8,374 | 7,816 |
| Same pixels and colour as previous completed display | 2,136 / **25.51%** | 1,581 / **20.23%** |
| Same conservative dependencies as previous display's pool cell | 1,786 / 21.33% | 1,232 / 15.76% |
| Same pixels at the same screen cell and physical hidden slot | 1,354 / **16.17%** | 831 / **10.63%** |
| Same hidden slot, screen cell and conservative dependencies | 1,226 / **14.64%** | 703 / **8.99%** |

Allowing the hidden slot number to change raises the byte-match count only
to 1,472 cells, or 17.58%. That requires remapping allocations. Keeping
matching glyphs in the currently displayed bank requires a larger ownership
and capacity redesign: both banks can then contain live cells. The existing
assumption that the next bank is completely hidden would no longer hold.

There are 348 shared actor cells. In 1,097 pool cells, final pixels equal
the clean home pixels; their actor colour may still matter. An empty-looking
fragment cannot automatically be replaced with the home cell.

## Held positions, animation and background changes

There are **497 redraws with some actor coordinates changing** and **40 with
all visible actor coordinates held**. Held coordinates are a description of
rendered poses, not proof that the game logic has stopped.

Only 39 redraws retain all actor poses and composition dependencies. In
**eight of those**, background changes elsewhere still change the picture.
Only **31 complete displays are identical**, all covered on this sample by
an additional guard requiring no dirty tiles, full rebuild, rebuild phase or
pending maze flash at refresh entry.

Of those 31 identical displays, **30 occur while a ghost reward score is
visible**. Only one occurs outside the reward-score segment. A whole-display
early exit is therefore a bounded alternative to a cell cache, but this
sample suggests it would help reward pauses much more than moving gameplay.
It must still preserve background servicing and the arcade logic/audio tick.

There are 367 actor stamps whose entire footprints satisfy the conservative
same-hidden-slot condition, but only **144 of 2,647 stamps** in redraws with
changing actor coordinates. Partial-footprint hits cannot skip the whole
stamp: its other cells still need composition. No stamp-cycle saving is
claimed from these counts.

## Cycle and memory implications

The current instruction profile proves an exclusive cost of **209 cycles**
per clean 16-byte home copy: 1,780,889 cycles / 8,521 native copies. This
kernel cost is applied to the separate VICE opportunity counts; the two
emulators' redraw populations are not treated as identical.

| Copy work hypothetically avoided | Cycles per redraw | Share of captured CPU cycles |
| --- | ---: | ---: |
| All 1,354 identical same-cell hidden slots | 527 | **1.41%** |
| The stricter 1,226 matching dependency cases | 477 | **1.28%** |

These are **copy-only ceilings with zero checking overhead** at the measured
cadence, not predicted FPS gains or bounds on every possible cache. A real
implementation must identify reusable contents before copying or stamping.
Comparing the finished bytes afterwards cannot recover composition time.
Stamp/allocation savings could add to the benefit, but need their own measured
implementation; dependency checks, invalidation and remapping subtract from it.
During redraws with changing coordinates, the stricter copy opportunity is
only about **296 cycles per redraw**, before any checks.

The offline keys are not a proposed on-machine representation. For example,
storing exact 16-byte background snapshots for 24 cells in both banks would
need **768 bytes**, exceeding the 397 resident bytes before code or pose
history. An alternative needs explicit invalidation rather than those copies.
Tracking four pose bytes for six actors in both banks would take 48 bytes
before sharing existing storage; two 24-bit invalidation maps add six bytes,
but neither budget includes the checking/invalidation code or slot management.
No storage has been reserved and no stack space has been reduced.

## Decision and retained design requirements

**Measurement complete; persistent reuse deferred.** The 25.51% headline is
not sufficient justification for a renderer rewrite. The immediate same-slot
opportunity is smaller, particularly while actors move, and the current memory
budget makes exact invalidation a material part of the design. The recommended
VIC audio translation investigation has since produced an accepted pitch lookup.
Persistent reuse remains deferred.

If revisited, start with a costed prototype that keeps the two disjoint banks.
Compare its checking overhead with the roughly 296 moving-redraw copy cycles
available here, and measure any whole-stamp savings separately. Retain these
requirements:

- Include source mask/flip, position, palette, shared-cell contributors and
  all relevant home pixel/colour changes. The saved snapshots omit home
  colour RAM at `$9400`; a future runtime/capture design must cover it.
- Invalidate on pellets, score/background edits, maze flashes, full rebuilds,
  actor visibility changes, rewards and intermission transitions.
- Define displayed and pending ownership, old/new footprints, cache validity,
  allocation failure and safe fallback. Never write a currently visible glyph.
- If a whole-display guard is tried, update/invalidate the existing pose cache
  coherently and skip before bank/count/epoch changes, or roll them back safely.
- Reprofile actual throughput, worst input/audio gaps and visible poses on a
  separate trial; use full gameplay/audio/intermission checks before acceptance.

## Reproduction and evidence

```sh
python3 tests/pool_reuse.py
python3 tools/arcade/pool_reuse.py \
  --capture build/pool-stamp-fast/evaluation/trial-vice \
  --profile-capture build/pool-stamp-fast/evaluation/trial-cpu \
  --output build/pool-stamp-fast/evaluation/reuse-opportunities.json
```

The analyser's **nine host checks pass**, including animation, recolouring,
background edits, shared cells, clipping and physical-slot mismatches. The
full capture check passes all 555 triplets; 537 are in the counted raster
window. No new gameplay regression run was required because this work changes
only offline measurement tools, tests and documentation.

The [frozen summary](baselines/pool-reuse.json) retains binary/input/source
hashes, counts, percentages and copy ceilings. Per-redraw observations are in
the generated sibling `reuse-opportunities-redraws.json`. The raw VICE capture
and native profile remain ignored build evidence; they are needed to reproduce
these exact results. This single active-play route is not a worst-case or
intermission/maze-flash coverage claim.
