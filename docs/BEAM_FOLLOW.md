# Original graphics: drawing behind the beam

**2026-11-04 playable revisit:** current-artwork all-group and player-priority
builds were supplied for direct play testing. The user rejected the
raster-priority approach: no noticeable improvement and a performance hit.
See [BEAM_PRIORITY.md](BEAM_PRIORITY.md) for the review, commands,
actual-capture rates and remaining unprotected cases. The
historical rejection and measurements below describe the earlier trial.

**Not accepted after user review:** the user saw no perceptible difference.
The subsequent [capture audit](CAPTURE_AUDIT.md) verifies that the experimental
code ran, but also finds that the previously quoted FPS came from a different
benchmark workload. The fresh active capture measures 23.51 renderer calls/s
versus 33.42 for the original, below the user's 30 FPS trial threshold.
The original remains unchanged; this separate target is retained for diagnosis.

This experiment
uses the accepted original graphics and gameplay. It schedules actor erase,
background-colour restoration, drawing and new colours together while the
VIC is outside the affected character rows. It does not use the rejected
multicolour renderer or temporary character copies.

```sh
make run-beam
```

The executable is `build/pacman-beam.prg`. Controls and the conventional +3K
plus BLK1/2/3/5 expansion remain unchanged. `make run` still launches the
original accepted build, with its original PRG bytes.

[Compare VICE gameplay](../build/beam-follow/vice/comparison.mp4): original
left, beam-scheduled build right. Both silent ten-second recordings use the
same joystick-input sequence without patching guest code or state. Different
startup/render costs put their first samples at ticks 431 and 433, respectively;
they are representative playthroughs rather than identical game-state frames.

## Scheduling

The existing dirty-actor scan runs once. Each dirty actor gets a bounding box
covering the full colour cells of both its old and new footprints. Intersecting
boxes form groups. Every group retains the original reverse restoration and
forward drawing order, including colour ownership and output-slot swaps.
Independent groups can be processed in another order safely.

The scheduler reads `$9004` and selects a group with enough time before the
beam's next visit. If none is ready, it polls until a safe window opens.
The window starts after the affected rows have passed and includes the wrap
through the top border, provided drawing will finish before those rows return.
This avoids waiting for a particular raster line after a usable window has
already opened.

Bounds cover whole 8×16 colour cells, with a margin after their last line.
The initial conservative budget is 40 scanlines per actor plus 16 scanlines
of group overhead. A group whose span plus budget cannot fit in a frame uses
the original drawing path without waiting. **Queued background edits, full
rebuilds and completion flashing also retain the original transaction.**
Those fallback updates can still flicker.

The 16,875-cycle arcade timer is unchanged. Ghost decisions, movement masks,
random sequence, collisions and game-task ordering continue on the original
clock. Waiting happens in presentation, so input and audio service can be
delayed; logical parity does not mean perfectly even real-time service.

## Measurements

The standard native NTSC CPU-cycle samples include the game, with scripted
setup and no continuing joystick turns in the opening sample. These figures
are not the FPS of the recorded computer-controlled playthrough:

| Scene | Original FPS | Beam build FPS |
| --- | ---: | ---: |
| Normal play | 51.93 | 32.57 |
| Frightened | 54.61 | 34.55 |
| Attract chase | 43.65 | 44.55 |
| First intermission | 60.03 | 58.88 |
| Board transition | 41.86 | 40.32 |

Normal refresh elapsed time, including waits, rises from 9.29 to 15.63 ms.
Its maximum input/audio service gaps are 32.67/39.55 ms. The largest normal
refresh is 25.83 ms. These are sample averages and maxima, not guaranteed
minimum frame rates. The user considers results above 30 FPS worth a play test.

In a separate 600-video-frame native run, **854 of 1,270 actor erases** occur
inside protected groups. All 787 scheduled groups in that sample fit their
budgets and stay outside their affected colour rows throughout erasing and
drawing. The longest protected group takes 8.777 ms. These are timing checks;
user review found no perceptible benefit to justify the lower FPS.

## Memory and checks

The original bitmap, screen matrix and virtual-I/O addresses remain intact.
Renderer metadata occupies 72 bytes at `$1D40–$1D87`; a 184-byte bounds helper
runs at `$1DC0–$1E77`. Its load image fits the existing temporary boot region
and is copied before gameplay. A 256-byte software stack remains at
`$1F00–$1FFF`, against 32 bytes of actual use observed through all three
intermissions. Linker assertions and runtime checks protect the regions.
No new memory hardware or banking is introduced.

Verification covers:

- Six native arcade-parity/memory/audio tests and all six existing renderer
  tests, including movement, frightened RNG, artwork, clipping and overlaps.
- 480 changing grouped scenes with exact final bitmap and colour agreement
  against the original executable, including disappearances and tunnel wrap.
- 1,048 native phase fixtures: 917 protected groups and 131 deliberate
  six-actor fallbacks. Protected groups of up to five actors finish within
  budget and outside the affected colour rows across the raster phases.
- A 600-frame live native timing trace covering protected and fallback erases.
- Seven smoke scenes through all three intermissions, with stack/IRQ guards
  and the copied helper checked in every scene.
- 64 live groups observed in actual VICE across all four initial ghost slots.
  Every checked group stays outside its affected rows for the complete
  erase/draw interval, with no guest patches.

Hashes, full timing results and checks are recorded in
[the beam-build baseline](baselines/beam-follow.json). Physical hardware and
PAL have not been tested. The accepted original remains the default.

```sh
make beam
make test-beam
python3 tests/performance.py --prg build/pacman-beam.prg --output build/beam-follow/performance
python3 tools/arcade/check_beam.py
python3 tools/arcade/record_shadow.py --after build/pacman-beam.prg --output build/beam-follow/vice --frames 600
```
