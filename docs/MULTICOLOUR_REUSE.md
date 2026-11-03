# Multicolour reuse experiment and cell setup optimization

Reusing unchanged actor groups did not pay for its bookkeeping, so that
implementation was discarded. A smaller optimization to the existing
compositor is retained: **mean rendering time falls from 25.181 to 24.466 ms**,
or **2.84% less CPU time**, with identical output in all 480 recorded scenes.

The later [background-row pass](MULTICOLOUR_BACKGROUND_ROWS.md) reduces the
current mean further to 23.780 ms. The measurements here preserve the earlier
reuse/cell-setup result.

[Watch the current VICE preview](../build/multicolour-motion/motion-preview-cell-setup.mp4).
This remains the separate renderer prototype. Its approved blue maze, white
pellets, custom artwork, corrected Pac-Man facing and animation schedule are
preserved.

## Why group reuse was rejected

The experiment compared each actor's position, pose, colour and painter slot
against the committed image. It propagated changes through old shared cells
and potential new overlaps so a changed actor could not corrupt a retained
group. Unchanged groups kept their existing character codes. Changed groups
allocated hidden characters from the same 108-slot pool, with transaction
rollback returning unused slots.

Several revisions reduced the bookkeeping: shared-cell dependency lists,
conservative coordinate proximity tests, metadata stored by character slot,
and a free-slot stack. The best measured revision retained an average 6.335
cells per scene and reused cells in 228 of the 480 scenes. Its final pixels
and colours matched the prior renderer in every recorded scene. It also
passed the existing 2,274-scene native checks, including hidden preparation,
clipping, overlap, maximum capacity and transaction recovery.

Nevertheless, **335 scenes became slower and only 145 became faster**.
Preparation improved slightly, but dependency checks, list construction,
allocation and publication outweighed the skipped drawing. Both the average
and the longer frame costs regressed. No VICE recording or hardware test was
needed to reject that CPU regression.

| Work | Previous renderer | Rejected group reuse | Retained cell setup |
| --- | ---: | ---: | ---: |
| Mean preparation | 20.008 ms | 19.500 ms | 19.293 ms |
| Mean commit, including cleanup | 5.172 ms | 5.826 ms | 5.172 ms |
| Mean entire renderer | 25.181 ms | 25.325 ms | 24.466 ms |
| Entire renderer, 95th percentile | 30.041 ms | 32.519 ms | 29.098 ms |
| Entire renderer, maximum | 33.679 ms | 36.392 ms | 32.623 ms |

These are identical-packet, consecutive-scene instruction-cycle measurements
at 1,022,727 Hz. They exclude game logic, sound, input and IRQ overhead. This
does not establish that every reuse design will fail, but this implementation
should not be listed as an untried optimization again.

The rejected source, binary, assets, configuration and paired measurements are
archived locally under `build/multicolour-motion/rejected-actor-reuse/`.
The approved pre-experiment version is preserved in `before-actor-reuse/`.
The main game is unchanged.

## What is retained

The existing `get_work_cell` routine called two small helpers to construct
the temporary-map pointer and destination-glyph pointer. Both are now inlined
on that preparation path. Each lookup saves two `JSR`/`RTS` pairs: exactly
**24 cycles per call**. Publication and abort still share the map helper.

The replay averages 30.46 lookups per scene, saving 731.15 cycles, or 0.715 ms.
Every scene improves by 480–1,080 cycles; commit/publication costs are exactly
unchanged in the paired replay. No allocator, dirty-group logic, extra raster
wait or gameplay change remains from the rejected experiment.

Code grows by **14 bytes**, from 1,932 to 1,946. Alignment keeps the data and
temporary-map addresses unchanged, so the packed PRG length and expansion-RAM
high-water mark are unchanged. Metadata remains 386 bytes, zero page 29 bytes,
and the temporary cell map 567 bytes. The same conventional RAM target is
retained.

## Verification and limits

- All 2,274 native scenes and the 590 Pac-Man facing checks pass.
- All 480 before/after pictures and colour maps are identical. Source poses,
  artwork and replay packets are byte-identical.
- Hidden preparation, permanent glyphs, the 54-cell limit, transaction recovery
  and the 960-byte I/O/software-stack guard pass.
- VICE independently checks hidden preparation and every picture pixel in a
  completed scene. A fresh process records 600 frames without guest patches;
  the complete recording decodes successfully.

The capture still follows the original replay deadlines at about 32.6 updates
per second. CPU savings are not an integrated game FPS measurement. Physical
hardware has not been tested. The accepted main PRG is byte-identical to its
previous build. Full hashes and measurements are frozen in
[the reuse/cell-setup record](baselines/multicolour-reuse.json).

The subsequent background-row pass improves glyph setup without extra data
space. Further performance work can target the remaining masked row blits.
Full-game integration still needs the live background
cache, pellets/HUD, all game states and auxiliary-colour preservation described
in [the motion notes](MULTICOLOUR_MOTION.md).
