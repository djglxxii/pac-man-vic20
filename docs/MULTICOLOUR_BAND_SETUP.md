# Multicolour band setup

The renderer now calculates colour eligibility once per actor and uses a tail
jump for column resolution. Mean complete rendering falls from **21.990 to
21.766 ms**, saving **1.02% CPU time**. Every one of the 480 recorded scenes
improves, with identical completed pixels and colours.

The later [direct background lookup](MULTICOLOUR_BACKGROUND_LOOKUP.md) reduces
current total rendering further to 21.398 ms while freeing more code and zero
page. The measurements here preserve the band-setup result.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-band-setup.mp4).
This remains the standalone renderer prototype. Artwork, colour priority,
replay deadlines and the accepted playable game are unchanged.

## What changed

After horizontal clipping, the pose's accent flag becomes a mask of eligible
visible columns. That mask is written into the band's colour-initialization
operand once per actor. Each band then resets its pending colours with one
immediate load and one zero-page store. Returning eyes still use zero; actual
colour writes still require accent pixels in the current row.

`resolve_row` now jumps directly to the selected column routine. Its final
`RTS` returns to preparation, removing an extra dispatcher call and return.
The allocator sets `mc_status` when its 54-cell limit fails, so the existing
error check and transaction cleanup still work with the tail dispatch.

Existing column-bit and phase-offset bytes move after a tail jump to preserve
the publisher's branch-page constraint. No table bytes are duplicated and no
padding is added. The existing link-time assertions remain enforced.

## Measurements

These are identical-packet native instruction-cycle measurements at 1,022,727
Hz, excluding game logic, audio, input and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 17.652 ms | 17.427 ms |
| Mean commit, including cleanup | 4.338 ms | 4.338 ms |
| Mean complete renderer | 21.990 ms | 21.766 ms |
| Complete renderer, 95th percentile | 26.308 ms | 26.078 ms |
| Complete renderer, maximum | 29.395 ms | 29.147 ms |

Every scene saves 160–273 cycles. Preparation uses 1.27% less CPU time, and
commit/publication costs are exactly unchanged in the paired replay. Inclusive
band-resolution cost falls from 9,250.34 to 8,958.42 cycles per scene; the new
upfront actor-mask calculation accounts for part of that saving.

Code shrinks by **three bytes**, from 1,987 to 1,984. STATE shrinks by **one
byte**, from 378 to 377, ending at `$1BAF`. Zero page remains 28 bytes and the
temporary map 567 bytes. All DATA bytes, DATA/BSS addresses, packed PRG length
and the `$6F36` expansion-RAM high-water mark are unchanged.

## Verification and limits

All **2,274 native scenes** and 590 Pac-Man facing checks pass. Independent
checks cover clipped and overlapping actors, returning eyes, partial bands,
maximum capacity, hidden preparation and transaction recovery. The forced
55th allocation still reports failure and preserves the live image. Permanent
glyphs and the 960-byte I/O/software-stack guard remain intact.

Instruction profiling confirms all seven nonzero colour masks still execute
in both work banks, with the same per-mask counts and 6,131 colour-update rows
as before. Every recorded picture and colour map matches the previous renderer.

VICE independently verifies hidden preparation and every picture pixel in a
completed scene. A fresh process captures 600 frames without guest patches;
the complete video decodes successfully. Original replay deadlines still yield
**32.61 updates per second**. These are renderer CPU savings, not integrated
game FPS or a new perceptual flicker result. Physical hardware has not been
tested. The main-game PRG remains byte-identical.

Hashes, measurements, path counts and capture metadata are frozen in
[the band-setup record](baselines/multicolour-band-setup.json). Remaining
performance and integration work is described in
[the motion notes](MULTICOLOUR_MOTION.md).
