"""Apply concise_def_skip rule to data/audit_full_deck_v2.jsonl.

For entries whose def_before is already short and simple, we revert the
gloss_after to def_before so we don't introduce semantic drift from a
near-synonym gloss.

Rules (either condition triggers the skip):

1. Standard skip:
   - def_before has <= 3 words (punctuation ignored)
   - Single sense (no '|' or ';' separators)
   - All content words in def_before are in the Oxford A1-A2 band
     (function words handled separately as automatic pass)

2. Whitelist skip (length-4 simple phrases):
   def_before exactly matches one of the pre-baked A1-A2 phrases

For matches we set:
  gloss_after       = def_before (verbatim)
  rule_applied      = "concise_def_skip"
  gloss_word_count  = word count of def_before
  gate_status       = "pass"  (kept)
  fix_status        = "rebuilt"  (preserved if it was "rebuilt" or "expanded_glossed")

Usage:
  python -m tools._apply_concise_skip              # apply in place, with backup
  python -m tools._apply_concise_skip --dry-run    # show what would change, no writes
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
sys.path.insert(0, str(PROJECT_ROOT))

from nltk.stem import WordNetLemmatizer  # noqa: E402

AUDIT_PATH = PROJECT_ROOT / "data" / "audit_full_deck_v2.jsonl"
OXFORD_3000_PATH = PROJECT_ROOT / "vocab_list" / "Oxford" / "Oxford_3000.md"

# Common grammatical function words - treated as A1-A2 automatically
# (pronouns, prepositions, determiners, auxiliary verbs, common conjunctions/adverbs)
FUNCTION_WORDS = frozenset({
    # determiners / pronouns
    "a", "an", "the", "this", "that", "these", "those",
    "my", "your", "his", "her", "its", "our", "their",
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "us", "them",
    "who", "what", "which", "whose",
    "some", "any", "all", "every", "each",
    "much", "many", "more", "most", "few", "little", "less", "least", "several",
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "another", "other", "such", "own", "same", "whole", "different",
    # conjunctions / adverbs
    "and", "or", "but", "if", "because", "so", "as", "than",
    "then", "when", "while", "until", "before", "after", "since", "once",
    "here", "there", "now", "today", "yesterday", "tomorrow",
    "not", "no", "nor", "very", "too", "also", "just", "only", "even",
    "still", "already", "yet", "again",
    "how", "why", "where",
    # prepositions
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "about",
    "into", "onto", "over", "under", "across", "through", "between", "among",
    "against", "without", "within", "around", "out", "off", "up", "down",
    "back", "away", "along", "toward", "towards", "near", "behind",
    "beside", "beyond", "except",
    # auxiliaries / copula
    "is", "am", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "done",
    "have", "has", "had", "having",
    "will", "would", "can", "could", "should", "shall", "may", "might", "must",
    # generic high-frequency nouns that show up in many defs
    "people", "thing", "things", "way", "time", "times", "place", "part",
})

# Whitelist phrases (length-4 simple A1-A2 phrases)
WHITELIST_PHRASES = frozenset({
    "at the same time",
    "a husband or wife",
    "a brother or sister",
    "a business or company",
    "general health and happiness",
})


def load_a1a2_vocab(path: Path = OXFORD_3000_PATH) -> set[str]:
    """Parse Oxford_3000.md and return lowercase set of A1-A2 words/phrases.

    Format of relevant rows:
        | **word** | POS | CEFR | Note |
    POS column may carry multi-POS like "prep., adv." — we keep the
    CEFR column and filter to A1/A2 only.
    """
    a1a2: set[str] = set()
    pattern = re.compile(r"\|\s*\*\*(.+?)\*\*\s*\|\s*[^|]+\|\s*(A1|A2)\s*\|")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line)
        if not m:
            continue
        head = m.group(1)
        # 'a, an' / 'according to' / 'in' — split on ', ' or '/' to capture each form
        for w in re.split(r",\s*|/", head):
            w = w.strip().lower()
            if w:
                a1a2.add(w)
    # Function words are auto-A1-A2
    a1a2 |= FUNCTION_WORDS
    return a1a2


def word_count(def_text: str) -> int:
    """Count words ignoring punctuation."""
    cleaned = re.sub(r"[^\w\s\-\']", " ", def_text)
    return len([w for w in cleaned.split() if w])


def is_single_sense(def_text: str) -> bool:
    """Return True iff def has no '|' or ';' sense separators."""
    return "|" not in def_text and ";" not in def_text


def content_words_all_a1a2(
    def_text: str, a1a2: set[str], lemmatizer: WordNetLemmatizer
) -> tuple[bool, str | None]:
    """Check every word in def_text is in A1-A2 (after POS-aware lemmatization).

    Returns (ok, missing_word). missing_word is the first word that didn't match,
    useful for debugging; None if all matched.
    """
    cleaned = re.sub(r"[^\w\s\-\']", " ", def_text)
    for raw in cleaned.split():
        w = raw.lower()
        if not w:
            continue
        # Try raw, then noun/verb/adj lemmas
        candidates = {
            w,
            lemmatizer.lemmatize(w, "n"),
            lemmatizer.lemmatize(w, "v"),
            lemmatizer.lemmatize(w, "a"),
        }
        if not any(c in a1a2 for c in candidates):
            return False, w
    return True, None


def match_concise_skip(
    record: dict,
    a1a2: set[str],
    lemmatizer: WordNetLemmatizer,
) -> str | None:
    """Return the rule that matched (whitelist / standard), or None if no skip."""
    def_before = (record.get("def_before") or "").strip()
    if not def_before:
        return None
    norm = def_before.lower()

    # Whitelist match (exact, case-insensitive)
    if norm in WHITELIST_PHRASES:
        return "whitelist"

    # Standard skip: short, single sense, all A1-A2
    if word_count(def_before) <= 3 and is_single_sense(def_before):
        ok, _ = content_words_all_a1a2(def_before, a1a2, lemmatizer)
        if ok:
            return "standard"
    return None


def backup_audit(path: Path) -> Path:
    """Copy audit jsonl to a timestamped .bak next to it. Returns backup path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(path.suffix + f".bak_concise_skip_{ts}")
    shutil.copy2(path, backup)
    return backup


def apply_skips(records: list[dict]) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Apply concise_def_skip rule to a list of records (in-place mutated).

    Returns the same list plus a list of (record, rule) pairs that were
    updated — useful for reporting and dry-run.
    """
    a1a2 = load_a1a2_vocab()
    lemmatizer = WordNetLemmatizer()
    updated: list[tuple[dict, str]] = []
    for r in records:
        rule = match_concise_skip(r, a1a2, lemmatizer)
        if not rule:
            continue
        def_before = r["def_before"]
        r["gloss_after"] = def_before
        r["rule_applied"] = "concise_def_skip"
        r["gloss_word_count"] = word_count(def_before)
        r["gate_status"] = "pass"
        # fix_status: keep "rebuilt" semantics, but if it's "kept_no_match" or
        # "kept_not_found", upgrade to "rebuilt" since we are actively emitting
        # a new gloss (= the original def).
        if r.get("fix_status") in (None, "kept_no_match", "kept_not_found"):
            r["fix_status"] = "rebuilt"
        updated.append((r, rule))
    return records, updated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Show what would change, do not write")
    ap.add_argument("--audit", type=Path, default=AUDIT_PATH, help="Path to audit jsonl")
    args = ap.parse_args()

    if not args.audit.exists():
        print(f"ERR: audit file not found: {args.audit}")
        return 1

    lines = args.audit.read_text(encoding="utf-8").splitlines()
    records = [json.loads(l) for l in lines if l.strip()]
    print(f"Loaded {len(records)} records from {args.audit}")

    # Always work on a copy for dry-run; for apply, mutate then write
    if args.dry_run:
        _, updated = apply_skips(records)
        print(f"\n[DRY-RUN] Would update {len(updated)} records:")
        from collections import Counter
        rule_counts = Counter(rule for _, rule in updated)
        print(f"  rule breakdown: {dict(rule_counts)}")
        print()
        print(f"  {'word':<22} {'cefr':<12} {'rule':<10} def_before")
        for r, rule in updated:
            print(
                f"  {r['word']:<22} {r['cefr']:<12} {rule:<10} {r['def_before']!r}"
            )
        return 0

    # Real run
    backup = backup_audit(args.audit)
    print(f"Backup written: {backup}")

    records, updated = apply_skips(records)
    print(f"Updated {len(updated)} records")

    # Rewrite the jsonl
    with args.audit.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {args.audit}")

    # Print summary
    from collections import Counter
    rule_counts = Counter(rule for _, rule in updated)
    print(f"  rule breakdown: {dict(rule_counts)}")
    print()
    print(f"  {'word':<22} {'cefr':<12} {'rule':<10} def_before  ->  gloss_after")
    for r, rule in updated:
        print(
            f"  {r['word']:<22} {r['cefr']:<12} {rule:<10} {r['def_before']!r}  ->  {r['gloss_after']!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
