# Playable raster-priority review

**Rejected after user visual review on 2026-11-04:** "I don't think it's
noticeably better and there is a slight performance hit. I guess give up
on this." Further work on raster-priority scheduling stops. The trials
remain separate diagnostic targets for reproduction; the normal renderer
remains accepted. This review does not establish which individual variants
were played, so no separate verdict is assigned to the opportunistic mode.

User-requested revisit on 2026-11-04. The earlier comparison may have been
reviewed only as video, so these are standalone programs for direct play.
All use the current lettering, horizontal rewards, frightened ghosts and
revised Pac-Man artwork. The rejected experiments are described below.

Reproduce the player-priority trial:

```sh
make run-beam-priority
```

Use arrows to move, **5** to insert a coin and **1** to start. Close VICE
before launching another version. The other choices are:

| Command | Behaviour |
| --- | --- |
| `make run` | Normal accepted renderer |
| `make run-beam-review` | Earlier all-group raster scheduler, rebuilt with current artwork |
| `make run-beam-priority` | Wait for Pac-Man's group first; protect nearby ghosts where eligible |
| `make run-beam-opportunistic` | Same focus selection, using only windows already open; otherwise draw immediately |

## What priority means

The strict trial gives the group containing Pac-Man first choice of a safe
raster window. It identifies him from the renderer's cached palette in
output slot 10 or 2, following the arcade's frightened-mode priority swap.
The priority applies when that group needs repainting.

Ghosts within **24 native pixels horizontally and 32 vertically** of Pac-Man
also qualify for raster protection. This is a rectangular neighbourhood,
not a maze-path distance or a nearest-first sort. Distant independent groups
are restored and painted immediately without raster waits. A distant actor
that shares an overlapping component with a focused actor stays in that
component; it cannot safely be separated just to change scheduling priority.

Within a component, the original erase, paint and shared-cell colour order
is preserved. Whole colour rows and both old and new footprints determine
the safe window. No game rules, ghost decisions or movement masks change.
The 16,875-cycle arcade clock stays intact. Presentation waits can still
delay real-time input and audio service.

Both focused versions retain the earlier scheduler's limitations:

- Refreshes with queued pellet/score background changes use the original
  transaction. Those refreshes do not receive focus protection.
- Full rebuilds, completion flashing and components too large for a safe
  window also use unprotected drawing.
- The opportunistic version additionally falls back whenever a focused
  component's window is closed. It never polls waiting for that window.

Thus neither version guarantees that Pac-Man or nearby ghosts never blink.
The user found no noticeable improvement to justify the performance cost.

## Actual-play capture measurements

Fresh VICE NTSC recordings replay the same joystick inputs indexed by logical
tick. Each contains 600 raster frames; the counter interval is 9.936 seconds.
No guest code or program counter is patched. Every launched program's 33,792
depacked bytes are checked before startup.

| Program | Completed redraws | Completed redraws/s |
| --- | ---: | ---: |
| Normal renderer | 325 | 32.71 |
| All-group raster review | 228 | 22.95 |
| Strict player priority | 226 | 22.75 |
| Opportunistic player priority | 233 | 23.45 |

These count renderer completions, not unique movement poses. All four runs
have 603 matching active input/game-state observations. Their completed
bitmap/foreground-colour pictures match the normal renderer at every common
completed tick: 147, 138 and 142 pictures for the three trials respectively.
Render cadence and raster phase vary naturally; the videos do not align
intermediate poses frame for frame.

**Priority has not recovered the normal renderer's speed.** Removing polling
waits helps only slightly in this sample. All three trials remain below the
user's earlier 30 FPS threshold. They were provided for direct play testing
and are now rejected after user review. No visible flicker reduction has
been established for these versions.

The recordings, immutable launched PRGs, inputs, per-render checks and summary
are under `build/beam-priority/replay/`. Program SHA-256 prefixes are
`9fb85cf6` (normal), `79299dc4` (all-group), `afe8e2b0` (strict), and
`a4d1ced4` (opportunistic). The normal PRG remains byte-identical to the saved
pre-trial game.

## Memory and validation

The conventional +3K and BLK1/2/3/5 expansion configuration is unchanged.
The current artwork does not fit with the old scheduler's original resident
placement. [beam_priority.ld](../src/beam_priority.ld) therefore places bounds
and grouping helpers in `$1D90–$1F7F`, copied from temporary boot storage.
The software stack reserves `$1F80–$1FFF` (128 bytes). Linker assertions bound
the code, initializer and stack. This is a different placement from the
archived beam executable, with the same drawing algorithm in the reference.

The strict helper uses 490 bytes and ends at `$1F7A` exclusive. Its resident
image ends at `$7FFC`; the opportunistic resident image ends at `$7FFF`.
All three long smoke runs exercise fruit and all three intermissions, check
the lower stack guard and IRQ vector, and compare the copied helper after
each scene. Observed software stack use is 32 bytes; this is workload evidence,
not a formal maximum-depth proof.

Validation includes the full pixel/colour oracle, revised Pac-Man masks,
overlap/clipping/restoration, live background edits, rewards, original-ROM
movement/frightened-state parity, focus boundaries, both Pac-Man slots, and
player-first scheduling. Each variant runs 1,179 phase fixtures across all
131 raster-register phases, including five-actor protected components and
six-actor fallbacks. Every protected erase/draw interval must remain outside
the affected colour rows and within budget. Opportunistic protection covers
719 fixture groups, strict priority covers 1,179, and the all-group reference
covers 1,310. These are group counts across 1,179 refresh calls per variant.

Actual VICE checks also observe complete protected transactions, rather than
only checking the entry raster position. These checks establish the limited
timing protection, not a perceptual result. Physical hardware is untested.

```sh
make test-beam-priority
python3 tests/beam_priority.py --prg build/beam-priority/focused/pacman.prg
python3 tests/beam_priority.py --prg build/beam-priority/reference/pacman.prg
python3 tools/arcade/check_beam.py --prg build/beam-priority/strict/pacman.prg --output build/beam-priority/strict/window-check
```

The recorder defaults to the retained logical input trace from the earlier
matched-cadence experiment; `--input` can select another recording. Reproduce
each mode with `python3 tools/arcade/record_beam_priority.py --mode MODE`, then
use `--summarize` to check common states/pictures and report actual capture
rates. The static scheduler cycle annotation is under
`build/beam-priority/focused/scheduler-cycles.txt`; full transaction budgets
are checked against measured emulated execution.
