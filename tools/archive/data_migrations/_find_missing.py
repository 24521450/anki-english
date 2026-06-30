"""Find cards in txt that don't have a verdict in gloss_all_verdicts.json."""
import json
import re
from collections import Counter

# Read txt
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    raw = f.read()

lines = raw.split('\n')
# Cards = non-comment lines, non-empty
cards = []
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    parts = l.split('\t')
    if len(parts) >= 5:
        # Fields: GUID, NoteType, Deck, Word, POS, [empty?], Definition, Example, ...
        # Let me check the actual field order from a sample
        cards.append({'line': l, 'parts': parts, 'fields': {}})

# Inspect the first card to confirm field order
print('First card fields:')
for i, p in enumerate(cards[0]['parts'][:20]):
    print(f'  col {i}: {repr(p[:80])}')

# From prior inspection: GUID, NoteType, Deck, Word, POS, <empty>, Definition, Example, ...
# Let me parse properly
# Word is col 3, POS is col 4, CEFR is col 14, Definition is col 6, Example is col 7

# Actually, from the sample earlier:
# "pL@#qNFU&M"\tEnglish Academic Vocabulary Model\tEnglish Academic Vocabulary::TED YT\tabdominal\tadjective\t\tof the abdomen\tabdominal pains\t\t\t[sound:cambridge_uk_abdominal.mp3]\t[sound:cambridge_us_abdominal.mp3]\tOxford\tOxford\tUNCLASSIFIED\tSource::Oxford CEFR::UNCLASSIFIED CEFR::oxford
# 0: GUID, 1: NoteType, 2: Deck, 3: Word, 4: POS, 5: empty, 6: Definition, 7: Example,
# 8: ?, 9: ?, 10: UK audio, 11: US audio, 12: ?, 13: ?, 14: CEFR, 15: tags

txt_cards = []
for c in cards:
    p = c['parts']
    if len(p) < 15:
        print(f'WARN: card with {len(p)} fields: {c["line"][:100]}')
        continue
    txt_cards.append({
        'word': p[3].strip(),
        'pos': p[4].strip(),
        'cefr': p[14].strip() if p[14] else 'UNCLASSIFIED',
        'definition': p[6] if len(p) > 6 else '',
        'example': p[7] if len(p) > 7 else '',
    })

print(f'\nTotal parsed txt cards: {len(txt_cards)}')

# Read verdicts
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    verdicts_raw = json.load(f)
verdicts = verdicts_raw['verdicts'] if isinstance(verdicts_raw, dict) and 'verdicts' in verdicts_raw else verdicts_raw

verdict_keys = set()
for v in verdicts:
    verdict_keys.add((v.get('word'), v.get('pos'), v.get('cefr')))

print(f'Total verdicts: {len(verdicts)} ({len(verdict_keys)} unique keys)')

# Find cards in txt that DON'T have a verdict
missing = []
for c in txt_cards:
    key = (c['word'], c['pos'], c['cefr'])
    if key not in verdict_keys:
        missing.append(c)

print(f'\nCards in txt WITHOUT verdict: {len(missing)}')
print(f'\nFirst 20 missing:')
for c in missing[:20]:
    print(f'  {c["word"]}|{c["pos"]}|{c["cefr"]}: def="{c["definition"][:60]}"')

# Group by CEFR
cefr_dist = Counter(c['cefr'] for c in missing)
print(f'\nMissing by CEFR: {dict(cefr_dist)}')

# Save to file for review
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_txt_no_verdict.json', 'w', encoding='utf-8') as f:
    json.dump(missing, f, indent=2, ensure_ascii=False)
print(f'\nSaved {len(missing)} missing cards to data/simplify_diff/audit_txt_no_verdict.json')

# Also: cards with verdict but NOT in txt
verdict_set = set()
for v in verdicts:
    verdict_set.add((v.get('word'), v.get('pos'), v.get('cefr')))

txt_set = set((c['word'], c['pos'], c['cefr']) for c in txt_cards)
verdict_only = verdict_set - txt_set
print(f'\nVerdicts NOT in txt: {len(verdict_only)}')
if verdict_only:
    print('First 10:')
    for k in list(verdict_only)[:10]:
        print(f'  {k}')
