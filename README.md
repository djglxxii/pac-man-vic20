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

Graphics are decoded from the local ROMs. Original tiles become 4×6 pixels
and sprites become 8×12 pixels. The full portrait screen occupies 112×216
native pixels; NTSC's wide pixels restore the original proportions.

The VIC has no hardware sprites. Its eight foreground colors and one color
per 8×16 character cause color clashes, and small facial details are reduced.
Drawing can skip refreshes to let the game logic catch up. These are visible
differences from an arcade board.

The current CPU-cycle benchmark measures about 49 FPS in normal play,
53 FPS when frightened, 45 FPS in the attract chase and 60 FPS in an intermission.
Game logic retains its 60.606 Hz clock. Gameplay is not yet a sustained
60 FPS; see [performance measurements](docs/PERFORMANCE.md) and the
[optimization-guide review](docs/OPTIMIZATION_REVIEW.md).

The [end-of-stage maze flash](docs/MAZE_FLASH.md) changes colours without
rebuilding the bitmap. Its four blue/white pairs retain the arcade timing;
full drawing of the next board can still pause separately.

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
- `src/video.c`, `src/bitmap.S`, `src/sprites.S`: bitmap display and incremental
  native sprite compositor.
- `tools/arcade/`: local asset extraction, PRG packing and original-ROM runner.
- `tests/`: comparisons with the Z80 reference and the built VIC program.

The [baseline audit](docs/ARCADE_PARITY_AUDIT.md) records the custom engine
that this revision replaces; its findings are historical.
