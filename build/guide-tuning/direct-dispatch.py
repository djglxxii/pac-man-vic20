import re
from pathlib import Path
s=Path('build/guide-tuning/core-before.c').read_text()
sigs={n:args.strip() for n,args in re.findall(r'\b(?:void|uint8_t|uint16_t|XYPOS|int)\s+(\w+)\s*\(([^;{}]*)\)\s*\{',s)}
p=re.compile(r'static\s+(void|uint8_t)\s*\(\*const func\[\]\)(.*?)=\s*\{(.*?)\};',re.S)
changes=[]
for m in p.finditer(s):
 funcs=re.findall(r'\b\w+\b',m[3]);ret=m[1]
 tail=s[m.end():]
 c=re.search(r'tableCall_0020\(func,\s*(.*?)\);|(?:(int vol) = )?func\[(.*?)\]\((.*?)\);',tail)
 if c is None:raise RuntimeError(m.group()[:80])
 selector=c[1] or c[3];args=(c[4] or '').strip();assign='vol = ' if c[2] else ''
 out=['int vol;' if c[2] else '',f'switch ({selector}) {{']
 groups={}
 for i,fn in enumerate(funcs):groups.setdefault(fn,[]).append(i)
 for fn,indices in groups.items():
  if fn not in sigs:raise RuntimeError('No signature: '+fn)
  fnargs='' if sigs[fn] in ('','void') else args
  if fnargs=='' and sigs[fn] not in ('','void'):raise RuntimeError('Missing arguments: '+fn)
  out.extend(f'case {i}:' for i in indices)
  if not fn.startswith('nothing'):out.append(f'    {assign}{fn}({fnargs});')
  out.append('    break;')
 out.append('default: ASSERT(false);'+(' vol = 0;' if assign else ''))
 out.append('}')
 changes.append((m.start(),m.end()+c.end(),'\n'.join(out)))
for start,end,out in reversed(changes):s=s[:start]+out+s[end:]
Path('src/arcade/core.c').write_text(s)
print('Converted',len(changes),'dispatch tables')
