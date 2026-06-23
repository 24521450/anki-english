"""Shared mechanics for audit full deck JSONL and vocabulary TXT patching.

Provides a clean public Interface to load, validate, match, and write updates deterministically.
"""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path
from typing import NamedTuple, Callable, Any

class AuditPatchPaths(NamedTuple):
    audit_jsonl_path: Path
    txt_path: Path
    ledger_path: Path | None = None

class AuditPatchResult(NamedTuple):
    updated_audit_text: str
    updated_txt_text: str
    matched_count: int
    replaced_count: int
    deferred_count: int
    validation_errors: list[str]

def load_jsonl(path: Path) -> list[dict]:
    """Reads a JSON Lines file into a list of dicts."""
    if not path.exists():
        raise FileNotFoundError(f'Not found: {path}')
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]

def write_jsonl_text(rows: list[dict]) -> str:
    """Serializes a list of dicts to a JSON Lines string with exactly one trailing newline."""
    if not rows:
        return ""
    return '\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n'

def parse_txt_rows(text: str) -> list[list[str] | str]:
    """Parses a TSV vocabulary text file.
    
    Preserves header lines (beginning with '#'), blank lines, and malformed lines (fewer than 17 columns)
    as raw string rows so they can round-trip unchanged.
    """
    rows: list[list[str] | str] = []
    for line in text.splitlines():
        if line.startswith('#') or not line.strip():
            rows.append(line)
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            rows.append(line)
        else:
            rows.append(parts)
    return rows

def replace_txt_definition_cells(
    txt_text: str,
    new_gloss_by_key: dict[tuple[str, str, str], str],
) -> tuple[str, int, set[tuple[str, str, str]]]:
    """Updates column index 6 (Definition) only for 17-column data rows keyed by (word, pos, cefr) in lowercase/uppercase.
    
    Returns (updated_txt_text, replaced_count, deferred_keys).
    """
    lines = txt_text.splitlines()
    new_lines: list[str] = []
    replaced_count = 0
    seen_keys: set[tuple[str, str, str]] = set()

    for line in lines:
        if line.startswith('#') or not line.strip():
            new_lines.append(line)
            continue
        parts = line.split('\t')
        if len(parts) < 17:
            new_lines.append(line)
            continue

        word = parts[3].strip().lower()
        pos = parts[4].strip().lower()
        cefr = parts[14].strip().upper()
        key = (word, pos, cefr)
        seen_keys.add(key)

        if key in new_gloss_by_key:
            parts[6] = new_gloss_by_key[key]
            new_lines.append('\t'.join(parts))
            replaced_count += 1
        else:
            new_lines.append(line)

    deferred_keys = {k for k in new_gloss_by_key if k not in seen_keys}
    updated_txt_text = '\n'.join(new_lines)
    if txt_text.endswith('\n') and not updated_txt_text.endswith('\n'):
        updated_txt_text += '\n'
    return updated_txt_text, replaced_count, deferred_keys

def match_by_guard(
    audit_rows: list[dict],
    decisions: list[dict],
    audit_guard_fn: Callable[[dict], tuple],
    decision_guard_fn: Callable[[dict], tuple] | None = None,
) -> dict[tuple, dict]:
    """Validates and performs exact 1-to-1 matching between decisions and audit rows.
    
    Raises ValueError listing unmatched/ambiguous guards if diagnostics fail.
    """
    if decision_guard_fn is None:
        decision_guard_fn = audit_guard_fn

    audit_by_guard: dict[tuple, list[dict]] = {}
    for r in audit_rows:
        g = audit_guard_fn(r)
        audit_by_guard.setdefault(g, []).append(r)

    unmatched: list[dict] = []
    ambiguous: list[tuple] = []
    matched: dict[tuple, dict] = {}

    for d in decisions:
        g = decision_guard_fn(d)
        rows = audit_by_guard.get(g, [])
        if len(rows) == 0:
            unmatched.append(d)
        elif len(rows) > 1:
            ambiguous.append(g)
        else:
            matched[g] = rows[0]

    if unmatched or ambiguous:
        err_msg = []
        if unmatched:
            err_msg.append(f"NO AUDIT MATCH: {len(unmatched)} decisions have no matching audit row.")
            for d in unmatched[:5]:
                word = d.get('word') or d.get('guard_word') or '?'
                pos = d.get('pos') or d.get('guard_pos') or '?'
                cefr = d.get('cefr') or d.get('guard_cefr') or '?'
                err_msg.append(f"  ({word}, {pos}, {cefr})")
        if ambiguous:
            err_msg.append(f"AMBIGUOUS: {len(ambiguous)} decisions matched multiple audit rows.")
            for g in ambiguous[:5]:
                err_msg.append(f"  {g}")
        raise ValueError("\n".join(err_msg))

    return matched

def backup_and_write(paths: AuditPatchPaths, result: AuditPatchResult, label: str) -> None:
    """Creates timestamped pre-apply backups of audit, TXT, and optional ledger, then writes modifications."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Backup audit
    audit_bak = paths.audit_jsonl_path.with_suffix(paths.audit_jsonl_path.suffix + f'.bak_pre_{label}_{ts}')
    audit_bak.write_text(paths.audit_jsonl_path.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  Audit backup: {audit_bak.name}')

    # Backup TXT
    txt_bak = paths.txt_path.with_suffix(paths.txt_path.suffix + f'.bak_pre_{label}_{ts}')
    txt_bak.write_text(paths.txt_path.read_text(encoding='utf-8'), encoding='utf-8')
    print(f'  TXT backup:   {txt_bak.name}')

    # Optional backup ledger
    if paths.ledger_path and paths.ledger_path.exists():
        ledger_label = 'p5' if label == 'p5_precision_phrase' else label
        ledger_bak = paths.ledger_path.with_suffix(paths.ledger_path.suffix + f'.bak_pre_{ledger_label}_{ts}')
        ledger_bak.write_text(paths.ledger_path.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'  Ledger backup: {ledger_bak.name}')

    # Write audit
    paths.audit_jsonl_path.write_text(result.updated_audit_text, encoding='utf-8')
    print(f'  Wrote audit:  {paths.audit_jsonl_path.name} ({len(result.updated_audit_text.splitlines())} rows)')

    # Write TXT
    paths.txt_path.write_text(result.updated_txt_text, encoding='utf-8')
    print(f'  Wrote TXT:    {paths.txt_path.name}')
