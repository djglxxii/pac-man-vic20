# Moving multicolour character prototype

**Live integration has started:** [the separate game target](MULTICOLOUR_GAME.md)
now runs real input, arcade logic, dynamic pellets/scores and audio with this
visual direction. Its current VICE sample manages about 9 updates/s; the
measurements below describe the earlier renderer-only replay. Integration
and missing game-state visuals now take priority over further standalone
micro-optimizations.

The user accepted the wider multicolour artwork as the visual direction. This
moving implementation demonstrates hidden character preparation and
screen-code publication with that design. It is a separate native 6502 PRG;
the accepted playable game remains unchanged.

The subsequent [preparation optimization](MULTICOLOUR_PREPARATION.md) is now
retained: character-band processing reduces mean hidden preparation from
24.219 to 20.008 ms while preserving the approved pixels and animation pace.
The later [cell-setup pass](MULTICOLOUR_REUSE.md) reduces it further to
19.293 ms. That pass also records the rejected unchanged-group reuse experiment.
The [background row tables](MULTICOLOUR_BACKGROUND_ROWS.md) reduce hidden
preparation further to 18.607 ms, using the same data space and artwork.
The [publication page cache](MULTICOLOUR_PUBLICATION.md) reduces mean
commit time to 4.596 ms, bringing total renderer time to 23.203 ms.
The [colour-write paths](MULTICOLOUR_COLOURS.md) reduce colour handling
by 27.3% and complete rendering to 22.737 ms, preserving the same final image.
The [loop operands](MULTICOLOUR_LOOP_OPERANDS.md) reduce total rendering
to 22.344 ms while shrinking both code and metadata.
The [shared map-address byte](MULTICOLOUR_MAP_POINTER.md) reduces total
rendering to 21.990 ms while freeing code and zero page.
The [band setup](MULTICOLOUR_BAND_SETUP.md) reduces total rendering to
21.766 ms while shrinking code and metadata again.
The [direct background lookup](MULTICOLOUR_BACKGROUND_LOOKUP.md) reduces
total rendering to 21.398 ms and releases another two zero-page bytes.
The [direct work-cell setup](MULTICOLOUR_CELL_SETUP.md) reduces total
rendering to 20.579 ms with nine extra code bytes, while releasing two more
zero-page bytes and one metadata byte.
The [register-held list cursors](MULTICOLOUR_LIST_CURSORS.md) reduce
commit time to 3.907 ms and total rendering to 20.152 ms, releasing 22 code
bytes and another metadata byte.
The [cached restoration](MULTICOLOUR_RESTORATION.md) reduces commit
time to 3.135 ms and total rendering to 19.380 ms, releasing eight code bytes
and four zero-page bytes.
The [allocation cleanup](MULTICOLOUR_CELL_ALLOCATION.md) reduces hidden
preparation to 15.957 ms and total rendering to 19.091 ms, releasing 18 code bytes.
The [sprite lookup layout](MULTICOLOUR_ROW_LAYOUT.md) reduces hidden
preparation to 15.895 ms and total rendering to 19.029 ms, using the same memory.
The latest [background glyph ordering](MULTICOLOUR_BACKGROUND_LAYOUT.md)
reduces preparation to 15.885 ms and total rendering to 19.019 ms without
changing any assembly instructions or memory allocations.

[Watch the real VICE recording](../build/multicolour-motion/motion-preview.mp4)
or run the test directly:

```sh
bash build/multicolour-motion/run.sh
```

The recording is ten seconds, 600 NTSC video frames, 1008×864, without sound.
It shows a renderer replay, not an integrated game or a new playthrough.
The maze, pellets and score are fixed while the actors move.

## What is implemented

[The assembly compositor](../prototypes/multicolour-motion.S) supports six
actors, custom normal/frightened ghosts, returning eyes, Pac-Man mouth phases
and a cherry. Each actor has signed horizontal clipping and is clipped away
from the hires HUD. The colour-cell priority is the same reverse painter order
as the arcade output slots, including the original output swaps in the replay.
Blue walls and uncovered white pellets retain their global colours. Actor
accents can still share a cell.

The prototype reserves character codes 0–146 for backgrounds and uses two
54-character work banks, 147–200 and 201–254. The fully visible initial maze
plus the complete HUD font needs 136 of those reserved background characters.
It does not preload every possible eaten-pellet pattern. The
[earlier character analysis](MULTICOLOUR_PROTOTYPE.md#character-and-memory-budget)
explains the 147-slot demand-loaded background bound; that background cache
is not yet implemented here.

On each update it:

1. Copies the appropriate permanent background glyph into a hidden working
   character for every cell touched by the next actor footprints.
2. Composes all actors into those shared work cells in painter order. Actors
   sharing a cell use the same prepared glyph, preserving pixel priority.
3. Restores only vacated old cells. Cells needed by a new actor are switched
   directly to prepared graphics, without first removing their old actors.
4. Publishes the new screen codes and cell accents, then swaps work banks.

Six 6×14 actors can require nine cells each, and both complete images can
coexist in the 108 work slots. All permanent glyphs, live screen codes and
live colours stay untouched throughout preparation. No raster wait is added
to publication; a scan can still contain parts of consecutive images. This
removes the explicit live erase/paint sequence, not every possible scan effect.

Prepared images can be discarded or replaced without becoming visible. Invalid
pose input aborts the transaction and preserves the prior complete image.

## Sources and memory

The builder records 480 stable `video_frame_begin` boundaries from the accepted
game using joystick input. Sampling there avoids the temporary sprite-code
rotations that can occur during the ISR. Recorded arcade ticks span 1212–2138;
the source game consumes pellets 3–110, with all sampled level states equal to
normal play. No source RAM or gameplay state is patched. Every sampled pose
maps to a supported custom graphic without fallback artwork.

The replay's Pac-Man facing mapping is corrected after visual review: the
screen-space ROM frames 44/46 face right before horizontal flipping, and
45/47 face down before vertical flipping. The original closed-circle frame
does not encode vertical facing; the custom eye retains a direction from
recorded movement or the latest open-mouth frame. Only custom pose selection
changes. Recorded positions, colours, pacing and every other actor remain
identical. There are 192 direction/flip/slot checks plus 398 checks against
actual recorded movement, covering all four directions.

The demo replays those coordinates and output priorities. It uses the same
16,875-cycle VIA period for replay pacing, with an IRQ counter and deadlines
so renderer work does not silently discard elapsed timer periods. It executes
no arcade game logic, collision, sound, or input handling. It therefore cannot
certify game patterns or integrated throughput; those remain in the unchanged
game implementation.

The first implementation computed horizontal shifts at runtime. Replacing that
work with a dictionary of pre-shifted rows avoids a large sprite table: all
27 poses, four horizontal phases and fourteen rows use 1,512 row indices and
147 shared seven-byte records, or 2,541 bytes. Each record contains three
output bytes, three transparency masks and an accent mask. Direct row
composition, clipping dispatch per band, glyph-address lookups and clearing
the temporary map during publication reduce further overhead.

The current standalone image uses 20 zero-page bytes, 375 bytes of metadata in
`$1A37–$1BAD`, and a 567-byte temporary cell map in expansion RAM. It retains
the virtual-I/O reservation and the entire software stack at `$1C40–$1FFF`.
The replay stream is test-only data and would be removed for integration.
These allocations fit conventional VIC-20 RAM; no exotic expansion is used.
This is not a completed placement of the full game beside the new renderer.

## Correctness and performance

All **2,274 native scenes pass** against an independent pixel compositor:

- 480 recorded actor scenes, applied successively.
- 864 combinations of all 27 poses, four horizontal phases and eight vertical
  phases.
- 99 left/right/top/bottom clipping and HUD-boundary cases.
- 648 partial-character-band cases across all poses and horizontal phases.
- 180 random or deliberately overlapping six-actor scenes.
- Maximum-capacity, complete disappearance and recovery scenes.

Every checked preparation preserves the prior visible pixels, screen codes,
colour nibbles and permanent backgrounds. The maximum-footprint scene uses all
54 work characters in one image. Discarding, replacing and rejecting prepared
images preserve the live picture. Forced capacity failure in each of the
left, middle and right column paths rejects and recovers safely. The 960-byte
I/O/software-stack canary stays
intact. Additional transaction checks accompany the scene count above.

VICE independently confirms hidden preparation and exact published data across
32 consecutive scenes, including vacated-cell restoration. After freezing the
final completed validation scene for three rasters, all 36,288 native
picture pixels match the independent reference using VICE's palette. A fresh
VICE process records the moving demo without any guest code or memory patches.

A separate continuous native check runs 496 replay frames through the actual
packet loader and timer IRQ, including 16 after stream wraparound. All actor
packets, published pictures, permanent glyphs and guards match the reference.

Current CPU-cycle costs for the 480 recorded scenes, excluding game logic, audio,
input and IRQ overhead:

| Work | Mean | 95th percentile | Maximum |
| --- | ---: | ---: | ---: |
| Hidden preparation | 15.885 ms | 18.884 ms | 21.179 ms |
| Screen/colour publication, including restoration | 3.032 ms | 3.680 ms | 4.072 ms |
| Entire renderer, including commit bookkeeping | 19.019 ms | 22.672 ms | 25.295 ms |

The [character-band pass](MULTICOLOUR_PREPARATION.md) reduced total renderer
time by 14.41%; the subsequent [cell-setup pass](MULTICOLOUR_REUSE.md) saves
another 2.84%, and [background row tables](MULTICOLOUR_BACKGROUND_ROWS.md) save
a further 2.80%. The [publication page cache](MULTICOLOUR_PUBLICATION.md) saves
another 2.43% overall, followed by 2.00% from the
[colour-write paths](MULTICOLOUR_COLOURS.md) and 1.73% from
[loop operands](MULTICOLOUR_LOOP_OPERANDS.md). The shared
[map-address byte](MULTICOLOUR_MAP_POINTER.md) saves another 1.58%, followed by
1.02% from [band setup](MULTICOLOUR_BAND_SETUP.md) and 1.69% from
[direct background lookup](MULTICOLOUR_BACKGROUND_LOOKUP.md). The
[direct work-cell setup](MULTICOLOUR_CELL_SETUP.md) saves another 3.83%.
The [register-held list cursors](MULTICOLOUR_LIST_CURSORS.md) save
another 2.07% overall and 9.85% of commit time.
The [cached restoration](MULTICOLOUR_RESTORATION.md) saves another
3.83% overall and 19.76% of commit time.
The [allocation cleanup](MULTICOLOUR_CELL_ALLOCATION.md) saves another
1.49% overall and 1.78% of preparation time.
The [sprite lookup layout](MULTICOLOUR_ROW_LAYOUT.md) saves another
0.32% overall and 0.39% of preparation time without increasing memory use.
The latest [background glyph ordering](MULTICOLOUR_BACKGROUND_LAYOUT.md)
saves a further 0.05% overall and 0.06% of preparation time with unchanged
assembly and memory use.
All preserve the approved artwork.

The actual VICE capture completes 324 updates across its sampled ten seconds,
about 32.61 replay updates per second. That is **not a game FPS result**. This
replay follows the original recorded deadlines. The renderer still redraws
every actor and rebuilds its working-cell image every update,
including unchanged actors. Its full redraw cost is too high for integration
with the current game, whose logic and sound also need CPU time.

The selected design and its preparation optimization are retained in this
standalone test; visible flicker is not claimed to be solved. The original main PRG
remains byte-identical to the accepted ghost-state build. Physical hardware
has not been tested. Full hashes, checks, costs and capture metadata are frozen
in [the current background-layout record](baselines/multicolour-background-layout.json),
[the sprite lookup-layout record](baselines/multicolour-row-layout.json),
[the allocation record](baselines/multicolour-cell-allocation.json),
[the restoration record](baselines/multicolour-restoration.json),
[the list-cursor record](baselines/multicolour-list-cursors.json),
[the cell-setup record](baselines/multicolour-cell-setup.json),
[the background-lookup record](baselines/multicolour-background-lookup.json),
[the band-setup record](baselines/multicolour-band-setup.json),
[the map-pointer record](baselines/multicolour-map-pointer.json),
[the loop-operand record](baselines/multicolour-loop-operands.json),
[the colour-write record](baselines/multicolour-colours.json),
[the publication record](baselines/multicolour-publication.json),
[the background-row record](baselines/multicolour-background-rows.json),
[the reuse/cell-setup record](baselines/multicolour-reuse.json),
[the preparation record](baselines/multicolour-preparation.json) and
[the initial motion record](baselines/multicolour-motion.json).

## Next implementation steps

Continue the [live integration](MULTICOLOUR_GAME.md) before further standalone
optimization. Remaining state-specific artwork, UI and the actual game's CPU
budget must be addressed before replacing the accepted playable renderer.
Character-band runs, inlined cell setup, direct background-row loads, cached
publication addresses, direct colour writes, immediate loop operands and the
shared map-address byte are implemented and measured. Band setup now computes
colour eligibility once per actor and tail-dispatches column resolution.
Background-map reads use direct indexing and share temporary pointer storage.
Column-specific work-cell setup eliminates per-cell calls and temporary
glyph-pointer copies, sharing its three blocks with clipped footprints.
Publication, restoration and abort cleanup now hold their list positions in
registers, avoiding repeated memory loads and increments. Old-cell checks and
restoration also use cached absolute accesses, removing their indirect pointer
setup and freeing four zero-page bytes.
Allocation now retains its list slot in Y, reuses the capacity check's carry
flag and omits the final unused scanline decrement. Its caller uses the
resolver's carry result directly, retaining all failure cleanup.
Sprite-row indices put frequently used artwork rows first, and the field
planes place common reads within a page without padding.
Background character numbers now put common static playfield patterns first,
also reducing row-plane page crossings without adding runtime work.
Unchanged-group reuse was tested and rejected: its bookkeeping cost more than
the skipped drawing. Further experiments can examine remaining masked row
blits, preserving shared-cell overlap and the
old/new visibility guarantees.

The later integration also needs the demand-loaded background cache, live
pellet/HUD writes, messages, attract/death/intermission coverage, colour-only
completion flashing and auxiliary-colour preservation in the audio driver.
Arcade movement, collision, timers, update order and ghost decisions remain
unchanged constraints.

To rebuild the current test, record a new pose sample and verify it:

```sh
python3 tools/arcade/build_multicolour_motion.py --frames 480
python3 tools/arcade/check_multicolour_motion.py
python3 tools/arcade/record_multicolour_motion.py --frames 600
```

Use `--reuse-source` on the first command to rebuild with the frozen local pose
sample. `make run` continues to launch the original accepted game.
