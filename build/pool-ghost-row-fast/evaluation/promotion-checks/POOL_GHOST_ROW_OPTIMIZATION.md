# Normal-ghost row control

**Trial ready for live review, 2026-11-04.** Actual VICE throughput improves
**33.75 → 33.85 redraws/s**, about **0.3%**, on the saved route. The accepted
shift build remains standard. This is a small CPU saving; partial poses and
uneven pacing remain.

The accepted [accumulator-shift build](POOL_SHIFT_OPTIMIZATION.md) is now the
default, at **33.75 actual VICE redraws/s**. This separate trial targets the
normal-ghost stamper's row counter, preserving its existing masks, movement,
destination allocation and completed-glyph publication.

```sh
make run-pool-ghost-row-fast
```

Press **5**, then **1**; use the arrow keys. `make run` and
`make run-pool-shift-fast` retain the accepted comparison build. This trial
requires live review before promotion.

## Opportunity and contract

The accepted build's unmodified native replay spends **2.52% of CPU time**
in the normal-ghost stamper: **942 calls**, or **760.00 exclusive cycles per
redraw**. Each call draws ten pre-shifted ink rows between two transparent
rows. The source index already advances or retreats through those ten rows,
but the old loop also decrements a separate zero-page counter.

`POOL_GHOST_ROW_FAST` replaces that decrement with an immediate source-index
comparison. The forward path runs X=0…9 and stops at 10; the reverse path
runs X=9…0 and stops at 255. Existing self-modified `INX`/`DEX` selection stays
in place; a second immediate operand holds the selected end index. Y carries
that end index during setup, then resumes its destination-row role.

Entry remains X=twice the pre-shifted source selection, `v_flip` bit 0 for
vertical reversal, and the existing row/destination scratch. A/X/Y, flags and
scratch are clobbered as before. No extra writable state, lookup data, IRQ
work or hardware is introduced. The main-thread renderer owns both patched
operands; the old counter remains available behind the build conditional.

Replacing `DEC zp` (five cycles) with `CPX #imm` (two) saves **30 cycles**
over ten rows. Added setup costs one cycle forward and three reverse, for
**29/27 cycles saved per call** before placement effects. This trace contains
942 forward calls and no reversed normal ghosts, giving an estimated
**27,318 cycles**, **40.41 cycles/redraw**, or **0.13% of total CPU** from row
control alone. That estimate is not a frame-rate prediction; boundary tests
also exercise reversed rows.

## Linked placement

Two explicit unused bytes after RTS put the 32-byte source-pointer table at
**$2F00** instead of $2EFB. Its indexed loads then avoid the predecessor's
0–2 page-crossing cycles per call. The row branch stays in one page: target
**$2ED3**, branch fallthrough **$2EFD**. The epoch-clear branch also retains its
page. Routine plus padding grows **90 → 95 bytes**, absorbed by existing
layout slack.

A first alignment-directive draft was rejected before profiling. `.p2align 5`
raised the entire input section's alignment, causing linker reordering and
reducing resident headroom by 32 bytes. Two explicit bytes preserve the
original section placement. The rejected binary/map and interrupted test log
are under `build/pool-ghost-row-fast/evaluation/rejected-section-alignment/`;
no speed or correctness result is claimed for that draft.

The linked final trial retains **141 resident bytes**, **23 BLK5 bytes** and
the full **704-byte software stack**. Hardware remains NTSC with +3K and
BLK1/2/3/5 RAM expansion; the 16,875-cycle arcade tick remains unchanged.

## Results

| Measurement | Accepted sprite shifts | Ghost-row trial |
| --- | ---: | ---: |
| Actual VICE completed redraws | 660 | **662** |
| Actual VICE redraws/s | 33.75 | **33.85** |
| Actual 95th-percentile redraw interval | **45.07 ms** | 45.69 ms |
| Actual maximum redraw interval | 54.20 ms | **54.17 ms** |
| Native completed redraws | 676 | **678** |
| Native redraws/s | 33.94 | **34.04** |
| Mean full native refresh, cycles | 15,331.14 | **15,290.78** |
| Native 95th-percentile refresh, cycles | **20,142** | 20,324 |
| Native maximum refresh, cycles | **27,061** | 27,777 |
| Normal-ghost exclusive cycles/native redraw | 760.00 | **716.50** |
| Maximum native input-service gap | **35.95 ms** | 40.73 ms |
| Maximum native audio-service gap | **34.58 ms** | 35.11 ms |
| Resident end / free before stack | $7CB3 / 141 bytes | $7CB3 / 141 bytes |
| BLK5 end / free | $BFE9 / 23 bytes | $BFE9 / 23 bytes |
| Packed PRG bytes | 26,838 | 26,840 |

The native image remains **33,792 bytes**. Native and actual VICE rates are
separate measurements. Different redraw cadences sample different poses;
per-redraw native means do not isolate instruction savings. The identical-input
kernels below provide that proof. This single saved route does not establish a
fixed 30 Hz deadline, a perceptible smoothness improvement or less flicker.

## Correctness and display evidence

The new independent per-pixel oracle checks **1,024 normal-ghost cases per
build**: both body phases, eight horizontal shifts, four flips and all sixteen
glyph-row offsets. Nonzero backgrounds and adjacent guards catch extra or
missing writes. At row offsets 0–5, unreachable bottom pointers deliberately
point to guards. Every case saves **27–31 cycles**, exactly the predicted
29/27 row-control saving plus the predecessor's 0–2 pointer page crossings.
Mean kernel cost falls **552.56 → 522.88 cycles**. All outputs match.

All **8,768 complete-scene cases per build** match the independent pixel,
colour, background, retained-input and restoration oracle. **180 cases save
27–31 cycles; 8,588 are unchanged; none are slower.** Mean transaction cost
falls **2,556.09 → 2,555.49 cycles**. Actor preparation and destination setup
have identical exclusive totals. All **10,496 generic-stamper cases per build**
also match, with identical cycle counts and poisoned unused bottom pointers.

The trial passes **69 unit checks** (15 original-ROM, 41 pooled, 13 display
classifier). All **1,207 active game states** and **1,639 sound-state/VIC-register
ticks** match the accepted build. Smoke covers all three intermissions and
**7,192 logical ticks**; boot handoff, IRQ vector and stack guard pass. The
observed software/hardware stack use is 30/24 bytes, not a worst-case bound.
Smoke forces intermission levels rather than playing every board unaided.
Exact sound-register replay does not test write-time identity or physical sound.

Both actual VICE captures contain **1,180 consecutive lossless raster frames**
on the same logical-tick joystick trace. Both loaded images match their own
33,792-byte executable. No guest code is patched, and no clock, render gate or
pose timing is altered. The accepted capture is reused only after matching its
PRG/native/label identities; the new capture has **789 different raw frames**
at the same indices.

The trial classifier passes **639 settled-picture checks** and **5,186 synthetic
host controls** (2,593 absent and 2,593 partial), with no false absent/partial
settled results. No eligible actor is classified as fully absent. Remaining
present/partial/excluded counts are:

| Actor | Accepted shifts | Ghost-row trial |
| --- | ---: | ---: |
| Pac-Man | 989 / 17 / 174 | 979 / 27 / 174 |
| Blinky | 888 / 7 / 285 | 883 / 17 / 280 |
| Pinky | 842 / 9 / 329 | 832 / 17 / 331 |
| Inky | 927 / 19 / 234 | 925 / 16 / 239 |
| Clyde | 870 / 6 / 304 | 872 / 9 / 299 |

Exclusions include shared colour, reward expansion, clipping, hidden actors
and insufficient distinct ink. Several partial counts grow; visible-ink colour
mismatches also vary (Clyde 3→4, Blinky 3→2, Inky 8→5). The average gain and the
worse native service gaps/partial counts are all part of this trial's tradeoff.
The accepted appearance, artwork and tick-indexed game behavior remain intact.

The [comparison preview](../build/pool-ghost-row-fast/evaluation/comparison.png)
and [consecutive-frame evidence](../build/pool-ghost-row-fast/evaluation/trial-vice/evidence.png)
were visually inspected. The evidence shows Pac-Man present/partial/present
at frames **29/30/31**. The [comparison video](../build/pool-ghost-row-fast/evaluation/glyph-pool-comparison.mp4)
labels both executable hashes and uses natural cadence without audio.

The [frozen record](baselines/pool-ghost-row-fast.json) retains compact results,
identities, source hashes and evidence hashes. The trial stays separate pending
live review. The shift [promotion record](baselines/pool-shift-promotion.json)
identifies the accepted default and its full `make test` result.

## Reproduction

```sh
make test-pool-ghost-row-fast
python3 tools/arcade/profile_game.py --prg build/pool-ghost-row-fast/pacman.prg --map build/pool-ghost-row-fast/pacman.map --input tests/fixtures/active-replay.json --output build/pool-ghost-row-fast/new-cpu
python3 tools/arcade/pool_profile.py --capture build/pool-ghost-row-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-ghost-row-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/pool-ghost-row-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/pool-ghost-row-fast/new-vice
```

Run native tools sequentially and use fresh capture directories. Evidence
belongs under `build/pool-ghost-row-fast/evaluation/`. Persistent display
caching and pacing remain deferred.
