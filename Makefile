# SNAPBUG for the VIC-20 (NTSC, full memory expansion)
CC65BIN ?= $(CURDIR)/tools/cc65/usr/bin
CA65    := $(if $(wildcard $(CC65BIN)/ca65),$(CC65BIN)/ca65,ca65)
LD65    := $(if $(wildcard $(CC65BIN)/ld65),$(CC65BIN)/ld65,ld65)
PY      := python3

GEN  := build/gen
SRCS := $(wildcard src/*.s) src/vic.inc
PRG  := build/snapbug.prg

all: $(PRG)

$(GEN)/consts.inc $(GEN)/data.inc $(GEN)/charset.bin: tools/mkdata.py
	$(PY) tools/mkdata.py $(GEN) --preview build/preview

$(GEN)/sound.inc: tools/mksound.py
	$(PY) tools/mksound.py $@

build/snapbug.o: $(SRCS) $(GEN)/consts.inc $(GEN)/data.inc $(GEN)/charset.bin $(GEN)/sound.inc
	$(CA65) --cpu 6502 -I src -I $(GEN) --bin-include-dir $(GEN) -g -l build/snapbug.lst -o $@ src/snapbug.s

$(PRG): build/snapbug.o src/snapbug.cfg
	$(LD65) -C src/snapbug.cfg -o $@ -m build/snapbug.map -Ln build/snapbug.lbl $<
	@echo "built $@ ($$(stat -c %s $@) bytes)"

tools/vicsim/vicsim: tools/vicsim/vicsim.c
	cc -O2 -w -o $@ $<

test: $(PRG) tools/vicsim/vicsim
	$(PY) tests/sound.py
	$(PY) tests/bot.py 30000

# NTSC VIC-20, full RAM expansion, program injected straight into RAM.
# Joystick port 1 = arrow keys + space (tools/vice-keys.vrc).
VICEFLAGS = -model vic20ntsc -memory all -autostartprgmode 1 \
            -addconfig tools/vice-keys.vrc -joydev1 2

run: $(PRG)
	xvic $(VICEFLAGS) -autostart $(PRG)

clean:
	rm -rf build

.PHONY: all test run clean
