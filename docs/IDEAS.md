Your document already diagnoses the problem precisely. The blink isn't caused by missing a back buffer. It's caused by the live glyphs passing through a state that should never be visible: the playfield with the actor removed. A double buffer is one way to hide intermediate states. The other way is to never write one. Below are four ideas, roughly from most radical to most incremental.

## 1. Glyph pool: per-cell double buffering by swapping character codes

This is the "different painting mechanism" I'd seriously consider.

Treat each cell's home code (cell *i* → code *i*) as the **clean background only**. Actors are never stamped into home glyphs. Every cell an actor touches gets displayed through a code borrowed from a free pool.

- **Drawing an actor cell:** take a free pool code, copy the home glyph's 16 bytes into it, and stamp every actor overlapping that cell in priority order. Then write `matrix[cell] = poolcode`. That last step is a single-byte write, so it's atomic.
- **Erasing an old cell:** write `matrix[cell] = cell`. That's one byte. Restoring a whole actor box takes four `STA`s.
- **Freeing:** the old pool code goes back on the free list as soon as the matrix stops pointing at it.

What this buys you:

- The beam only ever sees a cell's old glyph or its new glyph. There is no window in which the actor is missing.
- Underlays go away, along with the 36 bytes per actor, the restore pass, and the topmost-first/reverse-paint ordering. Priority is resolved inside each composed glyph.
- The overlap-marking logic gets simpler, because a shared cell is just composed with two actors in it.
- Dots and digits write straight into home glyphs, which is a final state, so they're safe. If that cell is currently showing a pool code, mark it dirty so it gets recomposed.
- The progressive board rebuild also writes home glyphs, so it can't disturb actors at all.

Draw new cells before erasing old-only cells. The worst case a mistimed beam can show is then an actor briefly in *both* positions. That reads as motion blur, not a blink.

**The memory cost.** Six actors touch at most 24 cells, so you need about 24 spare codes plus some slack. You have 256 − 196 = 60 codes above the bitmap. They're currently used by the output-port image (16 codes) and the C stack (44 codes). Neither needs to be visible to the chip.

You also have $0400–$0FFF, 3K that main wipes after boot and that the VIC *can't* see. That makes it an ideal home for the software stack and the port image. Moving them there frees all 60 codes. Moving only the stack (44 codes) would probably still be enough.

**The time cost** should be in the same range as your current restore plus paint. Per actor cell you do a 16-byte copy and a stamp, instead of a save, a restore and a stamp. Unrolled copies help. One optimization: when a cell stays occupied by the same pool code between refreshes, recompose it in place, writing each byte only once with its final value. That's also blink-free.

## 2. Write-once compositing, if you can't free the codes

This is the same principle without the pool. Keep a shadow of the clean background (196 × 16 = 3,136 bytes) in expansion RAM. The chip doesn't need to see it.

For each dirty cell, compute every byte in a register and store it once:

```
lda bg_shadow,y
and mask1,y : ora shape1,y
and mask2,y : ora shape2,y   ; further actors in priority order
sta live_glyph,y
```

No live byte ever holds "playfield without actor." The beam can catch a cell half-updated, which looks like a tear between old and new rows, but it can never catch the actor gone. Cells that are only in the old box get plain background bytes, which is their final state.

This removes the underlays and the restore pass, and probably costs less than what you have now.

## 3. Lock the clock to the raster, then schedule around the beam

Check this against your measurements, but if I have the 6560 figures right, an NTSC frame is 65 cycles × 261 lines = 16,965 cycles. Your timer period is 16,875. The tick would then run about 90 cycles ahead of the frame each time, slipping roughly 1.4 scanlines per frame and wrapping about every 3 seconds.

If so, your refresh lands at a different beam position on every tick. That makes blink and tear behaviour shift over time and makes beam-aware scheduling impossible.

Two ways to fix it:

- **Sync the timer to the frame.** Start timer 1 from a known raster line by polling `$9004`, and set the latch to the frame length. The game runs about 0.5% slower than the arcade's 60.61 Hz, which no one will notice.
- **Keep the logic clock and trigger only the refresh from the raster.**

Once the phase is fixed, you can sort dirty actors by y and update each one just after the beam passes its band. That gives you nearly a whole frame before the beam comes back to it. With idea 1 or 2 in place this is just polish that removes tears. With your current scheme it would also shrink the blink a lot, as long as each actor's restore and repaint are done together rather than split across the tile pass.

## 4. Fix the hitching with frame pacing, not more work

Going from 52 refreshes a second to 33, with every skipped refresh dropping the whole picture, is probably more visible than the average rate. Even, steady motion looks smoother than jittery motion at a higher rate. Some options:

- **Partial refresh instead of all-or-nothing.** With a pool or write-once scheme, actors are independent, so you can refresh as many as the remaining time allows. Always do the player first, then rotate through the opponents.
- **Render from a published snapshot.** The game update copies the six actors' position, frame and palette into a small buffer when it finishes. The renderer, possibly running from a raster interrupt, always draws the latest snapshot. Logic overruns then delay the data, not the picture.
- **If you can't sustain 60, pick a fixed 30 Hz render rate.** A locked 30 Hz will probably look steadier than a rate that wanders between 33 and 52.
- **Profile the steering path.** Holding the joystick costs nearly 20 refreshes a second, which suggests something in the update gets much more expensive while turning. That may be the cheapest win available.

If I were picking, I'd move the stack and port image into $0400–$0FFF and build the glyph pool (1). That replaces the part of the architecture that causes the blink, rather than racing it. Then I'd add the raster lock (3) and partial refresh (4) on top. Write-once compositing (2) is the fallback if relocating the stack turns out to be painful.

I can sketch the pool allocator and the compose routine in 6502 or in your C if that would help.
