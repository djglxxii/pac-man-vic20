# White-pellet color priorities

Historical experiment at `38c5750`. The subsequent [all-white maze](WHITE_MAZE.md)
removes the neighbor checks/cache, restores rendering throughput and keeps the
aligned-sprite fix. The measurements below describe this earlier experiment.

Implemented after `249bb5a`, on `optimization/color-priorities`, following the
user's preference that standing pellets remain white. The NTSC display stays
112×216 pixels with one foreground color per 8×16 hardware cell.

## Visible behavior

Visible standing pellets take priority over other background colors. A wall
sharing a pellet's cell becomes white too. This makes substantially more of
the maze white; it cannot retain blue walls and white pellets within the same
hires cell. This change implements pellet visibility rather than eliminating
the hardware's color clashes.

In an identical early-play snapshot, 237 remaining pellet tiles occupy 113
hardware cells. Previously only 41 of those cells were white; now all 113
are white. The logical screen/palette data and rendered bitmap bytes are
identical before and after. Only foreground color assignments differ.

Removing a pellet rechecks the other pellets sharing its cell. The cell stays
white until the last visible pellet is removed, then returns to the wall's
blue. Invisible power-pellet blink phases do not claim white priority. The
existing end-board blue/white flash is retained.

Actors keep their existing drawing priority. They can temporarily recolor a
pellet sharing the same hardware cell, even when their individual pixels do
not overlap it. An aligned sprite no longer recolors its entirely empty
right-hand column. Other transparent corners within its footprint can still
share colors with background pixels. Restoring an actor restores the white
pellets beneath it.

## Implementation and memory

`bitmap_cell_priority` examines the logical screen and palette for the two
arcade columns and up to four arcade rows overlapping a hardware cell. The
14-byte row table excludes the small pellet's transparent boundary rows;
power pellets count where their wider source masks have ink. Top score rows
skip this work. The bottom HUD still checks shared maze cells.

The existing maze-wall coverage determines the fallback color after pellet
removal. A two-byte zero-page cache avoids repeating a lookup for adjacent
tiles sharing a hardware cell. Changed logical screen/palette writes and
fresh full rebuilds invalidate it. The helper preserves the tile renderer's
scratch and uses only caller-saved compiler registers.

The sprite compositor keeps its existing pixels and underlays. At horizontal
shift zero, it suppresses right-column color writes; all other drawing and
restoration ordering is retained.

The current RAM expansion still works. Two zero-page bytes are added, with
the compiler's allocation cap reduced from 92 to 90. The link ends its
allocated zero-page state at `$0085`, below arcade flags at `$00A0`.
Small read-only mask/dispatch tables move into remaining BLK5 space.
**BLK1-3 now have no free resident bytes; BLK5 has one.** The queued memory
lifetime audit is needed before adding more resident code. No display RAM,
stack guard or arcade-state storage is repurposed.

## Measured cost

CPU-cycle measurements use the same five-scene benchmark as the preceding
bounded-rebuild revision. Sample starts can differ because setup duration
changes. These are representative samples rather than guaranteed rates.

| Measurement | Before | With white-pellet priorities |
| --- | ---: | ---: |
| Normal-play completed renders/s | 49.74 | 45.58 |
| Frightened completed renders/s | 53.73 | 51.61 |
| Attract-chase completed renders/s | 44.37 | 43.56 |
| Intermission completed renders/s | 60.30 | 60.08 |
| Longest coherent transition draw interval | 1800.99 ms | 2073.70 ms |
| Longest transition background slice | 6.08 ms | 7.52 ms |
| Longest transition input-service gap | 28.95 ms | 28.80 ms |
| Longest transition audio-update gap | 29.73 ms | 26.04 ms |

Neighbor inspection adds rendering work. A preliminary uncached version
took about 2.23 seconds in the focused construction test; caching and direct
row indexing reduced this to 2057.79 ms, compared with 1785.01 ms previously.
The focused completion limit is increased from 2000 to 2250 ms to accommodate
this visual feature's cost. The input/audio limits remain 33.01 ms. The
focused run measured 23.03/23.82 ms input/audio gaps and at most 11 queued
entries. The arcade clock remains 16,875 cycles per tick.

The [measurement record](baselines/color-priorities.json) freezes the current
profiles, validation and artifact hashes. Earlier baseline records remain
unchanged. Large traces and images are kept under ignored `build/`:

- `build/color-priorities/comparison.png`: same logical scene and bitmap,
  with actors removed, before and after the color rule.
- `build/color-priorities/vice/`: actual VICE gameplay, all eight flash
  phases, progressive rebuilding, settled board and recorded sound.
- `build/performance/color-priorities/`: CPU profiles and timing traces.

## Validation

`make test` passes all 41 checks: 15 ROM, six native, four compositor, five
color-priority, three flash and eight bounded-rebuild tests. The smoke run
covers 7,199 logical ticks with its IRQ vector and stack guard intact.

The new independent pixel-based checks cover a real maze, shuffled tile
order, last-pellet removal, power-pellet blinking, every vertical cell-boundary
phase, dirty-map overflow and white-pellet restoration after an actor. The
existing compositor reference now expects aligned sprites to leave their
empty right-hand column's colors unchanged; its pixel oracle is unchanged.

VICE boots, accepts coin/start, displays all eight flash phases, captures
partial construction and settles board 1. Its 48 kHz mono recording is
non-silent. Physical hardware has not been tested.

```sh
make test
python3 tests/performance.py --output build/performance/color-priorities
python3 tools/arcade/vice_check.py --maze-flash --output build/color-priorities/vice
```
