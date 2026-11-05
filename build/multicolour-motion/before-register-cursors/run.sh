#!/bin/sh
set -eu
vic_motion_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec xvic -model vic20ntsc -memory all -autostartprgmode 1 -autostart "$vic_motion_dir/motion.prg"
