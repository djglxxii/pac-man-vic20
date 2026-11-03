---
name: 6502-assembly
description: Write, review, debug and optimize NMOS 6502 assembly language (VIC-20, C64, Atari 8-bit, NES, Apple II, BBC Micro). Use whenever the task involves .s/.asm/.a65/.inc 6502 source, ca65/ACME/64tass/DASM/xa syntax, cycle counting, zero-page planning, 16-bit math on 8-bit registers, lookup tables, self-modifying code, undocumented opcodes, or converting C/BASIC logic to 6502 machine code. Includes a cycle-counting script and full opcode/cycle tables.
---

# 6502 Assembly

Guidance for writing correct and fast NMOS 6502 code. For VIC-20 hardware specifics, also load the
`vic20-system`, `vic20-graphics`, `vic20-audio` or `vic20-optimization` skills.

## Bundled resources

| File | Use it for |
|---|---|
| `references/instruction-set.md` | Every opcode × addressing mode with bytes and cycles, flag effects, branch cheat-sheet, the 65C02 instructions that do **not** exist, the JMP indirect bug |
| `references/idioms.md` | Tested routines: 16-bit math, compares (unsigned/signed), multiply/divide, lookup tables, jump tables, memcpy/fill, hex/BCD output, RNGs, fixed point, SMC, cycle-exact delays, assembler syntax cross-reference |
| `references/illegal-opcodes.md` | Stable undocumented opcodes (LAX, SAX, DCP, SLO…), naming aliases, which to avoid |
| `scripts/cycles.py` | Annotates a source file (or a `--from LABEL --to LABEL` range) with opcode, size and cycle cost per line. `--op LDA` for one mnemonic, `--table` for the whole matrix |

Run the cycle counter on hot loops and anything timing-sensitive:

```bash
python3 .claude/skills/6502-assembly/scripts/cycles.py src/raster.s --from irq --to irq_end --illegal
```

It distinguishes zero page from absolute using `NAME = $xx` equates, ca65 `.zeropage` labels, `<expr` and `z:`/`a:` prefixes. Add `--zp sym1,sym2` for symbols it can't resolve. Loop bodies are summed once; multiply them by the iteration count yourself.

## Ground rules (the mistakes that recur)

1. **Target the NMOS 6502 only.** Never emit `STZ`, `BRA`, `PHX/PHY/PLX/PLY`, `INC A`, `TRB/TSB`, `(zp)` without Y, `BIT #imm`, `JMP (abs,X)`. These are 65C02 instructions. Replacements are in `instruction-set.md`.
2. **Carry discipline.** `CLC` before `ADC`, `SEC` before `SBC`, unless you deliberately chain a carry (comment it when you do). After `CMP`: `BCC` means less-than and `BCS` means greater-or-equal (unsigned). Signed comparisons need the N XOR V fix.
3. **`INC`/`DEC`/`INX`/`DEX`/`INY`/`DEY` don't touch carry.** A 16-bit increment needs a `BNE` test, not `ADC`.
4. **Loads set N and Z.** `LDA x / CMP #0 / BEQ` wastes 2 bytes and 2 cycles. `DEX / BNE` needs no compare.
5. **Branch range is −128..+127 bytes.** If the assembler reports "range error", invert the condition and branch around a `JMP`.
6. **Zero-page indexed addressing wraps** (`LDA $F0,X` with X=$20 reads `$0010`), and `(zp),Y` pointers must be in zero page, low byte first.
7. **`JMP ($xxFF)` bug:** the high byte comes from `$xx00`. Never put a vector at a page's last byte.
8. **Decimal mode is sticky across interrupts on NMOS.** Wrap `SED`…`CLD` in `SEI`…`CLI`, or begin your IRQ handlers with `CLD`.
9. **Preserve what you clobber.** Document each routine's inputs, outputs and clobbered registers/zero-page bytes in a header comment. IRQ handlers must save and restore A/X/Y (the Commodore KERNAL entry does this before jumping to the RAM vector).
10. **Shared multi-byte data between main code and IRQ** needs `SEI`/`CLI` around updates, or a single-byte "ready" flag written last.
11. **Match the project's assembler.** ca65, ACME, 64tass, DASM and xa differ in directives, local labels and how they force zp vs absolute. See the syntax table in `idioms.md` §14.

## Writing fast code: priority order

1. **Pick a better algorithm or data layout first**: lookup tables instead of math, dirty-flag updates instead of full redraws, work spread across frames.
2. **Zero page** for pointers, hot counters and temporaries (`LDA zp` is 3 cycles vs 4, and `(zp),Y` needs it).
3. **Tables instead of arithmetic**: row-address lo/hi tables, multiply tables, shift tables, pre-shifted graphics. Page-align hot tables so indexed reads don't pick up page-cross penalties.
4. **Count down** (`DEX/BNE`, `DEY/BPL`) and arrange data to suit.
5. **Unroll** small fixed loops (8-byte character copies) and **specialize** routines for common cases instead of one generic routine.
6. **Self-modifying code**: patch absolute operands (`abs,Y` 4–5 cycles beats `(zp),Y` 5–6), patch immediate constants, patch jump targets. Not in reentrant or ROM code.
7. **Tail calls** (`JSR x / RTS` → `JMP x`), the `RTS` jump-table trick, and the `BIT` skip-byte trick for shared entry points.
8. **Undocumented opcodes** (`LAX`, `SAX`, `DCP`, `SBX`) only when measured gains justify them, and only on NMOS targets.

Size optimisation reverses some of these choices: loops instead of unrolling, shared subroutines, `BIT` skip tricks, packed data, and table-driven dispatch. Ask which matters before trading one for the other. On an unexpanded VIC-20 (3.5 KB free) size often wins everywhere except the inner loops.

## Cycle-exact code

- Keep timed loops **inside one page**. A taken branch across a page costs 4 cycles instead of 3. Use assembler assertions (ca65: `.assert >(*) = >(label), error, "page cross"`).
- `LDX #n / DEX / BNE` delays `5n+1` cycles. Use `NOP` (2) and `BIT zp` (3) to pad odd counts.
- Interrupt entry has 0–6 cycles of jitter (the instruction being finished) plus 7 for the interrupt sequence. Removing it needs a timer read plus a variable delay (see the `vic20-graphics` skill, raster section).
- Annotate every instruction with its cycle count in timed code, and verify in a cycle-accurate emulator.

## Workflow for a new routine

1. Write the contract first: inputs (registers / zero page), outputs, clobbers, cycle budget.
2. Write the straightforward version and get it correct.
3. Measure (cycle counter script, emulator profiling, or border-colour timing on Commodore machines).
4. Optimize only the measured hot spots, keeping the old version in a comment or under a conditional for comparison.
5. Re-test boundary cases: zero counts, 255/256 elements, page-crossing pointers, negative values, carry-in states.

## Reviewing existing 6502 code: checklist

- [ ] Missing `CLC`/`SEC` before arithmetic, or a carry that is wrongly assumed.
- [ ] `BCC`/`BCS` vs `BMI`/`BPL` confusion (unsigned vs signed).
- [ ] Loop counters off by one (`DEY/BPL` runs Y+1 times; `DEY/BNE` runs Y times, 256 if Y=0).
- [ ] 8-bit index overflows (tables > 256 bytes need pointer arithmetic or split tables).
- [ ] Indirect vectors at `$xxFF`.
- [ ] Zero-page addresses that collide with the OS, the C runtime or other modules.
- [ ] Registers not saved in IRQs; decimal mode leaking into IRQs.
- [ ] Self-modifying code that runs from ROM, or is re-entered from an interrupt.
- [ ] Timing loops that straddle a page boundary.
- [ ] 65C02-only instructions.
