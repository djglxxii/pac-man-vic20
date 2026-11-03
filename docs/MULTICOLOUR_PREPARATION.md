# Multicolour preparation optimization

The selected blue-maze renderer now uses **17.39% less CPU time** to prepare
its hidden characters, reducing the complete renderer's CPU time by **14.41%**. All 480
recorded scenes improve, with identical published pixels and colours. This
change is retained in the separate moving prototype; full-game integration
still needs further work.

A later [reuse/cell-setup pass](MULTICOLOUR_REUSE.md) discards group reuse after
measurement and retains a smaller address-setup optimization, reducing current
total rendering time further to 24.466 ms. The tables below preserve this
earlier character-band measurement.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-preparation.mp4).
The artwork, corrected Pac-Man facing and recorded animation schedule are
unchanged.

## What changed

Profiling the previous version found that cell lookup and setup consumed
13,319 cycles of the average 24,770-cycle preparation, including 8,793 cycles
inside working-cell lookup/allocation.

The compositor now processes each actor in eight-scanline character bands.
It clips the actor and selects its column routines once, resolves destination
characters once per band, then keeps Y as the scanline index throughout that
band. A biased source pointer lets the same index fetch the matching pose row.
Specialized column routines advance the cell address directly instead of
repeating clipping, multiplication-table lookups and pointer selection for
each column.

This preserves the shared-cell map and painter order. Every overlapping actor
still composes into the same hidden glyph, and preparation cannot alter the
live image. The allocator and background-copy work are unchanged; their mean
cost remains 8,793 cycles. The combined band/cell setup falls to 10,971
cycles, and the remaining saving comes from the scanline loop.

Allocation failure now propagates from the specialized resolver to the
preparation transaction. A forced 55th allocation verifies rejection and
recovery without changing the prior visible image.

## Measured result

Both native binaries receive the same 480 packets consecutively, starting from
the same initial scene. Measurements use actual 6502 instruction cycles at
1,022,727 Hz and exclude game logic, audio, input and IRQ overhead.

| Work | Previous mean | Optimized mean | Reduction |
| --- | ---: | ---: | ---: |
| Hidden preparation | 24.219 ms | 20.008 ms | 17.39% |
| Commit, including cleanup | 5.201 ms | 5.172 ms | 0.55% |
| Entire renderer | 29.421 ms | 25.181 ms | 14.41% |

The complete renderer's 95th percentile falls from 35.252 to 30.041 ms, and
its maximum falls from 39.171 to 33.679 ms. Every recorded scene saves at
least 3,608 cycles overall. The small commit saving comes from code/address
layout and the changed cell order; publication is not redesigned in this pass.

The real VICE recording still measures **32.61 replay updates per second**.
Its original deadlines limit the replay rate, so CPU savings do not accelerate
the recorded animation. The new mean cost corresponds to roughly 39.7 updates
per second if only this renderer ran without pacing; that is a CPU-capacity
estimate, not a measured game frame rate. No integrated-game FPS improvement
is claimed.

## Memory and verification

Code and inline dispatch tables grow by 424 bytes, from 1,508 to 1,932 bytes.
Metadata grows by four bytes, from 382 to 386, ending at `$1BB8`. Zero-page use
remains 29 bytes, and the temporary cell map remains 567 bytes. Page alignment
moves the end of the standalone expansion-RAM allocation from `$6D36` to
`$6F36`; both fit the existing conventional expansion target. No additional
character slots or new RAM configuration are needed. This remains a prototype
allocation rather than a final layout beside the full game.

- All **2,274 native scenes** match the independent pixel compositor. The
  additional 648 cases cover partial first/last bands for every pose and
  horizontal phase, including a single visible scanline.
- All 480 before/after recorded pictures and colour maps are identical.
  Artwork assets, source poses and replay packets are byte-identical.
- Maximum 54-cell images, hidden preparation, discard/replacement, invalid
  poses and forced capacity failure/recovery pass. Permanent backgrounds and
  the 960-byte I/O/software-stack guard remain intact.
- The 590 Pac-Man facing checks still pass in all four directions.
- VICE independently verifies hidden preparation, published screen codes and
  colours, and all 36,288 picture pixels in a completed scene. A fresh process
  captures 600 video frames without patching guest code or RAM; the entire
  video decodes successfully.

The accepted main-game PRG remains byte-identical. Full hashes, segment sizes,
before/after profiles and capture metadata are frozen in
[the preparation measurement record](baselines/multicolour-preparation.json).
The [initial motion record](baselines/multicolour-motion.json) preserves the
earlier result.

## Remaining work

At 25.181 ms per complete redraw before game logic and sound, the prototype
still needs more optimization. The subsequent group-reuse experiment was
rejected because its bookkeeping outweighed the saved work; see
[the measured result](MULTICOLOUR_REUSE.md). Integration also needs the live background
cache, pellets, score/messages, all game states and audio auxiliary-colour
preservation described in [the moving-renderer notes](MULTICOLOUR_MOTION.md).
