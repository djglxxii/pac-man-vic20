import json, re, sys
from pathlib import Path
ROOT=Path.cwd(); b=ROOT/'build/multicolour-motion'
sys.path.insert(0,str(ROOT/'tests'))
from native import Sim
listing=(b/'restore-pages.lst').read_text()
names=('restore_page','restore_map','restore_background','restore_code','restore_color')
labels={name:0x2000+int(re.search(r'^([0-9A-F]{6})r.*?\b'+name+r':$',listing,re.M).group(1),16) for name in names}
replay=(b/'replay.bin').read_bytes(); packet=b/'restore-cache.bin'
sim=Sim(b/'motion.prg')
try:
    sim.cmd('until demo_ready 100'); sim.cmd('profile reset')
    for start in range(0,len(replay),25):
        packet.write_bytes(replay[start:start+24])
        sim.cmd('load actors '+str(packet.relative_to(ROOT)))
        sim.cmd('call mc_prepare'); sim.cmd('call mc_commit')
    sim.cmd('profile '+str((b/'restore-pages.profile').relative_to(ROOT)))
finally:
    sim.close()
profile={int(p[0],16):{'cycles':int(p[1]),'hits':int(p[2])} for line in (b/'restore-pages.profile').read_text().splitlines() if len(p:=line.split())==3}
cells=profile[labels['restore_page']]['hits']; misses=profile[labels['restore_page']+4]['hits']
restored=profile[labels['restore_background']]['hits']
result={'frames':len(replay)//25,'old_cells_visited':cells,'cache_misses':misses,'cache_hits':cells-misses,
        'hit_percent':round((1-misses/cells)*100,2),'vacated_cells_restored':restored,
        'shared_cells_left_for_publication':cells-restored,'code_addresses':labels,
        'cached_branch_same_page':(labels['restore_page']+4)>>8==labels['restore_map']>>8,
        'background_load_cycles':profile[labels['restore_background']]['cycles'],
        'background_index_page_crossings':profile[labels['restore_background']]['cycles']-4*restored}
assert result['cached_branch_same_page']
(b/'restore-pages-cache.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
