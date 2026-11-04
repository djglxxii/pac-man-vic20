# Faster ghost tunnel lookups

**Accepted on 2026-11-04 after live review; now included in the standard
[composition build](POOL_STAMP_OPTIMIZATION.md).** The standalone tunnel build
remains available for comparison. Its original promotion verified the default
PRG, labels, native image, ELF and profiler map against the measured build below.
The preceding [sound-effect build](SOUND_EFFECT_OPTIMIZATION.md) remains
available for comparison.
This is the first completed experiment from the ghost-state/movement
candidate in the [optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates).

Actual VICE capture improves from **25.67 to 26.44 redraws/s**, about **3.0%**
on the saved route. This is a modest speed improvement; it does not establish
another perceptible flicker reduction.

```sh
make run-tile-address-fast
```

Press **5**, **1**, then use the arrow keys. `make run` launches the latest
standard; compare with `make run-sound-effect-fast` for the tunnel build's
predecessor. The standalone PRG is `build/tile-address-fast/pacman.prg`.

## Measured target and implementation

The preceding sound build's native replay spends **17.51%** of CPU time in
`updateGhostStates_1017` and its callees. Inspection of the recorded instruction
costs and linked disassembly finds repeated maze-colour address arithmetic
inside the four ghosts' movement paths. This reads the arcade's logical maze
metadata to decide tunnel speed; it does not change displayed wall colours.

Under `TILE_ADDRESS_FAST`, `src/tile_address.S` replaces only
`checkGhostEnterTunnel_205a`. Two 32-byte tables supply the column portion of
the original offset, including its constant +64. The routine adds the wrapped
row offset, preserves carry and the final ten-bit wrap, reads logical colour
RAM at physical $0800, and stores exactly 1 for colour $1B or 0 otherwise.
Both tables are aligned so an indexed read cannot cross a page.

The complete lookup is in assembly to avoid a second C wrapper saving pointers
and registers around a small arithmetic callee. That wrapper outweighed the
isolated arithmetic saving in an earlier development measurement. The retained
lookup takes **64 cycles** for a non-tunnel colour or **66 cycles** for $1B,
including RTS and excluding the caller's JSR/setup, with IRQs masked.

The original C lookup remains in the host reference and all earlier builds.
The other screen/colour address functions are unchanged. The ABI preserves
the aux pointer, software stack, callee-saved compiler registers and renderer
scratch; it uses two existing caller-scratch bytes. C assertions check the
two-byte coordinate layout used by assembly. No new writable scratch is added.

Ghost speed masks, update count/order, movement, AI, RNG, collisions,
house/death handling, the 16,875-cycle arcade clock, renderer and sound logic
are unchanged.

## Results

| Measurement | Previous sound build | Accepted tunnel lookup |
| --- | ---: | ---: |
| Actual VICE redraws/s | 25.67 | **26.44** |
| Native replay redraws/s | 25.75 | **26.57** |
| Mean active ghost-state call, cycles including callees/IRQs | 1,477.47 | **1,378.01** |
| Active ghost-state calls | 2,414 | 2,414 |
| Mean identical-input ghost fixture, IRQs masked | 1,444.06 | **1,339.52** |
| Actual 95th-percentile redraw interval | 56.55 ms | **54.61 ms** |
| Actual longest redraw interval | 70.47 ms | **68.54 ms** |
| Maximum native input-service gap | 42.61 ms | 42.44 ms |
| Maximum native audio-service gap | 37.18 ms | 37.50 ms |
| Resident code/data end | $7BBC | **$7B73** |
| Free before full software stack | 388 bytes | **461 bytes** |

The active ghost-state path uses about **6.73% fewer cycles**. Both native
replays match all **1,207 logical game states**. Uniform fixtures are not an
FPS prediction: their 528 cases cover eleven modes, including returning,
in-house and death-pause paths. The 384 active-movement cases average 1,594.96
versus 1,453.08 cycles; none of the 528 cases regresses. Code placement also
affects cycle costs outside the changed lookup.

The largest observed audio-service gap increases slightly. Faster average
processing does not guarantee every latency improves. These measurements use
one saved route/capture pair and do not establish worst-case performance.

## Memory and hardware

The build uses the same period-correct NTSC +3K and BLK1/2/3/5 configuration.
The two new tables occupy 64 resident bytes. Changed compiler inlining grows
some intermission code in BLK5; `src/tile_address.ld` relocates the existing
64-byte task dispatch table to BLK1–3 so the bank still fits. This linker script
must precede the base `glyph_pool.ld` script when linking.

Despite the added lookup tables and relocation, resident code/data ends
**73 bytes earlier**, leaving 461 bytes before the unchanged **704-byte stack**
at $7D40–$7FFF. BLK5 has 24 bytes free. All base linker bounds remain enabled.
The packed PRG grows from 26,591 to 26,695 bytes; compression size is separate
from resident memory use. No hardware expansion or VIC-visible pool allocation
changes are required.

## Validation and visible limits

`make test-tile-address-fast` passes 15 ROM comparisons, all 39 pooled
logic/render/colour/font/memory checks, three new kernel tests, 12 classifier
tests and smoke through all three intermissions and 7,183 logical ticks.
Stack guards, IRQ vector and boot handoff survive; observed stack use is
30 software and 22 hardware bytes, with the full reservation retained.

The new kernel tests execute **141,568 actual PRG calls**: all 65,536
coordinate pairs with both incoming carries, ten independent address-bit
palettes covering all 1,024 logical cells, and all 256 colour-byte values.
They check adjacent output canaries, the unchanged palette and all zero page
except the two declared scratch bytes. A five-cycle carry-setting/JMP fixture
is excluded from the quoted 64/66-cycle kernel cost.

Separate 528-case ghost runs compare each compiled build with the original
Z80 ROM on identical fixtures. The sound replay matches all effect/song state,
frequency/volume state and arcade/VIC register values on **1,639 ticks**.
That compares values per logical tick, not CPU write timestamps or PCM audio.
No new listening or physical-hardware test is claimed.

The actual capture contains **1,180 consecutive raster frames**, verifies all
33,792 depacked bytes against its own PRG, and passes **498 settled-picture
oracles** and **4,026 synthetic absent/partial controls** without a false
partial/absent result on settled pictures. No fully absent actors occur among
classified samples. Partial poses remain and change in both directions:

| Actor | Standard present / partial / excluded | Trial present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 977 / 24 / 179 | 982 / 21 / 177 |
| Blinky | 890 / 10 / 280 | 877 / 21 / 282 |
| Pinky | 838 / 12 / 330 | 838 / 15 / 327 |
| Inky | 927 / 15 / 238 | 924 / 14 / 242 |
| Clyde | 866 / 10 / 304 | 867 / 11 / 302 |

Shared colour cells, rewards, clipping and insufficient distinct ink remain
excluded from classification. Different raster phase/cadence can expose
different partial poses; the result is not a guarantee of flicker-free actors.
The [comparison video](../build/tile-address-fast/evaluation/glyph-pool-comparison.mp4)
uses natural-cadence VICE frames with executable hashes and ticks, without
retiming or audio. Its preview and the partial-pose evidence were inspected.

## Reproduction and tracking

```sh
make test-tile-address-fast
python3 tests/ghosts.py --pooled --prg build/sound-effect-fast/pacman.prg --output build/tile-address-fast/evaluation/baseline-ghosts.json
python3 tests/ghosts.py --pooled --prg build/tile-address-fast/pacman.prg --output build/tile-address-fast/evaluation/trial-ghosts.json
python3 tools/arcade/profile_game.py --prg build/tile-address-fast/pacman.prg --map build/tile-address-fast/pacman.map --output build/tile-address-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/tile-address-fast/pacman.prg --output build/tile-address-fast/new-vice --frames 1180
python3 tools/arcade/analyze_display.py --capture build/tile-address-fast/new-vice
```

Run native fixture tools sequentially because they share a work directory.
[Frozen results](baselines/tile-address-fast.json) retain compact evidence;
their status records the trial before live acceptance and promotion.
Raw profiles, captures and logs are under `build/tile-address-fast/evaluation/`.
The standalone tunnel PRG is byte-identical to the measured trial. Its SHA-256 is
`5104973e43a2e0db2e1112ee18454012bbbbaa89646d914d3a9fa3663f0d40b4`.
The preceding sound build remains
`1f33cc8ed6eba5a7216edf6d94ae54c671ea12296bae4e05eeb2c57fd4b47659`.
The original promotion ran the kernel checks against the then-default PRG and
compared its full-program sound replay with that predecessor. That run passed
15 ROM, 39 pooled, four effect, three tunnel-kernel and 12 classifier tests,
the 1,639-tick audio replay and smoke through all three intermissions. Its
[log](../build/tile-address-fast/evaluation/promotion-tests.log) records the
then-default build. All five default files were also byte-identical to their
explicit tunnel-build counterparts. The queue records this first ghost-state
experiment as accepted; the subsequent composition improvement is now standard,
and the other three candidates remain queued/deferred.
