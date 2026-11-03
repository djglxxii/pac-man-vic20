# Direct background-map lookup

Background-map reads now use absolute indexed addressing instead of building
a source pointer for each new work cell. Mean rendering falls from **21.766
to 21.398 ms**, saving **1.69% CPU time**. Every recorded scene improves with
identical completed pixels and colours.

Together with the preceding [band-setup pass](MULTICOLOUR_BAND_SETUP.md), this
reduces the last accepted 21.990 ms baseline by 2.69%.

The subsequent [direct work-cell setup](MULTICOLOUR_CELL_SETUP.md) reduces
current total rendering to 20.579 ms, using nine extra code bytes while
releasing another two zero-page bytes and one metadata byte.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-background-lookup.mp4).
This remains the standalone renderer prototype. Artwork, colour priority,
replay deadlines and the accepted playable game are unchanged.

## What changed

Cell lookup already calculates the work-map pointer's high byte. That value
also determines the background-map page. The new code converts it and patches
the high byte of an absolute-X read; X supplies the cell's low index byte.
The CPU handles any indexed page crossing. This removes the separate source
pointer calculation and indirect read from the allocation path.

The conversion uses the clear carry left by work-map address setup for valid
cell pages. Link-time assertions protect page alignment and the page range.
Existing resolver lookup bytes move to preserve the publisher's branch-page
constraint, with no duplicated data or padding.

Replay input and old-cell restoration can now share `src_ptr` with the map
pointer because their lifetimes do not overlap. Restoration captures the
screen/colour destinations before overwriting the shared low byte with the
background source address. This releases a two-byte zero-page pointer.

## Measurements

These are identical-packet native instruction-cycle measurements at 1,022,727
Hz, excluding game logic, audio, input and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 17.427 ms | 17.060 ms |
| Mean commit, including cleanup | 4.338 ms | 4.338 ms |
| Mean complete renderer | 21.766 ms | 21.398 ms |
| Complete renderer, 95th percentile | 26.078 ms | 25.624 ms |
| Complete renderer, maximum | 29.147 ms | 28.595 ms |

Every scene saves 250–564 cycles. Preparation uses 2.11% less CPU time, and
commit/publication costs are exactly unchanged in the paired replay. Inclusive
`get_work_cell` cost falls from 7,146.54 to 6,770.68 cycles per scene.

Code shrinks by **seven bytes**, from 1,984 to 1,977. Zero page shrinks from
28 to **26 bytes**. STATE remains 377 bytes and the temporary map 567 bytes.
All DATA bytes, DATA/BSS addresses, packed PRG length and the `$6F36`
expansion-RAM high-water mark are unchanged. No new RAM configuration is needed.

## Verification and limits

All **2,274 native scenes** and 590 Pac-Man facing checks pass, covering
clipping, overlap, capacity, hidden preparation and transaction recovery.
Every recorded picture and colour map matches the previous renderer.

A new continuous-program check also verifies **496 replay frames**, including
16 after the source stream wraps. It runs the actual packet loader and timer
IRQ, without patching packets or control state, and checks every actor packet,
published picture, permanent glyph and guard. This tests the pointer's replay,
preparation and restoration roles together rather than only isolated calls.
Only the unused I/O/software-stack guard receives a test pattern.

VICE independently verifies hidden preparation and every picture pixel in a
completed scene. A fresh process captures 600 frames without guest patches;
the complete video decodes successfully. Original replay deadlines still yield
**32.61 updates per second**. These are renderer CPU savings, not integrated
game FPS or a new perceptual flicker result. Physical hardware has not been
tested. The main-game PRG remains byte-identical.

Hashes, measurements, continuous replay checks and capture metadata are frozen
in [the background-lookup record](baselines/multicolour-background-lookup.json).
Remaining performance and integration work is described in
[the motion notes](MULTICOLOUR_MOTION.md).
