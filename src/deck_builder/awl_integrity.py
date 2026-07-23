"""Validate and normalize AWL POS/CEFR enrichment against dictionary sources."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from lxml import html as lxml_html

from src.deck_builder.corpus_tag_sync import POS_NORM
from src.deck_builder.simplify_senses import simplify_record


CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
HEADWORD_ALIASES = {
    "criteria": "criterion",
    "maximise": "maximize",
    "minimise": "minimize",
    "utilise": "utilize",
}
POS_DISPLAY = {
    "noun": "n.",
    "verb": "v.",
    "adjective": "adj.",
    "adverb": "adv.",
    "preposition": "prep.",
    "conjunction": "conj.",
    "pronoun": "pron.",
    "determiner": "det.",
    "number": "num.",
    "modal": "modal",
    "predeterminer": "predet.",
    "auxiliary": "aux.",
    "exclamation": "exclam.",
    "abbreviation": "abbr.",
    "phrasal verb": "phrasal v.",
}

# Cambridge renders these POS labels outside the CALD entry structure used by
# the cache parser. The values were verified against the official percent page.
CAMBRIDGE_POS_OVERRIDES = {
    ("percent", "adjective"): {"B1"},
    ("percent", "noun"): {"UNCLASSIFIED"},
}

# Oxford has two adjective levels for contrary. The existing AWL entry denotes
# the primary "opposite/different" sense, which is C1; C2 is a secondary sense.
PRIMARY_CEFR_OVERRIDES = {("contrary", "adjective"): "C1"}

ROW_RE = re.compile(
    r"\| \*\*([^*]+)\*\* \| ([^|]+) \| ([^|]+) \| ([^|]+) \|([^|]*)\|"
)


@dataclass(frozen=True, slots=True)
class AwlIntegrityPaths:
    awl_md: Path
    oxford_jsonl: Path
    cambridge_fallbacks_json: Path
    cambridge_cache_dir: Path | None = None


@dataclass(frozen=True, slots=True)
class AwlRow:
    line_number: int
    word: str
    pos: tuple[str, ...]
    cefr: str
    sublist: int
    note: str
    raw_line: str


@dataclass(frozen=True, slots=True)
class AwlCorrection:
    line_number: int
    word: str
    old_line: str
    new_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AwlAuditResult:
    proposed_text: str
    rows_before: int
    rows_after: int
    headword_count: int
    corrections: tuple[AwlCorrection, ...]
    errors: tuple[str, ...]


@dataclass(slots=True)
class _OxfordFacts:
    assigned: dict[str, set[str]]
    raw_pos: set[str]
    unbadged_pos: set[str]


def normalize_pos(value: str) -> str:
    pos = value.strip().rstrip(".").lower()
    aliases = {
        "phrasal v": "phrasal verb",
        "phrasal verb": "phrasal verb",
        "auxiliary verb": "auxiliary",
    }
    return aliases.get(pos, POS_NORM.get(pos, pos))


def split_pos(value: str) -> tuple[str, ...]:
    return tuple(
        normalize_pos(part)
        for part in re.split(r",|/", value)
        if part.strip()
    )


def parse_awl_rows(text: str) -> list[AwlRow]:
    rows: list[AwlRow] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("| **"):
            continue
        match = ROW_RE.fullmatch(line)
        if not match:
            raise ValueError(f"Malformed AWL row at line {line_number}: {line}")
        rows.append(AwlRow(
            line_number=line_number,
            word=match.group(1).strip(),
            pos=split_pos(match.group(2)),
            cefr=match.group(3).strip().upper(),
            sublist=int(match.group(4).strip()),
            note=match.group(5).strip(),
            raw_line=line,
        ))
    return rows


def parse_cambridge_pos_cefr(html_bytes: bytes) -> dict[str, set[str]]:
    """Extract POS-scoped CEFR from Cambridge entry blocks.

    Cambridge pages bundle CALD, American, and Business dictionaries. For each
    POS we use the first available dictionary in that order and never attach
    every page sense to every POS (the legacy JSONL parser currently does).
    """
    root = lxml_html.fromstring(html_bytes)
    grouped: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for entry in root.cssselect(".entry-body__el"):
        cid = entry.cssselect(".cid")
        entry_id = cid[0].get("id", "") if cid else ""
        if entry_id.startswith("cald"):
            dictionary = "cald"
        elif entry_id.startswith("cacd"):
            dictionary = "cacd"
        elif entry_id.startswith("cbed"):
            dictionary = "cbed"
        else:
            dictionary = "other"

        headers = entry.cssselect(".pos-header")
        if not headers:
            continue
        positions = {
            normalize_pos(node.text_content())
            for node in headers[0].cssselect("span.pos.dpos")
        }
        levels = {
            node.text_content().strip().upper()
            for node in entry.cssselect(".epp-xref")
            if node.text_content().strip().upper() in CEFR_LEVELS
        }
        if not levels:
            levels = {"UNCLASSIFIED"}
        for pos in positions:
            grouped[dictionary][pos].update(levels)

    result: dict[str, set[str]] = {}
    all_pos = {
        pos for dictionary in grouped.values() for pos in dictionary
    }
    for pos in all_pos:
        for dictionary in ("cald", "cacd", "cbed", "other"):
            if pos not in grouped[dictionary]:
                continue
            levels = grouped[dictionary][pos]
            classified = levels & CEFR_LEVELS
            result[pos] = classified or {"UNCLASSIFIED"}
            break
    return result


def _load_oxford_facts(path: Path) -> dict[str, _OxfordFacts]:
    records: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            records[(record.get("word") or "").strip().lower()].append(record)

    result: dict[str, _OxfordFacts] = {}
    for word, word_records in records.items():
        assigned: dict[str, set[str]] = defaultdict(set)
        raw_pos: set[str] = set()
        unbadged_pos: set[str] = set()
        for record in word_records:
            pos_data_list = record.get("pos_data") or []
            badge = (record.get("oxford_badge") or "").strip().upper()
            record_poses = [normalize_pos(p) for p in (record.get("pos") or []) if p]
            if not pos_data_list and badge in CEFR_LEVELS and record_poses:
                for p in record_poses:
                    raw_pos.add(p)
                    assigned[p].add(badge)
            for pos_data in pos_data_list:
                pos = normalize_pos(pos_data.get("pos") or "")
                definitions = pos_data.get("definitions") or []
                if pos and definitions:
                    raw_pos.add(pos)
                    if any(definition.get("cefr") is None for definition in definitions):
                        unbadged_pos.add(pos)
            for sense in simplify_record(record):
                if sense.pos and sense.cefr:
                    assigned[normalize_pos(sense.pos)].add(
                        str(sense.cefr).upper()
                    )
        result[word] = _OxfordFacts(dict(assigned), raw_pos, unbadged_pos)

    # Oxford owns phrasal verbs on independent target pages.  AWL rows name
    # the lexical base (for example ``derive | phrasal verb``), so expose the
    # target page's POS under that base without folding its senses back into
    # the base dictionary record.  Unbadged targets inherit only the reviewed
    # base verb level used by the AWL row.
    for target_word, target_facts in tuple(result.items()):
        if " " not in target_word or "phrasal verb" not in target_facts.raw_pos:
            continue
        base_word = target_word.split(" ", 1)[0]
        base_facts = result.get(base_word)
        if base_facts is None:
            continue
        base_facts.raw_pos.add("phrasal verb")
        target_levels = target_facts.assigned.get("phrasal verb", set())
        inherited_levels = base_facts.assigned.get("verb", set())
        if target_levels or inherited_levels:
            base_facts.assigned.setdefault("phrasal verb", set()).update(
                target_levels or inherited_levels
            )
        elif "phrasal verb" in target_facts.unbadged_pos:
            base_facts.unbadged_pos.add("phrasal verb")
    return result


def _load_cambridge_fallbacks(path: Path) -> dict[str, dict[str, set[str]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    for entry in payload.get("entries", []):
        word = str(entry["word"]).strip().lower()
        pos = normalize_pos(str(entry["pos"]))
        cefr = str(entry["cefr"]).strip().upper()
        if cefr not in CEFR_LEVELS | {"UNCLASSIFIED"}:
            raise ValueError(f"Invalid Cambridge fallback CEFR: {entry}")
        result[word][pos].add(cefr)
    return {
        word: {pos: set(levels) for pos, levels in positions.items()}
        for word, positions in result.items()
    }


def _format_row(
    word: str, positions: list[str], cefr: str, sublist: int, source: str
) -> str:
    pos_text = ", ".join(POS_DISPLAY.get(pos, pos) for pos in positions)
    note = "Cambridge" if source == "Cambridge" else ""
    return f"| **{word}** | {pos_text} | {cefr} | {sublist} | {note} |"


def audit_awl(paths: AwlIntegrityPaths) -> AwlAuditResult:
    text = paths.awl_md.read_text(encoding="utf-8")
    rows = parse_awl_rows(text)
    oxford = _load_oxford_facts(paths.oxford_jsonl)
    cambridge_manifest = _load_cambridge_fallbacks(
        paths.cambridge_fallbacks_json
    )
    cambridge_cache: dict[str, dict[str, set[str]]] = {}
    errors: list[str] = []
    corrections: list[AwlCorrection] = []
    replacement_by_line: dict[int, tuple[str, ...]] = {}

    sublist_by_word: dict[str, int] = {}
    for row in rows:
        word_key = row.word.lower()
        previous = sublist_by_word.setdefault(word_key, row.sublist)
        if previous != row.sublist:
            errors.append(
                f"{row.word}: conflicting sublists {previous} and {row.sublist}"
            )

    def get_oxford(word: str) -> _OxfordFacts:
        key = HEADWORD_ALIASES.get(word, word)
        return oxford.get(key, _OxfordFacts({}, set(), set()))

    def get_cambridge(word: str) -> dict[str, set[str]]:
        if word in cambridge_cache:
            return cambridge_cache[word]
        facts = {
            pos: set(levels)
            for pos, levels in cambridge_manifest.get(word, {}).items()
        }
        candidates = [word, HEADWORD_ALIASES.get(word, "")]
        cache_path = None
        if paths.cambridge_cache_dir is not None:
            cache_path = next((
                paths.cambridge_cache_dir / f"cambridge_{candidate}.html"
                for candidate in candidates
                if candidate
                and (
                    paths.cambridge_cache_dir / f"cambridge_{candidate}.html"
                ).exists()
            ), None)
        if cache_path is not None:
            facts = parse_cambridge_pos_cefr(cache_path.read_bytes())
        for (override_word, pos), levels in CAMBRIDGE_POS_OVERRIDES.items():
            if override_word == word:
                facts[pos] = set(levels)
        cambridge_cache[word] = facts
        return facts

    for row in rows:
        word_key = row.word.lower()
        oxford_facts = get_oxford(word_key)
        outcomes: list[tuple[str, str, str]] = []
        for pos in row.pos:
            levels = oxford_facts.assigned.get(pos, set())
            if (
                row.cefr == "UNCLASSIFIED"
                and pos in oxford_facts.unbadged_pos
            ):
                outcomes.append((pos, row.cefr, "Oxford"))
                continue
            if row.cefr in levels:
                outcomes.append((pos, row.cefr, "Oxford"))
                continue
            if levels:
                override = PRIMARY_CEFR_OVERRIDES.get((word_key, pos))
                if override in levels:
                    outcomes.append((pos, override, "Oxford"))
                elif len(levels) == 1:
                    outcomes.append((pos, next(iter(levels)), "Oxford"))
                else:
                    errors.append(
                        f"line {row.line_number} {row.word}|{pos}: ambiguous Oxford "
                        f"CEFR {sorted(levels)}"
                    )
                continue

            cambridge_levels = get_cambridge(word_key).get(pos, set())
            classified = cambridge_levels & CEFR_LEVELS
            if row.cefr in classified:
                outcomes.append((pos, row.cefr, "Cambridge"))
            elif len(classified) == 1:
                outcomes.append((pos, next(iter(classified)), "Cambridge"))
            elif len(classified) > 1:
                errors.append(
                    f"line {row.line_number} {row.word}|{pos}: ambiguous Cambridge "
                    f"CEFR {sorted(classified)}"
                )
            elif pos in oxford_facts.raw_pos:
                outcomes.append((pos, "UNCLASSIFIED", "Oxford"))
            elif "UNCLASSIFIED" in cambridge_levels:
                outcomes.append((pos, "UNCLASSIFIED", "Cambridge"))
            else:
                errors.append(
                    f"line {row.line_number} {row.word}|{pos}: POS absent from "
                    "Oxford and Cambridge"
                )

        if len(outcomes) != len(row.pos):
            replacement_by_line[row.line_number] = (row.raw_line,)
            continue

        groups: dict[tuple[str, str], list[str]] = {}
        for pos, cefr, source in outcomes:
            groups.setdefault((cefr, source), []).append(pos)
        new_lines = tuple(
            _format_row(row.word, positions, cefr, row.sublist, source)
            for (cefr, source), positions in groups.items()
        )
        replacement_by_line[row.line_number] = new_lines
        if new_lines != (row.raw_line,):
            corrections.append(AwlCorrection(
                row.line_number, row.word, row.raw_line, new_lines
            ))

    output_lines: list[str] = []
    seen_rows: set[str] = set()
    row_line_numbers = {row.line_number for row in rows}
    for line_number, line in enumerate(text.splitlines(), 1):
        if line_number not in row_line_numbers:
            output_lines.append(line)
            continue
        for replacement in replacement_by_line[line_number]:
            if replacement not in seen_rows:
                seen_rows.add(replacement)
                output_lines.append(replacement)

    proposed_text = "\n".join(output_lines) + "\n"
    proposed_rows = parse_awl_rows(proposed_text)
    if len(sublist_by_word) != 570:
        errors.append(
            f"Expected 570 AWL headwords, found {len(sublist_by_word)}"
        )
    if {row.word.lower() for row in proposed_rows} != set(sublist_by_word):
        errors.append("Headword set changed during normalization")
    for row in proposed_rows:
        if sublist_by_word[row.word.lower()] != row.sublist:
            errors.append(f"{row.word}: sublist changed during normalization")

    manifest_tuples = {
        (word, pos, cefr)
        for word, positions in cambridge_manifest.items()
        for pos, levels in positions.items()
        for cefr in levels
    }
    proposed_cambridge_tuples = {
        (row.word.lower(), pos, row.cefr)
        for row in proposed_rows
        if row.note == "Cambridge"
        for pos in row.pos
    }
    if manifest_tuples != proposed_cambridge_tuples:
        missing = sorted(proposed_cambridge_tuples - manifest_tuples)
        extra = sorted(manifest_tuples - proposed_cambridge_tuples)
        errors.append(
            "Cambridge fallback manifest drift: "
            f"missing={missing}, extra={extra}"
        )

    return AwlAuditResult(
        proposed_text=proposed_text,
        rows_before=len(rows),
        rows_after=len(proposed_rows),
        headword_count=len(sublist_by_word),
        corrections=tuple(corrections),
        errors=tuple(errors),
    )
