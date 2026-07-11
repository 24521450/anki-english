"""Build-stage source labels, tags, and legacy routing helpers."""
from __future__ import annotations

import secrets


def source_label(source_files: list[str] | None) -> str:
    if not source_files:
        return "Oxford"
    first = source_files[0]
    if first.startswith("oxford_"):
        return "Oxford"
    if first.startswith("cambridge_"):
        return "Cambridge"
    if first.startswith("awl_"):
        return "AWL"
    return "Oxford"


def regenerate_tags(
    word: str,
    pos: str,
    cefr: str,
    source1: str,
    audio_source: str,
    has_idioms: bool,
    oxford_lists: list[str],
    opal: str | None,
    awl_flag: bool,
    is_in_vocab_3000: bool,
    is_in_vocab_5000: bool,
) -> str:
    tags: list[str] = []
    if audio_source and audio_source != source1:
        tags.append(f"Audio::{audio_source}")
    tags.append(f"Source::{source1}")
    tags.append(f"CEFR::{cefr}")
    tags.append("CEFR::oxford")
    if is_in_vocab_3000:
        tags.append("Oxford_3000")
    if is_in_vocab_5000:
        tags.append("Oxford_5000")
    if opal in ("W", "S"):
        tags.append(f"OPAL_{opal}")
    if has_idioms:
        tags.append("idioms")
    return " ".join(tags)


def sync_idioms_feature_tag(tags: str | None, idioms: str | None) -> str:
    """Derive the idioms feature tag from the serialized learner payload."""
    tokens = [token for token in (tags or "").split() if token != "idioms"]
    if (idioms or "").strip():
        tokens.append("idioms")
    return " ".join(tokens)


def deck_for_source(source1: str, is_awl: bool) -> str:
    if is_awl or source1 == "AWL":
        return "English Academic Vocabulary::AWL 50 Academic Words"
    if source1 == "Cambridge":
        return "English Academic Vocabulary::TED YT"
    return "English Academic Vocabulary::Oxford"


def new_guid() -> str:
    import string

    alphabet = string.ascii_letters + string.digits + "!#$%&()*+,-./:;<=>?@[]^_`{|}~"
    return "".join(secrets.choice(alphabet) for _ in range(10))


def merge_collocations_dicts(dicts: list[dict]) -> dict:
    """Merge multiple collocation dicts by key, union-ing values."""
    out: dict[str, list] = {}
    for collocations in dicts:
        for key, value in (collocations or {}).items():
            if isinstance(value, list):
                out.setdefault(key, [])
                for item in value:
                    if item not in out[key]:
                        out[key].append(item)
            else:
                out.setdefault(key, []).append(value)
    return out
