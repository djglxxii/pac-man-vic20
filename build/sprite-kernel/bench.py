import argparse, json, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tests'))
from native import Sim

p=argparse.ArgumentParser()
p.add_argument('--prg',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
s=Sim(a.prg)
try:
 s.cmd('run 500')
 s.cmd('until frame_wait 100')
 rows=[]
 for eye in (False,True):
  for code in range(8 if eye else 64):
   for shift in range(8):
    for flip in range(4):
     for flags in (1,2,3):
      for column,y in ((0,0),(7,209)):
       source=s.labels['arcade_eyes' if eye else 'arcade_sprites']+12*code
       dest=0x1000+224*column+y
       save=s.labels['under']+8
       for name,value in (('v_data',source&255),('v_data+1',source>>8),('v_addr',dest&255),('v_addr+1',dest>>8),('v_save',save&255),('v_save+1',save>>8),('v_shift',shift),('v_flip',flip),('v_flags',flags)):
        if '+' in name:
         base,delta=name.split('+')
         name=f'${s.labels[base]+int(delta):x}'
        s.cmd(f'poke {name} {value}')
       line=s.cmd('call bitmap_draw')[-1]
       cost=int(line.split('cycles=')[1])
       rows.append({'eyes':eye,'code':code,'shift':shift,'flip':flip,'flags':flags,'column':column,'y':y,'cycles':cost})
 groups=defaultdict(list)
 for row in rows:
  groups['all'].append(row['cycles'])
  groups['full' if row['flags']==3 else 'clipped'].append(row['cycles'])
  groups[f"shift-{row['shift']}"].append(row['cycles'])
 report={'cases':len(rows),'groups':{name:{'min':min(v),'mean':sum(v)/len(v),'max':max(v)} for name,v in groups.items()},'rows':rows}
 a.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'cases':len(rows),'groups':report['groups']},indent=2))
finally:s.close()
