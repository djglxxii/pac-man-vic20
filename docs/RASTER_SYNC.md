# Rejected raster-synchronization experiment

**Reverted at the user's request after visual review found no perceptible
improvement.** The faster generic sprite-kernel build remains active. Removing
the experiment recovers 317 resident bytes, returning BLK1–3 headroom to
391 bytes; BLK5 retains 15. The hardware configuration is unchanged.

The prototype deferred eligible updates in Pac-Man's usual actor slot until
the other actors had finished, then checked the VIC scan position before
erasing and repainting that actor. Conservative old/new footprint and dirty
background checks preserved overlap priority and shared colour cells. Frame
wrap and complete 16-line colour rows were included in its timing gate.
Ghosts generally continued through the existing renderer.

## Why it was removed

The protection was limited and did not produce a visible improvement for the
user. Frightened and attract throughput also regressed:

| Sample | Accepted kernel renders/s | Rejected prototype |
| --- | ---: | ---: |
| Normal play | 51.38 | 51.39 |
| Frightened | 54.02 | 52.02 |
| Attract chase | 44.25 | 42.60 |
| First intermission | 60.15 | 60.26 |
| Board transition | 41.86 | 41.72 |

Only 16 of 480 actor erases in the short normal-play sample used the protected
path. Mean actor erase-to-paint time fell from 5.738 to 5.463 ms, but those CPU
work windows do not establish a perceptible reduction in flicker. A separate
600-frame joystick-driven VICE capture confirmed 149 scheduled protected
updates, with visible ghost flicker remaining. Both captures ran from tick
431 to 1033 and pellet count 3 to 73 using identical inputs.

The performance cost and 317 resident bytes were not justified by the visual
result. The earlier generic painter optimization is retained because it
improves throughput and frees memory.

## Historical validation and archive

The rejected build passed 51 regression tests, a 7,192-tick smoke run and VICE
checks for boot, controls, audio, maze flashing and the next board. Its four
additional renderer checks included 1,048 scan-phase cases, 2,304 deferred
mask/shift/flip cases, overlap/disappearance fallbacks and queued background
interactions. These established correctness of the limited path, not a useful
visual improvement. Physical hardware was not tested.

The restored build uses the preceding 47-test suite. The four experiment-only
tests, wrapping diagnostic counter, scan observer and runtime changes were
removed. The [frozen measurement record](baselines/raster-sync.json) explicitly
identifies its after measurements and hashes as the rejected executable.
The rebuilt PRG and native image are byte-identical to the saved accepted
sprite-kernel build. All 47 tests and the frontend smoke run pass after
restoration, with the IRQ vector and stack guard intact. Its existing VICE
validation therefore applies; VICE was not rerun after this reversion.

Local artifacts remain in ignored `build/raster-sync/`. The exact experimental
source, tests, observer, documentation and binaries are preserved under
`rejected/`. The comparison video, raw profiles/traces, phase observations and
VICE captures remain available. They should help avoid repeating the same
limited single-actor approach. This result does not rule out a broader
renderer redesign, but provides no reason to retain this implementation.
