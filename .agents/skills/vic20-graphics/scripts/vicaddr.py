#!/usr/bin/env python3
"""
VIC-20 screen / character-set / colour-RAM address calculator.

  vicaddr.py --screen 0x1e00 --chars 0x1c00     -> $9005 and $9002 bit 7 values
  vicaddr.py --reg9005 0xf0 --bit9 1            -> addresses those settings select
  vicaddr.py --table                             -> every legal base address

Rules (MOS 6560/6561 on the VIC-20):
  $9005 bits 7-4 = screen address bits 13-10, bits 3-0 = character address bits 13-10
  $9002 bit 7    = address bit 9 of the screen AND colour RAM ($9400 / $9600)
  VIC address bit 13 = NOT CPU A15, so VIC $0000-$1FFF = CPU $8000-$9FFF (char ROM, I/O)
  and VIC $2000-$3FFF = CPU $0000-$1FFF (internal RAM).
  Only CPU $0000-$03FF, $1000-$1FFF (RAM) and $8000-$8FFF (char ROM) hold usable data;
  $0400-$0FFF (3K expansion) is not connected to the VIC.
"""
import argparse
import sys


def nib_to_cpu(n):
    return (0x8000 + n * 0x400) if n < 8 else (n - 8) * 0x400


def cpu_to_nib(addr):
    if 0x8000 <= addr < 0xA000:
        return (addr - 0x8000) // 0x400
    if addr < 0x2000:
        return 8 + addr // 0x400
    return None


def describe(addr):
    if 0x8000 <= addr < 0x9000:
        return {0x8000: "char ROM upper/graphics", 0x8400: "char ROM upper reversed",
                0x8800: "char ROM lower/upper", 0x8C00: "char ROM lower reversed"}.get(addr & 0xFC00, "char ROM")
    if 0x9000 <= addr < 0xA000:
        return "I/O area: NOT usable"
    if addr < 0x0400:
        return "low RAM (zero page/stack/system: usable with care)"
    if addr < 0x1000:
        return "3K expansion: NOT visible to the VIC"
    return "internal RAM"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--screen", type=lambda s: int(s, 0))
    ap.add_argument("--chars", type=lambda s: int(s, 0))
    ap.add_argument("--reg9005", type=lambda s: int(s, 0))
    ap.add_argument("--bit9", type=int, choices=[0, 1], default=None)
    ap.add_argument("--table", action="store_true")
    a = ap.parse_args()

    if a.table:
        print("| nibble | char/screen base (bit9=0) | screen with bit9=1 | notes |")
        print("|---|---|---|---|")
        for n in range(16):
            b = nib_to_cpu(n)
            print(f"| {n:X} | ${b:04X} | ${b + 0x200:04X} | {describe(b)} |")
        return 0

    if a.reg9005 is not None:
        sn, cn = a.reg9005 >> 4, a.reg9005 & 15
        bit9 = a.bit9 if a.bit9 is not None else 0
        scr = nib_to_cpu(sn) + bit9 * 0x200
        ch = nib_to_cpu(cn)
        print(f"$9005=${a.reg9005:02X}, $9002 bit7={bit9}")
        print(f"  screen  ${scr:04X}  ({describe(scr)})")
        print(f"  chars   ${ch:04X}  ({describe(ch)})")
        print(f"  colour  ${0x9400 + bit9 * 0x200:04X}")
        if ch == 0x1C00:
            print("  note: codes 128-255 wrap to the ROM font at $8000 (the '$1C00 trick')")
        return 0

    if a.screen is None and a.chars is None:
        ap.print_help()
        return 1
    hi = lo = 0
    bit9 = 0
    if a.screen is not None:
        if a.screen % 0x200:
            sys.exit("screen must be on a 512-byte boundary")
        base = a.screen & ~0x3FF
        bit9 = 1 if a.screen & 0x200 else 0
        n = cpu_to_nib(base)
        if n is None:
            sys.exit(f"${a.screen:04X} is not addressable by the VIC")
        hi = n
        print(f"screen ${a.screen:04X}: {describe(a.screen)}")
    if a.chars is not None:
        if a.chars % 0x400:
            sys.exit("character set must be on a 1 KB boundary")
        n = cpu_to_nib(a.chars)
        if n is None:
            sys.exit(f"${a.chars:04X} is not addressable by the VIC")
        lo = n
        print(f"chars  ${a.chars:04X}: {describe(a.chars)}")
    v = (hi << 4) | lo
    print(f"=> $9005 = ${v:02X} ({v}); $9002 bit 7 = {bit9} -> colour RAM ${0x9400 + bit9 * 0x200:04X}")
    print(f"   e.g.  LDA #${v:02X} / STA $9005 ; LDA $9002 / {'ORA #$80' if bit9 else 'AND #$7F'} / STA $9002")
    return 0


if __name__ == "__main__":
    sys.exit(main())
