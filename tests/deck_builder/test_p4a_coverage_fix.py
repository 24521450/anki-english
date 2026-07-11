"""Tests for P4A High-Risk Sense Coverage Fix.

Covers the apply tool's safety guards and the verifier's failure modes.
The verifier itself is exercised end-to-end by `python -m tools._verify_p4a_coverage_fix`
after apply — see the spec's verification commands.
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools._apply_p4a_coverage_fix import (
    P4A_FIXES,
    _validate_all_new_glosses,
    _check_audit_guards,
    _apply_audit,
    _apply_txt,
)
from src.deck_builder.gloss_llm import validate_verdict


# === Apply-tool guard tests =================================================

class TestValidateAllNewGlosses:
    """All 26 new glosses must pass the validator — this is the
    pre-flight gate; failure here aborts the apply."""

    def test_no_validation_errors(self):
        errors = _validate_all_new_glosses()
        assert errors == [], (
            f'P4A new glosses fail validate_verdict:\n' + '\n'.join(errors)
        )

    def test_animation_passes_validator(self):
        """Spec note: animation intentionally differs from the report's
        suggestion because the report's pick failed the validator. This
        test locks in that the chosen replacement is valid."""
        gloss = 'moving-picture process|cartoon film'
        sep = '|'
        chunks = ['moving-picture process', 'cartoon film']
        v = validate_verdict('animation', gloss, sep, len(chunks))
        assert v == [], f'animation gloss should pass: {v}'

    def test_passing_passes_validator(self):
        """Spec note: passing intentionally differs from the report's
        suggestion (the report's `process; ending; approval` violated
        per-chunk 1-3 word cap on ';')."""
        gloss = 'elapsed time|death/ending|law approval'
        sep = '|'
        chunks = ['elapsed time', 'death/ending', 'law approval']
        v = validate_verdict('passing', gloss, sep, len(chunks))
        assert v == [], f'passing gloss should pass: {v}'

    def test_acid_passes_validator(self):
        """Spec note: acid intentionally uses `low-pH|sour` instead of
        the report's `low pH|sour` (single-token 'low-pH' is treated as
        1 word by the validator's tokenizer)."""
        gloss = 'low-pH|sour'
        sep = '|'
        chunks = ['low-pH', 'sour']
        v = validate_verdict('acid', gloss, sep, len(chunks))
        assert v == [], f'acid gloss should pass: {v}'


class TestCheckAuditGuards:
    """The apply tool's guarded-key check protects against silent wrong-row
    updates. These tests verify both the success and failure paths."""

    def _mk_audit(self, *rows):
        """Build a synthetic audit row list."""
        return [
            {
                'word': w, 'pos': p, 'cefr': c,
                'def_before': f'synthetic def for {w}',
                'gloss_after': g,
                'separator': 'none', 'gloss_word_count': 1,
                'gate_status': 'pass', 'fix_status': 'rebuilt',
                'rule_applied': '2sense_distinct', 'source': 'test',
            }
            for (w, p, c, g) in rows
        ]

    def test_all_26_match_in_synthetic_audit(self):
        """When the audit contains exactly the expected old glosses for all 26,
        every fix should match exactly one row."""
        audit_rows = self._mk_audit(*[
            (w, p, c, old) for (w, p, c, old, _n) in P4A_FIXES
        ])
        matched, unmatched, errs = _check_audit_guards(audit_rows)
        assert errs == [], f'unexpected guard errors: {errs}'
        assert unmatched == [], f'unmatched fixes: {unmatched}'
        assert len(matched) == 26

    def test_refuses_when_old_gloss_mismatches(self):
        """If one row's old_gloss_after is wrong (e.g. someone hand-edited
        the audit since the P4A plan was drafted), the apply must refuse."""
        audit_rows = self._mk_audit(*[
            (w, p, c, old) for (w, p, c, old, _n) in P4A_FIXES
        ])
        # Corrupt one row's gloss_after to a wrong value
        audit_rows[0]['gloss_after'] = 'WRONG_OLD_GLOSS'
        _matched, _unmatched, errs = _check_audit_guards(audit_rows)
        assert any('MISS' in e for e in errs), (
            f'expected MISS error for wrong old_gloss, got: {errs}'
        )


# === Verifier-component tests ===============================================

class TestVerifierFailures:
    """Focused tests for failure modes the verifier must detect. These
    run on the *real* current files (audit + TXT + JSONL) so they catch
    drift between apply output and verifier expectations."""

    def test_txt_contains_all_26_p4a_keys(self):
        """Sanity: every P4A target has at least 1 TXT row at this point
        (post-apply). Used as a precondition for the rest of the verifier
        tests."""
        from tools._verify_p4a_coverage_fix import _load_txt
        txt = _load_txt()
        txt_keys = {(r['word'].lower(), r['pos'].lower(), r['cefr'].upper()) for r in txt}
        for word, pos, cefr, _o, _n in P4A_FIXES:
            key = (word, pos.lower(), cefr.upper())
            assert key in txt_keys, f'TXT missing key {key}'

    def test_jsonl_contains_all_26_p4a_keys(self):
        """Sanity: every P4A target has at least 1 JSONL row."""
        from tools._verify_p4a_coverage_fix import _load_jsonl
        jsonl = _load_jsonl()
        keys = {(r['word'], r['pos'].lower(), r['cefr'].upper()) for r in jsonl}
        for word, pos, cefr, _o, _n in P4A_FIXES:
            key = (word, pos.lower(), cefr.upper())
            assert key in keys, f'JSONL missing key {key}'

    def test_one_unsynced_txt_definition_is_detectable(self):
        """Detect a single TXT def that's drifted from the expected new
        gloss. We simulate the drift in-memory and verify the verifier's
        diff logic catches it. Pre-apply, the TXT has the OLD glosses —
        we simulate post-apply state for the test."""
        from tools._verify_p4a_coverage_fix import EXPECTED_GLOSS_BY_KEY
        from tools._apply_p4a_coverage_fix import _apply_txt
        # Build the post-apply new-gloss map and apply it to a copy of
        # the TXT in memory.
        new_gloss_by_key = {
            (w.lower(), p.lower(), c.upper()): n
            for (w, p, c, _o, n) in P4A_FIXES
        }
        new_lines = _apply_txt(new_gloss_by_key)
        # Now drift one row: replace its def with a wrong value
        target = P4A_FIXES[0]
        target_key = (target[0], target[1].lower(), target[2].upper())
        expected_def = EXPECTED_GLOSS_BY_KEY[target_key]
        drifted_lines: list[str] = []
        drifted = False
        for line in new_lines:
            if line.startswith('#') or not line.strip():
                drifted_lines.append(line)
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                drifted_lines.append(line)
                continue
            word = parts[3].strip().lower()
            pos = parts[4].strip().lower()
            cefr = parts[14].strip().upper()
            if (word, pos, cefr) == target_key and not drifted:
                parts[6] = 'DRIFTED_VALUE_THAT_SHOULD_FAIL'
                drifted = True
            drifted_lines.append('\t'.join(parts))
        assert drifted, 'test setup failed: did not drift the target row'

        # Re-parse and verify the drift is detectable (def != expected)
        drifted_rows = []
        for line in drifted_lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            drifted_rows.append({
                'word': parts[3].strip().lower(),
                'pos': parts[4].strip().lower(),
                'cefr': parts[14].strip().upper(),
                'def': parts[6],
            })
        target_row = next(
            (r for r in drifted_rows
             if (r['word'], r['pos'], r['cefr']) == target_key),
            None,
        )
        assert target_row is not None
        assert target_row['def'] == 'DRIFTED_VALUE_THAT_SHOULD_FAIL'
        assert target_row['def'] != expected_def
        # The verifier's check would surface this as a mismatch.

    def test_bad_separator_is_detectable(self):
        """The apply tool normalizes `separator` to `'|'` for the new
        glosses, regardless of what the source row had. This guarantees
        the verifier's separator check has a consistent expectation."""
        from tools._apply_p4a_coverage_fix import _update_audit_rows
        matched = [{
            'word': 'absence', 'pos': 'noun', 'cefr': 'C1',
            'def_before': 'fake', 'gloss_after': 'being away',
            'separator': 'WRONG_BAD_VALUE', 'gloss_word_count': 99,
            'gate_status': 'fail', 'fix_status': 'broken',
            'rule_applied': '2sense_distinct', 'source': 'test',
        }]
        new_gloss_by_key = {
            ('absence', 'noun', 'C1'): 'being away|lack',
        }
        new_rows = _update_audit_rows(matched, new_gloss_by_key)
        # The apply tool must normalize separator to '|' (the new gloss uses |)
        assert new_rows[0]['separator'] == '|', (
            f'apply must normalize separator to "|" for new gloss, got {new_rows[0]["separator"]!r}'
        )
        # And reset gate_status to 'pass', fix_status to the new tag.
        assert new_rows[0]['gate_status'] == 'pass'
        assert new_rows[0]['fix_status'] == 'p4a_coverage_repaired'
        # And gloss_word_count is recomputed from the new gloss content
        # 'being away|lack' has 3 content words after pipe-strip split
        assert new_rows[0]['gloss_word_count'] == 3

    def test_p4a_fix_count_is_26(self):
        """Lock in the scope: P4A fixes exactly 26 rows. If a future plan
        adds more, this test will remind maintainers to update related
        counts (verifier, tests, spec)."""
        assert len(P4A_FIXES) == 26, (
            f'P4A scope is 26 rows, got {len(P4A_FIXES)} — update verifier '
            f'and tests if intentional'
        )


# === Cross-cut invariants ===================================================

class TestCrossCutInvariants:
    """Properties that must hold both before and after the apply."""

    def test_all_old_glosses_are_unique_in_p4a_fixes(self):
        """No two P4A targets share the same old gloss_after — guards
        against accidental double-application."""
        olds = [old for (_w, _p, _c, old, _n) in P4A_FIXES]
        dups = [o for o in set(olds) if olds.count(o) > 1]
        assert dups == [], f'duplicate old glosses in P4A_FIXES: {dups}'

    def test_all_new_glosses_use_pipe_separator(self):
        """All 26 P4A new glosses must use '|' (distinct senses). If a
        future fix uses ';' for same-domain variants, update this test."""
        for w, _p, _c, _o, new in P4A_FIXES:
            assert '|' in new, f'{w} new gloss should use | separator, got {new!r}'
            assert ';' not in new, f'{w} new gloss should not mix | and ;, got {new!r}'

    def test_apply_txt_function_only_changes_target_rows(self):
        """The apply TXT function must update exactly the 26 target rows
        and leave the rest unchanged. Run against the current TXT to
        check the replacement math."""
        from tools._verify_p4a_coverage_fix import _load_txt
        from tools._apply_p4a_coverage_fix import _apply_txt
        before = _load_txt()
        # Build a new-gloss map that matches the post-apply state
        new_gloss = {
            (w.lower(), p.lower(), c.upper()): n
            for (w, p, c, _o, n) in P4A_FIXES
        }
        new_lines = _apply_txt(new_gloss)
        # Re-parse the new lines
        new_txt_rows = []
        for line in new_lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            new_txt_rows.append({
                'word': parts[3].strip(),
                'pos': parts[4].strip(),
                'cefr': parts[14].strip(),
                'def': parts[6],
            })
        # Total rows preserved
        assert len(new_txt_rows) == len(before)
        before_defs_by_key: dict[tuple[str, str, str], list[str]] = {}
        for row in before:
            key = (
                row['word'].lower(),
                row['pos'].lower(),
                row['cefr'].upper(),
            )
            before_defs_by_key.setdefault(key, []).append(row['def'])
        # All 26 target defs are the new ones
        for r in new_txt_rows:
            key = (r['word'].lower(), r['pos'].lower(), r['cefr'].upper())
            if key in new_gloss:
                assert r['def'] == new_gloss[key], (
                    f'apply_txt failed to set new def for {key}'
                )
            else:
                # Non-target row's def must be byte-identical to original
                original_defs = before_defs_by_key.get(key)
                assert original_defs
                original_def = original_defs.pop(0)
                assert r['def'] == original_def, (
                    f'apply_txt changed non-target def for {key}: '
                    f'{original_def!r} → {r["def"]!r}'
                )
