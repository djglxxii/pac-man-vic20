#!/bin/sh
set -eu
vic_preview_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec xvic -model vic20ntsc -memory all -autostartprgmode 1 \
  -addconfig "$vic_preview_dir/../../../tools/vice-keys.vrc" -joydev1 2 \
  -autostart "$vic_preview_dir/pacman.prg"
