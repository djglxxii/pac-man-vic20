# Multicolour loop operands

The renderer now uses immediate operands for values that remain constant
during an actor, character band or work-bank interval. Mean rendering falls
from **22.737 to 22.344 ms**, saving **1.73% CPU time**. All 480 recorded scenes
improve, with identical completed pixels and colours.

The later [map-pointer pass](MULTICOLOUR_MAP_POINTER.md) reduces current total
rendering further to 21.990 ms while freeing more code and zero page. The
measurements here preserve the loop-operand result.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-loop-operands.mp4).
The approved artwork, actor order, replay pacing and accepted playable game
are unchanged. This remains the separate moving renderer prototype.

## What changed

The band scanline limit is written directly into its `CPY` operand. Actor
colour and the two bytes of the biased pose-row address similarly become
immediate operands. Their setup already stored these values once; redirecting
those stores removes repeated absolute-memory reads without extra row setup.

The working-bank base lives in the allocation instruction's `ADC` operand.
The exported `mc_new_base` name refers to that byte. Bank selection also
updates the publisher's immediate copy, keeping character allocation,
metadata selection and publication synchronized. Initialization, commit and
abort semantics are preserved.

Both calls to the glyph-address macro already hold the character code in A.
`TAX` now uses that value directly, avoiding a redundant absolute-memory
reload. Lookup tables move to an unreachable gap after a tail jump so the
publisher's common cached-page branch stays within a page. No table bytes
are duplicated and no padding is added. Link-time assertions protect the
branch and lookup-table page boundaries.

The code already runs from writable expansion RAM and patches its pose and
publication instructions. This extends that existing approach; the replay
IRQ counts timer ticks and does not reenter the renderer.

## Measurements

These are identical-packet native instruction-cycle measurements at 1,022,727
Hz, excluding game logic, audio, input and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 18.168 ms | 17.830 ms |
| Mean commit, including cleanup | 4.570 ms | 4.514 ms |
| Mean complete renderer | 22.737 ms | 22.344 ms |
| Complete renderer, 95th percentile | 27.193 ms | 26.746 ms |
| Complete renderer, maximum | 30.375 ms | 29.881 ms |

Every scene saves 314–505 cycles overall. Preparation uses 1.86% less CPU
time and commit 1.22% less.

Code shrinks by **seven bytes**, from 2,002 to 1,995. STATE shrinks by **five
bytes**, from 383 to 378, ending at `$1BB0`. Zero page remains 29 bytes and
the temporary map 567 bytes. All DATA bytes, DATA/BSS addresses, packed PRG
length and the `$6F36` expansion-RAM high-water mark are unchanged. The same
RAM configuration is retained.

## Verification and limits

All **2,274 native scenes** and 590 Pac-Man facing checks pass. The scene set
includes all poses and horizontal/vertical phases, partial bands, HUD and
edge clipping, overlap, 54-cell capacity and transaction recovery. Every
recorded picture and colour map matches the previous renderer. Permanent
glyphs and the 960-byte I/O/software-stack guard remain intact.

VICE independently verifies hidden preparation and all 36,288 picture pixels
in a completed scene. A fresh process records 600 frames without guest
patches; the entire video decodes successfully. Original replay deadlines
still produce **32.61 updates per second**. CPU headroom here is not an
integrated game FPS measurement or a new perceptual flicker result. Physical
hardware has not been tested; the main-game PRG remains byte-identical.

Hashes, measurements and capture metadata are frozen in
[the loop-operand record](baselines/multicolour-loop-operands.json). Remaining
performance and integration work is described in
[the motion notes](MULTICOLOUR_MOTION.md).
