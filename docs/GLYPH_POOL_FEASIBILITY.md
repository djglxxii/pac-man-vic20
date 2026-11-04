# Glyph-pool feasibility: initial memory audit

**Follow-up:** the candidate has now been implemented as the accepted
[glyph-pool renderer](GLYPH_POOL.md). The two 24-glyph banks fit, the full stack is
preserved, and capacity/reuse checks pass. Actual capture shows fewer missing
actors but only 22.07 versus 32.88 previous redraws/s. It missed the original
throughput gate; the user accepted the visible improvement and slowdown after
live play testing, and it is now the default. Optimize speed next. The text
below preserves the initial audit.

Started 2026-11-04 when the user stopped the colour experiment and returned to
[IDEAS.md](IDEAS.md), particularly idea 1. This is Stage 1 of the
[finished-cell plan](FINISHED_CELL_PUBLISHING_PLAN.md). **No pool code or new
linker configuration has been implemented.** The accepted default is unchanged.

## Baseline and a concrete candidate

Use the accepted `build/pacman.prg`, SHA-256
`9fb85cf61add5d729142183a48285041a47e55fa0f0fd16043f0d15b2aae35af`.
Its current resident allocation ends at $7EC5, leaving 315 BLK1–3 bytes and
15 BLK5 bytes. The rejected colour trial's full resident map is not this baseline.

The original proposal's $0400–$0FFF relocation is unavailable: those addresses
remain live game/renderer state. However, a different candidate can preserve
the **entire 704-byte software-stack reservation** while freeing all 60 upper
glyph codes, without changing the period-correct RAM configuration:

1. Replace the underlay renderer, freeing its low-memory storage and obsolete
   resident code.
2. Map the virtual output fields actually used by this native build into low
   RAM, with explicit holes for hardware vectors and other persistent state.
3. Move the software stack to $7D40–$7FFF in existing BLK3 RAM. Its top becomes
   $8000; it retains 704 bytes. Replacement code/data must end at or below $7D40.
4. Reserve $1C40–$1FFF for 60 pool glyphs, codes 196–255. The 196 clean home
   glyphs at $1000–$1C3F keep their existing mapping.

This is an address-level candidate, not a claim that new renderer code already
fits or that the allocator's retirement rule is proved.

## Why the virtual I/O need not occupy 256 exclusive bytes

The declared structure has a 256-byte address span, but the VIC native build's
actual accesses are narrower:

| Access | Current physical address | Candidate address |
| --- | --- | --- |
| Eight output flags (`ARCADE_IO`, including sound enable) | $1C40–$1C47 | $0300–$0307 |
| 32 sound nibbles (`SOUND`) | $1C80–$1C9F | $0340–$035F |
| Sound reset, `memset(SOUND, 0, 0x40)` | $1C80–$1CBF | **Reserve $0340–$037F**, not just 32 bytes |
| Native sprite coordinates | Already redirected to $0C30 | Unchanged |

Source checks: [memmap.h](../src/arcade/memmap.h) defines `REGSWRITE`, `SOUND`
and the separate native `SPRITECOORDS`; [core.c](../src/arcade/core.c)
clears only the first eight output bytes and 64 bytes starting at `SOUND`.
Native `kickWatchdog()` is empty. No accessed watchdog field or input-page
read has been found in this source inventory.

The proposed C structure base would be $0300. Its padding is **not available
for blanket clears or allocations as part of an exclusive 256-byte object**:
it contains the real IRQ/NMI vectors, candidate metadata and the random index.
All actual accesses must remain confined to the used fields above. The current
startup `memset($1C40, 0, 0x100)` must therefore become explicit initialization
of the used fields; simply changing that clear's base to $0300 is unsafe.

The assembly output copy in [bitmap.S](../src/bitmap.S), currently
`STA $1C90,X`, must follow the new sound base: $0350–$035F. C audio reads follow
`SOUND`; the sound-enable byte would move to $0301.

This deliberately reuses memory only after removing underlays. It cannot be
combined with the old renderer's $0320–$03F7 underlays or the stopped colour
trial's $0300 queue.

## Candidate address map

| Address range | Proposed use / constraint |
| --- | --- |
| $0200–$02C3 | Existing 196-byte screen matrix |
| $02C4–$02FB | Existing 56-byte dirty-queue/rebuild/bulk state |
| $0300–$0307 | Eight virtual output flags |
| $0314–$0319 | Preserve live IRQ, BRK and NMI vectors |
| $0320–$033F | 32 candidate metadata bytes from removed underlays |
| $0340–$037F | 64-byte sound/reset range |
| $0380–$03F7 | 120 candidate metadata bytes from removed underlays |
| $03F8–$03F9 | Preserve the random-sequence index |
| $0400–$0FFF | Existing logical video, arcade state and renderer metadata |
| $1000–$1C3F | 196 clean home glyphs, 16 bytes each |
| $1C40–$1FFF | 60 pool glyphs, 960 VIC-visible bytes |
| $2000–$7D3F | Resident code/data, with a new upper bound |
| $7D40–$7FFF | 704-byte software stack; top $8000 |
| $A000–$BFFF | Existing BLK5 tables; currently 15 bytes free |

Other currently unused holes are not counted as allocations. Existing caches
at $0F80–$0FE1 may be redesigned only with their live-state roles accounted for.
The two metadata fragments total **152 bytes**; they are not one contiguous
buffer. New metadata has not yet been fully specified or allocated.

## Resident code budget

The current linker map gives an initial replacement budget:

| Resource | Bytes |
| --- | ---: |
| Current resident headroom | 315 |
| Entire `.text.sprites` frontend, if replaced | 1,232 |
| `bitmap_setup` through the old sprite painters, if replaced | 390 |
| Total space before reserving relocated stack | 1,937 |
| Preserve software-stack reservation | −704 |
| **New resident renderer/extra-data budget** | **1,233** |

The 390-byte range is $2061–$21E6. The preceding 23-byte
`arcade_prepare_outputs` routine at $204A–$2060 remains needed and is not counted
as reclaimed. Only the old sprite frontend calls the setup/erase/painters in
the current native source. Background tile rendering remains separate.

This budget assumes replacing those routines completely. Reused old code counts
against it, along with new grouping, allocation, colour publication, copying,
stamping and metadata not placed in the candidate low-memory fragments. Compiler
and linker changes may alter sizes/alignment; a successful link and complete
transaction measurement are required. The budget does not establish lower cost.

## Capacity and retirement still need proof

One six-slot displayed pose touches at most 24 cells. Arbitrary old/new poses
can occupy 48 distinct cells. Reserving one additional transient glyph gives a
**49-glyph conservative starting budget before retirement delays**. A 60-glyph
layout would leave 11 beyond that count, but the number is not a proved bound
on glyphs that the VIC may still read after a matrix update.

The next audit must specify exactly when a glyph can be overwritten, tie the
capacity bound to the actual reserve/compose/publish/release sequence, and ensure
progress for cell crossings, connected overlap groups, teleports/appearance,
rewards and background changes. Do not rely on "24 plus slack", immediate reuse,
or a stack footprint observed only in smoke.

The old home mapping remains essential: screen cell `r*14+c` maps to home glyph
`c*14+r`. Complete glyph publication still needs a separately ordered live
colour store; this requirement does not resume the stopped colour experiment.

## Integration checks before a benchmark can become a live trial

- Define and bound metadata within the 152-byte fragments and retained cache
  space, including displayed/pending poses, free codes and retirement state.
- Use linker assertions for resident end <= $7D40, pool/stack separation, low
  RAM fragments and preserved vectors/random state.
- Update native fixtures that currently load all 256 I/O bytes or access
  $1C80/$1C41 directly. They must load the used fields without overwriting vectors.
- Update stack observers: `vicsim` and some checks currently assume a $2000
  software-stack top. The moved stack must be measured relative to $8000;
  retaining the existing observed 32-byte figure would be misleading.
- Update startup initialization and every fixed-address output access. Preserve
  logical audio/arcade parity, full-stack guards and loader verification.
- Complete a costed transaction benchmark before wiring this to live play.
  The actual-capture target remains approximately 33 redraws/s, with no automatic
  promotion based on a shorter erase window or an isolated copy timing.

**Initial finding:** a promising layout exists without shrinking the stack or
adding hardware. Stage 1 remains incomplete until metadata, glyph retirement
and capacity/progress rules are proved. No complete feasibility result or
implementation is claimed here; this audit records the candidate.
