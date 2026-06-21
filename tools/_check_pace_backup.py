import os
p = r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt.bak_pre_retag_20260618'
with open(p, encoding='utf-8') as f:
    lines = f.read().split('\n')
n = sum(1 for l in lines if l.strip() and not l.startswith('#'))
print(f'bak_pre_retag: {n} non-comment')
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) >= 16 and p[3] == 'pace':
        print(f'  {p[3]}|{p[4]}|{p[14]}: tags={p[15]!r}')
