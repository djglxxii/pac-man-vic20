# Cached restoration of old actor cells

Direct, cached accesses to old actor cells reduce mean commit time from
**3.907 to 3.135 ms**, a **19.76% CPU saving**. Complete rendering falls from
**20.152 to 19.380 ms**. Published pixels and colours remain identical across
all 480 recorded scenes.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-restoration.mp4).
This remains the standalone moving-renderer prototype. The accepted playable
game is unchanged.

## What changed

Previously, every old cell rebuilt an indirect pointer to the temporary work
map. Vacated cells also called a screen/colour pointer helper and constructed
a background pointer. Most old cells are still needed by the new image, but
they paid the initial pointer setup anyway.

Restoration now keeps its old-list cursor in Y and the cell's low byte in X.
It caches the raw cell page in a comparison operand. When that page changes,
it patches four absolute-X operands: the map read, background read, screen
store and colour store. A cache hit skips that setup. All three valid cell
pages use the same path, and the cache remains valid across updates.

The background table has a nonzero low address. Its indexed read retains
normal 6502 page crossing, including the extra cycle. Screen, colour and work
map bases are page-aligned. A linker assertion keeps the common cache-hit
branch within one code page.

The map still determines whether an old cell is shared or vacated. Shared
cells retain their old visible glyph until publication switches them directly
to the prepared image. Vacated cells recover their original background and
white accent before new cells are published. Publication's palette-before-code
ordering, abort cleanup and hidden preparation are preserved.

The screen/colour pointer helper and its two zero-page pointers are removed.
The replay loader still shares the map pointer before preparation begins.

## Measurements

The same 480 frozen actor packets run on both binaries, with instruction costs
converted at 1,022,727 Hz. Logic, input, audio and IRQ overhead are excluded.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 16.246 ms | 16.246 ms |
| Mean commit, including cleanup | 3.907 ms | 3.135 ms |
| Mean publication, including restoration | 3.804 ms | 3.032 ms |
| Mean complete renderer | 20.152 ms | 19.380 ms |
| Complete renderer, 95th percentile | 24.033 ms | 23.125 ms |
| Complete renderer, maximum | 26.732 ms | 25.780 ms |

There are 479 faster scenes, one equal scene and no slower scenes. The equal
scene has no prior actor cells. Preparation costs are exactly identical across
all 480 scenes. Complete rendering uses **3.83% less CPU time**; publication,
including restoration, uses 20.29% less.

The restoration cache hits on **89.07%** of 14,424 old-cell visits. Of those
cells, 13,661 are shared with the next image and 763 are restored. The timings
include all cache misses and 466 indexed background page crossings.

Code shrinks by **eight bytes**, from 1,964 to **1,956**. Zero page shrinks
from 24 to **20 bytes**. Metadata remains 375 bytes. All 17,444 DATA bytes,
their addresses, the 567-byte work map and the 23,077-byte PRG length are
unchanged. No larger memory configuration is needed; final placement with the
full game remains future work.

## Verification and limits

All **2,274 native scenes**, 590 facing checks and the **496-frame continuous
replay** pass. These cover clipping, overlaps, empty/full lists, hidden
preparation, discard/replacement, invalid input, and capacity failure and
recovery in all three allocation paths. Continuous replay uses the real packet
loader and timer IRQ through stream wraparound.

VICE verification now checks **32 consecutive scenes**, including actual
vacated-cell restoration, against the independent compositor. Hidden
preparation, permanent backgrounds and the 960-byte I/O/software-stack guard
remain intact. All 36,288 picture pixels of the final validation scene match.
A separate fresh VICE process records 600 frames without guest patches; every
frame decodes. Replay deadlines retain their original pacing.

This measures renderer CPU time, not integrated-game FPS or perceptual flicker.
Live pellets, scores, input, audio, game logic and the background cache remain
pending integration. The main-game PRG remains byte-identical. Physical
hardware has not been tested.

The [frozen measurement record](baselines/multicolour-restoration.json)
contains hashes, paired measurements, memory figures and capture checks.
The [motion notes](MULTICOLOUR_MOTION.md) track remaining integration work.

The subsequent [allocation cleanup](MULTICOLOUR_CELL_ALLOCATION.md) preserves
this restoration path and reduces complete rendering further to 19.091 ms.
