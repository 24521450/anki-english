"""Tests for build_notes.py encoding fix + parenthetical lookup.

Locks in:
1. The `|` separator change (was ` ; `) and the max_n=1 default
   in `_format_examples` (was 2). These are paired: def and ex must have
   the same number of pipe-separated chunks for the template to pair
   def[i] with ex[i] correctly.
2. Card Identity = (Word, CEFR, LIST) — `_parse_existing_txt` preserves
   parenthetical disambiguators in the lookup key, and `lookup_gloss`
   exact-matches the full disambiguated word before falling back to the
   base word (with a ghost-verdict guard).

See CONTEXT.md § Card Identity (2026-06-21) and § Sense Sorting
(replaces the legacy Sense Cap, removed 2026-06-21).
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')
sys.path.insert(0, str(PROJECT_ROOT))

from tools.build_notes import (
    _format_examples,
    DEF_SEPARATOR,
    EX_SEP,
    _parse_existing_txt,
    get_word_candidates,
    lookup_gloss,
)


class TestSeparators:
    """The build pipeline must use '|' (pipe) as the between-sense separator
    so the EAVM template (back_template.txt:172, front_template.txt:82) can
    split def and ex into rows."""

    def test_def_separator_is_pipe(self):
        assert DEF_SEPARATOR == '|', (
            f"DEF_SEPARATOR must be '|' (template contract), got {DEF_SEPARATOR!r}"
        )

    def test_ex_separator_is_pipe(self):
        assert EX_SEP == '|', (
            f"EX_SEP must be '|' (template contract), got {EX_SEP!r}"
        )


class TestFormatExamples:
    """`_format_examples` default max_n must be 1 so def[i] pairs with ex[i]
    in the template (def has 1 chunk per sense, ex must also have 1 chunk per
    sense — not 2 — to maintain index alignment)."""

    def test_max_n_1_default_keeps_only_first_example(self):
        examples = [
            {'text': 'first ex'},
            {'text': 'second ex'},
            {'text': 'third ex'},
        ]
        result = _format_examples(examples)  # default max_n=1
        assert result == 'first ex'
        assert '|' not in result  # no separator with single example
        assert ' ; ' not in result  # never use '; ' here

    def test_max_n_1_keeps_pipe_separator_when_override_to_2(self):
        examples = [
            {'text': 'first ex'},
            {'text': 'second ex'},
        ]
        result = _format_examples(examples, max_n=2)
        # Even when caller asks for 2, separator is '|' not ' ; '
        assert result == 'first ex|second ex', (
            f"EX_SEP.join must use '|', got {result!r}"
        )

    def test_empty_examples_returns_empty_string(self):
        assert _format_examples([]) == ''
        assert _format_examples(None) == ''

    def test_skips_examples_with_empty_text(self):
        examples = [
            {'text': 'first ex'},
            {'text': ''},       # empty text — should be skipped
            {'text': 'third ex'},
        ]
        result = _format_examples(examples, max_n=3)
        assert result == 'first ex|third ex'


class TestBuildRecordCardsPairing:
    """Simulate the def + ex join logic from build_record_cards. Confirms that
    with the new encoding, a 3-sense card produces def and ex with matching
    chunk counts (so def[i] pairs with ex[i] in the template)."""

    def test_3_sense_card_pairing(self):
        # 3 senses, each with 1 example — the typical case after build_notes fix
        senses = [
            {'text': 'sense 1 def', 'examples': [{'text': 'sense 1 ex'}]},
            {'text': 'sense 2 def', 'examples': [{'text': 'sense 2 ex'}]},
            {'text': 'sense 3 def', 'examples': [{'text': 'sense 3 ex'}]},
        ]
        capped = senses  # Sense Sorting: no per-card cap (2026-06-21)
        defn = DEF_SEPARATOR.join((s['text'] or '') for s in capped)
        ex = EX_SEP.join(_format_examples(s['examples'] or []) for s in capped)

        assert defn == 'sense 1 def|sense 2 def|sense 3 def'
        assert ex == 'sense 1 ex|sense 2 ex|sense 3 ex'
        # Same number of chunks → template can pair def[i] with ex[i]
        assert defn.count('|') == ex.count('|'), (
            f"def and ex must have same number of chunks: defn={defn!r}, ex={ex!r}"
        )

    def test_1_sense_card_no_separator(self):
        senses = [{'text': 'only def', 'examples': [{'text': 'only ex'}]}]
        capped = senses  # Sense Sorting: no per-card cap (2026-06-21)
        defn = DEF_SEPARATOR.join((s['text'] or '') for s in capped)
        ex = EX_SEP.join(_format_examples(s['examples'] or []) for s in capped)

        assert defn == 'only def'
        assert ex == 'only ex'
        assert '|' not in defn
        assert '|' not in ex

    def test_within_sense_semicolon_preserved(self):
        """Within a sense, Oxford uses ' ; ' for sub-chunks (e.g. 'the act of
        finding sb guilty; the fact of having been found guilty'). This must
        NOT be confused with the between-sense '|' separator."""
        senses = [
            {
                'text': 'the act of finding sb guilty; the fact of having been found guilty',
                'examples': [{'text': 'one ex'}],
            },
            {
                'text': 'a strong opinion or belief',
                'examples': [{'text': 'two ex'}],
            },
        ]
        capped = senses  # Sense Sorting: no per-card cap (2026-06-21)
        defn = DEF_SEPARATOR.join((s['text'] or '') for s in capped)

        # Within-sense ';' kept, between-sense '|' added
        assert ';' in defn, "Within-sense ';' must be preserved (Oxford style)"
        assert '|' in defn, "Between-sense '|' must be present (template contract)"
        assert defn == (
            'the act of finding sb guilty; the fact of having been found guilty'
            '|a strong opinion or belief'
        )

    def test_conviction_regression_one_per_sense(self):
        """Regression test for the original build_notes.py:771 encoding bug.

        The conviction card originally had 1 short gloss (sense 2 only) but
        6 examples concatenated from all 3 senses, causing def/ex mismatch
        (learner saw 'firm belief' but read 'He plans to appeal against his
        conviction' — confusing). After the fix, _format_examples returns
        1 example per sense (max_n=1) and uses '|' to join, so def[i] pairs
        with ex[i] in the template (back_template.txt:172).

        Fixture: conviction has 3 senses at noun/C1 (legal, opinion, sincerity).
        """
        # Simulate the 3 senses as they appear in oxford_merged.jsonl
        conviction_senses = [
            {
                # sense 0: legal — 3 examples in jsonl
                'examples': [
                    {'text': 'He plans to appeal against his conviction.'},
                    {'text': 'She has six previous convictions for theft.'},
                    {'text': 'an offence that carries, on conviction, a sentence of not more than five years\' imprisonment'},
                ],
            },
            {
                # sense 1: opinion — 3 examples
                'examples': [
                    {'text': 'strong political/moral convictions'},
                    {'text': 'She was motivated by deep religious conviction.'},
                    {'text': 'We were sustained by the conviction that all would be well in the end.'},
                ],
            },
            {
                # sense 2: sincerity — 3 examples
                'examples': [
                    {'text': "'Not true!' she said with conviction."},
                    {'text': 'He said he agreed but his voice lacked conviction.'},
                    {'text': "The leader's speech in defence of the policy didn't carry much conviction."},
                ],
            },
        ]

        # Simulate the build_record_cards logic (lines 449, 772)
        ex = EX_SEP.join(_format_examples(s['examples'] or []) for s in conviction_senses)

        # The fix: max_n=1 keeps ONLY the first example of each sense
        assert ex == (
            'He plans to appeal against his conviction.|'
            'strong political/moral convictions|'
            "'Not true!' she said with conviction."
        ), f"Expected 1 ex per sense joined with '|', got: {ex!r}"

        # 3 senses → 2 separators (between-sense), 0 within-sense
        assert ex.count('|') == 2, (
            f"3 senses must produce 2 '|' separators (between-sense), got {ex.count('|')}"
        )
        assert ex.count(' ; ') == 0, (
            f"_format_examples with max_n=1 must not produce within-sense ' ; ' separators, got: {ex!r}"
        )

        # And verify the original bug: with max_n=2 (the old default), each sense
        # would contribute 2 examples, producing 6 chunks with 5 '|' separators
        # (or 5 ' ; ' separators with the old build_notes). Either way, def[i]
        # would NOT pair with the right example. This is the regression we're
        # locking in.
        ex_old_default = EX_SEP.join(_format_examples(s['examples'] or []) for s in conviction_senses)
        # With max_n=1 (current default), ex is 1 per sense — template pairing works.
        # The old default of max_n=2 would have produced 6 chunks, breaking the
        # def[i]/ex[i] pairing. We don't test the old path directly (it's gone),
        # but the assertion on `ex.count('|') == 2` documents the invariant.


class TestParseExistingTxtPreservesParenthetical:
    """Card Identity = (Word, CEFR, LIST). `_parse_existing_txt` keeps the
    parenthetical disambiguator in the lookup key so audit glosses for
    homonym cards can be exact-matched.

    Regression for the P3C bug: pre-2026-06-21, the parser stripped
    parentheticals into base-word keys, so `counter (argue against)`
    and `counter (long flat surface)` both mapped to `counter` and could
    not be distinguished during gloss lookup. Audit glosses keyed by the
    full disambiguated word were silently bypassed.
    """

    def _write_minimal_txt(self, tmp_path: Path, data_rows: list[str]) -> Path:
        """Write a minimal 17-col TXT with the required header."""
        header = (
            "#separator:tab\n"
            "#html:true\n"
            "#guid column:1\n"
            "#notetype column:2\n"
            "#deck column:3\n"
            "#tags column:17\n"
        )
        path = tmp_path / "vocab.txt"
        path.write_text(header + "\n".join(data_rows) + "\n", encoding="utf-8")
        return path

    def _make_row(
        self,
        guid: str,
        word: str,
        pos: str,
        cefr: str,
        defn: str = "stub",
        tags: str = "Source::Oxford CEFR::B2 CEFR::oxford",
    ) -> str:
        """Build a 17-col TSV row matching the EAVM contract."""
        return "\t".join([
            guid,                                # 1: GUID
            "English Academic Vocabulary Model", # 2: notetype
            "English Academic Vocabulary::Oxford", # 3: deck
            word,                                # 4: word
            pos,                                 # 5: pos
            "/ipa/",                             # 6: ipa
            defn,                                # 7: definition
            "stub ex",                           # 8: example
            "",                                  # 9: collocations
            "",                                  # 10: wordfamily
            "[sound:stub_uk.mp3]",               # 11: uk_audio
            "[sound:stub_us.mp3]",               # 12: us_audio
            "Oxford",                            # 13: source1
            "Oxford",                            # 14: source2
            cefr,                                # 15: cefr
            "",                                  # 16: idioms
            tags,                                # 17: tags
        ])

    def test_parenthetical_word_preserved_in_key(self, tmp_path):
        path = self._write_minimal_txt(tmp_path, [
            self._make_row("G1", "counter (argue against)", "verb", "C1"),
            self._make_row("G2", "counter (long flat surface)", "noun", "B2"),
        ])
        parsed = _parse_existing_txt(path)
        assert ("counter (argue against)", "verb", "C1") in parsed
        assert ("counter (long flat surface)", "noun", "B2") in parsed
        # And the base-word key MUST NOT exist (would silently collapse
        # the two homonym rows into one key — the P3C bug).
        assert ("counter", "verb", "C1") not in parsed
        assert ("counter", "noun", "B2") not in parsed

    def test_word_base_field_strips_parenthetical(self, tmp_path):
        path = self._write_minimal_txt(tmp_path, [
            self._make_row("G1", "grave (serious)", "adjective", "C1"),
        ])
        parsed = _parse_existing_txt(path)
        row = parsed[("grave (serious)", "adjective", "C1")]
        assert row["word_base"] == "grave"
        assert row["word_orig"] == "grave (serious)"

    def test_no_parenthetical_unchanged(self, tmp_path):
        path = self._write_minimal_txt(tmp_path, [
            self._make_row("G1", "yield", "noun, verb", "C1"),
        ])
        parsed = _parse_existing_txt(path)
        assert ("yield", "noun, verb", "C1") in parsed
        row = parsed[("yield", "noun, verb", "C1")]
        assert row["word_base"] == "yield"
        assert row["word_orig"] == "yield"


class TestGetWordCandidatesStripsParenthetical:
    """`get_word_candidates` strips parentheticals for source (jsonl)
    lookup. Card Identity keeps the disambiguator in the build key;
    this function still produces base-word candidates only."""

    def test_parenthetical_word_yields_base_first(self):
        cands = get_word_candidates("counter (argue against)")
        assert cands[0] == "counter", (
            f"First candidate must be base word 'counter', got {cands[0]!r}"
        )
        # And the full disambiguated word is NOT a candidate.
        assert "counter (argue against)" not in cands

    def test_three_documented_examples(self):
        # The 3 examples called out in the P3C spec.
        assert get_word_candidates("counter (argue against)")[0] == "counter"
        assert get_word_candidates("grave (serious)")[0] == "grave"
        assert get_word_candidates("strip (long narrow piece)")[0] == "strip"

    def test_no_parenthetical_unchanged(self):
        assert get_word_candidates("yield")[:1] == ["yield"]
        assert get_word_candidates("firm")[:1] == ["firm"]


class TestLookupGlossParentheticalHandling:
    """Card Identity (2026-06-21): parenthetical disambiguators must be
    preserved through gloss lookup, and unsafe base-word fallbacks must
    be blocked when disambiguated siblings exist."""

    def test_exact_match_parenthetical(self):
        """`counter (argue against)|verb|C1` exact-matches the audit key."""
        audit = {
            ("counter (argue against)", "verb", "C1"): "oppose",
            ("counter (long flat surface)", "noun", "B2"): "service desk",
        }
        result = lookup_gloss(
            audit, "counter (argue against)", "verb", "C1",
            "counter", ["verb"], "C1",
        )
        assert result == "oppose"

    def test_exact_match_long_flat_surface(self):
        audit = {
            ("counter (argue against)", "verb", "C1"): "oppose",
            ("counter (long flat surface)", "noun", "B2"): "service desk",
        }
        result = lookup_gloss(
            audit, "counter (long flat surface)", "noun", "B2",
            "counter", ["noun"], "B2",
        )
        assert result == "service desk"

    def test_unsafe_fallback_blocked_with_disambiguated_siblings(self):
        """When TXT word has disambiguator AND audit has disambiguated
        siblings at the same (pos, cefr), base-word fallback is unsafe.
        The function must NOT apply a ghost verdict from a different sense."""
        audit = {
            # Disambiguated siblings at (verb, C1) — same base word "counter"
            ("counter (argue against)", "verb", "C1"): "oppose",
            ("counter (long flat surface)", "noun", "B2"): "service desk",
            # Ghost verdict for base counter at (verb, C1) — wrong sense
            ("counter", "verb", "C1"): "WRONG_GHOST_VERDICT",
        }
        # TXT card with parenthetical + (verb, C1) → must return the
        # disambiguated gloss ("oppose"), NOT the ghost verdict.
        result = lookup_gloss(
            audit, "counter (argue against)", "verb", "C1",
            "counter", ["verb"], "C1",
        )
        assert result == "oppose", (
            f"Disambiguator guard failed — got {result!r}, "
            f"ghost verdict was incorrectly applied"
        )

    def test_no_siblings_falls_back_to_base_safely(self):
        """When TXT word has disambiguator but NO disambiguated siblings
        exist in the audit, base-word fallback is safe (no ghost to avoid)."""
        audit = {
            ("counter", "verb", "C1"): "respond",
        }
        result = lookup_gloss(
            audit, "counter (some disamb)", "verb", "C1",
            "counter", ["verb"], "C1",
        )
        assert result == "respond"

    def test_no_parenthetical_uses_base_word(self):
        audit = {
            ("firm", "adjective", "B2"): "solid|unlikely to change",
            ("firm", "noun", "B2"): "a business or company",
        }
        result = lookup_gloss(
            audit, "firm", "adjective", "B2",
            "firm", ["adjective"], "B2",
        )
        assert result == "solid|unlikely to change"

    def test_multi_pos_joins_with_pipe(self):
        """Multi-POS card (yield|noun, verb|C1) joins individual POS
        glosses with ' | '."""
        audit = {
            ("yield", "noun", "C1"): "output",
            ("yield", "verb", "C1"): "produce|surrender",
        }
        result = lookup_gloss(
            audit, "yield", "noun, verb", "C1",
            "yield", ["noun", "verb"], "C1",
        )
        # The POS-order in the joined result follows all_parts (orig + res).
        assert result is not None
        assert "output" in result
        assert "produce|surrender" in result
        assert " | " in result

    def test_no_match_returns_none(self):
        audit = {
            ("unrelated", "noun", "C1"): "x",
        }
        result = lookup_gloss(
            audit, "completely_different", "verb", "C1",
            "completely_different", ["verb"], "C1",
        )
        assert result is None
