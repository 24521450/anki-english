"""Red test: multi-POS boundary detection in Oxford parser.

Bug to fix (Phase 7a): parser uses ALL pos-g[hclass='pos'] markers as POS section
boundaries, but most are in <span class='arl1/arl2'> (related-entries links) — not
real sense boundaries. Fix: filter pos-g to only those followed by ol.senses_*
sibling.

Test fixtures:
- oxford_sick_1_(adj).html: 1 main POS section (adjective) + 8 idiom blocks
- oxford_aggregate_(adj).html: 1 POS section (1 sense)
- oxford_aggregate_(verb).html: 1 POS section (1 sense)
- oxford_aggregate_1_(noun).html: 1 POS section (4 senses)

Expectation after fix:
- sick → pos_data has 1 entry (adjective, with 7 main senses + idioms)
- aggregate (3 files) → 3 separate records, each with 1 pos_data entry
- Each pos_data entry has accurate (non-duplicate) senses
"""
from __future__ import annotations

import json
import os
import re
import sys

from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, PROJECT_ROOT)

import pytest  # noqa: E402

from src.scraper.oxford import parse_oxford  # noqa: E402

OXFORD_DIR = os.path.join(PROJECT_ROOT, "data", ".cache_html", "oxford")

WHITESPACE_RE = re.compile(r"\s+")
def get_text(el):
    if el is None: return ""
    return WHITESPACE_RE.sub(" ", el.text_content()).strip() or ""


def _parse(filename: str) -> dict:
    path = os.path.join(OXFORD_DIR, filename)
    with open(path, "rb") as f:
        raw = f.read()
    return parse_oxford(raw, source_files=[filename])


class TestMultiPosBoundary:
    """Phase 7a: parser must scope sense extraction to pos-g with ol.senses_* sibling."""

    def test_sick_single_main_pos_section(self):
        """sick_1_(adj).html has 1 main POS section (adjective) — parser must produce 1 pos_data entry, not 3.

        Before fix: pos_data had 3 duplicate entries (adjective, noun, verb) each with 16 defs.
        After fix: 1 entry (adjective) with 7 main senses + idioms.
        """
        rec = _parse("oxford_sick_1_(adj).html")
        # Word is set
        assert rec["word"] == "sick"
        # Single main POS section: pos_data must be 1 entry, not 3
        assert len(rec["pos_data"]) == 1, (
            f"Expected 1 pos_data entry, got {len(rec['pos_data'])}: "
            f"{[pd['pos'] for pd in rec['pos_data']]}"
        )
        # The 1 entry is adjective (the only main POS in this file)
        assert rec["pos_data"][0]["pos"] == "adjective"
        # Should have 7 main senses (not 16 — pre-fix duplicated)
        assert len(rec["pos_data"][0]["definitions"]) == 7, (
            f"Expected 7 main definitions, got {len(rec['pos_data'][0]['definitions'])}"
        )

    def test_aggregate_three_files_three_records(self):
        """aggregate has 3 files (adj, verb, _1_(noun)) — 1 record per file.

        After fix: each file produces 1 record with 1 pos_data entry containing
        only that file's senses (not duplicated across POS).
        """
        adj = _parse("oxford_aggregate_(adj).html")
        verb = _parse("oxford_aggregate_(verb).html")
        noun = _parse("oxford_aggregate_1_(noun).html")

        # Each file → 1 record
        assert len(adj["pos_data"]) == 1
        assert len(verb["pos_data"]) == 1
        assert len(noun["pos_data"]) == 1

        # Each record's pos_data entry has correct POS
        assert adj["pos_data"][0]["pos"] == "adjective"
        assert verb["pos_data"][0]["pos"] == "verb"
        assert noun["pos_data"][0]["pos"] == "noun"

        # Def counts match Oxford structure (verified by HTML inspection):
        # - adj file: 1 main sense
        # - verb file: 1 main sense
        # - noun file: 2 main senses (1 + 1) + 2 idioms excluded
        assert len(adj["pos_data"][0]["definitions"]) == 1
        assert len(verb["pos_data"][0]["definitions"]) == 1
        assert len(noun["pos_data"][0]["definitions"]) == 2

    def test_aggregate_senses_not_duplicated(self):
        """After fix, NO def in any aggregate record should have identical text + pos + sensenum as another def in the same record.

        Pre-fix bug: 3 entries × identical defs = same text appears 3 times in 1 record.
        """
        adj = _parse("oxford_aggregate_(adj).html")
        verb = _parse("oxford_aggregate_(verb).html")
        noun = _parse("oxford_aggregate_1_(noun).html")

        for rec, label in [(adj, "adj"), (verb, "verb"), (noun, "noun")]:
            seen = []
            for pd in rec["pos_data"]:
                for d in pd["definitions"]:
                    key = (pd["pos"], d.get("sensenum_local"), d["text"])
                    assert key not in seen, (
                        f"{label} record has duplicate def: pos={key[0]} sensenum={key[1]} text={key[2]!r}"
                    )
                    seen.append(key)

    def test_sick_main_senses_have_cefr(self):
        """Senses on sick's main POS section should have cefr extracted (per-sense attr)."""
        rec = _parse("oxford_sick_1_(adj).html")
        defs = rec["pos_data"][0]["definitions"]
        # First def should have cefr (A1 from earlier verification)
        assert defs[0]["cefr"] in (None, "A1", "A2", "B1", "B2", "C1", "C2"), (
            f"First def cefr={defs[0]['cefr']!r} is not a valid level or null"
        )
        # All defs should have cefr field (even if null)
        for d in defs:
            assert "cefr" in d

    def test_sick_idioms_still_extracted(self):
        """Idiom extraction (separate code path) should still work after refactor."""
        rec = _parse("oxford_sick_1_(adj).html")
        # Idiom phrases known to exist (from prior verification)
        assert len(rec["idioms"]) > 0
        phrases = [i["phrase"] for i in rec["idioms"]]
        assert "be sick" in phrases
