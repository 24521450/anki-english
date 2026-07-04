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
from src.deck_builder.build_validation import _parse_txt_cards

TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
OUT_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_jobs.jsonl'

# Words excluded from this batch (data bugs, fix separately)
EXCLUDE_WORDS = {'hallucination'}

def main():
    cards, issues = _parse_txt_cards(TXT_PATH.read_text(encoding='utf-8'), TXT_PATH)
    if issues:
        raise RuntimeError("\n".join(issue.format() for issue in issues))
    print(f'Loaded {len(cards)} cards from new txt')
    jobs = []
    excluded = []
    for card in cards:
        word, pos, cefr = card.word, card.pos, card.cefr
        if word in EXCLUDE_WORDS:
            excluded.append((word, pos, cefr))
            continue
        defn = card.definition
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
