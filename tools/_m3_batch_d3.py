"""M3 batch D3: 12 verdicts for jobs 25-36."""
import json
import sys as _sys
import importlib.util as u

spec = u.spec_from_file_location('gloss_llm', r'C:\Users\admin\Downloads\ankideck\src\deck_builder\gloss_llm.py')
mod = u.module_from_spec(spec)
_sys.modules['gloss_llm'] = mod
spec.loader.exec_module(mod)

verdicts = [
    # 25. destabilizing (verb) - def: "to make a system, country, government, etc. become less well established or successful"
    {
        'word': 'destabilizing', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'undermining', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'present participle, 1 concept'
    },
    # 26. randomized (adjective) - def: "to use a method in an experiment" - POS MISMATCH (def is verb "randomize")
    # Card is "randomized" (adjective, "made random"). Gloss: "made random"
    {
        'word': 'randomized', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'made random', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def is verb); gloss follows adj meaning'
    },
    # 27. have the floor (phrase) - def: "To have the right to speak at a public meeting or in a debate"
    {
        'word': 'have the floor', 'pos': 'phrase', 'cefr': 'UNCLASSIFIED',
        'gloss': 'have speaking turn', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'phrase, 1 concept'
    },
    # 28. consist (verb, B1) - def: "To be sth that is made or formed of various specific things"
    {
        'word': 'consist', 'pos': 'verb', 'cefr': 'B1',
        'gloss': 'be made of', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept'
    },
    # 29. behalf (noun, C1) - def: "in order to help sb|as the representative of sb or instead of them"
    {
        'word': 'behalf', 'pos': 'noun', 'cefr': 'C1',
        'gloss': 'on behalf of', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept; usually "on behalf of"'
    },
    # 30. criteria (noun) - def: "standards by which sth is judged, decided, or graded"
    {
        'word': 'criteria', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'standards', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept (plural of criterion)'
    },
    # 31. accordance (noun, C1) - def: "according to a rule or the way that sb says that sth should be done"
    {
        'word': 'accordance', 'pos': 'noun', 'cefr': 'C1',
        'gloss': 'agreement', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept'
    },
    # 32. accused (noun, C1) - def: "to say that sb has done sth wrong or is guilty of sth" - POS MISMATCH (def is verb "accuse")
    # Card is "accused" (noun, "person accused"). Gloss: "defendant"
    {
        'word': 'accused', 'pos': 'noun', 'cefr': 'C1',
        'gloss': 'defendant', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def is verb accuse); gloss = noun meaning'
    },
    # 33. AIDS (noun, B2) - def: "HIV disease"
    {
        'word': 'AIDS', 'pos': 'noun', 'cefr': 'B2',
        'gloss': 'HIV disease', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '1 sense, 1 concept'
    },
    # 34. counter (long flat surface) (noun, B2) - def: "service counter"
    {
        'word': 'counter (long flat surface)', 'pos': 'noun', 'cefr': 'B2',
        'gloss': 'service desk', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS has disambiguator (long flat surface); gloss matches'
    },
    # 35. counter (argue against) (verb, C1) - def: "reply proving wrong; reduce bad effects"
    {
        'word': 'counter (argue against)', 'pos': 'verb', 'cefr': 'C1',
        'gloss': 'oppose', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'POS has disambiguator (argue against); gloss = oppose'
    },
    # 36. grave (for dead person) (noun, C1) - def: "burial site"
    {
        'word': 'grave (for dead person)', 'pos': 'noun', 'cefr': 'C1',
        'gloss': 'burial site', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS has disambiguator (for dead person); gloss = burial site'
    },
]

out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_batch_D3.json'
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
