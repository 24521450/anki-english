"""Check CEFR of Anki deck vs oxford.jsonl source.

Compares (Word, POS, sense_text) triples from the Anki deck export against
`data/sources/oxford.jsonl` (schema v2, per-def cefr).

Deck format: Anki's "Notes in Plain Text" with `html:false`. 16 tab-
separated columns. Card fields:
  col 4: word
  col 5: POS (single or comma-separated)
  col 7: definition (pipe-separated for multi-sense)
  col 13: Cambridge-source ("Oxford" or "Cambridge" — which dict the
          def text came from)
  col 14: Oxford-source
  col 15: declared CEFR level
  col 16: tags (space-separated)

Outputs:
  data/cefr_audit/per_sense_audit.csv  (one row per (word, sense))
  data/cefr_audit/per_card_audit.csv   (one row per card)

Decision spec (grilled with user 2026-06-11):
  - Source: sources/oxford.jsonl
  - Per-card + per-sense output
  - Strict text match (unmatched sense = mismatch). Tolerance:
    strip "[register,tag] " prefix, expand "sth"/"sb" abbreviations,
    ignore whitespace and trailing period.
  - Source cefr resolution: per-def `cefr` if non-null, else fall back
    to word-level `oxford_badge` (Oxford's tier endorsement IS the
    word's CEFR — per-def being null doesn't mean "unclassified").
  - Multi-POS: strict in-order per POS group (senses 1..n in pos_data[0],
    then senses 1..m in pos_data[1], etc.). Surface "flat-matched"
    caveat when deck has no per-sense POS chip.
"""
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from src.config import ProjectPaths

paths = ProjectPaths()
ROOT = paths.root
DECK_PATH = paths.anki_notes_txt
SOURCE_PATH = paths.oxford_jsonl
OUT_DIR = ROOT / 'data' / 'cefr_audit'

UNCLASSIFIED = 'UNCLASSIFIED'


def _norm(s: Optional[str]) -> str:
    """Tolerant-match normalizer.

    Handles:
      - Leading register-tag bracket: "[disapproving, informal] "
      - Cambridge abbrevs: "sth" → "something", "sb" → "somebody"
      - Whitespace + trailing period
    Lowercased.
    """
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


def _jaccard_score(a: str, b: str) -> float:
    ta, tb = set(_tokenize(a)), set(_tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# --- Deck parser (Anki Notes in Plain Text, 16 cols) ---

def parse_deck(txt_path: Path) -> list[dict]:
    cards = []
    with txt_path.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        for line_no, row in enumerate(reader, 1):
            if not row or row[0].startswith('#'):
                continue
            if len(row) < 16:
                # Malformed row; skip
                continue
            word = row[3].strip()
            pos_raw = row[4].strip()
            pos_list = [p.strip() for p in re.split(r'[,/]', pos_raw) if p.strip()]
            defs = [d.strip() for d in row[6].split('|') if d.strip()]
            cefr_declared = row[14].strip() or UNCLASSIFIED
            tags = row[15].split() if row[15] else []
            # Source-of-def (Cambridge/Oxford/empty)
            src_cambridge = row[12].strip()
            src_oxford = row[13].strip()
            cards.append({
                'line_no': line_no,
                'word': word,
                'pos_list': pos_list,
                'senses': defs,
                'declared_cefr': cefr_declared,
                'tags': tags,
                'src_cambridge': src_cambridge,
                'src_oxford': src_oxford,
            })
    return cards


# --- Source loader ---

def load_source(jsonl_path: Path) -> dict[str, dict]:
    src = {}
    with jsonl_path.open(encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            w = rec.get('word')
            if w is None:
                continue
            src[w] = rec
    return src


# --- Per-sense matcher ---

def match_senses(card: dict, src_rec: Optional[dict]) -> list[dict]:
    declared = card['declared_cefr']
    senses = card['senses']
    pos_list = card['pos_list']
    is_multi_pos = len(pos_list) > 1

    if src_rec is None:
        return [{
            'sense_idx': i,
            'sense_pos_chip': '',
            'sense_text': s,
            'source_pos': '',
            'source_def_idx': '',
            'source_cefr': '',
            'source_cefr_origin': '',
            'source_oxford_badge': '',
            'declared_cefr': declared,
            'status': 'mismatch',
            'reason': 'word-not-in-source',
            'match_kind': 'none',
        } for i, s in enumerate(senses, 1)]

    if src_rec.get('_skip'):
        skip_reason = src_rec.get('_skip_reason', '')
        return [{
            'sense_idx': i,
            'sense_pos_chip': '',
            'sense_text': s,
            'source_pos': '',
            'source_def_idx': '',
            'source_cefr': '',
            'source_cefr_origin': '',
            'source_oxford_badge': '',
            'declared_cefr': declared,
            'status': 'mismatch',
            'reason': f'source-skip: {skip_reason}',
            'match_kind': 'none',
        } for i, s in enumerate(senses, 1)]

    pos_data = src_rec.get('pos_data', [])
    flat = []
    for pd in pos_data:
        p = pd.get('pos', '')
        for di, d in enumerate(pd.get('definitions', []), 1):
            flat.append((p, di, d))

    word_badge = src_rec.get('oxford_badge') or ''
    # Multi-POS deck card with no per-sense POS chip: surface as caveat
    caveat = ''
    if is_multi_pos and not _deck_emits_per_sense_pos(card):
        caveat = 'no-per-sense-pos-in-deck; flat-matched'

    rows = []
    for i, s in enumerate(senses, 1):
        s_norm = _norm(s)
        match = None
        match_kind = None

        # Pass 1: exact (post-norm) text match
        for fpos, di, d in flat:
            if s_norm and _norm(d.get('text')) == s_norm:
                match = (fpos, di, d)
                match_kind = 'exact-norm'
                break

        # Pass 2: fuzzy Jaccard >= 0.5
        if match is None and s_norm:
            best, best_score = None, 0.0
            for fpos, di, d in flat:
                t_norm = _norm(d.get('text'))
                if not t_norm:
                    continue
                score = _jaccard_score(s_norm, t_norm)
                if score > best_score:
                    best_score = score
                    best = (fpos, di, d)
            if best_score >= 0.5:
                match = best
                match_kind = f'fuzzy-jaccard={best_score:.2f}'

        if match is None:
            rows.append({
                'sense_idx': i,
                'sense_pos_chip': '',
                'sense_text': s,
                'source_pos': '',
                'source_def_idx': '',
                'source_cefr': '',
                'source_cefr_origin': '',
                'source_oxford_badge': word_badge,
                'declared_cefr': declared,
                'status': 'mismatch',
                'reason': f'sense-text-not-in-source{("; " + caveat) if caveat else ""}',
                'match_kind': 'none',
            })
            continue

        fpos, di, d = match
        per_def_cefr = d.get('cefr')
        if per_def_cefr is not None:
            src_cefr_str = per_def_cefr
            cefr_origin = 'per-def'
        elif word_badge:
            src_cefr_str = word_badge
            cefr_origin = 'oxford-badge'
        else:
            src_cefr_str = UNCLASSIFIED
            cefr_origin = 'none'

        if src_cefr_str == declared:
            status = 'match'
            reason = ''
        else:
            status = 'mismatch'
            reason = f'cefr-mismatch (deck={declared}, source={src_cefr_str} [{cefr_origin}]'
            if cefr_origin == 'per-def' and word_badge and word_badge != per_def_cefr:
                reason += f', source-badge={word_badge}'
            reason += ')'

        if caveat:
            reason = (reason + '; ' if reason else '') + caveat

        rows.append({
            'sense_idx': i,
            'sense_pos_chip': '',
            'sense_text': s,
            'source_pos': fpos,
            'source_def_idx': di,
            'source_cefr': src_cefr_str,
            'source_cefr_origin': cefr_origin,
            'source_oxford_badge': word_badge,
            'declared_cefr': declared,
            'status': status,
            'reason': reason,
            'match_kind': match_kind or 'unknown',
        })
    return rows


def _deck_emits_per_sense_pos(card: dict) -> bool:
    """EAVM back_template doesn't emit per-sense POS chips.
    Set to True here only if a future template change adds them.
    """
    return False


# --- Per-card aggregator ---

def audit(cards: list[dict], source: dict) -> tuple[list[dict], list[dict]]:
    per_sense_rows = []
    per_card_rows = []

    for card in cards:
        word = card['word']
        src_rec = source.get(word)
        sense_rows = match_senses(card, src_rec)

        # Card-level summary
        sense_statuses = [r['status'] for r in sense_rows]
        if not sense_statuses:
            card_status = 'mismatch'
            card_reason = 'no-senses-in-deck'
        elif any(s == 'mismatch' for s in sense_statuses):
            card_status = 'mismatch'
            bad = [r for r in sense_rows if r['status'] == 'mismatch']
            n_bad = len(bad)
            n_total = len(sense_statuses)
            unique_reasons = sorted({r['reason'] for r in bad})
            card_reason = f"{n_bad}/{n_total} senses failed: " + '; '.join(unique_reasons)
        else:
            card_status = 'match'
            card_reason = ''

        # Card-level CEFR cross-check
        badge = (src_rec or {}).get('oxford_badge') or ''
        badge_match = 'yes' if badge == card['declared_cefr'] else 'no'

        per_card_rows.append({
            'line_no': card['line_no'],
            'word': word,
            'pos_list': '|'.join(card['pos_list']),
            'n_senses': len(card['senses']),
            'declared_cefr': card['declared_cefr'],
            'source_oxford_badge': badge,
            'badge_match': badge_match,
            'src_cambridge_flag': card['src_cambridge'],
            'src_oxford_flag': card['src_oxford'],
            'card_status': card_status,
            'card_reason': card_reason,
            'tags': ' '.join(card['tags']),
        })

        for r in sense_rows:
            per_sense_rows.append({
                'line_no': card['line_no'],
                'word': word,
                'pos_list': '|'.join(card['pos_list']),
                **r,
            })

    return per_card_rows, per_sense_rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    print(f'Parsing deck: {DECK_PATH}')
    cards = parse_deck(DECK_PATH)
    print(f'  -> {len(cards)} cards')

    print(f'Loading source: {SOURCE_PATH}')
    source = load_source(SOURCE_PATH)
    print(f'  -> {len(source)} words')

    per_card, per_sense = audit(cards, source)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Timestamped suffix so we don't collide with open CSVs (e.g. in
    # Excel or Anki holding a write lock on prior outputs).
    import datetime
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    per_card_path = OUT_DIR / f'per_card_audit_{stamp}.csv'
    per_sense_path = OUT_DIR / f'per_sense_audit_{stamp}.csv'
    write_csv(per_card, per_card_path)
    write_csv(per_sense, per_sense_path)

    total_cards = len(per_card)
    card_match = sum(1 for r in per_card if r['card_status'] == 'match')
    total_senses = len(per_sense)
    sense_match = sum(1 for r in per_sense if r['status'] == 'match')

    print(f'\n=== SUMMARY ===')
    print(f'Cards total : {total_cards}')
    print(f'Cards match : {card_match} ({card_match/total_cards*100:.1f}%)')
    print(f'Cards fail  : {total_cards - card_match}')
    print(f'Senses total: {total_senses}')
    print(f'Senses match: {sense_match} ({sense_match/total_senses*100:.1f}%)')

    # Categorize per-sense mismatches
    print(f'\n=== Per-sense mismatch breakdown ===')
    cat = Counter()
    for r in per_sense:
        if r['status'] != 'mismatch':
            continue
        if r['source_cefr_origin'] == 'oxford-badge' and r['source_cefr'] == r['declared_cefr']:
            cat['badge-matches-deck (not really a bug)'] += 1
        elif r['source_cefr_origin'] == 'none':
            cat['no source CEFR (deck CEFR unverified)'] += 1
        elif r['source_cefr'] == UNCLASSIFIED and r['source_oxford_badge']:
            cat['source per-def null but badge present (was wrongly flagged before)'] += 1
        elif 'sense-text-not-in-source' in r['reason']:
            cat['sense text not in Oxford source (likely Cambridge wording)'] += 1
        else:
            cat[f'genuine cefr-mismatch (deck vs source per-def)'] += 1
    for k, v in cat.most_common():
        print(f'  {v:5d}  {k}')

    # Top card-level reasons
    print(f'\n=== Top 10 card-level failure reasons ===')
    card_reasons = Counter()
    for r in per_card:
        if r['card_status'] != 'mismatch':
            continue
        for reason in r['card_reason'].split('; '):
            card_reasons[reason.strip()] += 1
    for k, v in card_reasons.most_common(10):
        print(f'  {v:5d}  {k}')

    # Card-level badge match
    print(f'\n=== Card-level: deck word-CEFR vs source oxford_badge ===')
    bm = Counter(r['badge_match'] for r in per_card)
    for k, v in bm.items():
        print(f'  {k}: {v} ({v/total_cards*100:.1f}%)')

    print(f'\nWrote: {per_card_path}')
    print(f'Wrote: {per_sense_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
