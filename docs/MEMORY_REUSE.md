# Memory-lifetime audit and startup reuse

This pass reclaims **358 resident bytes** within the existing period-correct
NTSC VIC-20 configuration. BLK1–3 now have **371 contiguous bytes free**, up
from 13; BLK5 still has 15. The game continues to require +3K and BLK1/2/3/5
RAM. Stack reservations and display resolution are retained.

The extra space can hold rendering code, tables or CPU-side working data.
The moving-actor compositor is unchanged by this pass, so further flicker work
remains. This does not create a second VIC-visible framebuffer.

## Retained reuse

Platform setup runs exactly once. The initial 6502 entry, hardware register
setup and `video_init()` now execute in a temporary boot image at
`$0400–$07FF`, before that range becomes the arcade's logical screen RAM.
The actual boot code occupies `$0400–$0525` (294 bytes).

The loader still produces one ordinary loadable PRG. It unpacks three images:

| Destination | Contents | Lifetime |
| --- | --- | --- |
| `$A000–$BFFF` | Resident ROM tables and selected code | Whole program |
| `$2000–$7FFF` | Resident native code, tables and initializer image | Whole program |
| `$0400–$07FF` | Temporary startup code, padded to 1 KB | Until resident `main()` begins |

After depacking, the loader jumps to `boot_start` at `$0400`. That entry sets
up the CPU and copies initialized zero-page data, then calls `platform_init()`.
Once that call returns, it jumps to resident `main()` without retaining a
return address into boot RAM. Resident code clears `$0400–$0FFF` and starts
the arcade setup. The old boot bytes are then ordinary game data.

Both the ELF entry and `_start` identify the new boot entry. The linker bounds
the boot image to its 1 KB window. The packer verifies all three decompressed
images and checks that stores cannot overwrite either its loader or unread
compressed input, including the boot destination below the PRG load address.

The remaining resident `main()` is also smaller after splitting off setup.
Together with relocating the former resident entry, this recovers 358 bytes.
The packed PRG grows from 26,838 to 26,857 bytes: compressed file size and
resident memory use are separate measurements.

`video_init()` must leave `$0400–$07FF` alone while it is executing there.
Clearing logical screen RAM belongs to resident code after the handoff.
`clock_init()` remains resident because it starts the arcade timer after that
handoff and the arcade's initial setup. Arcade setup/reset routines remain
resident; their names do not imply that their data or code has a boot-only
lifetime, and their clears can overlap the temporary boot window.

## Other allocations reviewed

| Allocation | Lifetime finding | Decision |
| --- | --- | --- |
| Six sprite underlays, 216 bytes at `$0320` | Survive across refreshes while unchanged actors stay visible; overlap priority depends on them | Retain |
| Random-sequence index, two bytes at `$03F8` | Persists between frightened decisions | Retain |
| Dirty queue and rebuild/bulk state, 56 bytes at `$02C4` | Continuations survive yields while game logic, input and audio run | Retain; four bytes remain unallocated in this region |
| Dirty bits, 128 bytes at `$0F00` | Record writes awaiting conversion, including writes behind the rebuild cursor | Retain |
| Sprite cache, 98 bytes at `$0F80` | Even actor slots and the dirty-band byte persist across frames | Retain; 55 scattered spare bytes remain candidates for metadata |
| Underlay record bytes 4 and 6 | Unused in each of the six records | Twelve scattered bytes remain candidates for metadata |
| Maze coverage and flash state, 26 bytes at `$0FE2` | Persist through pellet changes, flashes and progressive drawing | Retain; four bytes remain at the end of this region |
| Physical `$0DA0–$0DFF` | Flag accesses normally map to zero page, but whole-game initialization clears this physical range | No persistent allocation added here |
| Zero-page initializer image, 26 bytes at `$2000` | Copied once, but its live zero-page destination remains in use | Leave the existing load-image arrangement for this increment |
| Bitmap `$1000–$1C3F` and virtual I/O `$1C40–$1D3F` | Live throughout rendering/gameplay | Retain |

The other six bytes at the end of the low-RAM work region remain unallocated.
These small fragments are not one contiguous buffer. Compiler-managed zero
page remains within its existing budget; this pass adds no zero-page objects.

## Stack observations

Host-only instrumentation records actual guest stores within the software
stack reservation and the 6502 stack page. Host fixture writes and canaries
are excluded. This avoids treating the loader's use of zero-page pointers as
software-stack use, or sampling partially updated 16-bit stack pointers.

The smoke workload covers boot, attract, coin/start, fruit, all three
intermissions and more than 7,000 logical ticks:

| Observation | Before | After |
| --- | ---: | ---: |
| Lowest software-stack write | `$1FD8` | `$1FE0` |
| Written footprint below `$2000` | 40 bytes | 32 bytes |
| Lowest hardware-stack write | `$01E8` | `$01E8` |
| Written footprint below `$0200` | 24 bytes | 24 bytes |

These are observed write footprints, not a proof of maximum allocation across
every path or future build. The entire `$1D40–$1FFF` software-stack reservation
and `$0100–$01FF` hardware stack remain available. The lower software-stack
canary and IRQ vector are checked after the long run, not just before it.

## Validation and performance

All **46 regression tests pass**, followed by the smoke run. Three new memory
tests execute the actual 6502 loader and compare all three output regions
before boot starts; boot with nonzero logical RAM; exercise the reuse handoff;
and check that host canaries do not contaminate stack observations.

Every simulator run of this executable guards against executing
`$0400–$07FF` after resident `main()` begins. The smoke run observes one boot
entry, successful release and no later execution of that area through 7,191
logical ticks. VICE independently boots the new loader, accepts coin/start,
records non-silent audio, displays all eight blue/white flash phases and
settles the next board. Physical hardware has not been tested.

| Completed renders/s | Before | After |
| --- | ---: | ---: |
| Normal play | 49.61 | 49.64 |
| Frightened | 53.96 | 54.00 |
| Attract chase | 43.43 | 42.91 |
| First intermission | 60.06 | 60.15 |
| Board-transition sample | 40.82 | 40.89 |

This is a space improvement, with similar average frame rates. It does not
establish faster or steadier display updates. For example, the longest sampled
normal-play draw interval increases from 37.84 to 45.50 ms, while the coherent
transition gap remains about 1.94 seconds. The original 16,875-cycle game
clock is retained. Full results, hashes and stack observations are frozen in
[the measurement record](baselines/memory-reuse.json).

```sh
make test
python3 tests/memory.py
python3 tests/smoke.py --output build/memory-audit/current
python3 tests/performance.py --output build/memory-audit/current-performance
python3 tools/arcade/vice_check.py --maze-flash --output build/memory-audit/vice
```

Large artifacts are kept under ignored `build/memory-audit/`. The reclaimed
resident space is available for the next measured compositor or blitter
improvement; no unused rendering buffer has been allocated merely to reserve it.
