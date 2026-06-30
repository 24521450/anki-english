with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

for l in lines:
    for keyword in ['counter (argue', 'counter (long', 'strip (long', 'strip (remove', 'grave (for', 'grave (serious)']:
        if keyword in l:
            p = l.split('\t')
            if len(p) >= 7:
                word = p[3]
                pos = p[4]
                cefr = p[14]
                defn = p[6]
                print(f"  {word:35s} | {pos:10s} | {cefr:13s} | def: {defn!r}")
            break
