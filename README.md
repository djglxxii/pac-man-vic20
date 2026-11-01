# SNAPBUG

A maze-chase game for the Commodore VIC-20 (NTSC), written in 6502 assembly.
You're a beetle eating seeds in a maze while four spiders hunt you. Eat a
honey drop and the spiders turn blue for a few seconds, and you can eat them.

The maze and enemy behaviors are original. Graphics use arcade Pac-Man
silhouettes adapted to the VIC-20's 8×8, single-color sprites. Music and
effects adapt arcade pitch and timing data to the VIC's tone voices.

## Requirements

- An NTSC VIC-20 with the full memory expansion: 3K at `$0400`, 8K blocks at
  `$2000`/`$4000`/`$6000` and 8K at `$A000`. In VICE that's `-memory all`.
- A joystick in port 1.

## Building and running

```sh
make            # builds build/snapbug.prg (needs python3 + Pillow, ca65/ld65)
make run        # launches VICE (xvic) as an NTSC VIC-20 with full RAM
make test       # headless play test: bot plays ~8 minutes of game time
```

cc65 is unpacked locally in `tools/cc65` (from the Ubuntu `cc65` package). If
it's missing, the Makefile falls back to the `ca65`/`ld65` on your PATH.

**Controls in VICE:** arrow keys move, space is fire (press it to start).
This joystick-on-keyboard mapping comes from `tools/vice-keys.vrc`; a USB
gamepad can be picked instead under Settings → Joystick.

**ROMs:** Debian/Ubuntu's `vice` package ships without the Commodore ROMs.
Copy `data/VIC20/*.bin` and `data/DRIVES/*.bin` from the official VICE source
release (vice-emu.sourceforge.net) into `~/.local/share/vice/VIC20/` and
`~/.local/share/vice/DRIVES/`.

On a real machine: `LOAD"SNAPBUG",8` then `RUN`.

## How to play

| Item           | Points                   |
|----------------|--------------------------|
| Seed           | 10                       |
| Honey drop     | 50                       |
| Spiders eaten  | 200, 400, 800, 1600      |
| Bonus item     | 100 to 5000, by level    |

You get an extra life at 10,000. A bonus item appears below the nest after
60 and 140 seeds. The tunnel at the sides wraps around and slows spiders down.

### The cast

Each spider makes its decisions at tile centers and never reverses on its own.

- **STALKER** (red) heads for the tile you're on.
- **PROWLER** (purple) charges if it can see you in a straight, open row or
  column. Otherwise it patrols, alternating left-hand and right-hand turns at
  each junction.
- **MIRROR** (cyan) heads for your position mirrored through the center of the
  maze. It's far away when you're near the edges and closes in as you cross
  the middle.
- **TRACKER** (yellow) follows your scent: it heads for where you were about
  two seconds ago.

Frightened spiders pick exits with a pseudo-random generator that is reseeded
at the start of every life. All movement uses fixed-point speeds advanced once
per frame, so the game is deterministic: the same joystick input always
produces the same game, and routes you work out can be repeated.

## Technical notes

**Display.** The screen is 21×24 characters at `$1000`, with the character set
at `$1800`. These are the only places the VIC chip can see when RAM is
expanded. Rows 0–1 hold the score, rows 2–22 the 21×21 maze, and row 23 shows
spare lives and level items.

**Smooth movement with characters.** The renderer is in `src/render.s`.

- Character codes `$C0–$FF` are two pools of 32 "dynamic" characters.
- Each frame, every actor is drawn into the pool that is *not* on screen. For
  each 8×8 cell an actor overlaps (up to 2×2), it takes a free dynamic
  character, copies in the background tile, then merges the sprite using
  `(background AND NOT mask) OR image`.
- Actors that share a cell are drawn into the same character.
- Once the raster passes the bottom of the display, `flip` points those cells
  at the new characters, restores cells that are no longer covered, and swaps
  pools. This gives tear-free, one-pixel movement.

**Pre-shifted sprites.** All 36 sprite images are pre-shifted into all 8
horizontal positions, with their masks, when the game starts. They fill the
8K block at `$A000` plus `$7000`. Each image gets one 256-byte page, so a
sprite's data address is just `page:shift*32`.

**Timing.** Game logic and drawing finish before the next frame. The play
test measured normal play at no more than about 68% of an NTSC frame (261
lines × 65 cycles). The overall peak, about 82%, happens during the
level-clear transition (wall flash and maze redraw).

**Memory map.**

| Address       | Contents                                              |
|---------------|-------------------------------------------------------|
| `$0002–$00FF` | zero-page variables                                   |
| `$0400–$09FF` | background map, color map, overlay map (3K block)     |
| `$0A00–$0FFF` | other variables                                       |
| `$1000–$11F7` | screen                                                |
| `$1201`       | BASIC `SYS 8192` stub                                 |
| `$1800–$1FFF` | character set                                         |
| `$2000–$6FFF` | code and data                                         |
| `$7000–$7FFF` | pre-shifted sprite pages 32 and up                    |
| `$A000–$BFFF` | pre-shifted sprite pages 0–31                         |

**Sound.** The engine is in `src/sound.s`. Each of the VIC's voices plays a
one-shot effect when one is active, otherwise its looping background sound
(the siren, fright warble or eyes returning). All sound data comes from
`tools/mksound.py`.

## Source layout

| Path                    | Contents                                               |
|-------------------------|--------------------------------------------------------|
| `src/snapbug.s`         | startup, main loop, game modes (title, ready, play, death, level clear, game over) |
| `src/render.s`          | soft-sprite compositor, flip, background cell writes, printing |
| `src/actors.s`          | player movement and cornering, spider AI, nest release, fright, collisions, bonus |
| `src/screen.s`          | score, high score, status line, maze setup             |
| `src/sound.s`           | sound engine                                           |
| `src/tables.s`          | lookup tables and per-level tuning (speeds, fright time, release rules) |
| `tools/mkdata.py`       | maze definition and checks (symmetry, no dead ends, connected), wall autotiling, font, tiles, sprites, eyes-return pathfinding table |
| `tools/mksound.py`      | music and sound effects                                |
| `tools/vicsim/`         | headless VIC-20 test emulator: 6502 core that passes Klaus Dormann's functional test, raster timing, joystick, screenshots |
| `tests/bot.py`          | automated play test                                    |
| `tests/sound.py`        | sound stream timing, looping, voice routing and priority checks |

To change the maze, edit `MAZE` in `tools/mkdata.py` and run `make`. The
generator rejects mazes that aren't symmetric, have dead ends or aren't fully
connected.

To make your own sprites, tiles, font or sound, see [docs/ASSETS.md](docs/ASSETS.md).
