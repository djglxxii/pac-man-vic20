# Live multicolour integration

The approved blue maze, white pellets, custom actors and hires score digits
now run with the actual arcade game. This executable has live joystick and
keyboard input, ghost AI, collisions, pellet removal, scores, lives and sound.
It does not replay recorded actor positions.

This is an **integration build**, available alongside the accepted game:

```sh
make run-multicolour
```

Use arrows for movement, `5` for a coin and `1`/`2` to start. Joystick fire
also supplies coin/start through the existing controls. The executable is
`build/pacman-multicolour.prg`. `make run` still launches the accepted hires
game, which remains byte-identical.

[Watch current gameplay with sound](../build/multicolour-game/vice/playable-preview.mp4).
The computer in this recording uses joystick input only; it does not patch
positions, pellets, lives, levels or code.

## Current limits

**The complete game remains much slower than the isolated renderer demo.**
The current 600-frame VICE recording completes 89 actor publications, about
**8.96 updates/s**, versus 5.03 in the first integration. It still looks choppy
and is not ready to replace the accepted build. The VIA timer remains
16,875 CPU cycles, approximately 60.606 Hz, and logical tick comparisons still
match the arcade. Presentation throughput is insufficient to replace the
accepted build.

Full background construction is progressive and slow. Ordinary background
changes can remain queued while actors continue updating. The recording starts
after full maze construction; it does not demonstrate fast board loading.

Normal ghosts, returning eyes, Pac-Man's directions/mouth phases, blue and
white frightened frames, and the first cherry are connected. **Death poses,
other fruit, point popups and special intermission actors still use fallback
artwork.** Their game-state machines and sound continue running. Attract text
uses reduced versions of the existing tile masks; its visual treatment and
the complete two-player HUD still need review.

Further standalone micro-optimizations are on hold. The next feature work is
the remaining animation/state coverage and UI. Before switching the default
game, the measured CPU-budget gap must also be resolved in this actual game
workload. The earlier replay's 19.019 ms renderer figure excludes game logic,
input, sound and dynamic backgrounds and uses a different graphics-table layout.

## Integration

The native build links the existing arcade core, input code, timer, bounded
bulk tasks and sound driver to a new live display adapter. Arcade coordinates,
movement masks, ghost decisions, collision order, random sequence and score
calculations remain unchanged. The adapter consumes the stable output buffers
already produced by the original ISR.

The NTSC horizontal origin is now `$9000 = 6`, replacing 12. The KERNAL's
22-column layout starts at 5; our 21 columns start four dots later to retain
that centre. Vertical placement remains `$9001 = 18`. The VICE recorder reads
the live origin when cropping and also saves an uncropped monitor image.

Logical tile writes mark the hardware characters they affect. A permanent
glyph cache builds blue walls and white pellets from the approved 3×6 tiles.
Changing a pellet beneath an actor updates that actor's background reference;
the next preparation copies the updated background into its hidden work glyph.
Vacated cells restore the current background, rather than an earlier pellet.
The background builder combines two complete three-pixel tile rows per
scanline instead of resolving four individual pixels. A full scene replacement
releases the previous scene's glyph references and rebuilds the HUD. It finishes
queued background writes before publishing actors, avoiding cache exhaustion
from retaining both transitional scenes and the HUD.

The screen and per-work-character underlays together identify each cell's
background. This avoids a second 567-byte background map. Reference counts
protect all displayed background glyphs from eviction. Their high portions
use two owner bytes: with 567 cells, at most two complete groups of 256
references exist. An eight-byte pattern comparison confirms cache matches
after a small hash check.

Two 54-character actor banks retain hidden preparation and publication.
Forty-eight unique artwork rows have four precomputed horizontal phases,
giving 192 indexed records shared by all 29 poses. Two data columns and packed
third-column/colour IDs occupy 480 bytes reclaimed from the old stack
reservation. Masks and eleven small tail records complete the dictionary.
Actors no longer shift or expand their artwork during rendering.

Preparation has begin/step entry points. Each step completes one actor; the
live scheduler handles at most two per batch, servicing input, logic and audio
between batches. The actor packet and displayed background remain stable
until publication. Full scene invalidation aborts hidden work before rebuilding.
The synchronous entry remains available for exact compositor tests.

The same 480 recorded packets take an average of **24,684 preparation cycles**,
down from 43,164; every packet improves. These isolated calls measure rendering
only. A separate 600-frame native run using the same joystick bot and duration
as the saved first integration measures **8.74 updates/s**, versus 5.02, and
reduces the maximum audio-service gap from **102.17 to 31.37 ms**. The live
workloads start at their respective first playable pictures; faster board
construction changes their starting game state. These are representative
samples, not guaranteed minimum frame rates.

HUD scores read digits already formatted by the core, including its leading
blanks. They use the accepted 5×7 font in hires cells. The audio driver keeps
`$900E`'s upper nibble at white while updating the existing volume value.
Completion flashing changes the global wall source between blue and white;
the next full rebuild restores blue.

## Memory

The target remains the existing conventional +3K and BLK1/2/3/5 expansion.
No additional memory hardware or bank-switching facility is introduced.

| Region | Live use |
| --- | --- |
| `$1000–$17FF` | 256 VIC glyphs: 147 background slots, two 54-slot actor banks, one spare |
| `$1800–$1A36` | 21×27 screen matrix |
| `$1A37–$1C3E` | 520 bytes of renderer metadata, hashes, reference-overflow owners and scheduling state |
| `$1CC0–$1D2B` | 108 actor background references |
| `$0200–$02B4` | 181 bytes of font/artwork tables, copied from the temporary boot image |
| `$02C4–$02D4` | 17 bytes of bulk/background state |
| `$0320–$03FE` | 223 bytes of reference counts, HUD cache, scratch and RNG state |
| `$0F00–$0FC6` | 199 bytes of dirty bits |
| `$1D40–$1F1F` | 480 bytes of pre-shifted row data and packed tail IDs |
| `$1F20–$1FFF` | 224-byte software stack reservation |
| `$2000–$2236` | 567-byte working-cell map |

The default renderer's unused virtual-I/O padding supplies the new underlays.
Live virtual output accesses occupy `$1C40–$1CBF`; the largest sound clear ends
at `$1CC0`. The full 256-byte I/O clear runs only at boot, before underlay
initialization. `$1D2C–$1D3F` remains unused. The software stack previously
reserved 704 bytes; the revised 224-byte reservation exceeds the long smoke
run's **38-byte maximum actual use** by 186 bytes. Tests guard its lower end
and verify the adjacent graphics tables throughout all seven smoke scenes.

The boot region now reserves `$0400–$0BFF` for initializer code and table load
images, including zero-page initializers. All are released to logical video
RAM after handoff to resident code. The PRG packer reads the boot-region limit
from the linker symbols; the default game's original pack remains identical.
Linker checks protect pointer-page assumptions, region limits and the boot
initializer range. BLK1–3 retain 59 free bytes and BLK5 retains 47. Further
artwork still needs a memory-placement check.

## Verification

The accepted build's **48 regression tests** pass and its PRG hash is unchanged.
The live target passes six arcade-parity/memory/audio tests, including the
existing movement, frightened RNG and exact sound conversion cases. All 160
sound-register cases preserve the white auxiliary nibble.

Additional native checks cover **2,415 compositor scenes**, **5,112 actor
packets**, 36 pellet/power-pellet removals and palette recovery. They verify
hidden preparation, every pose/shift, edge and HUD clipping, overlap, all 54
work cells, allocation failure/recovery in three columns, cache ownership,
hashes and guard bytes. Twenty-nine scenes also run as six individual actor
steps, and aborts after every possible actor prefix clear the working map.
The scene/packet totals include optional frozen samples
from the earlier prototype; generated cases also run without that sample.

The long smoke run passes all three intermission state machines through
**7,205 logical ticks**, retaining the IRQ vector and stack guard. Cache
ownership and capacity checks also pass in all seven saved smoke scenes.
These are state and memory checks; special intermission artwork is still pending.

VICE checks 32 consecutive live scenes, 96 hidden actor batches spanning real
game ticks, and 98 vacated-cell restorations.
All **36,288 native picture pixels** match the independent compositor oracle.
A separate, unpatched VICE process captures 600 frames of actual play with
audible audio, increasing pellets eaten from 1 to 70 and score from 10 to
740. Every video frame and the audio stream decode successfully. Physical
hardware has not been tested.

```sh
make test-multicolour
python3 tools/arcade/record_multicolour_game.py --frames 600
python3 tests/multicolour_timing.py
```

Hashes, memory figures, checks, capture metadata and the limitations above are
frozen in [the playability record](baselines/multicolour-playability.json).
The [first integration record](baselines/multicolour-game.json) is historical.
