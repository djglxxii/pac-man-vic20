import sys,json,random
from pathlib import Path
ROOT=Path.cwd();sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'tools/arcade')]
from native import Sim
from performance import start_game
from check_multicolour_motion import expected_scene,image_state
b=ROOT/'build/multicolour-game'; poses=json.loads((b/'poses.json').read_text())['images']
s=Sim(ROOT/'build/pacman-multicolour.prg');p=b/'scene.bin';d=b/'scenes.ram'
def dump():
 s.cmd('dump '+str(d.relative_to(ROOT)));return d.read_bytes()
def load(packet):
 p.write_bytes(packet);s.cmd('load actors '+str(p.relative_to(ROOT)))
try:
 start_game(s);s.cmd('until frame_wait 100')
 for i in range(2000):
  s.cmd('call video_background')
  if s.peek('rebuild_phase')==b'\0':break
 else:raise AssertionError('Background did not drain')
 s.cmd('call mc_update_hud');m=dump();under=s.labels['mc_backgrounds']
 codes=[c if c<147 else m[under+c-147] for c in m[0x1800:0x1a37]]
 bg=[m[0x1000+c*8:0x1008+c*8] for c in codes]
 colors=bytearray(m[0x9400:0x9637]);colors[42:546]=bytes([14])*504
 charset=m[0x1000:0x1498]
 hidden=bytes((0,0,255,0))*6
 scenes=[(b'\0'*24)] if False else []
 replay=(ROOT/'build/multicolour-motion/replay.bin').read_bytes()
 scenes += [replay[i:i+24] for i in range(0,len(replay),25)]
 for pose in range(len(poses)):
  for x in range(4):
   for y in range(8):scenes.append(bytes((28+x,80+y,pose,2))+hidden[4:])
 for x in (-8,-7,-5,-3,-1,0,79,81,83,84,87):
  for y in (0,11,15,16,194,201,207,208,250):scenes.append(bytes((x&255,y,0,4))+hidden[4:])
 for pose in range(len(poses)):
  for x in range(4):
   for y in (3,10,15,193,200,207):scenes.append(bytes((28+x,y,pose,2))+hidden[4:])
 rng=random.Random(6502)
 for i in range(180):
  packet=bytearray()
  for actor in range(6):
   x=rng.randrange(28,38) if i&1 else rng.randrange(-7,87)
   y=rng.randrange(75,88) if i&1 else rng.randrange(10,207)
   packet.extend((x&255,y,rng.randrange(len(poses)),rng.randrange(8)))
  scenes.append(bytes(packet))
 for i,packet in enumerate(scenes):
  before=image_state(dump());load(packet);s.cmd('call mc_prepare');m=dump()
  assert s.peek('mc_status')==b'\0',(i,'status')
  assert image_state(m)==before,(i,'hidden')
  assert m[0x1000:0x1498]==charset,(i,'charset')
  s.cmd('call mc_commit');m=dump()
  expected=expected_scene(packet,poses,bg,colors);actual=image_state(m)
  assert actual==expected,(i,'pixels',next((j for j,(a,e) in enumerate(zip(actual[0],expected[0])) if a!=e),None), next((j for j,(a,e) in enumerate(zip(actual[1],expected[1])) if a!=e),None))
 print('Passed scenes',len(scenes),'cacheerrors',s.peek('mc_cache_errors').hex())
finally:s.close()
