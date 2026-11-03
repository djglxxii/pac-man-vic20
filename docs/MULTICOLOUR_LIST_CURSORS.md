# Register-held work-list cursors

Keeping work-list positions in CPU registers reduces mean commit time from
**4.333 to 3.907 ms**, a **9.85% CPU saving**. Complete rendering falls from
**20.579 to 20.152 ms**. All 480 recorded scenes finish faster with identical
published pixels and colours.

[Watch the updated VICE preview](../build/multicolour-motion/motion-preview-list-cursors.mp4).
This remains the standalone moving-renderer prototype. The accepted playable
game is unchanged.

## What changed

Publication now keeps the new-cell list position in Y throughout the loop.
Indirect reads already use Y, so the loop no longer reloads its position from
RAM on every cell. TYA supplies the working-character offset, and INY advances
to the next record. This saves ten cycles per published cell.

Restoration and abort/failure cleanup need Y for their indirect cell accesses.
They keep the list position in X instead, copying it into Y when reading each
record. Their pointer helpers preserve X. INX replaces the memory increment,
saving four cycles per visited cell. The shared list-position state byte is
removed.

Both traversals retain their original forward order and count checks, including
empty and full 54-cell lists. Vacated cells are restored before publication;
shared cells still switch directly to their hidden prepared glyphs. Palette
writes precede screen-code writes. The existing cached-page and lookup page
assertions remain in force.

## Measurements

The same 480 frozen actor packets run on both binaries, with instruction costs
converted at 1,022,727 Hz. Logic, input, audio and IRQ overhead are excluded.

| Work | Previous | Current |
| --- | ---: | ---: |
| Mean hidden preparation | 16.246 ms | 16.246 ms |
| Mean commit, including cleanup | 4.333 ms | 3.907 ms |
| Mean screen/colour publication | 4.231 ms | 3.804 ms |
| Mean complete renderer | 20.579 ms | 20.152 ms |
| Complete renderer, 95th percentile | 24.560 ms | 24.033 ms |
| Complete renderer, maximum | 27.336 ms | 26.732 ms |

Every recorded scene saves 245–619 cycles. Preparation costs are identical;
the complete renderer uses **2.07% less CPU time**. Publication, including
restoration, uses 10.08% less CPU time.

Code shrinks by **22 bytes**, from 1,986 to **1,964**. Metadata shrinks from
376 to **375 bytes** at `$1A37–$1BAD`. Zero page remains 24 bytes. DATA, the
567-byte work map, PRG length and RAM high-water mark are unchanged. All DATA
bytes retain their addresses and contents. No larger memory configuration is
needed; final placement with the full game remains future work.

## Verification and limits

All **2,274 native scenes**, 590 facing checks and the **496-frame continuous
replay** pass. These exercise clipping, overlaps, empty/full lists, hidden
preparation, discard/replacement, invalid input, and capacity failure and
recovery in each of the three allocation paths. The continuous replay runs the
real packet loader and timer IRQ through stream wraparound.

VICE independently verifies hidden preparation, matrix/colour output and all
36,288 picture pixels. The 960-byte I/O/software-stack guard stays intact. A
fresh VICE process captures 600 frames without guest patches; every frame
decodes. Replay pacing still follows the original deadlines at **32.61 updates
per second**.

This is a reduction in renderer CPU time, not an integrated-game FPS or
perceptual flicker result. Live pellets, scores, input, audio, game logic and the
background cache are still pending integration. The main-game PRG remains
byte-identical. Physical hardware has not been tested.

The [frozen measurement record](baselines/multicolour-list-cursors.json)
contains hashes, paired measurements, memory figures and capture checks.
The [motion notes](MULTICOLOUR_MOTION.md) track remaining integration work.

The subsequent [cached restoration pass](MULTICOLOUR_RESTORATION.md) retains
register-held cursors while removing old-cell pointer setup, reducing complete
rendering further to 19.380 ms.
