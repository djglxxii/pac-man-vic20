# Arcade graphics and sound

The main asset source is the user's local `pacman.zip`. Maze and most actor art
are decoded from the original data. [Letters, digits and bonus scores](FONTS.md)
use hand-drawn VIC-native shapes from `docs/artwork/hires-font.json`.
Normal Pac-Man and his death animation use the user's revised 8×12 masks
from [`artwork/hires-pacman.json`](artwork/hires-pacman.json).
`make` runs `tools/arcade/mkrom.py` and writes `build/arcade/rom.c`, `rom.h`,
`program-rom.bin` and a SHA-256 manifest. Source ROM addresses stay virtual;
the native port stores only the data ranges it uses.

## Display and sprites

The VIC display uses 14×14 double-height characters. Screen memory is at
`$0200`; the bitmap occupies `$1000–$1C3F`, with a different character for
each screen cell. Columns are stored vertically so sprite scanlines can be
copied without crossing a character boundary. The original 28×36 screen,
including scores and the lower status area, becomes 112×216 native pixels.
The final eight scanlines of the 224-line display remain black.

The generator decodes `pacman.5e` as 256 two-bit, 8×8 tiles and `pacman.5f`
as 64 two-bit, 16×16 sprites. It rotates the artwork to the arcade's portrait
orientation, then scales tiles to 4×6 and sprites to 8×12. Normal ghosts retain
eye cutouts and directional pupils; returning eyes use a separate mask. The
64 source frames include fruit, frightened ghosts, score popups, all death
frames, the large intermission Pac-Man, stretched legs and the torn costume.
After scaling, the generator replaces lettering and ghost-score masks with
the custom font. Fruit score messages use individual digit tiles in the
existing corridor space; their native message records are reformatted
without changing scores or timing. The raw program-ROM reference stays original.

The eight bonus items are cherry, strawberry, orange, apple, melon, Galaxian,
bell and key. Their original sprite identifiers, scores and board progression
come from the ROM tables. The HUD uses the original fruit-history tiles.

Palette PROMs `82s123.7f` and `82s126.4a` determine colors. A packed table
records each image's dominant pixel class so the renderer uses that class's
actual palette entry. This matters for fruit bodies, score popups and the
large intermission sprites, which do not all use the same pixel class.
The palette is quantized to the VIC's eight foreground colors, with distinct
red, magenta, cyan and yellow for the four normal ghosts.

`build/arcade/sprite-reference.png` is a diagnostic atlas of the original
pixel classes; its red/white/blue colors identify bit patterns rather than
final game colors. `make vice-test` captures actual VICE screenshots under
`build/preview/`.

### Limits

The display remains one foreground color per 8×16 cell. Ghosts sharing a cell
can recolor each other, and a sprite can temporarily recolor nearby pellets,
walls or text. The [maze and standing pellets are white](WHITE_MAZE.md),
including walls left behind after pellets are eaten. Power pellets retain
their original blinking. Completion alternates blue/white for four pairs,
starting blue against the normally white maze. Existing wall coverage keeps
background art sharing a wall cell in the wall's color.
An aligned sprite no longer recolors its empty right-hand column.
Pink and orange cannot be reproduced exactly in this high-resolution
mode. Eyes, pupils and fruit stems lose detail when scaled. The custom
lettering is drawn directly at its displayed size.
These are renderer and palette compromises, not changes to collision sizes,
maze topology, ghost targets or game coordinates.

The native 6502 compositor saves the pixels and colors beneath each actor,
draws in the arcade's priority order, and restores in reverse order. It keeps
unchanged actors in place, propagating changes through actors whose old or
new footprints share pixels or color cells. Background changes invalidate
all affected underlays before tile writes. Rendering is skipped when the
game clock has pending work.

[Full rebuilds](BOUNDED_REBUILD.md) now use bounded progressive slices. Actors
are restored once and redrawn from current state at completion; input, logic
and audio continue. Partial batches are separate from coherent completed
refreshes. Continuation state uses 16 spare bytes in the existing
`$02C4-$02FF` screen-work region; no larger expansion is required.

The dirty-tile bitset uses `$0F00–$0F7F`; sprite caches occupy `$0F80–$0FE1`.
Maze-wall coverage for the [stage flash](MAZE_FLASH.md) uses `$0FE2–$0FFA`,
with its pending flag at `$0FFB`.
Frequently tested arcade flags at virtual `$4DA0–$4DFF` use native zero page
`$A0–$FF`. These memory choices leave the game values and coordinates intact.
The earlier pellet-neighbor checks and their two-byte zero-page cache have
been removed; no extra color-priority state is needed.

Two normal ghost masks cover source frames 32–37; frames 28–29 provide two
frightened masks. All four are horizontally symmetric with transparent first
and last rows. The frightened masks cut symmetric eye and mouth holes through
the scaled body and keep each frame's skirt. The generator verifies those
properties and stores eight shifts of each middle ten-row mask, using 640
bytes total. The normal cache lives in BLK5 and the frightened cache in
BLK1–3. Other frames, returning eyes and clipped sprites retain the generic
compositor. The saved edge underlays and vertical flips remain exact.
The ordinary Pac-Man masks are also hand-authored, as described below.

### Revised Pac-Man

The source was imported unchanged from
`/home/djglxxii/src/temp/pacman/revised-sprites/sprites.json`.
`tools/arcade/hires_pacman.py` installs its rows into the generated sprite
atlas after ROM decoding, so clean builds use the revised art without any
dependency on that external directory. Rows run top to bottom, bit 7 at
the left, with one yellow ink and transparent clear bits.

Five stored walking masks occupy `$2C`–`$30`: right open, down open,
right half, down half and closed. Left and up reuse the existing horizontal
and vertical flips. All four closed-mouth views share the same twelve bytes
at `$30`; its symmetry makes flipping it visually identical. That sharing
was already present in the port, so this substitution adds no sprite storage
and does not claim an additional saving. The eleven death masks replace
`$34`–`$3E`. The hidden `$3F` frame and large intermission art retain their
existing masks.

The revised circle fills the existing 8×12 box. Its centre is `(3.5, 5.5)`;
at the NTSC 3:2 pixel aspect the box is square. Sprite coordinates, animation
selectors, timing, collision logic, palettes and the renderer footprint are
unchanged. `tests/render.py` checks the loaded mask bytes, yellow palette,
shared closed views, shifted drawing, colour-row boundaries, tunnel clipping,
death frames and exact restoration beneath the revised art.

All 52 regression tests and the smoke run through all three intermissions
pass. A fresh [600-frame VICE gameplay capture](../build/revised-pacman/vic20-revised-pacman-9fb85cf6.mp4)
verifies all 33,792 loaded program bytes before startup. Against the preceding
build, the depacked image differs only in 124 bytes within those sixteen
masks; every code and data address stays the same. Capture identity and
asset checks are recorded under `build/revised-pacman/`.

## Sound

The original sound routines and tables remain in `src/arcade/core.c`.
`src/platform.c` converts their Namco output registers to VIC dividers.
This includes the introduction and intermission music, alternating dot
sounds, five siren stages, frightened sound, returning eyes, fruit and ghost
eating, extra life and the complete death sequence. Effect selection and
interruptions follow the original masks and channel priorities.

The arcade's first voice has a 20-bit phase step; the other two omit its
lowest nibble. The converter preserves that frequency relationship. It
selects prominent harmonics for waveform shapes that cannot be reproduced
by a square wave, then chooses an audible VIC divider.
The divider and voice-octave calculation follow the tone-channel clocking in
[VICE's VIC sound model](https://github.com/VICE-Team/svn-mirror/blob/main/vice/src/vic20/vic20sound.c).
Seven comparisons against precomputed thresholds replace software division
without changing the rounded divider. Native tests check every rounding
boundary and compare the complete VIC register output on varied input data.

The VIC has three tone oscillators and a shared four-bit volume. It cannot
reproduce the three independent wavetable voices or their separate volume
envelopes. The converter uses the largest active channel volume; quiet
channels still stop at their original rests. It does not add a replacement
melody or invent timing for effects.

`make vice-test` records the actual VIC audio generated by VICE as
`build/preview/vice-audio.wav`, alongside a JSON validation report. The WAV
includes the original start tune followed by normal play.

## Logic data and reproducibility

Movement masks, difficulty, scatter/chase timers, house-release limits,
frightened durations, messages, fruit tables and songs are extracted from
the program ROMs. The generator retains all 21 difficulty entries and fruit
entries. Sprite scaling does not change these values.

Frightened directions use the original ROM-backed random sequence and seed
reset. Its stored prefix covers 1,536 decisions before reseeding. Four
six-second energizers, four ghosts, at most two pixel steps per tick and one
decision per eight pixels bound normal play to fewer than that many calls;
the fixed attract and intermission sequences are also covered. A runtime
assertion protects that bound. The regression suite checks the stored values
against the original ROM bytes.

A 128-entry square table preserves all 256 original eight-bit squares using
`(128+n)^2 = n^2 + 256*n + 16384`. This saves memory without changing ghost
distance comparisons or their tie-breaking order.
