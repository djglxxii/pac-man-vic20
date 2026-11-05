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

The standard build uses the accepted [glyph-pool renderer](docs/GLYPH_POOL.md)
with faster cell addressing, empty-row skipping and
[optimized sound-effect processing](docs/SOUND_EFFECT_OPTIMIZATION.md), plus
the accepted [faster ghost tunnel lookup](docs/TILE_ADDRESS_OPTIMIZATION.md)
and [faster sprite composition](docs/POOL_STAMP_OPTIMIZATION.md), followed by
[precomputed VIC pitch translation](docs/AUDIO_DIVIDER_OPTIMIZATION.md) and a
[compact audio adapter](docs/AUDIO_UPDATE_OPTIMIZATION.md) and
[faster ghost-state dispatch](docs/GHOST_UPDATE_OPTIMIZATION.md), followed by
[cheaper cell allocation](docs/POOL_ALLOC_OPTIMIZATION.md),
[faster background-tile drawing](docs/TILE_STAMP_OPTIMIZATION.md) and
[precomputed sprite preparation](docs/POOL_SETUP_OPTIMIZATION.md) and
[cheaper destination setup](docs/POOL_DEST_OPTIMIZATION.md).
It measures **33.64 redraws/s** on the saved VICE route, about **1.1%** above
the preceding sprite-preparation build. Sound state and VIC register values
match on all 1,639 replayed ticks. `make run-pool-dest-fast` launches the same
version. Occasional stalls and partial poses remain.

The [remaining optimization candidates](docs/RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates)
track the next work. Both ghost-state experiments, the glyph-composition,
cell-allocation, background-tile, sprite-preparation and destination-setup
experiments, and both audio optimizations are accepted. Unchanged-display
reuse has been measured; the larger cache rewrite and redraw-pacing changes
remain deferred.

Memory headroom remains 141 resident bytes before the full 704-byte software
stack and 23 bytes in BLK5. The longest captured redraw gap grows slightly,
61.28 → 61.51 ms, despite the better average. The user requested promotion.

A separate [sprite-shift trial](docs/POOL_SHIFT_OPTIMIZATION.md) is ready for
live review: `make run-pool-shift-fast`. It measures **33.75 redraws/s**, about
**0.3%** above the standard, with the same memory headroom. The maximum native
refresh grows while actual redraw and input/audio gaps improve on this route.
Partial poses remain; `make run` keeps the accepted destination version.

Earlier builds remain available for comparison: `make run-glyph-pool` launches
the original accepted pool (about 22 redraws/s), `make run-pool-address` the
[address improvement](docs/POOL_ADDRESS_OPTIMIZATION.md) (22.80), and
`make run-pool-skip-empty` the [empty-row improvement](docs/POOL_SKIP_EMPTY.md)
(23.21). `make run-sound-effect-fast` retains the sound improvement (25.67).
`make run-tile-address-fast` retains the tunnel-lookup improvement (26.44).
`make run-pool-stamp-fast` retains the composition improvement (27.46).
`make run-audio-divider-fast` retains the pitch-lookup improvement (28.84).
`make run-audio-update-fast` retains the audio-adapter improvement (29.81).
`make run-ghost-update-fast` retains the ghost-state improvement (30.78).
`make run-pool-alloc-fast` retains the cell-allocation improvement (31.55).
`make run-tile-stamp-fast` retains the background-tile improvement (32.21).
`make run-pool-setup-fast` retains sprite preparation (33.29).
`make run-legacy` launches the former underlay renderer (about 33),
which has the excessive flicker addressed by the pool.

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
on the compiled 6502 program. The published PacStrats routes clear this build:
pattern 1 on boards 1–4 and pattern 2 on boards 5–9, played in VICE by
joystick alone, with no deaths and the 10,000-point life collected. The next
direction has to be held about eight pixels before the corner. Pattern 2 also
cleared boards 10–20 in the native simulator. Pattern 3 (board 21 on) and a
physical joystick have not been tried. The recording is
`build/third-intermission/third-intermission.mp4`
([details](docs/VALIDATION.md)).

## VIC compromises

Maze and actor graphics are decoded from the local ROMs. Original tiles become 4×6 pixels
and sprites become 8×12 pixels. [Pac-Man's revised walking and death masks](docs/ASSETS.md#revised-pac-man)
are drawn directly at that size, with one shared closed-mouth frame for every direction.
[Custom letters and digits](docs/FONTS.md)
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
The accepted glyph pool prepares complete character cells off screen before
publishing them. Earlier [underlay-renderer work](docs/SPRITE_FLICKER.md) kept
stationary actors visible during unrelated background changes, but moving
actors still flickered.
The separate [stable-colour trial](docs/STABLE_COLOURS.md) keeps actor colour
priority through redraw, reducing white/actor-colour pulsing in shared cells.
For reproduction, use `make run-stable-colours`. Its actual active capture measures 29.77
redraws/s against 32.88 for the former underlay baseline; actor disappearance remains. User
review reports no perceptible benefit and continued flashing. This trial is
not accepted, and the user has stopped that colour investigation.
The [generic sprite-kernel pass](docs/SPRITE_KERNELS.md) shortens redraw windows
and recovers another 20 resident bytes, with flicker still visible.
The [ghost-state pass](docs/GHOST_STATE.md) removes redundant movement-mask
work and recovers another 325 resident bytes within the same RAM configuration.
The later [ghost-precomposition experiment](docs/GHOST_PRECOMPOSITION.md)
was rejected after user review found no significant flicker improvement to
justify its throughput cost. These earlier measurements concern the former
underlay renderer; the accepted glyph pool is the current starting point.

Further flicker work was paused at the user's request after visual review
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
reproduction. A later [comparison at matched cadence](docs/RATE_MATCH.md)
was noticeably better in user review, prompting a separate
[actor-commit throughput trial](docs/ACTOR_SPEED.md). Try
`make run-actor-speed`: it keeps the current fonts and improves natural
active rendering from 26.40 to 27.55 calls/s, while the normal build remains
faster at 33.13 calls/s on that trace. User review found a possible improvement,
less noticeable than in the initial matched-cadence trial. The overall
benefit remains inconclusive, and the normal renderer remains the default;
precise background invalidation remains deferred.

The [raster-priority revisit](docs/BEAM_PRIORITY.md) was rejected after user
review found no noticeable improvement and a performance hit.
For reproduction, `make run-beam-priority` gives Pac-Man
first choice of a safe raster window and protects nearby ghost groups.
`make run-beam-review` runs the earlier all-group approach. These trials
still manage about 23 redraws/s against 33 for the normal game on the same
input trace, and some updates remain unprotected. Further work on this
approach stops; `make run` continues to launch the accepted renderer.

The [CPU and display profile](docs/DISPLAY_PROFILE.md) now measures the accepted
build before another rendering experiment. In a 1,200-frame active VICE replay,
it completes 32.88 redraws/s. Pac-Man is missing in 165 sampled frames and
partial in 75, with 179 ambiguous frames excluded. The profile records drawing
cost, redraw intervals and visible motion separately. No game code changes.

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

The earlier underlay build's opening CPU-cycle benchmark measures about 52 FPS,
55 FPS when frightened, 44 FPS in the attract chase and 60 FPS in an intermission.
The opening benchmark supplies no continuing joystick turns; active play can
be slower. Those rates are completed renderer calls, not unique motion frames.
Game logic retains its 60.606 Hz clock. Gameplay is not yet a sustained
60 FPS; see [performance measurements](docs/PERFORMANCE.md) and the
[optimization-guide review](docs/OPTIMIZATION_REVIEW.md).
The [research optimization plan](docs/RESEARCH_OPTIMIZATION_PLAN.md) records
completed work and the current candidate queue. Its earlier
[bounded next-board work](docs/BOUNDED_REBUILD.md) keeps input, logic and sound
serviced while the next board draws progressively.

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
