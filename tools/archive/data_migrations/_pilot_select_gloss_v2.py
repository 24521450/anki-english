"""Select 30 pilot words for gloss v2 testing.

6 categories × 5 words each. Used to verify the new GLOSS_SYSTEM_PROMPT
(Rule A/B/C, separator semantics, safety net) before re-running the
full 580-650 verdict re-gloss.

Categories:
  1. cat1_safety_net      — multi-sense with domain-restricted only sense → test S1
  2. cat2_distinct        — multi-sense-3+ with 2 distinct domains → test B pick-2 with |
  3. cat3_near_syn        — multi-sense-3+ with near-synonyms → test B pick-1 or ;
  4. cat4_multi_pos       — multi-POS at same CEFR → test multi-POS detection
  5. cat5_abstract        — abstract (from existing verdicts) → test abstract handling
  6. cat6_concrete        — concrete control (from existing verdicts) → control group

Output: data/simplify_diff/pilot_v2_jobs.jsonl — one record per word with
word/pos/cefr/def/category/expected_separator/expected_count/notes.
"""
from __future__ import annotations
import json
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
JSONL_PATH = PROJECT_ROOT / 'data' / 'oxford_merged.jsonl'
JOBS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_jobs.jsonl'
VERDICTS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_all_verdicts.json'
OUT_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'pilot_v2_jobs.jsonl'

# Hardcoded candidates for cat 1-4. Each tuple: (word, pos, cefr, category, expected_sep, expected_count, notes)
HARD_CODED = [
    # === Category 1: safety net ===
    ('bar', 'noun', 'C1', 'cat1_safety_net', 'none', 1, 'Music only sense at C1'),
    ('bar', 'noun', 'C2', 'cat1_safety_net', 'none', 1, 'Law only sense at C2'),
    ('compose', 'verb', 'B2', 'cat1_safety_net', 'none', 1, 'Music only sense at B2'),
    ('bass', 'noun', 'C2', 'cat1_safety_net', 'none', 1, 'Music only sense at C2'),
    ('choir', 'noun', 'B2', 'cat1_safety_net', 'none', 1, 'Music only sense at B2'),

    # === Category 2: 3+ senses, 2 distinct domains ===
    ('court', 'noun', 'B1', 'cat2_distinct', '|', 2, 'Law + Sports distinct'),
    ('note', 'noun', 'B1', 'cat2_distinct', '|', 2, 'Comment + Money'),
    ('record', 'verb', 'A2', 'cat2_distinct', '|', 2, 'Write + Perform music'),
    ('pitch', 'verb', 'C2', 'cat2_distinct', '|', 2, 'Sports + Transport'),
    ('figure', 'noun', 'B2', 'cat2_distinct', '|', 2, 'Person + Drawing'),

    # === Category 3: 3+ senses, near-synonyms ===
    ('arrange', 'verb', 'A2', 'cat3_near_syn', ';', 2, 'Plan + put-in-order; drop music'),
    ('handle', 'verb', 'B2', 'cat3_near_syn', ';', 2, 'Deal with + control'),
    ('control', 'noun', 'A2', 'cat3_near_syn', ';', 1, '4 senses all related (power)'),
    ('use', 'verb', 'A1', 'cat3_near_syn', ';', 2, 'Multiple uses variants'),
    ('change', 'verb', 'A2', 'cat3_near_syn', ';', 2, 'Multiple uses variants'),

    # === Category 4: multi-POS ===
    ('address', 'noun', 'A1', 'cat4_multi_pos', ';', 1, 'Multi-POS noun: location'),
    ('appeal', 'noun', 'B2', 'cat4_multi_pos', ';', 1, 'Multi-POS noun: request'),
    ('progress', 'noun', 'A2', 'cat4_multi_pos', ';', 1, 'Multi-POS noun: movement'),
    ('arm', 'noun', 'C1', 'cat4_multi_pos', ';', 1, 'Multi-POS noun: body part'),
    ('alert', 'noun', 'C1', 'cat4_multi_pos', ';', 1, 'Multi-POS noun+adj+verb'),

    # === Category 7: ambiguous middle ground (3 candidates test "could go either way") ===
    # These test whether M3 can distinguish "distinct domains" from "variants" in the
    # grey zone. Expected `|` (we want M3 to identify the truly distinct senses and
    # collapse variants), but M3 may legitimately produce `;` — that's still a pass
    # as long as it's a coherent judgment, not a confused mixed output.
    ('pitch', 'verb', 'C2', 'cat7_ambiguous', '|', 2, 'Sports×2 variants + 1 transport + 1 holiday; M3 should pick 1 sport + 1 non-sport'),
    ('figure', 'noun', 'B2', 'cat7_ambiguous', '|', 2, 'Person + body shape + drawing; M3 should drop body shape as variant'),
    ('appeal', 'noun', 'B2', 'cat7_ambiguous', '|', 2, 'Request + attractive + legal; M3 should pick request+legal, drop attractive'),
]


def load_jsonl_records():
    """Load oxford_merged.jsonl, indexed by (word, pos, cefr) → list of def texts."""
    by_key = {}
    for line in JSONL_PATH.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get('_skip'):
            continue
        word = r.get('word', '').lower()
        for pd in r.get('pos_data', []):
            pos = pd.get('pos', '')
            for d in pd.get('definitions', []):
                cefr = d.get('cefr')
                if not cefr:
                    continue
                key = (word, pos, cefr)
                by_key.setdefault(key, []).append(d.get('text', ''))
    return by_key


def load_jobs_by_key():
    """Load gloss_jobs.jsonl, indexed by (word, pos, cefr) → def text (the actual M3 input)."""
    by_key = {}
    for line in JOBS_PATH.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        j = json.loads(line)
        key = (j['word'].lower(), j['pos'], j['cefr'])
        by_key[key] = j.get('def', '')
    return by_key


def load_verdicts():
    """Load gloss_all_verdicts.json, return list of verdict dicts."""
    data = json.loads(VERDICTS_PATH.read_text(encoding='utf-8'))
    return data.get('verdicts', [])


def join_defs(defs):
    """Join multiple def texts with ' ; ' (Oxford convention)."""
    return ' ; '.join(d for d in defs if d.strip())


def pick_from_verdicts(verdicts, category, n=5, valid_cefrs=None):
    """Pick n existing verdicts matching category (concrete/abstract).

    valid_cefrs: optional set of acceptable CEFR levels (excludes UNCLASSIFIED).
    """
    matches = [v for v in verdicts
               if v.get('category') == category
               and v.get('decision') == 'gloss'
               and (valid_cefrs is None or v.get('cefr') in valid_cefrs)]
    # Sort by word for determinism
    matches.sort(key=lambda v: (v.get('word', ''), v.get('pos', ''), v.get('cefr', '')))
    # Pick evenly distributed (every k-th)
    step = max(1, len(matches) // n)
    picked = matches[::step][:n]
    return picked


def main():
    jsonl_by_key = load_jsonl_records()
    jobs_by_key = load_jobs_by_key()
    verdicts = load_verdicts()

    out_records = []

    # Cat 1-4 from hardcoded
    for word, pos, cefr, cat, exp_sep, exp_count, notes in HARD_CODED:
        key = (word.lower(), pos, cefr)
        # Prefer jobs file (exact M3 input); fall back to jsonl
        def_text = jobs_by_key.get(key)
        sense_count = 0
        if def_text:
            sense_count = def_text.count(' ; ') + 1
        else:
            defs = jsonl_by_key.get(key, [])
            if not defs:
                print(f'  WARN: no def for {key}')
                continue
            def_text = join_defs(defs)
            sense_count = len(defs)
        out_records.append({
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'def': def_text,
            'sense_count': sense_count,
            'category': cat,
            'expected_separator': exp_sep,
            'expected_gloss_count': exp_count,
            'notes': notes,
        })

    # Cat 5: abstract from existing verdicts (filter to valid CEFRs only)
    valid_cefrs = {'A1', 'A2', 'B1', 'B2', 'C1', 'C2'}
    abstract_verdicts = pick_from_verdicts(verdicts, 'abstract', 5, valid_cefrs=valid_cefrs)
    for v in abstract_verdicts:
        word = v['word']
        pos = v['pos']
        cefr = v['cefr']
        key = (word.lower(), pos, cefr)
        def_text = jobs_by_key.get(key)
        sense_count = 0
        if def_text:
            sense_count = def_text.count(' ; ') + 1
        else:
            defs = jsonl_by_key.get(key, [])
            if not defs:
                print(f'  WARN: no def for {key} (abstract)')
                continue
            def_text = join_defs(defs)
            sense_count = len(defs)
        out_records.append({
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'def': def_text,
            'sense_count': sense_count,
            'category': 'cat5_abstract',
            'expected_separator': 'none',
            'expected_gloss_count': 1,
            'notes': f'Abstract existing-gloss={v.get("gloss", "")[:30]}',
        })

    # Cat 6: concrete (control) from existing verdicts (filter to valid CEFRs only)
    concrete_verdicts = pick_from_verdicts(verdicts, 'concrete', 5, valid_cefrs=valid_cefrs)
    for v in concrete_verdicts:
        word = v['word']
        pos = v['pos']
        cefr = v['cefr']
        key = (word.lower(), pos, cefr)
        def_text = jobs_by_key.get(key)
        sense_count = 0
        if def_text:
            sense_count = def_text.count(' ; ') + 1
        else:
            defs = jsonl_by_key.get(key, [])
            if not defs:
                print(f'  WARN: no def for {key} (concrete)')
                continue
            def_text = join_defs(defs)
            sense_count = len(defs)
        out_records.append({
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'def': def_text,
            'sense_count': sense_count,
            'category': 'cat6_concrete',
            'expected_separator': 'none',
            'expected_gloss_count': 1,
            'notes': f'Concrete control existing-gloss={v.get("gloss", "")[:30]}',
        })

    # Write output
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open('w', encoding='utf-8') as f:
        for r in out_records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'Wrote {len(out_records)} pilot jobs to {OUT_PATH}')

    # Print summary by category
    by_cat = {}
    for r in out_records:
        by_cat.setdefault(r['category'], []).append(r)
    for cat, recs in sorted(by_cat.items()):
        print(f'\n  {cat} ({len(recs)}):')
        for r in recs:
            print(f'    {r["word"]:15} {r["pos"]:8} {r["cefr"]:4} ({r["sense_count"]} senses) — {r["notes"][:50]}')


if __name__ == '__main__':
    main()
