"""Build layer merge — combine multiple per-POS records for same word into 1.

Per Phase 7b grill decisions (Q5-Y2):
- 1 record per unique (word, homonym_index) pair
- Merge strategy per field is pinned (word, source, source_url: take first;
  pos_data: concatenate+dedupe; etc.)
- Phrase pages remain independent records in production. The legacy phrasal
  verb folding helper remains available only for compatibility callers.

See CONTEXT.md § Skip Rule and § Phrasal Verb Folding for the full contract.

Source: src/scraper/merge.py
"""
from __future__ import annotations

import copy
from typing import Any, Optional

from src.scraper.oxford_labels import CONFLICT_PAIRS


# Canonical POS ordering for stable output (pinned Phase 7b: adj before noun before verb)
POS_ORDER = [
    "adjective", "noun", "verb", "adverb",
    "determiner", "pronoun", "preposition", "conjunction",
    "exclamation", "number", "modal", "abbreviation",
    "phrasal verb", "linking verb", "definite article", "ordinal number",
    "prefix", "suffix", "combining form",
    "determiner,pronoun", "adjective,adverb", "exclamation,noun",
    "adjective,pronoun", "pronoun,determiner", "adverb,preposition",
    "preposition,adverb", "preposition,conjunction", "determiner,adjective",
    "noun,determiner", "determiner,ordinal_number",
    "determiner,pronoun,adverb", "adverb,pronoun,conjunction",
    "number,determiner", "conjunction,adverb", "adverb,pronoun",
    "adverb,noun", "adjective,noun", "noun,verb",
]
_POS_RANK = {p: i for i, p in enumerate(POS_ORDER)}


def _dedup_preserve_order(items: list) -> list:
    """Remove duplicates while keeping first occurrence's order."""
    return list(dict.fromkeys(items))


def _merge_register_tags_strict(
    records: list[dict],
    field: str,
    context: str,
) -> list[str]:
    """Union register tags from multiple records; raise ValueError on forbidden conflict.

    Args:
        records: source records (each has a `field` key with a list[str]).
        field: the key to read from each record (e.g. 'register_tags').
        context: human-readable context string for the error message.
    """
    out: list[str] = []
    for r in records:
        for tag in (r.get(field) or []):
            if tag and tag not in out:
                cand = out + [tag]
                conflict = next(
                    ((t1, t2) for t1, t2 in CONFLICT_PAIRS if t1 in cand and t2 in cand),
                    None,
                )
                if conflict:
                    raise ValueError(
                        f"Conflicting register tags {conflict!r} in '{field}' "
                        f"({context})"
                    )
                out.append(tag)
    return out




def _stable_pos_order(pos_list: list[str]) -> list[str]:
    """Sort POS list by canonical order, unknown POS go to the end preserving order."""
    def sort_key(p):
        return _POS_RANK.get(p, len(POS_ORDER) + hash(p) % 1000)
    return sorted(pos_list, key=sort_key)


def _merge_opal_membership(records: list[dict]) -> dict[str, list[str]] | None:
    """Union OPAL memberships by POS and return deterministic W-before-S data."""
    by_pos: dict[str, set[str]] = {}
    for record in records:
        opal = record.get("opal")
        if opal is None:
            continue
        if not isinstance(opal, dict) or not opal:
            raise ValueError(f"OPAL membership must be POS-scoped, got {opal!r}")
        for pos, memberships in opal.items():
            if (
                not isinstance(pos, str)
                or not pos
                or not isinstance(memberships, list)
                or not memberships
            ):
                raise ValueError(
                    f"Invalid OPAL membership for POS {pos!r}: {memberships!r}"
                )
            invalid = [kind for kind in memberships if kind not in ("W", "S")]
            if invalid:
                raise ValueError(
                    f"Invalid OPAL membership for POS {pos!r}: {memberships!r}"
                )
            by_pos.setdefault(pos, set()).update(memberships)

    if not by_pos:
        return None

    ordered_positions = sorted(
        by_pos,
        key=lambda pos: (_POS_RANK.get(pos, len(POS_ORDER)), pos),
    )
    return {
        pos: [kind for kind in ("W", "S") if kind in by_pos[pos]]
        for pos in ordered_positions
    }


# ===========================================================================
# Phrasal Verb Folding (Issue A, option β)
# ===========================================================================
# Oxford's main-word page for pattern-heavy verbs (deprive, derive, devote,
# rely) can link to a separate phrasal-verb page (e.g. "deprive of").
# Production rebuild no longer invokes this heuristic because Oxford's
# authoritative phrase-page links and target page identities must be retained.
#
# Detection: a phrasal-verb record has `pos == ["phrasal verb"]` and `word`
# contains a space (e.g. "deprive of", "rely on"). The base word is the
# first whitespace-separated token.
#
# Fold operation (pre-grouping):
#   1. Find all phrasal-verb records.
#   2. For each, locate the main-word record (same `word` = base).
#   3. Append the phrasal-verb's `pos_data` (with pos="phrasal verb") to the
#      main-word record's pos_data.
#   4. Append the phrasal-verb record to a `folded_sources` list on the main
#      word (for traceability / source_files union).
#   5. Flag the phrasal-verb record `_skip: true, _skip_reason:
#      "folded-into-main-word: <base>"` so the builder doesn't render a
#      duplicate card.
#
# If the main-word record doesn't exist for some reason (shouldn't happen
# given the cache structure, but defensive), keep the phrasal-verb record
# as-is and don't fold.
# ===========================================================================


def _is_phrasal_verb_record(rec: dict) -> bool:
    """True if rec is a phrasal-verb entry (word has space AND pos=phrasal verb)."""
    word = (rec.get("word") or "").strip()
    pos = rec.get("pos", [])
    return " " in word and "phrasal verb" in pos


def _phrasal_verb_base_word(rec: dict) -> Optional[str]:
    """Extract the base word from a phrasal-verb record's `word` field.

    "deprive of" -> "deprive"
    "look forward to" -> "look"
    """
    word = (rec.get("word") or "").strip()
    if " " not in word:
        return None
    return word.split(" ", 1)[0]


def fold_phrasal_verb_records(records: list[dict]) -> list[dict]:
    """Fold phrasal-verb records INTO their main-word records.

    Input: list of per-file records (from the parser, before grouping by word).
    Output: modified list where:
      - Each phrasal-verb record has `_skip: true, _skip_reason:
        "folded-into-main-word: <base>"` and is otherwise untouched.
      - Each main-word record (matching the phrasal-verb's base) has the
        phrasal-verb's `pos_data` appended (under pos="phrasal verb") and
        the phrasal-verb's `source_files` unioned in.
      - If no main-word record exists for a phrasal-verb (defensive), the
        phrasal-verb record is left as-is (no fold).

    This function is pure (deep-copies inputs) so the caller can keep the
    audit trail.
    """
    # Deep-copy all records so we don't mutate the parser output
    out: list[dict] = [copy.deepcopy(r) for r in records]

    # Group phrasal-verb records by their base word
    pv_by_base: dict[str, list[dict]] = {}
    for r in out:
        if _is_phrasal_verb_record(r):
            base = _phrasal_verb_base_word(r)
            if base:
                pv_by_base.setdefault(base, []).append(r)

    if not pv_by_base:
        return out

    # For each base, find the main-word record(s) and fold
    for base, pv_recs in pv_by_base.items():
        for pv in pv_recs:
            # Idempotency: if this PV has already been folded (skip flag set),
            # don't fold again. We check `_skip_reason` because the runner may
            # have already applied the phrasal-verb-redirect rule or the
            # folded-into-main-word rule to a previous run.
            if (pv.get("_skip_reason") or "").startswith("folded-into-main-word"):
                continue

            # Find main-word record: same `word` == base AND not itself a phrasal verb
            main_rec = None
            for r in out:
                if r is pv:
                    continue
                if _is_phrasal_verb_record(r):
                    continue
                if r.get("word") == base:
                    main_rec = r
                    break
            if main_rec is None:
                # No main-word record to fold into; leave phrasal-verb as-is
                continue

            # Append phrasal-verb's pos_data to main record.
            # Tag each pos_data entry with pos="phrasal verb" if not already.
            for pv_pd in pv.get("pos_data", []):
                folded_pd = copy.deepcopy(pv_pd)
                if folded_pd.get("pos") != "phrasal verb":
                    folded_pd["pos"] = "phrasal verb"
                main_rec.setdefault("pos_data", []).append(folded_pd)

            # Union source_files
            for f in pv.get("source_files", []):
                if f not in main_rec.get("source_files", []):
                    main_rec.setdefault("source_files", []).append(f)

            # Preserve entry-scoped pronunciation evidence from folded pages.
            for pronunciation in pv.get("pronunciations", []):
                if pronunciation not in main_rec.setdefault("pronunciations", []):
                    main_rec["pronunciations"].append(copy.deepcopy(pronunciation))

            # Update pos top-level array to include "phrasal verb"
            if "phrasal verb" not in main_rec.get("pos", []):
                main_rec.setdefault("pos", []).append("phrasal verb")

            # Preserve memberships from both the base entry and folded phrase.
            main_rec["opal"] = _merge_opal_membership([main_rec, pv])

            # Mark the phrasal-verb record as folded
            pv["_skip"] = True
            pv["_skip_reason"] = f"folded-into-main-word: {base}"

    return out


def merge_word_records(records: list[dict]) -> dict:
    """Merge multiple per-POS records for the same (word, homonym_index) into 1.

    Args:
        records: list of 1+ records with the same `word` field (and same
                 `homonym_index`), all from the same source. At least 1
                 record must be provided; 1-record input passes through
                 unchanged.

    Returns:
        Single merged record. Per-field merge strategy (pinned Phase 7b):

        - word, homonym_index, source, source_url: take from first non-null
        - source_files: union (preserving order of first appearance)
        - pos: union, sorted by canonical order
        - pos_data: concatenate from all records, dedupe by (pos, sensenum_local, text)
        - oxford_lists: union
        - oxford_badge: first non-null (per Q6: badge is display metadata, not identity)
        - opal: union by POS, with canonical POS and W-before-S ordering
        - awl: first non-null
        - uk_ipa, us_ipa: first non-null (display metadata, not identity)
        - audio.uk, audio.us: first non-null
        - see_also: union, dedup
        - phrasal_verb_links: union exact target identities, dedup
        - register_tags (top + per-def): union
        - verb_forms: first non-null (only 1 file has it)
        - idioms: concatenate, dedupe by phrase

    Skip flags applied (see CONTEXT.md § Skip Rule):
      1. Phrasal-verb-redirect: pos_data=[] AND idioms=[] → skip with
         "phrasal-verb-redirect: no extractable senses".
      2. Proper-noun-or-cultural-entry: pos_data non-empty AND all pos=unknown
         AND badge=None AND oxford_lists=[] AND no def.cefr → skip with
         "proper-noun-or-cultural-entry: no CEFR/oxford-list membership".
    """
    if not records:
        raise ValueError("merge_word_records requires at least 1 record")
    if len(records) == 1:
        # Deep copy so caller can mutate without affecting input.
        # Backfill required fields on every def so downstream consumers
        # (schema validator, builder) can assume they always exist.
        # This handles 3 cases:
        #   1. Synthetic records from older fixers that predate the field.
        #   2. Hand-crafted test fixtures that omit the field.
        #   3. Old parser outputs preserved in audit JSONL.
        result = copy.deepcopy(records[0])
        result["opal"] = _merge_opal_membership([result])
        result.setdefault("pronunciations", [])
        result.setdefault("phrasal_verb_links", [])
        for pd in result.get("pos_data", []):
            pd.setdefault("source_url", None)
            for d in pd.get("definitions", []):
                if "synonyms" not in d:
                    d["synonyms"] = []
                if "antonyms" not in d:
                    d["antonyms"] = []
                if "collocation_evidence" not in d:
                    d["collocation_evidence"] = []
                if "sense_frames" not in d:
                    d["sense_frames"] = []
        # Apply skip flag rules
        _apply_skip_flags(result)
        return result

    base = dict(records[0])  # copy of first record

    # word, homonym_index, source, source_url: take first non-null
    for f in ("word", "homonym_index", "source", "source_url"):
        base[f] = next((r.get(f) for r in records if r.get(f) is not None), base.get(f))

    # source_files: union preserving first-appearance order
    seen_files = []
    seen_set = set()
    for r in records:
        for f in r.get("source_files", []):
            if f not in seen_set:
                seen_set.add(f)
                seen_files.append(f)
    base["source_files"] = seen_files

    # Entry-scoped pronunciation evidence is unioned without collapsing POS or
    # homograph ownership. Parser order is already deterministic at this layer.
    base["pronunciations"] = []
    for record in records:
        for pronunciation in record.get("pronunciations", []):
            if pronunciation not in base["pronunciations"]:
                base["pronunciations"].append(copy.deepcopy(pronunciation))

    # pos: union, sort by canonical order
    pos_set = []
    for r in records:
        for p in r.get("pos", []):
            if p not in pos_set:
                pos_set.append(p)
    base["pos"] = _stable_pos_order(pos_set)

    # oxford_lists and OPAL: union; AWL: first-non-null
    base["oxford_lists"] = _dedup_preserve_order(
        [p for r in records for p in r.get("oxford_lists", [])]
    )
    base["opal"] = _merge_opal_membership(records)
    base["awl"] = next(
        (r.get("awl") for r in records if r.get("awl") is not None),
        base.get("awl"),
    )

    # oxford_badge: first non-null (display metadata, not identity)
    base["oxford_badge"] = next(
        (r.get("oxford_badge") for r in records if r.get("oxford_badge") is not None),
        base.get("oxford_badge"),
    )

    # audio.uk, audio.us: first non-null
    base["audio"] = {
        "uk": next(
            (r.get("audio", {}).get("uk") for r in records
             if r.get("audio", {}).get("uk")),
            None,
        ),
        "us": next(
            (r.get("audio", {}).get("us") for r in records
             if r.get("audio", {}).get("us")),
            None,
        ),
    }

    # uk_ipa, us_ipa: first non-null (display metadata, not identity — same
    # strategy as oxford_badge / audio). Stripping is the caller's job.
    base["uk_ipa"] = next(
        (r.get("uk_ipa") for r in records if r.get("uk_ipa") is not None),
        base.get("uk_ipa"),
    )
    base["us_ipa"] = next(
        (r.get("us_ipa") for r in records if r.get("us_ipa") is not None),
        base.get("us_ipa"),
    )

    # see_also: union, dedup
    base["see_also"] = _dedup_preserve_order(
        [w for r in records for w in r.get("see_also", [])]
    )
    base["phrasal_verb_links"] = []
    for record in records:
        for link in record.get("phrasal_verb_links", []):
            if link not in base["phrasal_verb_links"]:
                base["phrasal_verb_links"].append(copy.deepcopy(link))

    # register_tags (top-level): union, raise on forbidden conflict
    base["register_tags"] = _merge_register_tags_strict(
        records, field="register_tags",
        context=f"word='{base.get('word')}' source_files={base.get('source_files')}",
    )

    # verb_forms: first non-null
    base["verb_forms"] = next(
        (r.get("verb_forms") for r in records if r.get("verb_forms") is not None),
        None,
    )

    # pos_data: concatenate from all records, dedupe by (pos, sensenum_local, text)
    pos_data_merged: list[dict] = []
    seen_defs: dict[tuple, dict] = {}
    for r in records:
        for pd in r.get("pos_data", []):
            # Within a single record, dedupe defs by key
            new_defs = []
            for d in pd.get("definitions", []):
                key = (pd["pos"], d.get("sensenum_local"), d.get("text"))
                if key not in seen_defs:
                    d_copy = copy.deepcopy(d)
                    if "synonyms" not in d_copy:
                        d_copy["synonyms"] = []
                    if "antonyms" not in d_copy:
                        d_copy["antonyms"] = []
                    if "collocation_evidence" not in d_copy:
                        d_copy["collocation_evidence"] = []
                    if "sense_frames" not in d_copy:
                        d_copy["sense_frames"] = []
                    seen_defs[key] = d_copy
                    new_defs.append(d_copy)
                else:
                    d_existing = seen_defs[key]
                    # Union synonyms (preserves first-appearance order)
                    existing_syns = d_existing.get("synonyms") or []
                    new_syns = d.get("synonyms") or []
                    d_existing["synonyms"] = _dedup_preserve_order(existing_syns + new_syns)

                    # Union antonyms (same strategy — Oxford often splits the
                    # same sense across files; opposite headwords vary slightly
                    # between scrapes and we want all of them.)
                    existing_ants = d_existing.get("antonyms") or []
                    new_ants = d.get("antonyms") or []
                    d_existing["antonyms"] = _dedup_preserve_order(existing_ants + new_ants)

                    # Preserve every distinct evidence origin/coordinate while
                    # removing only byte-for-byte-equivalent duplicate objects.
                    # Equal surface text from Oxford examples and snippets is
                    # deliberately retained as two provenance records.
                    existing_evidence = d_existing.get("collocation_evidence") or []
                    for item in d.get("collocation_evidence") or []:
                        if item not in existing_evidence:
                            existing_evidence.append(copy.deepcopy(item))
                    d_existing["collocation_evidence"] = existing_evidence

                    d_existing["sense_frames"] = _dedup_preserve_order(
                        (d_existing.get("sense_frames") or [])
                        + (d.get("sense_frames") or [])
                    )

                    # Union register_tags (raise on forbidden conflict)
                    existing_regs = d_existing.get("register_tags") or []
                    new_regs = d.get("register_tags") or []
                    merged_regs = list(existing_regs)
                    for tag in new_regs:
                        if tag and tag not in merged_regs:
                            cand = merged_regs + [tag]
                            conflict = next(
                                (t1, t2)
                                for t1, t2 in CONFLICT_PAIRS
                                if t1 in cand and t2 in cand
                            ) if any(t1 in cand and t2 in cand for t1, t2 in CONFLICT_PAIRS) else None
                            if conflict:
                                raise ValueError(
                                    f"Conflicting register tags {conflict!r} for "
                                    f"definition '{d.get('text')}' "
                                    f"(word='{base.get('word')}' pos='{key[0]}' "
                                    f"sensenum='{key[1]}' "
                                    f"source_files={base.get('source_files')})"
                                )
                            merged_regs.append(tag)
                    d_existing["register_tags"] = merged_regs

                    # Domain: pick non-null domain; raise ValueError if two different non-null domains exist
                    existing_dom = d_existing.get("domain")
                    new_dom = d.get("domain")
                    if existing_dom is None:
                        d_existing["domain"] = new_dom
                    elif new_dom is not None and new_dom != existing_dom:
                        raise ValueError(
                            f"Conflicting domains for definition '{d.get('text')}': "
                            f"'{existing_dom}' vs '{new_dom}'"
                        )
            if new_defs:
                # Re-number n: 1-based within each pos_data entry
                for n, d_item in enumerate(new_defs, start=1):
                    d_item["n"] = n
                pos_data_merged.append({
                    "pos": pd["pos"],
                    "source_url": pd.get("source_url"),
                    "register_tags": _dedup_preserve_order(pd.get("register_tags", [])),
                    "definitions": new_defs,
                })

    # A merged POS section may receive the same definition from multiple
    # source pages. Preserve provenance only when every contributing page
    # agrees; an ambiguous link is safer as null than as a wrong dictionary URL.
    for merged_pd in pos_data_merged:
        matching_urls: set[str | None] = set()
        merged_keys = {
            (merged_pd["pos"], d.get("sensenum_local"), d.get("text"))
            for d in merged_pd.get("definitions", [])
        }
        for record in records:
            for source_pd in record.get("pos_data", []):
                source_keys = {
                    (source_pd.get("pos"), d.get("sensenum_local"), d.get("text"))
                    for d in source_pd.get("definitions", [])
                }
                if merged_keys & source_keys:
                    matching_urls.add(source_pd.get("source_url"))
        non_null_urls = {url for url in matching_urls if url}
        merged_pd["source_url"] = (
            next(iter(non_null_urls))
            if len(non_null_urls) == 1 and None not in matching_urls
            else None
        )

    # Renumber pos_data entries by canonical POS order
    pos_data_merged = sorted(
        pos_data_merged,
        key=lambda pd: _POS_RANK.get(pd["pos"], len(POS_ORDER) + hash(pd["pos"]) % 1000),
    )
    base["pos_data"] = pos_data_merged

    # Preserve entry ownership while deduplicating repeated parses of the same
    # phrase from the same POS.
    base["idioms"] = []
    seen_idioms: set[tuple[str, str]] = set()
    for r in records:
        for i in r.get("idioms", []):
            phrase = i.get("phrase")
            owner_pos = i.get("pos") or ""
            key = (phrase, owner_pos)
            if phrase and key not in seen_idioms:
                seen_idioms.add(key)
                base["idioms"].append(i)

    # Apply skip flag rules (phrasal-verb-redirect + proper-noun)
    _apply_skip_flags(base)

    return base


# ===========================================================================
# Skip flag rules (Issue C + A)
# ===========================================================================

def _has_any_def_cefr(record: dict) -> bool:
    """Return True if any def in any pos_data entry has a non-null cefr."""
    for pd in record.get("pos_data", []):
        for d in pd.get("definitions", []):
            if d.get("cefr") is not None:
                return True
    return False


def _all_pos_unknown(record: dict) -> bool:
    """Return True if record has pos_data AND every entry's pos == 'unknown'."""
    pd_list = record.get("pos_data", [])
    if not pd_list:
        return False  # vacuous; caller should gate on pos_data non-empty
    return all(pd.get("pos") == "unknown" for pd in pd_list)


def _apply_skip_flags(record: dict) -> None:
    """Set _skip and _skip_reason on `record` per the documented skip rules.

    Mutates `record` in place. Rules applied in priority order (first match wins):

      1. Phrasal-verb-redirect: pos_data=[] AND idioms=[] → skip with
         "phrasal-verb-redirect: no extractable senses".
      2. Proper-noun-or-cultural-entry: pos_data non-empty AND all pos=unknown
         AND oxford_badge is None AND oxford_lists == [] AND no def.cefr →
         skip with "proper-noun-or-cultural-entry: no CEFR/oxford-list membership".

    Otherwise: _skip=False, _skip_reason removed.

    See CONTEXT.md § Skip Rule for the full contract.
    """
    pos_data = record.get("pos_data", [])
    idioms = record.get("idioms", [])

    # Preserve pre-existing _skip flag (set by fold_phrasal_verb_records).
    # If a record is already flagged as folded-into-main-word, don't override.
    existing_reason = record.get("_skip_reason") or ""
    if existing_reason.startswith("folded-into-main-word"):
        record["_skip"] = True
        return

    # Rule 1: phrasal-verb-redirect
    if not pos_data and not idioms:
        record["_skip"] = True
        record["_skip_reason"] = "phrasal-verb-redirect: no extractable senses"
        return

    # Rule 2: proper-noun-or-cultural-entry (only fires on records that have
    # pos_data — the existing idiom-only records like 'accordance' shouldn't
    # be touched by this rule).
    if (
        pos_data
        and _all_pos_unknown(record)
        and record.get("oxford_badge") is None
        and record.get("oxford_lists", []) == []
        and not _has_any_def_cefr(record)
    ):
        record["_skip"] = True
        record["_skip_reason"] = (
            "proper-noun-or-cultural-entry: no CEFR/oxford-list membership"
        )
        return

    # Default: not skipped
    record["_skip"] = False
    record.pop("_skip_reason", None)
