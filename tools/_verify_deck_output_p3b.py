"""P3B Final Deck Output QA Verifier.

Card Identity contract (2026-06-21): a card is uniquely identified by
`(Word, CEFRLevel, LIST)`. `LIST` is the primary corpus/list bucket
resolved from the card's tags via `primary_list_from_tags`. Hard
duplicate check uses the triple; the legacy `(Word, CEFR)` only check
is reported as informational because list-aware splits (e.g. `firm`
on Oxford_3000 vs Oxford_5000 at the same CEFR) are now legitimate.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths
from src.deck_builder.sense_labels import parse_existing_prefix

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

paths = ProjectPaths(PROJECT_ROOT)
DECK_TXT = paths.anki_notes_txt
MASTER_AUDIT = paths.deck_audit_jsonl

# Primary list priority — highest first. Used by primary_list_from_tags
# to collapse a tag set (which may carry multiple corpus list tags) into
# the single LIST bucket that participates in Card Identity.
LIST_PRIORITY = ("Oxford_5000", "Oxford_3000", "AWL_Coxhead")

# Explicitly reviewed exception to the default one-card-per-list identity rule.
# The two Oxford homonyms have different stress, meanings, and audio.
REVIEWED_HOMONYM_SPLITS = {
    ("converse", "UNCLASSIFIED", "AWL_Coxhead"): frozenset({
        "verb",
        "adjective, noun",
    }),
}


def primary_list_from_tags(tags: str) -> str:
    """Resolve the primary LIST bucket from a tags string.

    Card Identity = (Word, CEFR, LIST). A card may carry multiple corpus
    list tags (e.g. "Source::Oxford CEFR::B2 CEFR::oxford Oxford_5000 AWL");
    only the highest-priority tag contributes to identity, per the fixed
    priority `Oxford_5000 > Oxford_3000 > AWL > NO_LIST`.

    Returns one of: `Oxford_5000`, `Oxford_3000`, `AWL`, `NO_LIST`.
    `NO_LIST` is a valid identity bucket for cards without any curated
    list tag (e.g. Oxford proper nouns).
    """
    tokens = set((tags or '').split())
    for item in LIST_PRIORITY:
        if item in tokens:
            return item
    return "NO_LIST"


from src.deck_builder.gloss_hygiene import normalize_gloss


def run_command_capture(cmd: list[str], cwd: Path) -> tuple[int, str]:
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=cwd)
    return res.returncode, res.stdout


def load_audit_rows() -> list[dict]:
    rows = []
    if not MASTER_AUDIT.exists():
        return rows
    with MASTER_AUDIT.open(encoding='utf-8') as fp:
        for line in fp:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def verify_txt_structure(lines: list[str]) -> list[list[str]]:
    data_rows = []
    guids = set()
    errors = []

    # 1. Structural checks
    for idx, line in enumerate(lines, 1):
        if line.startswith('#'):
            continue
        if not line.strip():
            continue
        
        parts = line.split('\t')
        data_rows.append(parts)
        
        # Check tab column count
        if len(parts) != 19:
            errors.append(f"Row {idx} does not have exactly 19 columns (found {len(parts)})")
            
        # Check critical fields non-empty
        # 0: GUID, 1: notetype, 2: deck, 3: word, 4: pos, 6: definition, 14: cefr, 16: tags
        critical_indices = [0, 1, 2, 3, 4, 6, 14, 16]
        critical_names = ["GUID", "notetype", "deck", "word", "pos", "definition", "cefr", "tags"]
        for c_idx, c_name in zip(critical_indices, critical_names):
            if c_idx < len(parts):
                val = parts[c_idx].strip()
                if not val:
                    errors.append(f"Row {idx} has empty critical field '{c_name}'")
            else:
                errors.append(f"Row {idx} is missing index {c_idx} for '{c_name}'")

        # Check GUID uniqueness
        if len(parts) > 0:
            guid = parts[0]
            if guid in guids:
                errors.append(f"Row {idx} has duplicate GUID: '{guid}'")
            guids.add(guid)

        # Check no literal \|
        if any('\\|' in p for p in parts):
            errors.append(f"Row {idx} contains literal escaped pipe '\\|'")

        # Check no malformed newline or tab inside fields
        for col_idx, p in enumerate(parts):
            if '\n' in p or '\r' in p or '\t' in p:
                errors.append(f"Row {idx} column {col_idx} contains newline or tab character")

    # Assert row count
    if len(data_rows) != 2452:
        errors.append(f"Expected exactly 2452 data rows, but found {len(data_rows)}")

    if errors:
        print("TXT Structural Integrity Errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  - ... and {len(errors) - 10} more errors")
        sys.exit(1)

    print(f"  TXT rows count: {len(data_rows)}")
    print(f"  TXT columns count: {len(data_rows[0]) if data_rows else 0}")
    print(f"  GUID duplicates: 0")
    print(f"  Escaped pipes: 0")
    return data_rows


def verify_card_identity(data_rows: list[list[str]], audit_rows: list[dict]):
    # Normalize word, pos, cefr, list for uniqueness checks.
    # Card Identity contract (2026-06-21): `(Word, CEFR, LIST)`.
    # LIST is resolved from the card's tags via primary_list_from_tags.
    txt_keys_word_cefr = []
    txt_keys_word_pos_cefr = []
    txt_keys_word_cefr_list = []

    for parts in data_rows:
        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        tags = parts[16].strip() if len(parts) > 16 else ''
        primary_list = primary_list_from_tags(tags)
        txt_keys_word_cefr.append((word, cefr))
        txt_keys_word_pos_cefr.append((word, pos, cefr))
        txt_keys_word_cefr_list.append((word, cefr, primary_list))

    # TXT (Word, CEFR, LIST) duplicates check — HARD IDENTITY CONTRACT.
    # A duplicate here is a real bug (e.g. same word emitted twice on the
    # same list at the same CEFR, perhaps via Type A POS remap).
    unique_word_cefr_list = set(txt_keys_word_cefr_list)
    txt_word_cefr_list_dups = []
    for key in unique_word_cefr_list:
        if txt_keys_word_cefr_list.count(key) <= 1:
            continue
        positions = frozenset(
            parts[4].strip().lower()
            for parts, row_key in zip(data_rows, txt_keys_word_cefr_list)
            if row_key == key
        )
        if REVIEWED_HOMONYM_SPLITS.get(key) == positions:
            continue
        txt_word_cefr_list_dups.append(key)
    print(f"  TXT (word, CEFR, LIST) duplicates: {len(txt_word_cefr_list_dups)}")
    if txt_word_cefr_list_dups:
        print(f"    Duplicates found: {txt_word_cefr_list_dups}")
        sys.exit(1)

    # TXT (Word, CEFR) duplicates — INFORMATIONAL ONLY.
    # Legacy (pre-2026-06-21) check. With list-aware identity, the same
    # (word, CEFR) can legitimately appear on multiple lists (e.g. `firm`
    # on Oxford_3000 and Oxford_5000 at B2). Report count but do NOT fail.
    unique_word_cefr = set(txt_keys_word_cefr)
    txt_word_cefr_dups = [k for k in unique_word_cefr if txt_keys_word_cefr.count(k) > 1]
    print(f"  TXT (word, CEFR) duplicates (informational): {len(txt_word_cefr_dups)}")
    if txt_word_cefr_dups:
        # Show the (word, CEFR) → [list...] mapping for visibility.
        from collections import defaultdict
        cefr_to_lists = defaultdict(set)
        for (w, c), lst in zip(txt_keys_word_cefr, [
            primary_list_from_tags(parts[16].strip() if len(parts) > 16 else '')
            for parts in data_rows
        ]):
            cefr_to_lists[(w, c)].add(lst)
        sample = sorted(txt_word_cefr_dups)[:10]
        for k in sample:
            print(f"    {k} appears across lists: {sorted(cefr_to_lists[k])}")

    # TXT (Word, pos, CEFR) duplicates check — HARD contract.
    # A duplicate here is a real bug: same word + same POS + same CEFR
    # emitted as 2 cards in the TXT (build pipeline emitted the same card
    # twice under different GUIDs).
    unique_word_pos_cefr = set(txt_keys_word_pos_cefr)
    txt_word_pos_cefr_dups = [k for k in unique_word_pos_cefr if txt_keys_word_pos_cefr.count(k) > 1]
    print(f"  TXT (word, pos, CEFR) duplicates: {len(txt_word_pos_cefr_dups)}")
    if txt_word_pos_cefr_dups:
        print(f"    Duplicates found: {txt_word_pos_cefr_dups}")
        sys.exit(1)

    # Audit master duplicates check (audit keyed by (word, pos, cefr)).
    # Audit master keys already disambiguate by POS, so a duplicate here
    # would be an audit-side bug independent of the build pipeline.
    audit_keys = []
    for r in audit_rows:
        audit_keys.append((r['word'].strip().lower(), r['pos'].strip().lower(), r['cefr'].strip().upper()))
        
    unique_audit = set(audit_keys)
    audit_dups = [k for k in unique_audit if audit_keys.count(k) > 1]
    print(f"  Audit duplicate keys: {len(audit_dups)}")
    if audit_dups:
        print(f"    Audit duplicates: {audit_dups}")
        sys.exit(1)

    # Check for missing matching audit glosses
    # We load audit glosses into a dict for quick lookup
    audit_gloss_map = {}
    for r in audit_rows:
        k = (r['word'].strip().lower(), r['pos'].strip().lower(), r['cefr'].strip().upper())
        audit_gloss_map[k] = r.get('gloss_after') or ''

    missing_in_audit = []
    for (word, pos, cefr) in txt_keys_word_pos_cefr:
        # Check direct match
        if (word, pos, cefr) not in audit_gloss_map:
            # Replicate build_notes.py POS parsing to see if it matches individual POS parts
            pos_parts = [p.strip().lower() for p in pos.split(',') if p.strip()]
            matched = False
            for p in pos_parts:
                if (word, p, cefr) in audit_gloss_map:
                    matched = True
                    break
            if not matched:
                missing_in_audit.append((word, pos, cefr))

    print(f"  TXT cards not matching direct audit keys (legacy/non-Oxford scope): {len(missing_in_audit)}")
    if missing_in_audit and len(missing_in_audit) < 50:
        print(f"    Sample not-in-audit cards: {missing_in_audit[:10]}")


def verify_definition_sync(data_rows: list[list[str]], audit_rows: list[dict]):
    # Load audit glosses
    audit_gloss_map = {}
    for r in audit_rows:
        k = (r['word'].strip().lower(), r['pos'].strip().lower(), r['cefr'].strip().upper())
        audit_gloss_map[k] = r.get('gloss_after') or ''

    # Load review overrides by GUID
    from src.config import ProjectPaths
    paths_reg = ProjectPaths()
    review_file = paths_reg.non_oxford_non_c2_overrides
    review_overrides = {}
    if review_file.exists():
        with review_file.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    guid = item.get("guid")
                    if guid:
                        review_overrides[guid] = item

    synced_count = 0
    not_in_audit_count = 0
    mismatches = []

    # Re-implement lookup_gloss logic for comparison
    def resolve_expected_definition(word: str, pos: str, cefr: str) -> str | None:
        # Since TXT is built post-POS/lemmatize fixes, (word, pos, cefr) should match resolved keys.
        pos_parts = [p.strip().lower() for p in pos.split(',') if p.strip()]
        
        # 1. Direct match
        if (word, pos, cefr) in audit_gloss_map:
            return audit_gloss_map[(word, pos, cefr)]
            
        # 2. Individual POS parts
        matched_glosses = []
        seen_glosses = set()
        for p in pos_parts:
            # Check keys
            for gk in [(word, p, cefr)]:
                if gk in audit_gloss_map:
                    g = audit_gloss_map[gk]
                    if g not in seen_glosses:
                        matched_glosses.append(g)
                        seen_glosses.add(g)
                    break
                    
        if matched_glosses:
            return ' | '.join(matched_glosses)
        return None

    for parts in data_rows:
        guid = parts[0]
        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        txt_def = parts[6]

        if guid in review_overrides:
            expected_def = review_overrides[guid]["Definition"]
        else:
            expected_def = resolve_expected_definition(word, pos, cefr)

        if expected_def is None:
            not_in_audit_count += 1
            continue

        # Strip sense label prefixes before gloss normalization
        txt_chunks = [ch.strip() for ch in txt_def.split("|") if ch.strip()]
        clean_txt_chunks = [parse_existing_prefix(ch)[1] for ch in txt_chunks]
        txt_def_clean = " | ".join(clean_txt_chunks)

        txt_norm = normalize_gloss(txt_def_clean).gloss
        expected_norm = normalize_gloss(expected_def).gloss
        
        if txt_norm != expected_norm:
            mismatches.append({
                'word': word,
                'pos': pos,
                'cefr': cefr,
                'txt_def': txt_def,
                'expected_def': expected_def,
                'txt_norm': txt_norm,
                'expected_norm': expected_norm
            })
        else:
            synced_count += 1

    print(f"  Definition sync: synced={synced_count}  not-in-audit={not_in_audit_count}  mismatches={len(mismatches)}")
    if mismatches:
        print("Definition Mismatches Found:")
        for m in mismatches[:10]:
            print(f"  - ({m['word']}, {m['pos']}, {m['cefr']}):")
            print(f"      TXT:      {m['txt_def']!r}")
            print(f"      Expected: {m['expected_def']!r}")
        sys.exit(1)


def parse_build_output(stdout: str) -> dict:
    metrics = {}
    
    # Simple regex extraction
    patterns = {
        'existing_cards': r'(?:existing cards|built cards):\s*(\d+)',
        'built_cards': r'(?:built cards):\s*(\d+)',
        'missing_in_jsonl': r'missing in jsonl:\s*(\d+)',
        'dup_emit_skipped': r'Dup emit skipped:\s*(\d+)',
        'audit_glosses': r'audit glosses loaded:\s*(\d+)',
    }
    
    for key, pat in patterns.items():
        m = re.search(pat, stdout)
        if m:
            metrics[key] = int(m.group(1))
            
    return metrics


def extract_type_a_keys(stdout: str) -> list[tuple[str, str, str]]:
    # We can parse Type A POS fix keys from the output logs if build_notes outputs them,
    # or print them.
    # In build_notes.py:
    # "pos_fixed_keys.append((key, 'A', tuple(resolved_pos_parts)))"
    # Wait! build_notes.py does not print individual keys unless we extract them, but it prints:
    # "Type A (POS fix): 4"
    # To get the exact 4 keys, we can inspect build_notes.py execution or re-run the POS resolution
    # logic over all existing keys.
    # Let's re-run the POS resolution logic in a read-only way to list the 4 keys!
    from tools.build_notes import _parse_existing_txt, get_word_candidates, _source_label, POS_NORM, PROJECT_ROOT
    
    existing = _parse_existing_txt(DECK_TXT)
    
    # Load oxford.jsonl words and POS data
    by_word = {}
    with (paths.oxford_jsonl).open(encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            w = (r.get('word') or '').lower()
            if w:
                by_word.setdefault(w, []).append(r)
                
    word_pos_set = {}
    for word_lower, records in by_word.items():
        ps = set()
        for record in records:
            for pd in record.get('pos_data', []) or []:
                p = pd.get('pos')
                if p:
                    ps.add(p)
        word_pos_set[word_lower] = ps

    type_a_keys = []
    
    # Filter out filled keys to match build_notes logic
    FILLED_PATH = paths.manual_card_fills
    filled_keys = set()
    if FILLED_PATH.exists():
        try:
            filled_data = json.load(FILLED_PATH.open(encoding='utf-8'))
            for r in filled_data:
                filled_keys.add((
                    (r.get('word') or '').strip().lower(),
                    (r.get('pos') or '').strip().lower(),
                    (r.get('cefr') or '').strip().upper()
                ))
        except Exception:
            pass

    for key in sorted(existing.keys()):
        word_lower, pos_str, cefr = key
        if key in filled_keys:
            continue
            
        pos_parts = [p.strip() for p in pos_str.split(',') if p.strip()]
        cands = get_word_candidates(word_lower)
        matched_records = []
        resolved_word = word_lower
        for cand in cands:
            if cand in by_word:
                matched_records = by_word[cand]
                resolved_word = cand
                break
                
        avail = word_pos_set.get(resolved_word, set())
        has_overlap = any(p in avail for p in pos_parts)
        resolved_pos_parts = []
        if has_overlap:
            resolved_pos_parts = pos_parts
        else:
            seen_pos = set()
            for p in pos_parts:
                if p in avail:
                    if p not in seen_pos:
                        resolved_pos_parts.append(p)
                        seen_pos.add(p)
                elif avail:
                    cand = next(iter(sorted(avail)))
                    if cand not in seen_pos:
                        resolved_pos_parts.append(cand)
                        seen_pos.add(cand)
                        
        if resolved_word == word_lower and resolved_pos_parts != pos_parts:
            type_a_keys.append((key, resolved_pos_parts))
            
    return type_a_keys


def verify_build_drift():
    print("[4] Verifying build dry-run outputs and drift...")
    cmd = [sys.executable, '-m', 'tools.build_notes', '--dry-run']
    ret, out = run_command_capture(cmd, PROJECT_ROOT)
    
    if ret != 0:
        print(f"  ERROR: build_notes --dry-run failed with exit code {ret}")
        print(out)
        sys.exit(1)
        
    metrics = parse_build_output(out)
    print(f"  build dry-run: cards={metrics.get('built_cards')} missing={metrics.get('missing_in_jsonl')} dup_emit_skipped={metrics.get('dup_emit_skipped')}")
    
    # Assert build metrics
    expected = {
        'built_cards': 2452,
        'missing_in_jsonl': 0,
        'dup_emit_skipped': 0,
    }
    
    for k, v in expected.items():
        val = metrics.get(k)
        if val != v:
            print(f"  ERROR: Build drift metric mismatch for '{k}': expected {v}, got {val}")
            sys.exit(1)
            
    # Extract Type A keys
    type_a = extract_type_a_keys(out)
    print(f"  Type A keys found ({len(type_a)}):")
    for key, new_pos in type_a:
        print(f"    - {key} remapped to {new_pos}")
        
    # Standard classification
    # These 4 POS-fixes are expected behaviors mapping deck card definitions
    # to Oxford POS sections, matching design contracts.
    assert len(type_a) == 4, f"Expected exactly 4 Type A keys, found {len(type_a)}"


def main() -> int:
    print("=" * 72)
    print("P3B DECK OUTPUT QA VERIFIER")
    print("=" * 72)

    # Load TXT lines
    lines = DECK_TXT.read_text(encoding='utf-8').splitlines()

    # Load Audit rows
    audit_rows = load_audit_rows()

    print("[1] Verifying TXT structural integrity...")
    data_rows = verify_txt_structure(lines)

    print("[2] Verifying Card Identity...")
    verify_card_identity(data_rows, audit_rows)

    print("[3] Verifying Definition Sync...")
    verify_definition_sync(data_rows, audit_rows)

    verify_build_drift()

    print("\nPASS: deck output QA completed successfully.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
