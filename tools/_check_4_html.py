"""Show why each of 4 C1/B1 cards was dropped."""
import re
files = [
    ('accordance', r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_accordance_(noun).html'),
    ('behalf', r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_behalf_(noun).html'),
    ('consist', r'C:\Users\admin\Downloads\ankideck\data\.cache_html\oxford\oxford_consist_(verb).html'),
]

for word, path in files:
    print(f'\n=== {word} ===')
    with open(path, encoding='utf-8') as f:
        html = f.read()

    # Find all ol elements
    ol_matches = re.findall(r'<ol class="([^"]+)"', html)
    print(f'  ol classes: {ol_matches}')

    # Find each li.sense
    senses = re.findall(r'<li[^>]*hclass="sense"[^>]*>', html)
    print(f'  li.sense count: {len(senses)}')

    # Find idm-g contexts
    idm_sections = re.findall(r'<span class="idm"[^>]*>([^<]+)</span>', html)
    print(f'  idm phrases: {idm_sections}')

    # Check if main sense is inside idm-g
    sense_sng_count = len(re.findall(r'<ol class="sense_single"', html))
    sense_multi_count = len(re.findall(r'<ol class="senses_multiple"', html))
    idm_g_count = len(re.findall(r'<span class="idm-g"', html))
    idm_count = len(re.findall(r'<span class="idm"', html))
    print(f'  sense_single={sense_sng_count}, senses_multiple={sense_multi_count}, idm-g={idm_g_count}, idm={idm_count}')
