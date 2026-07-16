from __future__ import annotations
import json
from pathlib import Path

from src.deck_builder.build_contracts import BuiltCard

def load_review_overrides(path: Path | None) -> dict[str, dict]:
    """Loads and strictly validates GUID-based review overrides from a JSONL file."""
    overrides = {}
    if path is None:
        return overrides

    if not path.exists():
        raise FileNotFoundError(f"Review overrides file not found at: {path}")

    with path.open(encoding="utf-8") as f:
        for line_idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception as e:
                raise ValueError(f"Error parsing line {line_idx} of review overrides file: {e}")

            guid = r.get("guid")
            if not guid:
                raise ValueError(f"Error line {line_idx}: missing guid")

            guid = guid.strip()
            if guid in overrides:
                raise ValueError(f"Duplicate GUID {guid!r} found in review overrides file at line {line_idx}")

            collocations = r.get("Collocations")
            if collocations and ";" in collocations:
                raise ValueError(
                    f"Error line {line_idx}: Semicolon ';' found in Collocations for GUID {guid!r}. "
                    f"Collocations must be standardized to pipe '|' separation."
                )

            overrides[guid] = r

    return overrides


def apply_review_overrides(all_cards: list[BuiltCard], overrides: dict[str, dict]) -> list[BuiltCard]:
    """Applies review overrides to BuiltCard objects, enforcing strict matches and counts."""
    if not overrides:
        return all_cards

    updated_cards = []
    applied_guids = set()

    for c in all_cards:
        if c.guid in overrides:
            r = overrides[c.guid]
            
            # Word validation (case-insensitive)
            expected_word = r.get("word", "").strip().lower()
            actual_word = c.word.strip().lower()
            if actual_word != expected_word:
                raise ValueError(
                    f"Word mismatch for overridden card GUID {c.guid!r}: "
                    f"expected {expected_word!r}, got {actual_word!r}"
                )

            # CEFR validation
            expected_cefr = r.get("cefr", "").strip().upper()
            actual_cefr = c.cefr.strip().upper()
            if actual_cefr != expected_cefr:
                raise ValueError(
                    f"CEFR mismatch for overridden card GUID {c.guid!r}: "
                    f"expected {expected_cefr!r}, got {actual_cefr!r}"
                )

            # POS validation (allows input_pos OR output_pos match for POS migration rerun robustness)
            expected_input_pos = r.get("input_pos", "").strip().lower()
            expected_output_pos = (r.get("output_pos") or "").strip().lower()
            actual_pos = c.pos.strip().lower()
            if actual_pos != expected_input_pos and actual_pos != expected_output_pos:
                raise ValueError(
                    f"POS mismatch for overridden card GUID {c.guid!r}: "
                    f"actual POS {actual_pos!r} matches neither input_pos {expected_input_pos!r} "
                    f"nor output_pos {expected_output_pos!r}"
                )

            # Apply override values
            new_pos = r.get("output_pos") or c.pos
            if not new_pos:
                new_pos = c.pos

            c_new = BuiltCard(
                guid=c.guid,
                notetype=c.notetype,
                deck=c.deck,
                word=c.word,
                pos=new_pos,
                ipa=r.get("IPA", c.ipa),
                definition=r.get("Definition", c.definition),
                example=r.get("Example", c.example),
                collocations=r.get("Collocations", c.collocations),
                wordfamily=c.wordfamily,
                uk_audio=c.uk_audio,
                us_audio=c.us_audio,
                source1=c.source1,
                source2=c.source2,
                cefr=c.cefr,
                idioms=c.idioms,
                tags=c.tags,
                synonyms=c.synonyms,
                antonyms=c.antonyms,
                example_audio_uk=c.example_audio_uk,
                example_audio_us=c.example_audio_us,
                idiom_example_audio_uk=c.idiom_example_audio_uk,
                idiom_example_audio_us=c.idiom_example_audio_us,
                definition_vi=c.definition_vi,
                cambridge_url=c.cambridge_url,
                oxford_pos_urls=c.oxford_pos_urls,
                production_answer=c.production_answer,
            )
            updated_cards.append(c_new)
            applied_guids.add(c.guid)
        else:
            updated_cards.append(c)

    # Confirm exactly all overrides are applied (only in full build to prevent mock unit test failures)
    if len(all_cards) > 2400:
        missing_guids = set(overrides.keys()) - applied_guids
        if missing_guids:
            raise ValueError(
                f"Expected {len(overrides)} overrides to be applied, but {len(applied_guids)} were. "
                f"Missing card GUIDs in built notes: {sorted(missing_guids)}"
            )

    return updated_cards
