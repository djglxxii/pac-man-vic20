import importlib.util
from pathlib import Path
root=Path.cwd()
spec=importlib.util.spec_from_file_location('raster_capture',root/'build/flicker/capture.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
inputs=mod.capture(root/'build/sprite-kernel/before/pacman.prg',root/'build/sprite-kernel/before/vice',600)
mod.capture(root/'build/sprite-kernel/after/pacman.prg',root/'build/sprite-kernel/after/vice',600,inputs)
