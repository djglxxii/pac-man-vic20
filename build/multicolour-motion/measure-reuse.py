from pathlib import Path
import hashlib,json,statistics,sys
sys.path.insert(0,'tests')
sys.path.insert(0,'tools/arcade')
from native import Sim
from check_multicolour_motion import image_state
b=Path('build/multicolour-motion');replay=(b/'replay.bin').read_bytes();results={}
for name,prg in [('before',b/'before-actor-reuse/motion.prg'),('candidate',b/'motion.prg')]:
 s=Sim(prg);frames=[]
 try:
  s.cmd('until demo_ready 100')
  for i in range(480):
   (b/'probe.bin').write_bytes(replay[i*25:i*25+24]);s.cmd('load actors build/multicolour-motion/probe.bin')
   p=int(s.cmd('call mc_prepare')[-1].split('cycles=')[1]);n=s.peek('mc_reused_count')[0] if name=='candidate' else 0
   c=int(s.cmd('call mc_commit')[-1].split('cycles=')[1]);s.cmd('dump build/multicolour-motion/probe.ram')
   glyphs,colors=image_state((b/'probe.ram').read_bytes())
   frames.append({'scene':i,'prepare':p,'commit':c,'total':p+c,'retained_cells':n,'picture_sha256':hashlib.sha256(b''.join(glyphs)+colors).hexdigest()})
 finally:s.close()
 results[name]=frames
assert all(a['picture_sha256']==z['picture_sha256'] for a,z in zip(results['before'],results['candidate']))
summary={'all_480_published_pictures_identical':True,
         'retained_cells_per_scene':round(statistics.mean(x['retained_cells'] for x in results['candidate']),3),
         'scenes_with_retained_cells':sum(x['retained_cells']>0 for x in results['candidate']),
         'faster_scenes':sum(z['total']<a['total'] for a,z in zip(results['before'],results['candidate'])),
         'slower_scenes':sum(z['total']>a['total'] for a,z in zip(results['before'],results['candidate'])),
         'before_mean_cycles':round(statistics.mean(x['total'] for x in results['before']),2),
         'candidate_mean_cycles':round(statistics.mean(x['total'] for x in results['candidate']),2)}
(b/'reuse-comparison-scenes.json').write_text(json.dumps(results,indent=2)+'\n');(b/'reuse-comparison.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
