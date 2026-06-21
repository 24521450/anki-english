"""M3 spot-audit batch B1: review 25 cards (idx 0-24)."""
import json
import sys as _sys
import importlib.util as u

# Load module for gate
spec = u.spec_from_file_location('gloss_llm', r'C:\Users\admin\Downloads\ankideck\src\deck_builder\gloss_llm.py')
mod = u.module_from_spec(spec)
_sys.modules['gloss_llm'] = mod
spec.loader.exec_module(mod)

# Load sample
samples = [json.loads(l) for l in open(r'C:\Users\admin\Downloads\ankideck/data/simplify_diff/spot_audit_sample.jsonl', encoding='utf-8')]

# M3 review decisions for samples[0:25]
# Schema: {sample_idx, decision: 'pass'|'replace', new_gloss?: str, reason: str}
reviews = [
    # 0. absorb: def "to take in a substance or a form of energy", gloss "take in" — pass
    {'sample_idx': 0, 'decision': 'pass', 'reason': 'def 1 sense, gloss covers it'},
    # 1. accidentally: def "by chance; in a way that was not planned", gloss "by chance" — pass
    {'sample_idx': 1, 'decision': 'pass', 'reason': 'def has 2 near-synonym chunks, gloss collapsed to 1 (Rule A applied)'},
    # 2. activist: def "a person who works to achieve political or social change", gloss "change advocate" — pass
    {'sample_idx': 2, 'decision': 'pass', 'reason': 'def 1 sense, gloss is concise'},
    # 3. additionally: def "in a way that is more than was first mentioned or is usual", gloss "moreover" — pass
    {'sample_idx': 3, 'decision': 'pass', 'reason': 'def 1 sense, gloss is a single word synonym'},
    # 4. adequately: def "in a way that is enough in quantity, or good enough in quality", gloss "sufficiently" — pass
    {'sample_idx': 4, 'decision': 'pass', 'reason': 'def 1 sense, gloss is a single word synonym'},
    # 5. advocate: def "to support or recommend something publicly; a person who does this"
    # gloss not shown yet, let me check
    # 6. aerial: def "existing, happening or operating in the air" - gloss
    # 7. albeit: def "although" - gloss
    # 8. alien: def
    # 9. ambiguous
    # 10. amplify
    # 11. analogy
    # 12. animate
    # 13. anonymous
    # 14. appeal
    # 15. applaud
    # 16. appreciate
    # 17. approach
    # 18. approval
    # 19. approximately
    # 20. arbitrate
    # 21. assertion
    # 22. assumption
    # 23. atom
    # 24. attentive
]

# Need to look at remaining samples 5-24
# Let me get them and add reviews
for s in samples[5:25]:
    print(f'[{s["sample_idx"]}] {s["word"]} ({s["pos"]}, {s["cefr"]})')
    print(f'    def: {s["def_before"][:120]}')
    print(f'    gloss: {s["gloss_after"]!r} [sep={s.get("separator")}, rule={s.get("rule_applied")}]')
    print()
