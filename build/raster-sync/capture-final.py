import importlib.util,json
from pathlib import Path
root=Path.cwd();out=root/'build/raster-sync/after/vice'
spec=importlib.util.spec_from_file_location('raster_capture',root/'build/flicker/capture.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
labels={p[2][1:]:int(p[1],16) for line in (root/'build/pacman.lbl').read_text().splitlines() if len(p:=line.split())==3}
counts=[]
class Count(mod.FrameMonitor):
 def picture(self,palette):
  counts.append(self.memory(labels['raster_updates'],1)[0])
  return super().picture(palette)
mod.FrameMonitor=Count
inputs=json.loads((root/'build/sprite-kernel/after/vice/inputs.json').read_text())
mod.capture(root/'build/raster-sync/after/pacman.prg',out,600,inputs)
(out/'raster-counts.json').write_text(json.dumps(counts)+'\n')
print('Protected updates observed in VICE:',sum((b-a)&255 for a,b in zip(counts,counts[1:])))
