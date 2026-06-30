"""Quick test: parse_oxford on audition, verify fkcefr fallback works."""
import sys
PROJECT_ROOT = r'C:\Users\admin\Downloads\ankideck'
sys.path.insert(0, PROJECT_ROOT)

from src.scraper.oxford import parse_oxford

for filename in ['oxford_audition_(noun).html', 'oxford_aggregate_(adj).html',
                 'oxford_aggregate_(verb).html', 'oxford_aggregate_1_(noun).html']:
    path = f'{PROJECT_ROOT}/data/.cache_html/oxford/{filename}'
    with open(path, 'rb') as f:
        raw = f.read()
    result = parse_oxford(raw)
    defs = result.get('pos_data', [{}])[0].get('definitions', [])
    if defs:
        cefr = defs[0].get('cefr')
        print(f'{filename}: sense 1 cefr={cefr!r}')

# Count fkcefr in HTML files - optimized with grep
import subprocess
result = subprocess.run(
    ['grep', '-rl', 'fkcefr=', r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford'],
    capture_output=True, text=True
)
fkcefr_files = len([f for f in result.stdout.split('\n') if f.endswith('.html')])
print(f'\nHTML files with fkcefr attribute: {fkcefr_files}')
