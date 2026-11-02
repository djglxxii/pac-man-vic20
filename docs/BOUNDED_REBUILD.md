# Bounded next-board work

First implementation from [the research plan](RESEARCH_OPTIMIZATION_PLAN.md),
based on preparation commit `aebb093`. Input, logic and sound are now serviced
while rebuilding a board. The full-expansion NTSC target and 16,875-cycle
arcade clock are retained.

The measurements below describe commit `249bb5a`. The later
[white-pellet experiment](COLOR_PRIORITIES.md) added neighbor checks; the
current [all-white maze](WHITE_MAZE.md) removes those checks while retaining
bounded servicing. These original measurements are preserved for comparison.

## Behavior and measured tradeoff

The old renderer blocked in one full redraw. The new renderer progressively
updates the single visible bitmap in small calls. Actors are restored once
before a rebuild and drawn from their latest state when it finishes. There is
no second framebuffer and no deliberate whole-screen blanking.

The main benefit is continued service, not faster completion of a whole board:

| Measurement | Before | After |
| --- | ---: | ---: |
| Longest background routine call | 819.17 ms | 6.08 ms |
| Longest audio-update gap in the transition sample | 832.29 ms | 29.73 ms |
| Longest input-service gap in the transition sample | 832.17 ms | 28.95 ms |
| Longest gap between coherent completed refreshes | 1277.65 ms | 1800.99 ms |

The focused transition test measures about 1,785 ms from the first rebuild
request to a settled board. Progressive work takes longer to converge than
the old blocking draw. Intermediate pixels are visible during that time;
unfinished batches are not counted as completed refreshes. Actors remain
absent while their background is incomplete. Reducing that visible
construction time remains worthwhile.

The before service timings came from the unchanged preparation binary with
host-side routine watches; the original performance summary is in the
[frozen baseline](baselines/research-optimization.json). The after
[measurement record](baselines/bounded-board-rebuild.json) includes all five
performance samples, the focused transition check, memory figures and artifact
hashes. These are emulator measurements, not physical-hardware guarantees.

Normal-play throughput was 49.74 FPS, frightened play 53.73, attract chase
44.37 and the intermission 60.30 in that revision's short samples. Positions at
the beginning of a sample can differ because setup now runs cooperatively.
Gameplay remains below sustained 60 FPS; this change addresses transition
service rather than general gameplay rendering throughput.

## Implementation

- `src/rebuild.S` replaces the synchronous background scan. It clears display
  metadata, clears at most one 256-byte bitmap page per call, and converts at
  most six full-pass tile positions or four dirty-pass positions per call.
  Sparse passes scan empty bitset bytes directly, so repeated credit/score
  writes cannot force an endless slow sweep.
- Writes ahead of the cursor are included in that pass; writes behind it
  request a follow-up dirty pass. A full invalidation restarts clearing.
  All ten address bits are retained when screen and color addresses share
  the 1,024-bit dirty map.
- `src/tasks.S` provides bounded screen/palette fills, maze decompression,
  pill drawing and pill removal. A queue entry stays at the head until its
  final slice completes. Existing maze-flash states retain their fast path.
- Full C bulk routines remain in the host reference build. Native synchronous
  wrappers support isolated routine comparisons; the live queue calls the
  bounded step function instead of draining those wrappers.
- Native ghost-state clearing uses fixed loops over `$0D00-$0D9F` and
  `$A0-$FF`, preserving the original contiguous virtual range and eliminating
  another 26 ms address-translation loop during setup.
- The main loop retains input, arcade ISR work, queued work and sound
  conversion in their original order. Between ticks, bulk work takes priority
  over background slices. Setup draining yields at tick boundaries; ordinary
  gameplay decision tasks retain their scheduling.
- `video_refresh` distinguishes an unfinished slice from a completed refresh.
  Final sprite composition recomputes coordinates and palettes instead of
  using the state cached at the beginning of a long rebuild.

The CPU simulator watches routine entry/return without guest instructions.
Trace events also record rebuild requests/phases and bulk task lifetimes.
The performance runner reports service gaps and slice durations, and extends
a transition sample if rebuild or setup work is pending. `render_ms_*` tracks
elapsed coherent-refresh work, including yields during a rebuild;
`background_slice_ms_max` tracks an individual background call.

## Memory configuration

Continuation state uses 16 previously unused bytes in screen-work RAM. The
whole region occupies `$02C4-$02FB`, leaving four bytes. The final link has
214 bytes free in BLK1-3 and 27 in BLK5, up from 31 and 27 in preparation.
Assembly leaf routines recover enough resident space; no larger expansion
is required for this change.

Larger banked hardware remains an option. For example,
[UltiMem's hardware documentation](https://www.go4retro.com/products/ultimem/)
describes independently mapped 8 KiB banks and configuration registers.
Such a target could hold CPU-side background caches or pre-shifted assets,
but needs cartridge-specific loading, mapping and emulator checks. It does
not enlarge RAM directly visible to the VIC. The user has agreed that a
larger real-hardware configuration can be considered if useful.

## Validation

```sh
make test
python3 tests/performance.py --output build/performance/bounded-board-rebuild
make vice-test
python3 tools/arcade/vice_check.py --maze-flash --output build/maze-flash/vice-bounded-rebuild
```

There are 36 regression tests: the preceding 28 plus eight focused checks:

- Every screen/color dirty address, in shuffled order.
- All supported bulk tasks against original Z80 ROM video writes, using varied
  starting tiles, colors, pills and palette parameters.
- Writes behind/ahead of a cursor, compared with a fresh full redraw.
- Full invalidation in every rebuild phase and eventual convergence.
- The split native ghost-state clear against the original ROM.
- A complete forced transition, eight flash phases, bounded input/audio gaps,
  original bulk-task order and queue capacity. Maximum occupancy is 11 entries
  in the 32-entry task ring.
- A coin accepted before an active rebuild finishes.
- Final composition using actors that moved during the rebuild.

Isolated bulk tests measure at most 6,714 cycles per slice; the live transition
sample measures 5.56 ms. These bounds cover the tested paths. Ordinary sprite
frames can still exceed an arcade tick. The smoke run covers attract/credit/
play screens, all intermissions, over 7,000 ticks, the IRQ vector and stack
guard. VICE checks boot, coin/start, non-silent audio, all flash phases,
visible partial rebuilds and a settled next board. Real NTSC hardware has
not been tested.
