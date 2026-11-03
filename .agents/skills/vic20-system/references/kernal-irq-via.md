# KERNAL, Interrupts and the 6522 VIAs

Addresses verified against the VIC-20 KERNAL ROMs 901486-06 (NTSC) and 901486-07 (PAL); the routines below
are identical in both.

## Interrupt flow

```
IRQ  -> $FFFE -> $FF72: PHA / TXA / PHA / TYA / PHA / TSX / LDA $0104,X / AND #$10
                         BEQ -> JMP ($0314)   (IRQ;  default $EABF)
                         else   JMP ($0316)   (BRK;  default $FED2)
NMI  -> $FFFA -> $FEA9: SEI / JMP ($0318)     (NMI;  default $FEAD; nothing pushed yet!)
RESET-> $FFFC -> $FD22  (checks for the $A000 cartridge signature first)
```

The default IRQ handler `$EABF` updates the jiffy clock, blinks the cursor, handles the tape motor and **scans
the whole keyboard (SCNKEY)**: about 650+ cycles every frame. It ends:

```
EB12  JSR $EB1E    ; SCNKEY
EB15  BIT $9124    ; read VIA2 T1 low byte -> clears the T1 interrupt flag
EB18  PLA
EB19  TAY
EB1A  PLA
EB1B  TAX
EB1C  PLA
EB1D  RTI
```

- **`JMP $EB15`**: acknowledge VIA2 Timer 1, restore Y/X/A, RTI. The usual exit for your own handler when the
  interrupt came from VIA2 T1.
- **`JMP $EB18`**: restore and RTI only. Use it when you already acknowledged the source. If VIA2 T1 isn't
  acknowledged, the IRQ fires again at once and the machine locks up.
- **`JMP $EABF`**: chain to the full KERNAL handler (keyboard, jiffy clock, cursor). Use when you still need
  `GETIN`, the `TI` clock, or the BASIC editor.

The NMI handler you install at `$0318` gets control with **no registers saved**. Push what you use and end
with `RTI`. The KERNAL NMI path also checks the RESTORE key and the cartridge warm-start vector.

## Taking over the IRQ (game pattern)

```asm
        sei
        lda #<game_irq
        sta $0314
        lda #>game_irq
        sta $0315
        cli
        ...
game_irq:                       ; A/X/Y already pushed by the ROM at $FF72
        inc frame_count
        ; music tick, input sampling, page flip...
        jmp $eb15               ; ack VIA2 T1 + restore + RTI
```

This saves the keyboard scan (~4% of the frame) and the jitter it causes. You lose `GETIN`/`TI$`/cursor; read
the joystick and the few keys you need directly (`input.md`).

## Frame-locked IRQ (NTSC)

The KERNAL programs VIA2 T1 with latch **$4289 (17,033)** on NTSC (`$4826` on PAL), which is close to
but **not** one video frame, so the IRQ drifts slowly up the screen. Reprogram it to exactly one frame
and start it on a known raster line:

| | NTSC 6560 | PAL 6561 |
|---|---|---|
| Cycles per line | 65 | 71 |
| Lines per frame | 261 | 312 |
| Frame latch = lines × cycles − 2 | **16,963 = `$4243`** | **22,150 = `$5686`** |

```asm
FRAME = 261*65-2
        sei
        lda #$40
        sta $912b               ; VIA2 ACR: T1 continuous (free-running) interrupts
        lda #<FRAME
        sta $9126               ; T1 latch low
:       lda $9004               ; wait for raster line 2*N (bits 8-1)
        cmp #N
        bne :-
        lda #>FRAME
        sta $9125               ; T1 counter high: loads counter from latch, starts, clears flag
        lda #$c0
        sta $912e               ; IER: enable T1 interrupt (bit 7 = set)
        cli
```

This is stable to within a few cycles (the polling loop's granularity). For cycle-exact raster effects you
need a proper sync and jitter correction. See the `vic20-graphics` skill (raster effects).

The −2 accounts for the 6522 counting through 0 and `$FFFF` before reloading.

## Disabling RESTORE / NMIs

```asm
        lda #$7f
        sta $911e               ; VIA1 IER: disable all VIA1 interrupt sources (RESTORE is CA1)
```

Do this in games: a RESTORE press otherwise jumps into the KERNAL NMI handler mid-game, and an NMI during
stable-raster synchronisation permanently shifts the raster timing.

## 6522 VIA register map

| Offset | VIA1 | VIA2 | Register |
|---|---|---|---|
| +0 | `$9110` | `$9120` | ORB/IRB: port B data |
| +1 | `$9111` | `$9121` | ORA/IRA: port A data (with handshake: reading/writing clears CA1/CA2 flags) |
| +2 | `$9112` | `$9122` | DDRB (1 = output) |
| +3 | `$9113` | `$9123` | DDRA |
| +4 | `$9114` | `$9124` | T1 counter low (read: **clears T1 interrupt flag**; write: latch low) |
| +5 | `$9115` | `$9125` | T1 counter high (write: latch high → counter, start, clear T1 flag) |
| +6 | `$9116` | `$9126` | T1 latch low |
| +7 | `$9117` | `$9127` | T1 latch high (write: no restart; clears T1 flag) |
| +8 | `$9118` | `$9128` | T2 counter low (read: clears T2 flag; write: latch low) |
| +9 | `$9119` | `$9129` | T2 counter high (write: start one-shot) |
| +A | `$911A` | `$912A` | Shift register |
| +B | `$911B` | `$912B` | ACR: bits 7–6 T1 mode (`01` = continuous IRQs), bit 5 T2 mode, bits 4–2 SR mode, bits 1–0 latching |
| +C | `$911C` | `$912C` | PCR: CA1/CA2/CB1/CB2 control |
| +D | `$911D` | `$912D` | IFR: bit 7 = any, 6 = T1, 5 = T2, 4 = CB1, 3 = CB2, 2 = SR, 1 = CA1, 0 = CA2 |
| +E | `$911E` | `$912E` | IER: write bit 7 = 1 to set, 0 to clear the bits given in 0–6 |
| +F | `$911F` | `$912F` | ORA/IRA without handshake |

Wiring on the VIC-20:
- **VIA1 (`$9110`) → NMI line.** CA1 = RESTORE key. Port A: bit 0 serial CLK in, bit 1 serial DATA in, bit 2
  joy up, bit 3 joy down, bit 4 joy left, bit 5 joy fire, bit 6 cassette switch, bit 7 serial ATN out.
  Port B = user port. CA2 = cassette motor.
- **VIA2 (`$9120`) → IRQ line.** Port B = keyboard columns (output) + joystick right (bit 7). Port A =
  keyboard rows (input). CA1 = cassette read. CA2/CB2 = serial CLK/DATA out. T1 = KERNAL jiffy IRQ.

The four timers are the VIC-20's best timing resource: VIA2 T1 for the frame IRQ, VIA1 T1 (NMI) for a
sample-rate or raster-reference timer, the T2s for one-shot delays and measurement.

## KERNAL jump table (same as the C64 from `$FF8A` up)

| Address | Name | Function |
|---|---|---|
| `$FF8A` | RESTOR | Restore default I/O vectors |
| `$FF8D` | VECTOR | Read/set I/O vectors |
| `$FF90` | SETMSG | Control KERNAL messages |
| `$FF99` | MEMTOP | Read/set top of memory |
| `$FF9C` | MEMBOT | Read/set bottom of memory |
| `$FF9F` | SCNKEY | Scan keyboard (into `$CB`/buffer) |
| `$FFB7` | READST | Read I/O status |
| `$FFBA` | SETLFS | Set logical file, device, secondary address |
| `$FFBD` | SETNAM | Set filename (A = length, X/Y = address) |
| `$FFC0` | OPEN | |
| `$FFC3` | CLOSE | |
| `$FFC6` | CHKIN | |
| `$FFC9` | CHKOUT | |
| `$FFCC` | CLRCHN | |
| `$FFCF` | CHRIN | |
| `$FFD2` | CHROUT | Output PETSCII character in A |
| `$FFD5` | LOAD | A = 0 load / 1 verify; X/Y = address if secondary address = 0 |
| `$FFD8` | SAVE | |
| `$FFDB` | SETTIM | Set jiffy clock |
| `$FFDE` | RDTIM | Read jiffy clock |
| `$FFE1` | STOP | Check STOP key |
| `$FFE4` | GETIN | Get a character from the keyboard buffer (0 = none) |
| `$FFE7` | CLALL | Close all files |
| `$FFEA` | UDTIM | Update jiffy clock |
| `$FFED` | SCREEN | Returns X = columns, Y = rows |
| `$FFF0` | PLOT | C=1 read / C=0 set cursor (X = row, Y = column) |
| `$FFF3` | IOBASE | Returns VIA address |

**Not on the VIC-20:** `$FF81` CINT, `$FF84` IOINIT, `$FF87` RAMTAS (the area holds the IRQ entry code).
Call the routines directly: CINT `$E518`, IOINIT `$FDF9`, RAMTAS `$FD8D`, RESTOR `$FD52`.

Loading a file from disk in machine code (KERNAL must be running with its IRQ, or at least not broken):

```asm
        lda #fname_end-fname
        ldx #<fname
        ldy #>fname
        jsr $ffbd               ; SETNAM
        lda #1
        ldx #8                  ; device 8
        ldy #1                  ; secondary 1 = load to the file's own address
        jsr $ffba               ; SETLFS
        lda #0                  ; load (not verify)
        jsr $ffd5               ; LOAD; C=1 on error, A = error code
        bcs load_error
```

Serial bus (disk) transfers are slow and timing-sensitive. Restore the KERNAL IRQ and keep VIA settings at
their defaults during loads, or use a fast loader.
