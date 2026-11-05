# Faster generic sprite composition

**Accepted on 2026-11-04 after live review; included in the standard
[pitch-lookup build](AUDIO_DIVIDER_OPTIMIZATION.md).** This standalone composition
build remains available for comparison. Its original promotion checked the
default PRG, labels, native image, ELF and profiler map against the measured
build below. The preceding
[tunnel-lookup build](TILE_ADDRESS_OPTIMIZATION.md) remains available for comparison.
This is the first completed experiment in candidate 2 of the
[optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates).

Actual VICE capture improves **26.44 → 27.46 redraws/s**, about **3.9%**, on
the saved route. It preserves the existing pool renderer and artwork. Average
speed improves, but occasional stalls and partial poses remain; the longest
captured redraw interval increases from 68.54 to 74.87 ms.

```sh
make run-pool-stamp-fast
```

Press **5**, **1**, then use the arrow keys. `make run` launches the latest
standard. Compare with `make run-tile-address-fast` for this version's predecessor.
The standalone PRG is `build/pool-stamp-fast/pacman.prg`.

## Measurement before choosing the change

The preceding tunnel build's native replay spends **45.96%** of CPU time
rendering. Rebucketed instruction counts show these exclusive pool costs per
completed redraw:

| Work | Cycles/redraw | Share of total CPU |
| --- | ---: | ---: |
| Generic shifted stamping | 4,019.10 | 10.44% |
| Copying clean home glyphs | 3,245.62 | 8.43% |
| Cell lookup/allocation, excluding copy | 2,465.98 | 6.41% |
| Actor pose/palette/source setup | 2,295.57 | 5.96% |
| Restore/control/publication | 1,558.60 | 4.05% |
| Destination-pointer setup | 765.42 | 1.99% |
| Preshifted normal-ghost stamping | 764.66 | 1.99% |

The copy is already unrolled over all sixteen bytes. The generic stamper
has repeated shifts, temporary byte stores/reloads and a separate row counter,
making it a better bounded first experiment than adding large graphics tables.
The profile contains 2,081 generic calls and 744 specialized ghost calls;
21,081 of its 24,972 generic source rows are nonempty.

`tools/arcade/pool_profile.py` derives these costs from the saved instruction
profile and linked labels. Its disjoint ranges must sum to the recorded
`.text.pool` cost; the generic subranges must sum to the generic total.
No guest instructions, clocks or IRQs are instrumented or changed. These are
exclusive code-region costs; they are distinct from inclusive render-phase
timing and from the identical-input kernel comparisons below.

## Implementation

With `POOL_STAMP_FAST`, `src/glyph_pool.S` includes
`src/pool_stamp_fast.inc` in place of the original generic `pool_draw` body.
The original body remains available to earlier builds.

- Dispatch directly to the chosen shift kernel; mirror only when requested.
- Keep one shifted half in A through its OR/store, avoiding a temporary
  byte store and reload. Left/right OR order can change without changing the
  final pixels, including when clipped pointers share the sink glyph.
- Split four/five-pixel shifts with accumulator shifts instead of repeatedly
  rotating a two-byte value. Other phases retain shorter rotate sequences.
- For an aligned sprite, merge the left half only; the right half is zero.
- Use the source X index as the twelve-row counter, with a patched end value
  of 12 for forward order or 255 for reverse order. Empty rows still advance
  normally, and crossing glyph row 15 switches both destination pointers.

The routine uses legal NMOS 6502 instructions and existing scratch bytes.
Self-modified code remains confined to the main-thread renderer. Allocation,
home copying, overlapping actors, palettes/colour priority, both banks,
publication order, safe reuse, the normal-ghost fast path and arcade logic
are unchanged. There is no raster wait, IRQ drawing or audio change.

## Results

| Measurement | Previous tunnel build | Accepted composition build |
| --- | ---: | ---: |
| Actual VICE redraws/s | 26.44 | **27.46** |
| Native replay redraws/s | 26.57 | **27.57** |
| Generic exclusive cycles/native redraw | 4,019.10 | **3,434.68** |
| Mean full native refresh, cycles | 17,689.85 | **17,056.53** |
| Native 95th-percentile refresh, cycles | 23,687 | **23,056** |
| Actual mean redraw interval | 37.83 ms | **36.44 ms** |
| Actual 95th-percentile redraw interval | 54.61 ms | 54.50 ms |
| Actual longest redraw interval | 68.54 ms | 74.87 ms |
| Maximum native input-service gap | 42.44 ms | **40.34 ms** |
| Maximum native audio-service gap | 37.50 ms | 38.16 ms |
| Resident code/data end | $7B73 | $7BB3 |
| Free before full software stack | 461 bytes | 397 bytes |

Both native replays match all **1,207 logical game states**. The trial completes
549 native redraws versus 529, and 537 versus 517 in the actual capture window.
Its average generic cost per redraw falls about **14.5%**. Faster redraws sample
different poses, so per-redraw work is not an identical-input comparison.
Changes in placement and page crossings also affect whole-program timing.

The longer maximum redraw and audio gaps are real limits of this sample.
These results use one saved route/capture pair; they do not establish a fixed
30 Hz display, worst-case deadlines or a new perceptible flicker improvement.

## Independent kernel and gameplay checks

`tools/arcade/pool_stamp_timing.py` executes **10,496 cases per PRG**, covering
all 64 normal masks, eight eyes masks, four right-hand reward masks and six
synthetic empty/dense/narrow patterns. Each uses all eight horizontal shifts,
four flips and vertical offsets 0, 4, 5 and 15. A per-pixel host oracle checks
the four destination glyphs and adjacent guards over nonzero initial ink.
Source masks and initial bytes must match between binaries.

| Uniform kernel sample | Previous tunnel build | Accepted composition build |
| --- | ---: | ---: |
| Mean cycles | 889.40 | **766.59** |
| 95th-percentile cycles | 1,257 | **1,147** |
| Maximum cycles | 1,392 | **1,242** |

Every case is faster: **54–366 cycles saved**, averaging 122.81 cycles,
or **13.8%**. IRQs are masked during calls, and frontend costs are excluded.
The uniform sample is not an FPS prediction; normal ghosts ordinarily use
their unchanged specialized path.

`make test-pool-stamp-fast` passes:

- 15 original-ROM comparisons and all 39 pooled logic/render/colour/font/memory
  checks, including overlaps, clipping, full banks, teleports and epoch wraps.
- Three retained tunnel-kernel tests covering 141,568 calls.
- The 10,496-case-per-build sprite comparison above.
- Exact effect/song state and arcade/VIC sound-register values for all 1,639
  replayed ticks. Values match; CPU write timestamps can differ.
- 12 host classifier checks and smoke through all three intermissions and
  **7,181 logical ticks**, with IRQ vector, stack guards and boot handoff intact.

The full **704-byte software stack** remains at $7D40–$7FFF. Observed software
use is 30 bytes and hardware use 24 bytes. The build adds **64 resident bytes**,
no writable allocation or new graphics table; 397 bytes remain before the
stack. BLK5 still has 24 bytes free. NTSC, +3K and BLK1/2/3/5 expansion and the
16,875-cycle arcade clock are unchanged. The packed PRG grows 46 bytes,
from 26,695 to 26,741; compression size differs from resident use.

## Actual raster validation and visible limits

Both captures contain **1,180 consecutive VICE raster frames** at natural
cadence, with the same input per logical tick. The predecessor capture is
reused unchanged. All **33,792 depacked bytes** match each capture's own PRG;
there are no guest code patches, PC render gates or clock changes.

The trial passes **516 settled-picture oracles** and **4,170 synthetic
absent/partial controls**, with no false partial/absent classification of
settled actors. No fully absent actor is found among eligible raster cases.
Partial poses vary by actor:

| Actor | Previous tunnel build: present / partial / excluded | Composition build: present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 982 / 21 / 177 | 973 / 25 / 182 |
| Blinky | 877 / 21 / 282 | 883 / 13 / 284 |
| Pinky | 838 / 15 / 327 | 837 / 12 / 331 |
| Inky | 924 / 14 / 242 | 934 / 6 / 240 |
| Clyde | 867 / 11 / 302 | 860 / 12 / 308 |

Shared colour cells, reward expansion, clipping and insufficient distinct ink
remain excluded. Existing colour sharing and non-atomic actor publication
remain visible. The [comparison video](../build/pool-stamp-fast/evaluation/glyph-pool-comparison.mp4)
labels executable hashes and ticks and preserves natural cadence without
retiming or audio. Its [preview](../build/pool-stamp-fast/evaluation/comparison.png)
and the [partial-pose evidence](../build/pool-stamp-fast/evaluation/trial-vice/evidence.png)
were inspected; the latter shows consecutive frames 92–94.

## Reproduction and tracking

```sh
make test-pool-stamp-fast
python3 tools/arcade/pool_profile.py --capture build/tile-address-fast/evaluation/trial-cpu --output build/pool-stamp-fast/evaluation/baseline-pool-costs.json
python3 tools/arcade/profile_game.py --prg build/pool-stamp-fast/pacman.prg --map build/pool-stamp-fast/pacman.map --output build/pool-stamp-fast/new-cpu
python3 tools/arcade/pool_profile.py --capture build/pool-stamp-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/pool-stamp-fast/pacman.prg --output build/pool-stamp-fast/new-vice --frames 1180
python3 tools/arcade/analyze_display.py --capture build/pool-stamp-fast/new-vice
```

Run native tools sequentially because they share a fixture work directory.
[Frozen measurements](baselines/pool-stamp-fast.json) retain compact evidence;
raw profiles, captures and logs are in `build/pool-stamp-fast/evaluation/`.
The frozen status records the trial before live acceptance and promotion.
The original promotion's standard PRG was byte-identical to the measured trial;
its SHA-256 was
`480fa052510ac687a9477e4da305d9e1accb6aaeb39d77c7d444e63a51d315c5`.
The preceding tunnel build remains
`5104973e43a2e0db2e1112ee18454012bbbbaa89646d914d3a9fa3663f0d40b4`.
The original `make test` checked the default PRG's pixels against the independent
kernel oracle and compared its full-program sound replay with that predecessor.
That promotion run passed all 15 ROM, 39 pooled, four effect, three tunnel-kernel
and 12 classifier tests, 10,496 sprite cases per build, the 1,639-tick audio
replay and smoke through all three intermissions.
The promotion run and five-file identity check are recorded in
the [promotion log](../build/pool-stamp-fast/evaluation/promotion-tests.log).
The sound replay uses the checked-in [input fixture](../tests/fixtures/active-replay.json),
so `make test` does not depend on a recording left in the ignored build tree.
Its 1,639 inputs are identical to the archived route; the fixture omits video
metadata, so its input-file digest differs while the sound-output digest
remains unchanged.
The optimization queue records this first composition experiment as accepted.
