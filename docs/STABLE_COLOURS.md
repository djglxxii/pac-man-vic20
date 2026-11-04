# Stable colour publication trial

Implemented 2026-11-04 after `ae55528`, following the user's observation that
stationary fruit and shared walls flash between red and white. The general rule
is **background colour has lowest priority; actors retain existing priority**.
White actors still have actor priority. There are no fruit-specific rules.

**Status: stopped at the user's request; trial not accepted.** Subsequent live
play testing accepted the separate [glyph-pool renderer](GLYPH_POOL.md), which
is now the default. The default/throughput references below describe this
earlier colour trial and its underlay baseline. The
user still sees walls/fruit flash between white and actor colour. The focused
recorded metric improves, at an actual-capture throughput cost of about 9.5%,
but that does not establish a worthwhile visual result. The trial falls below
the earlier 30 FPS play-test preference and approximately 33 redraws/s target.
It remains archived for reproduction; the accepted default has not been replaced.
The user asked to return to the other agent's [original ideas](IDEAS.md).

```sh
make run-stable-colours
```

`make run` launches the accepted game. Both retain the existing controls, arcade
behaviour, 16,875-cycle clock, NTSC timing and +3K plus BLK1/2/3/5 configuration.
No additional hardware is required. Verification covers VICE NTSC and the native
simulator; physical hardware and PAL have not been tested.

## Confirmed cause and implementation

The existing renderer already gives actors colour priority in its completed
picture. During redraw it restores saved colours, paints background edits,
then actors. The VIC can scan the intervening white/lower-priority colours.

The retained 1,200-frame VICE capture contains **634 fruit-cell cases** with
red before redraw, white at paint entry and red after repainting. All cells
combined have 7,575 unchanged-final-colour cases with a paint-entry mismatch.
These are phase observations, not counts of perceived blinks. Stationary actors
can be dirtied by nearby actors and conservative background invalidation.

The trial composes colours in unused onboard colour RAM **$9400–$94C3**.
Restoration, background painting, underlay saves and actor painting use that
work page, preserving layer order and background data. A small assembly routine
publishes resolved values to displayed colour RAM **$9600–$96C3** afterwards.

Ordinary refreshes publish old/new actor rectangles plus a short background-cell
list. Identical rectangles are copied once; duplicate stores contain the same
final colour. There are no pixel searches, new actor priorities or raster waits.
The 16-entry background list uses a full 196-cell copy on overflow. Rebuild
clears and maze flashes also use that fallback. Explicit actor removal publishes
the restored background. Actor-free pellets stay white; shared walls/pellets
take their actor's colour. Blue/white completion flashing remains intact.

Unspecified colour-RAM read bits 4–7 are harmless here: work values are saved,
restored or copied into colour RAM, whose stores ignore the upper bits. They
are never used as indices or priorities. A test supplies noisy upper bits.

A first full-copy implementation measured only 27.46 native redraws/s. Limiting
publication to affected cells reached 28.53/s; avoiding duplicate rectangles and
specialising ordinary unclipped rectangles reaches 29.59/s. Earlier binaries
remain archived locally as diagnostics, not the final trial.

## Memory

| Resource | Trial allocation |
| --- | --- |
| Work colours | 196 onboard nibbles at $9400–$94C3 |
| Background queue | 16 bytes at $0300–$030F |
| Previous actor rectangles | Previously unused underlay bytes 4 and 6 |
| Publication state | Two bytes at $7FFE–$7FFF |
| Resident code/data | Ends at $8000: **zero BLK1–3 headroom** |
| BLK5 headroom | 15 bytes, unchanged |
| Software stack | Entire $1D40–$1FFF reservation retained: 704 bytes |

$0300–$030F contains BASIC vectors unused by the running game. The live IRQ
vector at $0314 and NMI vector at $0318 remain untouched. The game does not
return to BASIC or call BASIC/KERNAL services beyond its existing IRQ entry.
The linker bounds this queue; no stack memory is borrowed. Additional resident
code would require a separate memory decision.

## Measured results

Same logical-tick joystick route, uninstrumented PRGs and natural rendering
admission. Fresh baseline/trial VICE captures each contain 1,200 consecutive
lossless raster frames. No PC gating or runtime patching; raster phases are not
forced to align. Completed redraws are not unique motion poses.

| Measurement | Accepted baseline | Trial |
| --- | ---: | ---: |
| Actual VICE completed redraws/s | 32.88 | 29.77 |
| Redraws in capture counter interval | 654 | 592 |
| Redraw interval p95 / max | 51.08 / 65.81 ms | 54.60 / 68.07 ms |
| Native replay completed redraws/s | 32.94 | 29.59 |
| Mean native refresh cost | 12,186 cycles | 13,656 cycles |
| Native unchanged-final cell colour round trips | 7,437 | **0** |
| VICE fruit-cell paint-entry colour mismatches | 634 | **0** |
| Eligible fruit frames with white wall ink | 74 / 548 | **0 / 549** |
| Expected-colour wall samples / total | 37,133 / 40,874 | **40,818 / 40,818** |
| Native maximum input-service gap | 38.51 ms | 39.25 ms |
| Native maximum audio-service gap | 35.18 ms | 35.66 ms |

The native audit logs physical colour stores within complete refreshes. A round
trip means initial/final colour agree but intermediate stores assign another
colour. Native timestamps identify instruction starts, not exact bus phases.

The RGB audit samples persistent background ink in stationary-fruit-owned cells,
excluding all other actors' whole colour cells. Coverage differs slightly;
these are focused route measurements, not a whole-game guarantee. The retained
baseline had the same 74/548 frame count with 3,766 white pixels; the fresh one
has 3,741. Natural raster phase affects the exact pixel count. Other actor colour
interactions have independent renderer tests and native write coverage, rather
than this particular RGB classifier.

**Bitmap erasure still happens.** Pac-Man is absent in 166/1,200 trial frames
(181 excluded), versus 165/1,200 retained baseline frames (179 excluded). This
does not establish less actor disappearance. Red wall fragments can stay red
while the fruit's bitmap is temporarily absent. Colour pulsing and actor
disappearance remain separate measurements. Cells that genuinely change owners
still change colour; a newly drawn pose can retain the previous colour until
publication because bitmap and colour updates are separate.

Baseline PRG SHA-256:
`9fb85cf61add5d729142183a48285041a47e55fa0f0fd16043f0d15b2aae35af`.
Trial PRG SHA-256:
`82bc17d9d51494b849d1fa3e6c4447fc8da437f6c5c926166c7a9babd8e08627`.
See the [frozen record](baselines/stable-colours.json).

## Validation and review

- Accepted build: **52 regression checks** and whole-game smoke pass.
- Trial: **33 checks** pass: six native/ROM parity, ten independent renderer,
  six background-colour, three flash and eight rebuild tests.
- Trial smoke covers boot, attract, coin/start, fruit and all three intermissions;
  IRQ vector and stack guards remain intact. Observed software-stack writes
  occupy 32 bytes, not a proof of the maximum over every possible path.
- All **1,207 native active states** match the retained replay. VICE also verifies
  active states, loaded images and consecutive-frame spacing.
- Trial display analysis validates 554 settled snapshots and 2,229 identifiable
  settled actor cases, plus deliberate absent/partial controls. All nine
  display-classifier unit tests pass.

The native flash observer now reports actual publication after deferred colours
reach physical RAM; the old helper exit would report the previous colour.
Helper-only tests explicitly publish at their boundary. Live captures and smoke
exercise the actual renderer transaction.

Evidence under ignored `build/stable-colours/evaluation/`:

- `baseline-vice/`, `final-vice/`: frozen PRGs/labels, real PNGs and snapshots.
- `baseline-cpu/`, `final-cpu/`: profiles, colour writes and parity states.
- `fresh-baseline-colours.json`, `final-colours.json`: focused colour audits.
- [Comparison image](../build/stable-colours/evaluation/colour-comparison.png):
  real output at the same logical tick, with the fruit region enlarged.
- [Comparison video](../build/stable-colours/evaluation/colour-comparison.mp4):
  labelled natural raster frames, without render gating or substituted actors.

## User review and stopped follow-up

The user play-tested the trial and reported no noticeable improvement, with
walls/fruit still apparently alternating between white and actor colour. The
roughly **3.1 redraws/s loss** is therefore not justified by that review.
The user subsequently stopped this work. The remaining fruit question and the
possible ownership rewrite below are historical notes, not active tasks.

A follow-up audit of the recorded trial checks 554 settled active snapshots,
excluding borrowed reward-slot expansion. All 8,684 actor-owned cell observations
have the expected final colour. In 830 observations where fruit owns a cell,
none is white and there are no changes between consecutive fruit-owned samples.
The audit also finds 374 colour-to-white transitions when a cell is released to
the background and 39 when a white actor owns it. These are completed-state
observations, not proof that intermediate raster output or the user's specific
case is correct. See `build/stable-colours/review/ownership-audit.json`.

The previous focused metric excluded other actors' shared cells and cannot
explain all the reported flashing. Reproduce a cell turning white while it
remains owned, including whether stationary fruit does so without nearby actors,
before attributing the remaining effect to another cause. Cell entry/exit,
overlap, white actor states, colour/bitmap timing and actual bitmap disappearance
must be distinguished. Existing captures already prove bitmap disappearance.

The user's CPU expectation is reasonable: colour work should be tied to changes
in ownership, not repeated for every pixel redraw. This trial retains old colour
save/restore work and adds a publishing pass. It does not implement that saving.
A possible replacement would:

1. Keep colour state independent of bitmap underlays, retaining the resolved
   owner/colour while an actor moves within the same cells.
2. Reconsider colours only for cells entered or vacated, an actor's actual colour
   change, or a background edit. Resolve overlapping actors in existing priority.
3. Restore background colour when the last actor leaves, preserve white actors
   and frightened flashing, and coordinate changes with the displayed pose.
4. Remove superseded colour saves/restores and the added publication pass.
   Budget ownership checks and memory, then measure the complete replacement
   against the accepted renderer before claiming a cycle saving.

This is an unimplemented, stopped candidate, not evidence that another ownership
rewrite will solve the user's visual complaint. Both designs can have the same
final colours. The default remains unchanged. Work returns to the original
glyph-pool idea's memory/capacity audit before any benchmark implementation.

```sh
make test-stable-colours
python3 tools/arcade/profile_game.py --prg build/stable-colours/pacman.prg \
  --map build/stable-colours/pacman.map --colour-writes --output build/stable-colours/new-cpu
python3 tools/arcade/measure_display.py --prg build/stable-colours/pacman.prg \
  --output build/stable-colours/new-vice --frames 1200
python3 tools/arcade/analyze_colours.py --capture build/stable-colours/new-vice \
  --cpu build/stable-colours/new-cpu --output build/stable-colours/new-colours.json
python3 tools/arcade/analyze_display.py --capture build/stable-colours/new-vice
```
