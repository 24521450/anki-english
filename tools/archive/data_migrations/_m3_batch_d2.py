"""M3 batch D2: 12 verdicts for jobs 13-24."""
import json
import sys as _sys
import importlib.util as u

# Load module
spec = u.spec_from_file_location('gloss_llm', r'C:\Users\admin\Downloads\ankideck\src\deck_builder\gloss_llm.py')
mod = u.module_from_spec(spec)
_sys.modules['gloss_llm'] = mod
spec.loader.exec_module(mod)

verdicts = [
    # 13. logistical (adjective) - def: "Relating to the careful organization of a complicated activity"
    {
        'word': 'logistical', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'organizational', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept'
    },
    # 14. ligaments (noun) - def: "a strong band of tissue in the body" - POS MISMATCH (def is singular)
    {
        'word': 'ligaments', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'connecting tissue', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def singular); gloss matches plural word'
    },
    # 15. vertebrae (noun) - def: "The small bones that form the spine" - POS MISMATCH (def is plural explanation)
    {
        'word': 'vertebrae', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'spine bones', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def plural-form); gloss = spine bones'
    },
    # 16. foraging (noun) - def: "food for horses and cows" - this is for "forage" (noun), not "foraging" (gerund)
    # For "foraging" (gerund, looking for food): "searching for food"
    {
        'word': 'foraging', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'searching for food', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def is for forage noun); gloss follows gerund meaning'
    },
    # 17. designated (adjective) - def: "chosen to do a job but not yet having officially started it"
    # POS MISMATCH: def is for "designate" (noun = "director-designate"). Card says adjective.
    # "designated" (adjective, "officially chosen") - gloss: "officially chosen"
    {
        'word': 'designated', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'officially chosen', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def for designate noun); gloss follows adj meaning'
    },
    # 18. interweave (verb) - def: "twisted together or connected closely" - this is a past-participle-style definition
    # For "interweave" (verb, "to twist together"): "twist together" or "intertwine"
    {
        'word': 'interweave', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'intertwine', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def is adj-form); gloss = verb meaning'
    },
    # 19. gouging (noun) - def: "a sharp tool" - this is for "gouge" (noun, the tool). Card says "gouging" (gerund).
    # "gouging" (act of gouging) - gloss: "scraping out" (act) OR "price gouging" (specific sense)
    # The ex says "price gouging" - specific sense. Gloss: "overcharging" (matches the price-gouging sense)
    {
        'word': 'gouging', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'overcharging', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH (def for gouge noun tool); gloss follows ex (price gouging sense)'
    },
    # 20. shunned (verb) - def: "persistently avoided, ignored, or rejected" - this is past-participle
    # For "shunned" (past tense verb): "avoided persistently" or "rejected"
    {
        'word': 'shunned', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'rejected', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'past tense form, gloss = past participle'
    },
    # 21. dabbler (noun) - def: "a person who follows a pursuit without serious commitment or knowledge"
    {
        'word': 'dabbler', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'amateur', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '1 sense, 1 concept'
    },
    # 22. zigzagging (verb) - def: "moving by going from side to side, or changing direction frequently"
    {
        'word': 'zigzagging', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'changing direction', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'present participle, 1 concept'
    },
    # 23. shortsighted (adjective) - def: "lacking imagination or foresight"
    {
        'word': 'shortsighted', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'lacking foresight', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept'
    },
    # 24. untethered (adjective) - def: "not tied or limited to a particular thing"
    {
        'word': 'untethered', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'unrestricted', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': '1 sense, 1 concept'
    },
]

# Save
out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_batch_D2.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(verdicts, f, indent=2, ensure_ascii=False)
print(f'Wrote {len(verdicts)} verdicts to {out_path}')

# Validate
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
