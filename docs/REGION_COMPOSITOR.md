# Rejected region-compositor experiment

**Reverted at the user's request after visual review found little difference.**
At reversion, the renderer was restored to commit `cf81d64`, including its accepted
stationary-actor flicker reduction and startup memory reuse. BLK1–3 again had
371 bytes free; BLK5 had 15. The subsequent
[generic sprite-kernel pass](SPRITE_KERNELS.md) brings BLK1–3 headroom to 391
bytes within the same hardware configuration.

The experiment composed eligible updates in Pac-Man's usual slot directly from
its existing 24-byte background underlay. It avoided erasing those updates, but
required the same displayed row and bitmap columns, no conflicting background
writes, and isolation from other dirty actors. Larger movements and overlaps
continued through the original renderer.

Only **12 of 478 actor paint entries (about 2.5%)** used this path in the
normal-play sample. The limited coverage produced little visible improvement.
The extra code consumed 230 resident bytes and slightly slowed the attract
scene. This result does not justify retaining the renderer change.

| Sample | Original renders/s | Rejected experiment | Composed updates |
| --- | ---: | ---: | ---: |
| Normal play | 49.64 | 49.65 | 12 |
| Frightened | 54.00 | 53.67 | 15 |
| Attract chase | 42.91 | 41.65 | 0 |
| First intermission | 60.15 | 60.25 | 45 |

The experimental implementation passed 49 regression tests and VICE checks.
Those results established correctness, not a worthwhile visual improvement.
The restored checkpoint had the preceding 46-test suite; the three experiment-only
renderer tests and composition-specific observer changes were removed with it.
After restoration, all 46 tests and the frontend smoke run pass. The rebuilt
PRG and native image are byte-identical to the saved pre-experiment build.
The [archived measurement record](baselines/region-compositor.json) describes
the rejected executable, rather than the current build.

Broader prototypes also failed to justify their cost. Multi-actor isolation and
band bookkeeping reduced normal throughput to roughly 43–47 FPS. One-row
underlay sliding and rotating candidate selection measured 49.01 and 48.37 FPS,
with larger frightened-mode losses. These variants remain discarded.

Local evidence stays under ignored `build/region-compositor/`: the comparison
video (before left, experiment right), matching joystick input records, timing
reports and validation logs. `rejected/` preserves the exact experimental source
and binaries. Future work can use this evidence to avoid repeating the same
limited approach.

The next retained change is faster common sprite drawing, targeting shorter
erase-to-redraw gaps across more moving actors. See [SPRITE_KERNELS.md](SPRITE_KERNELS.md).
Score readability remains queued.
