"""Triage 818 mismatches into 3 buckets.

Bucket 1 — IN_PLACE: cefr-mismatch + badge_match=no + per-def non-null
Bucket 2 — MISSING_CARD: source sense with cefr=X has no matching (word, X) in deck
Bucket 3 — FALSE_POSITIVE: word-not-in-source / sense-text-not-in-source,
           try lemmatize(word) to see if resolution possible.

Scope: 818 failing cards from failures_only_*.csv.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import nltk
from nltk.stem import WordNetLemmatizer

ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
DECK_PATH = ROOT / 'English Academic Vocabulary.txt'
SOURCE_PATH = ROOT / 'data' / 'oxford_merged.jsonl'
AUDIT_DIR = ROOT / 'data' / 'cefr_audit'

lemmatizer = WordNetLemmatizer()


def _norm(s: Optional[str]) -> str:
    if s is None:
        return ''
    s = s.strip()
    s = re.sub(r'^\s*\[[^\]]+\]\s*', '', s)
    s = re.sub(r'\bsth\.?\b', 'something', s, flags=re.IGNORECASE)
    s = re.sub(r'\bsb\.?\b', 'somebody', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', ' ', s)
    s = s.rstrip('.').strip().lower()
    return s


def _tokenize(s: str) -> list[str]:
    s = re.sub(r'[^a-z0-9\s]', ' ', s.lower())
    return [t for t in s.split() if len(t) > 1]


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(_tokenize(a)), set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def load_deck() -> list[dict]:
    """Full deck — needed for MISSING_CARD cross-check."""
    cards = []
    with DECK_PATH.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if not row or row[0].startswith('#') or len(row) < 16:
                continue
            cards.append({
                'word': row[3].strip(),
                'declared_cefr': row[14].strip() or 'UNCLASSIFIED',
                'pos_list': [p.strip() for p in re.split(r'[,/]', row[4]) if p.strip()],
            })
    return cards


def load_source() -> dict[str, dict]:
    src = {}
    with SOURCE_PATH.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            w = rec.get('word')
            if w:
                src[w] = rec
    return src


def lemmatize_word(w: str) -> str:
    """Try multiple POS to find a base form. Returns the first non-trivial lemma."""
    candidates = set()
    for pos in ['n', 'v', 'a', 's', 'r']:
        lemma = lemmatizer.lemmatize(w.lower(), pos=pos)
        if lemma != w.lower() and len(lemma) > 2:
            candidates.add(lemma)
    # If nothing changed, return as-is
    if not candidates:
        return w.lower()
    # Return the shortest (most "base" form)
    return min(candidates, key=len)


def main() -> int:
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    # Find latest audit CSVs
    sense_files = sorted(AUDIT_DIR.glob('per_sense_audit_2*.csv'))
    card_files = sorted(AUDIT_DIR.glob('per_card_audit_2*.csv'))
    sense_path = sense_files[-1]
    card_path = card_files[-1]
    print(f'Sense audit: {sense_path.name}')
    print(f'Card audit : {card_path.name}')

    with sense_path.open(encoding='utf-8', newline='') as f:
        sense_rows = list(csv.DictReader(f))
    with card_path.open(encoding='utf-8', newline='') as f:
        card_rows = list(csv.DictReader(f))

    failing_card_rows = [r for r in card_rows if r['card_status'] == 'mismatch']
    failing_line_nos = {int(r['line_no']) for r in failing_card_rows}
    print(f'Failing cards: {len(failing_card_rows)}')

    deck = load_deck()
    source = load_source()

    # ============================================================
    # Bucket 1: IN_PLACE
    # ============================================================
    in_place_cards = {}  # line_no -> row info
    for sr in sense_rows:
        if sr['status'] != 'mismatch':
            continue
        line_no = int(sr['line_no'])
        if line_no not in failing_line_nos:
            continue
        # cefr-mismatch with per-def non-null AND badge_match=no
        if 'cefr-mismatch' not in sr['reason']:
            continue
        if sr['source_cefr_origin'] != 'per-def':
            continue
        # badge_match=no: source_oxford_badge != declared_cefr
        if sr['source_oxford_badge'] == sr['declared_cefr']:
            continue
        # If we already have a record for this card, keep the one with the
        # strongest CEFR disagreement (longest reason text)
        existing = in_place_cards.get(line_no)
        if existing is None or len(sr['reason']) > len(existing['reason']):
            in_place_cards[line_no] = sr

    in_place_list = list(in_place_cards.values())

    # ============================================================
    # Bucket 2: MISSING_CARD
    # ============================================================
    # Build (word, declared_cefr) set from ALL 3,020 cards
    deck_pairs = {(c['word'], c['declared_cefr']) for c in deck}

    # For each failing word, find source senses with cefr=X != null
    # that don't have a matching (word, X) card in deck
    failing_words = {r['word'] for r in failing_card_rows}
    missing_card_rows = []
    for word in sorted(failing_words):
        rec = source.get(word)
        if not rec:
            continue
        for pd in rec.get('pos_data', []):
            for di, d in enumerate(pd.get('definitions', []), 1):
                cefr = d.get('cefr')
                if cefr is None:
                    continue
                if (word, cefr) not in deck_pairs:
                    missing_card_rows.append({
                        'word': word,
                        'missing_cefr': cefr,
                        'source_pos': pd.get('pos', ''),
                        'source_def_idx': di,
                        'sense_text': (d.get('text') or '')[:120],
                        'badge': rec.get('oxford_badge') or '',
                    })

    # ============================================================
    # Bucket 3: FALSE_POSITIVE — try lemmatize
    # ============================================================
    false_pos_rows = []
    for cr in failing_card_rows:
        line_no = int(cr['line_no'])
        if 'word-not-in-source' in cr['card_reason']:
            word = cr['word']
            lemma = lemmatize_word(word)
            lemma_in_source = lemma in source
            false_pos_rows.append({
                'line_no': line_no,
                'word': word,
                'lemma': lemma,
                'lemma_in_source': 'yes' if lemma_in_source else 'no',
                'declared_cefr': cr['declared_cefr'],
                'card_reason': cr['card_reason'],
                'category': 'word-not-in-source',
            })
        elif 'sense-text-not-in-source' in cr['card_reason']:
            word = cr['word']
            lemma = lemmatize_word(word)
            lemma_in_source = lemma in source
            false_pos_rows.append({
                'line_no': line_no,
                'word': word,
                'lemma': lemma,
                'lemma_in_source': 'yes' if lemma_in_source else 'no',
                'declared_cefr': cr['declared_cefr'],
                'card_reason': cr['card_reason'],
                'category': 'sense-text-not-in-source',
            })

    # ============================================================
    # Report
    # ============================================================
    print(f'\n=== BUCKET 1: IN_PLACE ===')
    print(f'Count: {len(in_place_list)}')
    print(f'(cefr-mismatch + per-def non-null + badge != declared)')
    print(f'\nTop 20:')
    print(f'{"line":>6} {"word":<20} {"sense":>2} {"deck_cef":<13} {"src_cef":<6} {"src_badge":<10} reason')
    for r in sorted(in_place_list, key=lambda x: x['word'])[:20]:
        print(f'{r["line_no"]:>6} {r["word"]:<20} {r["sense_idx"]:>2} '
              f'{r["declared_cefr"]:<13} {r["source_cefr"]:<6} {r["source_oxford_badge"]:<10} '
              f'{r["reason"][:80]}')

    print(f'\n=== BUCKET 2: MISSING_CARD ===')
    print(f'Count: {len(missing_card_rows)}')
    print(f'(source has sense with cefr=X, no (word, X) card in deck)')
    print(f'\nTop 20:')
    for r in missing_card_rows[:20]:
        print(f'  {r["word"]:<20} missing={r["missing_cefr"]:<4} '
              f'pos={r["source_pos"]:<10} def#{r["source_def_idx"]} '
              f'sense={r["sense_text"][:60]!r}')

    print(f'\n=== BUCKET 3: FALSE_POSITIVE ===')
    print(f'Total failing in scope: {len(false_pos_rows)}')
    word_nis = [r for r in false_pos_rows if r['category'] == 'word-not-in-source']
    sense_nis = [r for r in false_pos_rows if r['category'] == 'sense-text-not-in-source']
    print(f'  word-not-in-source     : {len(word_nis)}')
    print(f'  sense-text-not-in-source: {len(sense_nis)}')

    # Lemmatize resolution
    print(f'\nLemmatize resolution (word-not-in-source, 62 cards):')
    resolved_lemma = [r for r in word_nis if r['lemma_in_source'] == 'yes']
    print(f'  lemma found in source: {len(resolved_lemma)} / {len(word_nis)}')
    print(f'\nTop 20 word-not-in-source cases with lemma:')
    for r in word_nis[:20]:
        marker = '[OK]' if r['lemma_in_source'] == 'yes' else '[NO]'
        print(f'  {marker} {r["word"]:<20} -> {r["lemma"]:<15} '
              f'in_source={r["lemma_in_source"]}')

    # ============================================================
    # Confirm: uncertain is MISSING_CARD (B1)?
    # ============================================================
    print(f'\n=== uncertain verification ===')
    uncertain_deck_cards = [c for c in deck if c['word'] == 'uncertain']
    print(f'Deck cards for "uncertain": {len(uncertain_deck_cards)}')
    for c in uncertain_deck_cards:
        print(f'  line={c.get("declared_cefr")} declared={c["declared_cefr"]}')

    uncertain_in_missing = [r for r in missing_card_rows if r['word'] == 'uncertain']
    print(f'\"uncertain\" in MISSING_CARD list: {len(uncertain_in_missing)}')
    for r in uncertain_in_missing:
        print(f'  missing_cefr={r["missing_cefr"]} pos={r["source_pos"]} '
              f'sense={r["sense_text"][:60]!r}')

    uncertain_is_missing_B1 = any(
        r['word'] == 'uncertain' and r['missing_cefr'] == 'B1'
        for r in missing_card_rows
    )
    print(f'\n*** uncertain IS MISSING_CARD (B1): {uncertain_is_missing_B1} ***')

    # ============================================================
    # Save CSVs
    # ============================================================
    import datetime
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    if in_place_list:
        p = AUDIT_DIR / f'bucket1_in_place_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(in_place_list[0].keys()))
            w.writeheader()
            w.writerows(in_place_list)
        print(f'\nWrote: {p.name}')
    if missing_card_rows:
        p = AUDIT_DIR / f'bucket2_missing_card_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(missing_card_rows[0].keys()))
            w.writeheader()
            w.writerows(missing_card_rows)
        print(f'Wrote: {p.name}')
    if false_pos_rows:
        p = AUDIT_DIR / f'bucket3_false_positive_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(false_pos_rows[0].keys()))
            w.writeheader()
            w.writerows(false_pos_rows)
        print(f'Wrote: {p.name}')

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
