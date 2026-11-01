# Making graphics and sound for SNAPBUG

This guide explains how to create your own graphics, maze and sound for the
SNAPBUG engine on the NTSC VIC-20. It covers what the hardware and engine
allow, where each asset lives, the formats the build tools expect, and how to
check your work.

All assets are written as **text in two Python scripts**. There are no image
or audio files to import. `make` runs the scripts, checks what you wrote, and
turns it into assembler data:

| Asset                                  | Where you edit it   | What it produces                        |
|----------------------------------------|---------------------|-----------------------------------------|
| Sprites, font, maze tiles, bonus items | `tools/mkdata.py`   | `build/gen/charset.bin`, `consts.inc`, `data.inc` |
| Maze layout                            | `tools/mkdata.py`   | maze tables in `data.inc`               |
| Music and sound effects                | `tools/mksound.py`  | `build/gen/sound.inc`                   |

---

## 1. What the VIC-20 can show

Everything follows from four hardware facts. Design for them from the start.
Art that ignores them won't survive being scaled down.

1. **Every graphic is an 8×8 grid of on/off pixels.** The VIC chip has no
   hardware sprites. SNAPBUG fakes them by drawing into spare characters every
   frame. Each sprite image is exactly **8×8 pixels, 1 bit per pixel**.
2. **One color per 8×8 screen cell.** A cell shows its "on" pixels in one
   foreground color, over the black background. When a sprite overlaps a seed
   or wall, that whole cell takes the sprite's color for a moment. Small,
   compact sprites hide this best.
3. **Only 8 foreground colors** in hi-res mode:

   | # | Color  | # | Color  |
   |---|--------|---|--------|
   | 0 | black  | 4 | purple |
   | 1 | white  | 5 | green  |
   | 2 | red    | 6 | blue   |
   | 3 | cyan   | 7 | yellow |

   VICE's default palette shows green (5) as a bluish teal. Don't rely on 3
   and 5 to tell two characters apart.
4. **Pixels are wide.** On an NTSC TV a VIC-20 pixel is about 1.5 times wider
   than it is tall. A shape drawn as a perfect circle on an 8×8 grid shows up
   as a wide oval. To look round, a shape should be about 1 pixel narrower
   than it is tall (for example 6 wide × 7 tall). Use the wide-pixel previews
   in section 7 or check in VICE when judging proportions.

### Working at 8×8

- **Start from the silhouette.** At this size people recognize a character
  by its outline, not its details. Fill in the shape first, then cut holes
  for eyes, mouths and so on.
- **Use single empty pixels for eyes and other features.** A 1-pixel hole in
  a solid shape reads far better than a 1-pixel dot on black.
- **Leave a 1-pixel border free when you can.** The maze corridors are 8
  pixels wide, so a full 8-pixel-wide sprite touches the walls on both sides.
  A 6–7-pixel-wide body looks cleaner as it moves through the maze.
- **Make animation frames differ in only a few pixels.** Two frames that
  share an outline and differ by 2–6 pixels (legs, jaws) animate smoothly.
  Frames with different outlines flicker.

---

## 2. The pixel format

All bitmaps use the `art()` helper in `tools/mkdata.py`: **8 strings of 8
characters**, top row first. `X` or `#` means the pixel is on; anything else
(`.` by convention) means off.

```python
MY_SHAPE = art(["..XXXX..",
                ".XXXXXX.",
                "XX.XX.XX",
                "XXXXXXXX",
                "XXXXXXXX",
                ".XXXXXX.",
                ".X.XX.X.",
                "X......X"])
```

Each string becomes one byte, with the leftmost character as bit 7. If a
string is shorter than 8 characters it is padded with `.`. If a list doesn't
have exactly 8 rows, the build stops with an error.

Helpers for making variations:

| Helper           | Effect                                            |
|------------------|---------------------------------------------------|
| `rot_cw(b)`      | rotates 90° clockwise                             |
| `flip_h(b)`      | mirrors left↔right                                |
| `flip_v(b)`      | mirrors top↔bottom                                |
| `silhouette(b)`  | builds the mask (see section 3.3); applied automatically |

---

## 3. Sprites

### 3.1 The sprite list

The engine refers to sprites by **index**, and the order is fixed.
`sprites()` in `mkdata.py` builds this list and writes a constant for each
image (`IMG_BUG_D0_F0`, `IMG_FRIGHT_F1`, …) to `build/gen/consts.inc`.

| Index | Name            | Count | Used for                                         |
|-------|-----------------|-------|--------------------------------------------------|
| 0–7   | `bug_d{d}_f{f}` | 4 dirs × 2 frames | player wide/narrow mouth; frame 0 when stopped |
| 8–15  | `spider_d{d}_f{f}` | 4 dirs × 2 frames | normal enemies; frame changes every 8 frames |
| 16–17 | `fright_f0/f1`  | 2     | frightened enemies (all four share them)         |
| 18–21 | `eyes_d{d}`     | 4     | eaten enemy returning to the nest                |
| 22–25 | `pop0`–`pop3`   | 4     | player death animation (`pop3` blank)            |
| 26–33 | `pts{N}_l/_r`   | 4 × 2 | score popups 200/400/800/1600 (16 px wide, two halves) |
| 34    | `bug_closed`    | 1     | shared closed-mouth player frame                 |
| 35    | `pop_spark`     | 1     | final burst in the death animation               |

Directions are always **0 = up, 1 = left, 2 = down, 3 = right**.

**Limits**

- **40 images at most.** Each image is pre-shifted into a 256-byte page at
  startup: 32 pages at `$A000–$BFFF` and 8 at `$7000–$77FF`. `mkdata.py`
  checks this (`assert len(imgs) <= 40`). Going above 40 means changing the
  memory layout (`img_page` in `src/tables.s`, `gen_shifts` in
  `src/render.s`).
- **Keep the order.** You can redraw any image freely. If you add, remove or
  reorder images, also update the code that uses the `IMG_*` constants:
  `build_player`, `build_enemies`, `death_seq`, the title screen in
  `src/snapbug.s`, and `chain_img` in `src/actors.s`.

### 3.2 Which images you draw, and which are generated

`sprites()` mirrors poses and generates the directional eyes:

- **Player (`BUG_UP`, `BUG_RIGHT`)**: draw wide and narrow mouths facing
  up and right. Down is a vertical flip of up; left is a horizontal flip of
  right. Each pose fits the same 6×8 disk, so it stays round on wide NTSC
  pixels when changing direction. `BUG_CLOSED` supplies the shared closed
  disk. `build_player` cycles wide → narrow → closed → narrow, advancing
  every 2 pixels moved. `LIFE` uses the right-facing wide mouth.
- **Enemies (`SPIDER_UP`)**: draw 2 solid body frames, changing only the
  bottom row for the waving skirt. `build_eye_variant()` cuts the two-pixel
  eye holes listed in `SPIDER_EYES`, in rows 2–4 (counting from 0). It
  preserves the rest of the body. Keep a solid rim around these holes.
- **Frightened (`FRIGHT`)**: draw the same dome with small eye holes and a
  zigzag mouth; keep the face fixed between skirt phases.
- **Returning eyes (`EYES`)**: generated from white sockets (`EYES_MASK`)
  with black directional pupils (`EYE_PUPILS`).
- **Death (`POP`, `POP_SPARK`)**: the sequence in `death_seq` starts with a
  closed disk, opens upward through the player poses, collapses to a lower
  crescent and line, then bursts and disappears.
- **Score popups** are generated from the 3×5 digits in `MINI`. A new
  value needs its digits added to `MINI`, a matching `popup_pair()` call in
  `sprites()`, and an update to the points table in `src/actors.s`.

### 3.3 Masks

Every sprite has a mask, which decides which background pixels it covers. The
renderer draws `(background AND NOT mask) OR image`, so:

- pixels **inside** the shape (including enclosed holes like eyes) blank the
  maze behind them;
- pixels **outside** the outline let seeds and walls show through.

`silhouette()` builds the mask automatically: everything you can't reach by
flood-filling empty pixels from the edge of the grid. Because of that, **an
opening that touches the edge counts as outside**. A mouth drawn open to the
edge shows the maze through it, while an enclosed eye hole shows black. Both
are usually what you want. `sprite_mask()` makes two exceptions: returning
eyes use `EYES_MASK`, so maze pixels cannot show through pupils touching the
socket edges; score popups use a solid mask so numbers stay readable over walls.

### 3.4 Sprite colors

A sprite is one color. Colors are set in code, not in the art:

| Actor                 | Where it's set                             | Default |
|-----------------------|--------------------------------------------|---------|
| Player                | `build_player`, `lda #7` (`src/snapbug.s`) | 7 yellow |
| Enemies 0–3           | `enemy_color` table (`src/snapbug.s`)      | 2, 4, 3, 7 |
| Frightened            | `build_enemies`, `lda #6`; flashes white at the end | 6 blue |
| Returning eyes        | `build_enemies`, `lda #1`                  | 1 white |
| Bonus items           | 3rd field of each `ITEMS` entry            | varies  |

Red, purple, cyan and yellow approximate the arcade ghost colors. Hi-res
mode has no pink or orange, so purple and yellow are the available substitutes.
The normal ghosts' eyes are black cutouts because each sprite has one color;
returning eyes use white sockets with black pupils.

---

## 4. Character-set tiles

The character set (`build_charset()`) holds 256 characters at `$1800`. The
codes are fixed because the engine and the maze tables refer to them:

| Codes       | Contents                                                     |
|-------------|--------------------------------------------------------------|
| `$20–$5F`   | font, ASCII codes (space, digits, `A–Z`, some punctuation)    |
| `$60–$6F`   | 16 wall pieces, chosen by which neighbors are walls          |
| `$70`       | nest door                                                    |
| `$71`       | seed (dot)                                                   |
| `$72`       | honey (power pellet); the engine blinks it by redefining it   |
| `$73`       | spare-life icon on the status line                           |
| `$74–$7B`   | 8 bonus items, one per level (level 8+ repeats the last one) |
| `$C0–$FF`   | **reserved**: the sprite renderer overwrites these every frame |

### 4.1 Font

`FONT` maps a character to **7 rows of 7 characters**. Column 8 and row 8 are
added blank, which gives letter and line spacing. Only characters in `FONT`
are defined. If you print text containing a missing character, it shows as
blank. Don't use lower case: codes `$60` and up are wall pieces and tiles,
so lower-case letters would print as walls.

### 4.2 Walls

You don't draw each wall piece separately. `wall_glyph(mask)` builds all 16
from simple rules: a 2-pixel-thick line (columns/rows 3–4) runs from the
center toward each neighboring wall (mask bits 1 = up, 2 = left, 4 = down,
8 = right). The four plain corners use a rounded piece. For a different look
(double lines, thicker walls, square corners), change `wall_glyph()`. Keep
the lines meeting at the center of the cell's edges so neighboring pieces
join up.

The whole maze is drawn in `COL_WALL`. The level-clear flash swaps it to
white and back.

### 4.3 Seeds, honey, door, life icon, items

Seeds, honey, door and life icon are single `art()` bitmaps: `DOT`, `HONEY`,
`DOOR`, `LIFE`. Each `ITEMS` entry is `(name, 8 rows, color, points)`. The
points must be a multiple of 100 below 10000, because they're stored as
2-digit BCD hundreds. A smaller seed (2×2) and a clearly bigger honey drop
(6×6) are easy to tell apart at a glance.

The eight bonus pictures are cherries, strawberry (`BERRY`), orange, apple,
melon, Galaxian flagship (`GALAX`), bell and key. They use arcade sprite
indices 0, 1, 2, 4, 5, 6, 3 and 7 as references; the bell is sprite 3.
The melon uses green with holes suggesting its netting. Preserve the cherry
stems above the fruit, the bell's clapper below its rim, and the key's teeth
on its right. `items-ntsc.png` shows each icon with its color and score.

---

## 5. The maze

`MAZE` is 21 strings of 21 characters:

| Char | Meaning                                        |
|------|------------------------------------------------|
| `#`  | wall                                           |
| `.`  | path with a seed                               |
| `o`  | path with honey                                |
| ` `  | empty path                                     |
| `T`  | tunnel (path, enemies slowed, wraps at the edge) |
| `x`  | empty space outside the maze                   |
| `-`  | nest door (only enemies pass)                  |
| `n`  | nest interior                                  |

The build rejects a maze unless:

- every row is 21 characters and **mirrors left↔right**;
- every path tile has **at least 2 open neighbors** (no dead ends);
- there's **no 2×2 block of walls** (the wall pieces can't draw one);
- **every path tile is reachable** from the player start;
- the player start, the tile above the door, and the bonus tile are paths,
  and `DOOR_TILE` is a `-`.

If you move the nest, door or tunnel, update `PLAYER_START`, `DOOR_TILE`,
`HOME_TILE`, `BONUS_TILE` and `TUNNEL_ROW` at the top of `mkdata.py`, and the
nest start positions in `reset_actors` (`src/snapbug.s`). The engine keeps
up to 255 seeds, and the bonus item appears after 60 and 140 have been eaten
(`ate_something` in `src/actors.s`).

---

## 6. Sound and music

### 6.1 The voices

The VIC chip has three square-wave tone voices and one noise voice, all
sharing one volume setting:

| Voice | Register | Range (NTSC)       | SNAPBUG uses it for                       |
|-------|----------|--------------------|-------------------------------------------|
| 0 bass    | `$900A` | ~31 Hz – 4 kHz  | start-tune bass line; five siren stages (looping) |
| 1 alto    | `$900B` | ~63 Hz – 8 kHz  | chomp, eat-enemy and bonus effects         |
| 2 soprano | `$900C` | ~126 Hz – 16 kHz | start-tune melody, extra life, death; fright/eyes (looping) |
| 3 noise   | `$900D` | —               | unused (free for your effects)            |

Each voice can only play **one note at a time**. To get chords, spread the
notes across voices. Each voice plays its one-shot effect if there is one,
and falls back to its looping background sound when the effect ends. A new
effect on a busy voice cuts off the old one.

### 6.2 Pitch

Register value `128 + n` gives the frequency `f = clock / (127 − n)`, where
clock is 3995, 7990 or 15980 for bass, alto or soprano. 0 means silent. The
steps are coarse near the top of each voice's range, so **high notes go out
of tune**. Keep melodies in the lower two-thirds of a voice's range: about
C3–C6 on soprano, C2–C5 on alto, C1–C4 on bass. You never write register
values by hand: `notes()` and `sweep()` work them out from note names or Hz.

### 6.3 Writing sounds

A sound is a list of `(register value, frames)` pairs. One frame is 1/60 s.
In `tools/mksound.py`:

```python
# a melody: note names with octave, lengths in units
SOUNDS["MY_TUNE"] = notes("sop", [("E5", 1), ("G5", 1), ("C6", 2), (None, 1)],
                          unit=8, gap=2)   # 8 frames per unit, 2 silent frames between notes
# a slide from 200 Hz to 900 Hz over 20 frames
SOUNDS["MY_ZAP"] = sweep("sop", 200, 900, 20) + [(0, 1)]
# raw pairs
SOUNDS["MY_BLIP"] = [(reg("alto", 600), 2), (0, 1)]
```

- `notes(voice, seq, unit, gap)` takes `(name, units)` pairs. Names are like
  `"C#4"`; `None` is a rest. `gap` silent frames separate repeated notes.
- `sweep(voice, f0, f1, frames, per)` slides smoothly in pitch, changing
  every `per` frames.
- Compute each voice's part with that voice's name, so the clock is right.
- End one-shot effects with `(0, 1)` so the voice falls silent. Background
  loops (sirens) should **not** end in silence, so they repeat seamlessly.

**Keeping the names.** The engine plays sounds by name (`SND_CHOMP1`,
`SND_SIREN2`, …). You can rewrite the contents of any existing entry freely.
A new name also needs a `jsr play_fx` (one-shot) or `jsr set_bg` (loop) call
in the engine, with the voice number in X.

**Start tune.** `JINGLE_S` (soprano) and `JINGLE_B` (bass) play together. The
READY screen lasts as long as the longer voice plus 10 frames. The melody
lasts 248 frames and the bass 256, each followed by one silent frame.
`JINGLE_FRAMES` takes the longer duration so neither voice gets cut off.

**Chomp.** `CHOMP1` and `CHOMP2` alternate on each seed eaten. Each has five
audible frames and one silent frame. Seeds are eight pixels apart, leaving
time for the complete chirp at the port's fastest movement speed.

**Size.** Each pair is 2 bytes. There is plenty of room (about 11 KB free in
the code block, `$2000–$6FFF`), so long tunes are fine.

---

### 6.4 Arcade sound adaptation

The intro uses the pitch lookup and note bytes in `pacman.6j`, rather than
rounded note names. The reference ROM is useful for comparison but is not
needed to build. The sound format is explained in
[Frédéric Vecoven's annotated sound disassembly](https://www.vecoven.com/elec/pacman/code/pac_z80.html).
The Namco waveform playback and clock conversion can be checked against
[MAME's sound implementation](https://github.com/mamedev/mame/blob/master/src/devices/sound/namco.cpp).

The VIC has square-wave voices and one shared volume, so this is a pitch
and timing adaptation. It cannot reproduce the arcade's wavetable shapes
or independent volume envelopes. For waveforms dominated by higher
harmonics, the VIC follows that component: harmonic 2 for bass/chomps,
8 for frightened ghosts and 16 for the ghost-eaten rise. These choices
come from the local waveform PROM (`82s126.1m`).

| Sound | Adaptation |
|-------|------------|
| Intro | Original note timing and ROM pitches; the bass's quiet tail becomes silence. |
| Waka | Complete five-step falling and rising chirps on alto. |
| Fruit | Full 23-frame fall/rise on alto; its lowest 46.9 Hz step clamps to about 63 Hz. |
| Ghost eaten | 32-frame rise following the waveform's strongest harmonic. |
| Siren | Five original pitch/sweep settings, advancing at fifths of this maze's remaining seeds. |
| Frightened | Eight-step chirp replaces the normal siren; no separate power-pellet sting. |
| Returning eyes | Sixteen-step falling sweep replaces fright and siren. |
| Extra life | Ten fixed-pitch pulses; gaps approximate the volume modulation. |
| Death | 90 frequency steps, including the two final rising chirps. |

`SND_HONEY` remains available as a one-shot version of the frightened chirp,
but eating a power pellet now switches the background loop directly.
`tests/sound.py` checks the assembled player's frame counts, loop boundaries,
silence at effect completion, pickup voice routing and background priority.

---

## 7. Checking your work

```sh
make            # regenerates everything; errors explain what's wrong
make run        # play it in VICE
make test       # automated play test (catches crashes and timing problems)
```

`make` also writes previews to `build/preview/`:

- `sprites.png`: every sprite image in index order;
- `sprites-ntsc.png`: labeled sprite sheet with colors and wide NTSC pixels;
- `actors.gif`: animated player, ghosts, frightened faces, eyes and death,
  with wide NTSC pixels;
- `items-ntsc.png`: all eight bonus icons with colors, scores and wide pixels;
- `charset.png`: all 256 characters on a 16×16 grid;
- `maze.png`: the maze in color.

The original `sprites.png`, `charset.png` and `maze.png` use square pixels.
Check `sprites-ntsc.png` and `actors.gif` after art changes to judge proportions,
mirroring, eye holes and animation before running VICE.

To grab a screenshot from VICE without playing (the title screen, for
example), add `+sound -limitcycles 9000000 -exitscreenshot shot.png` to the
xvic command from `make run`. VICE exits after about 9 seconds of emulated
time and saves the screen.

### Checklist

- [ ] Each bitmap has 8 rows of 8 characters (font glyphs: 7×7).
- [ ] Shapes are about 1 pixel narrower than tall, to allow for wide pixels.
- [ ] Player art has up/right poses and a matching closed disk.
- [ ] Enemy eye holes stay inside the body; returning pupils use `EYES_MASK`.
- [ ] 40 sprite images or fewer, in the original order.
- [ ] Colors chosen from 0–7, with no two enemies relying on cyan vs green.
- [ ] Item points are multiples of 100, below 10000.
- [ ] Maze passes the generator's checks.
- [ ] Sound names unchanged (or the engine calls updated); one-shots end in
      silence, loops don't.
- [ ] `make test` passes.
