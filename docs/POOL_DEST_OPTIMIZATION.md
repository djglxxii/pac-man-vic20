# Cheaper sprite destination setup

**Accepted and promoted, 2026-11-04.** Actual VICE throughput improves
**33.29 → 33.64 completed redraws/s**, about **1.1%**, on the saved route.
The user requested promotion; this accepted intermediate version is retained.
[Promotion evidence](baselines/pool-dest-promotion.json) records its historical
default identities and regression checks. The later
[normal-ghost row-control build](POOL_GHOST_ROW_OPTIMIZATION.md) is now standard.

```sh
make run-pool-dest-fast
```

Press **5**, then **1**, and use the arrow keys. Compare with `make run-pool-setup-fast` for the preceding build.
The explicit PRG is `build/pool-dest-fast/pacman.prg`.

## Measurement and change

The accepted build's exclusive instruction profile puts destination-pointer
setup at **765.41 cycles/native redraw**, or **2.50% of CPU time**. Generic
shifted composition uses 11.21%; copying clean home glyphs uses 10.59%.
The copy is already unrolled, and another large graphics table would not fit
comfortably in the remaining 141 resident / 23 BLK5 bytes. A small setup
change is therefore the first bounded experiment.

The original `pool_setup` initializes all four destination pointers to the
clipping sink, then overwrites the pointers for real cells. With
`POOL_DEST_FAST`, `src/glyph_pool.S` assigns a sink only to a clipped column
and assigns real destinations directly. It keeps the same allocation order:
top left, bottom left, top right, bottom right.

For an available column, a bottom pointer is left alone when the sprite's
starting glyph row is 0–4. Twelve rows then end at row 11–15, so neither the
generic stamper nor the normal-ghost stamper can dereference that bottom
pointer. At starting row 5 or later, bottom allocation and pointer assignment
remain unchanged. Missing columns still get both sink pointers, including the
zero-width right half of a horizontally aligned normal ghost. The unused
scratch values can differ; every destination the stamper reaches is prepared.

There are no new tables, state bytes, IRQ operations or hardware requirements.
Cell copying, overlap/colour order, bank capacity/failure handling, publication,
artwork, arcade logic and sound retain their behavior. The original setup
remains under the build conditional.

## Results

| Measurement | Standard sprite preparation | Destination trial |
| --- | ---: | ---: |
| Actual VICE completed redraws | 651 | **658** |
| Actual VICE redraws/s | 33.29 | **33.64** |
| Actual 95th-percentile redraw interval | 45.65 ms | **45.44 ms** |
| Actual maximum redraw interval | 61.28 ms | 61.51 ms |
| Native completed redraws | 665 | **673** |
| Native redraws/s | 33.39 | **33.78** |
| Mean full native refresh, cycles | 15,579.88 | **15,418.37** |
| Native 95th-percentile refresh, cycles | 20,747 | **20,474** |
| Native maximum refresh, cycles | 26,119 | **24,543** |
| Destination setup exclusive cycles/native redraw | 765.41 | **629.64** |
| Maximum native input-service gap | **36.77 ms** | 37.34 ms |
| Maximum native audio-service gap | 35.61 ms | **35.25 ms** |
| Setup routine code bytes | 114 | 122 |
| Resident end / free before full stack | $7CB3 / 141 bytes | $7CB3 / 141 bytes |
| BLK5 free | 23 bytes | 23 bytes |
| Packed PRG bytes | 26,814 | 26,829 |

Destination setup costs about **17.7% less per native redraw**. Alignment
absorbs the eight extra code bytes without changing the resident end. No
writable storage is added; the full **704-byte software stack** remains
reserved at $7D40–$7FFF. Hardware remains NTSC with +3K and BLK1/2/3/5
expansion. The native image remains 33,792 bytes.

Different redraw cadences sample different poses. The native profile is a
whole-program result; the identical-scene comparison below isolates the
transaction change. The longer maximum actual redraw and native input gaps
remain tradeoffs. This small average improvement does not establish a fixed
frame rate, a worst-case deadline or reduced perceptible flicker.

## Correctness and boundary checks

All **8,768 complete sprite scenes per build** pass the existing independent
pixel/colour oracle, including retained actor inputs and restored backgrounds.
They cover every regular frame and palette, flips and shifts, both tunnel
edges, row offsets 0/4/5/15, the bottom of the display, special eyes/rewards,
invisible/clipped actors, alternating banks and epoch wraps.

Mean complete transaction cost falls **2,575.77 → 2,567.10 cycles** across
the uniform fixture. **5,634 scenes save 1–30 cycles; 3,134 are unchanged**.
No scene is slower. Exclusive destination setup totals 622,290 → 546,547
cycles over the fixture; actor preparation is identical. The complete output
digest remains
`1c8e70e6e820b3f41d989da46703592dc0bd8d6adb36a322fa4eaf5ab8b9140d`.

An additional **10,496 generic-stamper cases per build** use
`pool_stamp_timing.py --poison-unused-bottom`. At row offsets 0 and 4, the
bottom pointers deliberately point at guard glyphs. Every real atlas mask,
synthetic empty/dense/narrow mask, shift and flip still matches an independent
per-pixel oracle, including unchanged guards. Generic kernel timings match
exactly between builds; this change affects setup, not the kernel.

The trial also passes 15 original-ROM comparisons, 41 pooled
logic/render/colour/font/memory checks and 13 display-classifier tests. All
**1,207 active replay game states** match the predecessor and fixture. All
**1,639 sound ticks** match the exact arcade state and VIC register values.
Smoke covers all three intermissions and **7,181 logical ticks**, with boot
handoff, IRQ vector, stack guard and the full stack reservation intact. Smoke
forces the intermission levels; it is not a complete unaided playthrough.

These checks do not replace listening or physical-hardware testing. CPU write
timestamps can differ even when tick-indexed sound values match.

## Actual display checks

Both recordings contain **1,180 consecutive raster frames** over the same
19.557-second window, with identical input per logical tick. Each capture's
33,792 depacked bytes match its own executable. There are no guest patches,
render gates, clock changes or retimed poses. The existing standard capture
is reused after checking its executable identities. **681 same-index raw
frames differ**, confirming distinct binaries and display cadence.

The trial passes **634 settled-picture checks** and **5,150 synthetic
absent/partial controls**, with zero false absent/partial results on settled
images. No fully absent actor appears among eligible cases:

| Actor | Standard present / partial / excluded | Trial present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 990 / 17 / 173 | 982 / 22 / 176 |
| Blinky | 889 / 10 / 281 | 883 / 17 / 280 |
| Pinky | 838 / 13 / 329 | 831 / 18 / 331 |
| Inky | 923 / 18 / 239 | 928 / 12 / 240 |
| Clyde | 869 / 10 / 301 | 859 / 16 / 305 |

Partial poses remain; several counts increase. Shared-colour cells, reward
expansion, clipping, hidden actors and insufficient distinct ink remain
exclusions. Alignment is x=8, y=4 at two output dots per VIC dot, with zero
initial mismatches and 3,576 at the next distinct alignment. The
[consecutive-frame evidence](../build/pool-dest-fast/evaluation/trial-vice/evidence.png)
and [comparison preview](../build/pool-dest-fast/evaluation/comparison.png)
retain those visual limits. The
[comparison video](../build/pool-dest-fast/evaluation/glyph-pool-comparison.mp4)
uses natural cadence, executable-hash labels and no audio.

## Rejected first draft and reproduction

The first draft still explicitly initialized unused bottom pointers. Its
setup routine grew 16 bytes, moving the epoch-clear and normal-ghost loops
across page boundaries. Complete scene calls became **24.56 cycles slower
on average**, despite cheaper setup and identical pixels. It was rejected.
Its source, binaries and test results remain in
`build/pool-dest-fast/evaluation/rejected-eager-bottom/`.

The smaller final routine grows eight bytes. Its clear-loop branch and ghost
row-loop branch remain within their pages, without adding padding. Static
cycle annotations use the actual linked zero-page symbols. This placement
must be checked again if later changes move the routines.

```sh
make test-pool-dest-fast
python3 tools/arcade/profile_game.py --prg build/pool-dest-fast/pacman.prg --map build/pool-dest-fast/pacman.map --input tests/fixtures/active-replay.json --output build/pool-dest-fast/new-cpu
python3 tools/arcade/pool_profile.py --capture build/pool-dest-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-dest-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/pool-dest-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/pool-dest-fast/new-vice
```

Run native fixture tools sequentially and use new profile/capture directories.
Raw evidence is under `build/pool-dest-fast/evaluation/`; the
[frozen record](baselines/pool-dest-fast.json) retains compact measurements,
identities and evidence hashes. The frozen trial status remains historical;
the promotion record above identifies this former default. The later
[generic-shift optimization](POOL_SHIFT_OPTIMIZATION.md) is accepted and
included in the later row-control default.
Persistent caching and pacing changes remain deferred.
