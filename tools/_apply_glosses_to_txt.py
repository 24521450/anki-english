"""Apply glosses to English Academic Vocabulary.txt — replace def column with gloss.

For each card (matched by word|pos|cefr) that has a verified gloss in
gloss_all_verdicts.json, replace the def column (col 6) with the gloss.

This does NOT add a new field. The def column simply becomes a shorter
gloss for cards where we have one. Cards without gloss keep the original
long def.

Backup is created before write.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))
from tools.build_notes import _parse_existing_txt
from src.deck_builder.gloss_llm import (
    load_existing_verdicts, validate_verdict, JOBS_PATH, VERDICTS_PATH,
)

TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
TXT_HEADER_LINES = 6


def _lookup_verdict(
    raw_word: str,
    pos: str,
    cefr: str,
    gloss_by_key: dict[tuple[str, str, str], str],
) -> str | None:
    """Look up a verdict for a txt card, with disambiguator-aware guard.

    Two failure modes the naive lookup creates:
      1. (silent fail) full key not found, falls back to base-word key,
         but base-word key doesn't exist either → keep Oxford def.
         SAFE — visible in audit as skip_fallback.
      2. (active corruption) full key not found, falls back to base-word key,
         which MATCHES a ghost verdict from a different sense.
         DANGEROUS — applies wrong meaning, audit shows "pass" because
         structurally valid.

    Guard: if the txt card has a disambiguator (e.g. "counter (argue against)")
    AND the verdict dict has any other card with the same base word + disambiguator
    (e.g. "counter (long flat surface)"), do NOT fall back to base-word key.
    The disambiguator exists precisely to disambiguate from base-word ghosts.
    """
    raw_word_lower = raw_word.strip().lower()

    # Try FULL key first (with disambiguator if any)
    full_key = (raw_word_lower, pos, cefr)
    if full_key in gloss_by_key:
        return gloss_by_key[full_key]

    # No full-key match. Extract base word (strip disambiguator if any)
    base_word = raw_word_lower.split(' (')[0].strip()
    has_disambiguator = base_word != raw_word_lower

    if has_disambiguator:
        # GUARD: only fall back to base-word key if NO disambiguated siblings
        # exist in the verdict dict. Otherwise the base-word key would be a
        # ghost verdict from a different sense.
        has_disambiguated_siblings = any(
            k[0].startswith(base_word + ' (') and (k[1], k[2]) == (pos, cefr)
            for k in gloss_by_key
        )
        if has_disambiguated_siblings:
            return None  # force skip_fallback, do NOT match ghost verdict

    # Safe to fall back: no disambiguator, or no disambiguated siblings exist
    base_key = (base_word, pos, cefr)
    return gloss_by_key.get(base_key)


def apply_glosses_to_txt(txt_path: Path, dry_run: bool = False) -> dict:
    """Replace def column with gloss for cards that have a verified gloss.

    Returns stats dict: {matched, replaced, kept_original, sample_before_after}.
    """
    verdicts = load_existing_verdicts()
    print(f'Loaded {len(verdicts)} gloss verdicts')

    parsed = _parse_existing_txt(txt_path)
    print(f'Loaded {len(parsed)} cards from txt')

    # Build (word_lower, pos, cefr) → gloss lookup. KEY INCLUDES DISAMBIGUATOR
    # so that "counter (argue against)" and "counter (long flat surface)" don't
    # collide with the base-word "counter" ghost verdict.
    gloss_by_key: dict[tuple[str, str, str], str] = {}
    skipped_violations: dict[tuple[str, str, str], list[str]] = {}
    for v in verdicts.values():
        if v.decision != 'gloss':
            continue
        # KEY: keep disambiguator in word (do NOT strip) — see _lookup_verdict
        key = (v.word.lower(), v.pos, v.cefr)
        # Defense-in-depth gate: skip verdict if it violates validation rules.
        sep = '|' if '|' in v.gloss else ';' if ';' in v.gloss else 'none'
        from re import split as rsplit
        chunks = [c.strip() for c in rsplit(r'\s*[|;]\s*', v.gloss) if c.strip()]
        errs = validate_verdict(v.word, v.gloss, sep, len(chunks))
        if errs:
            skipped_violations[key] = errs
            continue
        gloss_by_key[key] = v.gloss

    # Read raw lines (preserve formatting including blank lines)
    raw_lines = txt_path.read_text(encoding='utf-8').splitlines()
    header = raw_lines[:TXT_HEADER_LINES]
    body = raw_lines[TXT_HEADER_LINES:]

    matched = replaced = kept = 0
    ghost_blocked = 0  # disambiguated cards where we BLOCKED ghost fallback
    new_body: list[str] = []
    sample: list[tuple[str, str, str, str, str]] = []  # (word, pos, cefr, old_def, new_def)
    for line in body:
        if not line.strip():
            new_body.append(line)
            continue
        parts = line.split('\t')
        if len(parts) < 16:
            new_body.append(line)
            continue
        # Keep FULL word (with disambiguator) for lookup
        raw_word = parts[3].strip()
        pos = parts[4]
        cefr = parts[14]

        # Use the disambiguator-aware lookup
        new_def = _lookup_verdict(raw_word, pos, cefr, gloss_by_key)

        if new_def is not None:
            old_def = parts[6]
            if new_def != old_def:
                parts[6] = new_def
                replaced += 1
                if len(sample) < 5:
                    sample.append((parts[3], pos, cefr, old_def, new_def))
            matched += 1
            # Track if we BLOCKED a ghost fallback (lookup returned None for
            # a card that has a disambiguator with siblings)
            if ' (' in raw_word:
                base_word = raw_word.split(' (')[0].strip().lower()
                has_siblings = any(
                    k[0].startswith(base_word + ' (') and (k[1], k[2]) == (pos, cefr)
                    for k in gloss_by_key
                )
                # If full key matched, _lookup_verdict returned the full-key value
                # (not None). If we got here with new_def != None, the full key
                # matched — so we did NOT block. Skip counter.
        else:
            kept += 1
            # Check if this was a disambiguator card with siblings (ghost blocked)
            if ' (' in parts[3]:
                base_word = parts[3].split(' (')[0].strip().lower()
                has_siblings = any(
                    k[0].startswith(base_word + ' (') and (k[1], k[2]) == (pos, cefr)
                    for k in gloss_by_key
                )
                if has_siblings:
                    ghost_blocked += 1

        new_body.append('\t'.join(parts))

    print(f'\nMatched: {matched}  Replaced: {replaced}  Kept original: {kept}')
    if ghost_blocked:
        print(f'  Ghost-fallback BLOCKED on {ghost_blocked} disambiguated card(s) (would have matched wrong sense)')

    if skipped_violations:
        print(f'\n⚠️  {len(skipped_violations)} verdicts SKIPPED due to gate violations '
              '(their cards keep original Oxford def):')
        from collections import Counter
        cats = Counter()
        for errs in skipped_violations.values():
            for e in errs:
                cats[e.split(':', 1)[0]] += 1
        for k, c in cats.most_common():
            print(f'    {k}: {c}')

    if sample and not dry_run:
        print(f'\nFirst {len(sample)} cards replaced (word | pos | cefr | old -> new):')
        for w, p, c, o, n in sample:
            o_short = o[:50] + '..' if len(o) > 50 else o
            print(f'  {w:18} {p:12} {c:13}  {o_short!r}  ->  {n!r}')

    if not dry_run:
        # Backup
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = txt_path.with_suffix(f'.txt.bak_pre_gloss_apply_{ts}')
        backup.write_text(txt_path.read_text(encoding='utf-8'), encoding='utf-8')
        print(f'\nBackup: {backup.name}')

        # Write
        new_txt = '\n'.join(header + new_body) + '\n'
        txt_path.write_text(new_txt, encoding='utf-8')
        print(f'Wrote: {txt_path}')

    return {'matched': matched, 'replaced': replaced, 'kept': kept, 'sample': sample}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Compute but do not write')
    ap.add_argument('--txt', type=Path, default=TXT_PATH)
    args = ap.parse_args()
    apply_glosses_to_txt(args.txt, dry_run=args.dry_run)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
