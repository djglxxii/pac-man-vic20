# Direct composition from retained underlays

This increment avoids erasing some updates to slot 10, which normally holds
Pac-Man. It is a **small, partial flicker reduction**. Normal play remains
about 50 FPS; moving between bitmap footprints and overlapping other actors
still uses the existing erase/background/redraw sequence.

## Implementation

Each actor already retains the background beneath its two bitmap columns and
twelve scanlines: 24 bytes. When that footprint stays valid, the renderer can
read those saved bytes, combine them with the new shifted mask and write the
finished result directly to the display. There is no background-only erase of
the whole actor before painting it again.

Eligibility requires a valid two-column underlay, the same vertical position
and bitmap columns, no rebuild/maze flash, and no queued background change in
the actor's colour bands. The usual old/new overlap propagation runs first.
An isolation check then rejects sharing a possible pixel or colour footprint
with another dirty actor. Overlapping unchanged actors have already been pulled
into the dirty set by propagation. Clipped actors use the ordinary path.

Animation frames, flips, palettes and horizontal sub-byte position can change.
If the new mask becomes invisible, its deferred old image is explicitly
removed. The original saved colours survive composition; they are restored
immediately before applying the new actor colour. The pre-shifted ghost kernel
also has a composed path for masks appearing in this slot, including clearing
transparent edge rows left by an earlier generic frame.

This composes a small region one byte at a time using the existing underlay.
It does not allocate another bitmap or make display writes atomic. Some tearing
and colour transitions remain possible. White maze walls, white standing
pellets, actor priority, source graphics, scoring and the arcade clock are
preserved.

Checking every actor costs too much on this CPU. This first retained increment
tests one preferred slot. It continues to update every actor in the original
order; it does not change gameplay scheduling or ghost decisions.

The code consumes **230 resident bytes**, leaving **141 bytes in BLK1–3** and
15 in BLK5. One previously unused odd sprite-cache byte holds the current
painting mode. No RAM allocation, zero-page object, stack reduction or hardware
change is added. The PRG grows from 26,857 to 27,050 bytes.

## Measurements and limits

The frozen [measurement record](baselines/region-compositor.json) compares
parent `cf81d64` with this implementation using the same simulator and sample
setup. Standard samples last 180 NTSC frames; the transition lasts 360.

| Sample | Renders/s before | After | Composed updates after |
| --- | ---: | ---: | ---: |
| Normal play | 49.64 | 49.65 | 12 |
| Frightened | 54.00 | 53.67 | 15 |
| Attract chase | 42.91 | 41.65 | 0 |
| First intermission | 60.15 | 60.25 | 45 |
| Board transition | 40.89 | 40.88 | Not sampled |

The normal-play sample contains 478 actor paint entries. Only twelve avoid
erasing through this path, so this does not solve general moving-actor flicker.
Those composed paints average 1.231 ms of CPU work; frightened/intermission
composed paints average about 0.586 ms. These are paint durations, not measured
VIC pixel visibility or the duration of an atomic display update.

For the remaining normal-play erases, the 95th-percentile erase-to-paint window
changes from 11.666 to 11.408 ms, while its mean increases from 6.069 to
6.162 ms. Aggregate paired erase-window time changes from 987.21 to
963.26 actor-ms per second. Actor sets and sampled phases differ; fewer erases
alone must not be presented as a proportional reduction in perceived flicker.

Attract receives no composed updates in this sample and loses about 1.26 FPS.
The longer 1,800-frame gameplay workload measures 51.15 before and 50.71 FPS
after; it includes rebuild work. The normal gameplay rate is close, but this
is not a general speed improvement. Worst intervals remain uneven.

The coherent transition interval changes from 1939.72 to 1943.01 ms. The
focused settled-board check completes in 1927.15 ms, with maximum input/audio
gaps of 22.57/30.30 ms, within the existing acceptance limits.

## Validation and visual review

All **49 regression tests pass**, followed by 7,192 logical ticks through the
frontend scenes, including all three intermissions. The IRQ vector, stack guard
and one-time boot handoff remain intact. Observed software/hardware stack
write footprints are 32/22 bytes; the full reservations remain available.

Three additional renderer checks compare against the independent pixel/colour
model and verify restoration:

- Visible frames, all shifts/flips, palette changes and returning eyes compose
  without an actor erase when the footprint is valid.
- Row/column moves, invisible masks and neighbours sharing old/new colour
  footprints fall back safely, including deferred removal of invisible masks.
- All source vertical coordinates exercise quantization: movement within the
  same displayed row can compose, while an actual displayed-row change falls
  back, including hardware colour-row boundaries.

VICE verifies boot, coin/start, non-silent audio, the eight physical blue/white
flash phases and a settled next board. Separate 600-frame captures record actual
raster output with identical joystick inputs, without guest RAM edits. The
actors' exact sampled positions can differ because refresh timing differs.
Physical hardware has not been tested.

Local artifacts under ignored `build/region-compositor/` include:

- `comparison.mp4`: before on the left, after on the right; approximately ten
  seconds at 60.2845 video frames/s, 720×464, without audio.
- `before/vice/` and `after/vice/`: source clips, inputs and state records.
- `before/` and `after/`: performance, longer gameplay and actor trace reports.
- `regression.log` and `vice-validation/`: regression and emulator evidence.

```sh
make test
python3 tests/flicker.py --output build/region-compositor/current-flicker
python3 tests/performance.py --output build/region-compositor/current-performance
python3 tools/arcade/vice_check.py --maze-flash --output build/region-compositor/current-vice
```

Both timing tools accept `--prg PATH` with a sibling `.lbl` to compare a saved
executable. The actor observer identifies composed paints without adding guest
instructions. It reports their durations separately from erase-to-paint windows.

## Rejected expansions and next step

Multi-actor isolation checks, dirty-band occupancy bookkeeping and larger
composition opportunities reduced throughput to roughly 43–47 FPS in normal
play. Specialized aligned-column handling did not offset its setup cost. A
one-row underlay-slide prototype and rotating actor selection passed the
renderer oracle, but measured about 49.01 and 48.37 FPS respectively; frightened
throughput fell further. These variants were discarded. Local experiment
sources and timing reports remain under `build/region-compositor/experiment-*`.

Broader composition needs cheaper preparation and overlap handling. Faster
common sprite kernels remain the next performance candidate; score readability
is still queued. Keep this increment's limited coverage and the attract slowdown
visible when judging the comparison clip.
