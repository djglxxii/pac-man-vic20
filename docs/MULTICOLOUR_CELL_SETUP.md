# Direct work-cell setup

Work-cell setup now writes glyph addresses directly to the left, middle and
right drawing pointers. Mean complete rendering falls from **21.398 to
20.579 ms**, saving **3.83% CPU time**. All 480 recorded scenes improve with
identical completed pictures and colours.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-cell-setup.mp4).
This remains the standalone renderer prototype. The accepted playable game,
artwork, colour priority and replay deadlines are unchanged.

## What changed

Previously every resolved cell called a shared helper, received its glyph
address through a temporary pointer, and copied that address to the drawing
pointer. Three column-specific blocks now allocate or reuse cells directly.
The eight clipping masks enter and share these blocks, preserving left-to-right
allocation order and the common map used by overlapping actors. There is no
per-cell helper call or temporary glyph-pointer copy.

Each block owns its patched absolute background-map read. All three read the
same bank selector, now the publisher's immediate operand; changing banks
updates that single value. The capacity guard remains in each allocation path.

The temporary glyph pointer and current-code state byte are removed. Startup
copies permanent characters through the left drawing pointer before rendering
starts. Existing lookup bytes are reordered to preserve indexed-table and
publication branch page constraints, without padding or extra data.

## Measurements

These are native instruction-cycle measurements of the same 480 frozen
packets at 1,022,727 Hz. Game logic, audio, input and IRQ overhead are excluded.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 17.060 ms | 16.246 ms |
| Mean commit, including cleanup | 4.338 ms | 4.333 ms |
| Mean complete renderer | 21.398 ms | 20.579 ms |
| Complete renderer, 95th percentile | 25.624 ms | 24.560 ms |
| Complete renderer, maximum | 28.595 ms | 27.336 ms |

Every recorded scene saves 540–1,288 cycles. Preparation uses 4.77% less CPU
time. Inclusive column resolution falls from 8,582.56 to 7,755.31 cycles per
scene. Commit saves five cycles: four from removing the redundant bank-selector
store and one from code placement in publication.

Code grows by **nine bytes**, from 1,977 to 1,986. Metadata shrinks from 377 to
**376 bytes**, and zero page from 26 to **24 bytes**. DATA, the 567-byte work
map, PRG length and expansion-RAM high-water mark are unchanged. The added code
fits before the existing page-aligned DATA segment. No larger RAM configuration
is needed; final placement alongside the complete game remains future work.

A first candidate specialized only the common two/three-column footprints and
retained the general helper for clipping. It reached 20.480 ms but added 348
code bytes and moved DATA/BSS by 512 bytes. Sharing the new paths with clipped
actors recovers 339 code bytes while giving up only 0.099 ms per scene. That
smaller version is retained. The first candidate and measurements are archived
under `build/multicolour-motion/candidate-cell-specialization-fast/`.

## Verification and limits

All **2,274 native scenes**, 590 facing checks and the **496-frame continuous
replay** pass. Preparation leaves the live image hidden; overlaps, clipping,
replacement, rejection and recovery preserve the same transaction guarantees.
The forced 55th-allocation check now separately exercises left, middle and
right allocation failures, including reuse of earlier cells in the band.

VICE independently confirms hidden preparation, published data and all 36,288
picture pixels. The 960-byte I/O/software-stack guard remains intact. A fresh
VICE process captures 600 frames without guest patches, and all frames decode.
The replay retains its original pacing at **32.61 updates per second**.

These are renderer CPU savings, not integrated-game FPS or a new claim about
perceived flicker. The executable still uses a fixed maze, pellets and score;
game logic, input, audio and live background updates remain outside it. The
main-game PRG is byte-identical. Physical hardware has not been tested.

The subsequent [register-held list cursors](MULTICOLOUR_LIST_CURSORS.md) reduce
commit time further to 3.907 ms and complete rendering to 20.152 ms, while
freeing 22 code bytes and one metadata byte.

Hashes, costs, memory figures and capture checks are frozen in
[the cell-setup record](baselines/multicolour-cell-setup.json).
Remaining work is described in [the motion notes](MULTICOLOUR_MOTION.md).
