# Next optimization candidates

Review of the accepted glyph-pool build (`pool-ghost-row-fast`, all fourteen
`*_FAST` flags) on 2026-11-05. Nothing was rebuilt or newly measured. The
figures come from the saved instruction profile in
`build/pool-ghost-row-fast/evaluation/trial-cpu/active.profile` (PRG SHA-256
`e148017c…`) and its `pool-profile.log` bucketing. The adapted C core
(`src/arcade/core.c`) and the linked ELF are not in the tree, so the
game-logic items are inferred from profile addresses and label ranges only.

## Where the time goes

| Measure | Value |
| --- | ---: |
| Idle time (`frame_wait`) | 0.16% of CPU |
| Mean native refresh | 15,290 cycles |
| Game logic and audio per tick | ~8,280 cycles |
| Two ticks plus one refresh | ~31.8k of 33.75k cycles |

The CPU is fully busy. A two-tick window leaves only about 2k cycles of slack
for one refresh, so an ordinary logic spike pushes a gap to three ticks. Every
saving below makes that less likely.

Logic runs every tick, but a refresh only happens about every 1.8 ticks. A
cycle saved in logic is therefore worth about 1.8 cycles saved in the renderer.

Refresh cost by renderer area (cycles per completed redraw):

| Area | Cycles | CPU |
| --- | ---: | ---: |
| Generic shifted stamping | 3,366 | 11.2% |
| Home-glyph copy (`pool_copy`) | 3,235 | 10.8% |
| Cell lookup and allocation | 2,078 | 6.9% |
| Actor pose and setup | 1,832 | 6.1% |
| Restore control and publish | 1,552 | 5.2% |
| Pre-shifted normal-ghost stamping | 717 | 2.4% |
| Destination setup | 629 | 2.1% |
| Colour and pointer | 257 | 0.9% |
| Reuse guard | 72 | 0.2% |

Counters from the same run: 10,971 cell lookups, 10,496 fresh cells,
475 shared-cell hits, 2,681 generic calls and 944 pre-shifted ghost calls.

## Candidates, best payoff first

### 1. Don't copy rows the stamp will overwrite

Estimated saving: about 1,000–1,200 cycles per refresh (~7%).

Each fresh cell copies all 16 home bytes, about 208 cycles, and about 15.5
cells are fresh per refresh. The stamper then reads those bytes back to OR
the actor in.

For a fresh cell, let the stamper read from the home glyph and write to the
pool glyph. Only rows outside the actor's 12 need a plain copy, about 20 of
the 32 bytes in a two-cell column. A cell already allocated by an earlier
actor uses the pool glyph as both source and destination, so overlaps stay
correct.

Catch: rows the stamper currently skips (empty source rows, the ghosts'
transparent first and last rows) must become plain copies for fresh cells.

### 2. Treat each column as one 32-byte strip

Estimated saving: about 300 cycles per refresh. It also makes #1 simpler.

A cell's home code is `col*14 + row`, so the cell below is the next 16 bytes
in memory. `pool_setup` allocates top-left, bottom-left, top-right,
bottom-right, so two fresh cells in a column are also adjacent in the bank.

When the bottom pointer equals the top pointer plus 16, the stamper can run Y
from 0 to 27 without a break. That removes the `cpy #16` test and the pointer
swap (about 5 cycles per row) from `pool_row` and `pool_draw_ghost`. The copy
becomes one loop per column, and the partial copy from #1 becomes two simple
ranges: rows 0…t and t+13…31, where t = `v_sy & 15`.

Fall back to the current path when a cell was shared (475 of 10,971 lookups,
about 4%).

### 3. Game-logic hot spots

These count at the higher per-tick weight.

- **A 16-iteration loop inside `main` (`$3547`–`$3580`).** It runs exactly 16
  times per tick (19,312 = 16 × 1,207) and costs about 475 cycles a tick, 2.8%
  of all CPU. It looks like a fixed scan of a table. If most entries are
  usually empty, a count or bitmask of active entries would remove most of
  the work.
- **`updateGhostStates_1017`**: 5.1% of CPU, still the largest single game
  routine.
- **`arcade_ptr`**: about 3.2 calls per tick at around 70 cycles each.
  Inlining it or using a lookup table would help.
- **`__mulqi3`**: once per tick. If the multiplier is a constant, a shift-add
  or table replaces it.

### 4. Find out why most ghost draws use the generic stamper

Estimated saving: up to about 500 cycles per refresh.

Only 944 draws took the pre-shifted ghost path. About 678 of the 2,681 generic
calls are Pac-Man, so roughly 1,700–2,000 ghost draws went generic. A generic
call averages about 851 cycles; a pre-shifted one about 515.

Likely causes:

- The up-facing frames (codes 38 and 39) are not in `arcade_ghost_shifted`.
- Edge-clipped ghosts (`v_flags != 3`) always go generic.
- The pool build no longer links the frightened table that `bitmap.S` still
  references.

Count which branch rejects them before adding data. Memory is the limit
(141 bytes free in BLK1–3, 23 in BLK5). For a horizontally symmetric mask,
shift 8−s is shift s with its two halves swapped and bit-reversed. Storing
only shifts 0–4 cuts each table from 320 to 200 bytes, at the cost of a
`bit_reverse` lookup on the mirrored shifts.

### 5. Try locking redraws to every other tick

This is a presentation experiment, not a speed change. The
[rate-match diagnostic](RATE_MATCH.md) found a mix of 1-, 2-, 3- and 4-tick
gaps between completed renders. Admitting refreshes only on even ticks would
lower the average from about 34 to 30 redraws a second but make the gaps
even. Uneven motion is one of the two reported faults, so this needs a live
comparison. Spare time would go to the existing bounded slice work.

### 6. Small, cheap wins

Each is worth roughly 100–250 cycles per refresh.

- **Publish and settle loops.** Index the tables at `pool_cells-196` and
  `pool_colours-196` so X already holds the character code, removing
  `txa; clc; adc #196` per cell. Making `pool_limit` a zero-page byte or a
  patched immediate saves a little more.
- **`pool_clear_map`.** Unrolling it four times saves about 100 cycles per
  refresh for roughly 10 bytes.
- **One row loop per shift.** Giving each shift amount its own copy of the row
  loop removes the two or three `jmp`s per row (about 240 cycles). It costs
  code space that is not available yet, so it follows #1 and #2.

## Validation

The existing checks cover each candidate: the 8,768 complete-scene oracles,
the 10,496 generic-stamper cases, the 1,207-state native replay and the
sound-register replay. #1 and #2 belong in one change behind a single build
flag (for example `POOL_STRIP_FAST`), measured on the same saved route as the
earlier pool trials.
