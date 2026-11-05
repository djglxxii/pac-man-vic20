# Precomputed VIC pitch translation

**Accepted after live review, 2026-11-04; included in the standard
[audio-adapter build](AUDIO_UPDATE_OPTIMIZATION.md).** The standalone pitch-lookup
build remains available for comparison. Actual VICE capture improves
**27.46 → 28.84 redraws/s**, about **5.0%**, on the saved route.

```sh
make run-audio-divider-fast
```

Press **5**, **1**, then use the arrow keys. `make run` launches the latest
standard. Compare with `make run-pool-stamp-fast` for this version's predecessor.
The standalone PRG is `build/audio-divider-fast/pacman.prg`.
Both builds include
the intermission artwork accepted in commit `363f6a8`.

## What audio translation does

The original game routines produce virtual Namco pitch, waveform and volume
registers each logical tick. `audio_update` maps those instructions to the
VIC's three tone generators. Sound selection, envelopes, song sequencing and
interruptions stay in the game. The VIC chip generates the audible tones.

Precomputing exact pitch conversions avoids repeated arithmetic while
retaining variable gameplay sounds. This change stores pitch results, not
recorded audio clips or replacement effect sequences.

## Measurement before implementation

`tools/arcade/profile_audio.py` observes the actual PRG on the saved logical-tick
input replay. It verifies all 33,792 depacked bytes before startup, checks all
1,207 active game states, captures the audio inputs/outputs on 1,639 ticks and
attributes instruction cycles using audited ranges of the linked converter.
Its converter-body hash guard rejects a changed C layout until the ranges
are reviewed. Host observations add no guest instructions or cycles.

The baseline takes **967.81 cycles per tick**, including interrupts inside
the routine, or **5.74%** of native CPU time. Its exclusive work is:

| Work | Cycles per tick | Share of total CPU |
| --- | ---: | ---: |
| Nearest-divider search | 372.38 | 2.21% |
| Saturating pitch scaling | 275.69 | 1.63% |
| Frequency-register unpacking, including first-voice high bits | 92.53 | 0.55% |
| Volume/enable gates | 61.84 | 0.37% |
| Save/restore and return | 45.00 | 0.27% |
| Shared volume and noise output | 44.84 | 0.27% |
| Pitch-register comparison/writes | 43.93 | 0.26% |
| Zero check and divider call setup | 28.25 | 0.17% |

Interrupt entry and handler work account for the remaining 3.34 cycles per
tick. The interpreter optimized earlier is separate from these costs.

All **1,893 active-play divider calls** use a scaled phase step divisible
by 128. These are converter inputs, not frequencies in hertz. Across the
whole replay, including the introductory music, **1,988 of 2,278 calls**
(87.27%) fit that grid. There are 43 distinct active-play inputs and 57
across the whole replay.

Remembering only each voice's last conversion gives **zero hits during active
play**: each audible voice changes pitch on each call in this sample. It
would hit 284 times during the earlier music. A small exact table therefore
has stronger evidence than a last-pitch cache. A table with one entry for
every possible 16-bit input would take 64 KiB; the regular grid needs 256 bytes.

## Implementation

With `AUDIO_DIVIDER_FAST`, `src/audio.S` adds a fast path to `audio_divider`:

- Inputs divisible by 128 and below 32768 index a 256-byte table, generated
  by the assembler with the existing nearest-divider rounding formula.
- Grid inputs at or above 32768 directly return 254: their nearest legal
  divider is always one.
- Other inputs retain the original seven-comparison search, with five cycles
  added for the fast-path test. The original tables remain available.

The table is general over that input grid; it is not a list of pitches
encountered on this route. No cache, validity flags or new writable state are
needed. The routine uses legal NMOS 6502 instructions and existing scratch,
preserving Y, the software stack pointer, callee-saved compiler registers and
renderer scratch. The normal C converter and register-write order are unchanged.

Channel mapping, waveform approximation, saturation, pitch rounding, volume,
enable/disable handling, noise output, sound sequencing and audio service
frequency remain unchanged. The arcade clock stays at 16,875 cycles per tick.

## Results

| Measurement | Previous composition build | Accepted pitch lookup |
| --- | ---: | ---: |
| Actual VICE redraws/s | 27.46 | **28.84** |
| Completed redraws in actual capture window | 537 | **564** |
| Native replay redraws/s | 27.57 | **28.92** |
| Mean complete audio update, cycles including IRQs | 967.81 | **645.51** |
| Native CPU share in audio translation | 5.74% | **3.83%** |
| Exact active divider work, cycles | 449,463 | **62,469** |
| Mean native refresh, cycles including IRQs | 17,056.53 | 16,941.28 |
| Actual 95th-percentile redraw interval | 54.50 ms | **51.06 ms** |
| Actual maximum redraw interval | 74.87 ms | **58.53 ms** |
| Maximum native input-service gap | 40.34 ms | **37.55 ms** |
| Maximum native audio-service gap | 38.16 ms | **37.78 ms** |
| Resident end / free before full stack | $7BB3 / 397 bytes | $7CB3 / 141 bytes |

The grid path takes **33 cycles** below 32768, or **23 cycles** above it,
including RTS and excluding the caller's JSR, with IRQs masked. All grid cases
are faster. All 65,024 off-grid inputs cost exactly **five cycles more** than
the baseline. Exact weighting by the saved active-play inputs saves **386,994
divider cycles**, or **1.90% of baseline total CPU time**. Other exclusive
converter costs are identical. Mean complete audio cost falls about **33.3%**;
its inclusive saving also reflects different interrupt overlap.

This is one saved workload, not a worst-case deadline guarantee or a sustained
30 Hz claim. Faster rendering samples different poses, so full-refresh costs
are not identical-input kernel measurements. Partial poses and colour sharing
remain. This experiment targets speed.

## Memory and hardware

The lookup occupies 256 resident bytes. Its 22 added instruction bytes fit
within existing alignment space in this linked build, making the net resident
increase **256 bytes**. The table happens to be page aligned here; the source
requests no extra alignment padding. Another placement can add one cycle to
an indexed read. BLK5 retains 24 bytes free, and the full **704-byte software
stack** remains at $7D40–$7FFF. No writable allocation or hardware expansion
changes are needed. The target stays NTSC with +3K and BLK1/2/3/5 expansion.

The current baseline PRG is 26,758 bytes and the trial 26,854 bytes. Packed
size differs from resident use. The baseline differs from the earlier frozen
composition PRG because of the subsequently accepted intermission artwork;
both new measurements use that current artwork.

## Verification

`make test-audio-divider-fast` covers the original-ROM comparisons, pooled
gameplay/render/colour/font/memory tests, four new divider/converter tests,
the tick-indexed sound replay, classifier tests and all three intermissions.

`tests/audio_divider.py` calls both actual kernels for **all 65,536 inputs**,
checks each result against the rounding formula, reads back the whole new
table, checks ABI guards and compares 325 complete converter fixtures. These
include full-byte register masking, saturation, silence and disable/re-enable
transitions. Kernel costs are measured with IRQs masked; no timing estimate
is substituted for execution.

All **1,639 replayed ticks** have identical effect/song state, frequency/volume
state and arcade/VIC registers. Their output digest remains
`036d6b018d706342f9bc5344f1f5ef89a91b07515c86de0d7be9d5af4d777e26`.
This checks logical-tick values; CPU write timestamps differ. The user accepted
the live result and requested promotion. No physical-hardware test is claimed.

Both actual VICE captures contain **1,180 consecutive raster frames** and
verify all 33,792 depacked bytes against their own PRG. The trial passes
**543 settled-picture oracles** and **4,398 synthetic absent/partial controls**,
with no false absent/partial settled result. No fully absent actors occur
among eligible cases. Partial-pose counts are:

| Actor | Standard present / partial / excluded | Trial present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 979 / 19 / 182 | 987 / 16 / 177 |
| Blinky | 873 / 23 / 284 | 887 / 14 / 279 |
| Pinky | 837 / 12 / 331 | 843 / 12 / 325 |
| Inky | 931 / 9 / 240 | 932 / 12 / 236 |
| Clyde | 862 / 11 / 307 | 873 / 9 / 298 |

Shared-colour cells, rewards, clipping, hidden actors and insufficient distinct
ink remain excluded. Timing changes can expose different partial poses; the
capture does not establish a perceptible flicker improvement. Smoke reaches
7,183 ticks with the IRQ vector, stack guard and boot handoff intact; observed
stack use is 30 software and 22 hardware bytes.

## Reproduction and tracking

```sh
make test-audio-divider-fast
python3 tools/arcade/profile_audio.py --prg build/pool-stamp-fast/pacman.prg --native build/pool-stamp-fast/pacman-native.bin --map build/pool-stamp-fast/pacman.map --output build/audio-divider-fast/new-baseline-cpu
python3 tools/arcade/profile_audio.py --prg build/audio-divider-fast/pacman.prg --native build/audio-divider-fast/pacman-native.bin --map build/audio-divider-fast/pacman.map --output build/audio-divider-fast/new-trial-cpu
python3 tools/arcade/measure_display.py --prg build/audio-divider-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/audio-divider-fast/new-trial-vice
python3 tools/arcade/analyze_display.py --capture build/audio-divider-fast/new-trial-vice
```

Use a new capture directory and run native fixture tools sequentially. Raw
profiles, per-tick inputs/outputs, raster frames and logs live under
`build/audio-translation-profile/baseline/` and
`build/audio-divider-fast/evaluation/`. Compact results and source hashes are
tracked in [the frozen evidence](baselines/audio-divider-fast.json). The
[optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates)
records the pitch lookup as accepted and included in the standard build.
The frozen evidence retains its pre-promotion status as historical evidence.
Scaling is the largest remaining converter cost in this accepted version;
the accepted [adapter optimization](AUDIO_UPDATE_OPTIMIZATION.md) now addresses
it in the standard build. The larger
display cache and pacing changes remain deferred.

The original promotion preserved the tested executable: the default PRG,
labels, native image, ELF and linker map matched the accepted build byte for
byte. That PRG's
SHA-256 is `f0ca4b5135bb0cf7418996fc1e6cf9e05c245d92778fda566547f0f29bc39d7c`.
The promotion's `make test` ran the divider tests and audio replay against the default PRG,
alongside the existing gameplay, sound-effect, tunnel, sprite and intermission
checks. Promotion verification is recorded in
[the promotion evidence](baselines/audio-divider-promotion.json) and
[the test log](../build/audio-divider-fast/evaluation/promotion-tests.log).
