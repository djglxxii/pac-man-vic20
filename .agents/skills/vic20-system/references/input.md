# VIC-20 Input: Joystick, Keyboard, Paddles

## Joystick (single Atari-style port)

| Signal | Register | Bit | Active |
|---|---|---|---|
| Up | VIA1 port A `$9111` / `$911F` | 2 | low |
| Down | VIA1 port A | 3 | low |
| Left | VIA1 port A | 4 | low |
| Fire | VIA1 port A | 5 | low |
| Right | VIA2 port B `$9120` | 7 | low |

- Read VIA1 port A through **`$911F`** (no handshake) so you don't clear the CA1/CA2 interrupt flags. `$9111`
  works too and is what most listings use.
- **Right shares VIA2 port B with the keyboard column outputs.** The KERNAL leaves DDRB (`$9122`) at `$FF`
  (all outputs), so bit 7 must be made an input before reading and restored afterwards. If the KERNAL keyboard
  scan can run in between (stock IRQ), wrap the read in `SEI`/`CLI`.

Tested routine (returns 1 = pressed; also in the template):

```asm
JOY_UP    = $01
JOY_DOWN  = $02
JOY_LEFT  = $04
JOY_FIRE  = $08
JOY_RIGHT = $80

read_joystick:                  ; out: A = joy = bitmask; clobbers X
        lda #$7f
        sta $9122               ; VIA2 DDRB: bit 7 input
        lda $9120
        ldx #$ff
        stx $9122               ; restore all outputs
        and #$80                ; right
        sta joy_tmp
        lda $911f
        and #%00111100          ; up, down, left, fire
        lsr a
        lsr a
        ora joy_tmp
        eor #%10001111          ; invert: 1 = pressed
        sta joy
        rts
```

Edge detection for fire (act on press, not hold):

```asm
        lda joy
        tax
        eor joy_prev            ; bits that changed
        and joy                 ; ...and are now pressed
        sta joy_pressed
        stx joy_prev
```

## Keyboard matrix

Write a column mask to **`$9120`** (VIA2 port B, one bit low), read the rows from **`$9121`** (VIA2 port A).
Both are active-low. The table is the KERNAL's (ROM `$EC5E`; index = column × 8 + row):

| `$9120` bit low ↓ / `$9121` bit → | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| 0 (`$FE`) | 1 | 3 | 5 | 7 | 9 | + | £ | DEL |
| 1 (`$FD`) | ← | W | R | Y | I | P | * | RETURN |
| 2 (`$FB`) | CTRL | A | D | G | J | L | ; | CRSR→ |
| 3 (`$F7`) | STOP | L-SHIFT | X | V | N | , | / | CRSR↓ |
| 4 (`$EF`) | SPACE | Z | C | B | M | . | R-SHIFT | F1 |
| 5 (`$DF`) | C= | S | F | H | K | : | = | F3 |
| 6 (`$BF`) | Q | E | T | U | O | @ | ↑ | F5 |
| 7 (`$7F`) | 2 | 4 | 6 | 8 | 0 | − | HOME | F7 |

RESTORE is not in the matrix (it drives the NMI through VIA1 CA1).

Check one key directly (no KERNAL):

```asm
; is SPACE down? column 4 ($EF), row bit 0
key_space:
        lda #$ef
        sta $9120
        lda $9121
        and #$01                ; Z=1 -> pressed (active low)
        rts                     ; restore $9120 to $FF if the KERNAL scan will run later
```

Notes:
- Port B bit 7 (column 7) is also joystick right. Pushing the stick right looks like a column-7 key, and
  holding keys can disturb joystick reads. Read the joystick and the keys at different moments, and set
  `$9120` back to `$FF` afterwards.
- `$CB` holds the KERNAL's current matrix code (`$40` = none) and `$028D` the shift flags. Use them only
  while the KERNAL IRQ is still scanning.
- For text input in menus, keep the KERNAL IRQ (`$EABF`) and use `GETIN` (`$FFE4`). Switch to your own
  IRQ for gameplay.

## Paddles and light pen

- Paddle X/Y: `$9008` / `$9009` (VIC, 0–255). Paddle fire buttons are on the joystick lines
  (left = paddle X fire on VIA1 PA4, right = paddle Y fire on VIA2 PB7).
- Light pen X/Y: `$9006` / `$9007`. The light pen trigger is VIA1 PA5 (same as joystick fire).
