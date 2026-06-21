import sys
sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
from src.scraper.oxford import parse_oxford
import json

with open(r'C:\Users\admin\Downloads\ankideck/data/.cache_html/oxford/oxford_accordance_(noun).html', 'rb') as f:
    html_bytes = f.read()

result = parse_oxford(html_bytes, source_files=['oxford_accordance_(noun).html'])
print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
