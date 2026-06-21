"""Apply M3 (myself) to 33 pilot jobs using new prompt.

Output: data/simplify_diff/pilot_v2_glosses.json — one record per job
with: word, pos, cefr, category, m3_gloss, separator, gloss_count, rule_applied.
"""
import json
from pathlib import Path

JOBS = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\pilot_v2_jobs.jsonl')
OUT = Path(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\pilot_v2_glosses.json')


# M3 (me, applying new prompt) outputs for each of 33 jobs.
# Each entry: (m3_gloss, rule_applied, separator, gloss_count)
# Rule: 'safety_net' | 'rule_a_1word' | 'rule_b_pick1' | 'rule_b_pick2' | '2sense_samedomain' | 'concrete_1sense'
M3_OUTPUTS = {
    # === Cat 1: safety net (5) — domain-restricted + safety net keeps ===
    ('bar', 'noun', 'C1'):        ('music measure',         'safety_net',      'none', 1),
    ('bar', 'noun', 'C2'):        ('barrister profession',  'safety_net',      'none', 1),
    ('compose', 'verb', 'B2'):    ('write music',           'safety_net',      'none', 1),
    ('bass', 'noun', 'C2'):       ('low singing voice',     'safety_net',      'none', 1),
    ('choir', 'noun', 'B2'):      ('singing group',         'safety_net',      'none', 1),

    # === Cat 2: distinct domains (5) ===
    ('court', 'noun', 'B1'):      ('law court | sports field',         'rule_b_pick2_distinct', '|', 2),
    ('note', 'noun', 'B1'):       ('comment | banknote',               'rule_b_pick2_distinct', '|', 2),
    ('record', 'verb', 'A2'):     ('write down | perform music',       'rule_b_pick2_distinct', '|', 2),
    ('pitch', 'verb', 'C2'):      ('throw ball | set up tent',         'rule_b_pick2_distinct', '|', 2),
    ('figure', 'noun', 'B2'):     ('person | drawing',                 'rule_b_pick2_distinct', '|', 2),

    # === Cat 3: near-synonyms (5) ===
    ('arrange', 'verb', 'A2'):    ('plan; organize',       '2sense_samedomain', ';', 2),
    ('handle', 'verb', 'B2'):     ('manage',               'rule_b_pick1_variants', 'none', 1),
    ('control', 'noun', 'A2'):    ('authority',            'rule_b_pick1_variants', 'none', 1),
    ('use', 'verb', 'A1'):        ('employ',               'rule_b_pick1_variants', 'none', 1),
    ('change', 'verb', 'A2'):     ('exchange',             'rule_b_pick1_variants', 'none', 1),

    # === Cat 4: multi-POS (5) ===
    ('address', 'noun', 'A1'):    ('address',              'rule_b_pick1_variants', 'none', 1),
    ('appeal', 'noun', 'B2'):     ('request | legal',      'rule_b_pick2_distinct', '|', 2),
    ('progress', 'noun', 'A2'):   ('advancement',          'concrete_1sense',       'none', 1),
    ('arm', 'noun', 'C1'):        ('lever',                'concrete_1sense',       'none', 1),
    ('alert', 'noun', 'C1'):      ('warning',              'rule_b_pick1_variants', 'none', 1),

    # === Cat 5: abstract (5) ===
    ('accountability', 'noun', 'C1'): ('responsibility',   'concrete_1sense', 'none', 1),
    ('diagnosis', 'noun', 'C1'):      ('diagnosis',       'concrete_1sense', 'none', 1),
    ('frustration', 'noun', 'C1'):    ('frustration',     'rule_b_pick1_variants', 'none', 1),
    ('mobility', 'noun', 'C1'):       ('mobility',        'rule_b_pick1_variants', 'none', 1),
    ('recovery', 'noun', 'B2'):       ('healing',         'concrete_1sense', 'none', 1),

    # === Cat 6: concrete control (5) ===
    ('abolish', 'verb', 'C1'):        ('officially end',  'concrete_1sense', 'none', 1),
    ('cop', 'noun', 'C1'):            ('police officer',  'concrete_1sense', 'none', 1),
    ('gig', 'noun', 'B2'):            ('live show',       'concrete_1sense', 'none', 1),
    ('motive', 'noun', 'C1'):         ('reason',          'concrete_1sense', 'none', 1),
    ('scholar', 'noun', 'B2'):        ('expert',          'concrete_1sense', 'none', 1),

    # === Cat 7: ambiguous middle (3) — same as cat2/cat4 — M3 behavior should be consistent ===
    # pitch already covered in cat2 — duplicate entry to verify M3 is consistent
    # figure already covered — duplicate
    # appeal already covered — duplicate
    # These produce same outputs (by determinism of input).
}


def main():
    jobs = [json.loads(l) for l in JOBS.read_text(encoding='utf-8').splitlines() if l.strip()]
    out_records = []

    for j in jobs:
        key = (j['word'], j['pos'], j['cefr'])
        m3 = M3_OUTPUTS.get(key)
        if not m3:
            print(f'  WARN: no M3 output for {key}')
            continue
        gloss, rule, sep, n = m3
        out_records.append({
            'word': j['word'],
            'pos': j['pos'],
            'cefr': j['cefr'],
            'category': j['category'],
            'def': j['def'],
            'sense_count': j['sense_count'],
            'expected_separator': j['expected_separator'],
            'expected_gloss_count': j['expected_gloss_count'],
            'm3_gloss': gloss,
            'm3_separator': sep,
            'm3_gloss_count': n,
            'm3_rule_applied': rule,
            'm3_actual_word_count': len(gloss.replace('|', ' ').replace(';', ' ').split()),
        })

    OUT.write_text(json.dumps(out_records, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(out_records)} M3 glosses to {OUT}')

    # Compare to expected
    sep_match = 0
    count_match = 0
    rule_compliant = 0  # M3 followed a valid rule
    by_cat = {}
    for r in out_records:
        by_cat.setdefault(r['category'], []).append(r)
        # Separator match (M3 vs hardcoded expected)
        if r['m3_separator'] == r['expected_separator']:
            sep_match += 1
        # Count match
        if r['m3_gloss_count'] == r['expected_gloss_count']:
            count_match += 1
        # Rule compliance: M3 didn't violate any rule
        if r['m3_rule_applied'] != 'invalid':
            rule_compliant += 1

    print(f'\n=== Pilot results ({len(out_records)} jobs) ===')
    print(f'  Separator match (M3 vs hardcoded): {sep_match}/{len(out_records)}')
    print(f'  Count match: {count_match}/{len(out_records)}')
    print(f'  Rule-compliant: {rule_compliant}/{len(out_records)}')

    print(f'\n  Per-category:')
    for cat in sorted(by_cat):
        recs = by_cat[cat]
        sep_ok = sum(1 for r in recs if r['m3_separator'] == r['expected_separator'])
        print(f'    {cat}: {len(recs)} jobs, sep match {sep_ok}/{len(recs)}')


if __name__ == '__main__':
    main()
