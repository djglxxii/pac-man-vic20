# Response to IDEAS\_REPLY.md

Nov 3, 2026 · @David

Thanks for checking these against the source and the earlier trials. Most of the corrections stand, and I withdraw the claims below. A few points can be made concrete. But the experiment history changes what I think the next step should be.

## Withdrawn

- **$0400–$0FFF.** I read "wipes" as "frees." That was wrong: the range holds the logical screen, colour attributes, arcade RAM and the dirty/cache state. That idea is dead.
- **"24 plus slack."** This had no commit sequence behind it. A proper bound is below.
- **"Blink-free" and "worst case is motion blur."** Neither was verified. A mixed old/new cell is still possible.
- **The write-once fallback (idea 2).** It has no place to keep a 3,136-byte shadow, so it is out under the current memory target.
- **"Beam-aware scheduling is impossible."** BEAM\_FOLLOW.md shows otherwise.
- **Slowing the logic clock.** The arcade clock is a project constraint and stays.
- **Joystick steering as the cause of 52 vs 33.** Those figures come from different workloads, so the comparison doesn't hold.
- **IRQ rendering as cheap.** Self-modifying painters and shared scratch state make it a real redesign.
- **Equal or lower cost.** I have no cycle evidence for this.

## Pool details that can be made concrete

These only matter if the pool goes forward. I'm not recommending that yet; see the last section.

**Home glyphs replace the shadow.** In the pool design the home glyphs are the clean background, so idea 2's memory problem doesn't carry over. Restoring a cell means looking up its home code through the row-major/column-major mapping table, not writing `matrix[cell] = cell`. Thanks for catching that.

**Commit sequence and capacity.** The unit of update is an overlap group: a set of actors whose new or old footprints share cells. For each group in turn:

1. **Check capacity first.** The group needs one free code for each of its new-footprint cells that isn't already pool-backed, plus one transient code. If those aren't free, defer the whole group. Its previous pose stays fully displayed, which is the same outcome as a skipped refresh today.
2. **Publish each new-footprint cell.** Compose it with every displayed actor that covers it, in priority order. Publish the screen code, then the colour. Release the cell's previous pool code.
3. **Settle each old-only cell.** If another displayed actor still covers it, recompose it as in step 2. Otherwise restore the home code and home colour, and release the pool code.

Peak usage is the codes already displayed, plus the current group's newly backed cells, plus one. The pool must be larger than the maximum number of displayed actor cells, or deferral can stall indefinitely. The common case of moving 1 px inside the same 2×2 footprint needs only the transient code.

**Colour publication order.** For a cell taking on an actor, the safe order is screen code first, then colour. The intermediate state is the actor's bits shown in the playfield colour, so the actor is wrongly coloured but present. The reverse order (tinted cell, no actor) is the failure mode the temporary-character trial hit.

For a cell losing its actor, either order gives a brief tinted-wall state or a wrongly coloured actor, and neither is an absence. The mismatch lasts two stores, a few cycles. That doesn't prove nothing is visible, but it is a much smaller exposure than a millisecond erase gap.

If the home colour is the single playfield colour, or derives from the flash state, no 196-entry colour table is needed.

**Where the virtual I/O image could go.** Removing the six underlays frees 216 bytes. Together with the 315 bytes of resident headroom, that is 531 bytes before the new renderer's code and metadata. That could hold the 256-byte I/O image, which would add 16 codes to the 24 the shadow trial already proved, for 40 in total.

Whether it fits depends on the new renderer's code size versus the old one, which nobody knows yet. The I/O image may also be tied to a fixed address. Treat this as a candidate to check against the map, not a plan.

**Rebuild.** I agree that keeping actors absent during a rebuild, as now, is the right first version.

## What the experiment history changes

This matters more than any of the details above.

Three trials attacked the erase gap: preserving glyph bits, following the beam, and per-actor commit. Per-actor commit cut the mean erase-to-paint window by more than half, from 5.66 to 2.54 ms. All three lowered render throughput by roughly 22–37%, and in every case user review found no perceptible improvement.

There are two explanations, and the A/B reviews can't distinguish them:

- **H1:** the erase gap isn't the main thing being perceived. Halving it should have roughly halved the chance of the beam catching an actor missing. If that produced no visible change, the visible problem may be something else. The likeliest candidate is uneven pacing: at \~33 renders per 60.6 ticks, actors advance by irregular 1-, 2- and 3-tick steps, which reads as jerky or "flickery." Cell colour changes as actors move are another possibility.
- **H2:** the gap fix does help, but the throughput loss cancels it out.

Under either explanation, throughput is the binding constraint. Any new renderer that costs more than the current one will probably fail review the same way, however clean its publication rules are. The glyph pool might cost less than save/restore, or it might not, and the history says to find out which problem dominates before building it.

## Proposed next step: two diagnostics before any new renderer

1. **Rate-matched A/B.** Throttle the baseline renderer to the actor-commit build's render rate and skip pattern. Then compare the two on the same input trace.
   - If actor-commit looks better at matched rate, the gap fix works and cost is the whole problem (H2).
   - If it doesn't, the erase gap isn't what people are seeing (H1).
2. **Objective per-frame measurement.** Record VICE output at the full frame rate alongside a per-tick log of actor positions written to a RAM ring buffer. An offline script then classifies, for every displayed frame and every actor: present, absent, or partial. It also records how far each actor moved since its last displayed pose. That gives blinks per second and a judder histogram, so the next experiment is judged on numbers rather than only on review.

If the result is H1, the work shifts to pacing: an even render cadence and worst-case render interval, measured as above. If it's H2, a pool prototype is justified, and its acceptance test is matching the current throughput on the same trace, not just closing the gap.

I can write the capture-analysis script, or the throttled baseline build, whichever is easier to start with.
