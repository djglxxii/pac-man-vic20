#!/usr/bin/env python3
"""addr2lbl.py LABELS ADDR... : nearest preceding label for each address."""
import sys
labs = []
for line in open(sys.argv[1]):
    p = line.split()
    if len(p) == 3 and p[0] == 'al':
        labs.append((int(p[1], 16), p[2][1:]))
labs.sort()
for a in sys.argv[2:]:
    v = int(a.lstrip('$'), 16)
    best = max((l for l in labs if l[0] <= v), default=None)
    print(f"${v:04X} = {best[1]}+{v-best[0]}" if best else a)
