# Experimental raster-aware Pac-Man updates

This prototype times eligible updates in Pac-Man's usual actor slot around
the VIC's scan position. It is available on `optimization/raster-sync` for
visual review. **It is a limited experiment, with throughput tradeoffs, and
moving ghosts still flicker.** The preceding generic sprite-kernel improvement
is retained.

## How the update works

The existing renderer restores dirty actors in reverse priority order, updates
the background, and paints actors in forward order. Its incomplete images can
be scanned by the VIC while that work is in progress.

For eligible slot-10 updates, the prototype leaves the old image visible
through that process. Once the other actors are finished, it checks `$9004`,
waits if the scan is too close, then restores and repaints this one actor.
Eligibility requires an existing underlay, a nonzero new palette, old/new
motion within three display pixels, separation from other actors' old and
new footprints, and no queued background writes in the affected vertical
bands. Full rebuilds and maze flashes use the original path.

The isolation tests include the two bitmap columns and complete 16-line
colour cells, not just opaque actor pixels. They conservatively allow 35
pixels vertically and 23 horizontally around the new position, including
the allowed old/new motion. Unrelated actors can share rows if their columns
are sufficiently far apart. Overlaps and nearby tile/colour edits fall back
to the original priority-preserving renderer.

The scan gate covers the union of the old and new complete colour rows. It
allows at least two lines after that region and 56 lines before its next
visit. Both ordinary and frame-wrapping safe intervals are handled. The last
NTSC counter value covers one line; wrap calculations use a conservative
one-line allowance. Updates can run immediately if already in a safe window.
The original VIA gameplay clock and IRQ are unchanged.

Five spare odd entries in the sprite cache hold bounds, a completion flag
and a wrapping scheduled-update counter; the selected dirty flag uses its
high bit. There is no new allocation or hardware requirement. Resident code
costs **317 bytes**, leaving **74 bytes** in BLK1–3 and 15 in BLK5. No
additional framebuffer is used.

## Measurements

The baseline is the user-accepted generic sprite-kernel build, PRG SHA-256
`34a552f6377bf64ec3373882464c028244b43697a1471cbc3d6e06ede4dbc442`.
It is saved under `build/raster-sync/before/`; the common Git ancestor remains
`cf81d64`, because the preceding work has not yet been committed.
The [frozen record](baselines/raster-sync.json) identifies both actual binaries.

| Sample | Baseline renders/s | Prototype | Protected updates |
| --- | ---: | ---: | ---: |
| Normal play | 51.38 | 51.39 | 16 |
| Frightened | 54.02 | 52.02 | 0 |
| Attract chase | 44.25 | 42.60 | 0 |
| First intermission | 60.15 | 60.26 | 58 |
| Board transition | 41.86 | 41.72 | Not sampled |

Samples last 180 NTSC video frames, or 360 for transition. Normal play's mean
actor erase-to-paint window falls from 5.738 to 5.463 ms; its 95th percentile
falls from 10.830 to 10.601 ms. These samples can select different updates as
cadence changes. Only 16 of 480 total actor erases in the normal sample use
the protected path; the scope is much smaller than a complete synchronized
renderer. The frightened and attract throughput losses are a material cost.

The observer finds no scan intersection in the 16 normal and 58 intermission
protected windows. Normal protected updates take at most 2.404 ms from the
gate's return through final colours. The intermission's longest wait is
5.730 ms. These observations use the headless simulator's scan model; they
do not measure perceptual flicker or prove physical-hardware timing.

## Validation and review

All **51 regression tests** pass, followed by a smoke run covering 7,192
logical ticks with the IRQ vector and stack guard intact. The four new
renderer checks cover:

- 1,048 entry-phase cases at eight vertical positions, including colour-cell
  boundaries, the top/bottom of the display and frame wrap. The largest
  observed isolated update is 2,466 cycles; the largest wait is 5,842 cycles.
- 2,304 regular/returning-eye mask, shift and flip cases through the deferred
  path, with independent bitmap/colour/restoration comparison and a
  56-scanline update deadline.
- Movement jumps, disappearing actors and overlapping/shared-colour actors
  falling back to the original path.
- Unrelated queued HUD work allowing deferral, and a nearby colour-cell edit
  forcing fallback. Both results match a fresh complete background redraw.

The isolated routine calls mask IRQs. The ordinary workload measurements keep
the real game IRQ active. The headless simulator exposes the raster counter
but does not render individual VIC fetches or model all NTSC counter quirks.

VICE checks pass for boot, coin/start, sound, all eight blue/white maze-flash
phases and a settled next board. A focused transition settles in 1827.45 ms
with input/audio gaps of 24.68/27.59 ms. Physical hardware has not been tested.

`build/raster-sync/comparison.mp4` shows the kernel baseline on the left and
this prototype on the right. Both captures use the same 600 joystick inputs,
without guest patches, and run from tick 431 to 1033 with pellet count 3 to 73.
Reading the wrapping counter at frame boundaries confirms **149 scheduled
protected updates** during this actual VICE playthrough. The additional
code-breakpoint probes were inconclusive and are excluded from the timing
claims; the counter establishes coverage, while scan avoidance is checked
by the simulator tests.
The raster output retains intermediate drawing and visible flicker; the video
is for review, rather than proof of a large improvement.

Local artifacts remain under ignored `build/raster-sync/`: saved binaries,
profiles, actor/raster traces, comparison video, phase-check observations,
regression log and VICE results. Early variants and diagnostic probes are
experimental artifacts, not validation claims about the final build.

```sh
make test
python3 tests/performance.py --output build/raster-sync/current-performance
python3 tests/flicker.py --output build/raster-sync/current-flicker
python3 tools/arcade/vice_check.py --maze-flash --output build/raster-sync/vice-validation
```

The hardware mechanism is described in
[Mäkelä's raster-synchronization article](https://codebase.c64.org/doku.php?id=interrupts:making_stable_raster_routines).
NTSC counter and display-origin details were also checked against VICE's
[register reads](https://github.com/VICE-Team/svn-mirror/blob/main/vice/src/vic20/vic-mem.c)
and [display-cycle implementation](https://github.com/VICE-Team/svn-mirror/blob/main/vice/src/vic20/vic-cycle.c).
These references establish the mechanism, rather than validate this build on
real hardware. Broader protection would require scheduling overlapping groups
and background work together, with a fresh CPU and memory budget.
