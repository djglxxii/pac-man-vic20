> Historical baseline: this audit describes the initial custom engine, before
> the arcade-core replacement. See VALIDATION.md for the current revision.

# Arcade parity audit

Audited baseline: `beb08f2ae49502a09cb652033d50a3a11125e542`, 2026-10-31.

## Verdict

**The conversion does not currently meet the goal of arcade Pac-Man parity,
or of the closest practical VIC-20 adaptation.** It is a working original
maze-chase game with recently improved Pac-Man artwork and sound. Several
major differences are software design choices, not demonstrated hardware
limitations. Matching the arcade requires changes to game logic and the
presentation state machine, alongside a rendering feasibility study.

The sprite and audio passes improved individual assets. Their successful
tests did not establish parity for the game as a whole.

## Reference and scope

Use the original Midway US `pacman` release, normal difficulty, three lives,
and one bonus life at 10,000 as the baseline. This choice follows the local
`pacman.zip`; it is not an assumption that every Pac-Man revision has the
same names, settings or bugs. Its four program ROM checksums match the
[MAME Pac-Man driver](https://github.com/mamedev/mame/blob/master/src/mame/pacman/pacman.cpp):

| ROM | CRC32 |
|-----|-------|
| `pacman.6e` | `c1e6ab10` |
| `pacman.6f` | `1a6fb2d4` |
| `pacman.6h` | `bcdd1beb` |
| `pacman.6j` | `817d94e3` |

Evidence combines the repository's source, generated tables, runtime probes,
and direct inspection of those local ROMs. The arcade fruit table at `$0EFD`
and intermission dispatch table at `$0A45` were decoded directly.
[arcade-parity-evidence.json](arcade-parity-evidence.json) records the checksums,
table decodes and probe results.

For understanding the original instructions, the audit also consulted
[Mark Burkley's translation with retained Z80 listings](https://github.com/mburkley/pacman-c/blob/3277e56d24df82882fd99712464fed6786706e68/pacman.c).
The retained instructions and local ROM are the reference; the translation
itself documents remaining bugs and is not a substitute for an arcade oracle.
Additional reference material:

- [The Pac-Man Dossier](https://pacman.holenet.info/), especially its level,
  movement and ghost-house tables.
- [Frédéric Vecoven's sound disassembly](https://www.vecoven.com/elec/pacman/code/pac_z80.html).
- [Commodore's component data catalog, 6560/6561 section](https://www.bitsavers.org/pdf/commodore/Commodore_Component_Data_Catalog_1981.pdf).
- [VICE's VIC-20 timing definitions](https://github.com/VICE-Team/svn-mirror/blob/main/vice/src/vic20/vic20.h).

This was a source and targeted emulator audit, not a frame-by-frame comparison
of every arcade scene or a natural playthrough to board 256. Unmeasured
details below remain acceptance work, rather than being declared correct.

## Findings

P0 means a change is needed to establish the intended game. P1 means a
significant parity gap. P2 means presentation refinement or an edge case.

### P0: The game identity and presentation flow are different

`README.md` explicitly describes original beetles, spiders, seeds and honey.
`the original game entry source:449` prints the previous custom game and STALKER/PROWLER/MIRROR/TRACKER.
Changing sprites did not replace those identities or the flow around them.

| Area | Current behavior | Required arcade behavior |
|------|------------------|--------------------------|
| Character introduction | All four custom names displayed together; skirts animate in place. | Timed character/nickname reveals for Blinky, Pinky, Inky and Clyde, with the matching descriptors. |
| Attract chase | Absent. | Pac-Man/ghost chase, energizer reversal, and ghost-eating demonstration. |
| Attract maze demo | Absent. | Autonomous arcade-style demonstration, followed by the attract cycle. |
| Start presentation | PUSH FIRE immediately starts one game. | Arcade credit/start presentation and player selection, or an explicit free-play control adaptation that retains the sequence. |
| HUD | 1UP and HI-SCORE only. | Target-release score/credit/player indicators and messages, adapted to the screen. |

The target name pairs are Shadow/Blinky, Speedy/Pinky, Bashful/Inky and
Pokey/Clyde. The target release's copyright text and start messages also
belong in the presentation comparison.

The current `mode_title` only blinks PUSH FIRE and polls fire. No timeout
starts a demo (`the original game entry source:462`). After 18,000 emulated frames without
input, mode remained TITLE and all four actor positions were unchanged.

The arcade ROM's intro dispatcher at `$03FE` contains the timed introduction
and demonstration states. Those states have no counterpart in the conversion.
Do not replace them with a newly invented logo/menu and call that arcade parity.

### P0: Every intermission is missing

`the original game entry source:967` flashes the maze, increments `level`, and jumps directly
to `start_level`. The seven-mode dispatch table contains no intermission
mode, timeline, scene assets or intermission music.

The local arcade dispatch table gives this exact schedule:

| Completed board | Scene |
|-----------------|-------|
| 2 | First chase and giant Pac-Man reversal |
| 5 | Blinky's sheet catches and tears |
| 9 | Repaired-sheet chase and exposed-body return |
| 13 | Repeat third scene |
| 17 | Repeat third scene |

For this ROM, the third scene does **not** repeat indefinitely after board 17.
The dispatch clamps at entry 20, which selects no scene.

Forced completion probes at each of those five boards observed only LEVEL
followed by READY. A board-21 control did the same. These were controlled
transition tests, not claims of naturally reaching those boards.

### P0: The maze topology and collectible count differ

`tools/mkdata.py:11` defines an original 21×21 maze. It has 167 ordinary dots
and four energizers: 171 collectibles and 1,870 base points per board.
The arcade maze has 240 ordinary dots plus four energizers: 244 collectibles
and 2,600 base points. The arcade playfield is 28×31 logical tiles, within a
28×36-character portrait display.

This changes routes, junctions, distances, tunnel geometry, the house and
starting positions. Arcade movement patterns cannot transfer to this maze.
The generator also forbids 2×2 wall blocks, reflecting its thin-line autotiler
rather than a requirement of Pac-Man or the VIC.

A scaled rendering is expected on the VIC. Replacing the logical maze is not
an equivalent concession. Preserve the arcade graph and collectibles while
investigating smaller logical tiles or another display mapping.

### P0: Three ghost personalities and the mode system are substitutes

The current target functions (`src/actors.s:630`) are:

- STALKER: target the player's tile, broadly resembling Blinky's chase target.
- PROWLER: line-of-sight attack and alternating patrol turns.
- MIRROR: reflect the player through the maze center.
- TRACKER: follow a roughly two-second-old player position.

The latter three do not implement Pinky's forward target, Inky's target
relative to Blinky, or Clyde's distance-dependent chase/scatter target.
The original targeting quirks, including the packed-coordinate upward
overflow, must be preserved if original patterns are part of the goal.

There is no timed scatter/chase controller or corresponding reversals.
`enemy_decide` selects a custom target whenever a ghost reaches a tile center.
`greedy` uses Manhattan distance; the arcade compares squared distance with
look-ahead steering. The shared up/left/down/right tie preference alone
does not make these algorithms equivalent. Special no-up junction rules
are also absent.

These are logic differences with no established VIC hardware justification.

### P1: Difficulty stops evolving at board 8

`start_level` caps `lvidx` at 7 (`the original game entry source:526`). Movement, frightened
time and release timing all reuse that final entry thereafter.
The arcade's normal difficulty sequence continues through board 21.

The current frightened durations are 360, 300, 240, 180, 150, 120, 90 and
60 frames. Board 8 onward always grants 60 frames. The reference schedule
is not monotonic and includes boards with no blue time. The current player
also remains faster than a normal ghost in the terminal table, unlike the
late arcade speed relationship. Compare against the full reference level
specifications, not just the first two matching frightened durations.

The normal-ghost speed code adds the same late-board acceleration to every
active non-frightened ghost when at most 20 dots remain
(`src/actors.s:394`). This is not Blinky's two-stage Cruise Elroy behavior.

### P1: Ghost-house and frightened decisions differ

`release_update` uses one running dot total and first-board limits 0/15/40.
After death it uses 3/12/24 (`src/tables.s:80`). The original has personal
counters and separate post-death global-counter rules, including the
7/17/32 checks. Its release-timer level grouping is also different.
The current nest motion is horizontal, rather than the arcade bounce.

Returning eyes use a generated shortest-path table (`src/actors.s:503`);
that is an alternate routing policy, not evidence of matching arcade paths.

The current frightened PRNG is an eight-bit LFSR, not the arcade's ROM-backed
random sequence. Its fallback increments the direction index; with this
port's direction encoding that turns counterclockwise, whereas the arcade
fallback turns clockwise. Reseeding deterministically does not establish
arcade path parity.

### P1: Fruit graphics are closer, but fruit rules and history are wrong

The eight icon types and their individual scores now broadly match. However,
`lvidx` also selects the fruit and its popup, advancing one icon every board:

| Board | Current | Reference ROM |
|-------|---------|---------------|
| 4 | Apple, 700 | Orange, 500 |
| 5 | Melon, 1,000 | Apple, 700 |
| 8 | Key, 5,000 | Melon, 1,000 |
| 9 | Key, 5,000 | Galaxian, 2,000 |

Keys should begin at board 13. Fruit triggers are 60/140 dots
(`src/actors.s:210`), rather than the original `$46`/`$AA` (70/170).
Lifetime is a fixed 540 frames instead of the reference's randomized timer.
`draw_status` reconstructs history from this same incorrect progression.

The fruit mapping must become separate from the difficulty-table index.

### P1: Credits, alternating two-player play and settings are absent

The conversion has one score, one maze state, one life count and one joystick
start action. There is no credit counter, one/two-player selection, second
player state, turn alternation, or cabinet-setting profile.

Three lives and a single bonus at 10,000 agree with the chosen default.
Supporting arcade alternatives requires explicit settings. A coin mechanism,
coin meters and cocktail screen rotation need not be literal VIC peripherals;
their omission is different from omitting the playable two-player mode.

### P1: Collision and movement equivalence have not been established

The collision routine checks wrapped pixel distances less than six in both
axes (`src/actors.s:882`), rather than the original tile-comparison behavior.
This affects near misses and pass-through cases.

One-frame dot pauses and three-frame energizer pauses are present. Early-turn
support and fixed-point movement are also present, but their timing and
decision ordering have not been compared with arcade traces. An original
pattern compatibility claim would therefore be unsupported even after
replacing the maze and ghost targets.

### P1: Audio is an adaptation and omits a complete music cue

Intro note bytes and death frequency steps are grounded in reference data.
Waka, fruit, ghost-eaten, siren, frightened and returning-eyes streams are
recognizable adaptations. Nevertheless:

- Harmonic substitution, divider quantization and per-note gating change
  timbre, pitch balance and envelopes.
- Extra-life modulation is approximated by on/off pulses.
- Siren selection uses fifths of this custom maze's remaining dots, rather
  than a verified arcade trigger schedule (`src/sound.s:186`).
- Intermission music is absent despite its source songs existing in the
  arcade ROM at `$3BF3` and `$3C95`.
- The unused START tone does not implement a credit-insertion cue or flow.

The VIC's tone generators and shared volume justify audible differences.
They do not explain missing compositions or arbitrary event schedules.
Existing audio tests compare the 6502 player with this port's own streams;
they do not compare recordings or event timing with an arcade oracle.

### P2: Art, scene timing and long-session behavior need further work

Normal actors are 8×8 single-color reductions. Font, thin-line maze walls,
HUD placement, fruit coloring and simplified death poses remain visually
different. Scene transition, blink, freeze and animation timing require
reference captures before being accepted as close enough.

The eight-bit level counter wraps back to the first tuning entry after
board 256; there is no deliberate arcade split-screen behavior. The fruit
history's signed `bmi` check also treats high level values as empty entries
(`src/screen.s:169`). The kill screen and obscure arcade bugs are lower
priority than restoring ordinary play, but must be explicit parity decisions.

## What already aligns

Useful foundations should be retained: four ghosts, four energizers, tunnel
wrapping and slowdown, ghost-eating chains of 200/400/800/1,600, basic 10/50
dot scoring, a single 10,000-point bonus life, high score, returning eyes,
ready/death/game-over phases and a stable software-sprite renderer.
This is partial feature coverage, not a claim of exact timing or behavior.

## Hardware limits versus current engine limits

The existing asset guide conflated some renderer restrictions with VIC
restrictions. In particular, **the VIC does not impose an 8×8 maximum on
software sprites**. Multiple characters can form a larger object; this
engine already uses two halves for 16-pixel score popups.

| Constraint | Assessment |
|------------|------------|
| No hardware sprites; limited CPU and video-visible RAM | Real hardware constraints. |
| Eight foreground choices in the current high-resolution mode | Real constraint of that mode. |
| Every actor must be one color and exactly 8×8 | Current renderer choice. Multicolor trades horizontal resolution for color; larger composites need more rendering work. Neither guarantees an exact arcade image. |
| Exactly 21×21 logical maze, 40 images and 32 dynamic cells per buffer | Current allocation and code choices. |
| No attract sequence, intermission, correct ghost targets or later-level tables | Missing software, not established hardware necessities. |
| Full 224×288 portrait image at native arcade resolution | Cannot be reproduced unchanged by this 168×192 NTSC display. A measured scaling/layout compromise is necessary. |

The linker map leaves 11,615 bytes before `$7000` in the main code/data area.
The existing play test peaks at 212/261 raster lines, with normal play peaking
at 184. These measurements do not prove that a redesigned renderer will fit,
but they do not justify declaring all missing scenes or logic infeasible.
Intermissions can use different asset banks and a simpler scene compositor
while the maze is absent; that is a feasibility proposal, not a tested design.

VICE's timing constants give about 60.2845 video frames/second here, compared
with the arcade's 60.6061. Decide whether to compensate logical tick rate or
accept and document the roughly 0.53% slowdown in frame-counted sequences.

## Verification result and its limits

`make test` passed at the audited baseline: five sound tests and 30,004
emulated gameplay frames, reaching board 5. Peak work was 212/261 raster
lines. The additional probes confirmed the idle state, scene bypasses,
collectible count, fruit progression, tuning cap and level-counter wrap.

The current bot only requires acceptable frame work and at least one cleared
board (`tests/bot.py:204`). It never asserts an arcade attract loop,
intermission, ghost target or reference replay. Passing it demonstrates
useful stability/progress, not arcade fidelity. No parity percentage is
assigned because there is no agreed weighting or conformance suite.

## Recommended implementation order and acceptance checks

1. **Fix the project contract and logical model.** Adopt this exact ROM/default
   profile, preserve its maze graph and 244 collectibles, and separate fruit,
   difficulty and presentation indexing. Prototype the portrait layout before
   locking artwork dimensions.
2. **Restore the complete presentation flow.** Implement the named character
   reveals, chase/reversal sequence, maze demo, start/player selection and
   all three intermissions with music at boards 2/5/9/13/17. Capture each
   stage against a recording of the selected ROM. Check automatic looping,
   interruption by start/credit, and no accidental changes to a real game.
3. **Port the original decision rules.** Replace custom personalities;
   implement scatter/chase, reversals, distance/look-ahead rules, house
   counters, PRNG, Elroy and the full difficulty sequence. Test small
   deterministic target/turn fixtures before relying on whole-game replays.
4. **Restore the remaining game rules.** Match fruit timing/history, collisions,
   two-player turn state, settings, pauses and transition ordering. Add
   explicit fixtures for boards 1, 2, 5, 8, 9, 13, 17, 18, 19 and 21, including
   reversal without blue time on the relevant boards.
5. **Validate the audiovisual compromise.** Compare actual VICE output with
   the arcade reference, including music envelopes and event precedence.
   Record accepted color, resolution and clock-rate differences individually.
6. **Add conformance evidence.** Store reference logical-tick traces, fixed
   joystick replays, scene/event timelines and screenshot/audio comparisons.
   Keep timing/crash tests, but require these additional checks before calling
   the conversion arcade-faithful. Decide kill-screen and obscure-bug parity
   after normal gameplay and presentation are complete.

The immediate next milestone should be an arcade-correct logical maze plus a
complete presentation timeline, not another isolated sprite polish pass.
