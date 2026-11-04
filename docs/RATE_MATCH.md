# Rendering comparison at matched logical ticks

Diagnostic trial on 2026-11-03, following the proposal in
[Response to IDEAS_REPLY.md.md](Response%20to%20IDEAS_REPLY.md.md).
The comparison controls render cadence and displayed logical poses before
considering another renderer. It uses the archived original and
[independent-actor commit trial](ACTOR_COMMIT.md), both from before the
accepted font changes.

[Watch the roughly 20-second comparison](../build/rate-match/active-1200/vic20-rate-matched-actor-commit.mp4):
baseline on the left, actor-commit on the right. The video is silent and
labels both program hashes and the timing limitation.

## Result and what it establishes

Both programs complete **529 renders at 26.598 calls/s** in the same
19.889-second counter interval. Their completed render-tick sequences and
completed bitmap/foreground-colour hashes match. **1,207 active-play input
and game-state observations match**, with zero recorded logic or completed
picture mismatches.

| Check | Baseline with controlled render admissions | Actor-commit reference |
| --- | ---: | ---: |
| Captured VIC frames | 1,200 | 1,200 |
| First/last sampled logical tick | 432 / 1638 | 432 / 1638 |
| Completed calls in the capture counter interval | 529 | 529 |
| Completed calls per second | 26.598 | 26.598 |
| Compared completed render ticks | 434–1637 | 434–1637 |

The 528 intervals between completed render admissions contain 120 one-tick,
180 two-tick, 191 three-tick, 35 four-tick, and two five-tick steps on each
side. Those counts describe logical render admissions, not exact
pixel-fetch or display-completion intervals.

This removes the large render-rate difference from the earlier comparison.
It establishes a useful visual comparison with matching completed poses.

**User visual review:** "I think that is noticeably better. not perfect, but
better" — referring to the actor-commit side of this comparison. This is a
positive perceptual result at matched cadence, unlike the earlier comparison
in which the original ran faster. It supports the hypothesis that shorter
erase gaps help and that the earlier throughput loss could obscure that
benefit. Raster phase still differs, so this does not isolate erase-gap
duration as the sole cause or conclusively establish H2.

Missing actors remain visible at some moments. No automatic blink
classification is claimed. The next technical target is to retain the
observed visual benefit while recovering throughput. This review does not
establish that the slower actor-commit build improves on the full-speed
current game; the default build remains unchanged.

The rate is specific to this new input trace, which is indexed by logical
tick. It is not a remeasurement of the archived video that reported 24.13
calls/s, nor a measurement of the current font build.

## How the trial works

The [capture script](../tools/arcade/rate_match.py) first runs the archived
actor-commit program naturally in VICE with +3K and BLK1/2/3/5 expansion,
NTSC timing, and the original 16,875-cycle game clock. An external controller
applies joystick inputs immediately after `frame_wait`, before controls
are sampled. It records inputs by logical tick, main-loop render admissions,
completed pictures, and raster output.

The baseline then receives the same input trace. After each audio update,
the VICE monitor redirects the CPU program counter either to the existing
refresh call or to the existing loop jump. This admits refreshes on the
reference's completed render ticks and skips extra refresh opportunities.
It bypasses the baseline's usual render-eligibility checks during the active
sample. This is deliberate diagnostic control of execution, not an ordinary
unmodified-play benchmark or a standalone throttled game build.

No guest code bytes are patched and no guest RAM log buffer is allocated.
The monitor records state externally. Full logical screen, colour, arcade
RAM, relocated flags, and RNG-state hashes are compared before controls.
At completed renders, the 3,136-byte bitmap and 196 foreground-colour nibbles
are compared.

All 2,400 sampled images come from VICE's actual raster buffer at line 1,
cycle less than 8, using the existing capture approach. Capture does not
wait for a completed game picture. The video therefore retains visible
intermediate erases, paints, and colour changes.

**Raster phase and renderer completion times are not matched.** Matching
logical render ticks does not match the precise time each actor changes on
screen. That is a remaining confound when judging the size of any benefit.
The trial also does not measure input/audio service gaps or count absent
actors automatically.

## Validation and reproduction

Before each run, VICE's 33,792 depacked program bytes are compared against an
independent execution of that PRG's loader. Archived input hashes are:

- Baseline: `8e62f44052d280cf63674878c362ba72493d8e5aeba55363913e5cc5cf99b621`.
- Actor-commit: `3c4cf04b05a1c70df8ffd23a68a5be69c54644a5fc4b1f1cb55c856f3acc1d42`.

A 60-frame pilot passed before the longer capture. The final script checks
render-tick sequences, completed pictures, active inputs/states, and the
capture raster window, and exits unsuccessfully if those matching checks
fail. Python syntax validation also passes. Game sources and the Makefile
were not changed, so no game rebuild was needed for this diagnostic.

The normal `make run` PRG retains its pre-trial hash:
`eb6b29810453418818a1ffb83f8b0057464a903682c20970cc6019617067a4e9`.

```sh
python3 tools/arcade/rate_match.py --frames 1200 --output build/rate-match/active-1200
```

The command requires the archived PRG/label pairs, installed VICE and ROMs,
a working display, Pillow, and the existing FFmpeg setup. Use `--baseline`
and `--trial` to supply other archived pairs. `--reuse` rebuilds the report
and labelled comparison from an existing capture.

Raw input/state records, per-render hashes and raster positions, loaded-image
checks, PRG snapshots, captures, and the detailed summary remain under
`build/rate-match/active-1200/`. A compact result is retained in
[the baseline record](baselines/rate-match.json).
