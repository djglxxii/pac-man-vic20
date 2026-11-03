#!/usr/bin/env python3
"""
VIC-20 note-table generator.

Frequency formula (Marko Makela, VIC-I.txt rev 1.2; matches VICE):
    f = Phi2 / DIV / (128 - ((reg + 1) & 127))
    reg = full register byte incl. enable bit 7 (128..255)
    DIV = 256 bass ($900A), 128 alto ($900B), 64 soprano ($900C), 32 noise ($900D)
    Phi2 NTSC = 14318181/14 = 1022727 Hz ; PAL = 4433618/4 = 1108405 Hz
For reg = 128+X with X < 127 this is f = (Phi2/DIV) / (127 - X).

Examples:
  notetable.py                         # markdown: every note C1..B6, best voice, error in cents
  notetable.py --format ca65 --voice alto --from C3 --to B5
  notetable.py --format ca65 --best --from C2 --to C7   # emits note_reg + note_voice tables
  notetable.py --pal --format acme --voice soprano
  notetable.py --freq 440              # show the closest register value on every voice
  notetable.py --reg 200               # show the frequency each voice produces for one value
"""
import argparse
import math
import sys

PHI2 = {"ntsc": 14318181 / 14, "pal": 4433618 / 4}
VOICES = [("bass", 0x900A, 256), ("alto", 0x900B, 128), ("soprano", 0x900C, 64)]
NOISE = ("noise", 0x900D, 32)
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def freq(reg, div, phi2):
    return phi2 / div / (128 - ((reg + 1) & 127))


def parse_note(s):
    s = s.strip().upper().replace("S", "#")
    for i in range(len(s), 0, -1):
        name, octv = s[:i], s[i:]
        if name in NAMES and octv.lstrip("-").isdigit():
            return NAMES.index(name) + 12 * (int(octv) + 1)  # MIDI number, C4 = 60
    raise ValueError(f"bad note {s!r}; use e.g. C4, F#3, Bb2 -> A#2")


def note_name(midi):
    return f"{NAMES[midi % 12]}{midi // 12 - 1}"


def note_freq(midi, a4):
    return a4 * 2 ** ((midi - 69) / 12)


def best_reg(target, div, phi2):
    best = None
    for reg in range(128, 255):  # 255 is degenerate (top value, same as 127-wrap); skip
        f = freq(reg, div, phi2)
        cents = 1200 * math.log2(f / target)
        if best is None or abs(cents) < abs(best[2]):
            best = (reg, f, cents)
    return best


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pal", action="store_true", help="PAL timing (default NTSC)")
    ap.add_argument("--a4", type=float, default=440.0, help="tuning reference (default 440)")
    ap.add_argument("--from", dest="lo", default="C1")
    ap.add_argument("--to", dest="hi", default="B6")
    ap.add_argument("--voice", choices=["bass", "alto", "soprano"], help="restrict to one voice")
    ap.add_argument("--best", action="store_true", help="pick the voice with least error per note")
    ap.add_argument("--max-cents", type=float, default=50.0,
                    help="omit notes whose best error exceeds this (default 50)")
    ap.add_argument("--format", choices=["md", "ca65", "acme", "c"], default="md")
    ap.add_argument("--freq", type=float, help="find register values for a frequency in Hz")
    ap.add_argument("--reg", type=int, help="show frequencies for one register value (128-255)")
    a = ap.parse_args()
    std = "pal" if a.pal else "ntsc"
    phi2 = PHI2[std]

    if a.reg is not None:
        for name, addr, div in VOICES + [NOISE]:
            print(f"{name:8s} ${addr:04X} = {a.reg:3d} (${a.reg:02X}): {freq(a.reg, div, phi2):9.2f} Hz")
        return 0
    if a.freq is not None:
        for name, addr, div in VOICES:
            reg, f, c = best_reg(a.freq, div, phi2)
            print(f"{name:8s} ${addr:04X} = {reg:3d} (${reg:02X})  -> {f:8.2f} Hz  {c:+6.1f} cents")
        return 0

    lo, hi = parse_note(a.lo), parse_note(a.hi)
    voices = [v for v in VOICES if a.voice is None or v[0] == a.voice]
    rows = []
    for m in range(lo, hi + 1):
        t = note_freq(m, a.a4)
        cands = []
        for name, addr, div in voices:
            reg, f, c = best_reg(t, div, phi2)
            cands.append((abs(c), name, addr, reg, f, c))
        cands.sort()
        rows.append((m, t, cands))

    if a.format == "md":
        print(f"VIC-20 note table ({std.upper()}, Phi2 = {phi2:.0f} Hz, A4 = {a.a4} Hz)\n")
        hdr = "| Note | Target Hz | " + " | ".join(f"{v[0]} ${v[1]:04X} (value / cents)" for v in voices) + " | Best |"
        print(hdr)
        print("|" + "---|" * (len(voices) + 3))
        for m, t, cands in rows:
            by = {c[1]: c for c in cands}
            cells = []
            for v in voices:
                _, _, _, reg, f, c = by[v[0]]
                mark = "" if abs(c) <= a.max_cents else " ✗"
                cells.append(f"{reg} / {c:+.0f}{mark}")
            best = cands[0]
            bestcell = best[1] if best[0] <= a.max_cents else "—"
            print(f"| {note_name(m)} | {t:.1f} | " + " | ".join(cells) + f" | {bestcell} |")
        print("\n✗ = error larger than ±%g cents (out of the voice's usable range)." % a.max_cents)
        return 0

    # code output
    if a.best or a.voice is None:
        sel = [(m, c[0]) for m, t, c in rows]
        sel = [(m, c) for m, c in sel if c[0] <= a.max_cents]
        regs = [c[3] for m, c in sel]
        vix = [{"bass": 0, "alto": 1, "soprano": 2}[c[1]] for m, c in sel]
        comment = [f"{note_name(m)} {c[1]} {c[5]:+.0f}c" for m, c in sel]
        first = sel[0][0] if sel else lo
        emit(a.format, "note_reg", regs, comment, f"first note {note_name(first)}, {std.upper()}")
        emit(a.format, "note_voice", vix, None, "0=bass $900A, 1=alto $900B, 2=soprano $900C")
    else:
        regs, comment = [], []
        for m, t, c in rows:
            _, name, addr, reg, f, cents = c[0]
            if abs(cents) > a.max_cents:
                continue
            regs.append(reg)
            comment.append(f"{note_name(m)} {cents:+.0f}c")
        emit(a.format, f"note_{a.voice}", regs, comment, f"{a.voice} voice, {std.upper()}")
    return 0


def emit(fmt, label, values, comments, title):
    if fmt == "c":
        print(f"/* {title} */")
        print(f"static const unsigned char {label}[{len(values)}] = {{")
        for i in range(0, len(values), 8):
            chunk = values[i:i + 8]
            cm = ""
            if comments:
                cm = "  /* " + ", ".join(comments[i:i + 8]) + " */"
            print("    " + ", ".join(f"{v:3d}" for v in chunk) + "," + cm)
        print("};")
        return
    directive = ".byte" if fmt == "ca65" else "!byte"
    print(f"; {title}")
    print(f"{label}:")
    for i in range(0, len(values), 8):
        chunk = values[i:i + 8]
        cm = ""
        if comments:
            cm = "    ; " + ", ".join(comments[i:i + 8])
        print(f"        {directive} " + ", ".join(f"${v:02X}" for v in chunk) + cm)


if __name__ == "__main__":
    sys.exit(main())
