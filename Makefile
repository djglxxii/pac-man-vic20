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
NATIVE := src/start.S src/clock.S src/bitmap.S src/sprites.S src/audio.S src/pacman.c src/platform.c src/video.c $(CORE)
# $A0-$FF holds arcade flags. Of the remaining 126 zero-page bytes, assembly
# reserves 34; the compiler may allocate at most 92 more.
CFLAGS := -Oz -gline-tables-only -mlto-zp=92 -nostartfiles -DVIC20 -Wno-everything -Isrc/arcade -I$(GEN) -Tsrc/pacman.ld

all: $(PRG)

$(GEN)/rom.stamp: tools/arcade/mkrom.py pacman.zip
	$(PY) tools/arcade/mkrom.py --output $(GEN)
	@touch $@

$(MOSCC): tools/bootstrap-llvm-mos.py
	$(PY) tools/bootstrap-llvm-mos.py --output $(MOSROOT)

$(GEN)/pacman-native.bin: $(NATIVE) $(wildcard src/arcade/*.h) src/video.h src/pacman.ld $(GEN)/rom.stamp $(MOSCC)
	$(MOSCC) $(CFLAGS) $(NATIVE) $(GEN)/rom.c -Wl,-Map,$(GEN)/pacman.map -o $@

$(PRG): $(GEN)/pacman-native.bin tools/arcade/pack.py
	$(PY) tools/arcade/pack.py $< $@ --ca65 $(CA65) --ld65 $(LD65) --nm $(MOSNM)

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
	$(PY) tests/render.py
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

.PHONY: all reference test performance vice-test run clean
