# Ghost-precomposition experiment

**Rejected after visual review:** the user saw no significant difference in
the flicker itself. The broader precomposition proposal from
[the flicker audit](FLICKER_AUDIT.md) keeps the old picture visible while
preparing overlapping actors, but that does not establish a useful perceptual
improvement. Normal play falls from **51.93 to 29.28 FPS**, and frightened play
from **54.61 to 34.32 FPS**. That speed loss is not justified by the visual
result. The faster main executable was already restored before this review;
no additional runtime reversion is needed.

## What was tried

Unlike the earlier Pac-Man-only experiment, this prototype collects the old
and new footprints of every dirty actor into shared scratch columns. Ghosts,
Pac-Man, fruit and returning eyes can share those columns. Existing reverse
underlay restoration and forward painting operate on the scratch image,
preserving overlap priority and the background saved beneath each actor.
Only after composition finishes are prepared pixels and colours copied back.

The temporary image uses a **512-byte software-stack frame** within the
existing 704-byte reservation. Its first 196 bytes provide a colour-RAM
shadow; the remaining 316 bytes hold selected bitmap-column intervals. Only
touched colour cells are copied. The original stack reservation and hardware
configuration stay in place. A stack-pointer check leaves the lower canary
and at least 64 bytes beneath the scratch frame for callees.

Four 14-byte tables describe each column's minimum/maximum Y and translated
scratch address. Nearby or overlapping rectangles share storage. An unused
underlay-header byte caches the bitmap column, avoiding repeated address
searches. Four-byte copy unrolling and explicit zero-page declarations reduce
the first prototype's cost. The colour pointer adds two assembly zero-page
bytes, balanced by reducing the compiler's allocation ceiling from 92 to 90.

Queued background changes, full rebuilds, maze flashing, clipped dirty actors,
insufficient scratch capacity and insufficient stack room use the existing
renderer. Gameplay intermissions also retain the original path. No raster
wait, gameplay-timer change, ghost-state rescheduling or new expansion device
is introduced. Completed pixels, colours, shapes and underlays remain identical
to the existing renderer in the checks.

## Measurements

These are the standard 180-video-frame CPU-cycle samples, with at least 360
frames for the board transition. Different rendering costs change which
updates occur inside the sample; these are not identical-input kernel tests.

| Variant | Normal FPS | Frightened FPS | Normal actor erases performed in scratch |
| --- | ---: | ---: | ---: |
| Current main build | 51.93 | 54.61 | 0% |
| Initial full-colour prototype | 25.92 | 26.93 | 56.5% |
| Optimized full-colour preview | 29.28 | 34.32 | 59.8% |
| Limit composed pixels to 128 | 35.58 | 42.63 | 34.6% |
| Limit composed pixels to 96 | 40.28 | 47.66 | 16.4% |
| Limit composed pixels to 64 | 43.63 | 50.34 | 6.4% |
| Keep colour updates live | 31.91 | 36.24 | 64.0% |

The size-limited variants reject expensive spans before snapshotting them.
They recover speed by protecting fewer updates. Updating colours live avoids
part of the shadow work, but still loses too much throughput and permits
intermediate recolouring of the old picture. It is not the saved preview.

The optimized full-colour preview performs 217 normal-play actor erases in
scratch and 146 on the live bitmap. Its 56 complete publication transactions
average **3.387 ms**, with a 4.446 ms 95th percentile and 4.948 ms maximum.
Frightened publication averages 2.878 ms, with a 5.208 ms maximum. Attract chase
has no composed updates in this sample; the intermission is on the fallback.

These publication intervals differ from erase-to-paint intervals: the old
ghost remains visible during preparation, and publication copies a completed
image. The host observer distinguishes scratch erases from live erases rather
than reporting scratch work as a visible hole. Neither metric directly
measures individual VIC fetches or perceptual flicker. Fallback updates still
have holes, and their normal-play mean rises from 5.662 to 9.485 ms in these
different sampled workloads.

Normal refresh work averages 17.40 ms versus 9.29 ms before the change, leaving
too little room for logic and sound within a 16.50 ms arcade tick. Normal
input/audio gaps reach 33.27/33.08 ms; frightened gaps reach 33.09/37.35 ms.
The VIA clock remains unchanged. The audit's short-copy estimates are not
achieved by this implementation: interval collection, snapshotting, pointer
translation, colours and publication all cost CPU time.

The preview consumes **619 resident bytes**, leaving 97 raw bytes in BLK1–3
(96 after heap alignment) and 15 in BLK5. It does not require relocating or
shrinking the stack. The packed PRG is 27,198 bytes, versus 26,715 for main.

## Validation and local review

All **51 prototype regression tests** pass, followed by a 7,183-tick smoke run
covering all three intermissions. Three additional renderer tests check 480
changing overlapping scenes; hold pixels and colours unchanged through four
complete preparations before publication; and exercise eight fallback cases,
including capacity failure after a partial snapshot. Final underlay restoration,
the software-stack pointer and the colour pointer are checked.

The smoke run observes 518 bytes of software-stack writes and 24 hardware-stack
bytes, with the lower guard and IRQ vector intact. This is observed use, not
a proof of every possible path. VICE independently verifies boot, coin/start,
non-silent audio, all eight blue/white maze phases and the settled next board.
Physical hardware has not been tested.

Two 600-frame VICE captures replay the same joystick inputs without guest
patches. Both run from tick 431 to 1033 and pellet count 3 to 73. The comparison
has frames where the preview retains ghosts that are missing in main, while
other frames still lose actors on fallback updates. This supports visual
review, not a claim of flicker-free play or an acceptable motion tradeoff.
The user's subsequent review found no significant difference in the flicker
itself. Individual retained-ghost frames and improved scratch coverage do not
override that perceptual result.

Local artifacts under ignored `build/precompose/` include:

- `comparison.mp4`: current main on the left, full-colour preview on the right;
  720×496, 600 frames, no audio.
- `preview/pacman.prg` and `.lbl`: the playable experimental build.
- `preview/run.sh`: launch the preview with the usual VICE controls.
- `preview/implementation.patch`, source/tests/observer snapshots and native
  binaries: the complete experiment, independent of the restored main build.
- `before/` and `prototype-2/`: profiles, actor traces and actual raster captures.
- `prototype-regression.log` and `prototype-2/vice-validation/`: prototype checks.
- `restore-regression.log` and `restored-binaries.json`: restored-main checks.

The rejected preview remains archived for reproducing the comparison:

```sh
bash build/precompose/preview/run.sh
```

`make run` continues to launch the faster main build. After restoration, all
**48 main-build tests** pass and both the PRG and flat native image are
byte-identical to the pre-experiment baseline. No additional VICE run is needed
for those identical main binaries. The [frozen record](baselines/ghost-precomposition.json)
identifies the measured executables and archived source hashes.

This shared-column implementation provides no significant flicker improvement
in user review and costs too much throughput. Do not repeat it as a supported
flicker fix. This result does not establish that every precomposition design
will fail; a future proposal needs a concrete reason to expect a different
visual result as well as a lower CPU cost.
