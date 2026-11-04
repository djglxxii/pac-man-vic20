# Faster sound-effect processing

**Accepted on 2026-11-04; now included in the standard
[composition build](POOL_STAMP_OPTIMIZATION.md).** The standalone sound
version remains available for comparison. Its original promotion passed
`make test` against the default PRG and confirmed that all five default files
were byte-identical to their explicit sound-build files.

Third speed improvement, built on [empty-row skipping](POOL_SKIP_EMPTY.md). Actual
VICE capture improves from **23.21 to 25.67 redraws/s**, about **10.6%**, on
the saved route. The current sound is the reference: effect state, pitch,
volume and sequencing are preserved.

```sh
make run-sound-effect-fast
```

Press **5**, **1**, then use the arrow keys. Compare with
`make run-pool-skip-empty` for the preceding build, or `make run-glyph-pool`
for the original accepted pool. `make run` launches the latest standard build.
Listen to the pellet, siren, frightened, ghost-eaten and
death effects as well as the opening music. The hardware target and gameplay
clock are unchanged.

## Change

The previous active native profile attributed **8.08%** of CPU time to
`soundEffectOneChannel_2dee`, including its callees. This interpreter selects
the highest-priority requested effect, loads its definition and advances
duration, repetition, pitch and volume state. Its compiled C implementation
also paid substantial register-save, software-stack and pointer-access costs.

`src/sound_effect.S` replaces this bounded effect interpreter with legal NMOS
6502 assembly under `SOUND_EFFECT_FAST`. It uses the existing C calling
convention and caller scratch registers, with no new RAM. The existing
frequency-output and volume-envelope function remains the shared tail for
songs and effects. C compile-time assertions guard every state-field offset
used by assembly. The original C interpreter remains available in all earlier
builds and in the host reference.

The VIC pitch converter, waveform approximation, channel mapping, music
sequencer, game clock and renderer code are unchanged. The trial includes the
preceding address and empty-row optimizations. It changes neither how often
the logical sound routines are called nor their ordering within a game tick.

## Sound and gameplay equivalence

`tests/sound_effect.py` executes the actual baseline and trial PRGs with
**7,748 identical-input cases per binary**:

- All 16 real effect definitions and three combined priority masks, each
  advanced for 192 updates: 3,648 comparisons.
- Cancellation and inactive-state checks.
- 2,048 randomized states covering duration/repeat boundaries, effect changes,
  reversal and byte overflow.
- Every eight-bit pitch accumulator at all eight scales, covering all sixteen
  volume handler types: 2,048 comparisons.

The comparison checks all sixteen effect-state bytes, all four frequency
bytes and the returned volume exactly, including the unused high bits kept
by the C implementation. Adjacent canaries, software stack pointer and
callee-saved compiler registers must survive. Relocated fixtures exercise
page-crossing source/state/output pointers. Real effect definitions must be
identical between binaries.

`tools/arcade/check_audio_replay.py` separately runs each full program on the
saved input route. After every actual `audio_update` call it compares effect
and song state, frequency/volume state, all 32 virtual arcade sound-register
bytes and all five VIC sound-register bytes. **All 1,639 ticks match exactly**,
including boot and game lead-in. The native performance replay also matches
all **1,207 active logical game states** against the saved reference.

These are identical values at matching logical ticks, not identical CPU-cycle
write timestamps or a PCM waveform comparison. Faster processing changes
service delays and display cadence. No listening or real-hardware validation
is claimed; live play testing remains useful for judging the sound and feel.

## Speed and memory

| Measurement | Empty-row trial | Fast effects |
| --- | ---: | ---: |
| Actual VICE redraws/s | 23.21 | **25.67** |
| Native replay redraws/s | 23.40 | **25.75** |
| Active effect-channel calls | 2,009 | 2,009 |
| Mean effect-channel cycles, including callees/IRQs | 818.94 | **376.13** |
| Total effect-channel cycles on active route | 1,645,258 | **755,655** |
| Actual 95th-percentile redraw interval | 64.48 ms | **56.55 ms** |
| Actual longest redraw interval | 83.05 ms | **70.47 ms** |
| Maximum native input-service gap | 37.40 ms | 42.61 ms |
| Maximum native audio-service gap | 40.08 ms | **37.18 ms** |
| Resident code/data end | $7D34 | **$7BBC** |

Effect processing uses about **54% fewer cycles** on the active native replay.
The separate uniform kernel sample averages 806.96 versus 355.76 cycles; it
contains artificial states and inactive calls and is not an FPS prediction.
Not every latency improves: the largest observed input-service gap increases
as faster logic admits more redraws. No redraw scheduling policy changes here.

Resident code/data reclaims **376 bytes**, leaving **388 bytes** before the
unchanged 704-byte stack at $7D40–$7FFF. Existing compiler scratch is reused.
The period-correct NTSC +3K and BLK1/2/3/5 memory configuration remains the same.

## Display and regression validation

The actual capture contains **1,180 consecutive raster frames**, with the
same joystick input per logical tick as its predecessor. All **33,792 depacked
bytes** match the trial PRG. There are no guest code patches, PC gating or timer
changes. Analysis passes **482 settled-picture oracles** and 3,904 synthetic
absent/partial controls, with no false disappearance on settled pictures.
No fully absent actors occur among classified cases.

Partial poses remain. Pac-Man has 977 present, 24 partial and 179 excluded
samples, versus 993, 16 and 171 previously; ghost counts vary in both directions.
Shared cells, rewards, clipping and insufficient distinct ink retain the
classifier's exclusions. This is a speed improvement, not evidence of an
additional perceptible flicker reduction. The same route/capture pair does not
establish worst-case performance or variability across runs.

The [comparison video](../build/sound-effect-fast/evaluation/glyph-pool-comparison.mp4)
uses natural-cadence VICE frames, executable hashes and ticks. It has no audio.
Its preview and the trial's raster evidence were visually inspected.

The trial passes **15 ROM comparisons**, **39 pool/logic/audio/memory/font
checks**, the four new effect tests and **12 classifier checks**. Smoke reaches
all three intermissions and 7,183 logical ticks with the full stack reservation,
stack guards and IRQ vector intact. Maximum observed software stack use is
30 bytes. Static cycle review confirms legal NMOS addressing/instructions.

## Reproduction

```sh
make test-sound-effect-fast
python3 tools/arcade/profile_game.py --prg build/sound-effect-fast/pacman.prg --map build/sound-effect-fast/pacman.map --output build/sound-effect-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/sound-effect-fast/pacman.prg --output build/sound-effect-fast/new-vice --frames 1180
python3 tools/arcade/analyze_display.py --capture build/sound-effect-fast/new-vice
```

`make test` and `make test-sound-effect-fast` include exact effect comparisons
and the tick-indexed sound-register replay. Raw measurements remain under
`build/sound-effect-fast/evaluation/`; [frozen results](baselines/sound-effect-fast.json)
record program identities and compact evidence from before promotion. The
standalone sound-build PRG is byte-identical to the measured trial:
`1f33cc8ed6eba5a7216edf6d94ae54c671ea12296bae4e05eeb2c57fd4b47659`.
The predecessor remains
`e2ed39e298fefa8677eb7271056bedc8b7d5a4c410faabcbd99155bff3213211`.
