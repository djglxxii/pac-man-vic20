# Background glyph ordering

Assigning the common maze patterns lower character numbers reduces mean
complete rendering from **19.029 to 19.019 ms**, a **0.05% CPU saving**.
This is a small asset-only optimization: the assembly, memory allocations,
artwork and completed pictures are unchanged.

[Watch the current VICE preview](../build/multicolour-motion/motion-preview-background-layout.mp4).
This remains the standalone multicolour prototype. The accepted playable
game is unchanged, and this saving does not imply a visible flicker improvement.

## Change and measurement

The builder previously numbered background glyphs in byte-sorted order. It
now sorts them by how often each pattern occurs across the entire static
playfield, excluding the HUD. Pattern bytes break frequency ties. Recorded
actor positions do not influence the ordering.

Both charset encodings and the background map use the new numbers. Their
decoded glyphs and all 567 background cells are identical. The eight existing
147-byte row planes can then copy common glyphs with fewer absolute-indexed
reads crossing a 256-byte page. There is no runtime sorting or extra padding.

Both binaries receive the same 480 frozen packets at 1,022,727 Hz. Costs
exclude game logic, input, audio and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 15.895 ms | 15.885 ms |
| Mean commit, including cleanup | 3.135 ms | 3.135 ms |
| Mean complete renderer | 19.029 ms | 19.019 ms |
| Complete renderer, 95th percentile | 22.681 ms | 22.672 ms |
| Complete renderer, maximum | 25.302 ms | 25.295 ms |
| Mean background-copy page crossings per scene | 21.20 | 10.70 |

Of the 480 scenes, **474 improve**, four tie and two cost two additional
cycles. Mean saving is **10.51 cycles**, with a maximum of 24. An independent
count of background copies explains every paired cycle difference exactly.
Commit and publication costs are identical in every scene. Different maze
patterns or a future dynamic cache can have different savings.

CODE remains 1,938 bytes, DATA 17,444 bytes, metadata 375 bytes, zero page
20 bytes and the work map 567 bytes. All segment addresses, the 23,077-byte
PRG length and the `$6F36` RAM high-water mark are unchanged. The executable
instructions are byte-identical; only the background data changes.

## Verification and limits

All **2,274 native scenes**, 590 facing checks and the **496-frame continuous
replay** pass, including clipping, overlaps, hidden preparation, capacity
failure/recovery and stream wraparound. Paired runs produce identical pixels
and colours for all 480 recorded scenes.

VICE verifies 32 successive scenes, 37 vacated-cell restorations, all 36,288
final picture pixels, permanent glyphs and the 960-byte guard. A fresh
unpatched VICE process captures 600 frames; all frames decode successfully.
Replay pacing remains **32.61 updates/s**, not an integrated-game FPS result.

The main-game PRG remains byte-identical. Live pellets, HUD updates, the
background cache, logic, input, audio and final memory placement still need
integration; physical hardware has not been tested. A future cache must keep
both background encodings synchronized with its current glyph assignments.

The [frozen record](baselines/multicolour-background-layout.json) contains
hashes, paired timings, memory figures and verification. See the
[motion notes](MULTICOLOUR_MOTION.md) for the remaining work.
