"""Extract gloss jobs from new txt.

For each card in the new txt, output (word, pos, cefr, def) to a JSONL.
M3 will process these to generate 2-6 word glosses.

Output: data/simplify_diff/gloss_jobs.jsonl
  - One record per card
  - Schema: {word, pos, cefr, def, hash, source_card_index}

Hash is sha256 of (word + pos + cefr + def)[:16] for cache identity.
Excludes 'hallucination' for now (data bug fix in progress).
"""
import json
import hashlib
import sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))
from tools.build_notes import _parse_existing_txt

TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
OUT_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_jobs.jsonl'

# Words excluded from this batch (data bugs, fix separately)
EXCLUDE_WORDS = {'hallucination'}

def main():
    parsed = _parse_existing_txt(TXT_PATH)
    print(f'Loaded {len(parsed)} cards from new txt')
    jobs = []
    excluded = []
    for key, card in parsed.items():
        word, pos, cefr = key
        if word in EXCLUDE_WORDS:
            excluded.append(key)
            continue
        defn = card.get('definition_orig', '')
        h = hashlib.sha256(f'{word}|{pos}|{cefr}|{defn}'.encode()).hexdigest()[:16]
        jobs.append({
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'def': defn,
            'hash': h,
        })
    jobs.sort(key=lambda j: (j['word'], j['pos'], j['cefr']))
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open('w', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + '\n')
    print(f'Wrote {len(jobs)} jobs to {OUT_PATH}')
    if excluded:
        print(f'Excluded {len(excluded)} words: {excluded}')


if __name__ == '__main__':
    main()
