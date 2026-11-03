# Undocumented ("illegal") NMOS 6502 Opcodes

The VIC-20's 6502 is NMOS, so the undocumented opcodes work. They are used in size- and cycle-critical
code (viznut's waveform loader uses `axs` = SAX and `aso` = SLO, for example). Use them only when:

- the target is a real NMOS 6502 (VIC-20, C64, etc.; **not** a 65C02 and not some FPGA replacements),
- the assembler supports them (ca65: `.setcpu "6502X"`; ACME: `!cpu 6510`; 64tass: `.cpu "6502i"`; DASM: none, use `.byte`),
- the gain is measurable. Comment every use with what it does.

## Naming confusion

Different documents use different names. Check the opcode byte, not just the name:

| Common (NMOS "No More Secrets") | Aliases | Operation |
|---|---|---|
| SLO | ASO | M = M << 1; A \|= M |
| RLA | — | M = ROL M; A &= M |
| SRE | LSE | M = M >> 1; A ^= M |
| RRA | — | M = ROR M; A = A + M + C |
| SAX | AXS (e.g. viznut's code, ACME-era docs), AAX | M = A & X (no flags) |
| LAX | — | A = X = M |
| DCP | DCM | M = M − 1; CMP M |
| ISC | ISB, INS | M = M + 1; SBC M |
| ANC | AAC | A &= imm; C = N |
| ALR | ASR | A = (A & imm) >> 1 |
| ARR | — | A = ROR(A & imm); odd C/V rules |
| SBX | AXS (in other docs!) | X = (A & X) − imm; flags like CMP; ignores D and incoming C |

> Warning: "AXS" means **SAX ($87/$97/$8F/$83, store A AND X)** in some sources (viznut's `axs $900c`)
> and **SBX ($CB, X = (A AND X) − imm)** in others. Decide by the addressing mode / opcode byte.
> `scripts/cycles.py` resolves `axs #imm` → SBX and any other `axs` → SAX.

## Stable opcodes table

| Mnemonic | implied | accumulator | #imm | zp | zp,X | zp,Y | abs | abs,X | abs,Y | (abs) | (zp,X) | (zp),Y | rel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ALR * |  |  | 4B / 2 |  |  |  |  |  |  |  |  |  |  |
| ANC * |  |  | 0B / 2 |  |  |  |  |  |  |  |  |  |  |
| ARR * |  |  | 6B / 2 |  |  |  |  |  |  |  |  |  |  |
| DCP * |  |  |  | C7 / 5 | D7 / 6 |  | CF / 6 | DF / 7 | DB / 7 |  | C3 / 8 | D3 / 8 |  |
| ISC * |  |  |  | E7 / 5 | F7 / 6 |  | EF / 6 | FF / 7 | FB / 7 |  | E3 / 8 | F3 / 8 |  |
| LAS * |  |  |  |  |  |  |  |  | BB / 4+ |  |  |  |  |
| LAX * |  |  |  | A7 / 3 |  | B7 / 4 | AF / 4 |  | BF / 4+ |  | A3 / 6 | B3 / 5+ |  |
| RLA * |  |  |  | 27 / 5 | 37 / 6 |  | 2F / 6 | 3F / 7 | 3B / 7 |  | 23 / 8 | 33 / 8 |  |
| RRA * |  |  |  | 67 / 5 | 77 / 6 |  | 6F / 6 | 7F / 7 | 7B / 7 |  | 63 / 8 | 73 / 8 |  |
| SAX * |  |  |  | 87 / 3 |  | 97 / 4 | 8F / 4 |  |  |  | 83 / 6 |  |  |
| SBX * |  |  | CB / 2 |  |  |  |  |  |  |  |  |  |  |
| SLO * |  |  |  | 07 / 5 | 17 / 6 |  | 0F / 6 | 1F / 7 | 1B / 7 |  | 03 / 8 | 13 / 8 |  |
| SRE * |  |  |  | 47 / 5 | 57 / 6 |  | 4F / 6 | 5F / 7 | 5B / 7 |  | 43 / 8 | 53 / 8 |  |

Extra opcode bytes: `ANC` also at `$2B`; `SBC #imm` duplicate at `$EB`.

## Undocumented NOPs (useful for cycle padding)

| Opcode(s) | Mode | Bytes | Cycles |
|---|---|---|---|
| `$1A $3A $5A $7A $DA $FA` | implied | 1 | 2 |
| `$80 $82 $89 $C2 $E2` | #imm | 2 | 2 |
| `$04 $44 $64` | zp | 2 | 3 |
| `$14 $34 $54 $74 $D4 $F4` | zp,X | 2 | 4 |
| `$0C` | abs | 3 | 4 |
| `$1C $3C $5C $7C $DC $FC` | abs,X | 3 | 4 (+1 page cross) |

These do a dummy read. Don't point a reading NOP at I/O registers with read side effects (`$9124`/`$9128` VIA
timer-low reads acknowledge interrupts; `$9121`/`$9111` reads can clear port interrupt flags).

## Avoid (unstable or machine-dependent)

`ANE/XAA ($8B)`, `LXA ($AB)`, `SHA/AHX ($93, $9F)`, `SHX ($9E)`, `SHY ($9C)`, `TAS ($9B)`: results depend on the chip and temperature.
`JAM/KIL ($02 $12 $22 $32 $42 $52 $62 $72 $92 $B2 $D2 $F2)` lock up the CPU. A crash that "hangs" with the
screen frozen often means execution ran into data and hit one of these.

## Typical uses

```asm
; LAX: load A and X at once (save a TAX)
        lax (ptr),y         ; A = X = byte

; SAX: store A AND X without disturbing flags or A
        sax temp

; DCP: decrement memory, then compare A with the NEW value (one instruction)
        lda #LIMIT
        dcp lives           ; lives--, Z=1 if lives == LIMIT, C=1 if LIMIT >= lives

; ISC: INC + SBC; SLO: shift memory left and OR into A (bitmap shifting + collision mask)

; SBX: X = (A & X) - imm. Fast "X -= n" while keeping A, or index stepping:
        lda #$ff
        sbx #8              ; X = X - 8 (since A=$FF, A&X = X)
```
