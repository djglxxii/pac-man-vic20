# Streamlined work-cell allocation

Removing redundant register and flag work reduces mean hidden preparation
from **16.246 to 15.957 ms**, a **1.78% CPU saving**. Complete rendering falls
from **19.380 to 19.091 ms**. All 480 recorded scenes finish faster with
identical published pixels and colours, while code shrinks by **18 bytes**.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-allocation.mp4).
This remains the standalone moving-renderer prototype. Integration with the
playable game is still pending.

## What changed

The allocator loads the new-cell list position directly into Y and checks its
54-cell limit with CPY. Y remains the list position through the three metadata
writes, so TYA supplies the work-character offset without another RAM read.
The successful capacity check also leaves carry clear; none of the intervening
loads, stores or TYA changes carry. That removes a redundant CLC before adding
the working-character bank base.

The unrolled background copy stops after writing the final scanline. Its last
DEY had no consumer: the next resolver sets Y before using it, and the caller
sets Y before drawing. Together these changes save **eight cycles per newly
allocated cell**, across all three column paths.

The preparation caller now tests the resolver's carry result directly. Every
successful resolution returns C clear; capacity failure sets both C and
`mc_status`. Avoiding the status reload saves another **four cycles per band**.
The existing status byte and failure cleanup remain available.

Moving the eight-byte high-address resolution lookup ahead of publication
keeps both cached-page branches within their code pages without padding.
The lookup also has an explicit page-boundary assertion. This rearrangement
adds no data or runtime work.

## Measurements

The same 480 frozen actor packets run on both binaries at 1,022,727 Hz.
These costs exclude game logic, input, audio and IRQ overhead.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 16.246 ms | 15.957 ms |
| Mean commit, including cleanup | 3.135 ms | 3.135 ms |
| Mean complete renderer | 19.380 ms | 19.091 ms |
| Complete renderer, 95th percentile | 23.125 ms | 22.770 ms |
| Complete renderer, maximum | 25.780 ms | 25.366 ms |

Every scene saves **200–424 cycles**. Complete rendering uses **1.49% less CPU
time**. Cell resolution falls from 7,755.31 to 7,514.36 mean cycles per scene;
the caller supplies the remaining saving. Commit and publication costs are
exactly identical across all 480 scenes.

CODE shrinks from 1,956 to **1,938 bytes** at `$2000–$2791`. Zero page remains
20 bytes, metadata 375 bytes, DATA 17,444 bytes and the work map 567 bytes.
All DATA bytes retain their exact addresses and contents. PRG length remains
23,077 bytes and the RAM high-water mark stays at `$6F36`. No larger memory
configuration is needed; full-game placement remains future work.

## Verification and limits

All **2,274 native scenes**, 590 facing checks and the **496-frame continuous
replay** pass. They cover clipping, overlaps, hidden preparation, empty/full
lists, discard/replacement, invalid input and capacity failure/recovery in
all three allocation paths.

A separate native fault-injection check follows the actual preparation caller
when each column path encounters an extra allocation after the 54-cell limit.
All three reach the failure branch through the new carry test, preserve the
visible image and guards, clear the work map and accept a subsequent scene.
Only that isolated test injects capacity state.

VICE independently checks 32 successive scenes, including 37 vacated-cell
restorations. Hidden preparation, permanent glyphs and the 960-byte guard
remain intact; all 36,288 pixels of the final validation scene match. A fresh
VICE process records 600 frames without guest patches, and every frame decodes.

The paced replay still completes **32.61 updates/s**. The CPU saving is not an
integrated-game FPS result or a new perceptual flicker result. Live pellets,
scores, input, audio, game logic and the background cache still need
integration. The main-game PRG remains byte-identical. Physical hardware has
not been tested.

The [frozen measurement record](baselines/multicolour-cell-allocation.json)
contains hashes, paired timings, memory figures and verification results.
The [motion notes](MULTICOLOUR_MOTION.md) track remaining integration work.

The subsequent [sprite lookup layout](MULTICOLOUR_ROW_LAYOUT.md) reduces
complete rendering further to 19.029 ms without growing code or data. The
figures above describe the allocation pass in isolation.
