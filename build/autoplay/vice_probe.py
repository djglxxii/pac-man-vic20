import socket,struct,subprocess,time,sys
from pathlib import Path
sys.path.insert(0,'tools/arcade')
from vice_check import Monitor
class M(Monitor):
 def response(self):
  stx,v,length,kind,err,req=struct.unpack('<BBIBBI',self.read(12));b=self.read(length);return kind,err,req,b
 def cmd(self,kind,body=b''):
  self.req+=1;req=self.req;self.s.sendall(struct.pack('<BBIIB',2,2,len(body),req,kind)+body)
  while True:
   k,e,r,b=self.response()
   if k==0x62:self.stopped=True
   if r==req:
    if e:raise RuntimeError((kind,e,b))
    return b
 def stop(self):
  while not self.stopped:
   k,e,r,b=self.response()
   if k==0x62:self.stopped=True
 def run_stop(self,kind,body=b''):
  self.req+=1;req=self.req;self.s.sendall(struct.pack('<BBIIB',2,2,len(body),req,kind)+body)
  ack=running=stopped=False
  while not (ack and running and stopped):
   k,e,r,b=self.response()
   if k==0x63:running=True
   if k==0x62 and running:stopped=True
   if r==req:
    if e:raise RuntimeError((kind,e,b))
    ack=True
 def go(self):self.run_stop(0xaa)
 def frame(self,check):
  self.cmd(0x15,struct.pack('<IB',check,0));self.run_stop(0x71,struct.pack('<BH',0,12))
  self.cmd(0x15,struct.pack('<IB',check,1));self.go()
port=17861
log=open('build/autoplay/vice-probe.log','w')
p=subprocess.Popen(['xvic','-model','vic20ntsc','-memory','all','-initbreak','reset','-binarymonitor','-binarymonitoraddress',f'127.0.0.1:{port}','-sounddev','alsa','-soundarg','null','-speed','0','-autostartprgmode','1','-controlport1device','37','-autostart',str(Path('build/pacman.prg').resolve())],stdout=log,stderr=log)
try:
 for i in range(200):
  try:s=socket.create_connection(('127.0.0.1',port),timeout=.5);break
  except OSError:time.sleep(.05)
 s.settimeout(10);m=M(s);m.stopped=False;m.cmd(0x81);print('connected',flush=True)
 m.cmd(0xA2,struct.pack('<HH',0,255))
 b=m.cmd(0x12,struct.pack('<HHBBBBB',0,65535,1,1,4,0,0));check=struct.unpack_from('<I',b)[0];print('checkpoint',check,flush=True)
 cond=b'(RL == $1) && (CY < $8)';m.cmd(0x22,struct.pack('<IB',check,len(cond))+cond);m.go();print('at frame',list(m.memory(0x9003,2)),flush=True)
 t=time.monotonic()
 for i in range(180):
  m.frame(check)
  if i%60==0:print(i,round(time.monotonic()-t,2),list(m.memory(0x9003,2)),flush=True)
 m.screenshot(Path('build/autoplay/probe.png'));m.cmd(0xbb);p.wait(timeout=5)
finally:
 if p.poll()is None:p.terminate();p.wait(timeout=5)
 log.close()
