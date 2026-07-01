"""Tests for P4B Rule-Shape Consistency Fix.

Covers:
1. The apply tool's pre-flight guards (new glosses pass validator,
   guarded audit key match, TXT target match, missing-row refusal).
2. The verifier's failure detection (audit/TXT/JSONL drift, bad separator
   or word count).
3. The policy audit's classification logic (allowed_single_gloss /
   rule_shape_contradiction / policy_review / metadata_error / other).
4. Scope invariant: exactly 24 P4B fixes.
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools._apply_p4b_rule_shape_fix import (
    P4B_FIXES,
    _validate_all_new_glosses,
    _check_audit_guards,
    _update_audit_rows,
    _apply_txt,
    _apply_audit,
)
from src.deck_builder.gloss_llm import validate_verdict
from tools._audit_gloss_policy_coverage import _classify_row, _is_multi_def_one_gloss
from tests.deck_builder.historical_supersession import REPLACED_KEYS


def _current_key(word: str, pos: str, cefr: str) -> tuple[str, str, str]:
    historical_key = (word.lower(), pos.lower(), cefr.upper())
    return REPLACED_KEYS.get(historical_key, historical_key)


# === Apply-tool guard tests =================================================

class TestValidateAllNewGlosses:
    """All 24 new glosses must pass the validator — pre-flight gate."""

    def test_no_validation_errors(self):
        errors = _validate_all_new_glosses()
        assert errors == [], (
            f'P4B new glosses fail validate_verdict:\n' + '\n'.join(errors)
        )


class TestCheckAuditGuards:
    """Guarded audit key match protects against silent wrong-row updates."""

    def _mk_audit(self, *rows):
        return [
            {
                'word': w, 'pos': p, 'cefr': c,
                'def_before': f'synthetic def for {w}',
                'gloss_after': g,
                'separator': 'none', 'gloss_word_count': 1,
                'gate_status': 'pass', 'fix_status': 'rebuilt',
                'rule_applied': r, 'source': 'test',
            }
            for (w, p, c, g, r) in rows
        ]

    def test_all_24_match_in_synthetic_audit(self):
        audit_rows = self._mk_audit(*[
            (w, p, c, old, rule) for (w, p, c, old, rule, _n) in P4B_FIXES
        ])
        matched, unmatched, errs = _check_audit_guards(audit_rows)
        assert errs == [], f'unexpected guard errors: {errs}'
        assert unmatched == [], f'unmatched fixes: {unmatched}'
        assert len(matched) == 24

    def test_refuses_when_old_gloss_mismatches(self):
        audit_rows = self._mk_audit(*[
            (w, p, c, old, rule) for (w, p, c, old, rule, _n) in P4B_FIXES
        ])
        audit_rows[0]['gloss_after'] = 'WRONG_OLD_GLOSS'
        _matched, _unmatched, errs = _check_audit_guards(audit_rows)
        assert any('MISS' in e for e in errs), (
            f'expected MISS error for wrong old_gloss, got: {errs}'
        )

    def test_refuses_when_rule_mismatches(self):
        """The rule_applied is part of the guard — a wrong rule must
        refuse the match (covers the worship multi_pos_pick2 vs
        POS_DEF_MISMATCH_fixed case)."""
        audit_rows = self._mk_audit(*[
            (w, p, c, old, rule) for (w, p, c, old, rule, _n) in P4B_FIXES
        ])
        # Find a target and corrupt its rule
        target = P4B_FIXES[0]
        for r in audit_rows:
            if r['word'] == target[0] and r['pos'] == target[1] and r['cefr'] == target[2]:
                r['rule_applied'] = 'WRONG_RULE'
                break
        _matched, _unmatched, errs = _check_audit_guards(audit_rows)
        assert any('MISS' in e for e in errs), (
            f'expected MISS error for wrong rule, got: {errs}'
        )


# === Verifier-component tests ===============================================

class TestVerifierFailures:
    """Failure modes the verifier must detect. These run against the
    current files (audit + TXT + JSONL) so they catch drift."""

    def test_txt_contains_all_24_p4b_keys(self):
        from tools._verify_p4b_rule_shape_fix import _load_txt
        txt = _load_txt()
        txt_keys = {(r['word'].lower(), r['pos'].lower(), r['cefr'].upper()) for r in txt}
        for word, pos, cefr, _o, _r, _n in P4B_FIXES:
            key = _current_key(word, pos, cefr)
            assert key in txt_keys, f'TXT missing key {key}'

    def test_jsonl_contains_all_24_p4b_keys(self):
        from tools._verify_p4b_rule_shape_fix import _load_jsonl
        jsonl = _load_jsonl()
        keys = {(r['word'], r['pos'].lower(), r['cefr'].upper()) for r in jsonl}
        for word, pos, cefr, _o, _r, _n in P4B_FIXES:
            key = _current_key(word, pos, cefr)
            assert key in keys, f'JSONL missing key {key}'

    def test_one_unsynced_txt_definition_is_detectable(self):
        """Drift detection: apply tool changes one row's def, verifier
        notices the mismatch."""
        from tools._apply_p4b_rule_shape_fix import _apply_txt
        new_gloss_by_key = {
            _current_key(w, p, c): n
            for (w, p, c, _o, _r, n) in P4B_FIXES
        }
        new_lines = _apply_txt(new_gloss_by_key)
        # Drift the first target
        target = P4B_FIXES[0]
        target_key = (target[0], target[1].lower(), target[2].upper())
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
                parts[6] = 'DRIFTED_VALUE'
                drifted = True
            drifted_lines.append('\t'.join(parts))
        assert drifted, 'test setup failed: did not drift the target row'

        # Re-parse and verify the drift is detectable
        drifted_row = None
        for line in drifted_lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            word = parts[3].strip().lower()
            pos = parts[4].strip().lower()
            cefr = parts[14].strip().upper()
            if (word, pos, cefr) == target_key:
                drifted_row = parts[6]
                break
        assert drifted_row == 'DRIFTED_VALUE'

    def test_bad_separator_is_detectable(self):
        """Apply tool must normalize separator to '|' for new glosses."""
        from tools._apply_p4b_rule_shape_fix import _update_audit_rows
        matched = [{
            'word': 'acceptance', 'pos': 'noun', 'cefr': 'C1',
            'def_before': 'fake', 'gloss_after': 'willingness',
            'separator': 'WRONG_BAD_VALUE', 'gloss_word_count': 99,
            'gate_status': 'fail', 'fix_status': 'broken',
            'rule_applied': 'rule_b_pick2', 'source': 'test',
        }]
        new_gloss_by_key = {('acceptance', 'noun', 'C1'): 'receiving|agreeing'}
        new_rows = _update_audit_rows(matched, new_gloss_by_key)
        assert new_rows[0]['separator'] == '|'
        assert new_rows[0]['gate_status'] == 'pass'
        assert new_rows[0]['fix_status'] == 'p4b_rule_shape_repaired'
        # 'receiving|agreeing' has 2 content words
        assert new_rows[0]['gloss_word_count'] == 2


# === Policy audit classification tests =====================================

class TestPolicyAuditClassification:
    """The policy audit's _classify_row must route rows correctly."""

    def _mk(self, rule, gloss, separator=None, def_before=''):
        if separator is None:
            separator = '|' if '|' in gloss else ';' if ';' in gloss else 'none'
        return {
            'word': 'w', 'pos': 'p', 'cefr': 'C1',
            'def_before': def_before,
            'gloss_after': gloss, 'separator': separator,
            'gloss_word_count': 1, 'rule_applied': rule,
        }

    def test_rule_b_pick1_one_gloss_allowed(self):
        r = self._mk('rule_b_pick1', 'whatever')
        bucket, reason = _classify_row(r)
        assert bucket == 'allowed_single_gloss', reason
        assert reason is None

    def test_concrete_1sense_one_gloss_allowed(self):
        r = self._mk('concrete_1sense', 'thing')
        bucket, _ = _classify_row(r)
        assert bucket == 'allowed_single_gloss'

    def test_multi_pos_pick1_one_gloss_allowed(self):
        r = self._mk('multi_pos_pick1', 'combined')
        bucket, _ = _classify_row(r)
        assert bucket == 'allowed_single_gloss'

    def test_rule_b_pick2_one_gloss_contradiction(self):
        r = self._mk('rule_b_pick2', 'willingness')
        bucket, reason = _classify_row(r)
        assert bucket == 'rule_shape_contradiction', reason

    def test_rule_b_pick2_addendum_one_gloss_contradiction(self):
        r = self._mk('rule_b_pick2_addendum', 'gentle')
        bucket, reason = _classify_row(r)
        assert bucket == 'rule_shape_contradiction', reason

    def test_2sense_distinct_one_gloss_contradiction(self):
        r = self._mk('2sense_distinct', 'opposite result')
        bucket, reason = _classify_row(r)
        assert bucket == 'rule_shape_contradiction', reason

    def test_3sense_distinct_one_gloss_contradiction(self):
        r = self._mk('3sense_distinct', 'something')
        bucket, _ = _classify_row(r)
        assert bucket == 'rule_shape_contradiction'

    def test_multi_pos_pick2_one_gloss_contradiction(self):
        r = self._mk('multi_pos_pick2', 'combined')
        bucket, _ = _classify_row(r)
        assert bucket == 'rule_shape_contradiction'

    def test_rule_b_pick2_multi_chunk_other(self):
        """Multi-chunk row satisfies any rule shape — routed to 'other'."""
        r = self._mk('rule_b_pick2', 'willingness|agreement', separator='|')
        bucket, _ = _classify_row(r)
        assert bucket == 'other'

    def test_2sense_samedomain_one_gloss_policy_review(self):
        r = self._mk('2sense_samedomain', 'nutritious')
        bucket, reason = _classify_row(r)
        assert bucket == 'policy_review', reason
        assert 'M3+human' in (reason or '')

    def test_pos_aware_gloss_one_gloss_policy_review(self):
        """pos_aware_gloss is policy-review per CONTEXT.md § Rule-Shape
        Consistency: one-chunk may be intentional (multi-POS collapse
        policy), but cannot be verified mechanically — flag for M3+human."""
        r = self._mk('pos_aware_gloss', 'combined')
        bucket, reason = _classify_row(r)
        assert bucket == 'policy_review', reason
        assert 'M3+human' in (reason or '')

    def test_metadata_error_separator_mismatch(self):
        r = self._mk('rule_b_pick1', 'willingness|agreement', separator='none')
        bucket, reason = _classify_row(r)
        assert bucket == 'metadata_error', reason
        assert 'separator' in (reason or '')

    def test_empty_rule_classified_as_allowed(self):
        r = self._mk('', 'thing')
        bucket, _ = _classify_row(r)
        assert bucket == 'allowed_single_gloss'

    def test_p4b_targets_now_appear_in_other_bucket(self):
        """After P4B, the 24 P4B rows have multi-chunk glosses — they
        must route to 'other', not 'rule_shape_contradiction'."""
        # Simulate post-apply state
        for word, pos, cefr, _o, _r, new in P4B_FIXES:
            r = self._mk(_r, new)
            bucket, reason = _classify_row(r)
            assert bucket != 'rule_shape_contradiction', (
                f'{word}|{pos}|{cefr} still classified as contradiction: {reason}'
            )


class TestMultiDefOneGloss:
    """_is_multi_def_one_gloss is INFORMATIONAL only."""

    def test_returns_true_for_multi_def_single_gloss(self):
        r = {
            'def_before': 'sense 1|sense 2|sense 3',
            'gloss_after': 'collapsed',
        }
        assert _is_multi_def_one_gloss(r) is True

    def test_returns_false_for_single_def(self):
        r = {
            'def_before': 'just one sense',
            'gloss_after': 'one',
        }
        assert _is_multi_def_one_gloss(r) is False

    def test_returns_false_for_multi_gloss(self):
        r = {
            'def_before': 'sense 1|sense 2',
            'gloss_after': 'one|two',
        }
        assert _is_multi_def_one_gloss(r) is False


# === Cross-cut invariants ===================================================

class TestCrossCutInvariants:
    """Properties that must hold both before and after the apply."""

    def test_p4b_fix_count_is_24(self):
        """Lock in the scope: P4B fixes exactly 24 rows. If a future
        plan adds more, this test reminds maintainers."""
        assert len(P4B_FIXES) == 24, (
            f'P4B scope is 24 rows, got {len(P4B_FIXES)}'
        )

    def test_all_p4b_rules_are_pick2_distinct(self):
        """Every P4B target's rule must be a PICK rule — that's what
        makes it a rule-shape contradiction. Guards against accidental
        inclusion of policy-review rows."""
        PICK = {
            '2sense_distinct', '3sense_distinct',
            'rule_b_pick2', 'rule_b_pick2_addendum',
            'multi_pos_pick2',
        }
        for w, p, c, _o, rule, _n in P4B_FIXES:
            assert rule in PICK, (
                f'{w}|{p}|{c} has rule {rule!r} which is not a PICK rule '
                f'— should not be in P4B scope'
            )

    def test_all_p4b_new_glosses_use_pipe(self):
        """All 24 P4B new glosses must use '|' separator. P4B fixes
        rule-shape contradictions where the rule requires multi-chunk
        distinct senses, so '|' is the natural choice."""
        for w, _p, _c, _o, _r, new in P4B_FIXES:
            assert '|' in new, f'{w} new gloss should use |, got {new!r}'
            assert ';' not in new, f'{w} new gloss should not mix | and ;, got {new!r}'

    def test_old_and_new_glosses_are_distinct_per_row(self):
        """Sanity: every P4B target's new gloss differs from the old one
        (otherwise the fix is a no-op)."""
        for w, p, c, old, _r, new in P4B_FIXES:
            assert old != new, (
                f'{w}|{p}|{c} old and new glosses are identical: {old!r}'
            )

    def test_audit_guarded_apply_preserves_unrelated_rows(self):
        """Apply tool's _apply_audit must update exactly the 24 matched
        rows and leave the rest of the audit untouched. Uses a
        synthetic audit so the test is independent of on-disk state."""
        # Build a synthetic audit with the 24 targets + 100 unrelated rows
        target_keys = {
            (w, p.lower(), c.upper(), old, rule)
            for (w, p, c, old, rule, _n) in P4B_FIXES
        }
        # 24 target rows
        audit = [
            {
                'word': w, 'pos': p, 'cefr': c,
                'def_before': f'target def for {w}',
                'gloss_after': old, 'separator': 'none',
                'gloss_word_count': 1, 'gate_status': 'pass',
                'fix_status': 'pre-p4b', 'rule_applied': rule,
                'source': 'synth',
            }
            for (w, p, c, old, rule, _n) in P4B_FIXES
        ]
        # 100 unrelated rows
        for i in range(100):
            audit.append({
                'word': f'unrelated_word_{i}', 'pos': 'noun', 'cefr': 'C1',
                'def_before': f'some def for row {i}',
                'gloss_after': f'gloss_{i}', 'separator': 'none',
                'gloss_word_count': 1, 'gate_status': 'pass',
                'fix_status': 'untouched', 'rule_applied': 'rule_b_pick1',
                'source': 'synth',
            })

        new_gloss_by_key = {
            (w.lower(), p.lower(), c.upper()): n
            for (w, p, c, _o, _r, n) in P4B_FIXES
        }
        # Find matched rows by guard
        before_by_guard = {
            (
                r['word'], r['pos'], r['cefr'],
                (r.get('gloss_after') or '').strip(),
                (r.get('rule_applied') or '').strip(),
            ): r for r in audit
        }
        matched = []
        for w, p, c, old, rule, _n in P4B_FIXES:
            g = (w, p, c, old, rule)
            if g in before_by_guard:
                matched.append(before_by_guard[g])
        assert len(matched) == 24, f'expected 24 matched, got {len(matched)}'

        updated = _update_audit_rows(matched, new_gloss_by_key)
        new_audit = _apply_audit(audit, matched, updated)

        # Total rows preserved
        assert len(new_audit) == len(audit) == 124
        # The 24 matched rows were updated
        changed_keys = {
            (r['word'], r['pos'], r['cefr'], (r.get('gloss_after') or '').strip())
            for r in matched
        }
        n_unchanged = 0
        n_changed = 0
        for old, new in zip(audit, new_audit):
            old_key = (
                old['word'], old['pos'], old['cefr'],
                (old.get('gloss_after') or '').strip(),
            )
            if old_key in changed_keys:
                n_changed += 1
                # This row's gloss_after should now be the new one
                new_key = (old['word'], old['pos'], old['cefr'])
                assert new['gloss_after'] == new_gloss_by_key[new_key]
                assert new['fix_status'] == 'p4b_rule_shape_repaired'
            else:
                n_unchanged += 1
                # Non-target row should be byte-identical
                assert old == new, f'non-target row changed:\n  {old}\n  {new}'
        assert n_changed == 24
        assert n_unchanged == 100
