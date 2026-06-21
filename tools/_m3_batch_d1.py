"""M3 batch D1: 12 verdicts for cards 1-12 of streamD jobs."""
import json
import sys

# Load batch jobs
jobs = []
with open(r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_jobs_streamD.jsonl', encoding='utf-8') as f:
    for l in f:
        jobs.append(json.loads(l))

# M3 verdicts for jobs[0:12]
# Schema: (word, pos, cefr, gloss, separator, count, rule_applied, decision, category, reasoning)
verdicts = [
    # 1. evolved (verb, past participle) - def: "to develop gradually"
    # Gloss should be past-participle form: "developed" | rule: concrete_1sense
    {
        'word': 'evolved', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'developed', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'past participle, gloss matches inflected form'
    },
    # 2. hyperfocus (verb) - def: "to concentrate on sth very intensely"
    # Gloss: "concentrate intensely" (2 words) | rule: concrete_1sense
    {
        'word': 'hyperfocus', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'concentrate intensely', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'compound verb, 1 concept'
    },
    # 3. hallucination (noun, UNCLASSIFIED) - def: "the fact of seeming to see or hear"
    # Earlier session: Oxford 2024 added AI sense, removed; 2 medical senses survive
    # Card here is UNCLASSIFIED - the medical meaning | gloss: "perceiving what is not there" (5 words) | rule: concrete_1sense
    {
        'word': 'hallucination', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'perceiving what is not there', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'medical meaning (UNCLASSIFIED); AI sense excluded from this card'
    },
    # 4. soullessly (POS=verb but def is adverb) - def: "in a way that shows no human influence"
    # POS MISMATCH: def is for "soullessly" (adverb), card labeled as "verb" (likely data error)
    # Gloss: "without soul" (matches adverb meaning) | rule: concrete_1sense
    {
        'word': 'soullessly', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'without soul', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'abstract', 'reasoning': 'POS mismatch (def is adverb form); gloss matches meaning'
    },
    # 5. extrapolated (verb, past tense) - def: "to estimate"
    # Gloss: "estimated" (past tense form) | rule: concrete_1sense
    {
        'word': 'extrapolated', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'estimated from data', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'past tense, gloss matches inflected form'
    },
    # 6. harbor (verb) - def: "to contain sth, especially sth hidden or dangerous"
    # Gloss: "shelter secretly" (2 words) | rule: concrete_1sense
    {
        'word': 'harbor', 'pos': 'verb', 'cefr': 'UNCLASSIFIED',
        'gloss': 'shelter secretly', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '1 sense, 1 concept'
    },
    # 7. unfiltered (adjective) - def: "not having had anything removed or changed"
    # Gloss: "unprocessed" | rule: concrete_1sense
    {
        'word': 'unfiltered', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'unprocessed', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '1 sense, 1 concept'
    },
    # 8. carrying capacity (noun) - def: "max number of people/animals a particular area can support"
    # Gloss: "max supportable population" | rule: concrete_1sense
    {
        'word': 'carrying capacity', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'max supportable population', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'compound noun, 1 concept'
    },
    # 9. blink of an eye (idiom) - def: "extremely quickly"
    # Gloss: "instantly" | rule: concrete_1sense
    {
        'word': 'blink of an eye', 'pos': 'idiom', 'cefr': 'UNCLASSIFIED',
        'gloss': 'instantly', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'idiom, 1 concept'
    },
    # 10. harbor (noun) - def: "To contain or keep sth/sb within"
    # Gloss: "shelter" | rule: concrete_1sense
    {
        'word': 'harbor', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'shelter', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': '1 sense, 1 concept'
    },
    # 11. curated (adjective) - def is for "curate" (noun) - POS MISMATCH
    # Card is "curated" (adjective, "carefully selected"), def is "assistant to a vicar" (curate noun)
    # Gloss for "curated" (adjective): "carefully selected" | rule: concrete_1sense
    {
        'word': 'curated', 'pos': 'adjective', 'cefr': 'UNCLASSIFIED',
        'gloss': 'carefully selected', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS MISMATCH in source def (curate noun vs curated adj); gloss follows word-as-labeled'
    },
    # 12. relay (noun) - def mixes 2 senses: "device that receives a signal" + "to pass sth along"
    # POS is noun, so gloss should focus on noun meaning. But def has both. Pick 1 most common: "pass along"
    # Actually, POS=noun suggests the "device" sense. Let me use "signal transmitter" (2 words)
    {
        'word': 'relay', 'pos': 'noun', 'cefr': 'UNCLASSIFIED',
        'gloss': 'signal transmitter', 'separator': 'none', 'count': 1,
        'rule_applied': 'concrete_1sense', 'decision': 'gloss',
        'category': 'concrete', 'reasoning': 'POS=noun, def has 2 senses (device + act); picked device sense, dropped verb-passing sense'
    },
]

# Save to batch file
out_path = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\gloss_batch_D1.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(verdicts, f, indent=2, ensure_ascii=False)
print(f'Wrote {len(verdicts)} verdicts to {out_path}')

# Validate via gate
import importlib.util as u
import sys as _sys
spec = u.spec_from_file_location('gloss_llm', r'C:\Users\admin\Downloads\ankideck\src\deck_builder\gloss_llm.py')
mod = u.module_from_spec(spec)
_sys.modules['gloss_llm'] = mod  # register so dataclass __post_init__ can find it
spec.loader.exec_module(mod)

violations = []
for v in verdicts:
    word = v['word']
    gloss = v['gloss']
    sep = v['separator']
    count = v['count']
    bad = mod.validate_verdict(word, gloss, sep, count)
    if bad:
        violations.append((word, bad))
        print(f'  VIOLATION: {word}: {bad}')
    else:
        wc = len(gloss.split())
        print(f'  OK: {word}: "{gloss}" [{sep}/{count}/{v["rule_applied"]}] wc={wc}')

if violations:
    print(f'\n{len(violations)}/{len(verdicts)} violations - fix before appending')
    sys.exit(1)
else:
    print(f'\n{len(verdicts)}/{len(verdicts)} PASS')
