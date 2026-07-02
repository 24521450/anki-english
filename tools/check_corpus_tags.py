#!/usr/bin/env python3
"""Check sync and correctness of corpus tags and deck routing.

Reads vocab_list/Oxford/{Oxford_3000,Oxford_5000}.md as the source of truth,
and audits data/build/anki_notes.txt and data/build/English Academic Vocabulary.txt.

Exits 0 if no mismatches are found (except the accepted nursing exception),
otherwise exits 1.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Add project root to sys.path so we can import src modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import ProjectPaths
from src.deck_builder.corpus_tag_sync import (
    DECK_OXFORD_5000,
    DECK_OXFORD_3000_ADVANCED,
    DECK_OXFORD_3000_BASIC,
    DECK_AWL,
    HEADWORD_ALIASES,
    _parse_vocab_list,
    get_vocab_membership,
    route_deck,
    parse_header,
)

def load_cards_from_file(path: Path) -> tuple[int, list[dict]]:
    """Load and parse cards from txt file, dynamically resolving tags column."""
    if not path.exists():
        return 17, []
    tags_col = parse_header(path)
    cards = []

    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.rstrip('\r\n').split('\t')
            if len(parts) < 16:
                continue
            if len(parts) < 19:
                parts = parts + [''] * (19 - len(parts))

            guid = parts[0]

            # Map columns to values based on tags_col index
            if tags_col == 19:
                synonyms = parts[16]
                antonyms = parts[17]
                tags = parts[18]
            else:
                tags = parts[16]
                synonyms = parts[17]
                antonyms = parts[18]

            cards.append({
                'guid': guid,
                'notetype': parts[1],
                'deck': parts[2],
                'word': parts[3],
                'pos': parts[4],
                'ipa': parts[5],
                'definition': parts[6],
                'example': parts[7],
                'collocations': parts[8],
                'wordfamily': parts[9],
                'uk_audio': parts[10],
                'us_audio': parts[11],
                'source1': parts[12],
                'source2': parts[13],
                'cefr': parts[14],
                'idioms': parts[15],
                'synonyms': synonyms,
                'antonyms': antonyms,
                'tags': tags,
                'raw_line': line
            })

    return tags_col, cards


def audit_file(
    path: Path,
    vocab_3000: set[tuple[str, str, str]],
    vocab_5000: set[tuple[str, str, str]],
    label: str,
) -> bool:
    """Audit corpus tags and routing for a given file. Return True if clean (exit 0)."""
    if not path.exists():
        print(f"[{label}] File not found at {path}. Skipping audit.")
        return True

    tags_col, cards = load_cards_from_file(path)
    print(f"\n=== Auditing {label}: {path} (tags column: {tags_col}) ===")
    print(f"  Loaded {len(cards)} cards.")

    exact_matches = 0
    accepted_nursing_exceptions = 0
    missing_tags = []
    extra_tags = []
    deck_mismatches = []

    for c in cards:
        word = c['word']
        pos_str = c['pos']
        cefr = c['cefr']
        guid = c['guid']
        actual_deck = c['deck']
        actual_tags_set = set(c['tags'].split())

        word_clean = word.split(' (')[0].strip().lower()
        should_have_3000, should_have_5000 = get_vocab_membership(word, pos_str, cefr, vocab_3000, vocab_5000)

        is_nursing_exception = (word_clean == 'nursing' and cefr.upper() == 'B2' and 'noun' in pos_str.lower())

        expected_tags_set = set()
        if should_have_3000:
            expected_tags_set.add('Oxford_3000')
        if should_have_5000 or is_nursing_exception:
            expected_tags_set.add('Oxford_5000')

        actual_corpus_tags = actual_tags_set & {'Oxford_3000', 'Oxford_5000'}

        is_in_awl_coxhead = ('AWL_Coxhead' in actual_tags_set)
        expected_deck = route_deck(
            actual_deck, should_have_3000, should_have_5000, word, pos_str, cefr,
            is_in_awl_coxhead=is_in_awl_coxhead
        )

        if is_nursing_exception:
            if 'Oxford_5000' in actual_corpus_tags and actual_deck == DECK_OXFORD_5000:
                accepted_nursing_exceptions += 1
            else:
                if 'Oxford_5000' not in actual_corpus_tags:
                    missing_tags.append(f"{word} ({guid}): B2 noun nursing exception missing Oxford_5000 tag")
                if actual_deck != DECK_OXFORD_5000:
                    deck_mismatches.append(
                        f"{word} ({guid}): nursing exception deck mismatch. "
                        f"Got '{actual_deck}', expected '{DECK_OXFORD_5000}'"
                    )
            continue

        missing = expected_tags_set - actual_corpus_tags
        extra = actual_corpus_tags - expected_tags_set

        if missing:
            missing_tags.append(f"{word} ({guid}): missing tags {sorted(missing)}")
        if extra:
            extra_tags.append(f"{word} ({guid}): extra tags {sorted(extra)}")

        if actual_deck != expected_deck:
            deck_mismatches.append(
                f"{word} ({guid}) [CEFR: {cefr}]: deck mismatch. Got '{actual_deck}', expected '{expected_deck}'"
            )

        if not missing and not extra and actual_deck == expected_deck:
            exact_matches += 1

    print(f"  Exact matches: {exact_matches}")
    print(f"  Accepted exception 'nursing': {accepted_nursing_exceptions}")

    if missing_tags:
        print(f"  Missing tags ({len(missing_tags)}):")
        for m in missing_tags[:10]:
            print(f"    - {m}")
        if len(missing_tags) > 10:
            print(f"    - ... and {len(missing_tags) - 10} more")

    if extra_tags:
        print(f"  Extra tags ({len(extra_tags)}):")
        for e in extra_tags[:10]:
            print(f"    - {e}")
        if len(extra_tags) > 10:
            print(f"    - ... and {len(extra_tags) - 10} more")

    if deck_mismatches:
        print(f"  Deck routing mismatches ({len(deck_mismatches)}):")
        for d in deck_mismatches[:10]:
            print(f"    - {d}")
        if len(deck_mismatches) > 10:
            print(f"    - ... and {len(deck_mismatches) - 10} more")

    clean = (len(missing_tags) == 0 and len(extra_tags) == 0 and len(deck_mismatches) == 0)
    if clean:
        print(f"  [{label}] SUCCESS: No mismatches found.")
    else:
        print(f"  [{label}] FAILED: Mismatches detected.")

    return clean


def audit_awl_coxhead_rules(cards: list[dict], vocab_awl: set[tuple[str, str, str]]) -> bool:
    """Audit AWL_Coxhead contract rules:
    1. Exactly 54 cards carry AWL_Coxhead tag.
    2. No headword possesses both an Oxford tag (Oxford_3000 / Oxford_5000) and AWL_Coxhead.
    3. converse|UNCLASSIFIED homonym split cards exist in AWL_Coxhead.
    4. Deck routing matches tag.
    """
    print("\n=== Auditing AWL_Coxhead contract rules ===")

    awl_coxhead_cards = [c for c in cards if "AWL_Coxhead" in c["tags"].split()]
    print(f"  AWL_Coxhead tag count: {len(awl_coxhead_cards)} / 54")

    errors = []
    if len(awl_coxhead_cards) != 54:
        errors.append(f"Expected exactly 54 AWL_Coxhead cards, found {len(awl_coxhead_cards)}")

    headword_tags: dict[str, set[str]] = {}
    for c in cards:
        w_clean = c["word"].split(" (")[0].strip().lower()
        hw = HEADWORD_ALIASES.get(w_clean, w_clean)
        tags = set(c["tags"].split())
        list_tags = tags & {"Oxford_3000", "Oxford_5000", "AWL_Coxhead"}
        headword_tags.setdefault(hw, set()).update(list_tags)

    for hw, tags in headword_tags.items():
        has_oxford = bool(tags & {"Oxford_3000", "Oxford_5000"})
        has_awl = "AWL_Coxhead" in tags
        if has_oxford and has_awl:
            errors.append(f"Headword '{hw}' has both Oxford ({tags & {'Oxford_3000', 'Oxford_5000'}}) and AWL_Coxhead")

    converse_cards = [c for c in cards if c["word"].startswith("converse") and "AWL_Coxhead" in c["tags"].split()]
    if len(converse_cards) != 2:
        errors.append(f"Expected 2 converse homonym cards in AWL_Coxhead, found {len(converse_cards)}")

    for c in cards:
        tags = set(c["tags"].split())
        deck = c["deck"]
        if "AWL_Coxhead" in tags and deck != DECK_AWL:
            errors.append(f"Card {c['word']} has AWL_Coxhead tag but deck is '{deck}', expected '{DECK_AWL}'")
        elif "Oxford_5000" in tags and deck != DECK_OXFORD_5000:
            errors.append(f"Card {c['word']} has Oxford_5000 tag but deck is '{deck}', expected '{DECK_OXFORD_5000}'")
        elif "Oxford_3000" in tags:
            cefr = c["cefr"].strip().upper()
            expected = DECK_OXFORD_3000_ADVANCED if cefr == "B2" else DECK_OXFORD_3000_BASIC
            if deck != expected:
                errors.append(f"Card {c['word']} has Oxford_3000 tag but deck is '{deck}', expected '{expected}'")

    if errors:
        print(f"  [AWL_Coxhead] FAILED ({len(errors)} errors):")
        for err in errors[:10]:
            print(f"    - {err}")
        return False

    print("  [AWL_Coxhead] SUCCESS: All 54 AWL_Coxhead cards and routing rules verified.")
    return True


def audit_target_coverage(cards: list[dict], vocab_5000: set[tuple[str, str, str]]) -> bool:
    """Verify that all 2,138 target triples in Oxford_5000.md are covered by database cards."""
    print("\n=== Auditing target coverage (Oxford 5000) ===")
    covered = set()
    for c in cards:
        word_clean = c['word'].split(' (')[0].strip().lower()
        cefr = c['cefr'].strip().upper()
        pos_parts = [p.strip().lower() for p in c['pos'].split(',') if p.strip()]

        for pos in pos_parts:
            triple = (word_clean, pos, cefr)
            if triple in vocab_5000:
                covered.add(triple)

        if word_clean == 'nursing' and cefr == 'B2' and 'noun' in pos_parts:
            covered.add(('nursing', 'adjective', 'B2'))

    total_target = len(vocab_5000)
    covered_count = len(covered)
    uncovered = vocab_5000 - covered

    print(f"  Target triples covered: {covered_count} / {total_target} ({covered_count / total_target * 100:.1f}%)")

    if uncovered:
        print(f"  Uncovered triples ({len(uncovered)}):")
        for u in sorted(uncovered)[:10]:
            print(f"    - {u}")
        if len(uncovered) > 10:
            print(f"    - ... and {len(uncovered) - 10} more")
        print("  [coverage] FAILED: Some target triples are not covered.")
        return False

    print("  [coverage] SUCCESS: All target triples are fully covered.")
    return True


def validate_export_consistency(
    db_cards: list[dict],
    exp_cards: list[dict],
    tag_difference_guids: set[str] | None = None,
    expected_count: int | None = 2452,
) -> list[str]:
    """Pure function that validates metadata consistency between database cards and export cards.

    Returns a list of error strings. An empty list means clean/consistent.
    """
    if tag_difference_guids is None:
        tag_difference_guids = set()

    db_by_guid = {c['guid']: c for c in db_cards}
    exp_by_guid = {c['guid']: c for c in exp_cards}

    consistency_errors = []

    if expected_count is not None:
        if len(db_by_guid) != expected_count:
            consistency_errors.append(f"Database has {len(db_by_guid)} cards instead of {expected_count}")
        if len(exp_by_guid) != expected_count:
            consistency_errors.append(f"Export has {len(exp_by_guid)} cards instead of {expected_count}")

    for guid, db_card in db_by_guid.items():
        if guid not in exp_by_guid:
            consistency_errors.append(f"Card {db_card.get('word', '')} ({guid}) present in database but missing in export")
            continue
        exp_card = exp_by_guid[guid]

        # Check metadata fields
        for field in ('guid', 'notetype', 'word', 'pos', 'ipa', 'definition', 'example', 'collocations', 'wordfamily', 'uk_audio', 'us_audio', 'source1', 'source2', 'cefr', 'idioms', 'synonyms', 'antonyms'):
            db_val = db_card.get(field, '')
            exp_val = exp_card.get(field, '')
            if db_val != exp_val:
                consistency_errors.append(
                    f"Field mismatch for card '{db_card.get('word', '')}' ({guid}) on field '{field}': "
                    f"Database has '{db_val}', Export has '{exp_val}'"
                )

        # Compare tags semantically; Anki may reorder them during export.
        db_tags = set(db_card.get('tags', '').split())
        exp_tags = set(exp_card.get('tags', '').split())
        if guid in tag_difference_guids:
            exp_tags.add('Oxford_5000')

        if db_tags != exp_tags:
            consistency_errors.append(
                f"Tags mismatch for card '{db_card.get('word', '')}' ({guid}). "
                f"Database has {sorted(db_tags)}, Export has {sorted(exp_tags)}"
            )

    return consistency_errors


def main() -> int:
    paths = ProjectPaths()

    if not paths.oxford_3000_md.exists():
        print(f"Error: Oxford_3000.md not found at {paths.oxford_3000_md}", file=sys.stderr)
        return 1
    if not paths.oxford_5000_md.exists():
        print(f"Error: Oxford_5000.md not found at {paths.oxford_5000_md}", file=sys.stderr)
        return 1

    database_only = "--database-only" in sys.argv

    # Load vocab lists
    vocab_3000 = _parse_vocab_list(paths.oxford_3000_md)
    vocab_5000 = _parse_vocab_list(paths.oxford_5000_md)
    vocab_awl = _parse_vocab_list(paths.awl_md)

    # 1. Audit canonical txt
    db_clean = audit_file(paths.anki_notes_txt, vocab_3000, vocab_5000, "database")

    # 2. Audit target coverage (2,138 / 2,138)
    _, db_cards = load_cards_from_file(paths.anki_notes_txt)
    coverage_clean = audit_target_coverage(db_cards, vocab_5000)

    # 3. Audit AWL_Coxhead rules (54 cards)
    awl_clean = audit_awl_coxhead_rules(db_cards, vocab_awl)

    # 4. Verify database vs export snapshot consistency if export exists and not --database-only
    export_path = paths.anki_notes_txt.parent / "English Academic Vocabulary.txt"
    export_clean = True
    export_routing_clean = True

    if not database_only and export_path.exists():
        export_routing_clean = audit_file(
            export_path, vocab_3000, vocab_5000, "export"
        )
        print("\n=== Verifying Database vs Export consistency ===")
        _, exp_cards = load_cards_from_file(export_path)
        consistency_errors = validate_export_consistency(db_cards, exp_cards)

        if consistency_errors:
            print(f"  Consistency checks failed ({len(consistency_errors)} errors):")
            for err in consistency_errors[:10]:
                print(f"    - {err}")
            if len(consistency_errors) > 10:
                print(f"    - ... and {len(consistency_errors) - 10} more")
            export_clean = False
        else:
            print("  Consistency check PASSED. Database and Export metadata are consistent.")

    if not db_clean or not coverage_clean or not awl_clean or not export_clean or not export_routing_clean:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
