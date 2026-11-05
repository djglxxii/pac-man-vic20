# Faster audio register unpacking and pitch scaling

**Accepted, 2026-11-04; included in the standard build.** This intermediate
version is retained; see the [README](../README.md) for the latest default.
This standalone audio-adapter step improves actual VICE capture
**28.84 → 29.81 redraws/s**, about **3.4%**, on the saved route. Average audio
translation falls **646 → 393 cycles per tick**.

```sh
make run-audio-update-fast
```

Press **5**, **1**, then use the arrow keys. Compare this intermediate version
with `make run-audio-divider-fast`. `make run` includes this adapter and all
later accepted improvements.

## Profiled target

After the [accepted pitch lookup](AUDIO_DIVIDER_OPTIMIZATION.md), saturating
pitch scaling still costs **276 cycles per logical tick**, unpacking the
frequency registers costs **93**, and compiler save/restore costs **45**.
These are exclusive instruction costs averaged over the saved active route.
The complete C adapter averages 645.51 cycles including interrupts, or 3.83%
of native CPU time. The original sound interpreter is a separate routine and
is unchanged here.

The compiled scaling loops transfer a 16-bit value through temporaries and
repeat loop/overflow checks for individual shifts. The small remaining memory
budget favours compact code using existing scratch over another large table.

## Implementation and contract

`src/audio_update.S` supplies `audio_update` under `AUDIO_UPDATE_FAST`.
The C adapter in `src/platform.c` remains available to all other builds.
The complete small adapter is replaced so a C wrapper does not save pointers
and registers around each assembly operation.

- Unpack each pair of frequency nibbles directly. Four shifts discard the
  unused high bits of each upper nibble; the lower nibble is explicitly masked.
- Keep the high frequency byte in A while scaling. Shift the low scratch byte
  and rotate its carry into A. An outgoing high-byte carry detects saturation.
- Return the exact known divider result, 254, for a saturated phase step.
  Other nonzero pitches use the accepted divider, including its general fallback.
- Read, compare and conditionally write pitch ports in the existing order:
  bass, soprano, alto. Then write noise zero and the enabled maximum volume.

The eight waveform shifts are unchanged. Their small table moves from C's
zero-page data to read-only BLK5 storage. Channel biases, first-voice fifth
nibble, zero frequency, high-bit masking, rounding, saturation, mute/enable
behaviour and global volume all retain their previous results. Sound selection,
envelopes, sequencing, interruptions and the 16,875-cycle arcade clock remain
unchanged. There are no audio samples or replacement effect sequences.

The kernel uses legal NMOS 6502 instructions, A/X/Y, three existing caller
scratch bytes (`__rc2..4`) and the divider's existing `a_*` scratch. It preserves
the software stack pointer, `__rc5..31`, source sound registers, renderer and
game state. It runs only in the main thread; the clock IRQ preserves A/X/Y and
does not use these temporaries. No writable allocation or stack reservation is
added. Linked disassembly was checked for actual zero-page addressing.

## Measurements

| Measurement | Previous pitch lookup | Accepted adapter |
| --- | ---: | ---: |
| Actual VICE redraws/s | 28.84 | **29.81** |
| Completed redraws in actual capture window | 564 | **583** |
| Native replay redraws/s | 28.92 | **29.93** |
| Mean audio update, cycles including IRQs | 645.51 | **393.17** |
| Native CPU share in audio translation | 3.83% | **2.33%** |
| Identical live-input audio cycles, IRQs masked | 643.84 | **391.87** |
| Mean native refresh, cycles including IRQs | 16,941.28 | 16,871.66 |
| Actual 95th-percentile redraw interval | 51.06 ms | **50.24 ms** |
| Actual maximum redraw interval | 58.53 ms | **61.04 ms** |
| Maximum native input-service gap | 37.55 ms | **38.31 ms** |
| Maximum native audio-service gap | 37.78 ms | **37.56 ms** |
| Resident end / free before full stack | $7CB3 / 141 bytes | $7CB3 / 141 bytes |
| Free in BLK5 | 24 bytes | **151 bytes** |

Average complete audio cost falls about **39.1%**. On identical active-play
inputs with IRQs masked, the new adapter saves **304,129 cycles** in total,
about **1.49%** of the baseline whole-game replay's CPU time. Exclusive scaling
falls **275.69 → 115.42 cycles/tick**, unpacking **92.53 → 83.12**, pitch output
**43.93 → 25.93** and volume/noise **44.84 → 25.00**. The old 45-cycle compiler
save/restore disappears. Divider work is identical on this active sample.

The whole-game timing includes changed interrupt overlap and code placement.
Different redraw cadence also samples different sprite poses, so mean refresh
cost is not an identical-input renderer speed comparison. No renderer change
was made. The longest redraw and input gaps are slightly worse despite the
average gain. This remains below 30 redraws/s on the actual capture and does
not establish fixed 30 Hz pacing or worst-case deadlines.

The 473-byte C adapter becomes 338 bytes of assembly plus an eight-byte table.
BLK5 therefore recovers **127 bytes**. Resident headroom remains 141 bytes,
and the full **704-byte stack** remains at $7D40–$7FFF. The target is still
NTSC with +3K and BLK1/2/3/5 expansion. Packed PRG size falls from 26,854 to
26,701 bytes; packed size is separate from resident/bank usage.

## Equivalence and visible limits

`tests/audio_update.py` executes **524,288 frequency/shift pairs per build**:
all 65,536 raw 16-bit frequencies at each effective shift 0 through 7, using
representative voice/wave selections covering those eight shifts. Both
actual adapters must match an independent host formula for the five VIC sound
registers. Another 2,048 full-byte random cases, 2,048 fifth-nibble/wave cases,
768 volume-priority cases, three mute/re-enable cases and 1,639 saved live
inputs bring the recorded total to **530,794 cases per build**. Three additional
ABI fixtures check zero-page preservation, source registers and game state.
Isolated timing includes RTS and excludes the caller's JSR; IRQs are masked.

The live-input benchmark reproduces the captured previous hardware values and
audio inputs. Both active-input cost totals match the corresponding unmodified
game profiles' exclusive audio instruction costs. Uniform cases cover extremes
and are not an FPS prediction.

`make test-audio-update-fast` passes all **15 original-ROM comparisons**,
**40 pooled checks**, four new adapter tests and 12 classifier tests. The
whole-program replay matches all **1,207 active game states**. All **1,639 audio
ticks** have identical effect/song state, frequency/volume state and arcade/VIC
register values; the output digest remains
`036d6b018d706342f9bc5344f1f5ef89a91b07515c86de0d7be9d5af4d777e26`.
These are logical-tick values; CPU write timestamps differ. The user accepted
the live result and requested promotion. No physical-hardware test is claimed.

Smoke passes all three intermissions and **7,184 logical ticks**, preserving
the IRQ vector, stack guard and boot handoff. Observed software/hardware stack
use is 30/22 bytes, with the full reservation retained.

The new actual VICE capture has **1,180 consecutive raster frames** and verifies
all 33,792 depacked bytes against its own PRG. It passes **560 settled-picture
oracles** and **4,536 synthetic absent/partial controls**, with zero false
absent/partial settled results. No fully absent actors occur among eligible
cases. Partial poses remain and vary with timing:

| Actor | Standard present / partial / excluded | Trial present / partial / excluded |
| --- | --- | --- |
| Pac-Man | 987 / 16 / 177 | 981 / 22 / 177 |
| Blinky | 887 / 14 / 279 | 890 / 11 / 279 |
| Pinky | 843 / 12 / 325 | 839 / 12 / 329 |
| Inky | 932 / 12 / 236 | 921 / 19 / 240 |
| Clyde | 873 / 9 / 298 | 870 / 9 / 301 |

Shared-colour cells, rewards, clipping, hidden actors and insufficient distinct
ink remain excluded. The generated evidence image was inspected. This is a
speed experiment; it does not establish a perceptible flicker improvement.

## Reproduction and evidence

```sh
make test-audio-update-fast
python3 tools/arcade/profile_audio.py --prg build/audio-update-fast/pacman.prg --native build/audio-update-fast/pacman-native.bin --map build/audio-update-fast/pacman.map --output build/audio-update-fast/new-cpu
python3 tools/arcade/measure_display.py --prg build/audio-update-fast/pacman.prg --input tests/fixtures/active-replay.json --frames 1180 --output build/audio-update-fast/new-vice
python3 tools/arcade/analyze_display.py --capture build/audio-update-fast/new-vice
```

Run native fixture tools sequentially and use new capture/profile directories.
The audio profiler uses disjoint linked labels for the assembly adapter and
keeps the C layout's hash guard. Both modes verify depacked bytes and game/audio
outputs without guest patches. The accepted baseline's existing profile and
VICE capture are reused because their PRG/input hashes match this comparison.

Raw data is under `build/audio-update-fast/evaluation/`; the
[frozen results](baselines/audio-update-fast.json) retain compact measurements
and source hashes. Baseline PRG SHA-256:
`f0ca4b5135bb0cf7418996fc1e6cf9e05c245d92778fda566547f0f29bc39d7c`.
Accepted adapter PRG SHA-256:
`358a4f93334164904a12ecf60df43f13559df92feb6c534f634517e5b67b8672`.
The [optimization queue](RESEARCH_OPTIMIZATION_PLAN.md#remaining-optimization-candidates)
records this follow-up as accepted and included in the standard build. The
frozen results retain their pre-promotion status as historical evidence.

Promotion initially preserved the tested executable: the default PRG, labels,
native image, ELF and linker map matched the accepted build byte for byte.
The full `make test` run passed for that executable. `make test` checks the
default PRG with both exhaustive audio suites, the sound-state
replay and the retained gameplay, sprite, tunnel and intermission checks.
See [the promotion evidence](baselines/audio-update-promotion.json) and
[the test log](../build/audio-update-fast/evaluation/promotion-tests.log).

A concurrent edit to `hires-pacman.json` then replaced the final death-animation
frame and rebuilt the game. Its depacked image differs in just nine bytes,
all within sprite $3E's twelve-byte mask; all code and other data remain
identical to the fully tested executable. At that point the default and explicit
adapter builds matched. That separate artwork edit was preserved; the full suite
was not rerun during that earlier artwork rebuild. Both identities are recorded
in the audio promotion evidence. The later
[ghost-update promotion](baselines/ghost-update-promotion.json) retains that artwork.
