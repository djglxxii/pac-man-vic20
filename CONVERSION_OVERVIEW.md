# Bringing Pac-Man to the VIC-20 with coding agents

This is an **agentic homebrew** conversion: coding agents performed the
porting, VIC-20 implementation, debugging, profiling and automated validation
under the project owner's direction. Human play testing and visual review
determined which experiments were kept.

The conversion builds on [Mark Burkley's C translation of the arcade
program](src/arcade/UPSTREAM.md). LLVM-MOS compiles the adapted C into native
6502 code, with handwritten assembly for graphics, audio and platform work.
ROM data provides the reference artwork, music, effects and difficulty tables.
The goal is to retain the original movement, ghost rules, scoring, sound
sequencing, quirks and all three intermissions.

## From the initial pass to the optimized milestone

The [Initial Pass](youtube/INITIAL_PASS.md) was already playable and close to
the arcade. Its software sprites used programmable character graphics, since
the VIC-20 has no hardware sprites. Erasing and redrawing moving actors caused
the distracting flicker that prompted the later work.

The major visual improvement was the finished-cell glyph pool. The renderer
composes backgrounds and overlapping actors in hidden character slots, then
publishes completed cells. Live play testing found this a substantial
improvement. Partial poses, color sharing and uneven pacing still occur.

Fourteen accepted speed improvements then raised the pool renderer from
**22.07 to 33.85 completed redraws/s** on the saved VICE route, approximately
53%. They target drawing, address calculations, ghost processing and audio
translation. These route averages are separate from the approximately
60.606 Hz gameplay clock and do not establish a fixed display frame rate.

We also refined the graphics for Pac-Man himself and the frightened (scared)
ghosts, reused Pac-Man's symmetrical closed-mouth frame across directions,
and redesigned the fonts for more legible letters, score numerals and
horizontal reward scores on the small display.
White walls and pellets remain the accepted shared-color compromise, with
blue/white completion flashing. The original sound sequence is mapped to the
VIC's sound hardware; precomputed pitch translation avoids repeated division
without substituting a prerecorded soundtrack.

## Why the visuals still show compromises

In our high-resolution mode, each 8×16 character cell has one foreground color
against the shared black background. All lit pixels in that cell share it.
A yellow Pac-Man or colored ghost can therefore tint a nearby wall or pellet
in the same cell, even without touching its visible pixels. White walls make
that color clash less distracting; they cannot remove the hardware limit.
Standing pellets are white when no colored actor shares their cell.

The VIC-20 has no hardware sprites or native bitmap mode. We redefine
programmable characters to draw actors at pixel offsets. An actor can span
several cells, so the roughly 1 MHz CPU must combine its pixels with the
background and other actors while also servicing game logic, input and sound.
The glyph pool reduces visible erase/redraw flicker, but shared colors,
partial poses and uneven redraw intervals can remain.

Expansion RAM provides space for code and tables, but the video chip can read
graphics from only a limited memory area. It does not add independent sprite
layers, per-pixel color or CPU speed. Multicolor mode trades horizontal detail
for more colors, affecting the small faces and fonts. The VIC's tone voices
also share a volume control and approximate the arcade's different sound
hardware while retaining its music and effect sequencing.

## Validation and next steps

Comparisons with the original Z80 program, native 6502 routine checks,
game-state and sound replays, graphics oracles and VICE captures guide the
work. The accepted default passes its full regression checks, including all
three intermissions. A joystick bot used for gameplay recordings is separate
from the coding agents used to develop the conversion.

The hardware target remains an expanded NTSC VIC-20 with +3K and BLK1/2/3/5
RAM, retaining the full software stack. Physical hardware validation remains
ahead.

The final upload, through-game-over.mp4, follows the PacStrats patterns
documented in [10yard's pactrainer](https://github.com/10yard/pactrainer).
It clears boards 1–9 and completes the third intermission with no deaths.
The run is then deliberately ended to show the death animation and Game Over
screen.

The current optimization pass is complete. Extended play testing, gameplay
checks and presentation polish come next; further optimization should address
a noticeable, measured problem. See the
[Final Optimized write-up](youtube/final/WRITEUP.md) for the full optimization
series and [YouTube upload package](YOUTUBE_UPLOAD.md) for both milestones.
