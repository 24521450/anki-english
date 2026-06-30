"""Count HTML files with fkcefr using efficient string search."""
import os

cache_dir = r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford'
fkcefr_files = []
total = 0
for f in os.listdir(cache_dir):
    if not (f.startswith('oxford_') and f.endswith('.html')):
        continue
    total += 1
    path = os.path.join(cache_dir, f)
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            content = fh.read(50000)  # Only first 50K bytes (senses at top)
        if 'fkcefr=' in content:
            fkcefr_files.append(f)
    except Exception:
        pass

print(f'Total Oxford HTML files: {total}')
print(f'Files with fkcefr attribute: {len(fkcefr_files)}')
print(f'Sample:')
for f in fkcefr_files[:5]:
    print(f'  {f}')
