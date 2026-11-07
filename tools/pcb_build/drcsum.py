import re, sys
from collections import defaultdict
s=open(sys.argv[1],encoding='utf8',errors='replace').read()
by=defaultdict(list)
for e in re.split(r'\n(?=\[)', s):
    m=re.match(r'\[(\w+)\]', e)
    if m and m.group(1) not in ('silk_over_copper','silk_overlap'):
        by[m.group(1)].append(re.sub(r'\s+',' ',e)[:260].replace('Local override; error ','').replace('Missing connection between items ',''))
for k,v in sorted(by.items(), key=lambda kv:-len(kv[1])):
    print(f'\n=== {k} ({len(v)})')
    for e in v[:30]: print(' ', e)
