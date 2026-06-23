"""Thin CLI adapter for building Anki Notes from Oxford jsonl + γ verdicts + vocab_list.

Delegates core implementation to src.deck_builder.build_notes.
"""
from __future__ import annotations
import argparse
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Re-expose core types, functions, and constants for backwards-compatibility
from src.deck_builder.build_notes import (
    _format_examples,
    DEF_SEPARATOR,
    EX_SEP,
    COLL_SEPARATOR,
    _parse_existing_txt,
    get_word_candidates,
    lookup_gloss,
    _format_collocations,
    _format_idioms,
    _format_wordfamily,
    _format_ipa,
    _normalize_ipa,
    _format_ipa_field,
    _format_audio,
    _resolve_audio_filename,
    _source_label,
    _regenerate_tags,
    _deck_for_source,
    _new_guid,
    _merge_collocations_dicts,
    _simplify_with_gamma,
    _load_gamma_verdicts,
    _parse_vocab_list,
    find_idioms_for_word,
    BuiltCard,
    BuildNotesPaths,
    BuildNotesResult,
    POS_NORM,
    build_notes,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

JSONL_PATH = PROJECT_ROOT / 'data' / 'oxford_merged.jsonl'
GAMMA_VERDICTS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gamma_all_verdicts.json'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
OUT_JSONL = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'
OXFORD_3000_MD = PROJECT_ROOT / 'vocab_list' / 'Oxford' / 'Oxford_3000.md'
OXFORD_5000_MD = PROJECT_ROOT / 'vocab_list' / 'Oxford' / 'Oxford_5000.md'
AWL_MD = PROJECT_ROOT / 'vocab_list' / 'AWL' / 'AWL.md'
AUDIT_JSONL_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
FILLED_PATH = PROJECT_ROOT / 'data' / 'missing_oxford_5000_cards_filled.json'
AUDIO_DIR = PROJECT_ROOT / 'audio'


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='Compute but do not write')
    ap.add_argument('--jsonl', type=Path, default=JSONL_PATH)
    ap.add_argument('--txt', type=Path, default=TXT_PATH)
    ap.add_argument('--out-jsonl', type=Path, default=OUT_JSONL)
    ap.add_argument('--gamma', type=Path, default=GAMMA_VERDICTS_PATH)
    args = ap.parse_args()

    paths = BuildNotesPaths(
        jsonl_path=args.jsonl,
        txt_path=args.txt,
        audit_jsonl_path=AUDIT_JSONL_PATH,
        gamma_verdicts_path=args.gamma,
        oxford_3000_md=OXFORD_3000_MD,
        oxford_5000_md=OXFORD_5000_MD,
        awl_md=AWL_MD,
        filled_path=FILLED_PATH,
        audio_dir=AUDIO_DIR
    )

    sys.path.insert(0, str(PROJECT_ROOT))
    print('=== Loading inputs ===', file=sys.stderr)
    print(f'  audio dir: {paths.audio_dir}', file=sys.stderr)
    print(f'Vocab 3000: {paths.oxford_3000_md.name}', file=sys.stderr)
    print(f'Vocab 5000: {paths.oxford_5000_md.name}', file=sys.stderr)
    print(f'Vocab AWL:   {paths.awl_md.name}', file=sys.stderr)

    # Call the new Build Notes Module
    res = build_notes(paths)

    print('=== Building cards (existing txt scope) ===', file=sys.stderr)
    print(f'  Type A (POS fix): {res.type_a_count}', file=sys.stderr)
    print(f'  Type B (lemmatize): {res.type_b_count}', file=sys.stderr)
    print(f'  Type C (drop, no data): {res.type_c_count}', file=sys.stderr)
    print(f'  Dup emit skipped: {res.dup_emit_skip_count}', file=sys.stderr)
    print(f'  UNCLASSIFIED drop: {res.unclassified_drop_count}', file=sys.stderr)
    print(f'  built cards: {res.built_cards_count}', file=sys.stderr)
    print(f'  missing in jsonl: {res.missing_in_jsonl_count}', file=sys.stderr)

    # Write files if not dry-run
    if not args.dry_run:
        args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        args.out_jsonl.write_text(res.jsonl_text, encoding='utf-8')
        print(f'Wrote: {args.out_jsonl}', file=sys.stderr)

        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = args.txt.with_suffix(f'.txt.bak_pre_build_{ts}')
        backup.write_text(args.txt.read_text(encoding='utf-8'), encoding='utf-8')
        args.txt.write_text(res.txt_text, encoding='utf-8')
        print(f'Wrote: {args.txt}  (backup: {backup.name})', file=sys.stderr)

    # Quick stats
    print('\n=== Quick stats ===', file=sys.stderr)
    by_cefr = Counter(c.cefr for c in res.built_cards)
    by_deck = Counter(c.deck for c in res.built_cards)
    by_source = Counter(c.source1 for c in res.built_cards)
    print(f'  by cefr: {dict(by_cefr)}', file=sys.stderr)
    print(f'  by deck: {dict(by_deck)}', file=sys.stderr)
    print(f'  by source1: {dict(by_source)}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
