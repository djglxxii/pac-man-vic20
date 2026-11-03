# Sprite lookup layout

Rearranging the existing sprite lookup data reduces mean complete rendering
from **19.091 to 19.029 ms**, a **0.32% CPU saving**. All 480 recorded scenes
are faster, with identical published pixels and colours. Code, data, zero page
and working RAM occupy exactly the same space.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-row-layout.mp4).
This remains the standalone renderer prototype; playable-game integration is
still pending. The saving is small and does not establish a visible flicker
improvement.

The subsequent [background glyph ordering](MULTICOLOUR_BACKGROUND_LAYOUT.md)
reduces current rendering to 19.019 ms. Measurements below preserve the
sprite lookup pass.

## What changed

The 6502 takes an extra cycle when an absolute indexed read crosses a
256-byte page. The compositor reads three data planes, three mask planes and
one colour-accent plane, each containing 147 sprite-row records. Their former
order placed frequently used left and middle column lookups across page edges.

The asset builder now assigns small record indices to rows used most often
across **all artwork poses and horizontal shifts**. It does not use recorded
game positions to choose that order. The pose table is remapped to those new
indices, preserving every decoded row.

The assembly places the planes in this order: left data, accent, middle data,
right data, left mask, middle mask, right mask. Left and middle data and the
middle mask now fit entirely within their pages. Linker assertions protect
those three placements. The third column is used only at horizontal phase 3,
so its less frequent reads can occupy less favourable positions.

There is no padding, extra lookup, runtime sorting or new renderer instruction.
Existing instructions address the rearranged tables.

## Measurements

The same 480 frozen actor packets run on both binaries at 1,022,727 Hz.
These costs exclude game logic, input, audio and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 15.957 ms | 15.895 ms |
| Mean commit, including cleanup | 3.135 ms | 3.135 ms |
| Mean complete renderer | 19.091 ms | 19.029 ms |
| Complete renderer, 95th percentile | 22.770 ms | 22.681 ms |
| Complete renderer, maximum | 25.366 ms | 25.302 ms |
| Mean sprite lookup page crossings per scene | 85.56 | 22.50 |

Every recorded scene saves **21–129 cycles**, averaging **63.06 cycles**.
Preparation uses **0.39% less CPU time**. A separate access-count analysis
explains every paired cycle difference exactly through the removed page
crossings; cell resolution, commit and publication costs are unchanged.
Other artwork or positions may have different savings.

CODE remains 1,938 bytes, DATA 17,444 bytes, metadata 375 bytes, zero page
20 bytes and the work map 567 bytes. Segment addresses, the 23,077-byte PRG
length and the `$6F36` RAM high-water mark are unchanged. No larger RAM
configuration is needed; full-game placement is still future work.

## Verification and limits

All 1,512 decoded artwork rows match the previous tables. All **2,274 native
scenes**, 590 facing checks and the **496-frame continuous replay** pass,
including clipping, overlaps, hidden preparation, capacity failure/recovery
and replay wraparound.

VICE checks 32 successive scenes and 37 vacated-cell restorations. All 36,288
pixels in the final validation scene match; permanent glyphs, hidden
preparation and the 960-byte guard remain intact. A fresh, unpatched VICE
capture records 600 frames, and every frame decodes successfully.

The paced replay still completes **32.61 updates/s**. This is not an
integrated-game FPS result. Live pellets, scores, the background cache, game
logic, input and audio remain integration work. The main-game PRG is
byte-identical, and physical hardware has not been tested.

The [frozen measurement record](baselines/multicolour-row-layout.json) contains
hashes, paired timings, lookup-crossing counts, memory figures and validation.
The [motion notes](MULTICOLOUR_MOTION.md) track remaining integration work.
