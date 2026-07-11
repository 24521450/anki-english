#!/usr/bin/env python3
"""Audit canonical and live Anki card quality without modifying deck data."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

import requests

from src.config import ProjectPaths
from src.deck_builder.build_validation import validate_artifact_paths
from src.deck_builder.card_identity import primary_list_from_tags
from src.deck_builder.corpus_tag_sync import corpus_lookup_identity
from tools._detect_lexical_loops import detect_loops


AUDIT_DATE = "2026-07-10"
DEFAULT_STEM = f"anki_notes_quality_audit_{AUDIT_DATE}_v3"
SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")
SINGLE_BR_RE = re.compile(r"(?<!<br>)<br\s*/?>(?!<br>)", re.IGNORECASE)
REGISTER_RE = re.compile(r"^(?:\[[^]]+\])+")
TRAILING_GLOSS_RE = re.compile(r"\(([^()]*)\)\s*$")
SEVERITY_RANK = {"error": 0, "warn": 1, "review": 2}


@dataclass(frozen=True, slots=True)
class Finding:
    issue_type: str
    severity: str
    decision: str
    guid: str
    word: str
    pos: str
    cefr: str
    list: str
    deck: str
    canonical_owner: str
    precedent: str
    recommendation: str
    evidence: dict
    rationale: str = ""

    def key(self) -> tuple[str, str]:
        return (self.issue_type, self.guid)

    def to_dict(self) -> dict:
        return asdict(self)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def split_cells(value: str) -> list[str]:
    return value.split("|") if value else []


def english_gloss(chunk: str) -> str:
    chunk = REGISTER_RE.sub("", chunk).strip()
    return TRAILING_GLOSS_RE.sub("", chunk).strip()


def first_gloss_token(chunk: str) -> str:
    match = re.search(r"[a-z]+", english_gloss(chunk).lower())
    return match.group(0) if match else ""


def canonical_owner_for(
    card: dict,
    registry_by_guid: dict[str, dict],
    manual_keys: set[tuple[str, str, str, str]],
    review_guids: set[str],
    audit_keys: set[tuple[str, str, str]],
) -> str:
    guid = card.get("guid") or ""
    if guid in review_guids:
        return "data/review/non_oxford_non_c2_overrides.jsonl"
    registry = registry_by_guid.get(guid) or {}
    manual_key = (
        registry.get("word") or card.get("word") or "",
        (registry.get("cefr") or card.get("cefr") or "").upper(),
        registry.get("list") or primary_list_from_tags(card.get("tags"), canonical=True),
        registry.get("variant") or "",
    )
    if manual_key in manual_keys:
        return "data/review/manual_cards.jsonl"
    audit_key = (
        (card.get("word") or "").lower(),
        (card.get("pos") or "").lower(),
        (card.get("cefr") or "").upper(),
    )
    if audit_key in audit_keys:
        return "data/curated/deck_audit.jsonl"
    return "data/sources/oxford.jsonl"


def _finding(
    card: dict,
    issue_type: str,
    severity: str,
    decision: str,
    owner: str,
    precedent: str,
    recommendation: str,
    evidence: dict,
) -> Finding:
    return Finding(
        issue_type=issue_type,
        severity=severity,
        decision=decision,
        guid=card.get("guid") or "",
        word=card.get("word") or "",
        pos=card.get("pos") or "",
        cefr=(card.get("cefr") or "UNCLASSIFIED").upper(),
        list=primary_list_from_tags(card.get("tags"), canonical=True),
        deck=card.get("deck") or "",
        canonical_owner=owner,
        precedent=precedent,
        recommendation=recommendation,
        evidence=evidence,
    )


def detect_card_findings(card: dict, owner: str, audio_names: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    definitions = split_cells(card.get("definition") or "")
    examples = split_cells(card.get("example") or "")
    tags = set((card.get("tags") or "").split())
    idioms = card.get("idioms") or ""

    if len(examples) > len(definitions):
        findings.append(_finding(
            card, "unrendered_extra_example", "error", "confirmed_error", owner,
            "Example Alignment",
            "Join same-sense examples with <br><br> or add the missing Definition segment.",
            {"definition_count": len(definitions), "example_count": len(examples)},
        ))
    if len(definitions) > len(examples) or any(
        definition.strip() and (idx >= len(examples) or not examples[idx].strip())
        for idx, definition in enumerate(definitions)
    ):
        findings.append(_finding(
            card, "missing_example_for_definition", "warn", "confirmed_error", owner,
            "Example Alignment",
            "Add a source-backed example or explicitly accept the pedagogical gap.",
            {"definition_count": len(definitions), "example_count": len(examples)},
        ))

    if SINGLE_BR_RE.search(card.get("example") or ""):
        findings.append(_finding(
            card, "noncanonical_example_break", "error", "confirmed_error", owner,
            "Example Alignment", "Replace a single <br> with <br><br>.", {},
        ))

    for field in ("synonyms", "antonyms"):
        metadata = card.get(field) or ""
        if metadata and len(metadata.split("|")) != len(examples):
            findings.append(_finding(
                card, "relation_metadata_alignment", "error", "confirmed_error", owner,
                "Lexical Relation Metadata",
                f"Align {field} cells with Example chunks.",
                {"field": field, "metadata_cells": len(metadata.split("|")), "example_count": len(examples)},
            ))

    has_idiom_tag = "idioms" in tags
    if idioms and not has_idiom_tag:
        findings.append(_finding(
            card, "idioms_payload_without_tag", "error", "confirmed_error", owner,
            "forth", "Add the idioms feature tag for the populated Idioms field.", {},
        ))
    if has_idiom_tag and not idioms:
        findings.append(_finding(
            card, "idioms_tag_without_payload", "error", "confirmed_error", owner,
            "forth",
            "Derive the idioms feature tag from the serialized learner-facing Idioms payload.", {},
        ))

    if idioms:
        collocations = {value.strip().lower() for value in (card.get("collocations") or "").split("|") if value.strip()}
        for entry in idioms.split("$$"):
            phrase = entry.split("::", 1)[0].strip().lower()
            if phrase and phrase in collocations:
                findings.append(_finding(
                    card, "idiom_duplicated_in_collocations", "error", "confirmed_error", owner,
                    "Single field ownership",
                    "Keep the rich phrase in Idioms and remove the exact Collocations duplicate.",
                    {"phrase": phrase},
                ))

    for field in ("uk_audio", "us_audio"):
        for filename in SOUND_RE.findall(card.get(field) or ""):
            if filename not in audio_names:
                findings.append(_finding(
                    card, "missing_audio_file", "error", "confirmed_error", owner,
                    "Audio Button", "Restore the referenced local media file or clear the invalid reference.",
                    {"field": field, "filename": filename},
                ))

    if len(definitions) >= 4:
        findings.append(_finding(
            card, "semantic_overload_review", "review", "review_needed", owner,
            "proposition",
            "Review whether specialized or independent sense systems need compression or a reviewed variant.",
            {"definition_count": len(definitions), "definitions": definitions},
        ))

    tokens = [first_gloss_token(chunk) for chunk in definitions]
    adjacent_matches = [
        [idx + 1, idx + 2, tokens[idx]]
        for idx in range(len(tokens) - 1)
        if tokens[idx] and tokens[idx] == tokens[idx + 1]
    ]
    if adjacent_matches:
        findings.append(_finding(
            card, "sense_grouping_review", "review", "review_needed", owner,
            "concede",
            "Review whether adjacent same-core senses belong in one display row with <br><br> examples.",
            {"adjacent_matches": adjacent_matches, "definitions": definitions},
        ))

    overloaded_chunks = []
    for idx, definition in enumerate(definitions, 1):
        match = TRAILING_GLOSS_RE.search(definition)
        if match and match.group(1).count("/") >= 2:
            overloaded_chunks.append({"index": idx, "translation": match.group(1)})
    if overloaded_chunks:
        findings.append(_finding(
            card, "vietnamese_gloss_precision_review", "review", "review_needed", owner,
            "equate",
            "Keep the shortest accurate Vietnamese core gloss; remove redundant or misleading variants.",
            {"chunks": overloaded_chunks},
        ))
    return findings


def cambridge_cefr_index(rows: Iterable[dict]) -> dict[tuple[str, str], set[str]]:
    index: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        word = (row.get("word") or "").strip().lower()
        if not word:
            continue
        for pos_group in row.get("pos_data") or []:
            pos = (pos_group.get("pos") or "").strip().lower()
            for definition in pos_group.get("definitions") or []:
                cefr = (definition.get("cefr") or "").strip().upper()
                if pos and cefr:
                    index[(word, pos)].add(cefr)
    return index


def detect_source_rescues(cards: list[dict], owners: dict[str, str], cambridge_rows: list[dict]) -> list[Finding]:
    index = cambridge_cefr_index(cambridge_rows)
    findings: list[Finding] = []
    for card in cards:
        if (card.get("cefr") or "").upper() != "UNCLASSIFIED":
            continue
        word, positions = corpus_lookup_identity(card.get("word") or "", card.get("pos") or "")
        candidates = sorted({cefr for pos in positions for cefr in index.get((word, pos), set())})
        if candidates:
            findings.append(_finding(
                card, "exact_source_cefr_rescue_review", "review", "review_needed",
                owners[card["guid"]], "restrain",
                "Review exact Cambridge POS/sense evidence before replacing UNCLASSIFIED.",
                {"cambridge_cefr_candidates": candidates},
            ))
    return findings


def detect_regression_candidates(
    cards: list[dict],
    owners: dict[str, str],
    previous_findings: list[dict],
    antonym_decisions: list[dict],
) -> list[Finding]:
    """Only surface lexical/card-shape candidates not already reviewed in P4."""
    previous = {
        (row.get("issue_type") or "", row.get("guid") or "")
        for row in previous_findings
    }
    reviewed_antonyms = {
        (
            (row.get("word") or "").lower(),
            (row.get("pos") or "").lower(),
            (row.get("cefr") or "").upper(),
        )
        for row in antonym_decisions
    }
    findings: list[Finding] = []
    for card in cards:
        guid = card.get("guid") or ""
        word = (card.get("word") or "").lower()
        english_definition = "|".join(
            english_gloss(chunk) for chunk in split_cells(card.get("definition") or "")
        )
        key = (word, (card.get("pos") or "").lower(), (card.get("cefr") or "").upper())
        loop_types = detect_loops(word, english_definition)
        for loop_type, issue_type in (
            ("word_family_loop", "word_family_loop_review"),
            ("antonym_loop", "antonym_loop_review"),
        ):
            if loop_type not in loop_types or (issue_type, guid) in previous:
                continue
            if issue_type == "antonym_loop_review" and key in reviewed_antonyms:
                continue
            findings.append(_finding(
                card, issue_type, "review", "review_needed", owners[guid],
                "P4 lexical-loop policy",
                "Review learner clarity; do not rewrite a basic, natural gloss only to remove a heuristic hit.",
                {"definition": card.get("definition") or ""},
            ))

        word_pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        if word and word_pattern.search(english_definition) and ("exact_headword_in_gloss_review", guid) not in previous:
            findings.append(_finding(
                card, "exact_headword_in_gloss_review", "review", "review_needed", owners[guid],
                "P4 exact-headword policy",
                "Rewrite only if the gloss is circular; keep legitimate compounds and technical labels.",
                {"definition": card.get("definition") or ""},
            ))

        if "," in (card.get("pos") or "") and ("multi_pos_card_review", guid) not in previous:
            findings.append(_finding(
                card, "multi_pos_card_review", "review", "review_needed", owners[guid],
                "P4 multi-POS policy",
                "Split only for overload, independent sense systems, or a pronunciation/homograph distinction.",
                {"definition_count": len(split_cells(card.get("definition") or ""))},
            ))

    return findings


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (
            SEVERITY_RANK.get(item.severity, 9),
            item.issue_type,
            item.word.lower(),
            item.cefr,
            item.pos.lower(),
            item.guid,
        ),
    )


def load_decisions(path: Path | None) -> dict[tuple[str, str], dict]:
    if path is None or not path.exists():
        return {}
    decisions = {}
    for row in load_jsonl(path):
        key = (row.get("issue_type") or "", row.get("guid") or "")
        if not all(key) or key in decisions:
            raise ValueError(f"Invalid or duplicate audit decision key: {key!r}")
        decision = row.get("decision")
        if decision not in {"confirmed_error", "keep", "deferred"}:
            raise ValueError(f"Invalid decision {decision!r} for {key!r}")
        decisions[key] = row
    return decisions


def apply_decisions(findings: list[Finding], decisions: dict[tuple[str, str], dict]) -> list[Finding]:
    finding_keys = {finding.key() for finding in findings}
    unknown = set(decisions) - finding_keys
    if unknown:
        raise ValueError(f"Decision rows do not match current findings: {sorted(unknown)!r}")
    out = []
    for finding in findings:
        decision = decisions.get(finding.key())
        if decision:
            out.append(replace(
                finding,
                decision=decision["decision"],
                rationale=(decision.get("rationale") or "").strip(),
            ))
        else:
            out.append(finding)
    return out


def write_jsonl(path: Path, findings: list[Finding]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(finding.to_dict(), ensure_ascii=False, sort_keys=True) + "\n" for finding in findings)
    path.write_text(text, encoding="utf-8", newline="\n")


def render_markdown(findings: list[Finding], card_count: int, input_sha256: str) -> str:
    by_issue = Counter(finding.issue_type for finding in findings)
    by_decision = Counter(finding.decision for finding in findings)
    lines = [
        "# Anki Notes Quality Audit v3",
        "",
        "> Status: audit-only. No canonical card or live Anki note was modified.",
        "",
        "## Summary",
        "",
        f"- Input cards: **{card_count}**",
        f"- Input SHA-256: `{input_sha256}`",
        f"- Findings: **{len(findings)}**",
        f"- Confirmed errors: **{by_decision['confirmed_error']}**",
        f"- Kept candidates: **{by_decision['keep']}**",
        f"- Deferred candidates: **{by_decision['deferred']}**",
        f"- Undecided candidates: **{by_decision['review_needed']}**",
        "- Coverage boundary: active Card Registry inventory; AWL/Oxford seed rows are enrichment, not automatic missing-card defects.",
        "- Idiom-content policy: English idiom gloss and prioritization are out of scope; structural tag/payload drift remains audited.",
        "",
        "## Issue Distribution",
        "",
        "| Issue type | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| `{issue}` | {count} |" for issue, count in sorted(by_issue.items()))
    for decision, title in (
        ("confirmed_error", "Confirmed Errors"),
        ("review_needed", "Review Queue"),
        ("keep", "Reviewed Keeps"),
        ("deferred", "Deferred"),
    ):
        rows = [finding for finding in findings if finding.decision == decision]
        if not rows:
            continue
        lines.extend(["", f"## {title}", ""])
        for finding in rows:
            identity = f"{finding.word} | {finding.pos} | {finding.cefr} | {finding.list}"
            lines.extend([
                f"### `{finding.issue_type}` — {identity}",
                "",
                f"- GUID: `{finding.guid or 'MISSING'}`",
                f"- Severity: `{finding.severity}`",
                f"- Canonical owner: `{finding.canonical_owner}`",
                f"- Precedent: `{finding.precedent}`",
                f"- Recommendation: {finding.recommendation}",
                f"- Evidence: `{json.dumps(finding.evidence, ensure_ascii=False, sort_keys=True)}`",
            ])
            if finding.rationale:
                lines.append(f"- Review rationale: {finding.rationale}")
    return "\n".join(lines) + "\n"


def anki_call(url: str, action: str, **params):
    response = requests.post(
        url,
        json={"action": action, "version": 6, "params": params},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"AnkiConnect {action} failed: {payload['error']}")
    return payload.get("result")


def audit_live_anki(cards: list[dict], url: str, deck: str) -> list[Finding]:
    note_ids = anki_call(url, "findNotes", query=f'deck:"{deck}"') or []
    notes = []
    for start in range(0, len(note_ids), 500):
        notes.extend(anki_call(url, "notesInfo", notes=note_ids[start:start + 500]) or [])

    def canonical_tuple(card: dict) -> tuple:
        return (
            card.get("word") or "", card.get("pos") or "", card.get("cefr") or "",
            card.get("definition") or "", card.get("example") or "", card.get("collocations") or "",
            card.get("idioms") or "", card.get("uk_audio") or "", card.get("us_audio") or "",
            tuple(sorted((card.get("tags") or "").split())),
        )

    def live_tuple(note: dict) -> tuple:
        fields = note.get("fields") or {}
        value = lambda name: ((fields.get(name) or {}).get("value") or "")
        return (
            value("Word"), value("PartOfSpeech"), value("CEFRLevel"), value("Definition"),
            value("Example"), value("Collocations"), value("Idioms"), value("AudioUK"), value("AudioUS"),
            tuple(sorted(note.get("tags") or [])),
        )

    canonical = Counter(canonical_tuple(card) for card in cards)
    live = Counter(live_tuple(note) for note in notes)
    findings = []
    for row, count in sorted((canonical - live).items()):
        synthetic = {
            "guid": "", "word": row[0], "pos": row[1], "cefr": row[2], "deck": deck, "tags": " ".join(row[9]),
        }
        findings.append(_finding(
            synthetic, "live_anki_missing_or_drifted_note", "error", "confirmed_error",
            "live Anki via AnkiConnect", "Live parity",
            "Update the live note from canonical output after reviewing the field drift.",
            {"count": count},
        ))
    for row, count in sorted((live - canonical).items()):
        synthetic = {
            "guid": "", "word": row[0], "pos": row[1], "cefr": row[2], "deck": deck, "tags": " ".join(row[9]),
        }
        findings.append(_finding(
            synthetic, "live_anki_extra_or_drifted_note", "error", "confirmed_error",
            "live Anki via AnkiConnect", "Live parity",
            "Review and reconcile the live-only note without deleting it automatically.",
            {"count": count},
        ))
    return findings


def build_findings(paths: ProjectPaths, *, live: bool = False, anki_url: str = "http://127.0.0.1:8765") -> list[Finding]:
    validation = validate_artifact_paths(
        paths.anki_notes_jsonl,
        paths.anki_notes_txt,
        paths.card_registry,
        paths.audio_dir,
    )
    if not validation.ok:
        raise RuntimeError("Canonical artifact validation failed:\n" + validation.error_text())
    cards = load_jsonl(paths.anki_notes_jsonl)
    registry = load_jsonl(paths.card_registry)
    manual = load_jsonl(paths.manual_cards)
    review = load_jsonl(paths.non_oxford_non_c2_overrides)
    audit = load_jsonl(paths.deck_audit_jsonl)
    registry_by_guid = {(row.get("guid") or ""): row for row in registry}
    manual_keys = {
        (row.get("word") or "", (row.get("cefr") or "").upper(), row.get("list") or "", row.get("variant") or "")
        for row in manual
    }
    review_guids = {(row.get("guid") or "") for row in review}
    audit_keys = {
        ((row.get("word") or "").lower(), (row.get("pos") or "").lower(), (row.get("cefr") or "").upper())
        for row in audit
    }
    owners = {
        card["guid"]: canonical_owner_for(card, registry_by_guid, manual_keys, review_guids, audit_keys)
        for card in cards
    }
    audio_names = {path.name for path in paths.audio_dir.glob("*.mp3")}
    findings = [
        finding
        for card in cards
        for finding in detect_card_findings(card, owners[card["guid"]], audio_names)
    ]
    findings.extend(detect_source_rescues(cards, owners, load_jsonl(paths.cambridge_jsonl)))
    previous_report = paths.root / "scratch" / "anki_notes_quality_audit_20260705_v2.jsonl"
    findings.extend(detect_regression_candidates(
        cards,
        owners,
        load_jsonl(previous_report),
        load_jsonl(paths.antonym_loop_decisions),
    ))
    if live:
        findings.extend(audit_live_anki(cards, anki_url, "English Academic Vocabulary"))
    return sort_findings(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--jsonl", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--require-decisions", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--anki-url", default="http://127.0.0.1:8765")
    args = parser.parse_args(argv)

    paths = ProjectPaths(args.root)
    jsonl_path = args.jsonl or paths.root / "scratch" / f"{DEFAULT_STEM}.jsonl"
    markdown_path = args.markdown or paths.root / "scratch" / f"{DEFAULT_STEM}.md"
    try:
        findings = build_findings(paths, live=args.live, anki_url=args.anki_url)
        findings = apply_decisions(findings, load_decisions(args.decisions))
    except (OSError, ValueError, RuntimeError, requests.RequestException) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    undecided = [finding for finding in findings if finding.decision == "review_needed"]
    write_jsonl(jsonl_path, findings)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_markdown(findings, len(load_jsonl(paths.anki_notes_jsonl)), sha256_file(paths.anki_notes_jsonl)),
        encoding="utf-8",
        newline="\n",
    )
    print(f"Cards scanned: {len(load_jsonl(paths.anki_notes_jsonl))}")
    print(f"Findings: {len(findings)}")
    print(f"Undecided review candidates: {len(undecided)}")
    print(f"JSONL: {jsonl_path}")
    print(f"Markdown: {markdown_path}")
    if args.require_decisions and undecided:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
