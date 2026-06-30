"""Tests for P4C Policy Review Ledger.

Covers:
1. Apply tool guards (structural validation, missing-key refusal,
   keep_single no-mutation, repair_gloss metadata correctness).
2. Verifier failure modes (drift detection, missing counterpart).
3. Cross-cut invariants (scope lock, repair count, keep count).
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools._apply_p4c_policy_review import (
    _load_ledger,
    _validate_ledger_structure,
    _check_audit_coverage,
    _update_audit_rows,
    _apply_audit,
    _apply_txt,
    LEDGER_PATH,
    AUDIT_PATH,
    TXT_PATH,
)
from tools._verify_p4c_policy_review import _load_audit as _verify_load_audit


# === Apply-tool structural validation =========================================

class TestValidateLedgerStructure:
    """Apply tool's static structural checks on the ledger file."""

    def test_real_ledger_passes(self):
        ledger = _load_ledger()
        errs = _validate_ledger_structure(ledger)
        assert errs == [], f'real ledger should pass validation, got:\n' + '\n'.join(errs)

    def test_keepsingle_with_newgloss_fails(self):
        """A keep_single row with new_gloss set should fail validation."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'pos_aware_gloss', 'def_before': 'x',
            'old_gloss': 'old', 'decision': 'keep_single', 'reason': 'r',
            'p4c_version': 'v', 'new_gloss': 'should-be-None',
        }]
        errs = _validate_ledger_structure(bad)
        assert any('keep_single' in e and 'new_gloss set' in e for e in errs), errs

    def test_repair_with_new_equal_old_fails(self):
        """A repair_gloss with new_gloss == old_gloss is a no-op — fail."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'pos_aware_gloss', 'def_before': 'x',
            'old_gloss': 'same', 'decision': 'repair_gloss', 'reason': 'r',
            'p4c_version': 'v', 'new_gloss': 'same',
        }]
        errs = _validate_ledger_structure(bad)
        assert any('new_gloss == old_gloss' in e for e in errs), errs

    def test_duplicate_guard_fails(self):
        """Two ledger rows with the same (word, pos, cefr, rule, def_before, old_gloss)
        guard should fail validation."""
        e1 = {
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'pos_aware_gloss', 'def_before': 'x',
            'old_gloss': 'a', 'decision': 'keep_single', 'reason': 'r',
            'p4c_version': 'v', 'new_gloss': None,
        }
        e2 = dict(e1)
        bad = [e1, e2]
        errs = _validate_ledger_structure(bad)
        assert any('DUPLICATE ledger guard' in e for e in errs), errs

    def test_unknown_decision_fails(self):
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'pos_aware_gloss', 'def_before': 'x',
            'old_gloss': 'a', 'decision': 'mystery_decision', 'reason': 'r',
            'p4c_version': 'v', 'new_gloss': None,
        }]
        errs = _validate_ledger_structure(bad)
        assert any('unknown decision' in e for e in errs), errs

    def test_missing_field_fails(self):
        """Ledger row missing any required field fails."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            # missing rule_applied, def_before, old_gloss, decision, reason, p4c_version
            'new_gloss': None,
        }]
        errs = _validate_ledger_structure(bad)
        assert any('missing field' in e for e in errs), errs


# === Apply-tool audit coverage ================================================

class TestCheckAuditCoverage:
    """Apply tool's cross-check between ledger and audit.

    NOTE: The apply tool uses a 6-element full guard (including
    old_gloss) for ALL ledger rows. This works on the FIRST apply run
    (audit's gloss_after == old_gloss) but FAILS on re-runs because
    repair rows have already been updated to new_gloss. This is by
    design — apply is a one-shot tool, not idempotent. The verifier
    uses a different matching strategy (5-element guard for repair,
    6-element for keep) for post-apply verification.

    These tests use synthetic audit data to simulate the pre-apply state
    so the apply tool's matching logic can be exercised.
    """

    def test_real_ledger_covers_synthetic_pre_apply_audit(self):
        """Build a synthetic audit where repair rows still have OLD gloss_after
        (pre-apply state), then verify the apply tool matches 64 rows."""
        ledger = _load_ledger()
        # Build synthetic audit from ledger: each row's gloss_after = old_gloss
        # (so it matches the apply tool's 6-element guard).
        audit = []
        for rec in ledger:
            audit.append({
                'word': rec['word'],
                'pos': rec['pos'],
                'cefr': rec['cefr'],
                'rule_applied': rec['rule_applied'],
                'def_before': rec['def_before'],
                'gloss_after': rec['old_gloss'],
            })
        matched, repair_recs, keep_recs, errors = _check_audit_coverage(audit, ledger)
        assert errors == [], f'unexpected errors: {errors}'
        assert len(matched) == 64
        assert len(repair_recs) == 7
        assert len(keep_recs) == 57

    def test_missing_audit_row_fails(self):
        """If a ledger key has no matching audit row, abort."""
        ledger = [{
            'word': 'nonexistent', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'pos_aware_gloss', 'def_before': 'x',
            'old_gloss': 'a', 'decision': 'keep_single', 'reason': 'r',
            'p4c_version': 'v', 'new_gloss': None,
        }]
        audit: list[dict] = []
        matched, _rr, _kr, errors = _check_audit_coverage(audit, ledger)
        assert any('NO AUDIT MATCH' in e for e in errors), errors
        assert len(matched) == 0

    def test_repair_and_keep_partitioned(self):
        """Matched rows are correctly partitioned into repair_records vs
        keep_records by ledger decision."""
        ledger = _load_ledger()
        # Build synthetic pre-apply audit
        audit = []
        for rec in ledger:
            audit.append({
                'word': rec['word'],
                'pos': rec['pos'],
                'cefr': rec['cefr'],
                'rule_applied': rec['rule_applied'],
                'def_before': rec['def_before'],
                'gloss_after': rec['old_gloss'],
            })
        _matched, repair_recs, keep_recs, errors = _check_audit_coverage(audit, ledger)
        assert errors == []
        assert len(repair_recs) == 7
        for r in repair_recs:
            assert r['decision'] == 'repair_gloss', r
        for r in keep_recs:
            assert r['decision'] == 'keep_single', r


# === Apply-tool repair metadata ===============================================

class TestUpdateAuditRows:
    """repair_gloss audit row updates: separator, word_count, fix_status."""

    def test_repair_normalizes_metadata(self):
        """A repair entry normalizes separator to '|' (or ';' if used),
        recomputes word_count, and sets fix_status."""
        # An audit row that matches a repair entry
        audit_row = {
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'def_before': 'x|y', 'gloss_after': 'old',
            'rule_applied': 'pos_aware_gloss', 'separator': 'WRONG',
            'gloss_word_count': 99, 'gate_status': 'fail', 'fix_status': 'broken',
        }
        ledger = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'pos_aware_gloss', 'def_before': 'x|y',
            'old_gloss': 'old', 'decision': 'repair_gloss',
            'new_gloss': 'new|other',
            'p4c_version': 'v', 'reason': 'r',
        }]
        new_rows = _update_audit_rows([audit_row], ledger)
        assert len(new_rows) == 1
        new = new_rows[0]
        assert new['separator'] == '|'
        assert new['gloss_word_count'] == 2  # 'new' (1) + 'other' (1) = 2
        assert new['gate_status'] == 'pass'
        assert new['fix_status'] == 'p4c_policy_review_repaired'
        assert new['gloss_after'] == 'new|other'


# === Apply-tool audit mutation ===============================================

class TestApplyAudit:
    """`_apply_audit` must update exactly the matched ORIGINAL rows and
    leave unrelated rows untouched."""

    def test_keepsingle_does_not_mutate_audit(self):
        """keep_single rows should NOT appear in the matched_repair list."""
        ledger = _load_ledger()
        # Build synthetic pre-apply audit
        audit = []
        for rec in ledger:
            audit.append({
                'word': rec['word'],
                'pos': rec['pos'],
                'cefr': rec['cefr'],
                'rule_applied': rec['rule_applied'],
                'def_before': rec['def_before'],
                'gloss_after': rec['old_gloss'],
            })
        _matched, repair_recs, keep_recs, errors = _check_audit_coverage(audit, ledger)
        assert errors == []
        repair_keys = {(r['word'], r['pos'], r['cefr']) for r in repair_recs}
        keep_keys = {(r['word'], r['pos'], r['cefr']) for r in keep_recs}
        assert not (repair_keys & keep_keys), 'repair and keep sets must be disjoint'

    def test_apply_audit_replaces_only_repair_rows(self):
        """_apply_audit(audit, repair_originals, replacements) replaces
        only repair_originals, leaves other rows alone."""
        # Simulate a 3-row audit: 1 repair, 2 untouched
        audit = [
            {'word': 'a', 'pos': 'noun', 'cefr': 'C1',
             'rule_applied': 'r1', 'def_before': 'd1', 'gloss_after': 'ga1'},
            {'word': 'b', 'pos': 'noun', 'cefr': 'C1',
             'rule_applied': 'r2', 'def_before': 'd2', 'gloss_after': 'gb1'},
            {'word': 'c', 'pos': 'noun', 'cefr': 'C1',
             'rule_applied': 'r3', 'def_before': 'd3', 'gloss_after': 'gc1'},
        ]
        originals = [audit[1]]  # only 'b'
        replacement = [dict(audit[1], gloss_after='NEW')]
        out = _apply_audit(audit, originals, replacement)
        assert len(out) == 3
        assert out[0]['gloss_after'] == 'ga1'  # untouched
        assert out[1]['gloss_after'] == 'NEW'  # replaced
        assert out[2]['gloss_after'] == 'gc1'  # untouched


# === Apply-tool TXT mutation =================================================

class TestApplyTxt:
    """`_apply_txt` only changes the def cell (col 6) for repair keys."""

    def test_apply_txt_only_changes_repair_keys(self, tmp_path):
        """For a small TXT fixture with 2 known words, only the key in
        new_gloss_by_key gets its def cell updated; other rows stay."""
        # Create a minimal TXT (17 tab-separated cols; row 0 is NOT a # comment)
        # Cols: 3=word, 4=pos, 6=def, 14=cefr
        row_target = ['z1', 'a', 'b', 'curious', 'adjective', 'f', 'OLD', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'B2', 'o', 'p']
        row_other = ['z2', 'a', 'b', 'happy', 'adjective', 'f', 'HAPPY_DEF', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'B2', 'o', 'p']
        txt_path = tmp_path / 'test.txt'
        txt_path.write_text('\t'.join(row_target) + '\n' + '\t'.join(row_other) + '\n', encoding='utf-8')

        # Patch TXT_PATH
        import tools._apply_p4c_policy_review as m
        original_path = m.TXT_PATH
        m.TXT_PATH = txt_path
        try:
            new_gloss = {('curious', 'adjective', 'B2'): 'NEW_DEF'}
            lines = _apply_txt(new_gloss)
            assert lines is not None
            new_content = '\n'.join(lines)
            assert 'NEW_DEF' in new_content
            assert 'HAPPY_DEF' in new_content  # untouched
            assert 'OLD' not in new_content  # replaced
        finally:
            m.TXT_PATH = original_path


# === Cross-cut invariants ===================================================

class TestCrossCutInvariants:
    """Properties that must hold for any applied P4C ledger."""

    def test_ledger_count_is_64(self):
        """Lock in scope: P4C has exactly 64 entries. Future passes use
        a separate file (e.g. P4C v2 → p4c_v2.jsonl) and don't change this."""
        ledger = _load_ledger()
        assert len(ledger) == 64, f'P4C scope is 64, got {len(ledger)}'

    def test_repair_count_is_7(self):
        ledger = _load_ledger()
        n_repair = sum(1 for r in ledger if r.get('decision') == 'repair_gloss')
        assert n_repair == 7, f'expected 7 repair_gloss, got {n_repair}'

    def test_keep_count_is_57(self):
        ledger = _load_ledger()
        n_keep = sum(1 for r in ledger if r.get('decision') == 'keep_single')
        assert n_keep == 57, f'expected 57 keep_single, got {n_keep}'

    def test_all_repair_glosses_use_pipe(self):
        """P4C repairs are all distinct-sense → pipe."""
        ledger = _load_ledger()
        for rec in ledger:
            if rec.get('decision') == 'repair_gloss':
                new = rec.get('new_gloss', '')
                assert '|' in new, (
                    f'{rec["word"]} new_gloss should use | separator, got {new!r}'
                )

    def test_audit_gloss_after_matches_ledger_newgloss_for_repair(self):
        """For every repair_gloss ledger entry, the audit row's
        gloss_after == ledger's new_gloss (post-apply sync)."""
        ledger = _load_ledger()
        audit = _verify_load_audit()
        # Index audit by (word, pos, cefr, rule, def_before) — repair rows
        # already have new gloss_after so we use the 5-element guard.
        audit_by_pre_repair_guard: dict[tuple, dict] = {}
        for r in audit:
            g = (
                r['word'].strip().lower(),
                r['pos'].strip().lower(),
                r['cefr'].strip().upper(),
                (r.get('rule_applied') or '').strip(),
                (r.get('def_before') or '').strip(),
            )
            # Keep the first row (or any — for repair rows, audit has only 1
            # because the apply kept original rows for keep entries)
            audit_by_pre_repair_guard.setdefault(g, r)
        for rec in ledger:
            if rec.get('decision') != 'repair_gloss':
                continue
            g = (
                rec['word'].strip().lower(),
                rec['pos'].strip().lower(),
                rec['cefr'].strip().upper(),
                (rec.get('rule_applied') or '').strip(),
                (rec.get('def_before') or '').strip(),
            )
            audit_row = audit_by_pre_repair_guard.get(g)
            assert audit_row is not None, f'no audit row for repair {g}'
            if audit_row.get('fix_status') == 'gloss_review_log_20260630':
                continue
            assert audit_row['gloss_after'] == rec['new_gloss'], (
                f'{g!r} audit gloss_after={audit_row["gloss_after"]!r} '
                f'≠ ledger new_gloss={rec["new_gloss"]!r}'
            )
            assert audit_row['fix_status'] == 'p4c_policy_review_repaired', g

    def test_audit_unchanged_for_keepsingle_post_apply(self):
        """Post-apply, every keep_single ledger row's audit row has the
        same `gloss_after` as the ledger's `old_gloss` — UNLESS the row
        was later superseded by P5/P5B (drift tolerated via fix_status).

        After P5B manual review pass: 30 keep_single rows were superseded
        by P5/P5B repair_gloss verdicts. Their audit gloss_after changed,
        but `fix_status` is `p5b_manual_review_repaired` (or p5_*), so
        the drift is intentional, not a regression.
        """
        ledger = _load_ledger()
        audit = _verify_load_audit()
        audit_by_full_guard: dict[tuple, dict] = {}
        for r in audit:
            g = (
                r['word'].strip().lower(),
                r['pos'].strip().lower(),
                r['cefr'].strip().upper(),
                (r.get('rule_applied') or '').strip(),
                (r.get('def_before') or '').strip(),
                (r.get('gloss_after') or '').strip(),
            )
            audit_by_full_guard[g] = r
        # Audit by (word, pos, cefr) for drift-tolerance lookup.
        audit_by_key: dict[tuple, dict] = {}
        for r in audit:
            k = (
                r['word'].strip().lower(),
                r['pos'].strip().lower(),
                r['cefr'].strip().upper(),
            )
            audit_by_key.setdefault(k, []).append(r)
        drift_superseded_keys = {
            'p5_precision_phrase_repaired',
            'p5b_manual_review_repaired',
            'p5c_loop_guard_repaired',
            'p5d_manual_review_repaired',
            'p6_multisense_harddrop_repaired',
            'p7_redundant_sense_trimmed',
            'gloss_review_log_20260630',
        }
        for rec in ledger:
            if rec.get('decision') != 'keep_single':
                continue
            g = (
                rec['word'].strip().lower(),
                rec['pos'].strip().lower(),
                rec['cefr'].strip().upper(),
                (rec.get('rule_applied') or '').strip(),
                (rec.get('def_before') or '').strip(),
                (rec.get('old_gloss') or '').strip(),
            )
            if g in audit_by_full_guard:
                # Exact match: audit still has old_gloss, no drift.
                continue
            # No exact match: check if a P5/P5B/P5C/P5D/P6/P7 repair verdict
            # superseded this keep_single. Tolerated.
            k = (
                rec['word'].strip().lower(),
                rec['pos'].strip().lower(),
                rec['cefr'].strip().upper(),
            )
            candidates = audit_by_key.get(k, [])
            assert candidates, f'keep_single row {g!r} missing from audit entirely'
            audit_row = candidates[0]
            fix_status = (audit_row.get('fix_status') or '').strip()
            assert fix_status in drift_superseded_keys, (
                f'keep_single audit drift without P5/P5B/P5C/P5D/P6/P7 supersede: '
                f'{g!r} fix_status={fix_status!r}'
            )