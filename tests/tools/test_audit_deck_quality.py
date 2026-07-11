from __future__ import annotations

import pytest

from tools.audit_deck_quality import (
    Finding,
    apply_decisions,
    detect_card_findings,
    split_cells,
    sort_findings,
)


def _card(**changes) -> dict:
    card = {
        "guid": "g1",
        "deck": "Deck",
        "word": "sample",
        "pos": "noun",
        "cefr": "C1",
        "definition": "first sense (nghĩa một)",
        "example": "first example",
        "collocations": "sample phrase",
        "idioms": "",
        "tags": "Source::Oxford CEFR::C1 Oxford_5000",
        "uk_audio": "[sound:uk.mp3]",
        "us_audio": "[sound:us.mp3]",
        "synonyms": "",
        "antonyms": "",
    }
    card.update(changes)
    return card


def test_split_cells_preserves_empty_alignment_cells():
    assert split_cells("|second") == ["", "second"]
    assert split_cells("") == []


def test_detects_structural_alignment_and_missing_audio():
    findings = detect_card_findings(
        _card(example="one|two", uk_audio="[sound:missing.mp3]"),
        "owner.jsonl",
        {"us.mp3"},
    )
    issues = {finding.issue_type for finding in findings}
    assert "unrendered_extra_example" in issues
    assert "missing_audio_file" in issues


def test_detects_idiom_tag_drift_and_duplicate_ownership():
    findings = detect_card_findings(
        _card(
            collocations="make an exception",
            idioms="make an exception :: allow a rule break :: example",
            tags="Source::Oxford CEFR::C1 Oxford_5000",
        ),
        "owner.jsonl",
        {"uk.mp3", "us.mp3"},
    )
    issues = {finding.issue_type for finding in findings}
    assert issues >= {"idioms_payload_without_tag", "idiom_duplicated_in_collocations"}


def test_detects_manual_review_precedents():
    findings = detect_card_findings(
        _card(
            definition=(
                "admit truth (thừa nhận)|admit defeat (chấp nhận thua)|"
                "other sense (một/hai/ba)|fourth sense (bốn)"
            ),
            example="one|two|three|four",
        ),
        "owner.jsonl",
        {"uk.mp3", "us.mp3"},
    )
    issues = {finding.issue_type for finding in findings}
    assert issues >= {
        "semantic_overload_review",
        "sense_grouping_review",
        "vietnamese_gloss_precision_review",
    }
    assert all(
        finding.decision == "review_needed"
        for finding in findings
        if finding.issue_type in issues & {
            "semantic_overload_review",
            "sense_grouping_review",
            "vietnamese_gloss_precision_review",
        }
    )


def test_apply_decisions_requires_current_finding_keys():
    finding = Finding(
        issue_type="review",
        severity="review",
        decision="review_needed",
        guid="g1",
        word="word",
        pos="noun",
        cefr="C1",
        list="Oxford_5000",
        deck="Deck",
        canonical_owner="owner",
        precedent="precedent",
        recommendation="review",
        evidence={},
    )
    updated = apply_decisions(
        [finding],
        {("review", "g1"): {"decision": "keep", "rationale": "source senses are distinct"}},
    )
    assert updated[0].decision == "keep"
    assert updated[0].rationale == "source senses are distinct"

    with pytest.raises(ValueError, match="do not match current findings"):
        apply_decisions([finding], {("other", "g2"): {"decision": "keep"}})


def test_sort_findings_is_deterministic():
    base = dict(
        decision="confirmed_error",
        guid="g",
        pos="noun",
        cefr="C1",
        list="Oxford_5000",
        deck="Deck",
        canonical_owner="owner",
        precedent="p",
        recommendation="r",
        evidence={},
    )
    findings = [
        Finding(issue_type="z", severity="review", word="b", **base),
        Finding(issue_type="a", severity="error", word="a", **base),
    ]
    assert [finding.issue_type for finding in sort_findings(findings)] == ["a", "z"]
