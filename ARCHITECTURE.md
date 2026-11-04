# VIC-20 architecture

How the NTSC build draws, makes sound, and keeps time. The game rules are a C translation of the original arcade program, compiled to native 6502. A platform layer presents the joystick, the video chip, and the sound registers. The rules stay on their own clock when a picture update does not finish in time.

The machine is an expanded NTSC VIC-20: the 3K expansion plus blocks 1, 2, 3, and 5. PAL is not supported.

## How the visuals are drawn

The 6560 has no sprites and no bitmap mode. It paints a grid of programmable characters, reading the screen matrix and the character definitions on every scan, about 60 times a second. The bytes in that memory are the picture the beam is showing.

The grid is 14 columns by 14 rows of double-height characters. A character is 8 by 16 pixels, so the grid is 112 by 224. The game uses 112 by 216 of that, and the last eight scanlines stay black. The screen matrix is at `$0200`. Each of the 196 cells has its own character code. Those definitions occupy `$1000`–`$1C3F` and are the framebuffer. Columns are stored vertically, so the twelve scanlines of an actor are contiguous bytes and the painter can walk them with an index.

An actor is an 8 by 12 image placed on a pixel, not on a cell boundary. There are eight horizontal alignments inside a column. A shifted actor covers two columns, and most vertical positions cover two rows, so one actor touches up to four cells. The shape is written into the definitions those cells already have. There is no separate sprite plane above the playfield.

Six actors are tracked. Each keeps a 36-byte underlay: the bitmap bytes and colour nibbles that were in its cells before it was drawn. Colour RAM, at `$9600`, stores one foreground colour per cell. Drawing an actor writes that colour into every cell it covers, so walls, dots, and lettering in those cells take the actor's colour until the underlay is restored. The playfield is a single light colour so the tint is less noisy. A completion flash recolours wall cells in place and does not rebuild the bitmap.

A refresh of the moving actors runs in four steps.

1. Mark the actors that changed. Position, frame, flip, and palette all count, as does a queued tile in the actor's vertical band. An actor whose old or new box overlaps a dirty actor is marked too, so a shared cell is restored and redrawn in priority order.
2. Restore each dirty actor from its underlay, topmost first. The playfield shows through where the actor was.
3. Paint the queued background tiles into the live columns. Dots, digits, and other small edits sit in a queue of at most 20 tiles, with a 128-byte bitset so the same cell is not queued twice. Anything larger becomes a progressive rebuild, drawn in slices across later ticks.
4. Stamp the actors back in the reverse order, and save a new underlay under each one. The last actor painted is the one on top. The output list can swap two slots before this pass, and the paint order follows the list it is given.

Unchanged actors are left on screen. A stationary actor outside the dirty bands stays up through a score change or a dot eaten somewhere else. A band is 32 pixels high and ignores horizontal distance, so it sometimes redraws an actor that did not need it. It does not miss a shared colour cell.

The video chip can see `$0000`–`$03FF` and `$1000`–`$1FFF` only. Code and the large tables are in the expansion RAM, which the chip cannot display. The 196 glyph definitions fill the bottom of the display window. The 256 bytes above them hold a copy of the arcade machine's output ports. The remainder, up to `$2000`, is reserved for the software stack. A second copy of the picture does not fit in memory the chip can read.

The chip also has a hard limit of 256 character codes. A library of pre-drawn cells, one picture for every pose over every background and every overlap, is far larger than that. One actor at every pixel offset is on the order of a hundred pictures per pose, before a second actor shares the cell. The screen already spends 196 codes on unique cells. The picture is edited in place because that is the set of glyphs that fits.

## Audio

Note choice, waveforms, envelopes, and the moments when an effect takes over a musical voice all stay in the original game routines. Those routines write a block of sound registers. Once per tick the platform reads three voices from that block and programs the 6560.

The chip has three square-wave voices, one noise voice, and a single volume shared by all of them. The noise voice is held off. Each frequency word is shifted according to that voice's waveform, then matched to the nearest hardware divider. The match is a seven-step comparison against a 128-entry table built for the NTSC clock of 1,022,727 Hz. The shared volume is set to the loudest voice that is currently sounding. The same register also holds the auxiliary colour in its high half, so a volume write keeps the high half at the value the picture uses.

Cue order and interruptions follow the original registers. The tone is a square wave, and a quiet voice is played at the same volume as the loudest one.

## Program structure

Resident code is linked at `$2000`, in blocks 1–3. Read-only tables, decoded artwork, and the cold sound path sit in block 5 at `$A000`.

Startup runs from `$0400`. That stub sets the stack, copies zero-page constants, programs the video registers, and clears the picture. It then jumps to the resident main, which wipes `$0400`–`$0FFF`. The boot image is not kept. Idle time later in the session can paint a slice of a board rebuild. It does not bring the boot code back.

The game clock is timer 1 on the second VIA. The latch is `$41E9`, so the period is 16,875 cycles: about 60.606 Hz at 1,022,727 Hz. The interrupt increments a tick counter and returns. The KERNAL keyboard scan does not run on that interrupt. The joystick is read from the VIA ports. Coin and start are read from the keyboard matrix on the same ports.

The main loop waits until the tick changes. During the wait, one bounded slice of a board rebuild or another bulk job may run. When the tick arrives the loop reads controls, runs one original game update, runs the queued tasks, and maps the sound registers onto the VIC. It refreshes the picture only when the tick counter is still on the tick just consumed. If the body overran, the refresh is skipped and the next wait returns at once, so the rules can catch up. The 16,875-cycle clock keeps the game. The picture updates when the loop has time left.

The original update still walks the arcade memory image: actor state, timers, collision, score, and the task list. Coordinates stay in arcade units until the renderer converts a dirty actor to a pixel position. A few output routines are native replacements for hardware the VIC does not have. Everything else the renderer and the audio mapper need is in the register image those routines already write.

## Flicker

Two different faults show up in play.

An actor blinks because the video chip is reading the same bytes the processor is editing. A dirty actor is restored to the playfield, the queued tiles are written, and only then is the actor drawn again. If the beam scans those cells in between, it shows the playfield with the actor missing. A later scan shows the actor. The gap is the whole actor, not a torn row.

The actor painted on top is erased first on the next refresh, so that actor is missing for every other restore, every tile write, and every earlier repaint. The player actor is erased near the end of the list and painted near the start. The other actors are drawn while that actor is still on screen, or after it is already back. Its own gap is the tile writes, plus whichever transient object occupies the last slot. The opponent drawn on top carries the long gap, and during a chase that opponent is usually the one beside the player.

A both-column restore is about 0.3 ms. Painting one pre-shifted opponent is about 0.6 ms. The measured span from the start of an actor's restore to the end of its repaint averages about 5.7 ms in ordinary play, and the 95th percentile is about 10.8 ms. A frame is 16.7 ms. The painters are the short part. The wait between restore and repaint is the blink.

Motion also hitches, for a separate reason. The 60.606 Hz update always runs. A refresh is started only when it still fits in the current tick. An opening stretch with little steering completes about 52 refreshes a second. The same build with the joystick held over completes about 33. A skipped refresh leaves the old pose up, and the next one that lands shows a later position. Work added to hide the blink has, so far, lowered that completion rate until the motion looked the same or less steady. The hole on paper got shorter. The beam still caught actors missing, and it caught them less often only because fewer pictures were published.

The limits under both faults are the same ones in the drawing section. There is no second picture to draw into. Pointing the chip at the other screen page would still address these glyph definitions. The character codes above the bitmap are the stack and the output-port image. A stored catalog of every overlap does not fit in 256 glyphs. Leaving stationary actors alone removed the blinks that came from unrelated tiles. An actor that moved still has to come off the live picture before the playfield and the new position can be written back.
