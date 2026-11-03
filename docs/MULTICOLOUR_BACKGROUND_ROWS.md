# Multicolour background row tables

The moving prototype now stores its permanent background glyphs by scanline
instead of by character. This reduces mean rendering time from **24.466 to
23.780 ms**, saving **2.80% CPU time** across the same 480 recorded scenes.
Every scene improves, with identical completed pixels and colours.

The later [publication page cache](MULTICOLOUR_PUBLICATION.md) reduces current
total rendering further to 23.203 ms. The measurements here preserve the
background-row pass.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-background-rows.mp4).
The artwork, Pac-Man facing, palette, painter order and replay deadlines are
unchanged. The accepted playable game is still separate and unchanged.

## What changed

Previously, each new work character looked up the background character's
address, then copied its eight bytes through a source pointer. The PRG now
stores eight planes of 147 bytes: all first scanlines, then all second
scanlines, and so on. X remains the background character code, allowing each
copy instruction to load its scanline directly with absolute indexed addressing.
This removes the background glyph-address lookup and the indirect source reads.
The destination still uses the existing hidden-character pointer.

The eight planes **replace** the previous 1,176-byte character-major table in
the executable. They use exactly the same number of bytes. The builder also
keeps the canonical character-major file for the independent pixel oracle.
Transposing the planes back reproduces every byte of all 147 glyphs, including
the reserved blank entries. Boot loads the same permanent VIC character bytes
from the new representation before enabling the display.

Transparent/opaque row dispatch was considered before selecting this change.
In this replay, a byte-operation estimate gives about 595 cycles per scene
from eliminating the empty-column work and redundant opaque-column reads,
before page-cross effects or dispatch overhead. Row classification would
consume part of that saving. No new row-dispatch implementation is retained
or claimed to have been benchmarked.

## Measured result

Both binaries receive the same 480 actor packets consecutively. Costs are
actual native instruction cycles at 1,022,727 Hz, excluding game logic, sound,
input and IRQ overhead.

| Work | Previous mean | New mean |
| --- | ---: | ---: |
| Hidden preparation | 19.293 ms | 18.607 ms |
| Commit, including cleanup | 5.172 ms | 5.173 ms |
| Entire renderer | 24.466 ms | 23.780 ms |
| Entire renderer, 95th percentile | 29.098 ms | 28.261 ms |
| Entire renderer, maximum | 32.623 ms | 31.618 ms |

Preparation uses 3.56% less CPU time. Every full scene saves 478–1,027 cycles.
The inclusive `get_work_cell` cost falls from 8,061.78 to 7,420.38 cycles per
scene. Indexed page crossings and changes in code-address layout affect the
exact savings; publication costs one additional cycle per scene in this build.

Code grows by **31 bytes**, from 1,946 to 1,977. Existing alignment padding
absorbs the growth: DATA/BSS addresses, packed PRG length, and the allocation's
`$6F36` high-water mark are unchanged. The glyph data remains 1,176 bytes,
metadata 386 bytes, zero page 29 bytes and temporary cell map 567 bytes. No
additional working RAM, character slots or RAM configuration are needed.

Startup takes 5,906 extra cycles, about **5.775 ms**, once while the display is
disabled. This is the cost of reconstructing the permanent character-major
VIC glyphs from row planes; repeated rendering then uses the cheaper copies.

## Verification and limits

- All **2,274 native scenes** and 590 Pac-Man facing checks pass.
- Every recorded picture and colour map matches the previous renderer. Source
  poses, artwork, replay packets and canonical background files are unchanged.
- Native checks verify all permanent glyph bytes, hidden preparation, clipping,
  overlap, maximum 54-cell capacity, transaction recovery and the 960-byte
  I/O/software-stack guard.
- VICE independently verifies hidden preparation and all 36,288 picture pixels
  in a completed scene. A fresh process captures 600 frames without guest
  patches; the entire video decodes successfully.

The replay still follows its original deadlines at **32.61 updates per second**.
This is CPU headroom in the standalone renderer, not an integrated game FPS
measurement or a new perceptual flicker result. Physical hardware has not been
tested. The accepted main-game PRG remains byte-identical. Hashes, profiles,
startup costs and capture metadata are frozen in
[the background-row measurement record](baselines/multicolour-background-rows.json).

Further optimization can examine the remaining masked drawing work. Integration
still needs the background cache and live game-state coverage described in
[the motion notes](MULTICOLOUR_MOTION.md). When a future cache assigns a new
permanent glyph, it must update the corresponding row-plane bytes as well as
the VIC character data.
