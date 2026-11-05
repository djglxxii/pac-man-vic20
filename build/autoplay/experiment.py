import sys,heapq,json,time
from collections import deque
from pathlib import Path
sys.path.insert(0,'tests')
from native import Sim
from performance import start_game
DIR={'R':(-1,0),'D':(0,1),'L':(1,0),'U':(0,-1)}
class Bot:
 def __init__(self): self.visits={};self.last=None;self.goal=None
 def act(self,m):
  p=(m[0xd09]//8,m[0xd08]//8);screen=m[0x400:0x800]
  nodes={(x,y)for x in range(32)for y in range(32) if (2<=x<=29 or y==17) and screen[x*32+y]<192}
  def edges(p):
   for d,(dx,dy)in DIR.items():
    q=((p[0]+dx)%32,p[1]+dy)
    if q in nodes:yield d,q
  ghosts=[(m[0xd01+i*2]//8,m[0xd00+i*2]//8)for i in range(4)if not(m[0xa7+i]or m[0xac+i])]
  hazard={g:0 for g in ghosts if g in nodes};todo=deque(hazard)
  while todo:
   n=todo.popleft()
   for _,q in edges(n):
    if q not in hazard:hazard[q]=hazard[n]+1;todo.append(q)
  if p!=self.last:self.visits[p]=self.visits.get(p,0)+1;self.last=p
  heap=[(0,0,p,'')];seen=set();count=0
  while heap:
   cost,_,n,first=heapq.heappop(heap)
   if n in seen:continue
   seen.add(n)
   if screen[n[0]*32+n[1]]in(16,20)and n!=p:return first
   for d,q in edges(n):
    if q in seen:continue
    danger=hazard.get(q,100)
    extra=max(0,7-danger)**2*2
    if screen[q[0]*32+q[1]]==20:extra=0
    count+=1;heapq.heappush(heap,(cost+1+extra+self.visits.get(q,0)*.02,count,q,first or d))
  return 'L'
s=Sim();start_game(s);s.cmd('until frame_wait 100');bot=Bot();t=time.monotonic();last=None;events=[]
for f in range(0,60000,4):
 m=s.dump();state=(m[0xe13],m[0xe04],m[0xe14],m[0xe0e]);node=(m[0xd09]//8,m[0xd08]//8)
 if f%600==0 or state[:3]!=last:
  print(f,'state',state,'pos',node,'ghosts',[(m[0xd01+i*2]//8,m[0xd00+i*2]//8)for i in range(4)],'time',round(time.monotonic()-t,1),flush=True)
 last=state[:3]
 if m[0xe00]!=3: print('GAME OVER',flush=True);break
 if m[0xe06] and m[0xe13]==1:print('INTERMISSION',flush=True);break
 d=bot.act(m)if m[0xe04]==3 else '-';s.cmd('joy '+d);s.cmd('run 4');events.append(d)
Path('build/autoplay/experiment-inputs.json').write_text(json.dumps(events));s.close()
