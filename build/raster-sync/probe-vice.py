import importlib.util,json,struct
from pathlib import Path
root=Path.cwd();out=root/'build/raster-sync/vice-raster-probe'
spec=importlib.util.spec_from_file_location('raster_capture',root/'build/flicker/capture.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
labels={p[2][1:]:int(p[1],16) for line in (root/'build/pacman.lbl').read_text().splitlines() if len(p:=line.split())==3}
observations=[]
class Probe(mod.FrameMonitor):
 def setup(self):
  data=self.cmd(0x83,b'\0');pos=2;self.names={}
  for i in range(int.from_bytes(data[:2],'little')):
   size=data[pos];rid=data[pos+1];length=data[pos+3];name=data[pos+4:pos+4+length].decode();self.names[rid]=name;pos+=size+1
  print(self.names,flush=True)
  self.points={}
  for name,symbol in (('start','raster_safe'),('end','sprites_return')):
   pc=labels[symbol];body=struct.pack('<HHBBBBB',pc,pc,1,int(name=='start'),4,0,0)
   self.points[name]=int.from_bytes(self.cmd(0x12,body)[:4],'little')
  self.pending=None
 def regs(self):
  data=self.cmd(0x31,b'\0');pos=2;values={}
  for i in range(int.from_bytes(data[:2],'little')):
   size=data[pos];values[self.names[data[pos+1]]]=int.from_bytes(data[pos+2:pos+4],'little');pos+=size+1
  return values
 def toggle(self,name,enabled):self.cmd(0x15,struct.pack('<IB',self.points[name],enabled))
 def observe(self,r):
  if r['PC']==labels['raster_safe']:
   top=self.memory(labels['raster_top'],1)[0]*2;bottom=(self.memory(labels['raster_end'],1)[0]-1)*2
   self.pending={'start':r,'top':top,'bottom':bottom}
   self.toggle('start',0);self.toggle('end',1);return True
  if r['PC']==labels['sprites_return'] and self.pending:
   self.pending['end']=r;observations.append(self.pending);self.pending=None
   self.toggle('end',0);self.toggle('start',1);return True
  return False
 def next_frame(self,checkpoint):
  if not hasattr(self,'points'):self.setup()
  self.cmd(0x15,struct.pack('<IB',checkpoint,0))
  while True:
   super().run_until_stop(0x71,struct.pack('<BH',0,12))
   if not self.observe(self.regs()):break
  self.cmd(0x15,struct.pack('<IB',checkpoint,1))
  while True:
   super().run_until_stop()
   r=self.regs()
   if not self.observe(r):
    assert r.get('RL',r.get('LIN'))==1,r
    break
mod.FrameMonitor=Probe
inputs=json.loads((root/'build/sprite-kernel/after/vice/inputs.json').read_text())
try:mod.capture(root/'build/raster-sync/after/pacman.prg',out,600,inputs)
finally:
 out.mkdir(exist_ok=True);(out/'observations.json').write_text(json.dumps(observations,indent=2)+'\n')
 print('protected updates',len(observations),flush=True)
