# VIC-20 (unexpanded, NTSC) ca65 project
CL65   ?= cl65
XVIC   ?= xvic
TARGET := main

all: $(TARGET).prg

$(TARGET).prg: main.s
	$(CL65) -t vic20 -C vic20-asm.cfg -u __EXEHDR__ -g -Ln $(TARGET).lbl -m $(TARGET).map -o $@ $<

run: $(TARGET).prg
	$(XVIC) -model vic20ntsc -memory none -moncommands $(TARGET).lbl -autostart $<

# Headless smoke test: builds with TEST_FRAMES so the program exits VICE via the debug cart.
test: main.s
	$(CL65) -t vic20 -C vic20-asm.cfg -u __EXEHDR__ --asm-define TEST_FRAMES=120 -o test.prg $<
	../../scripts/vice-test.sh --shot test.png test.prg

clean:
	rm -f *.prg *.o *.lbl *.map test.png

.PHONY: all run test clean
