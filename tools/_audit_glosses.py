"""Audit M3_VERDICTS dict for data-quality bugs."""
import importlib.util

spec = importlib.util.spec_from_file_location('m3v2', r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Get all rules + their verdicts
from collections import defaultdict
by_rule = defaultdict(list)
for key, (gloss, sep, count, rule) in mod.M3_VERDICTS.items():
    by_rule[rule].append((key, gloss, sep, count))

# Audit 1: self-referential glosses (gloss word contains the headword)
self_ref_exact = []  # gloss equals word exactly
self_ref_contains = []  # gloss contains headword
for key, (gloss, sep, count, rule) in mod.M3_VERDICTS.items():
    word = key.split('|')[0].lower()
    gloss_lower = gloss.lower().strip()
    if sep == 'none' and gloss_lower == word:
        self_ref_exact.append((key, gloss))
    elif word in gloss_lower.split():
        self_ref_contains.append((key, gloss))

# Audit 2: Rule A violations for pick1 (multi-sense-3+ with all variants, but gloss = headword)
pick1_total = len(by_rule.get('rule_b_pick1', []))
pick1_self_ref = sum(1 for key, gloss, sep, count in by_rule['rule_b_pick1']
                     if gloss.lower().strip() == key.split('|')[0].lower())

# Audit 3: same-domain 2-sense verdicts with same word appearing
same_domain_self_ref = []
for key, (gloss, sep, count, rule) in mod.M3_VERDICTS.items():
    if rule != '2sense_samedomain':
        continue
    word = key.split('|')[0].lower()
    chunks = [c.strip().lower() for c in gloss.split(';')]
    if word in chunks:
        same_domain_self_ref.append((key, gloss))

# Audit 4: dead import check
import inspect
src = open(r'C:\Users\admin\Downloads\ankideck\tools\_m3_rerun_v2.py', encoding='utf-8').read()
glossverdict_used = 'GlossVerdict' in src.split('def main')[0] or 'GlossVerdict' in src.split('def main')[1]
# print(f'GlossVerdict used anywhere? {glossverdict_used}')

print('=== SELF-REFERENTIAL GLOSSES (gloss equals headword) ===')
print(f'Total exact self-ref: {len(self_ref_exact)}/{len(mod.M3_VERDICTS)} ({100*len(self_ref_exact)/len(mod.M3_VERDICTS):.1f}%)')
print(f'  in rule_b_pick1: {pick1_self_ref}/{pick1_total} ({100*pick1_self_ref/pick1_total:.1f}% of pick1)')
print(f'Total self-ref contains word: {len(self_ref_contains)}/{len(mod.M3_VERDICTS)}')

print('\n=== Same-domain with headword in chunks ===')
print(f'Total: {len(same_domain_self_ref)}')
for k, g in same_domain_self_ref[:5]:
    print(f'  {k}: {g!r}')

print('\n=== Sample self-ref exact (first 15) ===')
for k, g in self_ref_exact[:15]:
    print(f'  {k}: {g!r}')

print('\n=== Rule breakdown ===')
for rule in sorted(by_rule.keys()):
    print(f'  {rule}: {len(by_rule[rule])}')

# Audit 5: Word count violations
print('\n=== Word count audit ===')
wc_violations = []
for key, (gloss, sep, count, rule) in mod.M3_VERDICTS.items():
    chunks = gloss.split('|') if sep == '|' else gloss.split(';') if sep == ';' else [gloss]
    for c in chunks:
        wc = len(c.strip().split())
        if wc > 6:
            wc_violations.append((key, c, wc))
print(f'Chunks >6 words: {len(wc_violations)}/{sum(len(v[0].split("|") if v[1]=="|" else v[0].split(";") if v[1]==";" else [v[0]]) for v in mod.M3_VERDICTS.values())}')