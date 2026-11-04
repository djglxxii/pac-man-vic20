# VIC-native lettering

Accepted after user visual review on 2026-11-03. The user requested cleaner
letters, digits and bonus scores after finding the scaled arcade font garbled,
then approved the horizontal reward layout. The font is included in `make run`.
A later [actor-commit throughput trial](ACTOR_SPEED.md) retains this artwork
in a separate target; the accepted normal build is unchanged.

[Compare the old and new artwork](artwork/fonts/font-comparison.png).
The sheet uses the generated game assets at integer scale with the NTSC
3:2 pixel aspect. It shows the alphabet, digits, representative messages,
all four ghost scores and all eight fruit scores.

The editable source is [hires-font.json](artwork/hires-font.json). Ordinary
characters use three columns and five rows of ink inside the existing 4×6
tile. A blank column and bottom row separate neighboring characters.
The copyright sign uses four columns. The generator replaces the score
digits, their message/diagnostic aliases, uppercase letters and punctuation,
including the three separate P/T/S tiles.

Ghost scores are horizontal: 200, 400, 800 and 1600. They use 11 or 15
columns of ink in a 16×12 rectangle. The first draft stacked the leading
value above `00` to fit one actor; the user disliked that layout and asked
for a measured horizontal alternative.

During a ghost reward, Pac-Man is hidden. `score.S` borrows that actor slot
for the number's second eight-pixel half. Intervening ghosts shift slots
temporarily so both halves keep the original reward's draw priority. This
also handles the arcade's powered-up priority swap, which moves the hidden
Pac-Man to output slot 2 rather than slot 10. The
original arcade output bytes are restored after building the renderer
caches. The existing painter, clipping, saved backgrounds and reverse
restoration handle both halves; no extra underlay or zero-page allocation
is needed. Internal palette 31 selects the second half, using the original
cyan reward color. Sprite masks retain the ordinary dirty-actor behavior.

Fruit scores use ordinary digit tiles on one line: 100, 300, 500, 700, 1000,
2000, 3000 and 5000. They fit in the existing four-tile corridor space,
native x=48..63, y=120..125. The native copy of message records `$1B–$22`
and their pointers is reformatted inside its existing allocation. The
records retain palette `$83` and erase palette `$90`; both original removal
messages clear all four tiles. This intentionally changes the native logical
screen codes for fruit popups. The input ZIP, `program-rom.bin` and Z80
reference remain original. Score values, fruit progression, task scheduling
and popup timers are unchanged.

The text font and fruit formatting retain their original table sizes. The
horizontal ghost layout adds 48 bytes of masks, 22 bytes of temporary state
and the slot preparation code. Total resident use grows by 401 bytes over
the stacked draft: resident end is `$7EC5`, leaving 315 bytes in BLK1–3.
BLK5 still has 15 bytes free. The RAM expansion requirement is unchanged.

Fresh 180-frame CPU-cycle samples:

| Scene | Stacked draft, renders/s | Horizontal draft, renders/s |
| --- | ---: | ---: |
| Opening play | 52.17 | 52.04 |
| Frightened | 54.87 | 54.68 |
| Attract chase | 43.61 | 44.26 |

Opening and frightened play lose less than 0.4%; attract improves slightly with
the changed code layout. These are short benchmark windows, not active-play
video rates. All unrelated asset tables match the stacked comparison build.

Isolated compiled-6502 calls, averaged across all four values, ghost slots
and eight horizontal shifts, measure:

| Operation | Stacked, ms | Horizontal, ms | Added time, ms |
| --- | ---: | ---: | ---: |
| Paint reward through the sprite frontend | 3.256 | 5.119 | 1.863 |
| Refresh with the same reward unchanged | 1.942 | 2.780 | 0.838 |
| Restore saved backgrounds | 0.858 | 1.366 | 0.507 |

These fixtures isolate the reward; they do not represent an entire gameplay
frame. User review accepted the readability gain with this small measured cost.
Hashes and measurements are frozen in [the baseline](baselines/hires-font.json).

`make test` includes the two new compiled-game checks in `tests/fonts.py`:
every fruit value and both complete pixel/palette removal paths, and the
original four ghost-score frame selections and their return to a ghost.
The seven renderer checks cover all sprite frames, shifts, flips,
clipping and saved-underlay restoration. The reward check includes 1,148
cases across both hidden-slot positions, overlapping priorities, full-number
flips, both screen edges and incremental appearance/removal. The arcade
output attributes and positions must survive rendering unchanged.
All 51 tests pass. The frontend smoke run covers all
three intermissions. VICE verifies boot, coin/start and normal play, then
captures all four rewards in synthetic fixtures using the arcade's real
priority swaps. [The 1600-point VICE fixture](artwork/fonts/vice-reward-1600.png)
shows the wider reward in the maze.

Rebuild the comparison sheet with:

```sh
make
python3 tools/arcade/font_preview.py
python3 tests/font_timing.py --before build/font-study/stacked/pacman.prg
python3 tools/arcade/vice_check.py --font-rewards --output build/font-study/horizontal/vice
```

`mkrom.py --arcade-font --output <separate-directory>` generates the old
scaled lettering for comparisons. It does not change the default build.
Raw validation and timing artifacts are in `build/font-study/`.
