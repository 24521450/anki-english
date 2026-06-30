import json
import os

p_txt = r'C:\Users\admin\Downloads\ankideck\English Academic Vocabulary.txt'
p_notes = r'C:\Users\admin\Downloads\ankideck\data\anki_notes.jsonl'
p_audit = r'C:\Users\admin\Downloads\ankideck\data\simplify_diff\audit_full_deck.jsonl'

# Txt count
with open(p_txt, encoding='utf-8') as f:
    n_txt = sum(1 for l in f.read().split('\n') if l.strip() and not l.startswith('#'))
print(f'txt: {n_txt} non-comment lines')

# anki_notes count
with open(p_notes, encoding='utf-8') as f:
    n_notes = sum(1 for _ in f)
print(f'anki_notes.jsonl: {n_notes} records')

# audit count
with open(p_audit, encoding='utf-8') as f:
    n_audit = sum(1 for _ in f)
print(f'audit_full_deck.jsonl: {n_audit} records')

# anki_notes fields
with open(p_notes, encoding='utf-8') as f:
    first = json.loads(f.readline())
print(f'\nanki_notes.jsonl fields:')
for k in first.keys():
    v = first[k]
    if isinstance(v, str) and len(v) > 60:
        v = v[:60] + '...'
    print(f'  {k}: {v!r}')

# anki_notes covers what % of txt?
with open(p_txt, encoding='utf-8') as f:
    txt_keys = set()
    for l in f:
        if l.startswith('#') or not l.strip():
            continue
        p = l.split('\t')
        if len(p) >= 7:
            txt_keys.add((p[3], p[4], p[14]))

with open(p_notes, encoding='utf-8') as f:
    notes_keys = set()
    for l in f:
        r = json.loads(l)
        notes_keys.add((r['word'], r['pos'], r['cefr']))

print(f'\nanki_notes covers {len(notes_keys & txt_keys)}/{len(txt_keys)} of txt cards')

# Are there pace entries in anki_notes?
pace_in_notes = [r for r in (json.loads(l) for l in open(p_notes, encoding='utf-8')) if r['word'] == 'pace']
print(f'\npace in anki_notes: {len(pace_in_notes)}')
for p in pace_in_notes:
    w = p['word']
    pos = p['pos']
    cefr = p['cefr']
    defn = p['definition']
    print(f'  {w}|{pos}|{cefr}: def={defn!r}')

# Are there pace entries in audit?
pace_in_audit = [r for r in (json.loads(l) for l in open(p_audit, encoding='utf-8')) if r['word'] == 'pace']
print(f'\npace in audit: {len(pace_in_audit)}')
for p in pace_in_audit:
    w = p['word']
    pos = p['pos']
    cefr = p['cefr']
    db = p['def_before']
    gl = p['gloss_after']
    print(f'  {w}|{pos}|{cefr}')
    print(f'    def_before: {db[:80]!r}')
    print(f'    gloss_after: {gl!r}')
