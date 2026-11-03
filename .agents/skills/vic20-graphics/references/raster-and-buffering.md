# Raster Effects, Timing and Double Buffering (NTSC focus)

## Timing facts

| | NTSC 6560 | PAL 6561 |
|---|---|---|
| φ2 | 1,022,727 Hz | 1,108,405 Hz |
| Cycles per line | **65** | 71 |
| Lines per frame | **261** (0–260) | 312 |
| Cycles per frame | **16,965** | 22,152 |
| VIA one-frame latch (lines×cycles−2) | **16,963 = `$4243`** | 22,150 = `$5686` |
| Vertical blank | lines 0–27 | lines 0–27 |

- **The VIC never stalls the CPU** (no badlines, no sprite DMA). Every line is 65 usable cycles, and timing
  is identical anywhere on screen. This makes cycle-exact code practical; the limit is the 65-cycle line.
- **There is no raster interrupt.** Options: poll `$9004`, or run a VIA timer with a period of exactly one
  frame (optionally synchronised to cycle precision).
- The KERNAL's 60 Hz timer (latch `$4289`) is **not** frame-locked; it drifts through the picture.
- NTSC quirk: the 6560 raster counter changes ~37 cycles earlier (relative to the picture) than the 6561,
  i.e. mid-line, and the field has partial first/last lines (32/33 cycles). Don't port PAL raster constants;
  re-time and test.

## Level 1: polling split (simple, jitters by a few pixels)

```asm
; once per frame, from the main loop: wait for the beam, change colours, wait, restore
split:
:       lda $9004
        cmp #SPLIT_LINE/2       ; $9004 = line / 2
        bne :-
        lda #(C_BLUE<<4)|8|C_BLUE
        sta $900f               ; background + border for the lower band
:       lda $9004
        cmp #END_LINE/2
        bne :-
        lda #(C_BLACK<<4)|8|C_BLACK
        sta $900f
        rts
```

Fine for a status bar or sky/ground colour bands where a jittery edge in the border is acceptable. The
loop notices the change 0–7 cycles late (0–28 pixels).

## Level 2: frame-locked VIA IRQ (stable to a few cycles)

Reprogram VIA2 T1 to `$4243` after waiting for a raster line (code in `vic20-system/references/kernal-irq-via.md`).
The IRQ then fires at the same screen position every frame, apart from the interrupt-latency jitter
(0–8 cycles). Use it as the game's heartbeat: music tick, input, page flips, colour splits whose edges
fall in the border.

## Level 3: stable (cycle-exact) raster, `assets/stable-raster-ntsc.s`

Tested in VICE NTSC: a mid-line colour change is pixel-identical across frames. Method (Mike, after Marko
Mäkelä):

1. **Sync:** with interrupts off, poll `$9004` with ever-smaller uncertainty (7 → 3 → 1 → 0 cycles).
2. **Start VIA2 T1** with the one-frame latch at a known cycle. The horizontal position is fine-tuned by a
   delay loop *before* starting the timer.
3. **Jitter removal in the IRQ:** `SEC / LDA #PHASE / SBC $9124` measures the latency (0–8). The result is
   written into the operand of a `BCC`, which jumps into a chain of `LDA #$A9` opcodes (`A9 A9 A9 … A5 EA`).
   Every entry offset costs one cycle less, so all paths leave on the same cycle.

Rules: no IRQ/NMI during sync (disable RESTORE with `$911E = $7F`); keep the sync code and the IRQ server
each inside one page (the asset asserts this); don't remove the first `$9004` check (race condition); set
the horizontal position with `POS`. NTSC constants: `FRAME=$4243, LINE=17, PHASE=21, DELAY=21, POS=5`.
PAL: `$5686, 30, 88, 23, 1` (plus small NOP changes; see the asset header, untested here).

After the slide you own the beam. Each 65 cycles is one line, and 1 cycle = 4 pixels. Things to write mid-frame:

| Register | Effect per band/line |
|---|---|
| `$900F` | background (16 colours), border, reverse |
| `$900E` hi | aux colour (preserve the volume nibble!) |
| `$9005` | switch character set → more unique glyphs per screen, mixed fonts |
| `$9002` bit 7 / `$9005` hi | switch screen matrix |
| `$9000` / `$9001` | shift origin → wobble, split scrolling |
| `$9003` | rows / 8×16 mode (geometry tricks, overscan) |

Budget: a few `STA abs` (4 cycles each) per line, plus IRQ overhead (~40–50 cycles to reach the effect).
A per-line colour change for the whole screen eats most of the CPU. That's fine for title screens, but expensive in games.

Examples in the wild: *Robotic Liberation* (per-scanline global colours, PAL), *Realms of Quest 5* (stable
raster window), the *Pitfall!* port (FLI-style tricks), Mike's "New Frontiers in VIC-Hires-Graphics" (modes up
to ~80K pixels, mostly for still images).

## Double buffering

### Screen + colour page flip (cheap: one register write)

`$9002` bit 7 is address bit 9 for **both** the screen matrix and colour RAM. With the `$9005` screen nibble
fixed, toggling it switches screen `$1000 ↔ $1200` (nibble C) or `$1C00 ↔ $1E00` (nibble F) **and** colour
`$9400 ↔ $9600`. (Verified in VICE.)

```asm
; draw into the hidden page, then flip in vertical blank / bottom border
flip:   lda $9002
        eor #$80
        sta $9002
        lda draw_page_hi        ; swap drawing pointers: screen $10/$12, colour $94/$96
        eor #>($1000 ^ $1200)
        sta draw_page_hi
        lda draw_colour_hi
        eor #>($9400 ^ $9600)
        sta draw_colour_hi
        rts
```

Clear → draw → wait VBL → flip gives flicker-free output ("no flicker at all" in an analysis of a VIC-20 Elite
port). Two screen pages cost 1 KB of VIC-visible RAM.

### Character-set double buffering (expensive)

A second 2 KB set doesn't fit next to screens in 4 KB. Cheaper alternatives:
- Double-buffer only the sprite pool characters (two pools, alternate per frame).
- Keep old/new object state and redraw only dirty cells.
- XOR sprites (no background copies).
- With expansion: keep the logical screen in expansion RAM and copy only dirty regions into VIC RAM in vblank.

### When to flip / update

The frame-locked IRQ placed just below the text window (e.g. `$9004` ≈ 118 on a default NTSC screen) gives
the bottom border + vertical blank (~45–50 lines ≈ 3,000 cycles) for flips, charset updates and colour RAM
writes that must not tear. Update the screen top-down after that so the beam doesn't catch up.

## Profiling with the border

Write a distinct colour to `$900F` at the start of each routine and restore it at the end. The band height on
screen = cost in lines (×65 cycles). If bands wrap past the bottom, the frame is over budget. See the
`vic20-optimization` skill.
