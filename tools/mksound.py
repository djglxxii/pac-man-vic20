#!/usr/bin/env python3
"""SNAPBUG sound data generator (NTSC VIC-20).

Every sound is a stream of (register value, frames) pairs ending with a
(0, 0) pair.  Register value 0 = silent, otherwise 128 + n where the VIC
voice frequency is  f = clock / (127 - n)  (VIC-20 Programmer's Reference).

  python3 tools/mksound.py OUT.inc
"""
import math
import sys

CLK = {"bass": 3995.0, "alto": 7990.0, "sop": 15980.0}   # NTSC voice clocks

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
        "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

def note_freq(name):
    n, octv = name[:-1], int(name[-1])
    midi = 12 * (octv + 1) + NOTE[n]
    return 440.0 * 2 ** ((midi - 69) / 12)

def reg(voice, f):
    """Nearest audible VIC divider by pitch error; $FF wraps, so avoid it."""
    assert f > 0, f
    divider = CLK[voice] / f
    candidates = {max(1, min(127, d)) for d in (math.floor(divider), math.ceil(divider))}
    d = min(candidates, key=lambda n: abs(math.log2(CLK[voice] / n / f)))
    return 255 - d

def notes(voice, seq, unit, gap=2):
    """seq: list of (note-or-None, units)."""
    out = []
    for nm, u in seq:
        frames = u * unit
        if nm is None:
            out.append((0, frames))
        else:
            out.append((reg(voice, note_freq(nm)), frames - gap))
            out.append((0, gap))
    return out

def sweep(voice, f0, f1, frames, per=1):
    out = []
    steps = max(1, frames // per)
    for i in range(steps):
        f = f0 * (f1 / f0) ** (i / max(1, steps - 1))
        out.append((reg(voice, f), per))
    return out

def merge(pairs):
    """Merge adjacent equal values and split counts > 255."""
    out = []
    for v, c in pairs:
        if c <= 0:
            continue
        if out and out[-1][0] == v:
            out[-1] = (v, out[-1][1] + c)
        else:
            out.append((v, c))
    res = []
    for v, c in out:
        while c > 255:
            res.append((v, 255)); c -= 255
        res.append((v, c))
    return res

def tone(voice, seq):
    """(note-or-None, frames) with the rests already written out."""
    out = []
    for nm, frames in seq:
        if nm is None:
            out.append((0, frames))
        else:
            out.append((reg(voice, note_freq(nm)), frames))
    return out

def hz_stream(voice, pairs):
    """(hertz-or-0, frames). 0 is silence."""
    out = []
    for f, frames in pairs:
        out.append((0 if f <= 0 else reg(voice, f), frames))
    return out

def namco_hz(freq):
    """Namco 20-bit phase step at the 96 kHz waveform clock."""
    if not freq:
        return 0
    return freq * 96000.0 / 1048576.0

# Arcade pitches/timing come from pacman.6j's song/effect tables ($3B30+).
# The wavetable PROM has strong partials that a plain VIC square wave lacks:
# wave 2 -> harmonic 2 (bass/waka), wave 4 -> 8 (fright), wave 5 -> 16 (eat).
# Match those audible components rather than clamping their low fundamentals.
# See docs/ASSETS.md for references and the remaining timbre limitations.
ARCADE_PITCH = bytes.fromhex("00 57 5c 61 67 6d 74 7b 82 8a 92 9a a3 ad b8 c3")
INTRO_LEAD = bytes.fromhex(
    "42 50 4e 50 49 50 46 50 4e 49 70 66 70 "
    "43 50 4f 50 4a 50 47 50 4f 4a 70 67 70 "
    "42 50 4e 50 49 50 46 50 4e 49 70 66 70 "
    "45 46 47 50 47 48 49 50 49 4a 4b 50 6e")
INTRO_BASS = bytes.fromhex(
    "82 70 69 82 70 69 83 70 6a 83 70 6a "
    "82 70 69 82 70 69 89 8b 8d 8e")

def arcade_song(voice, data, shift, harmonic=1, decay=False):
    """Regular song bytes: duration in bits 5-7, pitch/octave in bits 0-4."""
    out = []
    step = 0
    for b in data:
        frames = 1 << (b >> 5)
        if b & 31:
            step = ARCADE_PITCH[b & 15] << (shift + bool(b & 16))
        # Type-1 bass notes reach zero volume for their final two frames.
        audible = min(frames, 14) if decay and step else frames
        out += hz_stream(voice, [(namco_hz(step) * harmonic, audible)])
        if frames > audible:
            out.append((0, frames - audible))
    return out

def arcade_steps(voice, steps, harmonic=1):
    return hz_stream(voice, [(namco_hz(f) * harmonic, 1) for f in steps])

# Five audible frames plus silence. Maze seeds are 8 pixels apart, leaving
# time for the complete falling/rising waka even at the fastest player speed.
CHOMP1 = arcade_steps("alto", [0x1500 - i * 0x300 for i in range(5)], 2) + [(0, 1)]
CHOMP2 = arcade_steps("alto", [0x0700 + i * 0x300 for i in range(5)], 2) + [(0, 1)]
FRIGHT = arcade_steps("sop", [i * 0x180 for i in range(1, 9)], 8)

# Death warble, one register dump frame each, then the two rising chirps.
DEATH_FREQ = [
    0x1F00, 0x1E00, 0x1D00, 0x1C00, 0x1B00, 0x1C00, 0x1D00, 0x1E00, 0x1F00, 0x2000, 0x2100,
    0x1D00, 0x1C00, 0x1B00, 0x1A00, 0x1900, 0x1800, 0x1900, 0x1A00, 0x1B00, 0x1C00, 0x1D00, 0x1E00,
    0x1B00, 0x1A00, 0x1900, 0x1800, 0x1700, 0x1600, 0x1700, 0x1800, 0x1900, 0x1A00, 0x1B00, 0x1C00,
    0x1900, 0x1800, 0x1700, 0x1600, 0x1500, 0x1400, 0x1500, 0x1600, 0x1700, 0x1800, 0x1900, 0x1A00,
    0x1700, 0x1600, 0x1500, 0x1400, 0x1300, 0x1200, 0x1300, 0x1400, 0x1500, 0x1600, 0x1700, 0x1800,
    0x1500, 0x1400, 0x1300, 0x1200, 0x1100, 0x1000, 0x1100, 0x1200,
    0x0800, 0x1000, 0x1800, 0x2000, 0x2800, 0x3000, 0x3800, 0x4000, 0x4800, 0x5000, 0x5800,
    0, 0x0800, 0x1000, 0x1800, 0x2000, 0x2800, 0x3000, 0x3800, 0x4000, 0x4800, 0x5000, 0x5800,
]

def siren(base, increment, half_period):
    """Channel-2 effect tables: an 8-bit base shifted seven hardware bits."""
    steps = [base + i * increment for i in range(half_period)]
    steps += [base + i * increment for i in range(half_period, 0, -1)]
    return arcade_steps("bass", [f << 7 for f in steps])

# Fruit bite: complete 23-frame triangle, including its low turning point.
# Alto keeps the low notes within one VIC divider of the target frequency.
def fruit_bite():
    steps = [0x1600 - i * 0x200 for i in range(11)]
    steps += [0x400 + i * 0x200 for i in range(12)]
    return arcade_steps("alto", steps) + [(0, 1)]

SOUNDS = {}
SOUNDS["JINGLE_S"] = arcade_song("sop", INTRO_LEAD, shift=6) + [(0, 1)]
SOUNDS["JINGLE_B"] = arcade_song("bass", INTRO_BASS, shift=3, harmonic=2, decay=True) + [(0, 1)]
SOUNDS["CHOMP1"] = CHOMP1
SOUNDS["CHOMP2"] = CHOMP2
SOUNDS["HONEY"] = FRIGHT + [(0, 1)]
SOUNDS["EAT"] = arcade_steps("alto", [i * 0x20 for i in range(32)], 16) + [(0, 1)]
SOUNDS["DEATH"] = hz_stream("sop", [(namco_hz(f), 1) for f in DEATH_FREQ]) + [(0, 1)]
SOUNDS["BONUS"] = fruit_bite()
SOUNDS["EXTRA"] = [(reg("sop", namco_hz(0x1000)), 10), (0, 2)] * 10 + [(0, 1)]
SOUNDS["SIREN1"] = siren(0x20, 4, 12)
SOUNDS["SIREN2"] = siren(0x28, 5, 11)
SOUNDS["FRIGHT"] = FRIGHT
SOUNDS["EYES"] = arcade_steps("sop", [0x6A00 - i * 0x600 for i in range(16)])
SOUNDS["START"] = [(reg("sop", 700), 3), (0, 1)]
# Append new streams to preserve existing sound IDs.
SOUNDS["SIREN3"] = siren(0x30, 6, 10)
SOUNDS["SIREN4"] = siren(0x3C, 7, 9)
SOUNDS["SIREN5"] = siren(0x48, 8, 8)

def main():
    out = ["; generated by tools/mksound.py -- do not edit\n"]
    names = list(SOUNDS)
    for i, nm in enumerate(names):
        out.append(f"SND_{nm} = {i}\n")
    out.append("snd_lo:\n" + "".join(f"    .byte <snd_{nm.lower()}\n" for nm in names))
    out.append("snd_hi:\n" + "".join(f"    .byte >snd_{nm.lower()}\n" for nm in names))
    total = 0
    for nm in names:
        pairs = merge(SOUNDS[nm]) + [(0, 0)]
        total += len(pairs) * 2
        out.append(f"snd_{nm.lower()}:\n")
        for i in range(0, len(pairs), 8):
            out.append("    .byte " + ",".join(f"${v:02X},{c}" for v, c in pairs[i:i + 8]) + "\n")
    jl = max(sum(c for _, c in merge(SOUNDS[nm])) for nm in ("JINGLE_S", "JINGLE_B"))
    out.insert(1, f"JINGLE_FRAMES = {jl}\n")
    with open(sys.argv[1], "w") as f:
        f.write("".join(out))
    print(f"sound: {len(names)} streams, {total} bytes, jingle {jl} frames")

if __name__ == "__main__":
    main()
