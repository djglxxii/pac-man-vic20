# cc65 C + assembly example for the unexpanded NTSC VIC-20 (tested in VICE 3.7.1)
CL65 ?= cl65
CFLAGS := -t vic20 -Osir -Cl

prog.prg: main.c kernels.s
	$(CL65) $(CFLAGS) -m prog.map -o $@ main.c kernels.s

# main.c exits VICE via the debug cart ($910F): 0 = all checks passed
test: prog.prg
	../../../vic20-system/scripts/vice-test.sh --shot test.png prog.prg

run: prog.prg
	xvic -model vic20ntsc -memory none -autostart prog.prg

clean:
	rm -f *.prg *.o *.map test.png
.PHONY: test run clean
