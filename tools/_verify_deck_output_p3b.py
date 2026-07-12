"""P3B Final Deck Output QA Verifier.

Core artifact, Card Identity, registry coverage, order, and card-count
validation belong to ``src.deck_builder.build_validation``. P3B adds
legacy audit/gloss checks without reimplementing registry contracts.
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
from src.deck_builder.build_validation import validate_artifact_paths
from src.deck_builder.sense_labels import parse_existing_prefix

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

paths = ProjectPaths(PROJECT_ROOT)
DECK_TXT = paths.anki_notes_txt
DECK_JSONL = paths.anki_notes_jsonl
MASTER_AUDIT = paths.deck_audit_jsonl

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
        # 0: GUID, 1: notetype, 2: deck, 3: word, 4: pos, 14: cefr, 16: tags
        critical_indices = [0, 1, 2, 3, 4, 14, 16]
        critical_names = ["GUID", "notetype", "deck", "word", "pos", "cefr", "tags"]
        for c_idx, c_name in zip(critical_indices, critical_names):
            if c_idx < len(parts):
                val = parts[c_idx].strip()
                if not val:
                    errors.append(f"Row {idx} has empty critical field '{c_name}'")
            else:
                errors.append(f"Row {idx} is missing index {c_idx} for '{c_name}'")

        if len(parts) > 15 and not parts[6].strip() and not parts[15].strip():
            errors.append(f"Row {idx} has neither a definition nor idioms")

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


def verify_audit_alignment(data_rows: list[list[str]], audit_rows: list[dict]):
    """Check legacy audit-key coverage after core registry validation passes."""
    txt_keys_word_pos_cefr = []

    for parts in data_rows:
        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        txt_keys_word_pos_cefr.append((word, pos, cefr))

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

    registry_key_by_guid = {}
    if paths_reg.card_registry.exists():
        with paths_reg.card_registry.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    guid = (item.get("guid") or "").strip()
                    if guid:
                        registry_key_by_guid[guid] = (
                            (item.get("word") or "").strip(),
                            (item.get("cefr") or "").strip().upper(),
                            (item.get("list") or "").strip(),
                            (item.get("variant") or "").strip(),
                        )

    manual_def_by_guid = {}
    if paths_reg.manual_cards.exists():
        manual_by_key = {}
        with paths_reg.manual_cards.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    key = (
                        (item.get("word") or "").strip(),
                        (item.get("cefr") or "").strip().upper(),
                        (item.get("list") or "").strip(),
                        (item.get("variant") or "").strip(),
                    )
                    manual_by_key[key] = item
        for guid, key in registry_key_by_guid.items():
            manual = manual_by_key.get(key)
            if manual is not None:
                manual_def_by_guid[guid] = manual.get("definition") or ""

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

        override_definition = review_overrides.get(guid, {}).get("Definition")
        if override_definition is not None:
            expected_def = override_definition
        elif guid in manual_def_by_guid:
            expected_def = manual_def_by_guid[guid]
        else:
            expected_def = resolve_expected_definition(word, pos, cefr)

        if expected_def is None:
            not_in_audit_count += 1
            continue

        # Strip sense label prefixes before gloss normalization
        txt_chunks = [ch.strip() for ch in txt_def.split("|") if ch.strip()]
        clean_txt_chunks = [parse_existing_prefix(ch)[1] for ch in txt_chunks]
        txt_def_clean = " | ".join(clean_txt_chunks)
        expected_chunks = [ch.strip() for ch in expected_def.split("|") if ch.strip()]
        clean_expected_chunks = [parse_existing_prefix(ch)[1] for ch in expected_chunks]
        expected_def_clean = " | ".join(clean_expected_chunks)

        txt_norm = normalize_gloss(txt_def_clean).gloss
        expected_norm = normalize_gloss(expected_def_clean).gloss
        
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
    return []


def verify_build_drift(expected_card_count: int):
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
        'built_cards': expected_card_count,
        'missing_in_jsonl': 0,
        'dup_emit_skipped': 0,
    }
    
    for k, v in expected.items():
        val = metrics.get(k)
        if val != v:
            print(f"  ERROR: Build drift metric mismatch for '{k}': expected {v}, got {val}")
            sys.exit(1)
            
    print("  Registry build is canonical; legacy Type A remap inventory is no longer checked here.")


def main() -> int:
    print("=" * 72)
    print("P3B DECK OUTPUT QA VERIFIER")
    print("=" * 72)

    # Load TXT lines
    lines = DECK_TXT.read_text(encoding='utf-8').splitlines()

    print("[0] Running core artifact validation...")
    report = validate_artifact_paths(DECK_JSONL, DECK_TXT, paths.card_registry, paths.audio_dir)
    if not report.ok:
        print("  ERROR: core artifact validation failed")
        print(report.error_text())
        return 1
    print(
        f"  Core validation OK: cards={report.card_count} "
        f"jsonl_sha256={report.jsonl_sha256} txt_sha256={report.txt_sha256}"
    )

    # Load Audit rows
    audit_rows = load_audit_rows()

    print("[1] Verifying TXT structural integrity...")
    data_rows = verify_txt_structure(lines)

    print("[2] Verifying legacy audit alignment...")
    verify_audit_alignment(data_rows, audit_rows)

    print("[3] Verifying Definition Sync...")
    verify_definition_sync(data_rows, audit_rows)

    verify_build_drift(report.card_count)

    print("\nPASS: deck output QA completed successfully.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
