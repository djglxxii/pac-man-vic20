# Pool address optimization

First speed follow-up to the accepted [glyph pool](GLYPH_POOL.md), starting
from commit `74f202e`. The focused allocator change is faster and preserves
settled pixels. The overall gain is modest: **22.04 → 22.80 actual redraws/s,
about 3.5%** on the saved route. The accepted default is unchanged.

```sh
make run-pool-address
```

Use **5**, **1**, and the arrow keys. `make run` launches the accepted baseline.
Both use the same artwork, game logic, clock and RAM expansion. The
[comparison video](../build/pool-address/evaluation/glyph-pool-comparison.mp4)
shows actual VICE frames at natural cadence, with executable hashes and ticks.
The settled picture should look the same; this is a small speed increment.

## Changes

The prior native profile charged about 6,493 cycles per refresh to cell
lookup/allocation and copying. Roughly half was the fixed 16-byte copy, which
already has an unrolled loop. This increment keeps that copy and reduces the
surrounding address calculations:

- Fresh cells use a running destination pointer within the pending bank.
  Existing allocations retain the original lookup/pointer path. The cursor
  advances only on new allocation, including carries across page boundaries.
- The existing 196-byte home-code table stores exchanged nibbles in this
  variant, making source addresses faster to read. Matrix restoration converts
  them back with a binary-mode arithmetic fragment.
- The low cursor reuses the unused old underlay cursor byte. Its high byte
  borrows a publication-bound byte while that bound is dead during composition.
  Publication rewrites both bounds before using them. No extra RAM is allocated.

The arithmetic uses legal NMOS 6502 instructions. Each ADC consumes carry from
its preceding ASL. Rendering already requires binary mode for existing address
math; the new fragment has the same requirement. The banks, clean home glyphs,
reuse guard, publication order and actor/colour priority remain unchanged.

## Measurements

| Identical-input kernel measurement | Accepted | Trial |
| --- | ---: | ---: |
| Fresh allocation, mean | 413.69 cycles | 377.69 cycles |
| Fresh allocation, maximum | 414 | 378 |
| Existing-cell lookup, mean | 119.08 | 119.08 |

All 392 fresh cases save exactly **36 cycles**, about 8.7%. Both programs
receive identical home bytes, cells, slot indices and lookup-tag phases,
covering all 196 home glyphs in both banks. Another 392 existing-cell hits check
that reuse does not advance the cursor. These calls mask IRQs; they establish
a kernel improvement, not live FPS.

The tradeoffs are included below: cursor initialization adds 19 cycles per
transaction, and restoring each home code adds 12 cycles. Complete refreshes
are the performance criterion. Both native runs match **1,207 logical game
states** against the same saved joystick trace.

| Whole-game measurement | Accepted | Trial |
| --- | ---: | ---: |
| Actual VICE redraws/s | 22.04 | **22.80** |
| Native replay redraws/s | 22.13 | 22.90 |
| Mean full native refresh cost | 18,966 cycles | 18,324 cycles |
| Actual 95th-percentile redraw interval | 68.07 ms | 65.28 ms |
| Actual longest redraw interval | 83.82 ms | 82.29 ms |
| Native maximum input-service gap | 45.72 ms | 41.92 ms |
| Native maximum audio-service gap | 41.16 ms | 39.94 ms |

These are observations on one route and capture pair, not guaranteed bounds.
The faster renderer completes more transactions, so work per refresh changes.
The identical-input kernel test independently establishes the local saving.

The video comparison analyses 1,180 consecutive raster frames per program and
verifies all 33,792 depacked bytes of each executable. Neither capture has a
fully absent Pac-Man or ghost among classified cases. Pac-Man has 987 present,
18 partial and 175 excluded samples on each side. Partial counts and exclusions
vary slightly for ghosts; this does not establish a further flicker reduction.
Shared cells, clipping, rewards and insufficient distinct ink remain excluded.

The accepted capture passes 415 settled-picture oracles and 3,364 deliberate
absent/partial controls. The trial passes 429 settled-picture oracles and 3,504
controls, with no false disappearance on settled pictures. Actual raster
screenshots and the comparison preview were visually inspected.

## Memory and validation

- The full **704-byte stack** remains at $7D40–$7FFF. Resident code/data ends at
  **$7D32**, leaving 14 bytes before the stack, versus 49 at the accepted
  checkpoint. BLK5 still has 19 bytes free. Linker bounds remain enabled.
- The trial passes the **39-check pool suite**: image oracles, original-ROM
  logic/audio parity, loader/stack checks, fonts/rewards, full-bank teleports,
  generation wraparound and the new address checks.
- One new test checks every home address, both banks, page boundaries and
  existing-cell hits. Another executes the actual compiled nibble decoder for
  all 256 inputs and both incoming carries: **512 cases**.
- Native smoke reaches all three intermissions and **7,184 logical ticks**,
  with IRQ and stack guards intact. Observed software stack use is 32 bytes;
  the reservation has not been reduced.
- The 12 host-classifier checks pass, including window selection and rejection
  of source gaps even when they lie outside a requested analysis window.

## Capture audit and reproduction

The baseline is the first 1,180 frames of a valid fresh 1,200-frame capture.
The entire source passes consecutive-frame validation before window selection.
Source PNGs and `recording.json` stay unchanged. The final trial directly
captures 1,180 frames, staying within the saved input trace.

An initial trial exceeded the trace by one tick and is incomplete. A separate
baseline attempt had two doubled raster intervals and was rejected. Those
directories are explicitly marked and excluded from all results. Missing
frames were not filled or retimed. `initial-trial-cpu` is also superseded.

```sh
make test-pool-address
python3 tools/arcade/pool_address_timing.py
python3 tools/arcade/profile_game.py --prg build/pool-address/pacman.prg --map build/pool-address/pacman.map --output build/pool-address/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-address/pacman.prg --output build/pool-address/new-vice --frames 1180
python3 tools/arcade/analyze_display.py --capture build/pool-address/new-vice
```

Analyse a matching prefix of a longer valid baseline with
`analyze_display.py --capture DIRECTORY --frames 1180`. Recreate the video with:

```sh
python3 tools/arcade/compare_display.py --baseline build/pool-address/evaluation/baseline-vice --trial build/pool-address/evaluation/final-trial-vice --output build/pool-address/evaluation --baseline-label "Accepted glyph pool" --trial-label "Faster pool addresses"
```

[Frozen results](baselines/pool-address.json) identify costs, memory and checks.
The accepted PRG remains
`0d33d3747809a302d400ef530ac7abd599e46c267b9181f7e752fc6f1f778fe5`.
The trial PRG is
`c96ed73ab9e7ea61e14eeceb56fd7e8c10eeedd62c11bb2dc67ad3f4fe20301c`.
The trial is available for live review and has not replaced the accepted build.

The next [empty-row trial](POOL_SKIP_EMPTY.md) retains these address changes
and reaches 23.21 actual redraws/s by skipping pixel work for empty sprite rows.
