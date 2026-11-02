# Arcade parity validation

Reference: the local Midway US `pacman.zip`, normal difficulty, three lives,
bonus life at 10,000 points. The program ROM CRCs are `c1e6ab10`, `1a6fb2d4`,
`bcdd1beb` and `817d94e3`. The build records every input ROM's SHA-256 in
`build/arcade/rom-manifest.json`.

This revision replaces the initial custom engine with a native 6502
adaptation of the arcade routines. Graphics, messages, movement masks,
difficulty tables, fruit, songs and effects come from the local ROM set.
The [baseline audit](ARCADE_PARITY_AUDIT.md) describes the superseded engine.
The [source provenance](../src/arcade/UPSTREAM.md) identifies the translation
and the errors repaired during comparison with the original instructions.

## Reproduce the checks

```sh
make clean
make -j2 test
make vice-test
```

Result on 2026-11-01: **15 ROM comparison tests, six native tests, four
renderer tests, six maze-color tests, three maze-flash tests and eight
bounded-rebuild tests passed** (42 total),
followed by the frontend
smoke run and the VICE check.
The smoke run exceeded 7,000 logical ticks with its IRQ vector and stack guard
intact; its clock measurement matched 180.96 ticks across 180 NTSC video frames
within the boundary tolerance. VICE
accepted coin/start and recorded non-silent 48 kHz mono audio.

The PRG loads below `$8000` before unpacking into BLK1/2/3/5. The packer
verifies both decompressed banks and checks that its
output cannot overwrite unread compressed data.

The reference runner executes the unmodified Z80 program, using a separate
CPU implementation. It does not call the converted game routines. The
host runner compiles the same C core as the VIC program. The native checks
execute the actual compressed PRG, loader, IRQ handler and 6502 instructions.

## What is compared

`tests/arcade.py` compares logical screen RAM, palette RAM, game state and
the meaningful nibbles of the Namco sound registers after each tested tick
or routine call. Its cases cover:

- The original 240 dots and four energizers, character introductions,
  attract chase and maze demonstration.
- First-life movement, timed directional input, early turns, scoring and
  the complete first death sequence.
- Four hundred ghost-target cases, including steering ties, scatter/chase,
  Elroy targeting and Pinky/Inky's upward-coordinate overflow.
- Eight hundred frightened-direction calls and all 1,536 stored random
  values against the ROM-backed sequence.
- All 21 difficulty entries, both fruit releases at 70/170 dots, later-board
  fruit selection and Elroy thresholds.
- Score carries, high scores, extra lives, score wraparound, coin debounce,
  queued credits, BCD credit subtraction and one/two-player starts.
- Reserve-life and fruit-history drawing, including board 256's overflow.
- Intermission selection and complete traces of all three animations.
- Both songs, all 16 used channel/effect combinations, and simultaneous
  effect masks that exercise channel priority, each for 192 sound ticks.

`tests/native.py` compares 600 compiled-6502 movement/turn/scoring ticks
and 300 frightened-mode ticks against the Z80 runner. It also checks the
PRG's address limits and every possible eight-bit square against the
smaller native lookup table.

Native audio tests check the threshold-based divider around every rounding
boundary and the complete five-register VIC output for 160 varied inputs.
`tests/render.py` compares the assembly compositor against an independent
bitmap model: 2,048 frame/shift/flip combinations, 160 six-actor clipping and
overlap scenes, and 360 consecutive incremental frames, including background
changes. Each comparison covers pixel data, color data and underlay restoration.
The fast-ghost test adds 256 visible frame/shift/flip cases and checks that
each executes the pre-shifted path, alongside the independent pixel model.

`tests/colors.py` derives pellet coverage from the decoded source pixels. It
checks a real maze's white walls/pellets and unchanged bitmap, shuffled tile
order, white walls after last-pellet removal, power-pellet blinking, all vertical
cell boundaries, dirty-map overflow and sprite color restoration. Its sixth
check limits blue wall rendering to completion-flash states, including a full
redraw. The compositor oracle checks
that an aligned sprite leaves its empty right column's color unchanged.

The comparisons load shared reference snapshots at stable points. Large
screen-building tasks span multiple arcade CPU frames; the native port
drains that task queue together. Tests therefore begin animation and maze
traces after those setup tasks finish. They do not claim that every
intermediate screen-building write occurs at the same wall-clock time.

`tests/flash.py` adds 64 palette/pixel/underlay comparisons against full
redraws, covering all fruit types and history lengths. It checks the complete
four-pair flash sequence, request-to-display timing, continued audio updates,
and wall coverage after incremental dot removal. Captures and timing reports
are in `build/maze-flash/`; see [MAZE_FLASH.md](MAZE_FLASH.md).

`tests/rebuild.py` adds eight checks for all dirty-map addresses, bulk video
writes against the original ROM, cursor replay/restarts, the split native
state clear, complete transition timing/queue order, a coin during rebuilding,
and actor movement before final composition. Input/audio gaps stay below two
arcade ticks in the focused transition. A settled board takes longer to
present than the old blocking draw; see [the measured tradeoff](BOUNDED_REBUILD.md).

## VIC frontend checks

`tests/smoke.py` boots the PRG, inserts a coin, starts a game, triggers a
fruit and advances completed boards into all three intermissions. Board
completion is injected for these scene checks; this is not a natural
playthrough to board 10. The run continues for more than 7,000 logical ticks
and checks that the IRQ vector and software-stack guard remain intact.
It also measures the VIA clock against the NTSC video clock: 180 video
frames should contain about 180.96 arcade ticks, allowing boundary rounding.

Images, RAM captures and `native-validation.json` are written to
`build/preview/`. Simulator images are captured between completed renders
so partially drawn software sprites are not mistaken for bad source art.

`make vice-test` independently boots the PRG in VICE's expanded NTSC VIC-20,
inserts a coin through the joystick port, releases and presses fire to start,
and verifies active gameplay. It saves actual emulator screenshots, a
48 kHz WAV containing the start tune and play, and `vice-validation.json`.
The audio check verifies valid, non-silent output; waveform fidelity is
limited by the VIC hardware and is not asserted by that check.
The optional `--maze-flash` mode of `tools/arcade/vice_check.py` also forces
board completion, verifies all eight physical blue/white phases, and saves
`vice-maze-flash.gif`. It also captures progressive next-board work and verifies
the new board settles. This mode runs VICE at normal speed for reliable capture.

`make performance` counts completed renders and records frame intervals from
emulated CPU cycles. Current gameplay samples reach about 48–54 FPS; the sampled
intermission reaches 60 FPS. [PERFORMANCE.md](PERFORMANCE.md) records the method,
changes and remaining frame budget, including the longer coherent draw interval
during progressive next-board construction.
The game timer rate alone does not establish
the display refresh rate.

## Remaining differences and limits

- The full screen is reduced to 112×216 native pixels, with 4×6 tiles and
  8×12 sprites. NTSC pixel aspect restores the portrait proportions.
- One foreground color per 8×16 cell causes wall/dot and sprite color
  clashes. Eight foreground colors cannot exactly match the arcade palette.
  Small eyes, fruit details and lettering lose information when scaled.
- Software sprite drawing can skip refreshes while pending game ticks run.
  This preserves logic throughput but does not reproduce arcade raster timing.
- Three square-wave voices and a shared volume approximate the arcade's
  independent wavetable voices. Pitch is quantized to VIC dividers; timbre
  and per-voice envelopes differ. Original sequencing and priorities remain.
- The game uses upright controls. Arcade board self-tests, service switches,
  cabinet outputs and cocktail display rotation are not exposed as VIC modes.
  PAL machines are not supported by this timing configuration.
- The tested input traces support pattern compatibility, but every published
  pattern has not been played or certified. Physical joystick sampling,
  initial input timing and presentation-task timing still require care.
- Board 256 is checked through its fruit-history routine, not a complete
  255-board playthrough. Real hardware has not been tested in this workspace.

The goal is the closest practical arcade conversion. These checks establish
specific matches; they do not certify a pixel-, waveform- or cycle-identical
replacement for an arcade board.
