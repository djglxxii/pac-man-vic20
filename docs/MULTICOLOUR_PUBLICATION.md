# Multicolour publication page cache

Publication now reuses its address setup while consecutive cells share a
screen page. Mean commit time falls from **5.173 to 4.596 ms**, saving **11.17%**.
Mean total rendering falls from **23.780 to 23.203 ms**, saving **2.43%**.
All 480 recorded scenes improve, with identical completed pixels and colours.

The later [colour-write pass](MULTICOLOUR_COLOURS.md) reduces current total
rendering further to 22.737 ms. The measurements here preserve the publication
cache result.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-publication.mp4).
This remains the standalone renderer prototype; artwork, replay pacing and the
accepted playable game are unchanged.

## What changed

The publisher patches three store instructions for each new cell: its screen
code, colour and temporary-map entry. Their high address bytes depend only on
the cell's page, which is 0, 1 or 2. Previously, all three were recalculated
for every published cell.

A comparison now skips that setup when the page matches the previous cell.
The cached value lives in the comparison instruction's operand, starts at the
invalid value `$FF`, and remains valid across frames. The publisher owns these
patched store operands; background restoration uses separate pointers.

In the 480-scene replay, **89.08%** of published cells reuse the existing
setup: 12,879 of 14,457 cells. Address setup runs 3.288 times per scene instead
of 30.119. Preparation and its CPU costs are unchanged.

## Measurements

These are identical-packet native instruction-cycle measurements at 1,022,727
Hz, excluding game logic, audio, input and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 18.607 ms | 18.607 ms |
| Mean publication | 5.071 ms | 4.494 ms |
| Mean commit, including cleanup | 5.173 ms | 4.596 ms |
| Mean complete renderer | 23.780 ms | 23.203 ms |
| Complete renderer, 95th percentile | 28.261 ms | 27.470 ms |
| Complete renderer, maximum | 31.618 ms | 30.667 ms |

Every recorded scene saves 319–973 cycles overall. Code grows by **seven
bytes**, from 1,977 to 1,984. Data, zero page, metadata and temporary storage
are unchanged. Alignment also keeps PRG length and the expansion-RAM allocation
ending at `$6F36` unchanged. No new RAM configuration is needed.

## Verification and limits

All **2,274 native scenes** and 590 Pac-Man facing checks pass. The scene set
covers the three address pages, clipping, overlapping actors, empty images,
capacity/recovery cases and consecutive preparations/publications. Every
recorded picture and colour map matches the prior version; all DATA bytes
and the main-game binary are unchanged. The 960-byte I/O/software-stack guard
remains intact.

VICE independently verifies hidden preparation and every picture pixel in a
completed scene. A fresh process records 600 frames without guest patches;
the entire recording decodes successfully. Original replay deadlines still
produce **32.61 updates per second**. These CPU savings do not establish an
integrated game FPS improvement or a perceptual flicker result. Physical
hardware has not been tested.

Hashes, profiles, cache counts and capture metadata are frozen in
[the publication measurement record](baselines/multicolour-publication.json).
Remaining masked drawing and full-game integration work are described in
[the motion notes](MULTICOLOUR_MOTION.md).
