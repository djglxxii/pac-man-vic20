#!/usr/bin/env python3
"""Build one backwards-depacking PRG, avoiding loads through VIC IO/ROM."""
import argparse, collections, subprocess
from pathlib import Path

LOADER = r"""
.setcpu "6502"
src=$02
dst=$04
ref=$06
count=$08
blocks=$09
offset=$0a
.segment "LOADADDR"
.word $1201
.segment "CODE"
.word basic_end
.word 10
.byte $9e,"4621",0
basic_end: .word 0
.export loader_start
loader_start:
 sei
 cld
 ldx #$ff
 txs
 lda #$7f
 sta $911e
 sta $912e
 lda #0
 sta $900e
 lda #8
 sta $900f
 lda #<(packed_end-1)
 sta src
 lda #>(packed_end-1)
 sta src+1
 lda #$ff
 sta dst
 lda #$bf
 sta dst+1
 lda #3
 sta blocks
next_command:
 jsr get_byte
 beq block_end
 bmi copy_match
 tax
literal:
 jsr get_byte
 ldy #0
 sta (dst),y
 jsr dec_dst
 dex
 bne literal
 jmp next_command
copy_match:
 and #$7f
 clc
 adc #3
 sta count
 jsr get_byte
 sta offset
 jsr get_byte
 sta offset+1
 clc
 lda dst
 adc offset
 sta ref
 lda dst+1
 adc offset+1
 sta ref+1
match_loop:
 ldy #0
 lda (ref),y
 sta (dst),y
 jsr dec_dst
 lda ref
 bne :+
 dec ref+1
: dec ref
 dec count
 bne match_loop
 jmp next_command
block_end:
 dec blocks
 beq complete
 lda #$ff
 sta dst
 ldx blocks
 cpx #2
 bne boot_block
 lda #$7f
 bne block_address
boot_block:
 lda #BOOT_HI
block_address:
 sta dst+1
 jmp next_command
complete:
 jmp ENTRY
get_byte:
 ldy #0
 lda (src),y
 pha
 lda src
 bne :+
 dec src+1
: dec src
 pla
 rts
dec_dst:
 lda dst
 bne :+
 dec dst+1
: dec dst
 rts
packed:
.incbin "packed.bin"
packed_end:
"""


def compress(raw):
    data = raw[::-1]
    out = bytearray()
    literals = bytearray()
    seen = collections.defaultdict(lambda: collections.deque(maxlen=64))
    i = 0

    def flush():
        while literals:
            chunk = literals[:127]
            del literals[:127]
            out.append(len(chunk))
            out.extend(chunk)

    while i < len(data):
        best = 0
        distance = 0
        for pos in reversed(seen[data[i : i + 3]]):
            n = 3
            while n < 130 and i + n < len(data) and data[pos + n] == data[i + n]:
                n += 1
            if n > best:
                best = n
                distance = i - pos
            if n == 130:
                break
        if best >= 4:
            flush()
            out.extend((128 + best - 3, distance & 255, distance >> 8))
            length = best
        else:
            literals.append(data[i])
            length = 1
        for p in range(i, i + length):
            if p + 3 <= len(data):
                seen[data[p : p + 3]].append(p)
        i += length
        if len(literals) == 127:
            flush()
    flush()
    out.append(0)
    return out


def verify(stream, main, bank, boot, payload_base):
    pos = 0
    def check_destination(destination):
        assert not 0x1201 <= destination < payload_base, "depacker would overwrite its loader"
        assert (destination < payload_base or
                destination > payload_base + len(stream) - pos - 1), "compressed payload would be overwritten"

    for expected, top in ((bank, 0xBFFF), (main, 0x7FFF), (boot, 0x400 + len(boot) - 1)):
        output = bytearray()
        while True:
            control = stream[pos]
            pos += 1
            if not control:
                break
            if control < 128:
                for _ in range(control):
                    v = stream[pos]
                    pos += 1
                    check_destination(top - len(output))
                    output.append(v)
            else:
                distance = stream[pos] | (stream[pos + 1] << 8)
                pos += 2
                for _ in range((control & 127) + 3):
                    check_destination(top - len(output))
                    output.append(output[-distance])
        assert output[::-1] == expected, "depacker round trip failed"
    assert pos == len(stream)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("binary")
    ap.add_argument("output")
    ap.add_argument("--ca65", required=True)
    ap.add_argument("--ld65", required=True)
    ap.add_argument("--nm", required=True)
    args = ap.parse_args()
    binary = Path(args.binary)
    out = Path(args.output)
    work = binary.parent
    raw = binary.read_bytes()
    symbols = subprocess.check_output([args.nm, "-n", str(binary) + ".elf"], text=True)
    parsed = [line.split() for line in symbols.splitlines() if len(line.split()) == 3]
    entry = next(int(v, 16) for v, t, n in parsed if n == "boot_start")
    boot_limit = next(int(v, 16) for v, t, n in parsed if n == "__boot_limit")
    assert entry == 0x400 and 0x800 <= boot_limit <= 0x1000 and boot_limit % 256 == 0
    assert len(raw) == 32768 + boot_limit - entry
    main, bank, boot = raw[:24576], raw[24576:32768], raw[32768:]
    stream = compress(bank) + compress(main) + compress(boot)
    (work / "packed.bin").write_bytes(stream[::-1])
    (work / "loader.s").write_text(LOADER.replace("ENTRY", f"${entry:04x}").replace("BOOT_HI", f"${(boot_limit-1)>>8:02x}"))
    (work / "loader.cfg").write_text(
        "MEMORY { H: start=$0000,size=$0002,file=%O; R: start=$1201,size=$6dff,file=%O; }\nSEGMENTS { LOADADDR: load=H,type=ro; CODE: load=R,type=ro; }\n"
    )
    subprocess.run(
        [
            args.ca65,
            "--bin-include-dir",
            str(work),
            "-o",
            str(work / "loader.o"),
            str(work / "loader.s"),
        ],
        check=True,
    )
    subprocess.run(
        [
            args.ld65,
            "-C",
            str(work / "loader.cfg"),
            "-o",
            str(out),
            "-Ln",
            str(work / "loader.lbl"),
            str(work / "loader.o"),
        ],
        check=True,
    )
    prg = out.read_bytes()
    payload_base = 0x1201 + len(prg) - 2 - len(stream)
    verify(stream, main, bank, boot, payload_base)
    labels = "".join(
        f"al {int(v,16):06X} .{n}\n" for v, t, n in parsed if int(v, 16) < 65536
    )
    out.with_suffix(".lbl").write_text(labels + (work / "loader.lbl").read_text())
    print(f"{out}: {len(prg)} bytes, entry ${entry:04x}, verified backwards depacking")


if __name__ == "__main__":
    main()
