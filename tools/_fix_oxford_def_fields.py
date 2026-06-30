"""One-shot fixer: backfill `countability`, `register_tags`, `domain`, and
`opal` fields in `data/sources/oxford.jsonl` from cache HTML.

Scope (4 fields):
  1. register_tags  — PARSER BUG FIX. Selector was `span.reg` (0 hits);
     correct selector is `span.labels`. Compounds like
     "(British English, informal)" are split on "," and each part is
     classified independently.
  2. countability   — NEW FIELD. Per-def, nouns only. Extracted from
     `span.grammar` text matching countability family
     ([C], [U], [C, U], [countable], [uncountable], [countable, uncountable]).
  3. domain         — NEW FIELD. Per-def. Extracted from `span.labels`
     text where a single part matches one of the 23 academic subjects
     in data/oxford_labels.json → subject_labels.
  4. opal           — NEW FIELD. Record-level. Extracted from
     `span.opal_symbol` or `.symbols` text content matching
     "OPAL W" / "OPAL S" / "OPAL WS".

Skipped:
  - records with _skip: true (left byte-identical)
  - records with missing source_files in cache (logged as [NEEDS REVIEW])

Output (v3 contract): writes IN-PLACE to jsonl_in atomically (via
.tmp + os.replace). No separate .fixed.jsonl file. v2's read-A-write-B
pattern was removed because the manual rename step was missed at
least 3 times in this codebase, leading to "data not promoted"
failures where Fix 4 (opal) ran successfully on a previous
invocation but the output was never copied over. Atomic in-place
write removes that entire failure class.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Optional

from lxml import html as lxml_html

# 17 register_tags = 12 from register_labels + 5 from usage_restrictions
# (data/oxford_labels.json). The user explicitly chose B1 (both lists).
# This covers the full set of "register/style" markers Oxford uses in
# span.labels — not just the academic register_labels subset.
REGISTER_TAGS = frozenset({
    # From register_labels (12)
    "approving", "disapproving", "figurative", "formal", "humorous",
    "informal", "ironic", "literary", "offensive", "slang", "specialist", "taboo",
    # From usage_restrictions (5)
    "dialect", "old-fashioned", "old use", "saying", "trademark",
})

# Countability regex patterns
COUNTABILITY_PATTERNS = [
    # (regex, output_value) — order matters: more specific first
    (re.compile(r"\[\s*c\s*,\s*u\s*\]", re.IGNORECASE), "both"),
    (re.compile(r"\[\s*countable\s*,\s*uncountable\s*\]", re.IGNORECASE), "both"),
    (re.compile(r"\[\s*u\s*\]", re.IGNORECASE), "uncountable"),
    (re.compile(r"\[\s*uncountable\s*\]", re.IGNORECASE), "uncountable"),
    (re.compile(r"\[\s*c\s*\]", re.IGNORECASE), "countable"),
    (re.compile(r"\[\s*countable\s*\]", re.IGNORECASE), "countable"),
]

# Pre-compiled for fast label parsing
_LABEL_RE = re.compile(r"\s*,\s*")
_PAREN_RE = re.compile(r"^\(|\)$")


# ── Pure functions (testable) ─────────────────────────────────────────────────


def parse_label_compound(label_text: str, subject_labels: set[str]) -> dict:
    """Parse a span.labels text value into structured register_tags and domain.

    Strategy:
      1. Strip outer parens
      2. Split on "," (compound handling — 10.7% of labels are compound)
      3. For each part: strip whitespace, lowercase
      4. Classify:
         - if part ∈ REGISTER_TAGS → add to register_tags
         - if part ∈ subject_labels → set domain (first match wins, single value)
         - else → drop (regional variants, qualifiers, multi-word combos)

    Returns:
        {"register_tags": list[str], "domain": str | None}
    """
    out = {"register_tags": [], "domain": None}
    if not label_text:
        return out
    # Strip outer parens
    text = label_text.strip()
    text = _PAREN_RE.sub("", text).strip()
    if not text:
        return out
    # Split compound
    parts = _LABEL_RE.split(text)
    for part in parts:
        p = part.strip().lower()
        if not p:
            continue
        if p in REGISTER_TAGS and p not in out["register_tags"]:
            out["register_tags"].append(p)
        if p in subject_labels and out["domain"] is None:
            out["domain"] = p
    return out


def extract_labels_for_def(html, sense_el, subject_labels: set[str]) -> dict:
    """Extract register_tags and domain from a sense element.

    Returns:
        {"register_tags": list[str], "domain": str | None}
    """
    out = {"register_tags": [], "domain": None}
    for lbl in sense_el.cssselect("span.labels"):
        t = (lbl.text_content() or "").strip()
        if t:
            parsed = parse_label_compound(t, subject_labels)
            for r in parsed["register_tags"]:
                if r not in out["register_tags"]:
                    out["register_tags"].append(r)
            if out["domain"] is None and parsed["domain"]:
                out["domain"] = parsed["domain"]
    return out


def extract_labels_for_def(html, sense_el, subject_labels: set[str]) -> dict:
    """Extract register_tags and domain from a sense element.

    Returns:
        {"register_tags": list[str], "domain": str | None}
    """
    out = {"register_tags": [], "domain": None}
    for lbl in sense_el.cssselect("span.labels"):
        t = (lbl.text_content() or "").strip()
        if t:
            parsed = parse_label_compound(t, subject_labels)
            for r in parsed["register_tags"]:
                if r not in out["register_tags"]:
                    out["register_tags"].append(r)
            if out["domain"] is None and parsed["domain"]:
                out["domain"] = parsed["domain"]
    return out


def extract_grammar_for_def(grammar_text: str, pos: str) -> Optional[str]:
    """Extract countability from span.grammar text. Returns None for non-noun."""
    if not grammar_text or pos != "noun":
        return None
    for pattern, value in COUNTABILITY_PATTERNS:
        if pattern.search(grammar_text):
            return value
    return None


# OPAL detection: page-top badge
# Real Oxford HTML: <span class="opal_symbol">OPAL W</span> (most common)
# or <span class="opal_symbol">OPAL S</span> or "OPAL WS" (rare)
# Some pages also have <div class="... opal_written"> with empty text (CSS hint only).
# We rely on the .opal_symbol text content.
OPAL_TEXT_PATTERNS = [
    # (regex, value) — most specific first
    (re.compile(r"\bOPAL\s+WS\b", re.IGNORECASE), "WS"),
    (re.compile(r"\bOPAL\s+W\b", re.IGNORECASE), "W"),
    (re.compile(r"\bOPAL\s+S\b", re.IGNORECASE), "S"),
]


def extract_opal_from_root(root) -> Optional[str]:
    """Extract OPAL value from page-top .symbols or span.opal_symbol.

    Returns "W" / "S" / "WS" / None.
    """
    if root is None:
        return None
    # 1. span.opal_symbol (most reliable — text directly)
    for s in root.cssselect("span.opal_symbol"):
        t = (s.text_content() or "").strip()
        if not t:
            continue
        for pattern, value in OPAL_TEXT_PATTERNS:
            if pattern.search(t):
                return value
    # 2. .symbols text content (fallback — only if .opal_symbol didn't match)
    for s in root.cssselect(".symbols"):
        t = (s.text_content() or "").strip()
        if not t or "OPAL" not in t.upper():
            continue
        for pattern, value in OPAL_TEXT_PATTERNS:
            if pattern.search(t):
                return value
    return None


# ── Record-level fixer ───────────────────────────────────────────────────────


def _load_subject_labels(labels_path: Path) -> set[str]:
    """Load the 23 academic subject_labels from data/oxford_labels.json."""
    with labels_path.open(encoding="utf-8") as f:
        data = json.load(f)
    return set(s.lower() for s in data.get("subject_labels", []))


def _resolve_sense_to_html(
    record: dict,
    cache_dir: Path,
) -> Optional[tuple[object, object, list[object]]]:
    """Load the source HTML and return (root, sense_elements, none).

    Returns None if the file is missing.
    For records with multiple source_files, loads the FIRST one only
    (per spec: 'use the source file whose POS matches the pos_data entry' is
    handled at the per-pos level in fix_record).
    """
    if record.get("_skip"):
        return None
    source_files = record.get("source_files", [])
    if not source_files:
        return None
    fpath = cache_dir / source_files[0]
    if not fpath.exists():
        return None
    try:
        tree = lxml_html.parse(str(fpath))
        return tree.getroot()
    except Exception:
        return None


def _classify_into_register_and_domain(
    parsed: dict, all_label_parts_lower: list[str], subject_labels: set[str]
) -> dict:
    """Take parsed {register_tags, domain} and re-classify each part against
    subject_labels to set domain.
    """
    # Already-classified register_tags stays
    # Re-walk all_label_parts_lower to find domain match
    for part in all_label_parts_lower:
        if part in subject_labels:
            parsed["domain"] = part
            break
    return parsed


def _extract_label_parts(html, sense_el) -> list[str]:
    """Extract all individual label parts (lowercased, parens stripped, split)."""
    parts = []
    for lbl in sense_el.cssselect("span.labels"):
        t = (lbl.text_content() or "").strip()
        if not t:
            continue
        text = _PAREN_RE.sub("", t).strip()
        if text:
            for p in _LABEL_RE.split(text):
                p = p.strip().lower()
                if p:
                    parts.append(p)
    return parts


def fix_record(
    record: dict,
    cache_dir: Path,
    labels_path: Path,
) -> tuple[dict, list[str]]:
    """Apply 3 fixes to a record. Returns (new_record, log_lines).

    Log format per spec:
      [FIXED]        <word> | Fix <1|2|3> | <field>: <old> → <new> (sense <n>)
      [NEEDS REVIEW] <word> | <reason>
      [NO CHANGE]    <word> | all fields already correct
    """
    log_lines = []
    word = record.get("word", "<unknown>")

    # 1. Skip check (byte-identical pass-through)
    if record.get("_skip"):
        log_lines.append(f"[SKIP] {word} | _skip=true (byte-identical)")
        return record, log_lines

    # 2. Resolve HTML
    root = _resolve_sense_to_html(record, cache_dir)
    if root is None:
        log_lines.append(f"[NEEDS REVIEW] {word} | missing source HTML: {record.get('source_files', [])}")
        return record, log_lines

    # 3. Load subject_labels (for domain classification)
    subject_labels = _load_subject_labels(labels_path)

    # 4. Process each pos_data entry
    new_record = copy.deepcopy(record)
    has_any_change = False

    # ── Fix 4: opal (record-level) ─────────────────────────────────────
    # Backfill from cache HTML. Only patch if currently null.
    if new_record.get("opal") is None:
        opal_value = extract_opal_from_root(root)
        if opal_value is not None:
            new_record["opal"] = opal_value
            log_lines.append(
                f"[FIXED] {word} | Fix 4 | opal: None → {opal_value!r}"
            )
            has_any_change = True

    for pd in new_record.get("pos_data", []):
        pos = pd.get("pos", "")
        # Find sense elements matching this pos — for now we use all senses
        # from the source file (multi-pos handling is future enhancement)
        sense_elements = root.cssselect("li.sense")

        for defn in pd.get("definitions", []):
            sense_num = defn.get("sensenum_local", "?")
            # Find matching sense element by sensenum
            matching_sense = None
            for se in sense_elements:
                if se.get("sensenum") == sense_num:
                    matching_sense = se
                    break
            if matching_sense is None:
                continue

            # ── Fix 2: countability (new field) ─────────────────────────────
            # ALWAYS set countability per spec ("Set countability: null for any
            # definition whose parent pos is not noun"). This makes the field
            # explicit in the output, even if null.
            if "countability" not in defn:
                grammar_text = ""
                for g in matching_sense.cssselect("span.grammar"):
                    t = (g.text_content() or "").strip()
                    if t:
                        grammar_text = (grammar_text + " " + t).strip()
                cb = extract_grammar_for_def(grammar_text, pos)
                defn["countability"] = cb
                if cb is not None:
                    log_lines.append(
                        f"[FIXED] {word} | Fix 2 | countability: <unset> → {cb!r} (sense {sense_num})"
                    )
                    has_any_change = True
                # else: countability=null is set but counts as "no real change" for log

            # ── Fix 1: register_tags (bug fix) ──────────────────────────────
            current_rt = defn.get("register_tags", [])
            if not current_rt:
                parsed = extract_labels_for_def(root, matching_sense, subject_labels)
                if parsed["register_tags"]:
                    defn["register_tags"] = parsed["register_tags"]
                    log_lines.append(
                        f"[FIXED] {word} | Fix 1 | register_tags: [] → {parsed['register_tags']} (sense {sense_num})"
                    )
                    has_any_change = True
                # If no register tags in HTML, leave the key absent (per spec: "leave [] as-is")

            # ── Fix 3: domain (new field) ──────────────────────────────────
            # ALWAYS set domain (to null if no match) so downstream consumers
            # can rely on the key being present.
            if "domain" not in defn:
                parsed_d = extract_labels_for_def(root, matching_sense, subject_labels)
                defn["domain"] = parsed_d["domain"]  # may be None
                if parsed_d["domain"]:
                    log_lines.append(
                        f"[FIXED] {word} | Fix 3 | domain: <unset> → {parsed_d['domain']!r} (sense {sense_num})"
                    )
                    has_any_change = True

    if not has_any_change:
        log_lines.append(f"[NO CHANGE] {word} | all fields already correct")

    return new_record, log_lines


# ── Whole-file driver ─────────────────────────────────────────────────────────


def run_fixer(
    jsonl_in: Path,
    cache_dir: Path,
    labels_path: Path,
    log_path: Path,
    jsonl_out: Path = None,  # deprecated v2 param, kept for backward compat
) -> None:
    """Read jsonl_in, apply fix_record to each, write IN-PLACE atomically.

    v3 contract: writes to `jsonl_in` via .tmp + os.replace. The deprecated
    `jsonl_out` parameter is accepted but ignored — v2's separate output
    file pattern is removed. No .fixed.jsonl file is ever created.

    On any exception before the atomic replace, `jsonl_in` is unchanged.
    """
    # v3: in-place write. v2's jsonl_out is ignored.
    if jsonl_out is not None:
        # Backward-compat: warn but don't fail. Old callers passing jsonl_out
        # continue to work; output is simply the same as input.
        import warnings
        warnings.warn(
            f"jsonl_out={jsonl_out} is deprecated (v2 pattern). Fixer now "
            f"writes IN-PLACE to jsonl_in={jsonl_in}. The .fixed.jsonl "
            f"pattern has been removed.",
            DeprecationWarning,
            stacklevel=2,
        )
    jsonl_out = jsonl_in  # in-place

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with jsonl_in.open(encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    out_lines = []
    all_logs = []
    for rec in records:
        new_rec, logs = fix_record(rec, cache_dir, labels_path)
        out_lines.append(json.dumps(new_rec, ensure_ascii=False))
        all_logs.extend(logs)

    # Atomic write: .tmp + os.replace. On crash, jsonl_in is unchanged.
    import os
    tmp_out = jsonl_in.with_suffix(jsonl_in.suffix + ".tmp")
    with tmp_out.open("w", encoding="utf-8", newline="") as f:
        f.write("\n".join(out_lines) + "\n")
    os.replace(tmp_out, jsonl_out)  # in-place; on Windows this is atomic

    # Write log
    with log_path.open("w", encoding="utf-8", newline="") as f:
        f.write("\n".join(all_logs) + "\n")


# ── CLI entry point ───────────────────────────────────────────────────────────


def main() -> int:
    from src.config import ProjectPaths
    paths = ProjectPaths(PROJECT_ROOT)
    jsonl_in = paths.oxford_jsonl
    # v3: no jsonl_out. Fixer writes IN-PLACE atomically to jsonl_in.
    cache_dir = PROJECT_ROOT / "data" / ".cache_html" / "oxford"
    labels_path = PROJECT_ROOT / "data" / "oxford_labels.json"
    log_path = PROJECT_ROOT / "data" / "_fix_oxford_def_fields.log"

    print(f"Reading:  {jsonl_in}")
    print(f"Writing:  {jsonl_in} (in-place, atomic)")
    print(f"Cache:    {cache_dir}")
    print(f"Log:      {log_path}")

    run_fixer(jsonl_in, cache_dir, labels_path, log_path)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
