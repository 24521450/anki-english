"""P3B Final Deck Output QA Verifier.

Core artifact, Card Identity, registry coverage, order, and card-count
validation belong to ``src.deck_builder.build_validation``. P3B adds
legacy audit-key checks plus exact Semantic Registry payload sync.
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
from src.deck_builder.build_contracts import CARD_FIELDS
from src.deck_builder.build_validation import validate_artifact_paths

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

paths = ProjectPaths(PROJECT_ROOT)
DECK_TXT = paths.anki_notes_txt
DECK_JSONL = paths.anki_notes_jsonl
MASTER_AUDIT = paths.deck_audit_jsonl
SEMANTIC_REGISTRY = paths.semantic_registry


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


def load_semantic_registry_rows() -> list[dict]:
    rows = []
    with SEMANTIC_REGISTRY.open(encoding="utf-8") as fp:
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
        if len(parts) != len(CARD_FIELDS):
            errors.append(
                f"Row {idx} does not have exactly {len(CARD_FIELDS)} columns "
                f"(found {len(parts)})"
            )
            
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


def verify_definition_sync(
    data_rows: list[list[str]], semantic_rows: list[dict]
) -> None:
    """Verify final bilingual fields against their canonical content owner."""
    expected_by_guid: dict[str, tuple[str, str]] = {}
    duplicate_guids: list[str] = []
    for row in semantic_rows:
        guid = (row.get("guid") or "").strip()
        if guid in expected_by_guid:
            duplicate_guids.append(guid)
            continue
        senses = row.get("senses") or []
        definition = "|".join(
            f"{sense['definition_en']} ({sense['definition_vi']})"
            for sense in senses
        )
        definition_vi = "|".join(sense["definition_vi"] for sense in senses)
        expected_by_guid[guid] = (definition, definition_vi)

    if duplicate_guids:
        print(f"Semantic Registry duplicate GUIDs: {sorted(set(duplicate_guids))[:10]}")
        sys.exit(1)

    guid_index = CARD_FIELDS.index("guid")
    word_index = CARD_FIELDS.index("word")
    definition_index = CARD_FIELDS.index("definition")
    definition_vi_index = CARD_FIELDS.index("definition_vi")
    seen_guids: set[str] = set()
    missing_guids: list[str] = []
    mismatches: list[dict] = []

    for parts in data_rows:
        guid = parts[guid_index]
        seen_guids.add(guid)
        expected = expected_by_guid.get(guid)
        if expected is None:
            missing_guids.append(guid)
            continue
        txt_definition = parts[definition_index]
        txt_definition_vi = parts[definition_vi_index]
        expected_definition, expected_definition_vi = expected
        if (
            txt_definition != expected_definition
            or txt_definition_vi != expected_definition_vi
        ):
            mismatches.append({
                "guid": guid,
                "word": parts[word_index],
                "txt_definition": txt_definition,
                "expected_definition": expected_definition,
                "txt_definition_vi": txt_definition_vi,
                "expected_definition_vi": expected_definition_vi,
            })

    extra_guids = sorted(set(expected_by_guid) - seen_guids)
    synced_count = len(data_rows) - len(missing_guids) - len(mismatches)
    print(
        "  Semantic Registry sync: "
        f"synced={synced_count} missing={len(missing_guids)} "
        f"extra={len(extra_guids)} mismatches={len(mismatches)}"
    )
    if missing_guids or extra_guids or mismatches:
        if missing_guids:
            print(f"  Build GUIDs missing from Semantic Registry: {missing_guids[:10]}")
        if extra_guids:
            print(f"  Semantic Registry GUIDs missing from build: {extra_guids[:10]}")
        if mismatches:
            print("Semantic Registry Definition Mismatches Found:")
            for mismatch in mismatches[:10]:
                print(f"  - ({mismatch['word']}, {mismatch['guid']}):")
                print(f"      TXT Definition:      {mismatch['txt_definition']!r}")
                print(f"      Registry Definition: {mismatch['expected_definition']!r}")
                print(f"      TXT DefinitionVI:      {mismatch['txt_definition_vi']!r}")
                print(f"      Registry DefinitionVI: {mismatch['expected_definition_vi']!r}")
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

    # Load canonical and legacy review artifacts.
    audit_rows = load_audit_rows()
    semantic_rows = load_semantic_registry_rows()

    print("[1] Verifying TXT structural integrity...")
    data_rows = verify_txt_structure(lines)

    print("[2] Verifying legacy audit alignment...")
    verify_audit_alignment(data_rows, audit_rows)

    print("[3] Verifying Semantic Registry Definition Sync...")
    verify_definition_sync(data_rows, semantic_rows)

    verify_build_drift(report.card_count)

    print("\nPASS: deck output QA completed successfully.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
