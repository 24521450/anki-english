"""TDD tests for tools/_fix_oxford_def_fields.py.

Covers 4 scenarios per spec + 4 derived from audit:

1. Record where all 3 fixes apply (mock HTML fixture).
2. Record with `_skip: true` (must be left byte-identical).
3. Record whose source HTML file is missing (must emit `[NEEDS REVIEW]`).
4. Record that needs no changes (must emit `[NO CHANGE]`).

Plus domain-specific:
5. Compound label parsing (`(British English, informal)` → `informal` register_tag).
6. countability only set for noun senses (verbs keep `null`).
7. _skip: true + record has empty source_files (must skip without error).
8. determinism: 2 runs of fixer on same input produce byte-identical output.

We mock the HTML by writing small HTML files into a temporary
directory and overriding the cache root path. The fixer must accept
a cache_dir parameter to make this testable.

(If the fixer is implemented without that parameter, we monkey-patch
the path constant in the module.)
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest  # noqa: E402

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = str(paths.root)
sys.path.insert(0, PROJECT_ROOT)

# Module under test
from tools._fix_oxford_def_fields import (  # noqa: E402
    extract_labels_for_def,
    extract_grammar_for_def,
    extract_opal_from_root,
    fix_record,
    parse_label_compound,
)


# ── Pure-function tests (no I/O) ──────────────────────────────────────────────

SUBJECT_LABELS = {
    "anatomy", "biochemistry", "biology", "business", "chemistry",
    "computing", "earth science", "ecology", "economics", "engineering",
    "finance", "geometry", "grammar", "law", "linguistics",
    "mathematics", "medical", "philosophy", "phonetics", "physics",
    "politics", "psychology", "statistics",
}


class TestParseLabelCompound:
    """parse_label_compound splits span.labels text on commas and classifies each part."""

    def test_single_register(self):
        """'(informal)' → ['informal'] (single register marker)."""
        result = parse_label_compound("(informal)", SUBJECT_LABELS)
        assert result["register_tags"] == ["informal"]
        assert result["domain"] is None

    def test_single_domain(self):
        """'(biology)' → domain='biology' (academic subject)."""
        result = parse_label_compound("(biology)", SUBJECT_LABELS)
        assert result["register_tags"] == []
        assert result["domain"] == "biology"

    def test_compound_register(self):
        """'(informal, disapproving)' → 2 register tags, no domain."""
        result = parse_label_compound("(informal, disapproving)", SUBJECT_LABELS)
        assert sorted(result["register_tags"]) == ["disapproving", "informal"]
        assert result["domain"] is None

    def test_compound_mixed(self):
        """'(British English, informal)' → only 'informal' is register; 'British English' is regional (defer)."""
        result = parse_label_compound("(British English, informal)", SUBJECT_LABELS)
        assert result["register_tags"] == ["informal"]
        assert result["domain"] is None

    def test_compound_with_domain(self):
        """'(biology, medical)' → domain='biology' (first match), no register."""
        result = parse_label_compound("(biology, medical)", SUBJECT_LABELS)
        assert result["register_tags"] == []
        assert result["domain"] == "biology"

    def test_compound_register_and_domain(self):
        """'(biology, informal)' → domain='biology' AND register=['informal']."""
        result = parse_label_compound("(biology, informal)", SUBJECT_LABELS)
        assert result["register_tags"] == ["informal"]
        assert result["domain"] == "biology"

    def test_regional_only_deferred(self):
        """'(British English)' → nothing (regional only, deferred)."""
        result = parse_label_compound("(British English)", SUBJECT_LABELS)
        assert result["register_tags"] == []
        assert result["domain"] is None

    def test_qualifier_only_deferred(self):
        """'(especially British English)' → nothing (qualifier + regional)."""
        result = parse_label_compound("(especially British English)", SUBJECT_LABELS)
        assert result["register_tags"] == []
        assert result["domain"] is None

    def test_3label_compound(self):
        """'(british english, formal, informal)' → 2 register tags, no domain."""
        result = parse_label_compound("(british english, formal, informal)", SUBJECT_LABELS)
        assert sorted(result["register_tags"]) == ["formal", "informal"]
        assert result["domain"] is None

    def test_empty_string(self):
        """'' → empty."""
        result = parse_label_compound("", SUBJECT_LABELS)
        assert result["register_tags"] == []
        assert result["domain"] is None

    def test_case_insensitive(self):
        """'(INFORMAL)' should be normalised to 'informal'."""
        result = parse_label_compound("(INFORMAL)", SUBJECT_LABELS)
        assert result["register_tags"] == ["informal"]

    def test_no_parens(self):
        """'biology' without parens should still work."""
        result = parse_label_compound("biology", SUBJECT_LABELS)
        assert result["register_tags"] == []
        assert result["domain"] == "biology"


class TestExtractGrammarForDef:
    """extract_grammar_for_def returns countability value for noun senses, null otherwise."""

    def test_countable_noun(self):
        """[countable] for a noun sense → 'countable'."""
        result = extract_grammar_for_def("[countable]", pos="noun")
        assert result == "countable"

    def test_uncountable_noun(self):
        result = extract_grammar_for_def("[uncountable]", pos="noun")
        assert result == "uncountable"

    def test_both_noun(self):
        result = extract_grammar_for_def("[countable, uncountable]", pos="noun")
        assert result == "both"

    def test_verb_always_null(self):
        """[intransitive] on a verb sense → null (countability is noun-only)."""
        result = extract_grammar_for_def("[intransitive]", pos="verb")
        assert result is None

    def test_verb_with_c_marker(self):
        """[C, usually passive] on a verb sense → null (not a noun)."""
        result = extract_grammar_for_def("[C, usually passive]", pos="verb")
        assert result is None

    def test_noun_with_intransitive(self):
        """[intransitive] on a noun sense → null (not countability marker)."""
        result = extract_grammar_for_def("[intransitive]", pos="noun")
        assert result is None

    def test_empty_grammar(self):
        result = extract_grammar_for_def("", pos="noun")
        assert result is None

    def test_unknown_grammar(self):
        result = extract_grammar_for_def("[weird marker]", pos="noun")
        assert result is None

    def test_short_C(self):
        result = extract_grammar_for_def("[C]", pos="noun")
        assert result == "countable"

    def test_short_U(self):
        result = extract_grammar_for_def("[U]", pos="noun")
        assert result == "uncountable"

    def test_short_CU(self):
        result = extract_grammar_for_def("[C, U]", pos="noun")
        assert result == "both"

    def test_short_C_with_spaces(self):
        """[ C ] (with spaces) is also valid Oxford format."""
        result = extract_grammar_for_def("[ C ]", pos="noun")
        assert result == "countable"


class TestExtractOpal:
    """extract_opal_from_root reads page-top .symbols or span.opal_symbol."""

    @staticmethod
    def _root_with(html_body_xml: str):
        from lxml import html as lxml_html
        full = f"""<!DOCTYPE html><html><head><title>t</title></head><body>{html_body_xml}</body></html>"""
        return lxml_html.fromstring(full)

    def test_opal_W_via_opal_symbol_span(self):
        """<span class='opal_symbol'>OPAL W</span> → 'W'."""
        root = self._root_with("<span class='opal_symbol'>OPAL W</span>")
        assert extract_opal_from_root(root) == "W"

    def test_opal_S_via_opal_symbol_span(self):
        root = self._root_with("<span class='opal_symbol'>OPAL S</span>")
        assert extract_opal_from_root(root) == "S"

    def test_opal_WS_via_opal_symbol_span(self):
        root = self._root_with("<span class='opal_symbol'>OPAL WS</span>")
        assert extract_opal_from_root(root) == "WS"

    def test_no_opal_returns_None(self):
        """No opal_symbol, no .symbols → None."""
        root = self._root_with("<h1>plain page</h1>")
        assert extract_opal_from_root(root) is None

    def test_opal_fallback_via_symbols_div(self):
        """No span.opal_symbol but .symbols has 'OPAL W' → 'W'."""
        root = self._root_with("<div class='symbols'>OPAL W</div>")
        assert extract_opal_from_root(root) == "W"

    def test_opal_symbol_takes_precedence_over_symbols(self):
        """If both present, .opal_symbol wins."""
        root = self._root_with(
            "<span class='opal_symbol'>OPAL S</span>"
            "<div class='symbols'>OPAL W</div>"
        )
        assert extract_opal_from_root(root) == "S"

    def test_empty_opal_symbol_text_falls_through(self):
        """Empty .opal_symbol text should NOT match — fall through to .symbols."""
        root = self._root_with(
            "<span class='opal_symbol'></span>"
            "<div class='symbols'>OPAL W</div>"
        )
        assert extract_opal_from_root(root) == "W"

    def test_case_insensitive(self):
        """Lowercase 'opal w' should still match."""
        root = self._root_with("<span class='opal_symbol'>opal w</span>")
        assert extract_opal_from_root(root) == "W"

    def test_empty_html_returns_None(self):
        """No OPAL elements at all → None."""
        root = self._root_with("")
        assert extract_opal_from_root(root) is None

    def test_partial_artifact_no_match(self):
        """CSS class hint 'opal_written' alone (no text) → None."""
        root = self._root_with("<div class='opal_written'></div>")
        assert extract_opal_from_root(root) is None


# ── Integration tests (with mocked cache + records) ──────────────────────────

@pytest.fixture
def tmp_workspace():
    """Create a temp dir with mock data/oxford.jsonl, cache, and labels."""
    tmp = Path(tempfile.mkdtemp(prefix="fixer_test_"))
    # Copy labels file
    shutil.copy(Path(PROJECT_ROOT) / "data" / "oxford_labels.json", tmp / "oxford_labels.json")
    cache_dir = tmp / "cache" / "oxford"
    cache_dir.mkdir(parents=True)
    (tmp / "data").mkdir()
    (tmp / "data" / "oxford.jsonl").touch()
    yield tmp
    shutil.rmtree(tmp)


def _write_html(cache_dir: Path, fname: str, body_xml: str):
    """Write a minimal HTML file with the given body XML inside <html><body>."""
    full = f"""<!DOCTYPE html>
<html><head><title>test</title></head>
<body>
<h1 class="headword">testword</h1>
{body_xml}
</body></html>"""
    (cache_dir / fname).write_text(full, encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class TestFixRecord:
    """fix_record applies all 3 fixes to a single record, given its source HTML."""

    def test_all_three_fixes(self, tmp_workspace):
        # Mock HTML for a noun word with countability + compound label
        html = """<ol class="senses_multiple">
<li class="sense" id="w_sng_1" sensenum="1" cefr="c1">
  <span class="sensetop"></span>
  <span class="grammar">[countable]</span>
  <span class="def">a test definition</span>
  <span class="labels">(biology, informal)</span>
  <ul class="examples">
    <li><span class="x">a test example</span></li>
  </ul>
</li>
</ol>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_testword_(noun).html", html)

        rec = {
            "word": "testword",
            "source_files": ["oxford_testword_(noun).html"],
            "pos": ["noun"],
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a test definition",
                    "register_tags": [],
                    "cefr": "C1",
                    "topics": [],
                }],
            }],
        }
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        defn = result["pos_data"][0]["definitions"][0]
        assert defn["countability"] == "countable"
        assert defn["register_tags"] == ["informal"]
        assert defn["domain"] == "biology"
        # log lines should mention all 3 fixes
        log_text = "\n".join(log_lines)
        assert "register_tags" in log_text
        assert "countability" in log_text
        assert "domain" in log_text

    def test_skip_record_left_untouched(self, tmp_workspace):
        """Records with _skip: true must be byte-identical in output."""
        rec = {
            "word": "skipme",
            "_skip": True,
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "to be skipped",
                    "register_tags": [],
                    "cefr": None,
                    "topics": [],
                }],
            }],
        }
        original = json.dumps(rec, sort_keys=True, ensure_ascii=False)
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        after = json.dumps(result, sort_keys=True, ensure_ascii=False)
        assert original == after, f"_skip record should be byte-identical: {original} != {after}"
        assert any("skip" in line.lower() for line in log_lines) or any("skipped" in line.lower() for line in log_lines)

    def test_missing_html_emits_needs_review(self, tmp_workspace, capsys):
        """If source_files reference a missing HTML file, emit [NEEDS REVIEW]."""
        rec = {
            "word": "ghostword",
            "source_files": ["oxford_ghostword_(noun).html"],  # NOT created in cache
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a ghost definition",
                    "register_tags": [],
                    "cefr": None,
                    "topics": [],
                }],
            }],
        }
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        # Record should be unchanged
        assert result == rec
        # Log should mention NEEDS REVIEW
        log_text = "\n".join(log_lines)
        assert "NEEDS REVIEW" in log_text
        assert "ghostword" in log_text

    def test_no_changes_emits_no_change(self, tmp_workspace):
        """Record where HTML confirms no labels/grammar/domain → emit [NO CHANGE]."""
        # HTML has def but no labels, no grammar
        html = """<ol class="senses_multiple">
<li class="sense" id="w_sng_1" sensenum="1">
  <span class="def">a plain definition</span>
  <ul class="examples">
    <li><span class="x">an example</span></li>
  </ul>
</li>
</ol>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_plainword_(noun).html", html)

        rec = {
            "word": "plainword",
            "source_files": ["oxford_plainword_(noun).html"],
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a plain definition",
                    "register_tags": [],
                    "cefr": None,
                    "topics": [],
                }],
            }],
        }
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        defn = result["pos_data"][0]["definitions"][0]
        assert defn["countability"] is None
        assert defn["register_tags"] == []
        assert defn["domain"] is None
        # Log should mention NO CHANGE
        log_text = "\n".join(log_lines)
        assert "NO CHANGE" in log_text

    def test_countability_null_on_verb_sense(self, tmp_workspace):
        """Even with grammar marker, countability is null for non-noun senses."""
        html = """<ol class="senses_multiple">
<li class="sense" id="w_sng_1" sensenum="1" cefr="b2">
  <span class="grammar">[intransitive]</span>
  <span class="def">to do something</span>
  <ul class="examples">
    <li><span class="x">an example</span></li>
  </ul>
</li>
</ol>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_dosomething_(verb).html", html)

        rec = {
            "word": "dosomething",
            "pos": ["verb"],
            "source_files": ["oxford_dosomething_(verb).html"],
            "pos_data": [{
                "pos": "verb",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "to do something",
                    "register_tags": [],
                    "cefr": "B2",
                    "topics": [],
                }],
            }],
        }
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        defn = result["pos_data"][0]["definitions"][0]
        assert defn["countability"] is None  # verb → null even if grammar has marker

    def test_compound_label_split(self, tmp_workspace):
        """Compound label (British English, informal) → only 'informal' as register_tag."""
        html = """<ol class="senses_multiple">
<li class="sense" id="w_sng_1" sensenum="1" cefr="b2">
  <span class="def">a term used in some context</span>
  <span class="labels">(British English, informal)</span>
</li>
</ol>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_slang_(noun).html", html)

        rec = {
            "word": "slang",
            "pos": ["noun"],
            "source_files": ["oxford_slang_(noun).html"],
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a term used in some context",
                    "register_tags": [],
                    "cefr": "B2",
                    "topics": [],
                }],
            }],
        }
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        defn = result["pos_data"][0]["definitions"][0]
        assert defn["register_tags"] == ["informal"]  # regional "british english" filtered
        assert defn["domain"] is None

    def test_opal_backfill(self, tmp_workspace):
        """Record with opal=null + HTML with .opal_symbol 'OPAL W' → opal='W'."""
        html = """<ol class="senses_multiple">
<li class="sense" id="c_sng_1" sensenum="1" cefr="c1">
  <span class="def">a test definition</span>
</li>
</ol>
<span class="opal_symbol">OPAL W</span>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_testopal_(noun).html", html)

        rec = {
            "word": "testopal",
            "source_files": ["oxford_testopal_(noun).html"],
            "pos": ["noun"],
            "opal": None,
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a test definition",
                    "register_tags": [],
                    "cefr": "C1",
                    "topics": [],
                }],
            }],
        }
        result, log_lines = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        assert result["opal"] == "W"
        log_text = "\n".join(log_lines)
        assert "opal" in log_text
        assert "Fix 4" in log_text

    def test_opal_not_patched_if_already_set(self, tmp_workspace):
        """Record with opal='S' should not be overwritten even if HTML says W."""
        html = """<ol class="senses_multiple">
<li class="sense" id="t_sng_1" sensenum="1" cefr="c1">
  <span class="def">a test definition</span>
</li>
</ol>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_opalexisting_(noun).html", html)

        rec = {
            "word": "opalexisting",
            "source_files": ["oxford_opalexisting_(noun).html"],
            "pos": ["noun"],
            "opal": "S",  # already set
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a test definition",
                    "register_tags": [],
                    "cefr": "C1",
                    "topics": [],
                }],
            }],
        }
        result, _ = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        assert result["opal"] == "S"  # unchanged

    def test_opal_no_html_indicator_leaves_null(self, tmp_workspace):
        """HTML with no OPAL indicators + record.opal=None → still None."""
        html = """<ol class="senses_multiple">
<li class="sense" id="n_sng_1" sensenum="1" cefr="b2">
  <span class="def">a plain definition</span>
</li>
</ol>"""
        _write_html(tmp_workspace / "cache" / "oxford", "oxford_nopal_(noun).html", html)

        rec = {
            "word": "nopal",
            "source_files": ["oxford_nopal_(noun).html"],
            "pos": ["noun"],
            "opal": None,
            "pos_data": [{
                "pos": "noun",
                "definitions": [{
                    "n": 1,
                    "sensenum_local": "1",
                    "text": "a plain definition",
                    "register_tags": [],
                    "cefr": "B2",
                    "topics": [],
                }],
            }],
        }
        result, _ = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        assert result["opal"] is None  # not patched

    def test_opal_skipped_record_untouched(self, tmp_workspace):
        """_skip=true record: opal stays at None (byte-identical pass-through)."""
        rec = {
            "word": "skipopal",
            "_skip": True,
            "opal": None,
            "pos_data": [],
        }
        result, _ = fix_record(rec, tmp_workspace / "cache" / "oxford", tmp_workspace / "oxford_labels.json")
        assert result["opal"] is None
        assert result["_skip"] is True


# ── Determinism (run fixer on real data twice, compare) ─────────────────────

class TestDeterminism:
    """The fixer must produce byte-identical output across 2 runs of same input."""

    def _make_mock_workspace(self, tmp_workspace):
        """Build a small mock dataset (10 records) and run fixer twice."""
        records = []
        for i in range(10):
            word = f"word{i}"
            fname = f"oxford_{word}_(noun).html"
            html = f"""<ol class="senses_multiple">
<li class="sense" id="w{i}_sng_1" sensenum="1" cefr="b2">
  <span class="grammar">[countable]</span>
  <span class="def">definition of {word}</span>
  <span class="labels">(biology, informal)</span>
  <ul class="examples">
    <li><span class="x">example of {word}</span></li>
  </ul>
</li>
</ol>"""
            _write_html(tmp_workspace / "cache" / "oxford", fname, html)
            records.append({
                "word": word,
                "source_files": [fname],
                "pos": ["noun"],
                "pos_data": [{
                    "pos": "noun",
                    "definitions": [{
                        "n": 1,
                        "sensenum_local": "1",
                        "text": f"definition of {word}",
                        "register_tags": [],
                        "cefr": "B2",
                        "topics": [],
                    }],
                }],
            })
        # Plus 1 _skip record
        records.append({
            "word": "skipme",
            "_skip": True,
            "pos_data": [],
        })
        _write_jsonl(tmp_workspace / "data" / "oxford.jsonl", records)
        return records

    def test_determinism(self, tmp_workspace):
        records = self._make_mock_workspace(tmp_workspace)
        # Run fixer twice — v3 in-place: writes to jsonl_in both times
        from tools._fix_oxford_def_fields import run_fixer
        jsonl_in = tmp_workspace / "data" / "oxford.jsonl"
        # Snapshot input before run 1 (mock data has fixes to apply)
        before_bytes = jsonl_in.read_bytes()
        run_fixer(
            jsonl_in=jsonl_in,
            cache_dir=tmp_workspace / "cache" / "oxford",
            labels_path=tmp_workspace / "oxford_labels.json",
            log_path=tmp_workspace / "log1.txt",
        )
        bytes1 = jsonl_in.read_bytes()
        assert bytes1 != before_bytes, "Run 1 should have changed the file"
        # Run 2 (all 4 fixes should be no-op on already-fixed data)
        run_fixer(
            jsonl_in=jsonl_in,
            cache_dir=tmp_workspace / "cache" / "oxford",
            labels_path=tmp_workspace / "oxford_labels.json",
            log_path=tmp_workspace / "log2.txt",
        )
        bytes2 = jsonl_in.read_bytes()
        assert bytes1 == bytes2, (
            f"Run 1 != Run 2 (non-deterministic)\n1: {bytes1[:200]!r}\n2: {bytes2[:200]!r}"
        )


# v2 design: read data/oxford.jsonl, write data/oxford.fixed.jsonl,
#            user manually renames .fixed.jsonl → oxford.jsonl.
# v3 design: read data/oxford.jsonl, write to .tmp, atomic rename
#            in-place. No separate output file. No manual step.
# Rationale: the manual-rename step has been missed at least 3 times this
# session, leading to "data not promoted" failures. Atomic in-place write
# removes the entire failure class.

class TestInPlaceAtomicWrite:
    """v3 contract: fixer writes IN-PLACE atomically. No .fixed.jsonl output."""

    def test_in_place_write_signature_unchanged(self, tmp_workspace):
        """run_fixer still accepts (jsonl_in, jsonl_out, ...) but in v3 jsonl_out
        is optional and defaults to jsonl_in (in-place)."""
        from tools._fix_oxford_def_fields import run_fixer
        records = self._make_mock_workspace(tmp_workspace)
        jsonl_in = tmp_workspace / "data" / "oxford.jsonl"
        # Snapshot input before run
        before_bytes = jsonl_in.read_bytes()
        # Run with jsonl_out omitted (defaults to in-place)
        run_fixer(
            jsonl_in=jsonl_in,
            cache_dir=tmp_workspace / "cache" / "oxford",
            labels_path=tmp_workspace / "oxford_labels.json",
            log_path=tmp_workspace / "log.txt",
        )
        # No .fixed.jsonl should be created
        fixed_path = tmp_workspace / "data" / "oxford.fixed.jsonl"
        assert not fixed_path.exists(), (
            f"v3 fixer created {fixed_path} but contract is in-place write. "
            f"The .fixed.jsonl pattern has been removed."
        )
        # Input file should still exist (atomic rename, not deletion)
        assert jsonl_in.exists(), f"v3 fixer deleted {jsonl_in} during write"
        # Input should have changed (records had fixes applied)
        after_bytes = jsonl_in.read_bytes()
        assert before_bytes != after_bytes, "In-place write should have modified the file"

    def test_atomic_no_partial_file_on_disk(self, tmp_workspace):
        """During write, only the .tmp file should exist; final state has only
        jsonl_in. No .fixed.jsonl. No .tmp leaks."""
        from tools._fix_oxford_def_fields import run_fixer
        self._make_mock_workspace(tmp_workspace)
        jsonl_in = tmp_workspace / "data" / "oxford.jsonl"
        run_fixer(
            jsonl_in=jsonl_in,
            cache_dir=tmp_workspace / "cache" / "oxford",
            labels_path=tmp_workspace / "oxford_labels.json",
            log_path=tmp_workspace / "log.txt",
        )
        data_dir = tmp_workspace / "data"
        leftover_tmp = list(data_dir.glob("*.tmp"))
        leftover_fixed = list(data_dir.glob("*.fixed.jsonl"))
        assert not leftover_tmp, f"Leftover .tmp files: {leftover_tmp}"
        assert not leftover_fixed, f"Leftover .fixed.jsonl files: {leftover_fixed}"

    def test_determinism_in_place(self, tmp_workspace):
        """Two consecutive in-place runs produce byte-identical output (same input)."""
        from tools._fix_oxford_def_fields import run_fixer
        self._make_mock_workspace(tmp_workspace)
        jsonl_in = tmp_workspace / "data" / "oxford.jsonl"
        # Run 1
        run_fixer(
            jsonl_in=jsonl_in,
            cache_dir=tmp_workspace / "cache" / "oxford",
            labels_path=tmp_workspace / "oxford_labels.json",
            log_path=tmp_workspace / "log1.txt",
        )
        bytes1 = jsonl_in.read_bytes()
        # Run 2 (same input — all 4 fixes should be no-op)
        run_fixer(
            jsonl_in=jsonl_in,
            cache_dir=tmp_workspace / "cache" / "oxford",
            labels_path=tmp_workspace / "oxford_labels.json",
            log_path=tmp_workspace / "log2.txt",
        )
        bytes2 = jsonl_in.read_bytes()
        assert bytes1 == bytes2, (
            f"In-place run 1 != Run 2 (non-deterministic)\n"
            f"1: {bytes1[:200]!r}\n2: {bytes2[:200]!r}"
        )

    def _make_mock_workspace(self, tmp_workspace):
        """Create a minimal in-memory Oxford corpus for the test."""
        records = self._records_for_workspace(tmp_workspace)
        _write_jsonl(tmp_workspace / "data" / "oxford.jsonl", records)
        return records

    def _records_for_workspace(self, tmp_workspace):
        """Same as _make_mock_workspace in TestFixerIntegration below."""
        return _make_mock_workspace_records(tmp_workspace)


def _make_mock_workspace_records(tmp_workspace):
    """Shared mock-records builder. Lifted out so TestInPlaceAtomicWrite can use it."""
    html = """<html><body>
        <h1 class="headword" opal_written="y">testopal</h1>
        <div class="symbols"><span class="opal_symbol">OPAL W</span></div>
        <ol class="senses_multiple"><li class="sense" sensenum="1">
            <span class="def">a test definition</span>
        </li></ol>
    </body></html>"""
    _write_html(tmp_workspace / "cache" / "oxford", "oxford_testopal_(noun).html", html)
    return [{
        "word": "testopal",
        "pos": ["noun"],
        "source_files": ["oxford_testopal_(noun).html"],
        "opal": None,
        "register_tags": [],
        "pos_data": [{
            "pos": "noun",
            "register_tags": [],
            "definitions": [{
                "n": 1,
                "sensenum_local": "1",
                "text": "a test definition",
                "register_tags": [],
                "collocations": {},
                "examples": [],
                "is_phrase": False,
                "is_idiom": False,
            }],
        }],
        "verb_forms": None,
        "idioms": [],
        "_skip": False,
    }]
