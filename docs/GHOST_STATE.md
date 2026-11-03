# Cheaper ghost movement-pattern updates

The first ghost-state optimization removes redundant work when advancing the
four ghosts' speed masks. The standard normal-play sample improves from
**51.38 to 51.93 completed renders/s**, and frightened play from **54.02 to
54.61**. It also frees **325 resident bytes**, leaving 716 bytes in BLK1–3
and 15 in BLK5. This is a modest performance improvement, not a flicker fix.

The baseline is the accepted generic sprite-kernel build on top of `cf81d64`,
after reverting the region-compositor and raster experiments. Its PRG SHA-256
starts `34a552f6`. The [frozen record](baselines/ghost-state.json) identifies
both builds, source hashes, cycle measurements and validation results.

## Implementation

The existing gameplay profile spends 6.73% of its recorded CPU cycles inside
`updateGhostStates_1017`, including its inlined helpers but excluding separate
callees. Inspection found repeated work around the 32-bit movement patterns:
the compiler rotates each pattern in RAM and also shifts temporary copies to
calculate the movement decision at bit 16.

The new `ghostMoveStep()` helper retains the original 32-bit rotation. On the
VIC target, a volatile read of the third byte then obtains bit 16 directly
from the stored result. This makes LLVM-MOS emit a carry setup, four in-place
byte rotations and a byte test. It avoids the extra temporary shifts without
handwritten assembly or a general memory barrier. The host build retains the
original full-width bit test.

All fourteen ghost pattern-selection sites use this helper: normal,
frightened and tunnel speed for each ghost, plus Blinky's two Elroy masks.
Pac-Man's movement path is unchanged. Pattern selection, update order,
movement count, house/death handling and the 16,875-cycle game timer remain
the same. No additional RAM, tables or zero-page storage are allocated.

The resident end moves from `$7E79` to `$7D34`; the compressed PRG shrinks
from 26,848 to 26,715 bytes. The linker script and memory configuration are
unchanged.

## Measurements

The new `tests/ghosts.py` compares the actual compiled routine to the original
Z80 entry at `$1017` on **528 identical fixtures**. Each of eleven scenarios
uses 48 patterns: zero, all ones, alternating bits, all 32 individual set-bit
positions and twelve deterministic random patterns. Scenarios cover normal,
frightened, tunnel and both Elroy modes; competing mode priorities; and
in-house, returning and death-pause paths.

Across the 384 active-movement fixtures, the complete routine uses
**7.62–8.24% fewer cycles per scenario on average**. Every active case saves
132–139 cycles. Returning and death-pause cases are unchanged; the 48
in-house cases cost two more cycles each. Across all equally weighted cases,
the mean falls from 1543.06 to 1443.70 cycles, or **6.44%**. Calls mask IRQs;
fixture loading is excluded. These weights do not represent actual play.

Standard CPU-cycle samples use 180 NTSC video frames, or 360 for transition:

| Scene | Renders/s before | After | Longest draw interval before → after |
| --- | ---: | ---: | ---: |
| Normal play | 51.38 | 51.93 | 44.77 → 36.70 ms |
| Frightened | 54.02 | 54.61 | 41.55 → 46.06 ms |
| Attract chase | 44.25 | 43.65 | 61.80 → 52.02 ms |
| First intermission | 60.15 | 60.03 | 22.61 → 22.60 ms |
| Board transition | 41.86 | 41.86 | 1843.18 → 1843.16 ms |

The short attract sample regresses, and frightened play's longest interval
increases. Faster logic does not guarantee better cadence in every sample.
Longer 1,800-frame workloads measure 51.93 → 52.38 renders/s from the play
setup, 50.21 → 52.95 from the frightened setup, and 37.98 → 38.76 from attract.
These longer runs include deaths, mode changes and screen construction; they
are mixed workloads, not sustained frightened movement or isolated chase.

The retained benefit is lower identical-input routine cost, recovered code
space and modest measured throughput gains. Visible flicker remains.

## Validation and reproduction

All **48 regression tests** pass. The new test compares complete logical
screen, palette, game state and meaningful sound-register bits to the Z80
reference, and verifies that its active fixtures actually rotate the intended
mask. Existing native movement/frightened traces and intermission checks pass.
The smoke run covers 7,183 logical ticks with its IRQ vector, startup handoff
and stack guard intact; observed stack use remains 32 software/24 hardware
bytes. Those observations are not formal worst-case stack bounds.

VICE confirms boot, coin/start, sound, all eight blue/white completion phases
and a settled next board. Physical hardware has not been tested.

```sh
make test
python3 tests/ghosts.py --output build/ghost-state/current-ghosts.json
python3 tests/performance.py --output build/ghost-state/current-performance
python3 tools/arcade/vice_check.py --maze-flash --output build/ghost-state/vice-validation
```

The ghost and performance tools accept `--prg PATH` with a sibling `.lbl` file.
Run the ordinary tests first to create the shared ROM fixture. Raw profiles,
per-case timings, before/after executables, regression logs and VICE captures
remain locally under ignored `build/ghost-state/`.
