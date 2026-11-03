# Improvement audit

Audit of the accepted hires game on 2026-11-03. Source of truth is the
current `src/` tree and the link map in `build/arcade/pacman.map` (resident
image ends at `$7D34`, PRG is 26,715 bytes). Frame-rate figures below are the
existing measurements in [PERFORMANCE.md](PERFORMANCE.md) and
[CAPTURE_AUDIT.md](CAPTURE_AUDIT.md). This pass did not re-run `make
performance` or VICE.

The subsequent [item 1 trial](ACTOR_COMMIT.md) did run fresh native and VICE
comparisons. Its results and decision are linked below; the baseline figures
in this initial audit still describe the accepted default.

The playable target stays the original white-maze build. Colour clash is an
accepted limit. The multicolour game, the beam scheduler and the temporary
character-copy preview stay separate experiments.

Current direction after user review on 2026-11-03: stop further flicker work
for now. The independent-actor comparison shows flicker alternating between
sides with no meaningful overall improvement. Item 1 is rejected; item 2,
finished-cell publishing and other flicker experiments are on hold until the
user asks to resume. The user subsequently selected lettering and bonus scores;
the [VIC-native font](FONTS.md) is implemented and approved after visual review. Sound work
remains unstarted. The initial audit's sizes above describe the pre-font build.

## What limits the picture

Three different defects get called "flicker" in play. They have different
fixes.

| Defect | What the player sees | Cause in this build |
| --- | --- | --- |
| Actor blink | A ghost or Pac-Man vanishes, the maze shows through, then the actor returns | One visible bitmap. Dirty actors are erased, then later repainted |
| Uneven motion | Movement hitches even when a pose is fully drawn | The 60.606 Hz logic tick keeps going. A refresh is started only when the whole loop still fits in the tick that just began |
| Colour clash | Walls and pellets take an actor's colour inside an 8×16 cell | One foreground colour per cell. White artwork makes that clash less noisy |

A change that hides the blink by adding work makes the hitch worse. The
rejected precomposition and character-copy trials did that: the hole got
shorter on paper, the update rate fell into the low 30s or below, and play
still looked the same. The next change has to shrink the hole without a
second full redraw.

### Where the blink is

`video_frame_begin` in `src/sprites.S` always runs in this order:

1. `sprite_mark`, then erase every dirty actor, Blinky first.
2. `video_background`, which paints queued 4×6 tiles into the live columns.
3. Paint the actors in reverse, so Blinky is drawn last and sits on top.

Blinky's missing-sprite window therefore includes every other erase, the
tile paints, and every earlier actor paint. Pac-Man is erased second to last
and painted second, so his window is already one of the shorter ones. VICE
captures show the maze restored and the actor absent, which matches this
order.

Static cost of the current painters, counting the bytes at `$207C`, `$20BA`
and `$218C`:

| Step | Cycles, roughly | Time at 1,022,727 Hz |
| --- | ---: | ---: |
| Both-column erase, 12 rows unrolled by two | 306 | 0.30 ms |
| Pre-shifted ghost, 10 opaque rows | 510, plus two edge saves | 0.59 ms |
| Generic opaque row (Pac-Man, eyes, fruit, clipped ghosts) | 67 per row, about 800 for a solid sprite, plus setup | about 1.0 ms |

The measured normal-play erase-to-paint window is still about 5.7 ms mean and
10.8 ms at the 95th percentile, against a 16.6 ms NTSC frame. The painters
themselves are short. The wait between them is the blink.

### Where the hitch is

`main` in `src/pacman.c` waits for one VIA tick, runs controls, `isr_008d`,
tasks and `audio_update`, then calls `video_refresh` only when `clock_ticks`
has not moved on. If the body overruns, that refresh is skipped and the next
wait returns immediately so logic can catch up.

The opening benchmark, which does not keep turning, completes about 52
renders/s in normal play and 55 when frightened. An active joystick capture
of the same program completes about 33 renderer calls/s. Those are completed
calls, not unique poses. Intermissions already hold 60. The gap is busy
play, not the clock.

`frame_wait` spends leftover cycles on a rebuild slice only while
`rebuild_phase` or a bulk task is set. On a frame that already finished
inside the tick, the wait is a spin. That slack cannot speed up a later
frame that overruns, because the next positions do not exist until
`isr_008d` runs.

## Budget from today's link

NTSC frame: 16,965 cycles. Logic tick: 16,875 cycles (`$41E9` plus the VIA's
+2), about 60.606 Hz. RAM the VIC can show is `$0000–$03FF` and
`$1000–$1FFF`.

| Region | Used by the current image | Free |
| --- | --- | ---: |
| BLK1–3 code and tables, `$2000–$7FFF` | Ends at `$7D34` | 716 bytes |
| BLK5, `$A000–$BFFF` | Ends at `$BFF1` | 15 bytes |
| Zero page before the arcade flags at `$A0` | Explicit zp ends at `$83` | 29 bytes |
| VIC bitmap `$1000–$1C3F` | 14×14 double-height cells, 112×224 pixels, playfield used as 112×216 | none |
| `$1C40–$1D3F` | Virtual I/O image copied from the arcade output ports | none |
| `$1D40–$1FFF` | LLVM-MOS software stack, growing down from `$2000` | 44 glyphs if the stack moves |

The software-stack reservation is the whole top of VIC RAM. A long smoke run
observed writes only from `$1FE0` up (32 bytes). That is one workload. A
glyph pool has to move the stack into the 716 free bytes in BLK1–3 and keep
a canary through fright, death and all three intermissions.

A second 3,136-byte bitmap does not fit in VIC RAM, and it does not fit in
the 716 free bytes of expansion RAM either. `$9002` bit 7 flips the screen
matrix and colour RAM together. Both matrices would still name the glyphs
that are being erased. Page flipping the current layout does not hide a
partial sprite.

## Already in good shape

Leave these alone unless a measurement says a specific one regressed.

- Column-major bitmap. Twelve sprite rows are contiguous, so the painters
  are `(zp),Y` walks instead of per-row address math.
- Dirty tiles, with a 128-byte bitset and a 20-entry queue. Overflow becomes
  a full rebuild rather than a dropped write.
- Unchanged actors stay up. Old and new boxes pull in overlapping actors
  before the erase, so priority and shared colours survive.
- Stationary actors outside a dirty 32-pixel band stay up. Score and HUD
  writes no longer wipe the maze. See [SPRITE_FLICKER.md](SPRITE_FLICKER.md).
- Ghost bodies are pre-shifted. Six normal frames share two symmetric masks,
  320 bytes, plus 320 bytes of frightened shifts. Empty edge rows skip the
  mask. `bitmap_draw_ghost` is 91 bytes.
- The generic painter resolves clip, mirror and shift once per sprite. A
  clipped column is aimed at the unused underlay half, so the row loop has
  one body. The row loop is 99 bytes. See [SPRITE_KERNELS.md](SPRITE_KERNELS.md).
- An aligned sprite does not recolour the empty right-hand cell.
- Maze completion recolours wall cells in place. It does not rebuild the
  bitmap. See [MAZE_FLASH.md](MAZE_FLASH.md).
- The next board is built in bounded slices while input, logic and sound
  keep running. See [BOUNDED_REBUILD.md](BOUNDED_REBUILD.md).
- The KERNAL keyboard scan is already gone. `clock_irq` ticks a counter and
  returns. Joystick and the 5 / 1 / 2 keys are read directly in `controls`.
- One-time startup runs from `$0400–$07FF`, then that RAM is released.
  See [MEMORY_REUSE.md](MEMORY_REUSE.md).
- Ghost speed-mask tests no longer rotate a temporary copy. See
  [GHOST_STATE.md](GHOST_STATE.md).

## Closed experiments

These ran, were looked at, and should not be repeated as the flicker plan.

| Attempt | Result |
| --- | --- |
| Shared scratch columns, then copy the finished pixels back ([GHOST_PRECOMPOSITION.md](GHOST_PRECOMPOSITION.md)) | 59.8% of normal-play erases moved off the live bitmap. Normal play fell from 51.93 to 29.28 renders/s. Play looked the same |
| Same idea, capped at 128 / 96 / 64 composed pixels | Speed came back only by composing fewer actors. The actors that still blink are the ones the eye follows |
| Copy old cells into spare glyphs, draw the new pose into the live bitmap, then point the screen back ([GHOST_SHADOW.md](GHOST_SHADOW.md)) | Old character bits survived the erase. New edges and colour RAM still changed live, so actors still vanished. Normal play fell to 33.51 renders/s. Active capture was about 21 calls/s against 33 for the original. Play looked the same |
| Raster-gated live painter ([RASTER_SYNC.md](RASTER_SYNC.md)) | The paint did not fit in vertical blank. No visible change. Frightened and attract samples lost throughput |
| Beam-scheduled slices ([BEAM_FOLLOW.md](BEAM_FOLLOW.md)) | No visible change. Active capture fell from about 33 to about 24 calls/s |
| Independent-actor grouping, and preparing metadata before the erase | Window moved from about 6.1 ms to 5.46 ms, throughput to about 42–43 renders/s. The grouping still erased every selected actor before any of them was repainted, and it used a 32-pixel box |
| One-row underlay sliding | 49.01 and 48.37 renders/s, with a larger frightened loss |
| Pac-Man-only off-screen compose | 12 of 478 normal-play paints. Reverted |
| Pellet-neighbour colour scans | Lost several renders/s to keep white pellets. The all-white maze removed the scans |
| Multicolour game as the default picture ([MULTICOLOUR_GAME.md](MULTICOLOUR_GAME.md)) | Blue walls and white pellets do work there. Live play is about 9 updates/s. Held until that budget is in the same range as this build |
| Actual independent-actor commits, with old/new byte and colour dependencies ([ACTOR_COMMIT.md](ACTOR_COMMIT.md)) | Mean opening actor window falls from 5.662 to 2.539 ms, but opening throughput falls from 51.93 to 44.91 renders/s and a fresh 1,200-frame active capture falls from 30.92 to 24.13 calls/s. Rejected after user review found no meaningful overall flicker improvement |

XOR restore is a poor fit: overlapping actors corrupt the maze. Spreading
`updateGhostStates_1017` across ticks, or replacing the 16,875-cycle timer
with the raster rate, would change arcade patterns. Both stay out of scope.

## Agreed next experiments

Agreed on 2026-11-03: try the following four items in this order. Item 1 has
now been [tested separately](ACTOR_COMMIT.md) and rejected after user visual
review; it also fails the throughput budget. Further flicker work, including
item 2, is on hold. Item 3's [font](FONTS.md) is implemented and approved; item 4
remains unstarted. The original
proposals and acceptance criteria below are reference material.
Keep each change separately measurable and reviewable. Each rendering change
needs its own before/after on the same joystick trace, judged by eye, plus
the numbers in the measurement section. Digit artwork can be reviewed
independently. Finished-cell publishing is deferred below.

### 1. Commit independent actors before erasing the next

This is the first change to try. It adds no second buffer and no spare
glyphs. It changes the order inside `video_update_begin` / `video_update_end`.

Trial status: rejected after user review found no meaningful overall flicker
improvement, with an unacceptable throughput loss. See [the result](ACTOR_COMMIT.md). The proposal
and its original acceptance criteria remain below for reference.

Today every dirty actor is erased, then every queued tile is painted, then
every dirty actor is drawn. For actors with independent restore and draw
footprints, that wait is unnecessary. Erase one actor, paint only the tiles
that affect its old or new footprint or shared colour cells, draw it, then
move on. The target is to reduce Blinky's hole from "everyone else" to his
own erase and paint. The painter-only estimates are about 0.9 ms for a ghost
and 1.3 ms for Pac-Man, against today's measured 6–11 ms windows. These are
hypotheses, not measured results for the proposed renderer; frontend work,
tile painting and clustering add cost.

Tiles that miss every dirty actor can be painted while the actors are still
up. `bitmap_tile` only writes the 4×6 footprint it was asked for. A pellet
on the other side of the board should not sit inside Blinky's hole.

Actors that do overlap stay one cluster. Erase the cluster in today's order,
paint the tiles inside it, draw the cluster in today's order. The ghost
house and a eaten-ghost pile keep the long hole. Those moments are short.
During chase the four ghosts are usually separate, which is the case this
change is for.

Cluster on the actual old and new byte footprints and saved-underlay
dependencies. An 8×12 visible pixel box alone does not establish independence:
`bitmap_erase` restores whole saved bytes, including an otherwise empty
neighbouring column on an aligned, unclipped sprite. Restoring one actor can
therefore remove another actor whose visible pixels do not overlap. Preserve
the old footprint until dependency analysis is complete; `sprite_mark`
currently commits new positions to the cache before restoration.

The 32-pixel band in `sprite_background_overlap` is a conservative vertical
background test, not an independence test. Replace broad grouping only where
the byte writes and underlays establish that it is safe. Preserve final
shared-cell colour priority as well as pixels. A temporary shared-cell tint
may be acceptable, but independent commits must not leave a different final
colour or punch a hole in a neighbour.

The earlier grouping pass is not this change. It still erased the whole
selection first, and the 32-pixel test glued actors that this pass would
separate. Expect a small bookkeeping cost. If normal-play completed renders
fall by more than about 2/s, the cluster walk is too heavy and should be
simplified before any other renderer work.

What to watch in the trace: per-actor window for a separated ghost, number
of actors erased per refresh, and a side-by-side VICE capture on one
joystick file. The win is a shorter hole, not a higher benchmark FPS.

### 2. Make background invalidation more precise

Reduce unnecessary redraws with a focused change after item 1. Reuse its
footprint information where practical, and measure this change separately.

`sprite_background_bands` marks a 32-pixel-tall strip and ignores X. A pellet
on the left dirties every stationary actor in that strip, including a ghost
that shares neither pixels nor a colour cell. Moving actors are already
dirty from their own position, so this does not fix their blink. It does
stop a needless erase of a ghost that is waiting, or one that did not step
this tick, when Pac-Man eats on the same row.

Test colour cells, not just the 4×6 pixels. A tile and an actor can share an
8×16 cell without their pixels touching, and that cell's colour has to
follow the actor. The vertical test can stay as a fast reject.

### 3. Draw clearer digits

The user expanded this item to uppercase lettering and all ghost/fruit
scores. The [VIC-native font](FONTS.md) is implemented and approved after visual review;
the original recommendation follows.

Scores are hard to read, and the fix is artwork.

`drawDigit_2ace` stores tile code `0–9`, or `$40` for a suppressed leading
zero, through `video_store`. `bitmap_tile` expands that code as a 4×6 glyph
from `arcade_tiles` (768 bytes, three packed bytes per code). The same
painter draws the maze. Codes `$C0` and up are walls. Codes `$10–$14` are
the pellet path. Codes `$40`, `$FC` and `$FD` are skipped on a full rebuild.
Codes `0–9` are the font, also used by messages.

Replace the ten digit shapes with hand-drawn 4×6 glyphs and look at them at
NTSC pixel aspect, wide pixels, integer scale, no smoothing. Check 3 against
8 and 9, and 5 against 6, in a single digit and in a full score. Keep the
values, the leading-blank rule and the one-tile step. Widening a digit to a
full 8-pixel cell changes every HUD address and will collide with the
existing text unless the layout is redesigned. Do the clearer 4×6 shapes
first. Spacing is a second change, only if empty tiles actually sit beside
the scores.

This does not move the frame rate. It is the graphical change with the
least machinery.

### 4. Re-profile, then optimize selected sound routines

Renderer micro-opts are the wrong place to buy the missing refreshes.
`updateGhostStates_1017` is 1,703 bytes at `$5C71`. `soundEffectOneChannel_2dee`
is 721 bytes at `$4362`. The last whole-game profile, from before the
sprite-kernel and ghost-mask passes, put about 6.7% of cycles in the ghost
routine and 3.8% in the sound-effect routine, excluding some callees. Those
shares have moved. Take a new profile before rewriting either one.

The ghost routine is already past the obvious mask waste. Further gains are
inside the four chase/scatter state machines. Port only a leaf that the new
profile actually heats up, and keep the 528 identical-input ghost checks.
A full assembly rewrite of ghost AI is a parity risk for a few percent.

Start with selected sound routines if the new profile supports it. A clear
channel mask takes the sound-clear path. With an active effect, the routine
selects the effect, decrements duration, advances frequency and updates the
volume envelope. New effect setup copies an 8-byte header; envelope handling
uses a function table during playback too. A small assembly fast path may
leave setup in C, but must preserve frequency changes, envelopes, priorities
and handoffs, not just the duration counter. Preserve the Namco frequency
bytes. `audio_update` then turns those bytes into VIC
dividers. It already lives in BLK5 (473 bytes) and the divider search is
seven comparisons. The C shift loop in `audio_voice` runs up to seven 16-bit
shifts per voice, every tick, whenever that voice is audible. That is the
part to count on the new profile. Silent voices already skip it.

`highestSoundBit` is already a 16-entry table. `rotate8` on the six sprite
coordinates is an inline byte rotate. Neither is worth a pass on its own.

Expected result of this step: more completed refreshes during siren and
chase, which softens the hitch. It does not close the erase/paint hole.
Profile the retained renderer after items 1 and 2, so targets reflect the
code that will stay. Optimize only measured hot paths; ghost work remains
conditional on evidence from that profile.

## Leave for later

These are real limits. They are not the next edit.

### Deferred: publish finished cells

Deferred outside the agreed four-item set. Reconsider only if the simpler
rendering changes visibly help but leave unacceptable blink. This needs a
separate renderer and memory feasibility assessment before implementation.

Draw the new 8×16 cell into a glyph the screen matrix does not name. When
the cell is finished, store its colour and its screen code. The VIC keeps
fetching the previous glyph until that store. The visible critical section
is a handful of stores per cell, on the order of one raster line, rather
than a 6 ms painter.

This is a different publish path from the rejected character-copy preview.
That preview pointed the screen at a copy of the old cell, then kept erasing
and drawing the live bitmap, then pointed the screen back. New footprint
edges and colour RAM changed while the beam was looking. The copy preserved
character bits and still left a missing actor on screen.

Requirements for a new attempt:

- Compose the finished cell, including every actor that lands in it and the
  maze bytes underneath, before any screen-code store.
- Do that compose instead of the live erase/draw for those cells. Wrapping
  another copy around the current painters is the cost that dropped play
  from 52 to 33 renders/s.
- Publish colour in the same tight loop as the screen code. Colour RAM is
  still live. A colour store a frame away from the glyph store is a flash
  even when the pixels are ready.
- On overlap, one published cell holds every actor in priority order. Publishing
  actors one by one reopens a hole in the other sprite.
- If the pool runs out, that frame uses the step-1 path. Clipped intermission
  actors can stay on the generic painter until they show up in a profile.

Memory that already proved out in the rejected preview: 24 glyphs (384
bytes) at `$1D40`, codes 212–235, with the software stack kept above them.
Four ghosts at up to four cells is 16 glyphs for a single buffer. A second
buffer, so the VIC can keep showing the previous pose while the next is
built, needs another 16 and pushes the stack move. Pac-Man and the fruit
can stay on step 1 until a ghost shares their cell. Codes 196–211 stay off
the screen matrix. Those bytes are the virtual I/O image at `$1C40–$1D3F`.

Abort if active-play renderer calls fall under about 30/s, or if a
side-by-side capture still shows the actor missing. The user has already
rejected two slower pictures that did not look different. A third one needs
a shorter hole on the capture, not only a passing pixel compare at the end
of the refresh.

### Other deferred work

**Generic-painter tightening.** Removing the two per-row jumps in
`bitmap_draw` saves on the order of 70–120 cycles on Pac-Man, about 0.1 ms.
Unrolling one shift into straight-line code costs a few hundred of the 716
free bytes and covers one of eight shifts. The ghost row loop is 25 bytes.
Unrolling it saves about 50 cycles per ghost. None of that changes a 6 ms
hole or a dropped refresh.

**Pre-shifted Pac-Man.** Eight shifts of one 12-byte frame cost 96 bytes.
Seven frames fit in the free RAM, and Pac-Man has more poses than that once
directions and animation are counted. The partial table also has to beat the
generic painter by enough to matter. It does not, until the hole and the
dropped refreshes are smaller.

**IRQ takeover at `$FFFE`.** The tick handler already skips the KERNAL scan.
Replacing the hardware vector saves the preamble, well under 100 cycles per
tick. That is noise next to a 9 ms refresh.

**Hidden next-board bitmap.** Progressive drawing leaves the new maze
incoherent for about 1.8 s, and actors stay off for that whole rebuild:
`video_refresh` skips `video_update_end` while `full_dirty` is set. A shadow
maze in expansion RAM would let the old picture hold, then copy across.
The shadow is 3,136 bytes and the link has 716 free. Building it means a
larger overlay or compression project, not a painter tweak. Redrawing actors
on top of the half-built board fights `bitmap_tile` and the saved underlays.

**Blue walls on this bitmap.** Every standing pellet shares an 8×16 cell
with wall pixels, so a single foreground colour cannot keep both. The
multicolour layout does it by a different screen. It is on hold at about 9
updates/s. Simpler wall art ([MAZE_MOCKUP.md](MAZE_MOCKUP.md)) drops the
pattern count from 118 to 109. That does not free a second screen.

**VIC waveforms.** Square waves and one shared volume are the current sound.
Closer timbre is real work and it does not help the picture. Keep it behind
the renderer.

**Alternate-frame actor updates.** Skipping a ghost's bitmap update on every
other refresh leaves the last pose up, so that ghost does not blink, at the
cost of a one-pixel hitch. Collision and patterns stay on arcade
coordinates. It is a visible compromise. Hold it until the agreed rendering changes have
been seen in motion. Any ghost whose box overlaps a ghost that is being
redrawn has to be redrawn in the same refresh, or the erase punches a hole
in the one left on screen.

## How to measure the next change

Use both of these. The opening benchmark alone has already been mistaken for
the rate in a playthrough.

1. `make performance`, same scenes as [PERFORMANCE.md](PERFORMANCE.md):
   normal play, frightened, attract, intermission, board transition.
   Record completed renders/s and the longest input and audio gaps. Use
   `python3 tests/flicker.py` separately for mean and 95th-percentile
   erase-to-paint windows per actor.
2. One VICE raster capture with a fixed joystick trace, original beside the
   change, long enough to include a chase, a fright, and a pellet streak.
   Watch for a missing actor, not for the finished frame. The capture method
   in [CAPTURE_AUDIT.md](CAPTURE_AUDIT.md) is the one that matched what play
   felt like.

Keep the white maze, the 16,875-cycle tick, sprite priority, and the
+3K / BLK1 / BLK2 / BLK3 / BLK5 machine. `make test` covers arcade state and
the renderer oracle. A renderer change also needs the overlap fixture in
`tests/render.py` (`test_05_dirty_tiles_preserve_actors_and_shared_colours`):
a background write outside an actor's cells must leave that actor's pixels
and colours untouched. Extend coverage for byte-sharing actors with disjoint
visible pixels, old/new restore dependencies and shared-cell colour priority.

## Trial decision and remaining queue

Item 1's [separate trial](ACTOR_COMMIT.md) passes parity and ordering checks,
but falls from 51.93 to 44.91 renders/s in opening play. A fresh longer active
capture falls from 30.92 to 24.13 calls/s on the same joystick inputs. These
are different workloads; neither meets the planned throughput criterion.
Keep the accepted original as the default. The diagnostic target remains
available through `make run-actor-commit` for reproduction. User review found
flicker alternating between sides without an overall improvement and rejected
the trial.

Further flicker work is on hold at the user's request, including precise
background invalidation and finished-cell publishing. The [font](FONTS.md)
is implemented and approved after visual review; measured sound-path optimization remains
unstarted. Multicolour, beam scheduling, scratch-column precomposition
and old-cell copies remain on the shelf. Resume flicker work only when the
user asks.
