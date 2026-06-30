with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    content = f.read()

for l in content.split('\n'):
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) >= 7 and p[3] == 'pace':
        word = p[3]
        pos = p[4]
        cefr = p[14]
        defn = p[6][:60] if p[6] else ''
        print(f"FOUND: word={word!r}, pos={pos!r}, cefr={cefr!r}, def={defn!r}")
