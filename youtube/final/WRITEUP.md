# Pac-Man on VIC-20: agentic homebrew — Final Optimized

This is the current accepted optimization milestone of our agentic homebrew
Pac-Man conversion. Coding agents performed the implementation, profiling,
debugging, test development and documentation under the project owner's
direction. Human play testing and visual review determined which experiments
became the standard build.

The conversion builds on Mark Burkley's C translation of the arcade program.
LLVM-MOS compiles the adapted game into native 6502 code, with handwritten
assembly for VIC-20 graphics, audio and other platform work. Original ROM
data supplies the reference game assets, sequencing and difficulty tables.
The [upstream notes](../../src/arcade/UPSTREAM.md) retain that attribution.

## The recorded playthrough

The final upload is
[through-game-over.mp4](../../build/through-game-over/through-game-over.mp4).
It follows the PacStrats patterns documented in
[10yard's Pac-Man Trainer (pactrainer)](https://github.com/10yard/pactrainer),
using computer-controlled joystick input in VICE. The run clears boards 1–9
and completes the third intermission with no deaths.

Afterwards, the run was deliberately ended by allowing Pac-Man to die until
Game Over, demonstrating the death animation and Game Over screen. The
intentional ending is separate from the death-free pattern playthrough.
The capture report records four deliberate deaths while exhausting the
remaining lives; none occurs before the third intermission.

The existing [capture report](../../build/through-game-over/report.json)
identifies the accepted optimized program and records all nine completed
boards, the intermissions and the intentional ending. The recording lasts
approximately 10 minutes 1 second. The older 2:18 recording remains the
separate Initial Pass video.

## The improvement that mattered most

The original software-sprite approach visibly erased actors before rebuilding
them. Faster drawing and raster-wait experiments did not produce the visible
improvement we wanted. The accepted solution was a finished-cell glyph pool.

The renderer combines clean background pixels and every overlapping actor
into character slots that are hidden from the displayed screen. It publishes
completed cells rather than exposing a cleared actor during composition.
Live play testing found this a substantial reduction in disappearance flicker.
It is still possible to see partial poses, shared cell colors and uneven
movement intervals; completed cells do not make an entire display update atomic.

The first accepted pool renderer cost speed: it measured 22.07 completed
redraws/s on the saved VICE route. We retained its visual improvement and
then recovered performance through fourteen individually measured changes.

## The optimization series

| Accepted stage | Measured VICE redraws/s |
| --- | ---: |
| Finished-cell glyph pool | 22.07 |
| Faster cell addressing | 22.80 |
| Skip empty sprite rows | 23.21 |
| Sound-effect processing | 25.67 |
| Ghost tunnel lookup | 26.44 |
| Generic sprite composition | 27.46 |
| Precomputed VIC pitch translation | 28.84 |
| Compact VIC audio adapter | 29.81 |
| Ghost-state dispatch | 30.78 |
| Cheaper cell allocation | 31.55 |
| Faster background tiles | 32.21 |
| Precomputed sprite preparation | 33.29 |
| Cheaper destination setup | 33.64 |
| Accumulator-first sprite shifts | 33.75 |
| Normal-ghost row control | 33.85 |

These are saved-route VICE averages from the documented experiments. The
final 33.85 redraws/s is approximately 53% above the first accepted pool
build. It is not a fixed 30 Hz deadline or a direct comparison with the
different workloads used to measure the initial-pass recording.

The [optimization plan](../../docs/RESEARCH_OPTIMIZATION_PLAN.md) links each
experiment and its evidence. The
[final promotion record](../../docs/baselines/pool-ghost-row-promotion.json)
identifies the accepted executable and regression checks.

The work removed repeated address calculations, unnecessary empty-row work,
expensive runtime pitch division and redundant state dispatch. Later passes
reduced cell allocation, background copying, sprite setup, shifting and row
control costs. Precomputed pitch values still follow the original live sound
sequencer; the game does not play a prerecorded soundtrack.

Each change was checked against identical-input routines, game-state and
sound replays, graphics oracles and actual VICE output. Rejected approaches
were removed. Full default regression checks pass, including all three
intermissions. Sound state and VIC-register values match on all 1,639 replayed
sound ticks; that check does not claim identical analog output or write times.

## Artwork, gameplay and hardware

The graphics for Pac-Man himself and the frightened (scared) ghosts were
refined for the small VIC-20 display. Pac-Man's symmetrical closed-mouth frame
is shared across directions.

The fonts were redesigned for better legibility on the VIC-20's small display,
replacing the hard-to-read scaled lettering with purpose-drawn letters and
score numerals. Horizontal reward scores also make bonus values easier to read.
The maze layout and arcade movement rules remain intact.

White walls and white standing pellets remain the accepted color compromise,
with blue/white completion flashing. Colored actors can tint their shared
cells. We retained the accepted sound, ghost patterns, collisions, scoring,
fruit progression and all three intermissions.

Gameplay retains its approximately 60.606 Hz logic clock, separately from
rendering. No optimization gains were obtained by slowing that clock or
reducing ghost update frequency.

The target remains an NTSC VIC-20 with +3K and BLK1/2/3/5 expansion: +35 KB
of expansion RAM, 40 KB total. These passes add no new hardware requirement.
The full 704-byte software stack is retained. Physical hardware validation
is still ahead.

## Why color clashes and other compromises remain

**Color belongs to a cell, not to each object.** In our high-resolution
graphics mode, each 8×16 character cell has one foreground color against
the shared black background. Every lit pixel in that cell uses the same
foreground color. If a yellow Pac-Man or a red ghost shares a cell with a
white wall or pellet, the hardware cannot give those shapes independent
colors. Nearby wall or pellet pixels can take the actor's color, even when
the shapes do not actually touch. Two actors sharing a cell also have to
share its foreground color. This produces the block-shaped patches of color
seen during play.

White walls make the maze more consistent and the tinting less distracting;
they do not remove that hardware restriction. Standing pellets are white
when no colored actor shares their cell. The maze returns to its background
color after an actor leaves. The VIC also offers a multicolor mode, but it
halves horizontal detail and shares several colors across the display. That
tradeoff would affect the small faces and lettering we worked to improve.

**There are no hardware sprites or a native bitmap mode.** The video chip
draws programmable characters. We use their pixel patterns as small pieces
of a picture, redefining them in RAM as the game runs. Smooth movement comes
from drawing an actor at different pixel offsets within those cells, rather
than jumping it a whole character at a time. An 8×12 actor can overlap up to
four 8×16 cells, so moving it can require several character definitions to be
recomposed, including any shared background and other actors.

**Flicker and color clash have different causes.** The earlier renderer
could expose an erased actor while rebuilding its graphics. The glyph pool
greatly reduces that disappearance by preparing completed cells out of view.
It cannot give a shared cell extra colors, and publishing several finished
cells is still a sequence of writes rather than an instantaneous replacement
of the entire picture. Partial poses can therefore remain.

**The CPU must do the drawing work.** The NTSC machine's roughly 1 MHz 6502
shares its time among game logic, software graphics, input and sound. More
actors overlapping or more background changes can increase the drawing cost.
The approximately 60.606 Hz game-logic clock is separate from display
updates: the current saved-route average of 33.85 redraws/s does not mean
every redraw arrives at an even interval. Holding the previous picture while
logic catches up can make movement look uneven. Waiting for the video beam
does not remove this workload or the shared-color restriction.

**Expansion RAM is not all usable as video memory.** Extra RAM holds code,
tables and other data, but the VIC can fetch character graphics from only a
small part of the address space. Character codes and visible graphics RAM
also have to accommodate the background and hidden pool slots. More general
RAM does not automatically provide room for two complete displayed pictures,
independent sprite layers or a faster processor. The pool works within those
limits rather than requiring a new expansion configuration.

**Sound hardware differs from the arcade board.** The VIC's three tone
voices share one volume control and do not reproduce the arcade's waveform
hardware. We preserve the music and effect sequencing while mapping pitch,
timbre and the mix to the controls available on the VIC. The accepted sound
is faithful in character, with hardware-dependent differences.

The refined actor graphics and redesigned fonts address another practical
limit: very few pixels are available for faces, mouth animation and digits.
Drawing those shapes for the actual display size makes better use of that
space while retaining the arcade layout and behavior.

The [project's VIC compromises](../../README.md#vic-compromises) and
[glyph-pool report](../../docs/GLYPH_POOL.md) document these choices and the
remaining visual tradeoffs.

## What comes next

This milestone closes the current optimization pass. The last improvement
added about 0.3%, so extended play testing, gameplay checks and presentation
polish now deserve priority. Persistent cell caching and redraw-pacing
rewrites remain deferred until measurements justify them. “Final Optimized”
names this milestone; it does not promise that the project can never change.

## Short video summary

An agentic homebrew Pac-Man conversion, built with coding agents and refined
through human play testing. A finished-cell glyph pool greatly reduces
disappearance flicker, and fourteen speed improvements raise its measured
redraw rate from 22.07 to 33.85/s on our saved VICE route. Refined Pac-Man and
frightened ghost graphics, redesigned fonts for more legible text and scores,
faithful game behavior and accepted VIC sound complete this optimization
milestone, on the same expanded NTSC VIC-20 target.

The recorded playthrough uses the PacStrats patterns documented in
[pactrainer](https://github.com/10yard/pactrainer), reaching the third
intermission with no deaths. The intentional ending afterwards demonstrates
the death animation and Game Over screen.

## Upload assets

Use [title.txt](title.txt), [description.txt](description.txt),
[pinned-comment.txt](pinned-comment.txt) and [tags.txt](tags.txt).
The [widescreen thumbnail](vic20-pacman-thumbnail.png) and
[portrait cover](vic20-pacman-shorts-cover.png) identify this as
**AGENTIC HOMEBREW — FINAL OPTIMIZED**, built with coding agents.

The standard-video metadata selects the existing through-game-over.mp4
recording. Recording date and chapter timestamps remain unspecified.
The portrait-cover metadata is retained for a future selected excerpt;
no separate Shorts edit has been prepared.
