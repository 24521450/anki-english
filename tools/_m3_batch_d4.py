"""M3 batch D4: 10 verdicts for jobs 37-46 (last batch)."""
import json
import sys as _sys
import importlib.util as u

spec = u.spec_from_file_location('gloss_llm', r'C:\Users\admin\Downloads\ankideck\src\deck_builder\gloss_llm.py')
mod = u.module_from_spec(spec)
_sys.modules['gloss_llm'] = mod
spec.loader.exec_module(mod)

verdicts = [
    # 37. ID (noun, B2) - def: "identification"
    {
        'word': 'ID', 'pos': 'noun', 'cefr': 'B2',
        'gloss': 'identification', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '1 sense, 1 concept (abbreviation)'
    },
    # 38. strip (long narrow piece) (noun, C1) - def: "narrow piece"
    {
        'word': 'strip (long narrow piece)', 'pos': 'noun', 'cefr': 'C1',
        'gloss': 'narrow strip', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS has disambiguator (long narrow piece); gloss = narrow strip'
    },
    # 39. strip (remove clothes/a layer) (verb, C1) - def: "remove"
    {
        'word': 'strip (remove clothes/a layer)', 'pos': 'verb', 'cefr': 'C1',
        'gloss': 'remove', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS has disambiguator (remove clothes/a layer); gloss = remove'
    },
    # 40. wellbeing (noun) - def: "general health and happiness"
    {
        'word': 'wellbeing', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'health and happiness', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept'
    },
    # 41. subjective (noun, B2) - def: "based on your own ideas or opinions rather than facts"
    # POS MISMATCH: def is for "subjective" (adjective). Card labeled as noun.
    # "subjective" (as noun, "subjective thing") is rare. The card is likely mislabeled.
    # Gloss follows the meaning: "personal opinion"
    {
        'word': 'subjective', 'pos': 'noun', 'cefr': 'B2',
        'gloss': 'personal opinion', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'POS MISMATCH (def is adj); gloss matches word meaning'
    },
    # 42. hallucination (noun, C2) - def: "the fact of seeming to see or hear"
    # Same medical meaning as #3 (UNCLASSIFIED) - C2 is the CEFR-classified version
    {
        'word': 'hallucination', 'pos': 'noun', 'cefr': 'C2',
        'gloss': 'perceiving what is not there', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'medical meaning (C2 card); AI sense excluded'
    },
    # 43. invading (verb) - def: "to enter a place in large numbers, especially in a way that causes damage or problems"
    {
        'word': 'invading', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'entering by force', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'present participle, 1 concept'
    },
    # 44. eliminated (verb) - def: "to stop considering that sb/sth might be responsible; to defeat a person or team"
    # 2 distinct senses: (1) remove from consideration, (2) defeat in competition
    # Distinct domains (investigative vs competitive) → use '|'
    {
        'word': 'eliminated', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'removed | defeated', 'separator': '|', 'count': 2,
        'rule_applied': '2sense_distinct', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '2 distinct senses (remove from consideration | defeat in competition); different domains'
    },
    # 45. byproducts (noun) - def: "a thing that happens, often unexpectedly, as the result of sth else"
    {
        'word': 'byproducts', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'side effects', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept (result of something else)'
    },
    # 46. grave (serious) (adjective, C1) - def: "serious"
    {
        'word': 'grave (serious)', 'pos': 'adjective', 'cefr': 'C1',
        'gloss': 'serious', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'POS has disambiguator (serious); gloss = serious'
    },
]

out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_batch_D4.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(verdicts, f, indent=2, ensure_ascii=False)
print(f'Wrote {len(verdicts)} verdicts to {out_path}')

violations = []
for v in verdicts:
    bad = mod.validate_verdict(v['word'], v['gloss'], v['separator'], v['count'])
    if bad:
        violations.append((v['word'], bad))
        print(f'  VIOLATION: {v["word"]}: {bad}')
    else:
        wc = len(v['gloss'].split())
        print(f'  OK: {v["word"]}: "{v["gloss"]}" [{v["separator"]}/{v["count"]}/{v["rule_applied"]}] wc={wc}')

if violations:
    print(f'\n{len(violations)}/{len(verdicts)} violations')
    _sys.exit(1)
else:
    print(f'\n{len(verdicts)}/{len(verdicts)} PASS')
