# NMOS 6502 Instruction Set Reference

Generated from `scripts/cycles.py --table` (single source of truth), with flag effects added below.
The VIC-20 uses an **NMOS 6502** at ~1.0227 MHz (NTSC) / ~1.1087 MHz (PAL).

## Opcode / cycle matrix (documented opcodes)

| Mnemonic | implied | accumulator | #imm | zp | zp,X | zp,Y | abs | abs,X | abs,Y | (abs) | (zp,X) | (zp),Y | rel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ADC |  |  | 69 / 2 | 65 / 3 | 75 / 4 |  | 6D / 4 | 7D / 4+ | 79 / 4+ |  | 61 / 6 | 71 / 5+ |  |
| AND |  |  | 29 / 2 | 25 / 3 | 35 / 4 |  | 2D / 4 | 3D / 4+ | 39 / 4+ |  | 21 / 6 | 31 / 5+ |  |
| ASL |  | 0A / 2 |  | 06 / 5 | 16 / 6 |  | 0E / 6 | 1E / 7 |  |  |  |  |  |
| BCC |  |  |  |  |  |  |  |  |  |  |  |  | 90 / 2** |
| BCS |  |  |  |  |  |  |  |  |  |  |  |  | B0 / 2** |
| BEQ |  |  |  |  |  |  |  |  |  |  |  |  | F0 / 2** |
| BIT |  |  |  | 24 / 3 |  |  | 2C / 4 |  |  |  |  |  |  |
| BMI |  |  |  |  |  |  |  |  |  |  |  |  | 30 / 2** |
| BNE |  |  |  |  |  |  |  |  |  |  |  |  | D0 / 2** |
| BPL |  |  |  |  |  |  |  |  |  |  |  |  | 10 / 2** |
| BRK | 00 / 7 |  |  |  |  |  |  |  |  |  |  |  |  |
| BVC |  |  |  |  |  |  |  |  |  |  |  |  | 50 / 2** |
| BVS |  |  |  |  |  |  |  |  |  |  |  |  | 70 / 2** |
| CLC | 18 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| CLD | D8 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| CLI | 58 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| CLV | B8 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| CMP |  |  | C9 / 2 | C5 / 3 | D5 / 4 |  | CD / 4 | DD / 4+ | D9 / 4+ |  | C1 / 6 | D1 / 5+ |  |
| CPX |  |  | E0 / 2 | E4 / 3 |  |  | EC / 4 |  |  |  |  |  |  |
| CPY |  |  | C0 / 2 | C4 / 3 |  |  | CC / 4 |  |  |  |  |  |  |
| DEC |  |  |  | C6 / 5 | D6 / 6 |  | CE / 6 | DE / 7 |  |  |  |  |  |
| DEX | CA / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| DEY | 88 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| EOR |  |  | 49 / 2 | 45 / 3 | 55 / 4 |  | 4D / 4 | 5D / 4+ | 59 / 4+ |  | 41 / 6 | 51 / 5+ |  |
| INC |  |  |  | E6 / 5 | F6 / 6 |  | EE / 6 | FE / 7 |  |  |  |  |  |
| INX | E8 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| INY | C8 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| JMP |  |  |  |  |  |  | 4C / 3 |  |  | 6C / 5 |  |  |  |
| JSR |  |  |  |  |  |  | 20 / 6 |  |  |  |  |  |  |
| LDA |  |  | A9 / 2 | A5 / 3 | B5 / 4 |  | AD / 4 | BD / 4+ | B9 / 4+ |  | A1 / 6 | B1 / 5+ |  |
| LDX |  |  | A2 / 2 | A6 / 3 |  | B6 / 4 | AE / 4 |  | BE / 4+ |  |  |  |  |
| LDY |  |  | A0 / 2 | A4 / 3 | B4 / 4 |  | AC / 4 | BC / 4+ |  |  |  |  |  |
| LSR |  | 4A / 2 |  | 46 / 5 | 56 / 6 |  | 4E / 6 | 5E / 7 |  |  |  |  |  |
| NOP | EA / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| ORA |  |  | 09 / 2 | 05 / 3 | 15 / 4 |  | 0D / 4 | 1D / 4+ | 19 / 4+ |  | 01 / 6 | 11 / 5+ |  |
| PHA | 48 / 3 |  |  |  |  |  |  |  |  |  |  |  |  |
| PHP | 08 / 3 |  |  |  |  |  |  |  |  |  |  |  |  |
| PLA | 68 / 4 |  |  |  |  |  |  |  |  |  |  |  |  |
| PLP | 28 / 4 |  |  |  |  |  |  |  |  |  |  |  |  |
| ROL |  | 2A / 2 |  | 26 / 5 | 36 / 6 |  | 2E / 6 | 3E / 7 |  |  |  |  |  |
| ROR |  | 6A / 2 |  | 66 / 5 | 76 / 6 |  | 6E / 6 | 7E / 7 |  |  |  |  |  |
| RTI | 40 / 6 |  |  |  |  |  |  |  |  |  |  |  |  |
| RTS | 60 / 6 |  |  |  |  |  |  |  |  |  |  |  |  |
| SBC |  |  | E9 / 2 | E5 / 3 | F5 / 4 |  | ED / 4 | FD / 4+ | F9 / 4+ |  | E1 / 6 | F1 / 5+ |  |
| SEC | 38 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| SED | F8 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| SEI | 78 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| STA |  |  |  | 85 / 3 | 95 / 4 |  | 8D / 4 | 9D / 5 | 99 / 5 |  | 81 / 6 | 91 / 6 |  |
| STX |  |  |  | 86 / 3 |  | 96 / 4 | 8E / 4 |  |  |  |  |  |  |
| STY |  |  |  | 84 / 3 | 94 / 4 |  | 8C / 4 |  |  |  |  |  |  |
| TAX | AA / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| TAY | A8 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| TSX | BA / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| TXA | 8A / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| TXS | 9A / 2 |  |  |  |  |  |  |  |  |  |  |  |  |
| TYA | 98 / 2 |  |  |  |  |  |  |  |  |  |  |  |  |

Cell format: `opcode / cycles`. `+` = +1 cycle if the indexed address crosses a page. `**` = branch: +1 if taken, +2 if taken to a different page. `*` = undocumented opcode.

### Cycle rules worth memorising

- Indexed **reads** (`abs,X`, `abs,Y`, `(zp),Y`) cost +1 when base+index crosses a page boundary.
- Indexed **writes** (`STA abs,X/Y` = 5, `STA (zp),Y` = 6) and **read-modify-write** (`INC abs,X` = 7) always pay the worst case; no page-cross variance.
- Branches: 2 not taken, 3 taken, 4 taken to a different page (page of the *next* instruction vs target).
- `zp,X` / `zp,Y` wrap inside zero page: `LDA $F0,X` with X=$20 reads `$10`, not `$110`.
- `JSR` 6 + `RTS` 6 = 12-cycle overhead per call. `JMP abs` = 3.
- Interrupt entry: 7 cycles plus finishing the current instruction (0–6 more) → the source of IRQ jitter.

## Flag effects

| Instruction | N | V | Z | C | Notes |
|---|---|---|---|---|---|
| ADC | ✓ | ✓ | ✓ | ✓ | A = A + M + C. Decimal mode if D=1 (NMOS: N/V/Z unreliable in decimal) |
| SBC | ✓ | ✓ | ✓ | ✓ | A = A − M − (1−C). C=1 means "no borrow" |
| AND, ORA, EOR | ✓ | | ✓ | | |
| ASL | ✓ | | ✓ | ✓ | C = old bit 7 |
| LSR | 0 | | ✓ | ✓ | C = old bit 0, N always cleared |
| ROL | ✓ | | ✓ | ✓ | old C → bit 0, bit 7 → C |
| ROR | ✓ | | ✓ | ✓ | old C → bit 7, bit 0 → C |
| BIT | M7 | M6 | ✓ | | Z from A AND M; N,V copied from memory bits 7,6 |
| CMP, CPX, CPY | ✓ | | ✓ | ✓ | C=1 if reg ≥ M (unsigned), Z=1 if equal, N = bit 7 of (reg−M) |
| INC, DEC, INX, INY, DEX, DEY | ✓ | | ✓ | | **Carry is not affected** |
| LDA, LDX, LDY | ✓ | | ✓ | | Loads set N/Z: a following `CMP #0` is redundant |
| STA, STX, STY | | | | | Stores never change flags |
| TAX, TAY, TXA, TYA, TSX, PLA | ✓ | | ✓ | | |
| TXS, PHA, PHP | | | | | |
| PLP, RTI | all | all | all | all | Restore P from stack |
| CLC/SEC, CLD/SED, CLI/SEI, CLV | | | | | Set/clear the named flag only |
| BRK | | | | | Pushes PC+2 and P (with B set), sets I, jumps via $FFFE |
| JSR | | | | | Pushes (return address − 1) |

## Branch condition cheat-sheet

| After `CMP M` (unsigned) | Branch |
|---|---|
| A = M | BEQ |
| A ≠ M | BNE |
| A < M | BCC |
| A ≥ M | BCS |
| A > M | BEQ skip, then BCS (or compare M with A instead) |
| A ≤ M | BCC or BEQ |

Signed comparisons need N XOR V; see `idioms.md` → "Signed compare".

## Instructions that do NOT exist on the NMOS 6502

These are 65C02 / 65816 / 65CE02 instructions or addressing modes. Assemblers targeting a plain 6502 reject them (or worse, a misconfigured assembler accepts them and the VIC-20 executes garbage):

`STZ`, `BRA`, `PHX`, `PHY`, `PLX`, `PLY`, `TRB`, `TSB`, `INC A` / `INA`, `DEC A` / `DEA`, `BBR`/`BBS`/`RMB`/`SMB`, `WAI`, `STP`, `(zp)` indirect without index (`LDA ($FB)`), `JMP (abs,X)`, `BIT #imm`, `BIT zp,X`, `BIT abs,X`.

Replacements:

| Wanted | NMOS 6502 replacement |
|---|---|
| `STZ addr` | `LDA #0 / STA addr` (keep a zero in a register if done repeatedly) |
| `BRA label` | `JMP label`, or an always-true branch (e.g. `CLV`/`BVC`, or `BNE` when Z is known clear) |
| `PHX` / `PLX` | `TXA / PHA` … `PLA / TAX` |
| `INC A` | `CLC / ADC #1` (or `TAX / INX / TXA`) |
| `LDA (zp)` | `LDY #0 / LDA (zp),Y` |
| `JMP (table,X)` | RTS trick or copy to a vector, see `idioms.md` |

## The JMP indirect page bug

`JMP ($xxFF)` fetches the high byte from `$xx00`, not `$(xx+1)00`. Never place a jump vector so that its low byte sits at `$xxFF`. With ca65 you can guard it: `.assert <(vector) <> $FF, error, "JMP () bug"`.

## Decimal mode

`SED` makes `ADC`/`SBC` operate in BCD. The NMOS 6502 does **not** clear D on interrupt entry, so an IRQ handler that does binary arithmetic while the main code is in decimal mode will compute garbage. Either wrap decimal code in `SEI`…`CLI` or start your own IRQ handlers with `CLD`.
