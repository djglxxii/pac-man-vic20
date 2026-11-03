#!/usr/bin/env python3
"""
6502 cycle counter / opcode reference (NMOS 6502, as used in the VIC-20, C64, etc.)

Usage:
  cycles.py FILE.s [--from LABEL] [--to LABEL] [--zp SYM,SYM...] [--illegal]
      Annotate each instruction with bytes and cycle cost, then print totals.
      Cycle cost is shown as "base" or "base-max" where max includes page-cross
      penalties and taken branches.

  cycles.py --table [--illegal]
      Print a Markdown opcode table (mnemonic x addressing mode -> opcode/bytes/cycles).

  cycles.py --op LDA
      Print every addressing mode for one mnemonic.

Zero-page detection (decides zp vs absolute encodings):
  * numeric operands <= $FF (e.g. $fb, 251, %0101) are zero page
  * symbols defined as `NAME = $xx` / `NAME equ $xx` / `.define`d to a small value
  * labels defined inside ca65 `.zeropage` / `.segment "ZEROPAGE"`
  * `<expr` forces zero page; ca65 `z:` / `a:` prefixes force zp / absolute
  * anything else is assumed absolute (pass --zp to override)

Limitations: no macro expansion, no conditional assembly, no expression evaluation
beyond simple literals. Use it on hand-written hot loops and raster code, not on
whole programs. Always confirm cycle-exact code in an emulator.
"""
import argparse
import re
import sys

# mode: (bytes, description)
MODES = {
    "imp": (1, "implied"),
    "acc": (1, "accumulator"),
    "imm": (2, "#imm"),
    "zp": (2, "zp"),
    "zpx": (2, "zp,X"),
    "zpy": (2, "zp,Y"),
    "abs": (3, "abs"),
    "absx": (3, "abs,X"),
    "absy": (3, "abs,Y"),
    "ind": (3, "(abs)"),
    "indx": (2, "(zp,X)"),
    "indy": (2, "(zp),Y"),
    "rel": (2, "rel"),
}

# Opcode table: mnemonic -> {mode: (opcode, cycles, page_cross_penalty)}
# page_cross_penalty = 1 means +1 cycle when the indexed address crosses a page.
_O = {}


def _def(mn, entries):
    _O[mn] = {m: e for m, e in entries.items()}


# Standard ALU group (ORA AND EOR ADC LDA CMP SBC share a layout)
def _alu(mn, base):
    # base opcodes: imm, zp, zpx, abs, absx, absy, indx, indy
    imm, zp, zpx, ab, abx, aby, ix, iy = base
    _def(mn, {
        "imm": (imm, 2, 0), "zp": (zp, 3, 0), "zpx": (zpx, 4, 0),
        "abs": (ab, 4, 0), "absx": (abx, 4, 1), "absy": (aby, 4, 1),
        "indx": (ix, 6, 0), "indy": (iy, 5, 1),
    })


_alu("ORA", (0x09, 0x05, 0x15, 0x0D, 0x1D, 0x19, 0x01, 0x11))
_alu("AND", (0x29, 0x25, 0x35, 0x2D, 0x3D, 0x39, 0x21, 0x31))
_alu("EOR", (0x49, 0x45, 0x55, 0x4D, 0x5D, 0x59, 0x41, 0x51))
_alu("ADC", (0x69, 0x65, 0x75, 0x6D, 0x7D, 0x79, 0x61, 0x71))
_alu("LDA", (0xA9, 0xA5, 0xB5, 0xAD, 0xBD, 0xB9, 0xA1, 0xB1))
_alu("CMP", (0xC9, 0xC5, 0xD5, 0xCD, 0xDD, 0xD9, 0xC1, 0xD1))
_alu("SBC", (0xE9, 0xE5, 0xF5, 0xED, 0xFD, 0xF9, 0xE1, 0xF1))

_def("STA", {"zp": (0x85, 3, 0), "zpx": (0x95, 4, 0), "abs": (0x8D, 4, 0),
             "absx": (0x9D, 5, 0), "absy": (0x99, 5, 0),
             "indx": (0x81, 6, 0), "indy": (0x91, 6, 0)})


def _rmw(mn, acc, zp, zpx, ab, abx):
    d = {"zp": (zp, 5, 0), "zpx": (zpx, 6, 0), "abs": (ab, 6, 0), "absx": (abx, 7, 0)}
    if acc is not None:
        d["acc"] = (acc, 2, 0)
    _def(mn, d)


_rmw("ASL", 0x0A, 0x06, 0x16, 0x0E, 0x1E)
_rmw("ROL", 0x2A, 0x26, 0x36, 0x2E, 0x3E)
_rmw("LSR", 0x4A, 0x46, 0x56, 0x4E, 0x5E)
_rmw("ROR", 0x6A, 0x66, 0x76, 0x6E, 0x7E)
_rmw("DEC", None, 0xC6, 0xD6, 0xCE, 0xDE)
_rmw("INC", None, 0xE6, 0xF6, 0xEE, 0xFE)

_def("LDX", {"imm": (0xA2, 2, 0), "zp": (0xA6, 3, 0), "zpy": (0xB6, 4, 0),
             "abs": (0xAE, 4, 0), "absy": (0xBE, 4, 1)})
_def("LDY", {"imm": (0xA0, 2, 0), "zp": (0xA4, 3, 0), "zpx": (0xB4, 4, 0),
             "abs": (0xAC, 4, 0), "absx": (0xBC, 4, 1)})
_def("STX", {"zp": (0x86, 3, 0), "zpy": (0x96, 4, 0), "abs": (0x8E, 4, 0)})
_def("STY", {"zp": (0x84, 3, 0), "zpx": (0x94, 4, 0), "abs": (0x8C, 4, 0)})
_def("CPX", {"imm": (0xE0, 2, 0), "zp": (0xE4, 3, 0), "abs": (0xEC, 4, 0)})
_def("CPY", {"imm": (0xC0, 2, 0), "zp": (0xC4, 3, 0), "abs": (0xCC, 4, 0)})
_def("BIT", {"zp": (0x24, 3, 0), "abs": (0x2C, 4, 0)})
_def("JMP", {"abs": (0x4C, 3, 0), "ind": (0x6C, 5, 0)})
_def("JSR", {"abs": (0x20, 6, 0)})

for mn, op in {"BPL": 0x10, "BMI": 0x30, "BVC": 0x50, "BVS": 0x70,
               "BCC": 0x90, "BCS": 0xB0, "BNE": 0xD0, "BEQ": 0xF0}.items():
    _def(mn, {"rel": (op, 2, 0)})  # +1 taken, +2 taken across page

for mn, op, cyc in [("BRK", 0x00, 7), ("RTI", 0x40, 6), ("RTS", 0x60, 6),
                    ("PHP", 0x08, 3), ("PLP", 0x28, 4), ("PHA", 0x48, 3), ("PLA", 0x68, 4),
                    ("CLC", 0x18, 2), ("SEC", 0x38, 2), ("CLI", 0x58, 2), ("SEI", 0x78, 2),
                    ("CLV", 0xB8, 2), ("CLD", 0xD8, 2), ("SED", 0xF8, 2),
                    ("DEY", 0x88, 2), ("TXA", 0x8A, 2), ("TYA", 0x98, 2), ("TXS", 0x9A, 2),
                    ("TAY", 0xA8, 2), ("TAX", 0xAA, 2), ("TSX", 0xBA, 2), ("INY", 0xC8, 2),
                    ("DEX", 0xCA, 2), ("INX", 0xE8, 2), ("NOP", 0xEA, 2)]:
    _def(mn, {"imp": (op, cyc, 0)})

LEGAL = set(_O)

# --- Undocumented (NMOS) opcodes. Names follow the common "NoMoreSecrets" set. ---
ILLEGAL_ALIASES = {"ASO": "SLO", "LSE": "SRE", "AAX": "SAX",
                   "DCM": "DCP", "ISB": "ISC", "INS": "ISC", "ASR": "ALR"}
# "AXS" is ambiguous: SBX ($CB, immediate) in some docs, SAX (store A&X) in others
# (viznut's waveform code uses `axs $900c` = SAX). Resolved by addressing mode below.


def _rmw_ill(mn, zp, zpx, ab, abx, aby, ix, iy):
    _def(mn, {"zp": (zp, 5, 0), "zpx": (zpx, 6, 0), "abs": (ab, 6, 0),
              "absx": (abx, 7, 0), "absy": (aby, 7, 0),
              "indx": (ix, 8, 0), "indy": (iy, 8, 0)})


_rmw_ill("SLO", 0x07, 0x17, 0x0F, 0x1F, 0x1B, 0x03, 0x13)
_rmw_ill("RLA", 0x27, 0x37, 0x2F, 0x3F, 0x3B, 0x23, 0x33)
_rmw_ill("SRE", 0x47, 0x57, 0x4F, 0x5F, 0x5B, 0x43, 0x53)
_rmw_ill("RRA", 0x67, 0x77, 0x6F, 0x7F, 0x7B, 0x63, 0x73)
_rmw_ill("DCP", 0xC7, 0xD7, 0xCF, 0xDF, 0xDB, 0xC3, 0xD3)
_rmw_ill("ISC", 0xE7, 0xF7, 0xEF, 0xFF, 0xFB, 0xE3, 0xF3)
_def("SAX", {"zp": (0x87, 3, 0), "zpy": (0x97, 4, 0), "abs": (0x8F, 4, 0), "indx": (0x83, 6, 0)})
_def("LAX", {"zp": (0xA7, 3, 0), "zpy": (0xB7, 4, 0), "abs": (0xAF, 4, 0),
             "absy": (0xBF, 4, 1), "indx": (0xA3, 6, 0), "indy": (0xB3, 5, 1)})
_def("ANC", {"imm": (0x0B, 2, 0)})
_def("ALR", {"imm": (0x4B, 2, 0)})
_def("ARR", {"imm": (0x6B, 2, 0)})
_def("SBX", {"imm": (0xCB, 2, 0)})
_def("LAS", {"absy": (0xBB, 4, 1)})
ILLEGAL = set(_O) - LEGAL

BRANCHES = {"BPL", "BMI", "BVC", "BVS", "BCC", "BCS", "BNE", "BEQ"}

# ---------------------------------------------------------------------------

NUM_RE = re.compile(r"^(\$[0-9a-fA-F]+|0x[0-9a-fA-F]+|%[01]+|[0-9]+)$")


def parse_num(tok):
    tok = tok.strip()
    if not NUM_RE.match(tok):
        return None
    if tok.startswith("$"):
        return int(tok[1:], 16)
    if tok.lower().startswith("0x"):
        return int(tok[2:], 16)
    if tok.startswith("%"):
        return int(tok[1:], 2)
    return int(tok)


def strip_comment(line):
    out, q = [], None
    for ch in line:
        if q:
            out.append(ch)
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        if ch == ";":
            break
        out.append(ch)
    return "".join(out).rstrip()


class Ctx:
    def __init__(self, zp_syms, illegal):
        self.zp = set(s.lower() for s in zp_syms)
        self.illegal = illegal
        self.in_zp_seg = False


EQU_RE = re.compile(r"^\s*([A-Za-z_.@][\w.@]*)\s*(?:=|\.?equ\b|\.set\b)\s*(.+)$", re.I)
DEFINE_RE = re.compile(r"^\s*\.define\s+([A-Za-z_][\w]*)\s+(.+)$", re.I)
LABEL_RE = re.compile(r"^\s*([A-Za-z_.@][\w.@]*):")


def prescan(lines, ctx):
    for raw in lines:
        line = strip_comment(raw)
        low = line.strip().lower()
        if low.startswith(".zeropage") or re.match(r'\.segment\s+"zeropage"', low):
            ctx.in_zp_seg = True
            continue
        if low.startswith(".segment") or low.startswith(".code") or low.startswith(".data") \
                or low.startswith(".bss") or low.startswith(".rodata"):
            ctx.in_zp_seg = False
        m = EQU_RE.match(line) or DEFINE_RE.match(line)
        if m:
            v = parse_num(m.group(2).strip())
            if v is not None and v < 256:
                ctx.zp.add(m.group(1).lower())
            continue
        m = LABEL_RE.match(line)
        if m and ctx.in_zp_seg:
            ctx.zp.add(m.group(1).lower())
    ctx.in_zp_seg = False


def is_zp_expr(expr, ctx):
    e = expr.strip()
    if e.startswith("z:"):
        return True
    if e.startswith("a:") or e.startswith("!"):
        return False
    if e.startswith("<"):
        return True
    v = parse_num(e)
    if v is not None:
        return v < 256
    # symbol, possibly with +offset
    m = re.match(r"^([A-Za-z_.@][\w.@]*)\s*(?:[+-]\s*(\$?[0-9a-fA-F]+))?$", e)
    if m and m.group(1).lower() in ctx.zp:
        return True
    return False


def classify(mn, operand, ctx):
    op = operand.strip()
    if mn in BRANCHES:
        return "rel"
    if op == "" or op.lower() == "a":
        return "acc" if "acc" in _O.get(mn, {}) else "imp"
    if op.startswith("#"):
        return "imm"
    low = op.lower().replace(" ", "")
    if low.startswith("("):
        if low.endswith(",x)"):
            return "indx"
        if low.endswith("),y"):
            return "indy"
        if low.endswith(")"):
            return "ind"
    idx = None
    base = op
    if low.endswith(",x"):
        idx, base = "x", op[: op.lower().rfind(",x")]
    elif low.endswith(",y"):
        idx, base = "y", op[: op.lower().rfind(",y")]
    zp = is_zp_expr(base, ctx)
    modes = _O.get(mn, {})
    if idx is None:
        if zp and "zp" in modes:
            return "zp"
        return "abs"
    if zp and ("zp" + idx) in modes:
        return "zp" + idx
    return "abs" + idx


INSTR_RE = re.compile(r"^\s*(?:([A-Za-z_.@][\w.@]*):|([-+]+|:)\s)?\s*([A-Za-z]{3})(?:\.[bwlBWL])?\b\s*(.*)$")


def analyse(path, start, end, ctx, branch_assume):
    with open(path) as f:
        lines = f.readlines()
    prescan(lines, ctx)
    active = start is None
    total_min = total_max = total_bytes = 0
    rows = []
    for n, raw in enumerate(lines, 1):
        line = strip_comment(raw)
        lm = LABEL_RE.match(line)
        if lm:
            name = lm.group(1)
            if start is not None and name == start:
                active = True
            if end is not None and name == end and active:
                break
        if not active:
            continue
        m = INSTR_RE.match(line)
        if not m:
            continue
        mn = m.group(3).upper()
        if mn == "AXS":
            mn = "SBX" if m.group(4).strip().startswith("#") else "SAX"
        mn = ILLEGAL_ALIASES.get(mn, mn)
        if mn not in _O:
            continue
        if mn in ILLEGAL and not ctx.illegal:
            continue
        mode = classify(mn, m.group(4), ctx)
        entry = _O[mn].get(mode)
        if entry is None:
            rows.append((n, raw.rstrip(), "?", "?", f"no {MODES[mode][1]} mode for {mn}"))
            continue
        opc, cyc, pc = entry
        size = MODES[mode][0]
        cmin, cmax, note = cyc, cyc + pc, ""
        if pc:
            note = "+1 if page crossed"
        if mode == "rel":
            if branch_assume == "taken":
                cmin = cmax = 3
                note = "assumed taken (+1 if crosses page)"
                cmax = 4
            elif branch_assume == "not":
                cmin = cmax = 2
                note = "assumed not taken"
            else:
                cmin, cmax = 2, 4
                note = "2 not taken / 3 taken / 4 taken+page cross"
        if mn in ILLEGAL:
            note = (note + "; " if note else "") + "undocumented"
        total_min += cmin
        total_max += cmax
        total_bytes += size
        cyc_s = f"{cmin}" if cmin == cmax else f"{cmin}-{cmax}"
        rows.append((n, raw.rstrip(), f"${opc:02X}", cyc_s, note))
    w = max([len(r[1]) for r in rows] + [20])
    w = min(w, 60)
    for n, src, opc, cyc_s, note in rows:
        print(f"{n:5d}  {src[:w]:<{w}}  {opc:>4}  {cyc_s:>5}  {note}")
    print("-" * (w + 30))
    print(f"bytes: {total_bytes}   cycles: {total_min}"
          + (f" .. {total_max}" if total_max != total_min else "")
          + "   (straight-line sum; multiply loop bodies yourself)")


def print_table(illegal):
    order = ["imp", "acc", "imm", "zp", "zpx", "zpy", "abs", "absx", "absy", "ind", "indx", "indy", "rel"]
    hdr = "| Mnemonic | " + " | ".join(MODES[m][1] for m in order) + " |"
    print(hdr)
    print("|" + "---|" * (len(order) + 1))
    names = sorted(LEGAL) + (sorted(ILLEGAL) if illegal else [])
    for mn in names:
        cells = []
        for m in order:
            e = _O[mn].get(m)
            if e is None:
                cells.append("")
            else:
                opc, cyc, pc = e
                extra = "+" if pc else ""
                if m == "rel":
                    extra = "**"
                cells.append(f"{opc:02X} / {cyc}{extra}")
        tag = " *" if mn in ILLEGAL else ""
        print(f"| {mn}{tag} | " + " | ".join(cells) + " |")
    print()
    print("Cell format: `opcode / cycles`. `+` = +1 cycle if the indexed address crosses a page. "
          "`**` = branch: +1 if taken, +2 if taken to a different page. `*` = undocumented opcode.")


def print_op(mn):
    mn = ILLEGAL_ALIASES.get(mn.upper(), mn.upper())
    if mn not in _O:
        print(f"unknown mnemonic {mn}")
        return 1
    for mode, (opc, cyc, pc) in _O[mn].items():
        extra = " (+1 page cross)" if pc else ""
        if mode == "rel":
            extra = " (+1 taken, +2 taken across page)"
        print(f"{mn} {MODES[mode][1]:<12} ${opc:02X}  {MODES[mode][0]} bytes  {cyc} cycles{extra}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?")
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--zp", default="", help="comma-separated symbols to treat as zero page")
    ap.add_argument("--illegal", action="store_true", help="recognise undocumented opcodes")
    ap.add_argument("--branches", choices=["range", "taken", "not"], default="range",
                    help="how to cost branches (default: show 2-4 range)")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--op")
    a = ap.parse_args()
    if a.table:
        print_table(a.illegal)
        return 0
    if a.op:
        return print_op(a.op)
    if not a.file:
        ap.print_help()
        return 1
    ctx = Ctx([s for s in a.zp.split(",") if s], a.illegal)
    analyse(a.file, a.start, a.end, ctx, a.branches)
    return 0


if __name__ == "__main__":
    sys.exit(main())
