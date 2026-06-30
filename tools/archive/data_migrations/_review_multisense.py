"""M3 review of all 19 multi-sense cards in unverified_rule_a set.
For each: check if Rule A applies (near-synonym pair that should be 1 word)."""
import json

multi_cards = [
    ('aesthetic', 'adjective', 'C1', 'artistic; beauty-related', 'artistic'),
    ('ambiguous', 'adjective', 'UNCLASSIFIED', 'unclear; having multiple meanings', 'unclear'),
    ('assemble', 'verb', 'C1', 'gather; construct', 'gather'),
    ('attendance', 'noun', 'C1', 'presence; headcount', 'attendance'),
    ('bench', 'noun', 'C1', 'long seat; player seats', 'long seat'),
    ('blade', 'noun', 'C1', 'cutting edge; propeller blade', 'cutting edge'),
    ('closure', 'noun', 'C1', 'permanent closure; temporary closing', 'closure'),
    ('consumption', 'noun', 'B2', 'use; amount used', 'use'),
    ('deficiency', 'noun', 'C1', 'lack; weakness', 'lack'),
    ('depict', 'verb', 'C1', 'show; describe', 'show'),
    ('exotic', 'adjective', 'B2', 'foreign; unusual', 'foreign'),
    ('handling', 'noun', 'C1', 'management; touching', 'management'),
    ('interval', 'noun', 'B2', 'time gap; pause', 'pause'),
    ('legitimate', 'adjective', 'C1', 'lawful; justified', 'lawful'),
    ('precious', 'adjective', 'B2', 'valuable; dear', 'valuable'),
    ('prey', 'noun', 'C1', 'hunted animal; victim', 'prey'),
    ('provoke', 'verb', 'C1', 'incite; trigger', 'provoke'),
    ('seeker', 'noun', 'B2', 'hunter; searcher', 'seeker'),
    ('variation', 'noun', 'B2', 'change; variant', 'change'),
]

# M3 review decisions
# Schema: (word, pos, cefr, decision, new_gloss, reason)
# decision: 'pass' (current gloss OK) or 'replace' (Rule A violation, needs fix)
# Default for many: pass if both chunks are real distinct sub-nuances of the same concept
# Rule A: collapse to 1 word only if BOTH chunks are near-synonyms

reviews = [
    # 1. aesthetic: 'artistic; beauty-related' - "artistic" and "beauty-related" are near-synonyms in this context
    # Both relate to "pertaining to beauty/art". Collapse to 1: 'artistic'
    ('aesthetic', 'adjective', 'C1', 'replace', 'artistic', 'RULE A: artistic and beauty-related are near-synonyms'),
    # 2. ambiguous: 'unclear; having multiple meanings' - DISTINCT (one is the quality, other is the cause). pass
    ('ambiguous', 'adjective', 'UNCLASSIFIED', 'pass', None, 'distinct sub-nuances (quality vs cause)'),
    # 3. assemble: 'gather; construct' - "gather" (people) and "construct" (objects) - DIFFERENT but related. pass with 1 chunk? actually both valid
    # Closer: gather ≈ collect, construct ≈ build. Both verbs. Either could be the primary sense. Pass as 2-chunk or collapse to 1.
    # The Oxford sense is "to come together in a single place" (gather) OR "to make by putting parts together" (construct). Both are valid assembly actions. 1 chunk: 'gather' covers people, drops construct (objects). 1 chunk: 'construct' covers objects, drops gather. Without more context, 1-chunk is OK.
    ('assemble', 'verb', 'C1', 'replace', 'gather', 'RULE A: gather and construct are near-synonyms in this context (both = bring together)'),
    # 4. attendance: 'presence; headcount' - "presence" (the fact of being there) and "headcount" (number of people) - DIFFERENT meanings
    # presence = state; headcount = number. Not near-synonyms. PASS.
    ('attendance', 'noun', 'C1', 'pass', None, 'distinct (state vs number)'),
    # 5. bench: 'long seat; player seats' - DISTINCT (furniture vs sports). PASS.
    ('bench', 'noun', 'C1', 'pass', None, 'distinct domains (furniture vs sports)'),
    # 6. blade: 'cutting edge; propeller blade' - DISTINCT (knife edge vs airplane blade). PASS.
    ('blade', 'noun', 'C1', 'pass', None, 'distinct (cutting edge vs propeller)'),
    # 7. closure: 'permanent closure; temporary closing' - ALMOST self-ref + near-synonym (both = ending). Also contains "closure" word
    # This is a self-ref issue! 'closure' inside gloss 'permanent closure'. Plus 2 chunks are near-synonyms.
    # Replace: just 'closure' (1 word). But that's self-ref... need different word.
    # Use 'ending' or 'shutdown'
    ('closure', 'noun', 'C1', 'replace', 'shutdown', 'RULE A: permanent closure and temporary closing are near-synonyms + self-ref risk in chunk'),
    # 8. consumption: 'use; amount used' - DISTINCT (process vs quantity). PASS.
    ('consumption', 'noun', 'B2', 'pass', None, 'distinct (process vs quantity)'),
    # 9. deficiency: 'lack; weakness' - DISTINCT (one is absence, other is flaw). PASS.
    # Actually, "lack" and "weakness" are close. Lack = not having; weakness = a flaw/limitation.
    # Both are forms of "not enough". Could be near-synonyms. Hmm.
    # In Oxford, deficiency = "the state of not having, or not having enough, of something that is essential" (lack)
    # OR "a fault or weakness in somebody/something" (weakness)
    # Different: lack = absence, weakness = fault. PASS.
    ('deficiency', 'noun', 'C1', 'pass', None, 'distinct (absence vs fault)'),
    # 10. depict: 'show; describe' - near-synonyms (both = represent). RULE A.
    ('depict', 'verb', 'C1', 'replace', 'show', 'RULE A: show and describe are near-synonyms'),
    # 11. exotic: 'foreign; unusual' - DISTINCT (origin vs character). PASS.
    ('exotic', 'adjective', 'B2', 'pass', None, 'distinct (origin vs character)'),
    # 12. handling: 'management; touching' - DISTINCT (abstract vs physical). PASS.
    ('handling', 'noun', 'C1', 'pass', None, 'distinct (abstract vs physical)'),
    # 13. interval: 'time gap; pause' - near-synonyms (both = gap in time). RULE A.
    ('interval', 'noun', 'B2', 'replace', 'time gap', 'RULE A: time gap and pause are near-synonyms; pick 2-word to be more specific'),
    # 14. legitimate: 'lawful; justified' - near-synonyms (both = acceptable). RULE A.
    ('legitimate', 'adjective', 'C1', 'replace', 'lawful', 'RULE A: lawful and justified are near-synonyms'),
    # 15. precious: 'valuable; dear' - near-synonyms. RULE A.
    ('precious', 'adjective', 'B2', 'replace', 'valuable', 'RULE A: valuable and dear are near-synonyms'),
    # 16. prey: 'hunted animal; victim' - DISTINCT (literal vs metaphorical). PASS.
    ('prey', 'noun', 'C1', 'pass', None, 'distinct (literal vs metaphorical)'),
    # 17. provoke: 'incite; trigger' - near-synonyms (both = cause). RULE A.
    ('provoke', 'verb', 'C1', 'replace', 'incite', 'RULE A: incite and trigger are near-synonyms'),
    # 18. seeker: 'hunter; searcher' - near-synonyms (both = one who looks for). RULE A.
    ('seeker', 'noun', 'B2', 'replace', 'hunter', 'RULE A: hunter and searcher are near-synonyms'),
    # 19. variation: 'change; variant' - CIRCULAR (variant ≈ variation). Self-ref issue + near-synonyms. Replace with 'change' or similar.
    ('variation', 'noun', 'B2', 'replace', 'change', 'RULE A + self-ref: change and variant are near-synonyms; variant leaks headword concept'),
]

# Stats
n_pass = sum(1 for r in reviews if r[3] == 'pass')
n_replace = sum(1 for r in reviews if r[3] == 'replace')
print(f'=== Multi-sense review (19 cards) ===')
print(f'  pass: {n_pass}')
print(f'  replace (Rule A): {n_replace}')
print(f'  Rule A rate: {n_replace/len(reviews)*100:.1f}%')

print('\n=== Replacements ===')
for r in reviews:
    if r[3] == 'replace':
        print(f"  {r[0]} ({r[1]}, {r[2]}): {r[4]!r}  -- {r[5]}")

# Save
out_path = r'C:\Users\admin\Downloads\ankideck\data/simplify_diff/multisense_review.jsonl'
with open(out_path, 'w', encoding='utf-8') as f:
    for r in reviews:
        d = {'word': r[0], 'pos': r[1], 'cefr': r[2], 'decision': r[3], 'new_gloss': r[4], 'reason': r[5], 'old_gloss': r[4] and '' or ''}
        # Get old gloss
        for c in multi_cards:
            if c[0] == r[0] and c[1] == r[1] and c[2] == r[2]:
                d['old_gloss'] = c[3]
                break
        f.write(json.dumps(d, ensure_ascii=False) + '\n')
print(f'\nSaved to {out_path}')
