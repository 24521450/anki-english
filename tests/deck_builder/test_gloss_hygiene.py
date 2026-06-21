"""Tests for the P0 gloss hygiene helper.

Locks in the 4 mechanical rules:
  1. Literal ``\\|`` → ``|`` (un-escape pipe)
  2. Compact pipe spacing (``a | b`` / ``a |b`` / ``a| b`` → ``a|b``)
  3. Infer separator (``|`` / ``;`` / ``none``)
  4. Recompute ``gloss_word_count`` using validator's rule
     (mirror of ``src.deck_builder.gloss_llm.validate_verdict``).

Plus: change-detection flags (``unescaped_pipe``, ``pipe_spacing_compacted``)
and the free-form ``compact_pipe_in_text`` helper for TXT cells.
"""
import json

import pytest

from src.deck_builder.gloss_hygiene import (
    normalize_gloss,
    compact_pipe_in_text,
    HygieneResult,
)
from tools._check_gloss_hygiene import check_audit
from tools._merge_expanded_glosses import merge


class TestUnescapePipe:
    """Literal ``\\|`` is a bug — must become plain ``|``."""

    def test_single_escaped_pipe_unquoted(self):
        r = normalize_gloss("arrange \\| make inclined to act")
        assert r.gloss == "arrange|make inclined to act"
        assert r.unescaped_pipe is True
        assert r.separator == "|"

    def test_two_escaped_pipes_in_same_gloss(self):
        # Real case from audit (grateful, manage, etc.)
        r = normalize_gloss("manage officially \\| give or apply")
        assert r.gloss == "manage officially|give or apply"
        assert r.unescaped_pipe is True
        # After un-escape, the pipe is now a real pipe → separator = '|'
        assert r.separator == "|"

    def test_escaped_pipe_with_semicolon_kept(self):
        # If both \\| and ; are present, separator prefers '|' (validator order).
        r = normalize_gloss("noun: wrong use; cruel \\| treat cruelly")
        assert r.gloss == "noun: wrong use; cruel|treat cruelly"
        assert r.unescaped_pipe is True
        assert r.separator == "|"


class TestCompactPipe:
    """Pipe with surrounding whitespace must collapse to compact."""

    def test_padded_pipe_compacts(self):
        r = normalize_gloss("find route | handle situation")
        assert r.gloss == "find route|handle situation"
        assert r.pipe_spacing_compacted is True
        assert r.unescaped_pipe is False

    def test_left_padded_pipe_compacts(self):
        r = normalize_gloss("find route| handle situation")
        assert r.gloss == "find route|handle situation"
        assert r.pipe_spacing_compacted is True

    def test_right_padded_pipe_compacts(self):
        r = normalize_gloss("find route |handle situation")
        assert r.gloss == "find route|handle situation"
        assert r.pipe_spacing_compacted is True

    def test_already_compact_pipe_passes_through(self):
        r = normalize_gloss("find route|handle situation")
        assert r.gloss == "find route|handle situation"
        assert r.pipe_spacing_compacted is False

    def test_multiple_padded_pipes_all_compact(self):
        r = normalize_gloss("a | b | c | d")
        assert r.gloss == "a|b|c|d"
        assert r.pipe_spacing_compacted is True


class TestSeparatorInference:
    """Separator is inferred from the (normalized) gloss content."""

    def test_no_separator_for_single_chunk(self):
        r = normalize_gloss("ridiculous")
        assert r.separator == "none"

    def test_pipe_separator(self):
        r = normalize_gloss("a|b")
        assert r.separator == "|"

    def test_semicolon_separator(self):
        r = normalize_gloss("a;b")
        assert r.separator == ";"

    def test_pipe_wins_over_semicolon_when_both_present(self):
        # Validator order: pipe checked first.
        r = normalize_gloss("a;b|c")
        assert r.separator == "|"

    def test_padded_pipe_still_infers_pipe(self):
        # Even if spacing is padded, separator is '|'.
        r = normalize_gloss("a | b")
        assert r.separator == "|"

    def test_escaped_pipe_becomes_pipe_after_unescape(self):
        r = normalize_gloss("a \\| b")
        assert r.separator == "|"


class TestWordCount:
    """gloss_word_count uses the validator's rule (replace separators then split)."""

    def test_single_word(self):
        r = normalize_gloss("ridiculous")
        assert r.gloss_word_count == 1

    def test_two_words(self):
        r = normalize_gloss("complete disorder")
        assert r.gloss_word_count == 2

    def test_six_words_pipe_split(self):
        r = normalize_gloss("foreigner|extraterrestrial")
        # 'foreigner|extraterrestrial' → replace | with space → 2 words
        assert r.gloss_word_count == 2

    def test_pipe_with_two_chunks_hyphen_counts_as_one_word(self):
        # 'hold/touch|manage situation' → replace | with space →
        # 'hold/touch manage situation' → split → 3 words (slash is one token)
        r = normalize_gloss("hold/touch|manage situation")
        assert r.gloss_word_count == 3

    def test_semicolon_split(self):
        r = normalize_gloss("in the middle of; among")
        # 'in the middle of; among' → 5 words (replace ; with space then split)
        assert r.gloss_word_count == 5

    def test_pipe_and_semicolon_together(self):
        r = normalize_gloss("plan; organize|adapt music")
        # All seps → spaces → 'plan  organize adapt music' = 4 words
        assert r.gloss_word_count == 4

    def test_escaped_pipe_counts_after_unescape(self):
        # Before un-escape, validator would NOT count the \| as a pipe and would
        # count \\| as 2 chars. After hygiene, the pipe counts as separator.
        r = normalize_gloss("arrange \\| make inclined to act")
        # → 'arrange|make inclined to act' → replace | with space → 5 words
        # (arrange, make, inclined, to, act)
        assert r.gloss_word_count == 5

    def test_padded_vs_compact_word_count_unchanged(self):
        # Word count must be the same regardless of pipe spacing.
        r1 = normalize_gloss("a | b")
        r2 = normalize_gloss("a|b")
        assert r1.gloss_word_count == r2.gloss_word_count == 2


class TestChangeDetection:
    """The HygieneResult.change() flag and individual booleans."""

    def test_no_change_for_already_clean_gloss(self):
        r = normalize_gloss("find route|handle situation")
        assert r.unescaped_pipe is False
        assert r.pipe_spacing_compacted is False
        assert r.changed() is False

    def test_escaped_pipe_signals_change(self):
        r = normalize_gloss("a \\| b")
        assert r.unescaped_pipe is True
        assert r.changed() is True

    def test_spacing_change_signals_change(self):
        r = normalize_gloss("a | b")
        assert r.pipe_spacing_compacted is True
        assert r.changed() is True

    def test_both_changes(self):
        r = normalize_gloss("a \\| b | c")
        assert r.unescaped_pipe is True
        assert r.pipe_spacing_compacted is True
        assert r.changed() is True


class TestEdgeCases:
    """None / empty / whitespace-only inputs."""

    def test_none_becomes_empty_string(self):
        r = normalize_gloss(None)
        assert r.gloss == ""
        assert r.separator == "none"
        assert r.gloss_word_count == 0
        assert r.changed() is False

    def test_empty_string(self):
        r = normalize_gloss("")
        assert r.gloss == ""
        assert r.separator == "none"
        assert r.gloss_word_count == 0

    def test_whitespace_only(self):
        r = normalize_gloss("   ")
        assert r.gloss == "   "
        assert r.separator == "none"
        assert r.gloss_word_count == 0  # split() on whitespace returns []


class TestCompactPipeInText:
    """Free-form text helper used for TXT def cells (not audit fields)."""

    def test_compacts_padded_pipe(self):
        new, changed = compact_pipe_in_text("a | b")
        assert new == "a|b"
        assert changed is True

    def test_unescapes_literal_pipe(self):
        new, changed = compact_pipe_in_text("a \\| b")
        assert new == "a|b"
        assert changed is True

    def test_already_compact_passes_through(self):
        new, changed = compact_pipe_in_text("a|b")
        assert new == "a|b"
        assert changed is False

    def test_does_not_touch_semicolons(self):
        new, changed = compact_pipe_in_text("a ; b")
        assert new == "a ; b"  # semi spacing unchanged
        assert changed is False

    def test_empty_string(self):
        new, changed = compact_pipe_in_text("")
        assert new == ""
        assert changed is False

    def test_none_safe(self):
        # Should not crash on None
        new, changed = compact_pipe_in_text(None)
        assert new is None or new == ""
        assert changed is False


def _audit_row(word, gloss, pos="noun", cefr="B2"):
    res = normalize_gloss(gloss)
    return {
        "word": word,
        "pos": pos,
        "cefr": cefr,
        "def_before": "source definition",
        "gloss_after": res.gloss,
        "separator": res.separator,
        "rule_applied": "test",
        "gloss_word_count": res.gloss_word_count,
        "gate_status": "pass",
        "source": "test",
        "fix_status": "test",
    }


class TestCheckerDebtReport:
    """The checker reports all validator/style debt, not only total word count."""

    def test_reports_validator_and_pos_label_debt(self, tmp_path):
        path = tmp_path / "audit.jsonl"
        rows = [
            _audit_row("navigate", "find or plan a route|handle a complex situation", pos="verb"),
            _audit_row("domain", "internet domain name"),
            _audit_row("generic", "general", pos="adjective"),
            _audit_row("abuse", "noun: wrong use|verb: treat badly"),
        ]
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8",
        )

        result = check_audit(path)

        assert result["hard"] == {}
        debt = result["debt"]
        assert len(debt["gloss_too_long"]) == 1
        assert len(debt["chunk_word_count"]) == 1
        assert len(debt["headword_in_definition"]) == 1
        assert len(debt["morphological_variant"]) == 1
        assert len(debt["pos_label_candidate"]) == 1


class TestMergeExpandedGlosses:
    """The merge tool must not update ambiguous duplicate-key master rows."""

    def test_multi_match_is_skipped_and_reported(self):
        expanded = [{
            "word": "duplicate",
            "pos": "noun",
            "cefr": "C1",
            "def_before": "source definition",
            "gloss_after": "new gloss",
            "gate_status": "pass",
        }]
        master = [
            _audit_row("duplicate", "old one", cefr="C1"),
            _audit_row("duplicate", "old two", cefr="C1"),
        ]

        updated, stats = merge(expanded, master)

        assert stats["multi_match"] == 1
        assert stats["updated"] == 0
        assert updated[0]["gloss_after"] == "old one"
        assert updated[1]["gloss_after"] == "old two"
