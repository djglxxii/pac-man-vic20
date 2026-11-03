# Flicker audit

Current follow-up: the [original-hires temporary-character experiment](GHOST_SHADOW.md)
was rejected after the user saw no perceptible flicker improvement.
It copies old displayed cells before bitmap erase/draw, but leaves colours
changing live. Normal/frightened samples fall to 33.51/38.20 FPS.
The multicolour redesign is on hold; the original accepted game stays default.

The subsequent [beam-scheduled trial](BEAM_FOLLOW.md) showed no perceptible
benefit in user review. The [capture audit](CAPTURE_AUDIT.md) verifies that
the code ran and the footage differs, but finds that native benchmark rates
were misleading alongside different recorded workloads. The fresh active
beam sample is 23.51 renderer calls/s, versus 33.42 for the original.

Prepared on 2026-11-02 from the retained compositor, the measurement notes, and
the reverted experiments. This is a proposal, not an implementation. It looks
for ways to shorten the visible erase/paint hole while leaving arcade ghost
and pattern behavior alone.

Follow-up: [the shared-column precomposition prototype](GHOST_PRECOMPOSITION.md)
tested recommendation 1. The user saw no significant difference in flicker,
while normal/frightened throughput fell to 29.28/34.32 FPS. That implementation
is rejected; the faster main build is restored. The proposals below describe
the original audit, not demonstrated improvements.

Gameplay stays on the 16,875-cycle VIA clock. Speed masks, target tiles, house
release, Cruise Elroy, fright timers, and ghost update order stay as they are.
The power-pill and eaten-ghost slot swaps stay too. They rewrite the output
copy at `$0C22` and do not change ghost state.

The accepted picture can bend. Cell colour, a one-frame overlap glitch, or a
one-pixel hitch are in scope if the ghosts still follow the arcade patterns.
A second full bitmap, XOR restore, and rescheduling ghost decisions are not.

## Where the blink comes from

`video_update_begin` in `src/sprites.S` erases every dirty actor, then paints
them afterward. Erase order is Blinky, Pinky, Inky, Clyde, Pac-Man, fruit.
Paint order is the reverse, so the last paint sits on top. That is the arcade
priority, including the slot swaps.

The host trace times `bitmap_erase` through that actor's painter return. For
Blinky the span includes every other erase and every earlier paint. The last
measured actor windows, from the generic sprite-kernel pass, are about 5.7 ms
mean and 10.8 ms at the 95th percentile. A frame is 16.7 ms. Some windows still
run longer than a frame. VICE captures show the actor missing, with the maze
already restored, rather than a half-drawn shape.

A ghost paint itself is short. `bitmap_draw_ghost` walks ten source rows, on
the order of 0.6 ms, and a both-columns erase is about 0.3 ms. The blink is
the wait between those two steps. Blinky is the actor the eye follows, and he
has the longest wait. Pac-Man is erased second to last and painted second, so
his hole is already one of the shorter ones.

## Already closed

Further work should leave these in place:

- Stationary actors survive unrelated maze and score updates. See
  [SPRITE_FLICKER.md](SPRITE_FLICKER.md).
- The generic painter is tighter, empty rows skip pixel writes, and clipping
  is resolved once per actor. Ghost shapes are already pre-shifted. Erase and
  `bitmap_draw_ghost` were not part of that pass. See
  [SPRITE_KERNELS.md](SPRITE_KERNELS.md).
- The ghost movement-mask pass removes redundant shifts in
  `updateGhostStates_1017`. It is a logic saving, not a flicker fix. See
  [GHOST_STATE.md](GHOST_STATE.md).

These were tried and should not be repeated as flicker fixes:

| Attempt | What happened |
| --- | --- |
| Temporary copies of old hires character cells | Character bits survived erasing, but colours still changed live. User saw no difference; normal play fell to 33.51 FPS. Rejected. [GHOST_SHADOW.md](GHOST_SHADOW.md). |
| Isolated compose of Pac-Man's usual slot | 12 of 478 normal-play paints. Reverted. [REGION_COMPOSITOR.md](REGION_COMPOSITOR.md). |
| Raster gate on that same slot | 16 of 480 erases. The slow paint still ran inside the hole. Reverted. [RASTER_SYNC.md](RASTER_SYNC.md). |
| Independent-actor grouping | Mean window about 5.46 ms, throughput down to 41.58 FPS. Discarded. |
| Cheaper isolation, and preparing metadata before the erase | Small window change at about 43 FPS. Discarded. |
| One-row underlay sliding | 49.01 and 48.37 FPS, with a larger frightened loss. Discarded. |

A second 3,136-byte bitmap does not fit in VIC-visible RAM. Flipping `$9002`
bit 7 switches the screen matrix and colour RAM together, and both pages would
still point at glyphs that are already on screen. XOR restore was set aside
because overlaps corrupt the maze. Changing the gameplay timer, or spreading
ghost decisions across ticks, would change patterns.

## 1. Compose while the old ghost is still up

Build the next image in expansion RAM, then copy it over the live columns.
The old ghost stays on screen during the OR and the shift. The visible
critical section becomes "copy the underlay back" plus "store the prepared
bytes."

The reverted experiments still ran the painter after the erase, and only for
an isolated Pac-Man. This does the expensive work first, for every dirty
ghost, including ghosts that overlap.

On a one-pixel step the new rectangle still covers most of the old one. Where
they overlap, background bytes have to come from the saved underlay, not from
the live bitmap. Where they do not, they come from the bitmap. Ghosts that
overlap each other, and Pac-Man during fright, have to be composited into one
image before any of them is erased. Publishing them one by one reopens a hole
in the other sprite. The ghost house at the start of a life is the same case.

A `(zp),Y` commit is about 0.6 ms, roughly ten raster lines, against a hole
that can cover half the frame. An unrolled absolute copy of four ghosts is
about 1,500 cycles. Vertical blank is raster lines 0–27, about 1,800 cycles.
The current painter does not fit there, which is why waiting on the raster
never looked better. If blank has already passed, commit anyway. Waiting
would stall the frame.

Final pixels can stay identical to today's renderer. The frame rate may drop
by the extra copy. Intermission actors that use the clipped generic painter
should keep the old path until they are measured separately.

BLK1–3 have room for the compose buffer. After the ghost-state pass, about
716 bytes are free there. Six actors at 24 bytes is 144 bytes. A union of
touched cells is still only a few hundred bytes.

## 2. Point screen codes at glyphs that are not on screen

The maze cells stay pristine. Each ghost is drawn into character definitions
the matrix does not currently show. One store per cell points the screen at
the new glyph. Restore is one store back to the maze glyph. The VIC never
fetches a half-erased character. A bad overlap becomes a one-frame priority
error, which is a different defect from a missing ghost.

This is not the `$9002` page flip. That flip keeps both screens aimed at the
same live glyphs. Here the bytes being written are not the bytes on screen.

Spare VIC-visible RAM is `$1D40–$1FFF`: 44 glyphs of 16 bytes, character
codes 212–255. Address check: code 212 starts at `$1000 + 212×16 = $1D40`,
and code 255 ends at `$1FFF`. The memory-lifetime audit reserves that range
for the LLVM-MOS software stack and left it there on purpose. The smoke run
wrote 32 bytes, from `$1FE0` up. See [MEMORY_REUSE.md](MEMORY_REUSE.md). That
measurement is one workload, not a proof of the high-water mark.

Moving the software stack into BLK1–3 frees those glyphs. Keep a stack canary
across fright, death, and all three intermissions before treating 32 bytes as
the ceiling. Four ghosts, two buffers, and up to four cells each is 32 glyphs.
Pac-Man and the fruit can stay on the bitmap path until they overlap a ghost.
If the pool runs out, fall back to the live painter for that frame.

Do not use codes 196–211. Those bytes are the virtual I/O image at
`$1C40–$1D3F`. Putting them on screen would display that scratch as pixels.

Colour RAM is still per cell, so a ghost can still tint the 8×16 cell it
occupies. A torn scanline can show one new cell beside an old one for a
single frame. Shapes and paths stay on arcade coordinates.

## 3. Draw some ghosts on alternate refreshes

Use this only if precompose and a tight commit still miss blank too often.

Skip the bitmap update for a ghost on every other refresh, and leave its last
pixels in place. There is no erase on the skipped tick, so there is no blink.
Collision, patterns, and scoring keep using arcade coordinates. The VIA tick
and `updateGhostStates_1017` still run every logic frame.

Co-update any ghost whose real 8×12 box overlaps a ghost that is being
redrawn. Otherwise the erase punches a hole in the sprite left on screen.
The discarded grouping pass is a different change: it still redrew every
actor, used a 32-pixel box, and barely moved the measured window.

The visible cost is a one-pixel hitch. Rendered motion is already one VIC
pixel per one or two arcade steps, because X is arcade X divided by two and
Y is the 3/4 scale in `sprite_mark`. The hitch is smaller than the current
blink. It is still a break from the current picture.

## Not worth a pass

More generic-kernel tightening, another Pac-Man-only path, and raster-gating
the live painter. Coarser scrolling on its own does not close the hole.
Underlay sliding tried to save cycles and got slower. The interval to remove
is the blank between erase and paint, even if the CPU does a little more work
outside that interval.

## Suggested order

1. Precompose dirty ghosts, including overlapping sets, and commit with a
   short copy. Measure the erase-to-visible-again gap and normal-play frame
   rate before keeping it.
2. If that gap is still obvious, move the software stack and try the
   off-screen glyph pool for the four ghosts.
3. Hold alternate-refresh drawing until those two have numbers.
