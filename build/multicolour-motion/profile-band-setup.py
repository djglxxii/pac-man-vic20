from pathlib import Path
import json,re,sys
sys.path.insert(0,'tests')
from native import Sim
b=Path('build/multicolour-motion');listing=(b/'band-setup.lst').read_text()
start=0x2000+int(re.search(r'^([0-9A-F]{6})r\s+\d\s+paint_colors:',listing,re.M)[1],16)
binary=(b/'motion.prg').read_bytes();base=int.from_bytes(binary[:2],'little')
branches={mask:start+2+4*i for i,mask in enumerate((3,2,1,7,5,6))}

def taken(p,addr):
 cycles,hits=p.get(addr,(0,0));offset=binary[addr+1-base+2]
 target=(addr+2+(offset if offset<128 else offset-256))&65535
 step=2 if ((addr+2)^target)&0xff00 else 1
 assert (cycles-2*hits)%step==0
 return (cycles-2*hits)//step

r=(b/'replay.bin').read_bytes();s=Sim(b/'motion.prg')
counts={name:{str(mask):0 for mask in range(1,8)} for name in ('147','201')};prior={mask:0 for mask in range(1,8)}
try:
 s.cmd('until demo_ready 100');s.cmd('profile reset')
 for i in range(480):
  bank=str(s.peek('mc_new_base')[0]);(b/'probe.bin').write_bytes(r[i*25:i*25+24])
  s.cmd('load actors build/multicolour-motion/probe.bin');s.cmd('call mc_prepare');s.cmd('call mc_commit')
  s.cmd('profile build/multicolour-motion/band-setup-colours.profile')
  p={int(a,16):(int(c),int(h)) for a,c,h in (l.split() for l in (b/'band-setup-colours.profile').read_text().splitlines())}
  now={mask:taken(p,pc) for mask,pc in branches.items()}
  now[4]=p.get(branches[6],(0,0))[1]-now[6]
  for mask,value in now.items():counts[bank][str(mask)]+=value-prior[mask]
  prior=now
finally:s.close()
result={'colour_write_masks_by_work_bank':counts,'all_seven_masks_executed_in_both_banks':all(n>0 for c in counts.values() for n in c.values()),'total_colour_update_rows':sum(sum(c.values()) for c in counts.values())}
(b/'band-setup-colour-coverage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
