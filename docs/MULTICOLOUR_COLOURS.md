# Multicolour colour-write paths

Colour handling now uses **27.3% fewer CPU cycles** in the recorded replay.
Mean complete rendering falls from **23.203 to 22.737 ms**, a **2.00%** saving.
Every one of the 480 recorded scenes improves, with identical finished pixels
and colours.

The later [loop-operand pass](MULTICOLOUR_LOOP_OPERANDS.md) reduces current
total rendering further to 22.344 ms while freeing more code and metadata.
The measurements here preserve the colour-write result.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-colours.mp4).
This remains the standalone renderer prototype. The approved artwork, colour
priority, replay deadlines and accepted playable game are unchanged.

## What changed

The former colour loop tested three column bits independently, loaded the
actor colour for each write, and saved/restored Y to use it as a colour index.
The new code selects a short path for the exact nonzero three-bit mask. It
loads the actor colour once, uses X for colour indices, and leaves Y holding
the glyph scanline. Common masks 3, 2 and 1 are tested first.

Both 54-byte colour banks are now adjacent. A colour slot is simply its work
character code minus 147, giving indices 0–107 into that contiguous array.
This permits fixed absolute-X stores and a cheaper immediate subtraction when
resolving cells. Screen codes, actor order and the rule of updating only cells
containing actor-accent pixels are preserved.

`color_pending` moves into a previously unused zero-page byte. The old pending
byte, temporary accent mask and saved Y byte leave STATE, freeing three bytes.
The zero-page allocation stays at 29 bytes.

## Measurements

These are identical-packet native instruction-cycle measurements at 1,022,727
Hz, excluding game logic, audio, input and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Colour handling, cycles per scene | 1,481.18 | 1,076.85 |
| Mean hidden preparation | 18.607 ms | 18.168 ms |
| Mean commit, including cleanup | 4.596 ms | 4.570 ms |
| Mean complete renderer | 23.203 ms | 22.737 ms |
| Complete renderer, 95th percentile | 27.470 ms | 27.193 ms |
| Complete renderer, maximum | 30.667 ms | 30.375 ms |

Every scene saves 238–693 cycles overall. The small commit saving comes from
code layout: the cached-page branch no longer crosses a page on a cache hit.
The publication algorithm is unchanged.

Code grows by **18 bytes**, from 1,984 to 2,002. Metadata falls from 386 to
**383 bytes**, ending at `$1BB5`. DATA/BSS addresses, the 567-byte temporary map,
packed PRG length and the `$6F36` expansion-RAM high-water mark are unchanged.
All DATA bytes remain identical. No new RAM configuration is needed.

## Verification and limits

All **2,274 native scenes** and 590 Pac-Man facing checks pass. Independent
pixel checks cover clipping, overlap, maximum capacity, hidden preparation,
transaction recovery and the 960-byte I/O/software-stack guard. All recorded
pictures and colour maps match the prior version.

Instruction profiling confirms **all seven nonzero colour masks execute in
both work banks**, including the rare mask 4. The 480-scene replay performs
6,131 colour-update rows; this coverage is counted from actual branch execution.

VICE independently verifies hidden preparation and every picture pixel in a
completed scene. A fresh process captures 600 frames without guest patches;
the complete video decodes successfully. Original replay deadlines still
produce **32.61 updates per second**. This is CPU headroom in the prototype,
not an integrated game FPS measurement or a new perceptual flicker result.
Physical hardware has not been tested. The accepted main-game PRG is unchanged.

Hashes, measurements, per-bank path counts and capture metadata are frozen in
[the colour-write record](baselines/multicolour-colours.json). Remaining
performance and full-game integration work is described in
[the motion notes](MULTICOLOUR_MOTION.md).
