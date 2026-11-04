# Skip empty sprite rows

**2026-11-04 update:** this change is accepted as part of the standard
[composition build](POOL_STAMP_OPTIMIZATION.md), launched with `make run`.
`make run-pool-skip-empty` retains the intermediate version measured here.

Second glyph-pool speed trial, built on the
[address-calculation trial](POOL_ADDRESS_OPTIMIZATION.md). Actual VICE captures
improve from **22.80 to 23.21 redraws/s**, about **1.8%**. Together, the two
speed changes improve on the accepted pool's 22.04 by about **5.3%** on this
route. The standard build now includes both changes.

```sh
make run-pool-skip-empty
```

Use **5**, **1**, and the arrow keys. Compare with `make run-pool-address` for
the preceding speed trial, or `make run-glyph-pool` for the original accepted
glyph pool. `make run` launches the latest standard build. The
graphics should look the same; this is a small throughput improvement.

## Change and measured choice

The generic stamper reads one eight-pixel source row at a time. If that byte
is zero, mirroring and shifting cannot produce any ink. A single `BEQ` now
skips straight to the normal row advance, avoiding those calculations and the
destination reads and stores. Existing backgrounds and previously composed
actors remain intact. Both twelve-row traversal and glyph-boundary handling
still run normally.

Allocation, overlap/colour priority, home copying, bank publication, the
safe-reuse guard and the preshifted normal-ghost path are unchanged. There is
no raster wait, new graphics table, clock change or additional RAM allocation.
The branch uses two bytes of legal NMOS 6502 code. Nonempty rows pay two
additional cycles; the taken branch stays within its page.

Checking each shifted half was also measured. Half-only checks gave almost
no whole-game benefit. Combining them with the empty-row check reached 23.30
native redraws/s, but their instruction trace showed the half checks adding
32,896 net cycles over 464 redraws. Removing those checks reached **23.40**.
The retained trial therefore skips whole empty source rows only. A nonempty
row can still write an empty shifted half.

## Whole-game measurements

| Measurement | Address trial | Skip empty rows |
| --- | ---: | ---: |
| Actual VICE redraws/s | 22.80 | **23.21** |
| Native replay redraws/s | 22.90 | **23.40** |
| Mean full native refresh, cycles | 18,324 | **17,943** |
| Generic stamping, exclusive cycles/native redraw | 4,348 | **4,015** |
| Actual 95th-percentile redraw interval | 65.28 ms | **64.48 ms** |
| Actual longest redraw interval | 82.29 ms | 83.05 ms |
| Native maximum input-service gap | 41.92 ms | **37.40 ms** |
| Native maximum audio-service gap | 39.94 ms | 40.08 ms |

Both native replays match **1,207 logical game states** against the same input
trace. The retained trial skips 3,453 of 21,996 generic source rows on that
route. Faster composition changes which poses reach a refresh, so work per
refresh is not identical. These are observations on one route, not guaranteed
worst-case limits or evidence that every latency improves.

Actual display comparison uses **1,180 consecutive raster frames per build**
at natural cadence, with the same input per logical tick. The predecessor's
valid capture is reused unchanged. Each capture verifies all **33,792**
depacked bytes against its own PRG, and consecutive-frame checks pass. No guest
instrumentation, PC gating or timer changes are used.

The trial passes **435 settled-picture oracles** and 3,536 deliberate
absent/partial controls with no false disappearance on settled pictures. It
has no fully absent actors among classified cases. Partial poses remain:
Pac-Man has 993 present, 16 partial and 171 excluded samples; the predecessor
has 987, 18 and 175. Ghost counts vary in both directions. Shared cells, rewards,
clipping and insufficient distinct ink retain the classifier's exclusions.
This does not establish another perceptible flicker reduction.

The [comparison video](../build/pool-skip-empty/evaluation/glyph-pool-comparison.mp4)
uses actual VICE frames with executable hashes and ticks, without retiming
poses. Its preview and the trial's raster evidence were visually inspected.

## Identical-input kernel checks

`tools/arcade/pool_stamp_timing.py` runs **10,496 cases per binary**, covering
all 64 normal masks, eight eyes masks, four right-hand reward masks and six
synthetic empty/dense/narrow patterns. Each is checked at all eight horizontal
shifts, four flips and vertical offsets 0, 4, 5 and 15. A separate per-pixel
oracle verifies the four destination glyphs and adjacent guards over nonzero
initial ink. Source masks and initial bytes must match between binaries.

| Uniform kernel sample | Address trial | Skip empty rows |
| --- | ---: | ---: |
| Mean cycles, all cases | 1,126.07 | **889.47** |
| Mean cycles, normal atlas | 1,126.06 | **920.98** |
| Mean cycles, eyes atlas | 1,125.88 | **621.81** |
| Mean cycles, right-hand rewards | 1,126.88 | **716.50** |

Per-case savings range from **24 cycles slower** for a fully nonempty mask to
**948 cycles faster** for an empty mirrored/shifted mask. Calls mask IRQs and
exclude the frontend; this uniform sample includes masks that do not occur
equally often in play. Normal ghosts ordinarily use the unchanged faster
specialized path. Kernel percentages must not be presented as a live FPS gain.

## Memory, validation and reproduction

The hardware target stays NTSC with +3K and BLK1/2/3/5 enabled, using the
existing 16,875-cycle arcade tick. Resident code/data ends at **$7D34**, leaving
**12 bytes** before the unchanged **704-byte stack** at $7D40–$7FFF. BLK5 still
has 19 bytes free. Linker guards remain enabled.

The trial passes **39 pool/logic/audio/memory/font checks**, including pixel
oracles, overlaps, clipping, teleports, generation wraps and address checks.
The 15 ROM comparisons and 12 classifier checks also pass. Smoke exercises all
three intermissions and **7,192 logical ticks**, with stack and IRQ guards
intact; observed software stack use is 32 bytes without reducing its reservation.

```sh
make test-pool-skip-empty
python3 tools/arcade/pool_stamp_timing.py
python3 tools/arcade/profile_game.py --prg build/pool-skip-empty/pacman.prg --map build/pool-skip-empty/pacman.map --output build/pool-skip-empty/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-skip-empty/pacman.prg --output build/pool-skip-empty/new-vice --frames 1180
python3 tools/arcade/analyze_display.py --capture build/pool-skip-empty/new-vice
```

[Frozen results](baselines/pool-skip-empty.json) record measurements and program
identities. The retained trial PRG is
`e2ed39e298fefa8677eb7271056bedc8b7d5a4c410faabcbd99155bff3213211`.
The address predecessor remains `c96ed73ab9e7ea61e14eeceb56fd7e8c10eeedd62c11bb2dc67ad3f4fe20301c`;
the original accepted pool remains
`0d33d3747809a302d400ef530ac7abd599e46c267b9181f7e752fc6f1f778fe5`.
