# Independent-actor commit trial

Item 1 of the [agreed experiments](IMPROVEMENT_AUDIT.md#agreed-next-experiments),
tested on 2026-11-03 and rejected after user visual review. Flicker appears
on either side at different moments, with no meaningful improvement overall.
The shorter measured actor windows also come with a throughput loss. The
trial remains a separate diagnostic target and is not retained in the default
game. Further flicker work was paused after that review.

A later user-requested [comparison at matched render ticks](RATE_MATCH.md)
received a positive visual review: "I think that is noticeably better. not
perfect, but better". Both archived programs completed 529 renders at
26.598 calls/s, with matching completed pictures and game states. This
supports a visible benefit at matched cadence; it does not resolve the
throughput penalty or promote this build into the default. Raster phase
remains an uncontrolled difference. The original measurements and rejection
below describe the earlier comparison at different render rates.

The subsequent [throughput trial](ACTOR_SPEED.md) retains current fonts and
raises natural active-capture rendering from 26.40 to 27.55 calls/s by
reducing group bookkeeping. It remains a separate `make run-actor-speed`
target; the normal game is unchanged. User review of that playable trial
found a possible improvement, less noticeable than in the initial
matched-cadence comparison. Its overall benefit remains inconclusive.

## Result

Fresh before/after native measurements use the same 180-frame scene setups.
The board-transition sample includes completion of pending rebuild work.

| Scene | Original renders/s | Trial renders/s | Original mean actor window, ms | Trial mean actor window, ms |
| --- | ---: | ---: | ---: | ---: |
| Opening play | 51.93 | 44.91 | 5.662 | 2.539 |
| Frightened | 54.61 | 48.60 | 5.030 | 3.007 |
| Attract chase | 43.65 | 38.52 | 6.585 | 6.146 |
| First intermission | 60.03 | 59.95 | 2.973 | 2.276 |
| Board transition | 41.86 | 42.01 | — | — |

Opening play's 95th-percentile actor window falls from 10.740 to 6.219 ms.
These windows measure `bitmap_erase` entry to the matching painter's return;
they are not exact VIC pixel-fetch timings. Opening play's maximum input and
audio service gaps increase from 27.56/26.58 to 31.40/31.06 ms.

The decisive check is a fresh **1,200-frame VICE capture with identical
joystick inputs**, covering chase and frightened play. Across the 19.889-second
counter interval, completed renderer calls fall from **30.92/s to 24.13/s**.
This longer sample is a different interval from the earlier six-second audit
that measured 33.42/s for the original. Neither capture rate is the opening
benchmark rate, and completed calls do not count unique movement poses.

The first implementation measured 31.27 renders/s in opening play. Inline
bounds preparation, direct singleton kernel calls and avoiding duplicate
dirty propagation recover throughput to 44.91, but the remaining loss still
exceeds the approximately 2 renders/s budget. Active play also falls below
30 calls/s. Do not promote this implementation based on the shorter windows.

## Implementation

`ACTOR_COMMIT` enables the trial in `src/sprites.S`. Each actor's bounds cover
old and new byte columns and whole colour rows. Connected components include
saved-underlay dependencies, including aligned sprites whose restore writes
an otherwise empty neighbouring column. Components preserve the original
restore order and reverse draw order, including final colour priority.

Actors affected by queued background tiles form the first transaction, with
their dependencies. Other components remain visible during that work. Each
remaining component is then erased and drawn before the next is erased.
Singletons enter the existing actor kernels directly. Full rebuilds and maze
flashing retain the original transaction path.

The background association still uses the existing conservative 32-pixel
bands; precise horizontal invalidation is item 2 and is now on hold with
the rest of the flicker work. Byte and colour-cell
dependencies also require more grouping than disjoint visible pixels alone.
Bounds construction, component merging and repeated transaction setup cost
more CPU time than the original single erase/background/draw transaction.

The resident image ends at `$7F35`, leaving 203 bytes in BLK1–3, versus 716
before: a cost of 513 resident bytes. Two extra zero-page bytes hold selection
and singleton state. Bounds reuse 24 unused odd cache slots; old footprint
coordinates reuse two unused bytes in each underlay record. BLK5 retains its
15 free bytes. The software stack, visible bitmap, conventional RAM target
and 16,875-cycle arcade timer are unchanged.

## Validation and artifacts

- `make test` passes all 48 default regression tests and the frontend smoke
  run. The default PRG is byte-identical to the archived original, SHA-256
  `8e62f44052d280cf63674878c362ba72493d8e5aeba55363913e5cc5cf99b621`.
- `make test-actor-commit` passes the 15 arcade reference tests, 16 native and
  renderer checks, and the frontend smoke run through all three intermissions.
  Checks cover separated actor ordering, disjoint pixels sharing restore
  bytes, old/new crossings, colour-only dependencies, transitive clusters,
  clipping, dirty tiles, loader output and final underlay restoration.
- Both VICE captures verify all 33,792 depacked program bytes before startup.
  The trial's `commit_group` checkpoint executes 1,551 times during recording.
  The trial PRG SHA-256 is
  `3c4cf04b05a1c70df8ffd23a68a5be69c54644a5fc4b1f1cb55c856f3acc1d42`.

[Watch the labelled raster comparison, original left and trial right](../build/actor-commit/vice/vic20-actor-commits-8e62f440-vs-3c4cf04b.mp4).
The video is silent. Pixel snapshots alone do not establish a visible flicker
benefit, and physical hardware has not been tested.

Compact results are frozen in [the baseline record](baselines/actor-commit.json).
Immutable before binaries, native profiles, actor traces, replay inputs,
loaded-image checks and capture manifests remain under `build/actor-commit/`.

```sh
make run-actor-commit
make test-actor-commit
python3 tests/performance.py --prg build/actor-commit/after/pacman.prg --output build/actor-commit/recheck/performance
python3 tests/flicker.py --prg build/actor-commit/after/pacman.prg --output build/actor-commit/recheck/flicker
```
