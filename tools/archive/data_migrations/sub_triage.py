"""Sub-triage Bucket 1 (IN_PLACE) and Bucket 2 (MISSING_CARD).

Bucket 1 sub-split:
  1A: homogeneous CEFR (all senses have same non-null CEFR) — safe to relabel
  1B: mixed CEFR (senses have different CEFRs or null mixed) — unsafe

Bucket 2 sub-split:
  2A: text EXISTS in some card of same word (regardless of declared_cefr) —
      mislabeled, content present
  2B: text ABSENT from all cards of word — truly missing

No patching — read-only analysis.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from src.config import ProjectPaths

paths = ProjectPaths()
ROOT = paths.root
DECK_PATH = paths.anki_notes_txt
SOURCE_PATH = paths.oxford_jsonl
AUDIT_DIR = ROOT / 'data' / 'cefr_audit'


def _norm(s: str) -> str:
    """Strict normalize: strip register-tag, expand sth/sb, collapse ws,
    strip trailing period, lowercase."""
    if s is None:
        return ''
    s = s.strip()
    s = re.sub(r'^\s*\[[^\]]+\]\s*', '', s)
    s = re.sub(r'\bsth\.?\b', 'something', s, flags=re.IGNORECASE)
    s = re.sub(r'\bsb\.?\b', 'somebody', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+', ' ', s)
    s = s.rstrip('.').strip().lower()
    return s


def load_deck_cards() -> list[dict]:
    """Full deck with senses list and declared_cefr."""
    cards = []
    with DECK_PATH.open(encoding='utf-8', newline='') as f:
        reader = csv.reader(f, delimiter='\t')
        for line_no, row in enumerate(reader, 1):
            if not row or row[0].startswith('#') or len(row) < 16:
                continue
            word = row[3].strip()
            pos_list = [p.strip() for p in re.split(r'[,/]', row[4]) if p.strip()]
            defs = [d.strip() for d in row[6].split('|') if d.strip()]
            cefr = row[14].strip() or 'UNCLASSIFIED'
            cards.append({
                'line_no': line_no,
                'word': word,
                'pos_list': pos_list,
                'senses': defs,
                'declared_cefr': cefr,
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


def main() -> int:
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    # Find latest triage CSVs (from previous run)
    b1_files = sorted(AUDIT_DIR.glob('bucket1_in_place_2*.csv'))
    b2_files = sorted(AUDIT_DIR.glob('bucket2_missing_card_2*.csv'))
    b1_path = b1_files[-1]
    b2_path = b2_files[-1]
    print(f'Reading: {b1_path.name} + {b2_path.name}')

    with b1_path.open(encoding='utf-8', newline='') as f:
        bucket1 = list(csv.DictReader(f))
    with b2_path.open(encoding='utf-8', newline='') as f:
        bucket2 = list(csv.DictReader(f))

    deck = load_deck_cards()
    source = load_source()

    # Build (word -> set of normalized sense texts across all its cards)
    word_to_sense_norms: dict[str, set[str]] = defaultdict(set)
    # Also: word -> list of (sense_norm, line_no, declared_cefr) for diagnostics
    word_to_sense_meta: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for c in deck:
        for s in c['senses']:
            sn = _norm(s)
            if sn:
                word_to_sense_norms[c['word']].add(sn)
                word_to_sense_meta[c['word']].append((sn, c['line_no'], c['declared_cefr']))

    # ============================================================
    # Bucket 2 sub-split
    # ============================================================
    bucket2a_mislabeled = []
    bucket2b_truly_absent = []
    for r in bucket2:
        word = r['word']
        sense_text = r['sense_text']
        sn = _norm(sense_text)
        if sn in word_to_sense_norms.get(word, set()):
            # Find which line_no has this sense
            matches = [m for m in word_to_sense_meta[word] if m[0] == sn]
            bucket2a_mislabeled.append({
                **r,
                'found_in_lines': '|'.join(str(m[1]) for m in matches),
                'found_in_declared_cef': '|'.join(m[2] for m in matches),
            })
        else:
            bucket2b_truly_absent.append(r)

    # ============================================================
    # Bucket 1 sub-split
    # ============================================================
    # For each card in bucket 1, look up source per-def CEFR for each deck sense.
    # Bucket 1 entries are per-sense (with line_no + sense_idx) — but we want
    # CARD-level analysis (homogeneity across all senses of the card).
    # Group by line_no.
    b1_by_line: dict[int, list[dict]] = defaultdict(list)
    for r in bucket1:
        b1_by_line[int(r['line_no'])].append(r)

    # Build a card lookup by line_no
    card_by_line = {c['line_no']: c for c in deck}

    bucket1a_homogeneous = []
    bucket1b_mixed = []
    for line_no, sense_rows in b1_by_line.items():
        card = card_by_line.get(line_no)
        if not card:
            continue
        word = card['word']
        src_rec = source.get(word)
        if not src_rec:
            continue
        # Build (sense_text -> source per-def cefr) from source
        # by walking pos_data and matching sense text via exact norm
        sense_to_src_cefr: dict[str, Optional[str]] = {}
        for pd in src_rec.get('pos_data', []):
            for d in pd.get('definitions', []):
                sn = _norm(d.get('text'))
                if sn:
                    sense_to_src_cefr[sn] = d.get('cefr')

        # For each deck sense, look up its source per-def CEFR
        per_sense_cef = []
        for s in card['senses']:
            sn = _norm(s)
            per_sense_cef.append(sense_to_src_cefr.get(sn))  # may be None

        # Homogeneity: all same non-null value
        non_null = [c for c in per_sense_cef if c is not None]
        if non_null and len(set(non_null)) == 1 and len(non_null) == len(per_sense_cef):
            # All senses have same non-null CEFR
            bucket1a_homogeneous.append({
                'line_no': line_no,
                'word': word,
                'declared_cefr': card['declared_cefr'],
                'per_def_cefr_uniform': non_null[0],
                'n_senses': len(per_sense_cef),
                'n_non_null': len(non_null),
            })
        else:
            # Mixed: not all same, or some null
            distinct = sorted(set(c for c in per_sense_cef if c is not None))
            has_null = any(c is None for c in per_sense_cef)
            bucket1b_mixed.append({
                'line_no': line_no,
                'word': word,
                'declared_cefr': card['declared_cefr'],
                'n_senses': len(per_sense_cef),
                'per_def_cefrs': '|'.join(c if c else 'NULL' for c in per_sense_cef),
                'distinct_non_null': '|'.join(distinct) if distinct else '(none)',
                'has_null': 'yes' if has_null else 'no',
            })

    # ============================================================
    # Report
    # ============================================================
    print(f'\n=== BUCKET 2 SUB-SPLIT ===')
    print(f'Total: {len(bucket2)}')
    print(f'  2A mislabeled (text exists in some card of word)  : {len(bucket2a_mislabeled)}')
    print(f'  2B truly absent (text absent from all cards of word): {len(bucket2b_truly_absent)}')

    print(f'\n--- Bucket 2A top 20 ---')
    for r in bucket2a_mislabeled[:20]:
        print(f'  {r["word"]:<20} missing={r["missing_cefr"]:<4} pos={r["source_pos"]:<10} '
              f'found_in_line#{r["found_in_lines"]} (declared={r["found_in_declared_cef"]}) '
              f'sense={r["sense_text"][:50]!r}')

    print(f'\n--- Bucket 2B top 20 ---')
    for r in bucket2b_truly_absent[:20]:
        print(f'  {r["word"]:<20} missing={r["missing_cefr"]:<4} pos={r["source_pos"]:<10} '
              f'sense={r["sense_text"][:50]!r}')

    print(f'\n=== BUCKET 1 SUB-SPLIT ===')
    print(f'Total: {len(b1_by_line)} cards')
    print(f'  1A homogeneous (all senses same non-null CEFR) : {len(bucket1a_homogeneous)}')
    print(f'  1B mixed (senses differ or some null)            : {len(bucket1b_mixed)}')

    print(f'\n--- Bucket 1A top 10 (safe to relabel card) ---')
    for r in bucket1a_homogeneous[:10]:
        print(f'  line={r["line_no"]:>4} word={r["word"]:<20} '
              f'deck={r["declared_cefr"]:<13} per_def_uniform={r["per_def_cefr_uniform"]:<3} '
              f'n_senses={r["n_senses"]}')

    print(f'\n--- Bucket 1B top 10 (mixed, relabel would be wrong) ---')
    for r in bucket1b_mixed[:10]:
        print(f'  line={r["line_no"]:>4} word={r["word"]:<20} '
              f'deck={r["declared_cefr"]:<13} per_defs=[{r["per_def_cefrs"]}] '
              f'has_null={r["has_null"]}')

    # uncertain verification
    print(f'\n=== uncertain verification (in sub-buckets) ===')
    unc_2a = [r for r in bucket2a_mislabeled if r['word'] == 'uncertain']
    unc_2b = [r for r in bucket2b_truly_absent if r['word'] == 'uncertain']
    unc_1a = [r for r in bucket1a_homogeneous if r['word'] == 'uncertain']
    unc_1b = [r for r in bucket1b_mixed if r['word'] == 'uncertain']
    print(f'  uncertain in 2A (mislabeled): {len(unc_2a)}')
    for r in unc_2a:
        print(f'    missing_cefr={r["missing_cefr"]} pos={r["source_pos"]} '
              f'found_in_line#{r["found_in_lines"]} (declared={r["found_in_declared_cef"]}) '
              f'sense={r["sense_text"]!r}')
    print(f'  uncertain in 2B (truly absent): {len(unc_2b)}')
    print(f'  uncertain in 1A (homogeneous): {len(unc_1a)}')
    print(f'  uncertain in 1B (mixed):       {len(unc_1b)}')
    for r in unc_1b:
        print(f'    line={r["line_no"]} deck={r["declared_cefr"]} '
              f'per_defs=[{r["per_def_cefrs"]}]')

    # ============================================================
    # Save CSVs
    # ============================================================
    import datetime
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    if bucket2a_mislabeled:
        p = AUDIT_DIR / f'sub_2a_mislabeled_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(bucket2a_mislabeled[0].keys()))
            w.writeheader()
            w.writerows(bucket2a_mislabeled)
        print(f'\nWrote: {p.name}')
    if bucket2b_truly_absent:
        p = AUDIT_DIR / f'sub_2b_truly_absent_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(bucket2b_truly_absent[0].keys()))
            w.writeheader()
            w.writerows(bucket2b_truly_absent)
        print(f'Wrote: {p.name}')
    if bucket1a_homogeneous:
        p = AUDIT_DIR / f'sub_1a_homogeneous_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(bucket1a_homogeneous[0].keys()))
            w.writeheader()
            w.writerows(bucket1a_homogeneous)
        print(f'Wrote: {p.name}')
    if bucket1b_mixed:
        p = AUDIT_DIR / f'sub_1b_mixed_{stamp}.csv'
        with p.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(bucket1b_mixed[0].keys()))
            w.writeheader()
            w.writerows(bucket1b_mixed)
        print(f'Wrote: {p.name}')

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
