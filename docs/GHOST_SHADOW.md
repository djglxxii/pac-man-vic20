# Original graphics: temporary character copies

**Rejected after user play testing:** the user could not see a difference in
the flicker. Normal-play throughput falls from 51.93 to 33.51 FPS without a
perceptible benefit. The accepted original build remains the default and is
byte-identical; no runtime reversion is needed. The separate target, source,
captures and measurements remain available for reproducing this result.

The user has clarified that the
accepted original game, its responsiveness and arcade behaviour are the
foundation. Reducing actor flicker is the main goal. Colour clash is acceptable;
the multicolour redesign is on hold. The user considers results above 30 FPS
worth trying, even when slower than the original.

```sh
make run-shadow
```

This launches `build/pacman-shadow.prg` with the original white maze, 112×216
hires picture, actors, scores and controls. `make run` continues to launch the
accepted game. Its PRG remains byte-identical, SHA-256
`8e62f44052d280cf63674878c362ba72493d8e5aeba55363913e5cc5cf99b621`.

[Side-by-side VICE video](../build/ghost-shadow/vice/comparison.mp4): original
on the left, preview on the right. These are silent ten-second raster captures
with identical joystick inputs, running from logical ticks 431 to 1033 and
pellet counts 3 to 73. Neither recording patches game code or state.
The new capture retains ghosts missing from some original frames, but the user
reported: "I cannot tell a differene. looks the same to me." Those individual
frames and the character-bit checks do not establish a worthwhile perceptual
improvement. The frame-rate cost is not justified by this result.

## How it works

Before an ordinary actor update, copy the old character cells touched by dirty
actors into spare VIC-visible glyphs. Point those screen cells at the copies.
The original erase, background update and actor drawing then operate on the
original bitmap. At the end, restore the screen codes to that updated bitmap.
The old actor bits remain available to the VIC while the working bitmap is
erased. All six slots participate, including overlapping actors and clipping.
An already-copied cell is shared, so six four-cell footprints need at most
24 copies.

This retains the existing drawing routines and artwork. It adds no background
cache or new gameplay scheduling. Full rebuilds and completion flashing use
the existing path; an explicit restore also releases pending copies.

**This does not eliminate all visible flicker.** Colour RAM still changes live:
held actors may change colour, and a restored black foreground can temporarily
hide their pixels. New footprint edges are also drawn live, and switching
screen codes can tear. The pixel-preservation checks below concern character
bits, rather than unchanged RGB output throughout the update.

## Performance

The later [capture audit](CAPTURE_AUDIT.md) clarifies that these staged native
benchmark rates are not the rates in the comparison videos. Fresh active
capture counts 20.82 renderer calls/s for this experiment and 33.42 for the
original. Loaded-program checks and 125 calls to the shadow routine during
that recording confirm that the experimental path ran.

The same native NTSC CPU-cycle samples measure completed pictures, including
the actual game logic, input and sound workload:

| Scene | Original FPS | Preview FPS |
| --- | ---: | ---: |
| Normal play | 51.93 | 33.51 |
| Frightened | 54.61 | 38.20 |
| Attract chase | 43.65 | 36.24 |
| First intermission | 60.03 | 59.82 |
| Board transition | 41.86 | 40.69 |

Normal refresh work rises from 9.29 to 15.07 ms. Its maximum measured
input/audio service gaps are 35.00/32.58 ms, versus 27.56/26.58 ms before.
The arcade timer remains 16,875 cycles (approximately 60.606 Hz), with
movement, RNG, collisions, sound sequencing and update order unchanged.
These are sample averages, not minimum frame rates. Board-transition figures
include progressive construction and are not steady gameplay rates.

## Memory and validation

The conventional +3K and BLK1/2/3/5 expansion remains the hardware target.
Twenty-four 8×16 glyphs use 384 bytes at `$1D40–$1EBF`, codes 212–235.
The software stack retains 320 bytes at `$1EC0–$1FFF`; the seven-scene smoke
run observes 32 bytes of actual software-stack use. Virtual I/O at
`$1C40–$1D3F` remains separate. Metadata uses 49 expansion-RAM bytes.
The preview retains 356 free bytes in BLK1–3 and 15 in BLK5.

The preview passes 13 native checks: six arcade-parity/memory/audio checks,
the six existing renderer tests, and a new hidden-pixel test. The latter
checks 121 transitions, including a full 24-cell footprint, arbitrary poses,
clipping, overlap, disappearance, explicit restoration and stack guards.
Every old displayed character bit survives the erase stage, and every completed
picture restores the fixed screen mapping. The original renderer oracle
continues to check exact final bitmap bytes and colour values.

The smoke run covers 7,183 logical ticks and all three intermissions, with
the software-stack guard and IRQ vector intact. Separate VICE checks verify
the temporary glyphs through actual VIC pixel fetches. See the frozen
[preview record](baselines/ghost-shadow.json). Physical hardware and PAL have
not been tested.

```sh
make ghost-shadow
make test-shadow
python3 tests/performance.py --prg build/pacman-shadow.prg --output build/ghost-shadow/performance
python3 tools/arcade/check_shadow.py
python3 tools/arcade/record_shadow.py --frames 600
```

This implementation is rejected. Do not repeat it as a demonstrated flicker
fix. A future trial needs to account for the visible output, including live
foreground-colour changes, and establish a reason to expect a perceptible
improvement. The 30 FPS play-test threshold remains acceptable, but crossing
that threshold alone does not justify a change.
