with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

for i, l in enumerate(lines):
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) >= 16 and p[3] == 'pace':
        print(f'line {i}: {l[:200]}')
        print(f'  fields: {len(p)}')
        print(f'  word={p[3]!r}, pos={p[4]!r}, cefr={p[14]!r}')
        print(f'  tags: {p[15]!r}')
        print(f'  delete in tags.split(): {"delete" in p[15].split()}')
