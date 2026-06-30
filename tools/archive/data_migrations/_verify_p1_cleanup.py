"""P1 Semantic Gloss Cleanup Verification Tool.

Reads pre-P1 backups and active files to compare and verify:
  - Master, Filled, TXT row counts unchanged.
  - Before/after counts of validator debt by category.
  - Touched rows: old -> new, and validator pass/fail.
  - TXT definition sync with master audit.
  - Check that the 5 P2-deferred duplicate keys are not merged/deleted.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))

from src.deck_builder.gloss_hygiene import normalize_gloss  # noqa: E402
from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

MASTER = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
FILLED = PROJECT_ROOT / 'data' / 'audit_expanded_needs_gloss_filled.jsonl'
TXT = PROJECT_ROOT / 'English Academic Vocabulary.txt'

POS_LABEL_RE = re.compile(
    r'(^|[|;]\s*)'
    r'(?:'
    r'noun|verb|adjective|adverb|adj|adv|'
    r'preposition|prep|pronoun|determiner|conjunction|'
    r'exclamation|modal|auxiliary|phrasal verb|'
    r'(?:noun|verb|adjective|adverb|adj|adv)\s*/\s*'
    r'(?:noun|verb|adjective|adverb|adj|adv)'
    r')\s*:',
    re.IGNORECASE,
)

P2_DEFERRED_KEYS = {
    ('labor', 'noun', 'C2'),
    ('migrate', 'verb', 'C1'),
    ('navigate', 'verb', 'C1'),
    ('sanctuary', 'noun', 'C2'),
    ('diplomatic', 'adjective', 'C1'),
}


def chunk_count(gloss: str) -> int:
    return len([c for c in re.split(r'\s*[|;]\s*', gloss.strip()) if c.strip()])


def debt_category(violation: str) -> str:
    category = violation.split(':', 1)[0].split('[', 1)[0]
    if category == 'word_count_out_of_range':
        return 'gloss_too_long'
    return category


def get_debt_categories(word: str, gloss: str) -> list[str]:
    if not gloss.strip():
        return []
    res = normalize_gloss(gloss)
    v = validate_verdict(word, res.gloss, res.separator, chunk_count(res.gloss))
    categories = [debt_category(item) for item in v]
    if POS_LABEL_RE.search(res.gloss):
        categories.append('pos_label_candidate')
    return categories


def load_audit(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding='utf-8') as fp:
        for line in fp:
            if not line.strip():
                continue
            rows.append(json.loads(line))
    return rows


def load_txt(path: Path) -> list[tuple[int, list[str]]]:
    rows = []
    raw_lines = path.read_text(encoding='utf-8').splitlines()
    body_start = 0
    for i, line in enumerate(raw_lines):
        if line.startswith('#'):
            body_start = i + 1
        else:
            body_start = i
            break
    for i, line in enumerate(raw_lines[body_start:], start=body_start + 1):
        if not line.strip():
            continue
        fields = line.split('\t')
        rows.append((i, fields))
    return rows


def collect_debt_stats(rows: list[dict]) -> Counter:
    counts = Counter()
    for r in rows:
        g = r.get('gloss_after') or ''
        cats = get_debt_categories(r['word'], g)
        for cat in cats:
            counts[cat] += 1
    return counts


def main():
    # Identify backups
    master_backups = sorted(PROJECT_ROOT.glob('data/audit_full_deck_v2.jsonl.bak_pre_gloss_p1_*'))
    filled_backups = sorted(PROJECT_ROOT.glob('data/audit_expanded_needs_gloss_filled.jsonl.bak_pre_gloss_p1_*'))
    txt_backups = sorted(PROJECT_ROOT.glob('English Academic Vocabulary.txt.bak_pre_gloss_p1_*'))

    if not master_backups or not filled_backups or not txt_backups:
        print("ERROR: Missing pre-P1 backups for comparison.")
        return 1

    master_bak_path = master_backups[-1]
    filled_bak_path = filled_backups[-1]
    txt_bak_path = txt_backups[-1]

    print("=" * 80)
    print("P1 SEMANTIC GLOSS CLEANUP VERIFICATION REPORT")
    print("=" * 80)
    print(f"Comparing active files against backups:")
    print(f"  Master: {MASTER.name} vs {master_bak_path.name}")
    print(f"  Filled: {FILLED.name} vs {filled_bak_path.name}")
    print(f"  TXT:    {TXT.name} vs {txt_bak_path.name}")
    print("-" * 80)

    # Load rows
    m_before = load_audit(master_bak_path)
    m_after = load_audit(MASTER)
    f_before = load_audit(filled_bak_path)
    f_after = load_audit(FILLED)
    t_before = load_txt(txt_bak_path)
    t_after = load_txt(TXT)

    # Row count checks
    print(f"Row count checks:")
    print(f"  Master: {len(m_before)} -> {len(m_after)} (Expected: Unchanged)")
    print(f"  Filled: {len(f_before)} -> {len(f_after)} (Expected: Unchanged)")
    print(f"  TXT:    {len(t_before)} -> {len(t_after)} (Expected: Unchanged)")
    if len(m_before) != len(m_after) or len(f_before) != len(f_after) or len(t_before) != len(t_after):
        print("WARNING: Row count mismatch detected!")

    # Before / After counts by category
    print("\nBefore / After Validator Debt Counts (Active Files):")
    debt_m_before = collect_debt_stats(m_before)
    debt_m_after = collect_debt_stats(m_after)
    debt_f_before = collect_debt_stats(f_before)
    debt_f_after = collect_debt_stats(f_after)

    all_categories = sorted(set(list(debt_m_before.keys()) + list(debt_m_after.keys()) +
                                 list(debt_f_before.keys()) + list(debt_f_after.keys())))

    print(f"{'Category':30s} | {'Master Before':13s} -> {'Master After':12s} | {'Filled Before':13s} -> {'Filled After':12s}")
    print("-" * 90)
    for cat in all_categories:
        mb = debt_m_before[cat]
        ma = debt_m_after[cat]
        fb = debt_f_before[cat]
        fa = debt_f_after[cat]
        print(f"{cat:30s} | {mb:13d} -> {ma:12d} | {fb:13d} -> {fa:12d}")

    # Touched rows listing, validator check, and txt sync check
    print("\nTouched Rows & Verification:")
    print("-" * 80)
    touched_master = 0
    mismatched_verdicts = 0

    # Build key mapping for TXT after defs
    txt_after_by_key = {}
    for idx, fields in t_after:
        if len(fields) <= 6:
            continue
        word = fields[3]
        pos = fields[4]
        cefr = fields[14] if len(fields) > 14 else ''
        txt_after_by_key[(word, pos, cefr)] = fields[6]

    # Map master after by key for duplicate check
    m_after_keys = Counter()
    for r in m_after:
        m_after_keys[(r['word'], r['pos'], r['cefr'])] += 1

    # Check Master Audit touched rows
    print("\n[Master Audit Touched Rows]")
    for idx, (rb, ra) in enumerate(zip(m_before, m_after), start=1):
        if rb['gloss_after'] != ra['gloss_after']:
            touched_master += 1
            word, pos, cefr = ra['word'], ra['pos'], ra['cefr']
            old_g, new_g = rb['gloss_after'], ra['gloss_after']

            # Run validator on new gloss
            res = normalize_gloss(new_g)
            violations = validate_verdict(word, res.gloss, res.separator, chunk_count(res.gloss))
            has_pos = bool(POS_LABEL_RE.search(res.gloss))
            verdict = "FAIL" if (violations or has_pos) else "PASS"
            if verdict == "FAIL":
                mismatched_verdicts += 1
                details = f"violations={violations}, has_pos={has_pos}"
            else:
                details = ""

            # Check TXT sync
            txt_def = txt_after_by_key.get((word, pos, cefr))
            if txt_def is not None:
                txt_sync = "SYNC_OK" if normalize_gloss(txt_def).gloss == res.gloss else f"SYNC_MISMATCH (TXT has: {txt_def!r})"
            else:
                txt_sync = "NOT_IN_TXT"

            print(f"L{idx:4d} {word} ({pos}, {cefr}):")
            print(f"  Old: {old_g!r}")
            print(f"  New: {new_g!r} -> {verdict} {details}")
            print(f"  TXT: {txt_sync}")

    touched_filled = 0
    print("\n[Filled Audit Touched Rows]")
    for idx, (rb, ra) in enumerate(zip(f_before, f_after), start=1):
        if rb['gloss_after'] != ra['gloss_after']:
            touched_filled += 1
            word, pos, cefr = ra['word'], ra['pos'], ra['cefr']
            old_g, new_g = rb['gloss_after'], ra['gloss_after']

            res = normalize_gloss(new_g)
            violations = validate_verdict(word, res.gloss, res.separator, chunk_count(res.gloss))
            has_pos = bool(POS_LABEL_RE.search(res.gloss))
            verdict = "FAIL" if (violations or has_pos) else "PASS"
            if verdict == "FAIL":
                mismatched_verdicts += 1
                details = f"violations={violations}, has_pos={has_pos}"
            else:
                details = ""

            txt_def = txt_after_by_key.get((word, pos, cefr))
            if txt_def is not None:
                txt_sync = "SYNC_OK" if normalize_gloss(txt_def).gloss == res.gloss else f"SYNC_MISMATCH (TXT has: {txt_def!r})"
            else:
                txt_sync = "NOT_IN_TXT"

            print(f"L{idx:4d} {word} ({pos}, {cefr}):")
            print(f"  Old: {old_g!r}")
            print(f"  New: {new_g!r} -> {verdict} {details}")
            print(f"  TXT: {txt_sync}")

    # Duplicate keys check
    print("\nDuplicate Keys Check:")
    dup_errors = 0
    for key in P2_DEFERRED_KEYS:
        n = m_after_keys.get(key, 0)
        print(f"  {key}: {n} row(s)")
        if n < 2:
            print(f"    ERROR: expected >=2 rows, got {n} (possibility of accidental merge/deletion!)")
            dup_errors += 1

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Master touched: {touched_master}")
    print(f"Filled touched: {touched_filled}")
    print(f"Mismatched validator verdicts: {mismatched_verdicts}")
    print(f"P2 duplicate keys check errors: {dup_errors}")
    print("=" * 80)

    if mismatched_verdicts > 0 or dup_errors > 0:
        print("FAIL: Verification failed with errors.")
        return 1
    else:
        print("PASS: Verification completed successfully.")
        return 0


if __name__ == '__main__':
    sys.exit(main())
