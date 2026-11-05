import importlib.util,json
from pathlib import Path
root=Path.cwd()
spec=importlib.util.spec_from_file_location('raster_capture',root/'build/flicker/capture.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
inputs=json.loads((root/'build/sprite-kernel/before/vice/inputs.json').read_text())
mod.capture(root/'build/raster-sync/experiment-3/pacman.prg',root/'build/raster-sync/experiment-3/vice',600,inputs)
