from pathlib import Path
txt = Path(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt')
n = 0
samples = []
for l in txt.read_text(encoding='utf-8').splitlines():
    if 'delete' in l.lower():
        n += 1
        if len(samples) < 3:
            samples.append(l[:200])
print(f'Lines with delete anywhere: {n}')
for s in samples:
    print(f'  {s!r}')
