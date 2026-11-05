import json,subprocess,sys,collections
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
from native import Sim,ROOT
out=ROOT/'build/performance'/sys.argv[1];out.mkdir(parents=True,exist_ok=True)
sim=Sim()
try:
 sim.cmd('run 1000');sim.cmd('key 5');sim.cmd('run 30');sim.cmd('key -');sim.cmd('run 60');sim.cmd('key 1');sim.cmd('run 80');sim.cmd('key -')
 for _ in range(500):
  if sim.peek(0xe00)[0]==3 and sim.peek(0xe04)[0]==3:break
  sim.cmd('run 1')
 sim.cmd('run 30');sim.cmd('until frame_wait 100')
 start=int.from_bytes(sim.peek('arcade_ticks',2),'little');sim.cmd('profile reset');sim.cmd('run 180');end=int.from_bytes(sim.peek('arcade_ticks',2),'little');sim.cmd('profile '+str(out/'play.profile'));sim.cmd('profile off')
 labels=sim.labels
finally:sim.close()
profile={int(a,16):(int(c),int(h)) for a,c,h in map(str.split,(out/'play.profile').read_text().splitlines())}
seconds=180*65*261/1022727
report={'logic_ticks':end-start,'seconds':seconds,'renders':profile.get(labels['video_frame_begin'],(0,0))[1],'render_ends':profile.get(labels['video_frame_end'],(0,0))[1]}
report['fps']=report['renders']/seconds
(out/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
elf=ROOT/'build/arcade/pacman-native.bin.elf'
subprocess.run(['cp',str(elf),str(out/'pacman-native.bin.elf')],check=True)
pcs=list(profile);text=subprocess.check_output(['tools/llvm-mos/bin/llvm-addr2line','-e',str(elf),'-f'],input=''.join(f'{pc:x}\n' for pc in pcs),text=True).splitlines()
byline=collections.Counter();byfunc=collections.Counter()
for i,pc in enumerate(pcs):
 func,line=text[2*i:2*i+2];byline[line]+=profile[pc][0];byfunc[func]+=profile[pc][0]
print('Functions');print('\n'.join(f'{v/180:7.0f} {k}' for k,v in byfunc.most_common(22)))
print('Lines');print('\n'.join(f'{v/180:7.0f} {k}' for k,v in byline.most_common(30)))
