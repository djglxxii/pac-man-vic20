# 6502 Idioms and Routines

Syntax is ca65 (`:`/`:-`/`:+` anonymous labels, `<`/`>` low/high byte). All routines target the NMOS 6502.
Zero-page variables are written as `zp_*` or named in comments. Cycle counts assume no page crossing unless noted.

## Contents
1. Multi-byte arithmetic
2. Comparisons
3. Shifts, sign, and bit tricks
4. Multiply and divide
5. Tables, pointers and indirection
6. Jump tables and dispatch
7. Memory copy / fill
8. Number output (hex, decimal, BCD)
9. Random numbers
10. Fixed-point motion
11. Loops, unrolling, and self-modifying code
12. Cycle-exact delays
13. Stack and subroutine tricks
14. Assembler syntax cross-reference

---

## 1. Multi-byte arithmetic

```asm
; 16-bit add: r = a + b
        clc
        lda a_lo
        adc b_lo
        sta r_lo
        lda a_hi
        adc b_hi
        sta r_hi

; 16-bit subtract: r = a - b
        sec
        lda a_lo
        sbc b_lo
        sta r_lo
        lda a_hi
        sbc b_hi
        sta r_hi

; add 8-bit unsigned A to 16-bit pointer (common for row stepping)
        clc
        adc ptr
        sta ptr
        bcc :+
        inc ptr+1
:

; 16-bit increment (5-6 cycles typical)
        inc ptr
        bne :+
        inc ptr+1
:

; 16-bit decrement
        lda ptr
        bne :+
        dec ptr+1
:       dec ptr

; add signed 8-bit A to 16-bit value (sign-extend into high byte)
        ldx #0
        cmp #$80          ; C = sign bit
        bcc :+
        dex               ; X = $FF for negative
:       clc
        adc val
        sta val
        txa
        adc val+1
        sta val+1

; negate A (two's complement)
        eor #$ff
        clc
        adc #1

; negate 16-bit
        sec
        lda #0
        sbc val
        sta val
        lda #0
        sbc val+1
        sta val+1
```

Carry rules: **CLC before ADC, SEC before SBC**, unless you deliberately chain a known carry. After `CMP` that branched with `BCS`, carry is already set: you can skip the `SEC` before a following `SBC` (a classic size/speed trick, comment it).

## 2. Comparisons

```asm
; unsigned 16-bit compare a vs b
        lda a_hi
        cmp b_hi
        bne :+
        lda a_lo
        cmp b_lo
:       ; BCC -> a < b ; BCS -> a >= b ; BEQ -> a == b

; signed 8-bit compare: branch if a < b (signed)
        lda a
        sec
        sbc b
        bvc :+
        eor #$80          ; fix sign on overflow
:       bmi a_less_than_b

; range check: is A in [LO, HI] (unsigned)?
        sec
        sbc #LO
        cmp #HI-LO+1
        bcc in_range       ; one compare instead of two

; test bit 7 / bit 6 of memory without touching A
        bit flags          ; N = bit7, V = bit6
        bmi bit7_set
        bvs bit6_set
```

## 3. Shifts, sign and bit tricks

```asm
; arithmetic shift right (signed /2) of A
        cmp #$80          ; C = sign
        ror a

; 16-bit shift left / right
        asl val
        rol val+1
        lsr val+1
        ror val

; absolute value
        bpl :+
        eor #$ff
        clc
        adc #1
:

; swap nibbles of A (8 bytes, 12 cycles, from the 6502 community)
        asl a
        adc #$80
        rol a
        asl a
        adc #$80
        rol a

; set C from bit 7 of A without changing A
        cmp #$80
; set C from bit 0 of memory without changing it: two-step with LSR/ROL, or
        lda mem
        lsr a              ; C = bit 0 (A changed)

; skip-next-instruction trick: $2C = BIT abs swallows the next 2 bytes
entry_a: lda #1
        .byte $2c          ; BIT $02A9 -> harmless read, skips "LDA #2"
entry_b: lda #2
        ; shared code...
; ($24 = BIT zp swallows 1 byte.) Make sure the swallowed bytes do not
; form an address with read side effects (VIA registers!).
```

Bit counting, bit reversal and "which bit is set" are fastest as 256-byte lookup tables if RAM allows.

## 4. Multiply and divide

```asm
; 8x8 -> 16 unsigned multiply. Inputs: num1, num2 (zp). Output: A = high, num1 = low.
; ~130-150 cycles.
mul8:   lda #0
        ldx #8
        lsr num1
@loop:  bcc @noadd
        clc
        adc num2
@noadd: ror a
        ror num1
        dex
        bne @loop
        rts

; 16 / 8 unsigned divide. dividend in div_lo/div_hi, divisor in divisor.
; Output: quotient in div_lo/div_hi, remainder in A.
div16_8:
        lda #0
        ldx #16
@loop:  asl div_lo
        rol div_hi
        rol a
        bcs @sub           ; 9-bit partial remainder: must subtract
        cmp divisor
        bcc @skip
@sub:   sbc divisor        ; C is 1 here on both paths
        inc div_lo         ; set quotient bit
@skip:  dex
        bne @loop
        rts
```

**Prefer avoiding multiply entirely:**
- Multiply by constants with shifts and adds: `x*22 = x*16 + x*4 + x*2` (screen row offsets on a 22-column VIC-20 screen). Better still, use a row-address table (§5).
- Quarter-square multiply: `a*b = f(a+b) - f(a-b)` with `f(x) = x²/4` tables (2 × 512 bytes) gives 8x8 multiply in ~50 cycles. Use when doing lots of multiplies (3D, rotation).
- Divide by constants with reciprocal multiply or tables.

## 5. Tables, pointers and indirection

```asm
; Row address tables: avoid multiplies when addressing a 2D grid
; (here: 22-column screen at SCREEN; 23 rows)
row_lo: .repeat 23, i
          .byte <(SCREEN + i*22)
        .endrep
row_hi: .repeat 23, i
          .byte >(SCREEN + i*22)
        .endrep

; plot char A at (X=col, Y=row)
plot:   pha
        lda row_lo,y
        sta zp_ptr
        lda row_hi,y
        sta zp_ptr+1
        txa
        tay
        pla
        sta (zp_ptr),y
        rts
```

- Split tables into separate lo/hi byte arrays ("structure of arrays"). Indexing `tbl_lo,x` / `tbl_hi,x` is faster than `tbl,x` with `x*2`.
- Pointers used with `(zp),Y` **must live in zero page** and be little-endian (low byte first).
- `(zp,X)` is rarely useful except for a table of zero-page pointers selected by X.
- Page-align hot tables (`.align 256` in ca65, or place them at `$xx00`) to avoid +1 cycle page-cross penalties and timing variance.
- Generate tables at assembly time (`.repeat`, `!for`, macros) or at init time in code that gets overwritten later. Don't type them by hand.

## 6. Jump tables and dispatch

```asm
; RTS trick: A = index (0..127). Table holds (address - 1).
dispatch:
        asl a
        tax
        lda jt+1,x
        pha
        lda jt,x
        pha
        rts                ; "returns" into handler
jt:     .word state_title-1, state_play-1, state_dead-1

; Split-table variant (index up to 255, no ASL):
        lda jt_hi,x
        pha
        lda jt_lo,x
        pha
        rts
jt_lo:  .byte <(h0-1), <(h1-1)
jt_hi:  .byte >(h0-1), >(h1-1)

; Indirect JMP through a vector (vector must not straddle $xxFF!)
        lda handlers_lo,x
        sta vec
        lda handlers_hi,x
        sta vec+1
        jmp (vec)

; Self-modified JMP (fastest when called often): patch the operand
        lda handlers_lo,x
        sta jmpop+1
        lda handlers_hi,x
        sta jmpop+2
jmpop:  jmp $ffff
```

## 7. Memory copy / fill

```asm
; copy X whole pages from (src) to (dst)
copy_pages:
        ldy #0
@loop:  lda (src),y
        sta (dst),y
        iny
        bne @loop
        inc src+1
        inc dst+1
        dex
        bne @loop
        rts

; fill X pages at (dst) with A
fill_pages:
        ldy #0
@loop:  sta (dst),y
        iny
        bne @loop
        inc dst+1
        dex
        bne @loop
        rts

; fixed-size, fixed-address copy: absolute indexed is faster than (zp),Y
        ldx #N
:       lda src-1,x
        sta dst-1,x
        dex
        bne :-
```

For fixed small blocks (8-byte character definitions) unroll completely: 8 × (`LDA abs` + `STA abs`) = 64 cycles, no loop overhead.

## 8. Number output

```asm
; print A as two hex digits via a char-output routine (CHROUT = $FFD2 on Commodore)
hexout: pha
        lsr a
        lsr a
        lsr a
        lsr a
        jsr @nib
        pla
        and #$0f
@nib:   cmp #10
        bcc :+
        adc #6             ; C=1 here, so +7: 10 -> 'A'
:       adc #'0'
        jmp CHROUT

; binary 0..255 in A -> BCD in bcd_hi:bcd_lo (decimal-mode doubling)
bin2bcd:
        sta bin
        lda #0
        sta bcd_lo
        sta bcd_hi
        ldx #8
        sei                ; NMOS: IRQ handler would inherit D=1
        sed
@loop:  asl bin
        lda bcd_lo
        adc bcd_lo
        sta bcd_lo
        lda bcd_hi
        adc bcd_hi
        sta bcd_hi
        dex
        bne @loop
        cld
        cli
        rts
```

**Scores:** keep them in BCD (e.g. 3 bytes = 6 digits) and add with `SED`/`ADC`/`CLD`. Display is then just nibble extraction; no binary-to-decimal conversion each frame.

## 9. Random numbers

```asm
; 8-bit Galois LFSR, period 255. seed must be non-zero.
rand8:  lda seed
        asl a
        bcc :+
        eor #$1d
:       sta seed
        rts

; 16-bit xorshift (7,9,8), period 65535, after John Metcalf. seed (2 bytes) non-zero.
rand16: lda seed+1
        lsr a
        lda seed
        ror a
        eor seed+1
        sta seed+1
        ror a
        eor seed
        sta seed
        eor seed+1
        sta seed+1
        rts                ; A = new low byte
```

Seed from something unpredictable, such as the frame counter at the moment the player presses fire, or the VIA timer low byte.

## 10. Fixed-point motion

Store positions and velocities as 8.8 fixed point (integer byte + fraction byte). Signed velocity in two's complement works with plain 16-bit add:

```asm
        clc
        lda x_frac
        adc vx_frac
        sta x_frac
        lda x_int
        adc vx_int          ; vx_int = $FF for small negative velocities
        sta x_int
```

Gravity = add a constant to `vy` each frame. Sub-pixel accumulation gives smooth, speed-varied movement with no multiplies. Sine/cosine: precompute a 256-entry table (one full period) with values -127..127 or 0..255.

## 11. Loops, unrolling and self-modifying code

- Count **down** to zero: `DEX/BNE` (or `DEY/BPL` for 0..127 inclusive) avoids a `CPX`.
- Lay out data so the index runs downward too (store bitmaps reversed if needed).
- Put the loop counter in X/Y, never in memory, in hot loops.
- **Unroll** when per-iteration overhead (`DEX/BNE` = 5 cycles) is a big share of the body.
- **Speedcode:** generate straight-line code at init time for a repeated operation (clears, scroll copies).
- **Self-modifying code (SMC):** patch operands to avoid `(zp),Y` (5–6 cycles) in favour of `abs,Y` (4–5):

```asm
        lda src_lo
        sta @ld+1
        lda src_hi
        sta @ld+2
        ldy #7
@ld:    lda $ffff,y          ; operand patched
@st:    sta $ffff,y          ; patch similarly
        dey
        bpl @ld
```

SMC rules: the code must be in RAM; never in an IRQ-reentrant path; mark patched operands with `$ffff` and a comment; patch once per call, not per iteration.

## 12. Cycle-exact delays

| Code | Bytes | Cycles |
|---|---|---|
| `NOP` | 1 | 2 |
| `BIT zp` (harmless zp addr) | 2 | 3 (changes N/V/Z) |
| `NOP` + `NOP` | 2 | 4 |
| `PHA` / `PLA` | 2 | 7 |
| `JSR rts_label` (to an `RTS`) | 3 | 12 |
| `LDX #n / : DEX / BNE :-` | 5 | `5n + 1` (no page cross, n ≥ 1) |
| `LDY #n / : DEY / BNE :-` | 5 | `5n + 1` |

Odd cycle counts: add a 3-cycle `BIT zp` (or `NOP zp` undocumented `$04`) to an even sequence.
Branches taken across a page add a cycle: keep timing loops inside one page (ca65: `.assert >(*) = >(loop), error`).

**Jitter-removing slide** (used in stable raster IRQs): jump into a run of `$C9 $C9 ... $C5 $EA` (CMP #$C9 ... ), entering at an offset computed from a timer read, so every entry point burns a different number of cycles. See the VIC-20 graphics skill for the full stable raster.

## 13. Stack and subroutine tricks

- **Tail call:** `JSR sub / RTS` → `JMP sub` (saves 6 cycles and a stack slot).
- `JSR` pushes return address − 1; `RTS` adds 1. Inline parameters: pop the return address, read bytes after the `JSR`, push the adjusted address back.
- `TSX` + `LDA $0101,X` reads stacked values without popping.
- Save registers in an IRQ: `PHA / TXA / PHA / TYA / PHA` (and restore in reverse). Commodore KERNAL IRQ entry already does this before jumping through the RAM vector.
- The stack is only 256 bytes (`$0100–$01FF`) and on Commodore machines part of page 1 is also used by the system. Avoid deep recursion.

## 14. Assembler syntax cross-reference

| Feature | ca65 | ACME | 64tass | DASM | xa |
|---|---|---|---|---|---|
| Origin | `.org` / linker cfg | `* = $1001` | `* = $1001` | `org $1001` (+ `processor 6502`) | `* = $1001` |
| Bytes | `.byte` | `!byte` / `!8` | `.byte` | `.byte` / `dc.b` | `.byt` |
| Words | `.word` | `!word` / `!16` | `.word` | `.word` / `dc.w` | `.word` |
| Text | `.byte "AB"` | `!text` / `!pet` | `.text` | `.byte "AB"` | `.asc` |
| Constant | `NAME = $FB` | `NAME = $FB` | `NAME = $FB` | `NAME equ $FB` | `NAME = $FB` |
| Local label | `@loop` (cheap local) | `.loop` | `_loop` | `.loop` (in SUBROUTINE) | — |
| Anonymous | `:` / `:-` / `:+` | `-` / `+` | `-` / `+` | — | — |
| Low/high byte | `<x` / `>x` | `<x` / `>x` | `<x` / `>x` | `<x` / `>x` | `<x` / `>x` |
| Force zp / abs | `z:x` / `a:x` | `+1` / `+2` suffix on mnemonic | `@b` / `@w` | `.b` / `.w` | — |
| Illegal ops | `.setcpu "6502X"` | `!cpu 6510` | `.cpu "6502i"` | via `.byte` | `-XMOS?` / via `.byt` |
| Include binary | `.incbin` | `!binary` | `.binary` | `incbin` | `.bin` |

When editing an existing project, **match its assembler and conventions**; don't mix syntaxes.
