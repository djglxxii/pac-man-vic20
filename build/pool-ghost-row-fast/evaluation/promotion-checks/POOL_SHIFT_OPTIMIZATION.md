# Accumulator-first sprite shifts

**Accepted and promoted to default, 2026-11-04.** Actual VICE throughput improves
**33.64 → 33.75 redraws/s**, about **0.3%**, on the saved route. The accepted
shift version is now standard at the user’s request. This experiment changes
only five generic sprite shift kernels.

```sh
make run-pool-shift-fast
```

Press **5**, then **1**, and use the arrow keys. `make run` launches this
accepted version; `make run-pool-dest-fast` preserves its predecessor. The
[promotion record](baselines/pool-shift-promotion.json) identifies the default
artifacts and full regression checks.

## Measured opportunity and contract

The preceding destination-setup build's unmodified native replay puts generic stamping at
**11.33% of CPU time**, including **3.06%** in shift kernels. Five kernel
entries execute 14,688 times over 673 redraws. Saving three cycles each would
remove 44,064 cycles, about **0.22% of total CPU**, or **65.47 cycles/redraw**
on that exact instruction trace. This is an opportunity estimate, not a
whole-game frame-rate prediction.

For shifts 1, 2, 3, 6 and 7, the old first operation stores the source byte,
then shifts that zero-page byte. `POOL_SHIFT_FAST` performs the first shift
in A, then stores the shifted half. `STA` and `LDA #0` preserve the carry
needed by the following `ROR` or `ROL`. The resulting halves and the remaining
merge operations are identical. This removes three cycles and one byte from
each affected nonempty row path. Empty rows and shifts 0, 4 and 5 retain their
kernels. Flips, destination allocation, background copying, colour order,
publication, arcade logic and sound retain their code paths.

The contract is unchanged: source byte in A; the selected shift produces the
same halves in A and existing `v_hi` / `v_lo` scratch before merging. A and
flags are clobbered as before, X/Y are preserved by each shift kernel, and
self-modified operands remain owned by the main-thread renderer. No new
state, lookup table, IRQ work or hardware is added. The old instructions
remain behind the build conditional.

Static cycle annotations using the linked zero-page symbols confirm the
shift-1 sequence falls from **15 to 12 cycles**, and **10 to 9 code bytes**.
The same first-operation saving applies to the other four paths. Linked
page placement and complete execution still require emulator checks.

## Results

| Measurement | Accepted destination setup | Shift trial |
| --- | ---: | ---: |
| Actual VICE completed redraws | 658 | **660** |
| Actual VICE redraws/s | 33.64 | **33.75** |
| Actual 95th-percentile redraw interval | 45.44 ms | **45.07 ms** |
| Actual maximum redraw interval | 61.51 ms | **54.20 ms** |
| Native completed redraws | 673 | **676** |
| Native redraws/s | 33.78 | **33.94** |
| Mean full native refresh, cycles | 15,418.37 | **15,331.14** |
| Native 95th-percentile refresh, cycles | 20,474 | **20,142** |
| Native maximum refresh, cycles | **24,543** | 27,061 |
| Generic composition exclusive cycles/native redraw | 3,429.58 | **3,362.96** |
| Shift kernels exclusive cycles/native redraw | 925.45 | **857.60** |
| Maximum native input-service gap | 37.34 ms | **35.95 ms** |
| Maximum native audio-service gap | 35.25 ms | **34.58 ms** |
| Generic stamper code bytes | 267 | **262** |
| Resident end / free before full stack | $7CB3 / 141 bytes | $7CB3 / 141 bytes |
| BLK5 free | 23 bytes | 23 bytes |
| Packed PRG bytes | **26,829** | 26,838 |

Alignment absorbs the five-byte reduction, leaving the same resident/BLK5
headroom and full **704-byte software stack**. No writable storage is added.
The native image remains 33,792 bytes. Hardware stays NTSC with +3K and
BLK1/2/3/5 expansion; the 16,875-cycle arcade clock is unchanged.

The smaller layout moves the normal-ghost source-pointer table from $2F00
to $2EFB. Some indexed pointer reads now cross a page, adding one or two
cycles to those ghost calls. The epoch-clear and normal-ghost row branches
remain within their pages. This placement cost is included in every reported
whole-scene and whole-game result; adding padding was not part of this trial.

The average gain is small. Different redraw cadences sample different poses;
per-redraw native averages do not isolate instruction savings. The larger
maximum native refresh remains a tradeoff, despite better input/audio gaps
and actual redraw intervals. This does not establish fixed 30 Hz pacing or
perceptible flicker reduction.

## Correctness and display evidence

All **10,496 generic-kernel cases per build** match the independent per-pixel
oracle with background/adjacent guards. The set includes every regular mask,
returning eyes, score halves, synthetic empty/dense/narrow masks, all eight
shifts, four flips and glyph-row offsets 0/4/5/15. Unused bottom pointers at
row offsets 0/4 deliberately point at guards. Every measured saving is exactly
three times the number of nonempty source rows for the five changed shifts,
and zero otherwise: **6,080 cases faster, 4,416 unchanged**, none slower.

All **8,768 complete sprite scenes per build** also match the independent
pixel/colour/background oracle, retained actor inputs and identical output
digest `1c8e70e6e820b3f41d989da46703592dc0bd8d6adb36a322fa4eaf5ab8b9140d`.
Mean transaction cost falls **2,567.10 → 2,556.09 cycles**. There are **3,637
faster, 4,997 unchanged and 134 slower** scenes. The slower normal-ghost scenes
cost 1–2 additional cycles from the pointer-table page crossings above;
faster scenes save up to 36 cycles. Actor preparation and destination setup
have identical exclusive totals.

The trial passes 15 original-ROM checks, 41 pooled logic/render/colour/font/
memory checks and 13 display-classifier checks. All **1,207 active game
states** and **1,639 sound-state/VIC-register ticks** match the accepted build.
Smoke covers all three intermissions and **7,192 logical ticks**; boot handoff,
IRQ vector, stack guard and stack reservation pass. Observed software/hardware
stack writes use 30/24 bytes; these are sample observations, not upper bounds.
Smoke forces intermission levels rather than playing every board unaided.
Exact tick-indexed register values do not prove identical audio write times
or replace listening/physical-hardware testing.

Both real VICE captures contain **1,180 consecutive raster frames** over the
same approximately 19.557-second window. Input trace hashes match, and all
33,792 depacked bytes match each capture's own executable. The accepted
capture is reused after verifying PRG/native/label identities. There are
**907 differing same-index raw frames**. No guest patches, render gates,
clock changes or pose retiming are used.

The trial passes **637 settled-picture checks** and **5,154 synthetic
absent/partial controls**, with zero false absent/partial results on settled
images. No eligible fully absent actor is found. Partial poses remain:

| Actor | Accepted present / partial / excluded | Trial present / partial / excluded |
| --- | ---: | ---: |
| Pac-Man | 982 / 22 / 176 | 989 / 17 / 174 |
| Blinky | 883 / 17 / 280 | 888 / 7 / 285 |
| Pinky | 831 / 18 / 331 | 842 / 9 / 329 |
| Inky | 928 / 12 / 240 | 927 / 19 / 234 |
| Clyde | 859 / 16 / 305 | 870 / 6 / 304 |

Exclusions include shared-colour cells, reward expansion, clipping, hidden
actors and insufficient distinct ink. Inky's partial count and visible-ink
colour mismatch count grow (12→19 and 4→8); the capture is not evidence that
colour clash or flicker has been solved.

The [comparison preview](../build/pool-shift-fast/evaluation/comparison.png)
and [consecutive-frame evidence](../build/pool-shift-fast/evaluation/trial-vice/evidence.png)
were visually inspected. The latter shows Pac-Man present/partial/present at
frames 105/106/107. The [comparison video](../build/pool-shift-fast/evaluation/glyph-pool-comparison.mp4)
labels both executable hashes and uses natural cadence without audio.

## Reproduction

```sh
make test-pool-shift-fast
python3 tools/arcade/profile_game.py --prg build/pool-shift-fast/pacman.prg --map build/pool-shift-fast/pacman.map --input tests/fixtures/active-replay.json --output build/pool-shift-fast/new-cpu
python3 tools/arcade/pool_profile.py --capture build/pool-shift-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-shift-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/pool-shift-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/pool-shift-fast/new-vice
```

Run native tools sequentially and use fresh profile/capture directories.
Raw evidence is under `build/pool-shift-fast/evaluation/`. The
[frozen record](baselines/pool-shift-fast.json) keeps compact measurements and
source/artifact identities. That original trial record is historical; the
promotion record above records acceptance. Persistent caching and pacing
remain deferred.
