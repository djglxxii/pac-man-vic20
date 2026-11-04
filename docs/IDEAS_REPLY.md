# Reply to IDEAS.md: assumptions, corrections, and open challenges

Reviewed against the current hires source and local build map on 2026-11-03.
Historical measurements below describe their recorded executables. No new
performance or VICE runs were made for this reply to [IDEAS.md](IDEAS.md).

The strongest proposal is to compose a finished cell before displaying it.
That could remove the explicit background-only state between erasing and
repainting actors. A permanent clean-background layout also offers a different
cost model from the rejected temporary-character experiment. However, several
claims depend on unavailable memory, incomplete publication rules, or
performance assumptions that the existing evidence does not establish.

## 1. Glyph pool: promising architecture, incorrect relocation premise

### Assumption: clearing $0400–$0FFF means those 3 KB are available

**Corrected fact:** those bytes become live game and renderer data immediately
after startup. Their current uses are:

| Address range | Runtime use |
| --- | --- |
| `$0400–$07FF` | Logical arcade screen codes |
| `$0800–$0BFF` | Logical arcade colour attributes |
| `$0C00–$0EFF` | Arcade RAM, including actor attributes and game state; some flag accesses are redirected to zero page |
| `$0F00–$0FFF` | Dirty bits, actor cache, maze coverage, and flash state, with a small unused tail |

The clear in `main()` initializes this memory. Only the startup code's lifetime
ends there. See [memmap.h](../src/arcade/memmap.h),
[video.c](../src/video.c), and the [memory-lifetime audit](MEMORY_REUSE.md).

The upper glyph-space arithmetic is correct: codes 196–211 overlap the
256-byte virtual I/O image at `$1C40–$1D3F`, and codes 212–255 overlap the
704-byte software-stack reservation at `$1D40–$1FFF`. Moving those allocations
could release the codes, but their destination has not been identified.

The current font build ends resident allocation at `$7EC5`, leaving **315
bytes in BLK1–3 and 15 in BLK5**. The older improvement audit's 716-byte figure
predates the horizontal ghost-score work. See [FONTS.md](FONTS.md),
[the local map](../build/arcade/pacman.map), and
[the linker layout](../src/pacman.ld).

The previous shadow trial demonstrated a smaller reservation: 24 glyphs at
`$1D40–$1EBF`, with a 320-byte stack above them. Its smoke run observed 32
bytes of stack writes. That observation does not prove a maximum stack
requirement for every path or a future renderer. Removing the six underlays
would release another 216 bytes, but pool metadata and replacement code also
need space. A complete memory layout must account for all of those changes.

### Assumption: 24 occupied cells establish the required pool size

**Corrected fact:** six four-cell actor slots establish a bound of 24 cells
for one displayed pose. Hidden preparation also needs space while the old
pose remains displayed.

The required capacity depends on the publication order. Preparing a whole new
set before releasing the old set could require up to 48 pool glyphs for
disjoint footprints. Composing and publishing one cell at a time can recycle
glyphs earlier, but still needs scratch capacity and accounting for old-only
cells held until new cells are visible. The proposed "24 plus some slack"
needs an explicit allocator and commit sequence to justify it.

Returning an old cell to its home glyph is valid only when no actor remains
in that cell. If another actor still occupies it, the final composed cell
must retain that actor. The update unit is the shared cell, with every
overlapping actor included in priority order.

There is also an implementation detail hidden by `matrix[cell] = cell`: the
current matrix is row-major and glyph storage is column-major. The home code
for matrix index `r * 14 + c` is `c * 14 + r`, as established by `video_init()`.
Restoration must preserve that mapping.

### Assumption: one atomic screen-code store guarantees no visible blink

**Corrected fact:** the screen-code store changes the glyph reference.
Foreground colour is a separate live write. The two values do not change
atomically together, and publishing multiple cells does not make an entire
actor change at once.

This matters because the [temporary-character trial](GHOST_SHADOW.md)
preserved old character bits yet still allowed visible disappearance through
live foreground-colour changes. New footprint edges also remained exposed.
Its active capture measured 20.82 renderer calls/s against 33.42 for its
original comparison build, and user review found no perceptible benefit.

The permanent clean-background proposal differs: it could replace underlay
save/restore work instead of adding copies around the existing renderer.
That remains a plausible advantage. It needs a colour-publication rule that
keeps the old glyph/colour pair useful until the new pair is ready, bounds
the mismatch interval, and preserves final shared-cell colour priority.
Colour clash is already accepted; temporarily making an actor invisible is
the relevant failure here.

Likewise, recomposing a displayed pool glyph in place abandons hidden
preparation for that cell. Writing only final bytes removes an explicit
erase pass, but the beam can still encounter a mixture of old and new rows.
"Blink-free" and "the worst case is motion blur" are unverified guarantees.

### Assumption: background changes and progressive rebuilds become safe automatically

**Corrected fact:** keeping actors out of home glyphs protects their stored
pixels from background writes. Background routines also update live colour
RAM, and dirty home glyphs need their displayed pool versions recomposed.
The [current rebuild](BOUNDED_REBUILD.md) deliberately restores actors once
and leaves them absent until the board finishes.

Keeping actors visible during that process requires changes to rebuild
scheduling, clearing, colour ownership, and pool invalidation. Merely
redirecting background pixel writes does not provide that behaviour.

### Assumption: copying and stamping cells will cost about the same or less

**Corrected fact:** the new CPU cost has not been measured. Removing saves
and restores offers savings, but the proposed renderer copies complete
16-byte cells and adds cell discovery, allocation, overlap composition,
colour selection, and publication. The current actor painters operate on
12 rows and already have specialized ghost and transparent-row paths.

The useful comparison is the complete refresh cost, including metadata and
background work. A byte-copy count alone cannot establish a win. A cycle
estimate should cover isolated motion, shared cells, background edits,
clipping, and reward poses before claiming comparable throughput.

## 2. Write-once compositing: the shadow buffer has no assigned home

### Assumption: expansion RAM can accommodate a 3,136-byte background shadow

**Corrected fact:** `196 * 16 = 3,136` bytes is the right size, but the current
expansion-RAM headroom is much smaller. Releasing the 216 underlay bytes also
does not close that gap. This fallback requires substantial additional
reclamation or a different background representation within the existing
hardware target.

Reconstructing background cells from logical tiles might trade memory for
CPU time, but that would be a separate design requiring a cost estimate.

The write-once byte loop does remove the explicit restore-then-stamp sequence.
It does not establish a coherent displayed actor across multiple bytes,
cells, and live colour writes. Its visual benefit and claim of lower CPU
cost remain hypotheses. The rejected [region compositor](REGION_COMPOSITOR.md)
had very limited coverage; its result does not settle a complete replacement.

## 3. Raster scheduling: valid drift arithmetic, unsupported conclusions

### Assumption: phase drift makes beam-aware scheduling impossible

**Corrected fact:** the documented NTSC frame budget is 16,965 cycles and
[clock.S](../src/clock.S) deliberately generates a 16,875-cycle arcade tick.
The 90-cycle difference and roughly three-second phase wrap are consistent
with those figures. However, knowing the beam's current position permits
scheduling without a fixed phase relationship to the logic tick.

The [beam-follow experiment](BEAM_FOLLOW.md) already read `$9004`, selected
safe windows, and retained the arcade timer. Its existence directly
contradicts the claim of impossibility. It produced no perceptible benefit
in user review and reduced active-capture throughput from 33.42 to 23.51
renderer calls/s for that comparison.

### Assumption: slowing the logic clock by about 0.5% is harmless

**Corrected fact:** the arcade clock is intentional, and preserving arcade
timing and pattern behaviour is a project constraint. Replacing it with the
display rate would change real-time game and sound timing. Whether a person
would notice is a subjective prediction, not a reason to discard the
constraint.

Separate display scheduling remains an option. It must account for render
duration and input/audio delays caused by waiting. Sorting actors by Y alone
does not establish that each transaction will finish before the beam returns,
especially when shared cells connect actors into a larger update.

## 4. Pacing: distinguish held pictures, shared cells, and unmatched workloads

### Assumption: skipping a refresh drops the whole picture

**Corrected fact:** [the main loop](../src/pacman.c) skips starting a refresh
when logic has fallen behind. The previous picture remains in video memory.
That produces a held pose and uneven motion. The explicit actor erase gap
occurs inside refreshes that actually run. Pacing and erase-related blinking
therefore need separate evidence of improvement.

### Assumption: a pool makes actors independently refreshable

**Corrected fact:** actors sharing a cell share its composed pixels and
foreground colour. A partial refresh must resolve those dependencies and
define which displayed poses it is composing. An old-only cell cannot be
released while another displayed actor still needs it.

The [independent-actor commit trial](ACTOR_COMMIT.md) already shortened the
mean opening erase-to-paint window from 5.662 to 2.539 ms. Its longer active
comparison fell from 30.92 to 24.13 renderer calls/s, and user review found
no meaningful overall flicker improvement. Those are historical results
for that trial, not measurements of a glyph-pool renderer.

### Assumption: a snapshot or fixed 30 Hz schedule supplies smoother output cheaply

**Corrected fact:** a snapshot can give the renderer consistent input, but
it does not remove rendering work from the single CPU. Interrupt rendering
can delay logic and audio. The existing drawing code also uses shared
scratch state and self-modifying instructions, so moving it into an IRQ
requires an explicit ownership and reentrancy design.

Six actor records alone do not describe background revisions, maze flashes,
or other display state. Snapshot publication needs a consistent relationship
to that state and to the actor-slot preparation used by horizontal rewards.

A fixed display cadence could improve pacing if the complete workload meets
its deadlines. An average near 30 calls/s does not demonstrate that every
required interval fits. Judge cadence, repeated poses, worst service gaps,
and visible actor continuity on the actual playthrough.

### Assumption: joystick steering alone costs nearly 20 refreshes/s

**Corrected fact:** the roughly 52/s opening benchmark and 33/s active capture
use different workloads and sample intervals. Active play includes changing
pellets, tasks, actor arrangements, and game states. This is not an isolated
measurement of the steering path. The [capture audit](CAPTURE_AUDIT.md)
documents that distinction explicitly.

The accepted font build's short opening benchmark is 52.04 calls/s, but
[FONTS.md](FONTS.md) does not provide a matching new active-play rate.
Profiling controlled input traces is reasonable; attributing the whole gap
to turning is unsupported.

## What would make the glyph-pool proposal concrete

The proposal remains worth a feasibility discussion. Its unresolved parts are:

1. An address-level memory plan for the pool, stack, virtual I/O, metadata,
   and replacement code, using the current 315-byte resident headroom.
2. A pool-capacity bound tied to an explicit prepare/publish/release sequence.
3. Rules for complete shared-cell composition, foreground colour publication,
   background changes, rebuilds, clipping, and the current reward layouts.
4. A cycle budget for the full replacement path, identifying work removed as
   well as work added.
5. If a prototype is subsequently requested, comparison on the same active
   input trace with actual-capture rates, service gaps, and visual review.

The prior experiments establish that preserved glyph bits and shorter erase
windows alone did not deliver an improvement the user could see. A new design
needs a specific explanation of how it addresses those failures while keeping
the accepted graphics, hardware target, and arcade clock.
