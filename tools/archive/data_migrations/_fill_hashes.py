"""Fill in cluster_hash into a verdicts file from the matching input."""
import sys
import json
import importlib.util
import hashlib

input_path = sys.argv[1]
verdicts_path = sys.argv[2]

data = json.loads(open(input_path, encoding='utf-8').read())
clusters = data['clusters']

def cluster_hash_for(c):
    word = c['word']
    pos = c['pos']
    texts = sorted(s['text'] for s in c['senses'])
    key = f"{word.lower()}|{pos}|" + '|'.join(texts)
    return hashlib.sha256(key.encode()).hexdigest()[:16]

by_word = {}
for c in clusters:
    by_word.setdefault(c['word'].lower(), []).append((cluster_hash_for(c), c['current_score']))

spec = importlib.util.spec_from_file_location("v", verdicts_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

filled = []
unmatched = []
for v in mod.VERDICTS:
    word_lower = v['word'].lower()
    cands = by_word.get(word_lower, [])
    if not cands:
        unmatched.append(v['word'])
        continue
    h, _ = cands[0]
    v_new = dict(v)
    v_new['cluster_hash'] = h
    filled.append(v_new)

print(f'Filled {len(filled)}/{len(mod.VERDICTS)}')
if unmatched:
    print(f'Unmatched: {unmatched}')

out = {
    'note': f'γ verdicts M3 session 2026-06-16. {len(filled)} clusters.',
    'verdicts': filled,
}
out_path = verdicts_path.replace('.py', '.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f'Wrote {out_path}')
