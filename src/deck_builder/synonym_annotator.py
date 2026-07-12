"""Annotate Anki example chunks with Oxford sense-level synonyms AND antonyms.

Pipeline
--------
1. `get_relation_specs_for_card(card, senses_index)` walks the senses_index
   keyed by (word, pos, cefr) and returns one spec per source example:
       {"text": ex_text, "synonyms": [...], "antonyms": [...]}
   The spec matches an Oxford example 1:1 — no inference, no guessing.

2. `annotate_card_examples(card, specs, synonym_overrides, antonym_overrides)`
   consumes the chunk-aligned specs and writes a parenthetical relation
   after the headword in each chunk. Returns:
       (annotated_example,        # pipe-aligned with original chunks
        synonyms_metadata,        # pipe-aligned: per-chunk synonym or empty
        antonyms_metadata,        # pipe-aligned: per-chunk antonym or empty
        errors)                   # build fails if non-empty

3. `clean_for_matching` normalizes text for case/punctuation-insensitive
   example matching.

Manual override format (JSONL):
    synonym overrides: data/review/synonym_example_overrides.jsonl
    antonym overrides: data/review/antonym_example_overrides.jsonl
    {guid, word, pos, cefr, original_example, action: annotate|skip,
     [source_example, annotated_example, reason]}
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING
import nltk
from nltk.stem import WordNetLemmatizer

if TYPE_CHECKING:
    from src.deck_builder.build_contracts import BuiltCard

try:
    lemmatizer = WordNetLemmatizer()
    lemmatizer.lemmatize("testing", pos="v")
except Exception as e:
    raise ImportError(f"Failed to initialize NLTK WordNet Lemmatizer: {e}")


# -----------------------------------------------------------------------------
# Public loader: manual synonym / antonym overrides (per GUID)
# -----------------------------------------------------------------------------

def load_relation_overrides(path: Path | str | None) -> dict[str, list[dict]]:
    """Loads manual synonym/antonym example overrides from a JSONL file."""
    overrides: dict[str, list[dict]] = {}
    if path is None:
        return overrides

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Relation overrides file not found at: {path}")

    seen_overrides: set = set()
    with p.open(encoding="utf-8") as f:
        for line_idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception as e:
                raise ValueError(
                    f"Error parsing line {line_idx} of relation overrides file: {e}"
                )

            guid = r.get("guid")
            word = r.get("word")
            pos = r.get("pos")
            cefr = r.get("cefr")
            original_example = r.get("original_example")
            action = r.get("action")

            if not all([guid, word, pos, cefr, original_example, action]):
                raise ValueError(
                    f"Error line {line_idx}: missing one of required fields "
                    f"(guid, word, pos, cefr, original_example, action)"
                )

            guid = guid.strip()
            word = word.strip()
            pos = pos.strip()
            cefr = cefr.strip()
            original_example = original_example.strip()
            action = action.strip().lower()

            if action not in ("annotate", "skip"):
                raise ValueError(f"Error line {line_idx}: invalid action {action!r}")

            if action == "annotate":
                annotated_example = r.get("annotated_example")
                if not annotated_example or not annotated_example.strip():
                    raise ValueError(
                        f"Error line {line_idx}: missing annotated_example for action 'annotate'"
                    )
                source_example = r.get("source_example")
                if not source_example or not source_example.strip():
                    raise ValueError(
                        f"Error line {line_idx}: missing source_example for action 'annotate'"
                    )
            else:
                reason = r.get("reason")
                if not reason or not reason.strip():
                    raise ValueError(
                        f"Error line {line_idx}: missing reason for action 'skip'"
                    )

            key = (guid, clean_for_matching(original_example))
            if key in seen_overrides:
                raise ValueError(
                    f"Duplicate override for GUID {guid!r} and example "
                    f"{original_example!r} at line {line_idx}"
                )
            seen_overrides.add(key)

            overrides.setdefault(guid, []).append(r)

    return overrides


# Back-compat alias for legacy call sites.
def load_synonym_overrides(path: Path | str | None) -> dict[str, list[dict]]:
    return load_relation_overrides(path)


# -----------------------------------------------------------------------------
# Text normalization helpers
# -----------------------------------------------------------------------------

def clean_for_matching(text: str) -> str:
    cleaned = text.replace("\u2019", "'").replace("\u2018", "'").replace(
        "\u201c", '"'
    ).replace("\u201d", '"')
    return " ".join(cleaned.lower().split())


# -----------------------------------------------------------------------------
# Auto-annotator primitives (used for both synonyms and antonyms)
# -----------------------------------------------------------------------------

def _strip_annotations_for_words(chunk: str, words: list[str]) -> str:
    """Remove parenthesized annotations whose comma-separated contents are all
    members of `words` (case-insensitive). Used to scrub existing relations
    before re-annotating so re-runs are stable (idempotent).

    Uses whole-word matching within the paren so substrings like
    "inexpensive" do NOT collide with "expensive".
    """
    if not words:
        return chunk

    words_lower = {w.lower().strip() for w in words}

    def replace_fn(match):
        content = match.group(1).lower()
        items = [w.strip() for w in content.split(",") if w.strip()]
        if items and all(w in words_lower for w in items):
            return ""
        return match.group(0)

    return re.sub(r"\s+\(([^)]+)\)", replace_fn, chunk)


def _has_annotation_for_any(chunk: str, words: list[str]) -> bool:
    """True when any word in `words` appears as a whole word inside any paren.

    Uses `\b` word boundaries so substrings like "inexpensive" do NOT match
    "expensive" — both lexemes are independent tokens. The word may appear
    anywhere inside the paren (e.g. "(clear, obvious)" matches "obvious"),
    not only as the first token.
    """
    if not words:
        return True
    chunk_lower = chunk.lower()
    for w in words:
        pattern = r"\([^()]*\b" + re.escape(w.lower().strip()) + r"\b[^()]*\)"
        if re.search(pattern, chunk_lower):
            return True
    return False


def matches_lemma(word_in_chunk: str, headword: str) -> bool:
    w_lower = word_in_chunk.lower().strip()
    h_lower = headword.lower().strip()
    if w_lower == h_lower:
        return True
    for p in ("n", "v", "a", "r"):
        try:
            lemma = lemmatizer.lemmatize(w_lower, pos=p)
            if lemma == h_lower:
                return True
        except Exception:
            pass
    return False


def _get_particles(words: list[str]) -> set[str]:
    particles = {"off", "out", "up", "down", "away", "in", "on", "back", "about", "over"}
    found: set[str] = set()
    for w in words:
        for tok in re.split(r"[\s\-]+", w):
            if tok.strip().lower() in particles:
                found.add(tok.strip().lower())
    return found


def _find_headword_tail_end(chunk: str, headword: str, particles: set[str]) -> int | None:
    """Return the insertion offset after the headword + any immediately-
    following parenthetical chain (separated from the headword only by
    whitespace).

    Used by the relation annotator so a second relation (e.g. antonym)
    appends AFTER an already-inserted relation (e.g. synonym) instead of
    between the headword and the first relation.

    Returns the offset to insert at, or None if the headword is not found.

    Examples:
        chunk = "a cheap (inexpensive) car", headword="cheap"
        → returns offset right after "(inexpensive)" (between ")" and " car")
        chunk = "Fish are abundant in the lake.", headword="abundant"
        → returns offset right after "abundant" (between "t" and " in")
    """
    if particles:
        headword_re = (
            r"\b" + re.escape(headword.lower().strip())
            + r"(?:\s+(?:" + "|".join(re.escape(p) for p in particles) + r"))?\b"
        )
    else:
        headword_re = r"\b" + re.escape(headword.lower().strip()) + r"\b"

    match = re.search(headword_re, chunk.lower())
    if match:
        tail_start = match.end()
    else:
        # Fall back to lemmatized word-match.
        words_iter = list(re.finditer(r"\b[a-zA-Z]+(?:'[a-zA-Z]+)?\b", chunk))
        tail_start = None
        for idx_w, m in enumerate(words_iter):
            if matches_lemma(m.group(), headword):
                tail_start = m.end()
                if idx_w + 1 < len(words_iter):
                    nxt = words_iter[idx_w + 1]
                    if nxt.group().lower() in particles:
                        between = chunk[m.end():nxt.start()]
                        if not between.strip():
                            tail_start = nxt.end()
                break
        if tail_start is None:
            return None

    # Walk past whitespace + immediately-following parentheticals.
    # We only consume whitespace that's required to reach the next paren.
    n = len(chunk)
    while tail_start < n:
        # Require a paren directly after the headword (or current position),
        # optionally preceded by whitespace. The whitespace consumed here is
        # necessary for the paren to be "immediately following".
        if chunk[tail_start] == "(":
            depth = 1
            i = tail_start + 1
            while i < n and depth > 0:
                if chunk[i] == "(":
                    depth += 1
                elif chunk[i] == ")":
                    depth -= 1
                i += 1
            if depth != 0:
                return tail_start  # unbalanced — bail
            tail_start = i
        elif chunk[tail_start].isspace():
            # Peek ahead: if the next non-space char is '(', consume the space;
            # otherwise leave the whitespace alone so the caller inserts there.
            j = tail_start
            while j < n and chunk[j].isspace():
                j += 1
            if j < n and chunk[j] == "(":
                tail_start = j  # skip space, fall through to paren handling
            else:
                break
        else:
            break
    return tail_start


def _annotate_chunk_with_words(
    chunk: str,
    headword: str,
    words: list[str],
) -> str | None:
    """Insert ` (w1, w2, ...)` after the first headword occurrence in chunk.

    Returns annotated chunk, or None if no headword match was found. Phrasal
    verb particles (off/out/up/...) are detected and consumed if the relation
    word is itself a phrasal verb (e.g. 'set off').

    Insertion position: after the headword + any immediately-following
    parenthetical chain. This lets multiple relations stack in order
    (synonym → antonym) without one sliding in between the headword and
    the other.
    """
    if not words:
        return chunk

    cleaned = _strip_annotations_for_words(chunk, words)
    if _has_annotation_for_any(cleaned, words):
        return cleaned

    rels = [w.strip() for w in words if w.strip()]
    if not rels:
        return cleaned

    particles = _get_particles(rels)
    insert_at = _find_headword_tail_end(cleaned, headword, particles)
    if insert_at is None:
        return None

    rel_str = f" ({', '.join(rels)})"
    return cleaned[:insert_at] + rel_str + cleaned[insert_at:]


# -----------------------------------------------------------------------------
# Override validation
# -----------------------------------------------------------------------------

def _validate_override_words(
    original: str,
    annotated: str,
    allowed_words: list[str],
    relation_label: str,
) -> list[str]:
    """Strict gate: every parenthesized token in `annotated` not present in
    `original` must appear in `allowed_words` (the sense's synonyms or
    antonyms list)."""
    errors: list[str] = []
    allowed_set = {w.lower().strip() for w in allowed_words}

    orig_parents = set(re.findall(r"\(([^)]+)\)", original.lower()))
    annotated_parents = re.findall(r"\(([^)]+)\)", annotated.lower())

    for p in annotated_parents:
        if p in orig_parents:
            continue
        items = [w.strip() for w in p.split(",") if w.strip()]
        if not items:
            errors.append(f"Empty parenthesized annotation found in: {annotated!r}")
            continue
        for w in items:
            if w not in allowed_set:
                errors.append(
                    f"{relation_label} {w!r} inside parenthesis in manual mapping is "
                    f"not associated with this sense's {relation_label.lower()}s: {allowed_words}"
                )
    return errors


# Back-compat synonym-only validator.
def _validate_override_synonyms(original: str, annotated: str, allowed_synonyms: list[str]) -> list[str]:
    return _validate_override_words(original, annotated, allowed_synonyms, "Synonym")


# -----------------------------------------------------------------------------
# Override resolution helpers
# -----------------------------------------------------------------------------

def _check_card_identity(
    actual_word_clean: str,
    actual_pos: str,
    actual_cefr: str,
    guid: str,
    ov_map: dict[str, list[dict]],
    ov_kind: str,
    errors: list[str],
) -> None:
    """Push card-identity mismatch errors for every override of this GUID."""
    for entry in ov_map.get(guid, []):
        expected_word = entry.get("word", "").strip().lower()
        expected_pos = entry.get("pos", "").strip().lower()
        expected_cefr = entry.get("cefr", "").strip().upper()
        if (
            actual_word_clean != expected_word
            or actual_pos != expected_pos
            or actual_cefr != expected_cefr
        ):
            errors.append(
                f"Card identity mismatch for {ov_kind} override GUID {guid!r}: "
                f"override expected ({expected_word!r}, {expected_pos!r}, {expected_cefr!r}), "
                f"got ({actual_word_clean!r}, {actual_pos!r}, {actual_cefr!r})"
            )


def _consume_override_for_chunk(
    ov_map: dict[str, list[dict]],
    guid: str,
    used_idxs: set[int],
    chunk_clean: str,
) -> dict | None:
    """Return the first unused override whose original_example matches chunk."""
    for idx, entry in enumerate(ov_map.get(guid, [])):
        if idx in used_idxs:
            continue
        if clean_for_matching(entry.get("original_example") or "") == chunk_clean:
            used_idxs.add(idx)
            return entry
    return None


def _apply_annotate_override(
    override_entry: dict,
    specs: list[dict],
    chunk_spec: dict | None,
    relation_label: str,
    cleaned_chunk: str,
    card: "BuiltCard",
    original_chunk: str,
    errors: list[str],
) -> list[str]:
    """Apply an `annotate` override. Returns the relation words (empty on error).

    Looks up the matching spec by source_example text. We scan the entire
    `specs` list (not just `chunk_spec`) because an override can reference an
    Oxford example that didn't end up on this chunk — i.e. the chunk text
    was glosstext-mangled and no longer matches Oxford verbatim, but the
    override's `source_example` is the original Oxford text.

    Validation:
      - source_example must match some spec's text.
      - the relation channel must have at least one allowed word on that spec.
      - annotated_example's new parenthesized tokens must all be in allowed_words.
      - the base text (after stripping allowed annotations) must equal the
        cleaned chunk text.
    """
    source_ex = override_entry.get("source_example") or ""
    if not source_ex.strip():
        errors.append(
            f"Missing source_example in annotate {relation_label} override for "
            f"card {card.word} ({card.guid}) for example {original_chunk!r}"
        )
        return []

    matched_spec = None
    source_ex_clean = clean_for_matching(source_ex)
    # First try the chunk's own spec (cheap path), then scan all specs.
    if chunk_spec is not None and clean_for_matching(chunk_spec.get("text") or "") == source_ex_clean:
        matched_spec = chunk_spec
    else:
        for sp in specs:
            if clean_for_matching(sp.get("text") or "") == source_ex_clean:
                matched_spec = sp
                break
    if matched_spec is None:
        errors.append(
            f"source_example {source_ex!r} in {relation_label} override does not match "
            f"any Oxford spec for card {card.word} ({card.guid})"
        )
        return []

    allowed_key = relation_label + "s"  # "synonyms" or "antonyms"
    allowed = matched_spec.get(allowed_key) or []
    if not allowed:
        errors.append(
            f"source_example {source_ex!r} has no {relation_label} list on card "
            f"{card.word} ({card.guid})"
        )
        return []

    annotated_ex = override_entry.get("annotated_example") or ""
    stripped = _strip_annotations_for_words(annotated_ex, allowed)
    if stripped.strip() != cleaned_chunk.strip():
        errors.append(
            f"Base text modified in {relation_label} override for {card.word} ({card.guid}): "
            f"cleaned chunk {cleaned_chunk!r}, stripped override {stripped!r}"
        )

    validation_errors = _validate_override_words(
        cleaned_chunk, annotated_ex, allowed, relation_label.capitalize()
    )
    if validation_errors:
        errors.extend(
            f"Manual {relation_label} override validation failed for "
            f"{card.word} ({card.guid}): {err}"
            for err in validation_errors
        )
    return list(allowed)


def _apply_relation_channel(
    output_text: str,
    validation_text: str,
    original_text: str,
    actual_word_clean: str,
    card: "BuiltCard",
    specs: list[dict],
    chunk_spec: dict | None,
    relation_label: str,
    override: dict | None,
    errors: list[str],
) -> tuple[str, list[str], bool]:
    """Apply one synonym/antonym channel through the shared relation flow."""
    relation_key = relation_label + "s"
    if override is not None:
        action = (override.get("action") or "").strip().lower()
        if action == "skip":
            if chunk_spec is not None and (chunk_spec.get(relation_key) or []):
                errors.append(
                    f"Skip action not allowed for exact sense with {relation_key} on "
                    f"card {card.word} ({card.guid}) for example {original_text!r}"
                )
            return output_text, [], True

        words = _apply_annotate_override(
            override,
            specs,
            chunk_spec,
            relation_label,
            validation_text,
            card,
            original_text,
            errors,
        )
        return override.get("annotated_example") or output_text, words, True

    if chunk_spec is None:
        return output_text, [], False

    words = list(chunk_spec.get(relation_key) or [])
    if not words:
        return output_text, [], False

    annotated = _annotate_chunk_with_words(output_text, actual_word_clean, words)
    if annotated is None:
        errors.append(
            f"Unresolved auto-annotation ({relation_label}) for {card.word} "
            f"({card.guid}) example: {original_text!r}. "
            f"{relation_key.capitalize()} of sense: {words}. Please add a manual override."
        )
        return output_text, [], False
    return annotated, words, False


# -----------------------------------------------------------------------------
# Card-level annotation
# -----------------------------------------------------------------------------

_SAME_SENSE_BREAK_RE = re.compile(r"((?:<br\s*/?>\s*)+)", re.IGNORECASE)


def _split_same_sense_examples(chunk: str) -> list[tuple[str, str]]:
    """Return ``(separator_before, example)`` pairs for one sense chunk."""
    parts = _SAME_SENSE_BREAK_RE.split(chunk)
    examples: list[tuple[str, str]] = []
    separator = ""
    for idx, part in enumerate(parts):
        if idx % 2:
            separator = part
            continue
        example = part.strip()
        if example:
            examples.append((separator, example))
            separator = ""
    return examples


def _annotate_same_sense_examples(
    chunk: str,
    card: "BuiltCard",
    specs: list[dict],
    all_syns: list[str],
    all_ants: list[str],
    synonym_overrides: dict[str, list[dict]],
    antonym_overrides: dict[str, list[dict]],
    syn_used_idxs: set[int],
    ant_used_idxs: set[int],
) -> tuple[str, list[str], list[str], list[str]]:
    """Annotate examples joined by HTML breaks while keeping one pipe cell."""
    annotated_parts: list[str] = []
    syn_words: list[str] = []
    ant_words: list[str] = []
    errors: list[str] = []
    has_any_syns = any(spec and spec.get("synonyms") for spec in specs)
    has_any_ants = any(spec and spec.get("antonyms") for spec in specs)
    actual_word_clean = re.sub(r"\s*\(.*?\)\s*", "", card.word).strip().lower()

    for separator, original_example in _split_same_sense_examples(chunk):
        cleaned_example = original_example
        if all_syns:
            cleaned_example = _strip_annotations_for_words(cleaned_example, all_syns)
        if all_ants:
            cleaned_example = _strip_annotations_for_words(cleaned_example, all_ants)

        example_clean = clean_for_matching(cleaned_example)
        spec = next(
            (
                candidate
                for candidate in specs
                if candidate
                and clean_for_matching(candidate.get("text") or "") == example_clean
            ),
            None,
        )

        syn_override = _consume_override_for_chunk(
            synonym_overrides, card.guid, syn_used_idxs, example_clean
        )
        ant_override = _consume_override_for_chunk(
            antonym_overrides, card.guid, ant_used_idxs, example_clean
        )

        validation_text = cleaned_example
        cleaned_example, example_syns, syn_consumed = _apply_relation_channel(
            cleaned_example,
            validation_text,
            original_example,
            actual_word_clean,
            card,
            specs,
            spec,
            "synonym",
            syn_override,
            errors,
        )
        cleaned_example, example_ants, ant_consumed = _apply_relation_channel(
            cleaned_example,
            validation_text,
            original_example,
            actual_word_clean,
            card,
            specs,
            spec,
            "antonym",
            ant_override,
            errors,
        )

        if spec is None:
            unresolved_syns = has_any_syns and not syn_consumed
            unresolved_ants = has_any_ants and not ant_consumed
            if unresolved_syns or unresolved_ants:
                errors.append(
                    f"Unresolved alignment for {card.word} ({card.guid}) example: "
                    f"{original_example!r}. Could not map it to any Oxford sense. "
                    "Please add a manual override."
                )

        for word in example_syns:
            if word not in syn_words:
                syn_words.append(word)
        for word in example_ants:
            if word not in ant_words:
                ant_words.append(word)

        annotated_parts.append(separator + cleaned_example)

    return "".join(annotated_parts), syn_words, ant_words, errors

def annotate_card_examples(
    card: "BuiltCard",
    specs: list[dict],
    synonym_overrides: dict[str, list[dict]] | None = None,
    antonym_overrides: dict[str, list[dict]] | None = None,
) -> tuple[str, str, str, list[str]]:
    """Annotate card examples with synonyms AND antonyms of exact Oxford senses.

    Returns (annotated_example, synonyms_metadata, antonyms_metadata, errors).
    `synonyms_metadata` and `antonyms_metadata` are pipe-aligned with the
    original Example chunks (one cell per chunk, empty when no relation).
    """
    errors: list[str] = []
    synonym_overrides = synonym_overrides or {}
    antonym_overrides = antonym_overrides or {}

    if not card.example.strip():
        return "", "", "", errors

    chunks = [ch.strip() for ch in card.example.split("|")]
    annotated_chunks: list[str] = []
    syn_metadata: list[str] = []
    ant_metadata: list[str] = []

    # Union of all relation words across specs (used to scrub existing parens).
    all_syns: list[str] = []
    all_ants: list[str] = []
    for spec in specs:
        if not spec:
            continue
        for s in spec.get("synonyms") or []:
            all_syns.append(s.strip())
        for a in spec.get("antonyms") or []:
            all_ants.append(a.strip())

    actual_word_clean = re.sub(r"\s*\(.*?\)\s*", "", card.word).strip().lower()
    actual_pos = card.pos.strip().lower()
    actual_cefr = card.cefr.strip().upper()

    # -- Card identity guard for ALL overrides on this card --
    _check_card_identity(
        actual_word_clean, actual_pos, actual_cefr,
        card.guid, synonym_overrides, "synonym", errors
    )
    _check_card_identity(
        actual_word_clean, actual_pos, actual_cefr,
        card.guid, antonym_overrides, "antonym", errors
    )

    syn_used_idxs: set[int] = set()
    ant_used_idxs: set[int] = set()

    for original_chunk in chunks:
        same_sense_examples = _split_same_sense_examples(original_chunk)
        if len(same_sense_examples) > 1:
            annotated_chunk, syn_words, ant_words, chunk_errors = (
                _annotate_same_sense_examples(
                    original_chunk,
                    card,
                    specs,
                    all_syns,
                    all_ants,
                    synonym_overrides,
                    antonym_overrides,
                    syn_used_idxs,
                    ant_used_idxs,
                )
            )
            annotated_chunks.append(annotated_chunk)
            syn_metadata.append(", ".join(syn_words))
            ant_metadata.append(", ".join(ant_words))
            errors.extend(chunk_errors)
            continue

        # Scrub pre-existing relation annotations.
        cleaned_chunk = original_chunk
        if all_syns:
            cleaned_chunk = _strip_annotations_for_words(cleaned_chunk, all_syns)
        if all_ants:
            cleaned_chunk = _strip_annotations_for_words(cleaned_chunk, all_ants)

        chunk_clean = clean_for_matching(cleaned_chunk)

        # Find the spec for this chunk by exact text match (no guessing).
        chunk_spec = next(
            (sp for sp in specs if sp and clean_for_matching(sp.get("text") or "") == chunk_clean),
            None,
        )

        syn_words: list[str] = []
        ant_words: list[str] = []
        syn_override = _consume_override_for_chunk(
            synonym_overrides, card.guid, syn_used_idxs, chunk_clean
        )
        ant_override = _consume_override_for_chunk(
            antonym_overrides, card.guid, ant_used_idxs, chunk_clean
        )
        validation_text = cleaned_chunk
        cleaned_chunk, syn_words, syn_override_consumed = _apply_relation_channel(
            cleaned_chunk,
            validation_text,
            original_chunk,
            actual_word_clean,
            card,
            specs,
            chunk_spec,
            "synonym",
            syn_override,
            errors,
        )
        cleaned_chunk, ant_words, ant_override_consumed = _apply_relation_channel(
            cleaned_chunk,
            validation_text,
            original_chunk,
            actual_word_clean,
            card,
            specs,
            chunk_spec,
            "antonym",
            ant_override,
            errors,
        )

        if chunk_spec is None:
            # chunk_spec is None — chunk doesn't map to any Oxford example.
            # Per legacy semantics: report unresolved only if some spec carries
            # relations AND no override was used to suppress annotation.
            has_any_syns = any(sp and sp.get("synonyms") for sp in specs)
            has_any_ants = any(sp and sp.get("antonyms") for sp in specs)
            if (
                not syn_override_consumed
                and not ant_override_consumed
                and (has_any_syns or has_any_ants)
            ):
                errors.append(
                    f"Unresolved alignment for {card.word} ({card.guid}) chunk: "
                    f"{original_chunk!r}. Could not map chunk to any Oxford sense. "
                    f"Please add a manual override."
                )

        annotated_chunks.append(cleaned_chunk)
        syn_metadata.append(", ".join(syn_words))
        ant_metadata.append(", ".join(ant_words))

    # -- Check for unused overrides for this card --
    for ov_kind, ov_map, used in (
        ("synonym", synonym_overrides, syn_used_idxs),
        ("antonym", antonym_overrides, ant_used_idxs),
    ):
        for idx, entry in enumerate(ov_map.get(card.guid, [])):
            if idx in used:
                continue
            errors.append(
                f"Unused manual {ov_kind} override for {card.word} ({card.guid}) with "
                f"example: {entry.get('original_example')!r}. Does not match any "
                f"cleaned example chunk."
            )

    return (
        "|".join(annotated_chunks),
        "|".join(syn_metadata),
        "|".join(ant_metadata),
        errors,
    )


# -----------------------------------------------------------------------------
# Card → spec resolution
# -----------------------------------------------------------------------------

def get_relation_specs_for_card(card: "BuiltCard", senses_index: dict) -> list[dict]:
    """Return one spec per source example for the card's (word, pos, cefr).

    Each spec is {"text": ex_text, "synonyms": syns, "antonyms": ants}.
    The annotator uses these specs to apply exact Oxford relations to
    matching example chunks.

    `senses_index` is the (word, pos, cefr) → list[MergedSense] map built by
    build_notes. We pull antonyms from the per-example dict attached by
    simplify_senses (each example carries the sense's relations), and fall
    back to the merged sense's `relation_specs` list for compatibility.

    When multiple source senses share the same example text, we **union**
    their relations (first-appearance order) instead of letting later
    senses shadow earlier ones. This protects the contract "the annotator
    uses these specs to apply exact Oxford relations" — losing relations
    to last-wins would silently strip metadata.
    """
    pos_parts = [p.strip().lower() for p in card.pos.split(",") if p.strip()]
    specs: list[dict] = []
    word_lower = card.word.lower()
    cefr = card.cefr or "UNCLASSIFIED"

    for p in pos_parts:
        key = (word_lower, p, cefr)
        if key not in senses_index:
            continue
        for ms in senses_index[key]:
            # Build a per-example text → (synonyms, antonyms) lookup from the
            # merged sense's relation_specs (single source of truth).
            rel_map: dict[str, dict] = {}
            for rs in (getattr(ms, "relation_specs", None) or []):
                rel_map[rs.get("text") or ""] = rs

            for ex_dict in ms.examples or []:
                ex_text = (ex_dict.get("text") or "").strip()
                if not ex_text:
                    continue
                rel = rel_map.get(ex_text) or {}
                specs.append({
                    "text": ex_text,
                    "synonyms": list(rel.get("synonyms") or []),
                    "antonyms": list(rel.get("antonyms") or []),
                })

    # Union relations across specs that share the same example text.
    # First-appearance order is preserved.
    unioned: dict[str, dict] = {}
    for sp in specs:
        text = sp.get("text") or ""
        if not text:
            continue
        if text not in unioned:
            unioned[text] = {
                "text": text,
                "synonyms": list(sp.get("synonyms") or []),
                "antonyms": list(sp.get("antonyms") or []),
            }
            continue
        cur = unioned[text]
        for w in (sp.get("synonyms") or []):
            if w not in cur["synonyms"]:
                cur["synonyms"].append(w)
        for w in (sp.get("antonyms") or []):
            if w not in cur["antonyms"]:
                cur["antonyms"].append(w)

    # Preserve the first-appearance order of unique texts (matches the
    # iteration order of the source senses).
    seen: set[str] = set()
    out: list[dict] = []
    for sp in specs:
        t = sp.get("text") or ""
        if t and t not in seen:
            seen.add(t)
            out.append(unioned[t])
    return out


# Back-compat: legacy synonym-only spec resolver.
def get_synonyms_specs_for_card(card: "BuiltCard", senses_index: dict) -> list[dict]:
    rel_specs = get_relation_specs_for_card(card, senses_index)
    return [{"text": s["text"], "synonyms": s["synonyms"]} for s in rel_specs]


# -----------------------------------------------------------------------------
# Legacy function-name aliases (kept so existing tests / external call sites
# continue to work after the rename in the lexical-relations refactor).
# -----------------------------------------------------------------------------
strip_synonym_annotations = _strip_annotations_for_words
is_already_annotated = _has_annotation_for_any


def annotate_chunk_auto(chunk: str, headword: str, synonyms: list[str]) -> str | None:
    """Legacy synonym-only auto-annotator wrapper around `_annotate_chunk_with_words`."""
    return _annotate_chunk_with_words(chunk, headword, synonyms)
