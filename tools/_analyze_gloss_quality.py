"""
Phân tích toàn bộ audit_full_deck.jsonl để tìm các card có khả năng mất nghĩa / gloss không đủ.

Heuristics:
1. MULTI_SENSE_COLLAPSED: def có nhiều nghĩa (|) nhưng gloss là 1 chunk (rule_b_pick1) → risk sense drop
2. SAME_DOMAIN_PAIR_COLLAPSE: def có 2 nghĩa, gloss dùng ';' nhưng 2 chunk quá giống nhau → Rule A violation?
3. SINGLE_WORD_GLOSS: gloss chỉ 1 từ với def phức tạp (>60 chars) → quá cô đọng?
4. GLOSS_TOO_NARROW: def có nhiều qualifier/context nhưng gloss bỏ hết
5. SEPARATOR_MISMATCH_RISK: def dùng '|' (distinct senses) nhưng gloss dùng ';' (same domain) hoặc ngược lại
6. DOMAIN_RESTRICTED_GLOSS: gloss dùng từ kỹ thuật ít phổ biến
7. ADDED_MEANING: gloss chứa từ không xuất hiện ngữ nghĩa trong def_before

Output: data/simplify_diff/quality_issues.json
"""
import json
import re
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
AUDIT_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'audit_full_deck.jsonl'
VERDICTS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gloss_all_verdicts.json'
OUT_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'quality_issues.json'

# ----- Load data -----
records = [json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
verdicts_raw = json.loads(VERDICTS_PATH.read_text(encoding='utf-8'))['verdicts']
verdict_by_key = {(v['word'], v['pos'], v['cefr']): v for v in verdicts_raw}

# Only inspect 'pass' records (gloss was applied)
pass_records = [r for r in records if r['gate_status'] == 'pass' and r.get('gloss_after')]
print(f'Inspecting {len(pass_records)} pass records...')

# ----- Technical/obscure words that may be hard for IELTS learners -----
TECHNICAL_WORDS = {
    'pyrotechnic', 'pyrotechnics', 'carcinogenic', 'stochastic', 'heuristic',
    'idiosyncratic', 'solipsistic', 'epistemological', 'ontological', 'hermeneutic',
    'phenomenological', 'axiological', 'deontological', 'teleological',
    'synergistic', 'autochthonous', 'endemic', 'exogenous', 'endogenous',
    'disingenuous', 'sycophantic', 'obsequious', 'truculent', 'pusillanimous',
    'peripatetic', 'specious', 'tendentious', 'invidious', 'recondite',
    'sesquipedalian', 'verisimilitude', 'loquacious', 'fastidious',
    'perspicacious', 'phlegmatic', 'sanguine', 'choleric', 'melancholic',
}

issues = []

for r in pass_records:
    word = r['word']
    pos = r['pos']
    cefr = r['cefr']
    def_before = r['def_before'] or ''
    gloss = r['gloss_after'] or ''
    rule = r.get('rule_applied') or ''
    sep = r.get('separator') or 'none'
    source = r.get('source') or ''

    # Count senses in def
    def_senses = [s.strip() for s in def_before.split('|') if s.strip()]
    n_def_senses = len(def_senses)

    # Count gloss chunks
    gloss_chunks = [c.strip() for c in re.split(r'[|;]', gloss) if c.strip()]
    n_gloss_chunks = len(gloss_chunks)

    flags = []
    details = {}

    # ---- Heuristic 1: Multi-sense def collapsed to single gloss ----
    if n_def_senses >= 2 and n_gloss_chunks == 1 and rule in ('rule_b_pick1', 'multi_pos_pick1', ''):
        # High risk if senses are semantically diverse
        flags.append('MULTI_SENSE_COLLAPSED')
        details['n_def_senses'] = n_def_senses
        details['def_senses_preview'] = [s[:50] for s in def_senses]

    # ---- Heuristic 2: Def has 3+ senses, gloss has 2 chunks (may drop 1+ sense) ----
    if n_def_senses >= 3 and n_gloss_chunks == 2:
        flags.append('SENSE_DROPPED_3TO2')
        details['n_def_senses'] = n_def_senses
        details['def_senses_preview'] = [s[:50] for s in def_senses]

    # ---- Heuristic 3: Very short gloss for complex def ----
    gloss_words = gloss.replace('|', ' ').replace(';', ' ').split()
    if len(gloss_words) == 1 and len(def_before) > 80:
        flags.append('SINGLE_WORD_GLOSS_COMPLEX_DEF')
        details['def_length'] = len(def_before)

    # ---- Heuristic 4: Technical/obscure word in gloss ----
    gloss_lower_words = set(re.sub(r'[^a-z\s-]', '', gloss.lower()).split())
    technical_hits = gloss_lower_words & TECHNICAL_WORDS
    if technical_hits:
        flags.append('TECHNICAL_GLOSS_WORD')
        details['technical_words'] = list(technical_hits)

    # ---- Heuristic 5: Separator mismatch risk ----
    # def uses | (distinct domains) but gloss uses ; (same domain)
    if '|' in def_before and sep == ';':
        flags.append('SEP_MISMATCH_DEF_PIPE_GLOSS_SEMI')
    # def uses ; (sub-chunks) but gloss uses | (distinct domains)
    # Less suspicious — def sub-chunks might be treated as 2 distinct glosses

    # ---- Heuristic 6: Near-duplicate gloss chunks (possible Rule A violation) ----
    if n_gloss_chunks == 2:
        c1, c2 = gloss_chunks[0].lower(), gloss_chunks[1].lower()
        # Simple overlap: count shared content words
        w1 = set(c1.split()) - {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'and', 'or'}
        w2 = set(c2.split()) - {'the', 'a', 'an', 'of', 'to', 'in', 'for', 'and', 'or'}
        if w1 and w2:
            overlap = w1 & w2
            overlap_ratio = len(overlap) / max(len(w1), len(w2))
            if overlap_ratio >= 0.5:
                flags.append('POSSIBLE_RULE_A_PAIR')
                details['gloss_chunks'] = [gloss_chunks[0], gloss_chunks[1]]
                details['shared_words'] = list(overlap)

    # ---- Heuristic 7: Gloss drops location/domain qualifier from def ----
    # e.g. def says "in sport" but gloss has no sport qualifier
    sport_markers = ['in sport', 'in football', 'in cricket', 'in baseball',
                     'in hockey', 'in basketball', 'in chess', 'in tennis']
    legal_markers = ['in law', 'in court', 'legally', 'in a legal context']
    music_markers = ['in music', 'musical', 'a piece of music', 'for instruments']

    for marker in sport_markers:
        if marker in def_before.lower() and n_gloss_chunks == 1:
            if not any(w in gloss.lower() for w in ['sport', 'game', 'match', 'play', 'ball']):
                flags.append('DOMAIN_QUALIFIER_DROPPED_SPORT')
                details['marker'] = marker
                break

    # ---- Heuristic 8: Def explicitly bi-directional but gloss is 1-directional ----
    # e.g. def says "A or B" where A and B are quite different
    if ' or ' in def_before and n_gloss_chunks == 1:
        or_parts = def_before.lower().split(' or ')
        if len(or_parts) >= 2 and len(or_parts[0].split()) >= 3 and len(or_parts[-1].split()) >= 3:
            # Check if gloss covers both sides
            flags.append('DEF_OR_GLOSS_SINGLE')

    if flags:
        issue = {
            'word': word,
            'pos': pos,
            'cefr': cefr,
            'def_before': def_before,
            'gloss_after': gloss,
            'rule_applied': rule,
            'source': source,
            'flags': flags,
            'details': details,
        }
        issues.append(issue)

print(f'\nFound {len(issues)} potential quality issues')

# Group by flag
by_flag = defaultdict(list)
for issue in issues:
    for f in issue['flags']:
        by_flag[f].append(issue)

print('\nBreakdown by flag:')
for flag, cards in sorted(by_flag.items(), key=lambda x: -len(x[1])):
    print(f'  {flag}: {len(cards)} cards')

# Save
output = {
    '_meta': {
        'source': str(AUDIT_PATH),
        'total_pass_records': len(pass_records),
        'total_issues': len(issues),
        'by_flag': {f: len(c) for f, c in by_flag.items()},
        'note': 'Heuristic-based; all findings need human review. False positives expected, especially in MULTI_SENSE_COLLAPSED and DEF_OR_GLOSS_SINGLE.',
    },
    'issues': issues
}

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'\nSaved to {OUT_PATH}')
