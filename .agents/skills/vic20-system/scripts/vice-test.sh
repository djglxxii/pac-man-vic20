#!/usr/bin/env bash
# Headless VIC-20 smoke test in VICE (xvic) using the debug cartridge.
#
# The program under test signals its result by writing a byte to $910F
# (VICE -debugcart): 0 = pass, anything else = failure code. The emulator exits
# with that byte as its exit status. If the program never writes $910F, VICE
# stops after --cycles and the script reports a timeout.
#
# Usage:
#   vice-test.sh [options] program.prg
# Options:
#   --mem LIST     memory expansion: none (default), 3k, 8k, 16k, 24k, all, or blocks "1,2,3,5"
#   --pal          PAL machine (default NTSC)
#   --cycles N     cycle limit (default 30000000 ~ 30 s of emulated time incl. boot)
#   --shot FILE    write a PNG screenshot on exit
#   --cart         treat the file as an $A000 cartridge image (-cartA) instead of autostarting a PRG
#
# Example (ca65): write `lda #0 / sta $910f` when your self-test passes.
#   cl65 -t vic20 -C vic20-asm.cfg -u __EXEHDR__ -o t.prg t.s && vice-test.sh --shot t.png t.prg
set -u
mem=none; model=vic20ntsc; cycles=30000000; shot=""; cart=0
while [ $# -gt 1 ]; do
  case "$1" in
    --mem) mem="$2"; shift 2;;
    --pal) model=vic20pal; shift;;
    --cycles) cycles="$2"; shift 2;;
    --shot) shot="$2"; shift 2;;
    --cart) cart=1; shift;;
    *) echo "unknown option $1" >&2; exit 2;;
  esac
done
prg="${1:?program file required}"
command -v xvic >/dev/null || { echo "xvic (VICE) not found in PATH" >&2; exit 2; }

args=(-default -model "$model" -memory "$mem" -console -sounddev dummy -debugcart -limitcycles "$cycles")
[ -n "$shot" ] && args+=(-exitscreenshot "$shot")
if [ "$cart" = 1 ]; then args+=(-cartA "$prg"); else args+=(-autostart "$prg"); fi

log="$(mktemp)"
xvic "${args[@]}" >"$log" 2>&1
status=$?
line="$(grep -m1 'DBGCART' "$log")"
rm -f "$log"
if [ -n "$line" ]; then
  echo "$line"
  [ "$status" = 0 ] && echo "PASS" || echo "FAIL (code $status)"
  exit "$status"
fi
echo "TIMEOUT: program never wrote \$910F within $cycles cycles (crash, hang, or missing exit write)"
[ -n "$shot" ] && echo "screenshot: $shot"
exit 124
