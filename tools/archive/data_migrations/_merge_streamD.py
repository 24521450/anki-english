"""Merge 46 streamD verdicts into gloss_all_verdicts.json with proper hashes."""
import json
import hashlib

# Read txt to get def for hashing
with open(r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt', encoding='utf-8') as f:
    lines = f.read().split('\n')

txt_defs = {}  # (word, pos, cefr) -> def
for l in lines:
    if l.startswith('#') or not l.strip():
        continue
    p = l.split('\t')
    if len(p) < 15:
        continue
    word = p[3].strip()
    pos = p[4].strip()
    cefr = p[14].strip() or 'UNCLASSIFIED'
    defn = p[6] if len(p) > 6 else ''
    txt_defs[(word, pos, cefr)] = defn

print(f'Loaded {len(txt_defs)} txt defs')

# Load all 4 batch files
all_verdicts = []
for batch in ['D1', 'D2', 'D3', 'D4']:
    with open(rf'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_batch_{batch}.json', encoding='utf-8') as f:
        batch_v = json.load(f)
    all_verdicts.extend(batch_v)
    print(f'  batch {batch}: {len(batch_v)} verdicts')

print(f'\nTotal: {len(all_verdicts)} verdicts')

# Add hash field for each
for v in all_verdicts:
    key = (v['word'], v['pos'], v['cefr'])
    defn = txt_defs.get(key, '')
    h = hashlib.sha256(f'{v["word"]}|{v["pos"]}|{v["cefr"]}|{defn}'.encode()).hexdigest()[:16]
    v['hash'] = h
    if not defn:
        print(f'  WARN: no def for {key}')

# Now load existing verdicts and check for duplicates
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', encoding='utf-8') as f:
    data = json.load(f)
existing = data['verdicts']
existing_keys = set((v['word'], v['pos'], v['cefr']) for v in existing)

# Check for duplicates
dup = [v for v in all_verdicts if (v['word'], v['pos'], v['cefr']) in existing_keys]
if dup:
    print(f'\nDUPLICATE keys found: {len(dup)}')
    for v in dup:
        print(f'  {v["word"]}|{v["pos"]}|{v["cefr"]}')
    print('These already exist in gloss_all_verdicts.json - skipping')
    all_verdicts = [v for v in all_verdicts if (v['word'], v['pos'], v['cefr']) not in existing_keys]

print(f'\nNew verdicts to add: {len(all_verdicts)}')

# Backup
backup_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json.bak_pre_streamD_20260618'
import shutil
shutil.copy(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json', backup_path)
print(f'Backup: {backup_path}')

# Append
data['verdicts'].extend(all_verdicts)
print(f'\nNew total: {len(data["verdicts"])} (was 2477 + 46 = 2523)')

# Write
out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f'Wrote {out_path}')
