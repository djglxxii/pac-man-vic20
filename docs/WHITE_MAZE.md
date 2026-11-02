# White maze and blue/white completion flash

Implemented after `38c5750` on `optimization/white-maze`, following the user's
decision to use a white maze instead of blue walls with white-pellet priority.

Maze walls and visible standing pellets are white throughout normal play.
Walls remain white after pellets are eaten. Power pellets keep the arcade's
blink timing. At completion, the existing four flash pairs now display
**blue, white, blue, white, blue, white, blue, white**, making the first change
visible against the white maze. The following board is white again.

Colored actors can still tint walls or pellets sharing their 8×16 hardware
cell. Their original drawing priority and color restoration remain intact.
The aligned-sprite fix from the previous revision remains: a sprite with no
pixels in its right-hand column does not recolor that column.

## Implementation

The native wall-color helper returns white except during completion states
15–29 when the logical maze palette is 31; that combination displays blue.
Palette 16 displays white. These are presentation mappings: the arcade's
logical screen, palette values, task order, state machine and 16,875-cycle
clock remain unchanged.

The existing 25-byte wall coverage map serves both completion flashing and
background updates. Background art sharing a known wall cell takes the wall's
color, keeping the maze consistent when HUD tiles are redrawn. Art outside
wall cells retains its palette. Flashing still changes color RAM without
rebuilding the pixels.

The experimental pellet-neighbor helper, 14-byte row table, two-byte cache
and write-invalidation work are removed. No replacement cache is needed.
The compiler zero-page allocation cap returns from 90 to 92. The current RAM
expansion is retained; BLK1-3 have 177 resident bytes free and BLK5 has 15,
compared with zero and one previously. This recovers 191 resident bytes and
two zero-page bytes.

Simulator trace requests describe the new physical color mapping; presentation
events read physical color RAM. The VICE check expects blue first and observes
all eight actual colors. Full-redraw comparisons use the same new wall-color
mapping.

## Measurements

The same five-scene CPU benchmark compares this change with the preceding
pellet-priority revision. Short sample starts can differ as setup timing changes.

| Measurement | Pellet priorities | White maze |
| --- | ---: | ---: |
| Normal-play completed renders/s | 45.58 | 48.10 |
| Frightened completed renders/s | 51.61 | 53.81 |
| Attract-chase completed renders/s | 43.56 | 44.00 |
| Intermission completed renders/s | 60.08 | 60.32 |
| Longest coherent transition draw interval | 2073.70 ms | 1843.77 ms |
| Longest transition background slice | 7.52 ms | 6.36 ms |
| Longest transition input-service gap | 28.80 ms | 28.90 ms |
| Longest transition audio-update gap | 26.04 ms | 27.16 ms |

Most of the experiment's performance cost is recovered. The earlier
bounded-rebuild baseline measured 49.74/53.73 FPS in normal/frightened play;
this change does not establish sustained 60 FPS.

The focused transition settles in 1827.77 ms and retains at most 11 queued
entries. Input/audio gaps in that focused run are 22.06/27.16 ms. Its original
2000 ms completion limit is restored, with the 33.01 ms service-gap limits
unchanged.

The [measurement record](baselines/white-maze.json) freezes hashes, memory,
timing and validation. Earlier baselines and the
[pellet-priority experiment](COLOR_PRIORITIES.md) remain as historical evidence.

## Validation and preview

`make test` passes 42 tests: 15 original-ROM, six native, four compositor,
six maze-color, three flash and eight bounded-rebuild checks. The frontend
smoke run covers 7,186 logical ticks with the IRQ vector and stack guard intact.

The maze-color tests verify white walls and pellets against source pixels,
shuffled tile drawing, pellet removal, power-pellet visibility, cell boundaries,
dirty-map overflow and actor restoration. They also explicitly restrict blue
walls to completion states, including full redraws before/during/after flashing.
The flash checks verify all four blue/white pairs, their timing and pixel/
underlay agreement with full redraws across all fruit/history cases.

VICE boots, accepts coin/start, records non-silent 48 kHz mono sound, observes
blue/white hardware colors through all eight phases and settles the next white
board after progressive construction. Physical hardware has not been tested.

In the fixed comparison snapshot, all 162 wall-containing cells are now white,
versus 113 with pellet priorities. Logical video data and bitmap bytes match
exactly. Preview artifacts are kept under ignored `build/`:

- `build/white-maze/comparison.png`: identical scene, actors removed, before/after.
- `build/white-maze/vice/vice-game.png`: actual VICE gameplay.
- `build/white-maze/vice/vice-maze-flash.gif`: the completion flash in VICE.
- `build/performance/white-maze/`: CPU profiles and timing traces.

```sh
make test
python3 tests/performance.py --output build/performance/white-maze
python3 tools/arcade/vice_check.py --maze-flash --output build/white-maze/vice
make run
```
