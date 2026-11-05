# Pac-Man on VIC-20: agentic homebrew — Initial Pass

This was the first playable milestone of an agentic homebrew conversion of
arcade Pac-Man to an expanded NTSC VIC-20. Coding agents carried out the
porting, platform implementation, debugging and automated validation. The
project owner set the goals, supplied visual feedback, play tested the builds
and decided which changes to retain.

The agents worked with an existing foundation: Mark Burkley's C translation
of the original arcade program and the Midway ROM set. LLVM-MOS compiles the
adapted C into native 6502 code; handwritten assembly handles platform work
where timing and drawing cost matter. The result is a native VIC-20 game.
The [upstream notes](../src/arcade/UPSTREAM.md) identify the source lineage.

The aim was to preserve movement, ghost behavior, scoring, sound sequencing
and intermissions while adapting their presentation to the VIC-20. The
machine has no hardware sprites, so programmable character graphics provide
the moving actors. The initial renderer restores backgrounds and draws actors
over them. That approach already gives a recognizable, playable arcade
conversion, but exposes distracting erase/redraw flicker.

White maze walls and pellets are a deliberate compromise with the shared
foreground color in each 8×16 cell. Colored actors can tint nearby wall
pixels. The maze flashes blue and white on completion. Arcade music and
effects are mapped to the VIC sound hardware, preserving their sequencing
while approximating the original timbre.

The existing 2:18 VICE recording belongs to this initial milestone. It clears
the first two boards, completes the first intermission and briefly reaches
board 3, with one life lost. A computer-controlled joystick bot supplies
ordinary input. That recording bot is separate from the coding agents used
to develop the game.

Later work introduced the glyph-pool renderer, revised artwork and lettering,
and fourteen accepted speed improvements. Those belong to the
[Final Optimized milestone](final/WRITEUP.md). The original recording is not
evidence of that later renderer's performance.

## Short video summary

An agentic homebrew Pac-Man conversion for the VIC-20, developed with coding
agents under human direction and play testing. This initial pass already
preserves the arcade maze, ghost behavior, scoring, sound sequencing and
intermissions. A joystick bot plays through two boards and the first
intermission in VICE. Visible flicker remains here; the later optimized
milestone tackles that problem.

## Upload assets

Use [the initial title](title.txt), [description](description.txt) and
[pinned comment](pinned-comment.txt). The
[landscape thumbnail](vic20-pacman-thumbnail.png) and
[portrait cover](vic20-pacman-shorts-cover.png) both identify this as
**AGENTIC HOMEBREW — INITIAL PASS**, built with coding agents.
