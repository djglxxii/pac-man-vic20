# Shared cell-map address byte

The cell index and temporary-map pointer now share their low byte. Mean
rendering falls from **22.344 to 21.990 ms**, saving **1.58% CPU time**. All
480 recorded scenes improve, with identical completed pixels and colours.

The later [band-setup pass](MULTICOLOUR_BAND_SETUP.md) reduces current total
rendering further to 21.766 ms while freeing more code and metadata. The
measurements here preserve the map-pointer result.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-map-pointer.mp4).
This remains the standalone renderer prototype. The approved artwork,
colour priority, replay pacing and accepted playable game are unchanged.

## What changed

The temporary map starts on a 256-byte boundary, so its pointer's low byte
always equals the low byte of the current cell index. Previously, each map
lookup copied that byte into a separate pointer. The new representation
aliases `cell_low` to the existing map pointer's low byte and keeps
`cell_high` separately as the raw index's high byte.

Pointer setup now calculates only the absolute high byte. This removes one
zero-page load/store pair, saving **six cycles per refresh** during character
preparation, old-cell checks and abort cleanup. Cell index increments still
update the raw high byte on carry. Background and screen addressing use the
named index bytes; they are no longer an adjacent two-byte index.

A link-time assertion enforces the map's page alignment. The map stays at
`$6D00`, so no storage or hardware configuration changes are required.

## Measurements

These are identical-packet native instruction-cycle measurements at 1,022,727
Hz, excluding game logic, audio, input and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 17.830 ms | 17.652 ms |
| Mean commit, including cleanup | 4.514 ms | 4.338 ms |
| Mean complete renderer | 22.344 ms | 21.990 ms |
| Complete renderer, 95th percentile | 26.746 ms | 26.308 ms |
| Complete renderer, maximum | 29.881 ms | 29.395 ms |

Every complete scene saves 149–509 cycles. Preparation uses 1.00% less CPU
time and commit averages 3.88% less. The first commit has no old map entries
and costs one cycle more because code addresses move; its complete scene
still improves.

Code shrinks by **eight bytes**, from 1,995 to 1,987. Zero page shrinks from
29 to **28 bytes**. STATE remains 378 bytes, ending at `$1BB0`, and the
temporary map remains 567 bytes. All DATA bytes, DATA/BSS addresses, packed
PRG length and the `$6F36` expansion-RAM high-water mark are unchanged.

## Verification and limits

All **2,274 native scenes** and 590 Pac-Man facing checks pass. Independent
pixel checks cover clipped and overlapping actors, map-page transitions,
54-cell capacity, hidden preparation, transaction recovery and the 960-byte
I/O/software-stack guard. All recorded pictures and colour maps match the
previous renderer.

VICE independently verifies hidden preparation and every picture pixel in a
completed scene. A fresh process captures 600 frames without guest patches;
the entire video decodes successfully. Original replay deadlines still yield
**32.61 updates per second**. These are renderer CPU savings, not integrated
game FPS or a new perceptual flicker result. Physical hardware has not been
tested. The main-game PRG remains byte-identical.

Hashes, measurements and capture metadata are frozen in
[the map-pointer record](baselines/multicolour-map-pointer.json). Remaining
performance and integration work is described in
[the motion notes](MULTICOLOUR_MOTION.md).
