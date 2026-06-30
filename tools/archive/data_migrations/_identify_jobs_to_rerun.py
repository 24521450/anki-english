"""Identify jobs whose hash doesn't match any existing verdict.

After encoding fix (build_notes uses '|'), only 1-sense (concrete) hashes
stay the same. Multi-sense jobs (with '|' between senses now vs ';' before)
have new hashes that need fresh M3 verdicts.
"""
import json
from pathlib import Path

JOBS = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs.jsonl')
VERDICTS = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_all_verdicts.json')
OUT = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_to_rerun.jsonl')


def main():
    jobs = [json.loads(l) for l in JOBS.read_text(encoding='utf-8').splitlines() if l.strip()]
    verdicts_data = json.loads(VERDICTS.read_text(encoding='utf-8'))
    existing_hashes = {v['hash'] for v in verdicts_data.get('verdicts', [])}

    print(f'Total jobs: {len(jobs)}')
    print(f'Existing verdict hashes: {len(existing_hashes)}')

    matched = 0
    unmatched = 0
    out_jobs = []
    for j in jobs:
        if j['hash'] in existing_hashes:
            matched += 1
        else:
            unmatched += 1
            out_jobs.append(j)

    print(f'  Matched (keep old verdict): {matched}')
    print(f'  Unmatched (need new M3 verdict): {unmatched}')

    # Group unmatched by category
    import sys
    sys.path.insert(0, r'C:\Users\admin\Downloads\ankideck')
    from src.deck_builder.gloss_llm import detect_category

    cat_counts = {}
    for j in out_jobs:
        cat = detect_category(j['def'], j['pos'])
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    print(f'  Unmatched by category: {cat_counts}')

    OUT.write_text('\n'.join(json.dumps(j, ensure_ascii=False) for j in out_jobs) + '\n', encoding='utf-8')
    print(f'\nWrote {len(out_jobs)} jobs to re-run → {OUT}')


if __name__ == '__main__':
    main()
