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

$(GEN)/rom.stamp: tools/arcade/mkrom.py tools/arcade/hires_font.py tools/arcade/hires_pacman.py docs/artwork/hires-font.json docs/artwork/hires-pacman.json pacman.zip
	$(PY) tools/arcade/mkrom.py --output $(GEN)
	@touch $@

$(MOSCC): tools/bootstrap-llvm-mos.py
	$(PY) tools/bootstrap-llvm-mos.py --output $(MOSROOT)

$(GEN)/pacman-native.bin: $(NATIVE) $(wildcard src/arcade/*.h) src/video.h src/pacman.ld $(GEN)/rom.stamp $(MOSCC)
	$(MOSCC) $(CFLAGS) $(NATIVE) $(GEN)/rom.c -Wl,-Map,$(GEN)/pacman.map -o $@

$(PRG): $(GEN)/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

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

test: $(PRG) tools/vicsim/vicsim reference
	$(PY) tests/arcade.py
	$(PY) tests/native.py
	$(PY) tests/ghosts.py
	$(PY) tests/memory.py
	$(PY) tests/render.py
	$(PY) tests/fonts.py
	$(PY) tests/colors.py
	$(PY) tests/flash.py
	$(PY) tests/rebuild.py
	$(PY) tests/smoke.py

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
