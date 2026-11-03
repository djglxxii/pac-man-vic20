# Bringing Pac-Man to the VIC-20

This conversion brings the original Midway arcade Pac-Man to an expanded NTSC
VIC-20. The aim has been to preserve the game's behavior—movement, ghost rules,
scoring, sounds and intermissions—while adapting its presentation to a much
more limited machine.

## Preserving the arcade game

The game logic builds on [Mark Burkley's C translation of the arcade
program](src/arcade/UPSTREAM.md). We adapted it for the VIC-20 and compiled it
into native 6502 code with LLVM-MOS. Graphics, music, sound-effect data and
difficulty tables are decoded from the original ROM set.

A separate desktop test runner executes the original Z80 program. Comparing
its results with the conversion helped us find and repair differences in
movement, frightened behavior, scoring, fruit progression and animation.
The original quirks and all three intermissions are retained.

A VIA timer keeps gameplay running at approximately 60.606 updates per second.
Display updates can be skipped when necessary so rendering does not slow down
the game rules.

## Adapting graphics and sound

The VIC-20 has no hardware sprites, so we built a software renderer using
programmable characters as a bitmap. The full portrait display, including
scores and status information, fits into 112×216 native pixels. Original
tiles and sprites are scaled down, with some loss of fine detail.

The renderer saves and restores the background beneath moving characters,
handles overlapping actors in their original priority order, and updates
changed areas. Handwritten assembly, cached unchanged sprites, pre-shifted
ghost graphics and lookup tables reduce the drawing cost.

Color is shared across each 8×16 display cell. We settled on white maze walls
and white pellets to avoid a distracting patchwork of blue and white. Colored
actors can still temporarily tint nearby pixels sharing their cell. On maze
completion, the walls flash blue and white four times, starting with blue.

The original music and effect sequencing drive the VIC's three tone voices.
Their square-wave sound and shared volume control approximate the arcade
hardware, so timbre and individual voice levels differ.

## Making it playable and checking the results

Large board-building operations now run in small, resumable steps. Input,
game logic and audio continue while the next maze draws progressively.
Completion flashing changes colors directly without rebuilding the bitmap.
The build produces a single loadable PRG for the existing full RAM expansion.

The current build passes 48 automated checks covering arcade behavior, native
6502 execution, graphics, sound conversion, maze colors and board transitions.
VICE checks confirm startup, controls, sound and presentation. We also recorded
a computer-controlled playthrough that cleared both initial boards and
completed the first intermission using ordinary joystick input.

Measured rendering is around 52 FPS during normal play and 55 FPS when ghosts
are frightened. Gameplay timing is preserved, but visible flicker and uneven
refreshes remain. Physical hardware validation is still ahead.

## What comes next

The immediate priority is reducing sprite flicker. We have measured the gaps
between erasing and redrawing actors, and stopped unrelated background changes
from erasing stationary characters. Faster generic sprite drawing now shortens
those gaps further, using fewer CPU cycles and 20 fewer resident bytes.
Moving actors still flicker. A region-composition experiment showed little
visible improvement and was reverted; further changes need fresh measurement.
A raster-timing experiment also showed no perceptible benefit and was reverted
after visual review.
The first ghost-logic optimization removes redundant movement-mask work,
modestly improves throughput and frees another 325 resident bytes.

Score readability is also on the improvement list. We plan to evaluate clearer
digit shapes and spacing for player scores and the high score at the current
resolution, preserving the original scoring behavior.

Supporting improvements include reclaiming memory through careful buffer and
initialization-lifetime analysis; specializing Pac-Man, returning-eye and
clipped-sprite drawing; and optimizing expensive gameplay and sound routines
identified by profiling. Closer sound timbres remain a later possibility.
Hardware changes must remain compatible with documented period equipment.

The first memory-reuse change runs one-time startup code in logical screen RAM
before the game uses it, reclaiming 358 resident bytes for future improvements.
The existing RAM expansion and stack allocations are retained.

Further changes will be introduced and measured individually, preserving the
accepted white-maze appearance and the original arcade behavior.

## Short YouTube video summary

Pac-Man on an expanded VIC-20! This homebrew conversion adapts the original
arcade game logic into native 6502 code, with software sprites, scaled ROM
graphics and music mapped to the VIC's sound hardware. A white maze helps
manage the machine's color limitations, while the original ghost behavior,
scoring and intermissions remain intact.

This video follows a computer-controlled playthrough of the first two boards
and the first intermission, using normal joystick input. Flicker is still
visible; reducing it and improving rendering speed are our next priorities.
