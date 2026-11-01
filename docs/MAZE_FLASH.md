# End-of-stage maze flash

The end-of-stage blue/white flash now changes VIC colour cells while retaining
all maze pixels. Previously each palette fill triggered a full bitmap rebuild,
which took roughly 787 ms and could stretch the gap between draws to 1.6 seconds.

The native palette entry recognizes the original flash states and writes the
same 896 maze and 64 border palette bytes as the arcade routine. Other palette
tasks keep the original full path. Game-state transitions and timers are unchanged.

A 25-byte coverage map records which VIC cells contain maze walls. Dot removal
cannot discard a wall that shared its cell. Full scene rebuilds clear and
recreate the map. Before recolouring, the compositor restores all actor
underlays, processes any ordinary background changes, updates covered cells,
and redraws the actors. Score text and fruit history retain their colours;
sprites retain their normal colours and priority. A sprite sharing a wall cell
still causes the usual VIC colour clash.

The map uses `$0FE2–$0FFA`; its pending flag uses `$0FFB`. General bulk fills
remain out of line to fit the additional code. The flash revision's link had 31 bytes free
in BLK1–3 and 27 bytes in BLK5.

## Verification

```sh
make test
python3 tools/arcade/vice_check.py --maze-flash --output build/maze-flash/vice
```

All 28 tests pass, including three new flash tests:

- 64 comparisons against full redraws cover every fruit/history type, the
  sprite pixels and colours, and their restored backgrounds.
- A complete native sequence presents all four white/blue pairs. Each request
  is visible within 17 ms; changes are about 198 ms apart, matching the original
  12-tick interval. The longest audio-update gap during flashing is about 25 ms.
- Incremental dot erasure preserves wall coverage and matches the full redraw
  in every cell containing visible pixels. Empty cells may retain unused
  foreground colour bytes after dot erasure.

The palette writes and hardware recolour together take at most 11,855 cycles,
about 11.6 ms at the NTSC CPU clock. VICE independently observes all eight
phases in order, verifies their hardware colours, and captures an animation.
Board completion is injected for these checks; it is not a natural playthrough.

`build/maze-flash/preview.gif` is the native simulator capture, and
`build/maze-flash/vice/vice-maze-flash.gif` is the VICE capture. Timing reports
and the 64-case renderer report are beside them.

This revision addressed flashing only. The later
[bounded rebuild](BOUNDED_REBUILD.md) services input, logic and audio during
progressive next-board construction. Its coherent draw gap is longer, about
1.8 seconds, while audio updates continue within about 30 ms in the sample.
