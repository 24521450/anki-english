"""Scoped Cambridge English–Vietnamese snapshot parsing and serialization."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

from lxml import etree
from lxml import html as lxml_html


SCHEMA_VERSION = 1
BASE_URL = "https://dictionary.cambridge.org/dictionary/english-vietnamese"
LOOKUP_ALIASES = {
    "adhere to": "adhere",
    "contend with sb/sth": "contend",
    "derive from": "derive",
    "deprive of": "deprive",
    "devote sth to sth": "devote",
}
SUPPLEMENTAL_LOOKUPS = {
    "provisions": "lexicalized_plural_source_evidence",
}

_DISPLAY_QUALIFIER_RE = re.compile(r"\s+\([^()]+\)\s*$")
_WHITESPACE_RE = re.compile(r"\s+")
_NO_ENTRY_MARKERS = (
    "we didn't find",
    "we did not find",
    "no results for",
    "no entries found",
)
_DICTIONARY_HOME_TITLE = (
    "Cambridge English–Vietnamese Dictionary: Translate from English to Vietnamese"
)


class CambridgeEnglishVietnameseParseError(ValueError):
    """Raised when cached HTML is neither a dictionary entry nor a no-result page."""


def normalize_text(value: object) -> str:
    return _WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", str(value or ""))).strip()


def normalize_lookup_headword(value: object) -> str:
    text = _DISPLAY_QUALIFIER_RE.sub("", normalize_text(value))
    return unicodedata.normalize("NFC", text.casefold())


def lookup_headword_for(word: object) -> tuple[str, str]:
    normalized = normalize_lookup_headword(word)
    aliased = LOOKUP_ALIASES.get(normalized)
    return (aliased or normalized), ("lookup_alias" if aliased else "card_identity")


def lookup_slug(headword: str) -> str:
    return quote(headword.replace(" ", "-"), safe="-")


def requested_url(headword: str) -> str:
    return f"{BASE_URL}/{lookup_slug(headword)}"


def build_lookup_plan(registry_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group active Card Identities under deterministic reviewed lookups."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    active_rows = [row for row in registry_rows if row.get("status") == "active"]
    for row in active_rows:
        lookup, reason = lookup_headword_for(row.get("word"))
        grouped.setdefault(lookup, []).append({
            "guid": str(row.get("guid") or ""),
            "word": str(row.get("word") or ""),
            "variant": str(row.get("variant") or ""),
            "pos": str(row.get("pos") or ""),
            "card_status": "active",
            "reason": reason,
        })

    provision_rows = [
        row
        for row in active_rows
        if lookup_headword_for(row.get("word"))[0] == "provision"
    ]
    if provision_rows:
        primary_rows = [
            row
            for row in provision_rows
            if str(row.get("variant") or "") == "primary"
        ]
        legacy_rows = [
            row for row in provision_rows if str(row.get("variant") or "") == ""
        ]
        if len(primary_rows) == 1:
            provision = primary_rows[0]
        elif not primary_rows and len(provision_rows) == 1 and len(legacy_rows) == 1:
            provision = legacy_rows[0]
        else:
            raise ValueError(
                "supplemental 'provisions' requires exactly one active "
                "'provision' owner with variant 'primary', or exactly one legacy "
                "unsplit owner with variant ''"
            )
        for lookup, reason in SUPPLEMENTAL_LOOKUPS.items():
            grouped.setdefault(lookup, []).append({
                "guid": str(provision.get("guid") or ""),
                "word": str(provision.get("word") or ""),
                "variant": str(provision.get("variant") or ""),
                "pos": str(provision.get("pos") or ""),
                "card_status": "active",
                "reason": reason,
            })

    plan = []
    for lookup, requests in grouped.items():
        unique = {
            (
                request["guid"],
                request["word"],
                request["variant"],
                request["pos"],
                request["card_status"],
                request["reason"],
            ): request
            for request in requests
        }
        plan.append({
            "lookup_headword": lookup,
            "requested_url": requested_url(lookup),
            "coverage_requests": sorted(
                unique.values(), key=_coverage_sort_key
            ),
        })
    return sorted(plan, key=lambda item: item["lookup_headword"])


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _first(root, selectors: tuple[str, ...]):
    for selector in selectors:
        matches = root.cssselect(selector)
        if matches:
            return matches[0]
    return None


def _text(element) -> str:
    return normalize_text(element.text_content()) if element is not None else ""


def _direct_dictionary_entries(root) -> list[Any]:
    dictionaries = root.cssselect(".pr.dictionary")
    if not dictionaries:
        dictionaries = root.cssselect(".dictionary")
    scope = dictionaries[0] if dictionaries else root
    entries = scope.cssselect(".d.pr.di.english-vietnamese.kdic")
    if not entries:
        entries = scope.cssselect(".entry-body__el")
    if not entries:
        entries = scope.cssselect(".entry-body")
    return [
        entry for entry in entries
        if not any(
            (
                "entry-body__el" in (ancestor.get("class") or "").split()
                or {
                    "d",
                    "pr",
                    "di",
                    "english-vietnamese",
                    "kdic",
                }.issubset(set((ancestor.get("class") or "").split()))
            )
            for ancestor in entry.iterancestors()
            if ancestor is not scope
        )
    ]


def _sense_blocks(entry) -> list[Any]:
    blocks = entry.cssselect(".sense-block")
    if not blocks:
        blocks = entry.cssselect(".def-block.ddef_block")
    return blocks or entry.cssselect(".def-block")


def _parse_examples(sense) -> list[dict[str, str | None]]:
    examples: list[dict[str, str | None]] = []
    for block in sense.cssselect(".examp.dexamp, .examp"):
        english = _text(_first(block, (".eg.deg", ".eg")))
        if not english:
            continue
        translation = _text(_first(block, (".trans.dtrans", ".trans")))
        examples.append({
            "text_en": english,
            "translation_vi": translation or None,
        })
    return examples


def _definition_translation(sense) -> str:
    for translation in sense.cssselect(".trans.dtrans, .trans"):
        if any(
            "examp" in (ancestor.get("class") or "").split()
            or "dexamp" in (ancestor.get("class") or "").split()
            for ancestor in translation.iterancestors()
            if ancestor is not sense
        ):
            continue
        return _text(translation)
    return ""


def _parse_entries(root, lookup_headword: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for entry in _direct_dictionary_entries(root):
        entry_order = len(parsed) + 1
        header = _first(
            entry,
            (".dpos-h.di-head", ".pos-header.dpos-h", ".dpos-h", ".pos-header"),
        )
        header_scope = header if header is not None else entry
        headword = (
            _text(
                _first(
                    header_scope,
                    (".dpos-h_hw.di-title", ".dhw", ".hw.dhw", ".headword", ".hw"),
                )
            )
            or lookup_headword
        )
        pos = _text(_first(header_scope, (".pos.dpos", ".pos")))
        grammar = _text(_first(header_scope, (".gram.dgram", ".gram")))
        source_entry_dom_id = (
            normalize_text(entry.get("id"))
            or normalize_text(header_scope.get("id"))
            or None
        )
        senses: list[dict[str, Any]] = []
        for sense in _sense_blocks(entry):
            definition = _text(_first(sense, (".def.ddef_d", ".def")))
            translation = _definition_translation(sense)
            if not definition and not translation:
                continue
            sense_order = len(senses) + 1
            examples = _parse_examples(sense)
            sense_payload = {
                "lookup_headword": lookup_headword,
                "headword": headword,
                "pos": pos,
                "grammar": grammar,
                "definition_en": definition or None,
                "translation_vi": translation or None,
                "examples": examples,
            }
            sense_fingerprint = _fingerprint(sense_payload)
            sense_classes = set((sense.get("class") or "").split())
            definition_block = (
                sense
                if "def-block" in sense_classes
                else _first(sense, (".def-block.ddef_block", ".def-block"))
            )
            wordlist_id = (
                normalize_text(definition_block.get("data-wl-senseid"))
                if definition_block is not None
                else ""
            )
            cid = _first(sense, (".cid",))
            dom_id = (
                wordlist_id
                or normalize_text(cid.get("id") if cid is not None else "")
                or normalize_text(sense.get("id"))
            )
            sense_identity = {
                "lookup_headword": lookup_headword,
                "entry_order": entry_order,
                "headword": headword,
                "pos": pos,
                "grammar": grammar,
                "source_wordlist_sense_id": dom_id or None,
                "sense_order": sense_order,
            }
            senses.append({
                "source_sense_id": f"cev-sense:{_fingerprint(sense_identity)[:24]}",
                "source_wordlist_sense_id": dom_id or None,
                "sense_order": sense_order,
                "definition_en": definition or None,
                "translation_vi": translation or None,
                "translation_status": "found" if translation else "missing",
                "examples": examples,
                "sense_fingerprint": sense_fingerprint,
            })
        if not senses:
            continue
        entry_identity = {
            "lookup_headword": lookup_headword,
            "source_entry_dom_id": source_entry_dom_id,
            "entry_order": entry_order,
            "headword": headword,
            "pos": pos,
            "grammar": grammar,
        }
        parsed.append({
            "source_entry_id": f"cev-entry:{_fingerprint(entry_identity)[:24]}",
            "source_entry_dom_id": source_entry_dom_id,
            "entry_order": entry_order,
            "headword": headword,
            "pos": pos or None,
            "grammar": grammar or None,
            "senses": senses,
        })
    return parsed


def _is_dictionary_home_fallback(root, canonical_url: str | None) -> bool:
    """Recognize Cambridge's successful query-to-dictionary-home redirect."""
    if canonical_url != f"{BASE_URL}/":
        return False
    title = _text(_first(root, ("title",)))
    heading = _text(_first(root, ("h1",)))
    return bool(
        title == _DICTIONARY_HOME_TITLE
        and heading == "English–Vietnamese Dictionary"
        and root.cssselect("form#searchForm input#searchword")
    )


def _validated_cambridge_url(
    value: str,
    *,
    label: str,
    allow_query: bool = False,
) -> str:
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise CambridgeEnglishVietnameseParseError(
            f"invalid {label}: {value!r}"
        ) from exc
    root_path = "/dictionary/english-vietnamese/"
    if (
        parts.scheme != "https"
        or parts.hostname != "dictionary.cambridge.org"
        or parts.username is not None
        or parts.password is not None
        or port is not None
        or (parts.query and not allow_query)
        or parts.fragment
        or not (
            parts.path == root_path
            or (
                parts.path.startswith(root_path)
                and len(parts.path) > len(root_path)
            )
        )
    ):
        raise CambridgeEnglishVietnameseParseError(
            f"invalid {label}: {value!r}"
        )
    return value


def _validate_source_url_relation(
    *,
    lookup_headword: str,
    status: str,
    requested: str,
    response: str,
    canonical: str | None,
) -> None:
    expected_request = requested_url(lookup_headword)
    if requested != expected_request:
        raise CambridgeEnglishVietnameseParseError(
            f"requested URL does not match lookup {lookup_headword!r}"
        )
    _validated_cambridge_url(requested, label="requested URL")
    _validated_cambridge_url(response, label="response URL", allow_query=True)
    if canonical is None:
        raise CambridgeEnglishVietnameseParseError("missing canonical URL")
    _validated_cambridge_url(canonical, label="canonical URL")
    root_url = f"{BASE_URL}/"
    response_parts = urlsplit(response)
    response_without_query = response_parts._replace(query="").geturl()
    response_query = parse_qs(
        response_parts.query,
        keep_blank_values=True,
        strict_parsing=True,
    ) if response_parts.query else {}
    expected_query = unquote(urlsplit(requested).path.rsplit("/", 1)[-1])
    valid_response_query = (
        not response_query
        or response_query == {"q": [expected_query]}
    )
    if not valid_response_query:
        raise CambridgeEnglishVietnameseParseError(
            "response URL query does not bind the requested lookup slug"
        )
    if canonical == root_url:
        if status != "no_entry" or response != root_url:
            raise CambridgeEnglishVietnameseParseError(
                "dictionary-root redirect is valid only for explicit no_entry"
            )
    elif not (
        requested == response == canonical
        or response_without_query == canonical
    ):
        raise CambridgeEnglishVietnameseParseError(
            "response/canonical URL relation is not a supported Cambridge redirect"
        )


def parse_snapshot(
    html_bytes: bytes,
    *,
    lookup_headword: str,
    coverage_requests: list[dict[str, Any]],
    cache_file: str,
    response_url: str,
    http_status: int = 200,
) -> dict[str, Any]:
    """Parse one isolated cache page into one deterministic canonical row."""
    normalized_lookup = normalize_lookup_headword(lookup_headword)
    try:
        root = lxml_html.fromstring(html_bytes)
    except (ValueError, etree.ParserError) as exc:
        raise CambridgeEnglishVietnameseParseError("invalid HTML") from exc

    entries = _parse_entries(root, normalized_lookup)
    canonical_element = _first(root, ("link[rel='canonical']",))
    canonical_url = (
        normalize_text(canonical_element.get("href")) or None
        if canonical_element is not None
        else None
    )
    page_text = _text(root).casefold()
    no_entry = bool(
        root.cssselect(".no-results, .no-result, .didyoumean")
        or any(marker in page_text for marker in _NO_ENTRY_MARKERS)
        or _is_dictionary_home_fallback(root, canonical_url)
    )
    if not entries and not no_entry:
        raise CambridgeEnglishVietnameseParseError(
            f"unrecognized Cambridge English–Vietnamese page for {normalized_lookup!r}"
        )

    status = "found" if entries else "no_entry"
    request_url = requested_url(normalized_lookup)
    _validate_source_url_relation(
        lookup_headword=normalized_lookup,
        status=status,
        requested=request_url,
        response=response_url,
        canonical=canonical_url,
    )
    resolved_headword = entries[0]["headword"] if entries else None
    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "record_id": f"cev:{_fingerprint(normalized_lookup)[:24]}",
        "lookup_headword": normalized_lookup,
        "slug": lookup_slug(normalized_lookup),
        "status": status,
        "requested_url": request_url,
        "response_url": response_url,
        "canonical_url": canonical_url,
        "http_status": http_status,
        "resolved_headword": resolved_headword,
        "coverage_requests": sorted(
            coverage_requests,
            key=lambda item: (
                item["guid"],
                item["word"].casefold(),
                item["variant"],
                item["pos"],
                item["reason"],
            ),
        ),
        "source_metadata": {
            "publisher": "Cambridge University Press & Assessment",
            "dictionary": "Cambridge English–Vietnamese Dictionary",
            "source_language": "en",
            "target_language": "vi",
        },
        "snapshot": {
            "cache_file": cache_file,
            "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
        },
        "entries": entries,
    }
    row["record_fingerprint"] = _fingerprint(row)
    return row


def validate_record_integrity(row: dict[str, Any]) -> None:
    lookup = row["lookup_headword"]
    if row["record_id"] != f"cev:{_fingerprint(lookup)[:24]}":
        raise ValueError(f"invalid record_id for {lookup!r}")
    _validate_source_url_relation(
        lookup_headword=lookup,
        status=row["status"],
        requested=row["requested_url"],
        response=row["response_url"],
        canonical=row["canonical_url"],
    )
    expected_entry_orders = list(range(1, len(row["entries"]) + 1))
    if [entry["entry_order"] for entry in row["entries"]] != expected_entry_orders:
        raise ValueError(f"non-contiguous entry_order for {lookup!r}")
    entry_ids: set[str] = set()
    sense_ids: set[str] = set()
    for entry in row["entries"]:
        if entry["source_entry_id"] in entry_ids:
            raise ValueError(f"duplicate source_entry_id for {lookup!r}")
        entry_ids.add(entry["source_entry_id"])
        expected_sense_orders = list(range(1, len(entry["senses"]) + 1))
        if [sense["sense_order"] for sense in entry["senses"]] != expected_sense_orders:
            raise ValueError(f"non-contiguous sense_order for {lookup!r}")
        for sense in entry["senses"]:
            sense_payload = {
                "lookup_headword": lookup,
                "headword": entry["headword"],
                "pos": entry["pos"] or "",
                "grammar": entry["grammar"] or "",
                "definition_en": sense["definition_en"],
                "translation_vi": sense["translation_vi"],
                "examples": sense["examples"],
            }
            fingerprint = _fingerprint(sense_payload)
            if sense["sense_fingerprint"] != fingerprint:
                raise ValueError(f"stale sense_fingerprint for {lookup!r}")
            sense_identity = {
                "lookup_headword": lookup,
                "entry_order": entry["entry_order"],
                "headword": entry["headword"],
                "pos": entry["pos"] or "",
                "grammar": entry["grammar"] or "",
                "source_wordlist_sense_id": sense["source_wordlist_sense_id"],
                "sense_order": sense["sense_order"],
            }
            expected_sense_id = f"cev-sense:{_fingerprint(sense_identity)[:24]}"
            if sense["source_sense_id"] != expected_sense_id:
                raise ValueError(f"invalid source_sense_id for {lookup!r}")
            if sense["source_sense_id"] in sense_ids:
                raise ValueError(f"duplicate source_sense_id for {lookup!r}")
            sense_ids.add(sense["source_sense_id"])
        entry_identity = {
            "lookup_headword": lookup,
            "source_entry_dom_id": entry["source_entry_dom_id"],
            "entry_order": entry["entry_order"],
            "headword": entry["headword"],
            "pos": entry["pos"] or "",
            "grammar": entry["grammar"] or "",
        }
        expected_entry_id = f"cev-entry:{_fingerprint(entry_identity)[:24]}"
        if entry["source_entry_id"] != expected_entry_id:
            raise ValueError(f"invalid source_entry_id for {lookup!r}")
    unsigned = dict(row)
    fingerprint = unsigned.pop("record_fingerprint")
    if fingerprint != _fingerprint(unsigned):
        raise ValueError(f"stale record_fingerprint for {lookup!r}")


def _coverage_sort_key(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        item["guid"],
        item["word"].casefold(),
        item["variant"],
        item["pos"],
        item["reason"],
    )


def validate_snapshot_rows(
    rows: list[dict[str, Any]],
    *,
    expected_plan: list[dict[str, Any]] | None = None,
) -> None:
    """Validate deterministic order, fingerprints, and exact active coverage."""
    lookup_headwords: set[str] = set()
    previous_lookup = ""
    for index, row in enumerate(rows, start=1):
        lookup = row["lookup_headword"]
        if lookup <= previous_lookup:
            raise ValueError(
                f"snapshot rows are not strictly sorted at row {index}: {lookup!r}"
            )
        previous_lookup = lookup
        if lookup in lookup_headwords:
            raise ValueError(f"duplicate lookup_headword at row {index}: {lookup!r}")
        lookup_headwords.add(lookup)
        if row["coverage_requests"] != sorted(
            row["coverage_requests"],
            key=_coverage_sort_key,
        ):
            raise ValueError(f"unsorted coverage_requests for {lookup!r}")
        validate_record_integrity(row)

    if expected_plan is not None:
        expected = {
            item["lookup_headword"]: item["coverage_requests"]
            for item in expected_plan
        }
        actual = {
            row["lookup_headword"]: row["coverage_requests"] for row in rows
        }
        if actual != expected:
            raise ValueError("snapshot does not provide exact active Card Registry coverage")


def serialize_rows(rows: list[dict[str, Any]]) -> str:
    ordered = sorted(rows, key=lambda row: row["lookup_headword"])
    return "".join(_canonical_json(row) + "\n" for row in ordered)
