# Pac-Man for the VIC-20

A private, local homebrew conversion of the original Midway Pac-Man ROM set
for an NTSC VIC-20 with full RAM expansion. The target is arcade behavior,
including its maze, ghost rules, attract sequence, intermissions and quirks.

## Start it

```sh
make run
```

This builds `build/pacman.prg` and launches VICE (`xvic`) with all required
RAM blocks enabled. The first build installs a pinned LLVM-MOS toolchain
locally if it is missing; the current workspace already has it.

- **Arrow keys:** move, using joystick port 1's keyboard mapping.
- **5:** insert a coin. **1:** start one player. **2:** start two players
  after inserting two coins.
- **Space / joystick fire:** insert a coin when there are no credits;
  release and press again to start. Down + fire adds another coin;
  up + fire starts two players.

On a real expanded VIC-20, load the PRG as `PACMAN`:

```basic
LOAD"PACMAN",8,1
RUN
```

The machine needs +3K at `$0400` and 8K blocks at `$2000`, `$4000`, `$6000`
and `$A000`. PAL timing is not supported.

This is +35 KB of expansion RAM, or 40 KB including the built-in RAM.
The hardware target must remain period-correct; future hardware requirements
need contemporary evidence. See the
[hardware constraint](docs/RESEARCH_OPTIMIZATION_PLAN.md#constraints-and-recommendations-to-adapt).

The [memory-reuse pass](docs/MEMORY_REUSE.md) runs one-time startup code in
logical screen RAM, then releases that area to the game. This reclaims 358
resident bytes within the same hardware configuration and load procedure.

## Arcade behavior

The conversion uses the original 28×31 maze, 240 dots and four energizers.
The arcade routines provide movement patterns, early turns, tunnel behavior,
ghost-house release, scatter/chase transitions, frightened movement, Cruise
Elroy, scoring, three starting lives and the extra life at 10,000 points.
Pinky and Inky retain the original upward-target overflow behavior.

Fruit appears after 70 and 170 dots. All eight fruit/item types follow the
original board progression, including the key from board 13 onward. The
original character introductions, credit/start screens, demonstration play,
death animation, two-player turns and all three intermissions are included.
Intermissions occur after boards 2, 5, 9, 13 and 17. The board-256 fruit-history
overflow is retained.

Movement stays in arcade pixels and runs from a 60.606 Hz VIA timer. Tests
compare game state against the original Z80 program and compare input traces
on the compiled 6502 program. This supports arcade pattern compatibility;
every published pattern and physical joystick timing have not been certified.

## VIC compromises

Maze and actor graphics are decoded from the local ROMs. Original tiles become 4×6 pixels
and sprites become 8×12 pixels. [Custom letters and digits](docs/FONTS.md)
use shapes drawn at the displayed size, including ghost and fruit scores.
Ghost and fruit rewards stay on one line. The wider ghost numbers borrow
Pac-Man's hidden drawing slot during the reward pause.
[Compare the fonts](docs/artwork/fonts/font-comparison.png).
The full portrait screen occupies 112×216
native pixels; NTSC's wide pixels restore the original proportions.

The VIC has no hardware sprites. Its eight foreground colors and one color
per 8×16 character cause color clashes, and small facial details are reduced.
The [maze and standing pellets are white](docs/WHITE_MAZE.md). Completion
flashes the maze blue/white for four pairs, starting blue. An actor can
temporarily recolor a shared cell. Aligned sprites leave their empty neighboring
column's color alone.
Drawing can skip refreshes to let the game logic catch up. These are visible
differences from an arcade board.
The [first flicker reduction](docs/SPRITE_FLICKER.md) keeps stationary actors
visible during unrelated background changes; moving actors can still flicker.
The [generic sprite-kernel pass](docs/SPRITE_KERNELS.md) shortens redraw windows
and recovers another 20 resident bytes, with flicker still visible.
The [ghost-state pass](docs/GHOST_STATE.md) removes redundant movement-mask
work and recovers another 325 resident bytes within the same RAM configuration.
The later [ghost-precomposition experiment](docs/GHOST_PRECOMPOSITION.md)
was rejected after user review found no significant flicker improvement to
justify its throughput cost. The faster main build remains in place.

Further flicker work is on hold at the user's request after visual review
found no meaningful overall improvement in the latest comparison. The
[temporary-character experiment](docs/GHOST_SHADOW.md) was rejected after user
play testing found no perceptible improvement, while normal play fell from
about 52 to 34 FPS. Its separate target and comparison remain for reproduction.
The original `make run` executable is unchanged. The multicolour redesign below
also remains on hold.

The [beam-scheduled experiment](docs/BEAM_FOLLOW.md) also produced no
perceptible benefit in user review. A [capture audit](docs/CAPTURE_AUDIT.md)
confirms that different programs ran, but finds that the quoted native
benchmark FPS did not describe the recorded playthrough. A fresh active
capture measures about 33 renderer calls/s for the original and 24 for the
beam build. Both experiments remain separate diagnostic targets.

The [independent-actor commit trial](docs/ACTOR_COMMIT.md) shortens the mean
opening actor window from 5.662 to 2.539 ms, but its fresh longer active
capture falls from 30.92 to 24.13 renderer calls/s. It fails the throughput
budget and was rejected after user review: flicker shifts between sides with
no meaningful overall improvement. It remains separate from the default for
reproduction. Further flicker experiments, including precise background
invalidation, are on hold.

A [selected multicolour redesign](docs/MULTICOLOUR_PROTOTYPE.md) uses a wider
maze, blue walls, white pellets, custom actors and hires score digits. Its
separate [moving renderer test](docs/MULTICOLOUR_MOTION.md) demonstrates hidden
character preparation in VICE. Retained optimizations reduce mean rendering
from 29.421 to 19.019 ms in the same 480-scene replay, preserving the approved
pixels. The latest [background glyph ordering](docs/MULTICOLOUR_BACKGROUND_LAYOUT.md)
saves another 0.05% of renderer CPU time without increasing memory use;
unchanged-group reuse was rejected after measurement.
A first [live integration](docs/MULTICOLOUR_GAME.md) now connects those visuals
to the actual game, controls, pellets, scores and sound. Try
`make run-multicolour` or [watch gameplay with audio](build/multicolour-game/vice/playable-preview.mp4).
This development target currently manages about 9 display updates/s and still
has fallback animation states. It needs further work before replacing the
default game; standalone micro-optimizations are on hold.

The default hires build's opening CPU-cycle benchmark measures about 52 FPS,
55 FPS when frightened, 44 FPS in the attract chase and 60 FPS in an intermission.
The opening benchmark supplies no continuing joystick turns; active play can
be slower. Those rates are completed renderer calls, not unique motion frames.
Game logic retains its 60.606 Hz clock. Gameplay is not yet a sustained
60 FPS; see [performance measurements](docs/PERFORMANCE.md) and the
[optimization-guide review](docs/OPTIMIZATION_REVIEW.md).
The [research optimization plan](docs/RESEARCH_OPTIMIZATION_PLAN.md) records
the changes in priority order. Its first item,
[bounded next-board work](docs/BOUNDED_REBUILD.md), now keeps input, logic and
sound serviced while the next board draws progressively.

The [end-of-stage maze flash](docs/MAZE_FLASH.md) changes colours without
rebuilding the bitmap. Its four blue/white pairs retain the arcade timing;
the next board takes longer to become fully coherent than the old blocking
draw, with a measured gap of about 1.84 seconds between completed refreshes.

The original music, effect tables, priorities and sequencing drive the VIC's
three tone voices. Square waves approximate the arcade waveform PROMs; timbre
and individual voice envelopes differ because the VIC shares one volume
control. See [the asset notes](docs/ASSETS.md) and
[validation details](docs/VALIDATION.md).

## Build and test

```sh
make            # build the single self-extracting PRG
make test       # original-ROM comparisons and compiled-6502 checks
make performance # completed render rates and frame intervals at NTSC CPU speed
make vice-test  # optional real VICE boot, coin/start, video and audio capture
```

An [automated playthrough recorder](docs/PLAYTHROUGH_CAPTURE.md) can drive
the unchanged game through the first intermission and save an MP4 with sound:
`python3 tools/arcade/record_playthrough.py`. It needs VICE and FFmpeg.

Dependencies: Python 3 with Pillow, a C compiler, ca65/ld65, and the pinned
LLVM-MOS SDK. The Makefile uses the local `tools/cc65` installation or tools
on `PATH`. `tools/bootstrap-llvm-mos.py` installs LLVM-MOS v23.4.0 under
`tools/llvm-mos`; downloaded toolchains and generated files are ignored by git.
VICE also needs its VIC-20 BASIC, KERNAL and character ROMs installed.

The supplied `pacman.zip` remains the asset and reference source. Nothing in
the build publishes the project or sends its ROMs to a service.

## Source

- `src/arcade/`: native adaptation of the original game routines, with
  upstream MIT notices and [provenance](src/arcade/UPSTREAM.md).
- `src/pacman.c`, `src/platform.c`, `src/clock.S`, `src/audio.S`: VIC startup,
  controls, game clock and sound-register conversion.
- `src/video.c`, `src/bitmap.S`, `src/rebuild.S`, `src/tasks.S`, `src/sprites.S`:
  bitmap display, bounded board construction and incremental sprite compositor.
- `tools/arcade/`: local asset extraction, PRG packing and original-ROM runner.
- `tests/`: comparisons with the Z80 reference and the built VIC program.

The [baseline audit](docs/ARCADE_PARITY_AUDIT.md) records the custom engine
that this revision replaces; its findings are historical.
