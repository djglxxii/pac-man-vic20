# Pac-Man, NTSC VIC-20 with 3K + BLK1/2/3/5 RAM expansion.
PY := python3
CC65BIN ?= $(CURDIR)/tools/cc65/usr/bin
CA65 := $(if $(wildcard $(CC65BIN)/ca65),$(CC65BIN)/ca65,ca65)
LD65 := $(if $(wildcard $(CC65BIN)/ld65),$(CC65BIN)/ld65,ld65)
MOSROOT ?= $(CURDIR)/tools/llvm-mos
MOSCC := $(MOSROOT)/bin/mos-sim-clang
MOSNM := $(MOSROOT)/bin/llvm-nm
GEN := build/arcade
PRG := build/pacman.prg
CORE := src/arcade/core.c
NATIVE := src/start.S src/clock.S src/bitmap.S src/rebuild.S src/tasks.S src/sprites.S src/audio.S src/pacman.c src/platform.c src/video.c $(CORE) src/score.S
MULTI := build/multicolour-game
MULTI_NATIVE := src/start.S src/clock.S src/tasks.S src/audio.S src/pacman.c src/platform.c src/multicolour.S src/multicolour.c $(CORE)
# $A0-$FF holds arcade flags. Of the remaining 126 zero-page bytes, assembly
# reserves 34; the compiler may allocate at most 92 more.
CFLAGS := -Oz -gline-tables-only -mlto-zp=92 -nostartfiles -DVIC20 -Wno-everything -Isrc/arcade -I$(GEN) -Tsrc/pacman.ld

all: $(PRG)

$(GEN)/rom.stamp: tools/arcade/mkrom.py tools/arcade/hires_font.py tools/arcade/hires_pacman.py tools/arcade/hires_intermission.py docs/artwork/hires-font.json docs/artwork/hires-pacman.json docs/artwork/hires-intermission.json pacman.zip
	$(PY) tools/arcade/mkrom.py --output $(GEN)
	@touch $@

$(MOSCC): tools/bootstrap-llvm-mos.py
	$(PY) tools/bootstrap-llvm-mos.py --output $(MOSROOT)

$(GEN)/pacman-native.bin: build/pool-ghost-row-fast/pacman-native.bin Makefile
	cp $< $@
	cp $<.elf $@.elf
	cp build/pool-ghost-row-fast/pacman.map $(GEN)/pacman.map

$(PRG): build/pool-ghost-row-fast/pacman.prg $(GEN)/pacman-native.bin Makefile
	cp $< $@
	cp build/pool-ghost-row-fast/pacman.lbl build/pacman.lbl

# Keep the former underlay renderer reproducible for historical comparisons.
build/legacy/pacman-native.bin: $(NATIVE) $(wildcard src/arcade/*.h) src/video.h src/colour_target.h src/pacman.ld $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(CFLAGS) $(NATIVE) $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/legacy/pacman.prg: build/legacy/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

legacy: build/legacy/pacman.prg

run-legacy: legacy
	xvic $(VICEFLAGS) -autostart build/legacy/pacman.prg

$(MULTI)/assets.stamp: tools/arcade/build_multicolour_assets.py tools/arcade/build_multicolour_motion.py tools/arcade/multicolour_mockup.py docs/artwork/multicolour/actors-and-font.json docs/artwork/maze-wall-tiles.json $(GEN)/rom.stamp
	$(PY) tools/arcade/build_multicolour_assets.py
	@touch $@

$(MULTI)/pacman-native.bin: $(MULTI_NATIVE) $(wildcard src/arcade/*.h) src/video.h src/multicolour.ld $(MULTI)/assets.stamp $(MOSCC)
	$(MOSCC) $(filter-out -mlto-zp=92 -Tsrc/pacman.ld,$(CFLAGS)) -mlto-zp=88 -DMULTICOLOUR -I$(MULTI) -Tsrc/multicolour.ld $(MULTI_NATIVE) $(GEN)/rom.c $(MULTI)/assets.c -Wl,-Map,$(MULTI)/pacman.map -o $@

build/pacman-multicolour.prg: $(MULTI)/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

multicolour: build/pacman-multicolour.prg

build/beam-follow/pacman-native.bin: $(NATIVE) src/beam_follow.S src/beam_follow.ld src/pacman.ld $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p build/beam-follow
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DBEAM_FOLLOW -Tsrc/beam_follow.ld $(NATIVE) src/beam_follow.S $(GEN)/rom.c -Wl,-Map,build/beam-follow/pacman.map -o $@

build/pacman-beam.prg: build/beam-follow/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

beam: build/pacman-beam.prg

run-beam: build/pacman-beam.prg
	xvic $(VICEFLAGS) -autostart $<

test-beam: beam tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/beam.py
	$(PY) tests/smoke.py --prg build/pacman-beam.prg --output build/beam-follow/smoke

# Fresh raster trials using current artwork; preserve the archived beam build.
BEAM_REVIEW_FLAGS = $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DBEAM_FOLLOW -DBEAM_REVIEW -Tsrc/beam_priority.ld

build/beam-priority/%/pacman-native.bin: $(NATIVE) src/beam_follow.S src/beam_priority.ld src/pacman.ld $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(BEAM_REVIEW_FLAGS) $(if $(filter focused strict,$*),-DBEAM_PRIORITY,) $(if $(filter strict,$*),-DBEAM_PRIORITY_WAIT,) $(NATIVE) src/beam_follow.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/beam-priority/%/pacman.prg: build/beam-priority/%/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

.PRECIOUS: build/beam-priority/%/pacman-native.bin

beam-priority: build/beam-priority/strict/pacman.prg

beam-review: build/beam-priority/reference/pacman.prg

beam-opportunistic: build/beam-priority/focused/pacman.prg

run-beam-priority: beam-priority
	xvic $(VICEFLAGS) -autostart build/beam-priority/strict/pacman.prg

run-beam-review: beam-review
	xvic $(VICEFLAGS) -autostart build/beam-priority/reference/pacman.prg

run-beam-opportunistic: beam-opportunistic
	xvic $(VICEFLAGS) -autostart build/beam-priority/focused/pacman.prg

test-beam-priority: beam-priority tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/beam_priority.py --prg build/beam-priority/strict/pacman.prg
	$(PY) tests/smoke.py --prg build/beam-priority/strict/pacman.prg --output build/beam-priority/strict/smoke

build/ghost-shadow/pacman-native.bin: $(NATIVE) src/ghost_shadow.S src/ghost_shadow.ld src/pacman.ld $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p build/ghost-shadow
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGHOST_SHADOW -Tsrc/ghost_shadow.ld $(NATIVE) src/ghost_shadow.S $(GEN)/rom.c -Wl,-Map,build/ghost-shadow/pacman.map -o $@

build/pacman-shadow.prg: build/ghost-shadow/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

ghost-shadow: build/pacman-shadow.prg

build/actor-commit/after/pacman-native.bin: $(NATIVE) $(wildcard src/arcade/*.h) src/video.h src/pacman.ld $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p build/actor-commit/after
	$(MOSCC) $(filter-out -mlto-zp=92,$(CFLAGS)) -mlto-zp=90 -DACTOR_COMMIT $(NATIVE) $(GEN)/rom.c -Wl,-Map,build/actor-commit/after/pacman.map -o $@

build/actor-commit/after/pacman.prg: build/actor-commit/after/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

actor-commit: build/actor-commit/after/pacman.prg

# Current artwork, with dependency code loaded into unused lower stack RAM.
# Keep the archived actor-commit pair intact for the matched-cadence study.
ACTOR_SPEED_FLAGS = $(filter-out -mlto-zp=92 -Tsrc/pacman.ld,$(CFLAGS)) -mlto-zp=90 -DACTOR_COMMIT -DACTOR_COMMIT_OVERLAY -Tsrc/actor_commit.ld

build/actor-speed/%/pacman-native.bin: $(NATIVE) src/actor_commit.ld src/pacman.ld $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(ACTOR_SPEED_FLAGS) $(if $(filter fast,$*),-DACTOR_COMMIT_FAST,) $(NATIVE) $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/actor-speed/%/pacman.prg: build/actor-speed/%/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

.PRECIOUS: build/actor-speed/%/pacman-native.bin

actor-speed: build/actor-speed/fast/pacman.prg

actor-speed-reference: build/actor-speed/reference/pacman.prg

# General background-fallback colour rule; accepted build remains unchanged.
build/stable-colours/pacman-native.bin: $(NATIVE) src/stable_colours.S src/stable_colours.ld src/colour_target.h src/pacman.ld $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DSTABLE_COLOURS -Tsrc/stable_colours.ld $(NATIVE) src/stable_colours.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/stable-colours/pacman.prg: build/stable-colours/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

stable-colours: build/stable-colours/pacman.prg

# Original accepted glyph pool, preserved before the five speed improvements.
POOL_NATIVE := $(filter-out src/sprites.S,$(NATIVE)) src/glyph_pool.S src/glyph_pool.c
build/glyph-pool/pacman-native.bin: $(POOL_NATIVE) src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -Tsrc/glyph_pool.ld $(POOL_NATIVE) $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/glyph-pool/pacman.prg: build/glyph-pool/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

glyph-pool: build/glyph-pool/pacman.prg

# Intermediate allocation/address build, preserved for comparisons.
build/pool-address/pacman-native.bin: $(POOL_NATIVE) src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -Tsrc/glyph_pool.ld $(POOL_NATIVE) $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-address/pacman.prg: build/pool-address/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-address: build/pool-address/pacman.prg

run-pool-address: pool-address
	xvic $(VICEFLAGS) -autostart build/pool-address/pacman.prg

test-pool-address: pool-address tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-address/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-address/pacman.prg --output build/pool-address/smoke

.PHONY: pool-address run-pool-address test-pool-address

# Skip empty generic-sprite source rows on top of the address trial.
build/pool-skip-empty/pacman-native.bin: $(POOL_NATIVE) src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -Tsrc/glyph_pool.ld $(POOL_NATIVE) $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-skip-empty/pacman.prg: build/pool-skip-empty/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-skip-empty: build/pool-skip-empty/pacman.prg

run-pool-skip-empty: pool-skip-empty
	xvic $(VICEFLAGS) -autostart build/pool-skip-empty/pacman.prg

test-pool-skip-empty: pool-skip-empty tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-skip-empty/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-skip-empty/pacman.prg --output build/pool-skip-empty/smoke

.PHONY: pool-skip-empty run-pool-skip-empty test-pool-skip-empty

# Intermediate sound-effect build, preserved for comparisons.
build/sound-effect-fast/pacman-native.bin: $(POOL_NATIVE) src/sound_effect.S src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/sound-effect-fast/pacman.prg: build/sound-effect-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

sound-effect-fast: build/sound-effect-fast/pacman.prg

run-sound-effect-fast: sound-effect-fast
	xvic $(VICEFLAGS) -autostart build/sound-effect-fast/pacman.prg

test-sound-effect-fast: sound-effect-fast pool-skip-empty tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/sound-effect-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/sound_effect.py
	$(PY) tools/arcade/check_audio_replay.py
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/sound-effect-fast/pacman.prg --output build/sound-effect-fast/smoke

.PHONY: sound-effect-fast run-sound-effect-fast test-sound-effect-fast

# Intermediate ghost tunnel-lookup build, preserved for comparisons.
build/tile-address-fast/pacman-native.bin: $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/tile-address-fast/pacman.prg: build/tile-address-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

tile-address-fast: build/tile-address-fast/pacman.prg

run-tile-address-fast: tile-address-fast
	xvic $(VICEFLAGS) -autostart build/tile-address-fast/pacman.prg

test-tile-address-fast: tile-address-fast sound-effect-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/tile-address-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/tile_address.py
	$(PY) tools/arcade/check_audio_replay.py --baseline build/sound-effect-fast/pacman.prg --trial build/tile-address-fast/pacman.prg --output build/tile-address-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/tile-address-fast/pacman.prg --output build/tile-address-fast/smoke

.PHONY: tile-address-fast run-tile-address-fast test-tile-address-fast

# Intermediate composition build, preserved for comparisons.
build/pool-stamp-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-stamp-fast/pacman.prg: build/pool-stamp-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-stamp-fast: build/pool-stamp-fast/pacman.prg

run-pool-stamp-fast: pool-stamp-fast
	xvic $(VICEFLAGS) -autostart build/pool-stamp-fast/pacman.prg

test-pool-stamp-fast: pool-stamp-fast tile-address-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-stamp-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/tile_address.py --prg build/pool-stamp-fast/pacman.prg --output build/pool-stamp-fast/evaluation/tile-kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/tile-address-fast/pacman.prg --trial build/pool-stamp-fast/pacman.prg --output build/pool-stamp-fast/evaluation/stamp-kernel.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/tile-address-fast/pacman.prg --trial build/pool-stamp-fast/pacman.prg --output build/pool-stamp-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-stamp-fast/pacman.prg --output build/pool-stamp-fast/smoke

.PHONY: pool-stamp-fast run-pool-stamp-fast test-pool-stamp-fast

# Intermediate pitch-lookup build, preserved for comparisons.
build/audio-divider-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/audio-divider-fast/pacman.prg: build/audio-divider-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

audio-divider-fast: build/audio-divider-fast/pacman.prg

run-audio-divider-fast: audio-divider-fast
	xvic $(VICEFLAGS) -autostart build/audio-divider-fast/pacman.prg

test-audio-divider-fast: audio-divider-fast pool-stamp-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/audio-divider-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/audio_divider.py
	$(PY) tools/arcade/check_audio_replay.py --baseline build/pool-stamp-fast/pacman.prg --trial build/audio-divider-fast/pacman.prg --output build/audio-divider-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/audio-divider-fast/pacman.prg --output build/audio-divider-fast/smoke

.PHONY: audio-divider-fast run-audio-divider-fast test-audio-divider-fast

# Intermediate audio-adapter build, preserved for comparisons.
build/audio-update-fast/pacman-native.bin: $(POOL_NATIVE) src/audio_update.S src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/audio-update-fast/pacman.prg: build/audio-update-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

audio-update-fast: build/audio-update-fast/pacman.prg

run-audio-update-fast: audio-update-fast
	xvic $(VICEFLAGS) -autostart build/audio-update-fast/pacman.prg

test-audio-update-fast: audio-update-fast audio-divider-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/audio-update-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/audio_update.py
	$(PY) tools/arcade/check_audio_replay.py --baseline build/audio-divider-fast/pacman.prg --trial build/audio-update-fast/pacman.prg --output build/audio-update-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/audio-update-fast/pacman.prg --output build/audio-update-fast/smoke

.PHONY: audio-update-fast run-audio-update-fast test-audio-update-fast

# Intermediate ghost-state build, preserved for comparisons.
build/ghost-update-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/ghost-update-fast/pacman.prg: build/ghost-update-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

ghost-update-fast: build/ghost-update-fast/pacman.prg

run-ghost-update-fast: ghost-update-fast
	xvic $(VICEFLAGS) -autostart build/ghost-update-fast/pacman.prg

test-ghost-update-fast: ghost-update-fast audio-update-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/ghost-update-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/ghost_update.py
	$(PY) tools/arcade/check_audio_replay.py --baseline build/audio-update-fast/pacman.prg --trial build/ghost-update-fast/pacman.prg --output build/ghost-update-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/ghost-update-fast/pacman.prg --output build/ghost-update-fast/smoke

.PHONY: ghost-update-fast run-ghost-update-fast test-ghost-update-fast

# Accepted intermediate build: cheaper fresh-cell bookkeeping.
build/pool-alloc-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -DPOOL_ALLOC_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-alloc-fast/pacman.prg: build/pool-alloc-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-alloc-fast: build/pool-alloc-fast/pacman.prg

run-pool-alloc-fast: pool-alloc-fast
	xvic $(VICEFLAGS) -autostart build/pool-alloc-fast/pacman.prg

test-pool-alloc-fast: pool-alloc-fast ghost-update-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-alloc-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tools/arcade/pool_address_timing.py --baseline build/ghost-update-fast/pacman.prg --trial build/pool-alloc-fast/pacman.prg --output build/pool-alloc-fast/evaluation/allocator-kernel.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/ghost-update-fast/pacman.prg --trial build/pool-alloc-fast/pacman.prg --output build/pool-alloc-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-alloc-fast/pacman.prg --output build/pool-alloc-fast/smoke

.PHONY: pool-alloc-fast run-pool-alloc-fast test-pool-alloc-fast

# Intermediate background-tile build, preserved for comparisons.
build/tile-stamp-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -DPOOL_ALLOC_FAST -DTILE_STAMP_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/tile-stamp-fast/pacman.prg: build/tile-stamp-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

tile-stamp-fast: build/tile-stamp-fast/pacman.prg

run-tile-stamp-fast: tile-stamp-fast
	xvic $(VICEFLAGS) -autostart build/tile-stamp-fast/pacman.prg

test-tile-stamp-fast: tile-stamp-fast pool-alloc-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/tile-stamp-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tools/arcade/tile_stamp_timing.py --baseline build/pool-alloc-fast/pacman.prg --trial build/tile-stamp-fast/pacman.prg --output build/tile-stamp-fast/evaluation/kernel.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/pool-alloc-fast/pacman.prg --trial build/tile-stamp-fast/pacman.prg --output build/tile-stamp-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/tile-stamp-fast/pacman.prg --output build/tile-stamp-fast/smoke

.PHONY: tile-stamp-fast run-tile-stamp-fast test-tile-stamp-fast

# Intermediate sprite-preparation build, preserved for comparisons.
$(GEN)/sprite_setup.inc: $(GEN)/rom.stamp
	@test -f $@ || $(PY) tools/arcade/mkrom.py --output $(GEN)
	@touch $@

build/pool-setup-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/pool_setup.ld src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(GEN)/sprite_setup.inc $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -DPOOL_ALLOC_FAST -DTILE_STAMP_FAST -DPOOL_SETUP_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld -Tsrc/pool_setup.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-setup-fast/pacman.prg: build/pool-setup-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-setup-fast: build/pool-setup-fast/pacman.prg

run-pool-setup-fast: pool-setup-fast
	xvic $(VICEFLAGS) -autostart build/pool-setup-fast/pacman.prg

test-pool-setup-fast: pool-setup-fast tile-stamp-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-setup-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/tile-stamp-fast/pacman.prg --trial build/pool-setup-fast/pacman.prg --output build/pool-setup-fast/evaluation/kernel.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/tile-stamp-fast/pacman.prg --trial build/pool-setup-fast/pacman.prg --output build/pool-setup-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-setup-fast/pacman.prg --output build/pool-setup-fast/smoke

.PHONY: pool-setup-fast run-pool-setup-fast test-pool-setup-fast

# Intermediate destination-setup build, preserved for comparisons.
build/pool-dest-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/pool_setup.ld src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(GEN)/sprite_setup.inc $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -DPOOL_ALLOC_FAST -DTILE_STAMP_FAST -DPOOL_SETUP_FAST -DPOOL_DEST_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld -Tsrc/pool_setup.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-dest-fast/pacman.prg: build/pool-dest-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-dest-fast: build/pool-dest-fast/pacman.prg

run-pool-dest-fast: pool-dest-fast
	xvic $(VICEFLAGS) -autostart build/pool-dest-fast/pacman.prg

test-pool-dest-fast: pool-dest-fast pool-setup-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-dest-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/pool-setup-fast/pacman.prg --trial build/pool-dest-fast/pacman.prg --output build/pool-dest-fast/evaluation/kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/pool-setup-fast/pacman.prg --trial build/pool-dest-fast/pacman.prg --poison-unused-bottom --output build/pool-dest-fast/evaluation/stamp-guards.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/pool-setup-fast/pacman.prg --trial build/pool-dest-fast/pacman.prg --output build/pool-dest-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-dest-fast/pacman.prg --output build/pool-dest-fast/smoke

.PHONY: pool-dest-fast run-pool-dest-fast test-pool-dest-fast

# Intermediate accumulator-shift build, preserved for comparisons.
build/pool-shift-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/pool_setup.ld src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(GEN)/sprite_setup.inc $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -DPOOL_ALLOC_FAST -DTILE_STAMP_FAST -DPOOL_SETUP_FAST -DPOOL_DEST_FAST -DPOOL_SHIFT_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld -Tsrc/pool_setup.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-shift-fast/pacman.prg: build/pool-shift-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-shift-fast: build/pool-shift-fast/pacman.prg

run-pool-shift-fast: pool-shift-fast
	xvic $(VICEFLAGS) -autostart build/pool-shift-fast/pacman.prg

test-pool-shift-fast: pool-shift-fast pool-dest-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-shift-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/pool-dest-fast/pacman.prg --trial build/pool-shift-fast/pacman.prg --output build/pool-shift-fast/evaluation/kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/pool-dest-fast/pacman.prg --trial build/pool-shift-fast/pacman.prg --poison-unused-bottom --output build/pool-shift-fast/evaluation/stamp-guards.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/pool-dest-fast/pacman.prg --trial build/pool-shift-fast/pacman.prg --output build/pool-shift-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-shift-fast/pacman.prg --output build/pool-shift-fast/smoke

.PHONY: pool-shift-fast run-pool-shift-fast test-pool-shift-fast

# Standard build: use the normal-ghost source index as its row counter.
build/pool-ghost-row-fast/pacman-native.bin: $(POOL_NATIVE) src/pool_stamp_fast.inc src/sound_effect.S src/tile_address.S src/audio_update.S src/pool_setup.ld src/tile_address.ld src/glyph_pool.ld src/colour_target.h $(wildcard src/arcade/*.h) src/video.h $(GEN)/rom.stamp $(GEN)/sprite_setup.inc $(MOSCC)
	@mkdir -p $(@D)
	$(MOSCC) $(filter-out -Tsrc/pacman.ld,$(CFLAGS)) -DGLYPH_POOL -DPOOL_ADDRESS_FAST -DPOOL_SKIP_EMPTY -DSOUND_EFFECT_FAST -DTILE_ADDRESS_FAST -DPOOL_STAMP_FAST -DAUDIO_DIVIDER_FAST -DAUDIO_UPDATE_FAST -DGHOST_UPDATE_FAST -DPOOL_ALLOC_FAST -DTILE_STAMP_FAST -DPOOL_SETUP_FAST -DPOOL_DEST_FAST -DPOOL_SHIFT_FAST -DPOOL_GHOST_ROW_FAST -Tsrc/tile_address.ld -Tsrc/glyph_pool.ld -Tsrc/pool_setup.ld $(POOL_NATIVE) src/sound_effect.S src/tile_address.S src/audio_update.S $(GEN)/rom.c -Wl,-Map,$(@D)/pacman.map -o $@

build/pool-ghost-row-fast/pacman.prg: build/pool-ghost-row-fast/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

pool-ghost-row-fast: build/pool-ghost-row-fast/pacman.prg

run-pool-ghost-row-fast: pool-ghost-row-fast
	xvic $(VICEFLAGS) -autostart build/pool-ghost-row-fast/pacman.prg

test-pool-ghost-row-fast: pool-ghost-row-fast pool-shift-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/pool-ghost-row-fast/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/pool-shift-fast/pacman.prg --trial build/pool-ghost-row-fast/pacman.prg --output build/pool-ghost-row-fast/evaluation/kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/pool-shift-fast/pacman.prg --trial build/pool-ghost-row-fast/pacman.prg --poison-unused-bottom --output build/pool-ghost-row-fast/evaluation/stamp-guards.json
	$(PY) tools/arcade/pool_ghost_timing.py --baseline build/pool-shift-fast/pacman.prg --trial build/pool-ghost-row-fast/pacman.prg --output build/pool-ghost-row-fast/evaluation/ghost-kernel.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/pool-shift-fast/pacman.prg --trial build/pool-ghost-row-fast/pacman.prg --output build/pool-ghost-row-fast/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/pool-ghost-row-fast/pacman.prg --output build/pool-ghost-row-fast/smoke

.PHONY: pool-ghost-row-fast run-pool-ghost-row-fast test-pool-ghost-row-fast

run-glyph-pool: glyph-pool
	xvic $(VICEFLAGS) -autostart build/glyph-pool/pacman.prg

test-glyph-pool: glyph-pool tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/glyph-pool/pacman.prg $(PY) tests/glyph_pool.py
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py --prg build/glyph-pool/pacman.prg --output build/glyph-pool/smoke

.PHONY: glyph-pool run-glyph-pool test-glyph-pool

run-stable-colours: stable-colours
	xvic $(VICEFLAGS) -autostart build/stable-colours/pacman.prg

test-stable-colours: stable-colours tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/stable_colours.py
	$(PY) tests/smoke.py --prg build/stable-colours/pacman.prg --output build/stable-colours/smoke

run-actor-speed: actor-speed
	xvic $(VICEFLAGS) -autostart build/actor-speed/fast/pacman.prg

test-actor-speed: actor-speed tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/actor_commit.py --prg build/actor-speed/fast/pacman.prg
	$(PY) tests/smoke.py --prg build/actor-speed/fast/pacman.prg --output build/actor-speed/fast/smoke

run-actor-commit: actor-commit
	xvic $(VICEFLAGS) -autostart build/actor-commit/after/pacman.prg

test-actor-commit: actor-commit tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/actor_commit.py
	$(PY) tests/smoke.py --prg build/actor-commit/after/pacman.prg --output build/actor-commit/smoke

run-shadow: build/pacman-shadow.prg
	xvic $(VICEFLAGS) -autostart $<

test-shadow: ghost-shadow tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/shadow.py
	$(PY) tests/smoke.py --prg build/pacman-shadow.prg --output build/ghost-shadow/smoke

run-multicolour: build/pacman-multicolour.prg
	xvic $(VICEFLAGS) -autostart $<

test-multicolour: multicolour tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/multicolour.py
	$(PY) tests/smoke.py --prg build/pacman-multicolour.prg --output $(MULTI)/smoke
	$(PY) tests/multicolour_timing.py

tools/vicsim/vicsim: tools/vicsim/vicsim.c
	$(CC) -O2 -Wall -Wno-unused-variable -Wno-misleading-indentation -o $@ $<

$(GEN)/oracle: tools/arcade/oracle.c tools/arcade/z80.h
	@mkdir -p $(GEN)
	$(CC) -O2 -o $@ $<

$(GEN)/native: $(CORE) tools/arcade/native.c $(wildcard src/arcade/*.h) src/video.h
	@mkdir -p $(GEN)
	$(CC) -O2 -fcommon -Wno-incompatible-pointer-types -Wno-pointer-sign -Isrc/arcade $(CORE) tools/arcade/native.c -o $@

reference: $(GEN)/rom.stamp $(GEN)/oracle $(GEN)/native

test: $(PRG) pool-shift-fast pool-dest-fast pool-setup-fast pool-skip-empty sound-effect-fast tile-address-fast pool-stamp-fast audio-divider-fast audio-update-fast ghost-update-fast pool-alloc-fast tile-stamp-fast tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/glyph_pool.py
	$(PY) tests/sound_effect.py
	$(PY) tests/audio_divider.py --trial $(PRG) --output build/evaluation/divider-kernel.json
	$(PY) tests/audio_update.py --trial $(PRG) --output build/evaluation/update-kernel.json
	$(PY) tests/ghost_update.py --trial $(PRG) --output build/evaluation/ghost-kernel.json
	$(PY) tools/arcade/pool_address_timing.py --baseline build/ghost-update-fast/pacman.prg --trial $(PRG) --output build/evaluation/allocator-kernel.json
	$(PY) tools/arcade/tile_stamp_timing.py --baseline build/pool-alloc-fast/pacman.prg --trial $(PRG) --output build/evaluation/tile-stamp-kernel.json
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/tile-stamp-fast/pacman.prg --trial $(PRG) --output build/evaluation/pool-setup-kernel.json
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/pool-setup-fast/pacman.prg --trial $(PRG) --output build/evaluation/pool-dest-kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/pool-setup-fast/pacman.prg --trial $(PRG) --poison-unused-bottom --output build/evaluation/pool-dest-guards.json
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/pool-dest-fast/pacman.prg --trial $(PRG) --output build/evaluation/pool-shift-kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/pool-dest-fast/pacman.prg --trial $(PRG) --poison-unused-bottom --output build/evaluation/pool-shift-guards.json
	$(PY) tools/arcade/pool_setup_timing.py --baseline build/pool-shift-fast/pacman.prg --trial $(PRG) --output build/evaluation/pool-ghost-row-scenes.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/pool-shift-fast/pacman.prg --trial $(PRG) --poison-unused-bottom --output build/evaluation/pool-ghost-row-generic.json
	$(PY) tools/arcade/pool_ghost_timing.py --baseline build/pool-shift-fast/pacman.prg --trial $(PRG) --output build/evaluation/pool-ghost-row-kernel.json
	$(PY) tests/tile_address.py --prg $(PRG) --output build/evaluation/tile-kernel.json
	$(PY) tools/arcade/pool_stamp_timing.py --baseline build/tile-address-fast/pacman.prg --trial $(PRG) --output build/evaluation/stamp-kernel.json
	$(PY) tools/arcade/check_audio_replay.py --baseline build/tile-stamp-fast/pacman.prg --trial $(PRG) --output build/evaluation/audio-replay
	$(PY) tests/display_profile.py
	$(PY) tests/smoke.py

test-legacy: legacy tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/native.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/ghosts.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/memory.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/render.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/fonts.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/colors.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/flash.py
	PACMAN_PRG=build/legacy/pacman.prg $(PY) tests/rebuild.py
	$(PY) tests/smoke.py --prg build/legacy/pacman.prg --output build/legacy/smoke

performance: $(PRG) tools/vicsim/vicsim
	$(PY) tests/performance.py

vice-test: $(PRG)
	$(PY) tools/arcade/vice_check.py

# Joystick port 1 uses arrows + space; keys 5, 1 and 2 are coin/start.
VICEFLAGS = -model vic20ntsc -memory all -autostartprgmode 1 \
            -addconfig tools/vice-keys.vrc -joydev1 2
run: $(PRG)
	xvic $(VICEFLAGS) -autostart $(PRG)

clean:
	rm -rf build

.PHONY: all reference test performance vice-test run clean multicolour run-multicolour test-multicolour ghost-shadow run-shadow test-shadow beam run-beam test-beam actor-commit run-actor-commit test-actor-commit
.PHONY: actor-speed actor-speed-reference run-actor-speed test-actor-speed
.PHONY: beam-priority beam-review beam-opportunistic run-beam-priority run-beam-review run-beam-opportunistic test-beam-priority
.PHONY: stable-colours run-stable-colours test-stable-colours
.PHONY: legacy run-legacy test-legacy
