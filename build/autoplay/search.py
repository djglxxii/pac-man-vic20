import sys,time,itertools
from pathlib import Path
src=Path('build/autoplay/experiment.py').read_text().split('s=Sim();')[0]
exec(src)
for radius,mult,step in itertools.product((5,6,8,4,9),(2,5,.5),(4,2)):
 ns={};exec(src.replace('max(0,7-danger)**2*2',f'max(0,{radius}-danger)**2*{mult}'),ns);B=ns['Bot']
 s=Sim();start_game(s);s.cmd('until frame_wait 100');bot=B();t=time.monotonic();reason='timeout';deaths=0;lastlives=3
 for frame in range(0,16000,step):
  m=s.dump()
  if m[0xe14]<lastlives:deaths+=1
  lastlives=m[0xe14]
  if m[0xe00]!=3:reason='gameover';break
  if m[0xe06] and m[0xe13]==1:reason='WIN';break
  d=bot.act(m)if m[0xe04]==3 else '-';s.cmd('joy '+d);s.cmd('run '+str(step))
 print(radius,mult,step,reason,'frame',frame,'board',m[0xe13],'dots',m[0xe0e],'lives',m[0xe14],'sec',round(time.monotonic()-t,1),flush=True);s.close()
 if reason=='WIN':Path('build/autoplay/winner.txt').write_text(str((radius,mult,step)));break
