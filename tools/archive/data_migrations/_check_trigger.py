with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) >= 7 and p[3] == 'trigger':
        word = p[3]
        pos = p[4]
        cefr = p[14]
        defn = p[6]
        print(f"  {word:15s} | {pos:10s} | {cefr:13s} | def: {defn!r}")
