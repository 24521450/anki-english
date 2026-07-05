"""Tests for P5 Precision Phrase Ledger.

Covers:
1. Apply tool guards (structural validation, missing-key refusal,
   keep-candidate/review-candidate no-mutation, repair metadata correctness).
2. Verifier failure modes (drift detection, audit mismatch).
3. Cross-cut invariants (scope lock, seed repair count, decision partitioning).
4. precision_phrase rule classification (audit policy tool allows it).
"""
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from tools.archive.data_migrations._apply_p5_precision_phrase import (
    _load_ledger,
    _validate_ledger_structure,
    _check_audit_coverage,
    _update_audit_rows,
    _apply_audit,
    _apply_txt,
    LEDGER_PATH,
)
from tools.archive.data_migrations._verify_p5_precision_phrase import (
    _load_audit as _verify_load_audit,
)

pytestmark = [
    pytest.mark.historical,
    pytest.mark.skipif(
        not LEDGER_PATH.exists(),
        reason=f'{LEDGER_PATH.name} retired from tracked data',
    ),
]


# === Apply-tool structural validation =========================================

class TestValidateLedgerStructure:
    """Apply tool's static structural checks on the ledger file."""

    def test_real_ledger_passes(self):
        ledger = _load_ledger()
        errs = _validate_ledger_structure(ledger)
        assert errs == [], 'real ledger should pass validation:\n' + '\n'.join(errs)

    def test_repair_with_new_equal_old_fails(self):
        """A repair_gloss with new_gloss == old_gloss is a no-op — fail."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'same', 'decision': 'repair_gloss',
            'reason': 'r', 'risk_type': 'contrast_pair',
            'candidate_gloss': 'same', 'p5_version': 'v',
            'new_gloss': 'same', 'rule_after': 'precision_phrase',
            'separator': 'none', 'gloss_word_count': 1,
        }]
        errs = _validate_ledger_structure(bad)
        assert any('new_gloss == old_gloss' in e for e in errs), errs

    def test_repair_with_empty_rule_after_fails(self):
        """A repair_gloss without rule_after fails (apply needs to know
        what rule to write to the audit row post-repair)."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'old', 'decision': 'repair_gloss',
            'reason': 'r', 'risk_type': 'contrast_pair',
            'candidate_gloss': 'phrase here', 'p5_version': 'v',
            'new_gloss': 'phrase here', 'rule_after': '',
            'separator': 'none', 'gloss_word_count': 2,
        }]
        errs = _validate_ledger_structure(bad)
        assert any('repair_gloss but rule_after empty' in e for e in errs), errs

    def test_review_candidate_with_newgloss_fails(self):
        """A review_candidate row with new_gloss set is a fail
        (review_candidate should NOT mutate anything)."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'old', 'decision': 'review_candidate',
            'reason': 'r', 'risk_type': 'overgeneralized_synonym',
            'candidate_gloss': '', 'p5_version': 'v',
            'new_gloss': 'should-be-None', 'rule_after': None,
            'separator': 'none', 'gloss_word_count': 1,
        }]
        errs = _validate_ledger_structure(bad)
        assert any('review_candidate but new_gloss set' in e for e in errs), errs

    def test_review_candidate_with_rule_after_fails(self):
        """review_candidate should have rule_after=None."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'old', 'decision': 'review_candidate',
            'reason': 'r', 'risk_type': 'overgeneralized_synonym',
            'candidate_gloss': '', 'p5_version': 'v',
            'new_gloss': None, 'rule_after': 'precision_phrase',
            'separator': 'none', 'gloss_word_count': 1,
        }]
        errs = _validate_ledger_structure(bad)
        assert any("decision='review_candidate' but rule_after" in e for e in errs), errs

    def test_keep_current_with_rule_after_fails(self):
        """keep_current should have rule_after=None."""
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'old', 'decision': 'keep_current',
            'reason': 'r', 'risk_type': 'overgeneralized_synonym',
            'candidate_gloss': '', 'p5_version': 'v',
            'new_gloss': None, 'rule_after': 'precision_phrase',
            'separator': 'none', 'gloss_word_count': 1,
        }]
        errs = _validate_ledger_structure(bad)
        assert any("decision='keep_current' but rule_after" in e for e in errs), errs

    def test_unknown_decision_fails(self):
        bad = [{
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'old', 'decision': 'mystery',
            'reason': 'r', 'risk_type': 'contrast_pair',
            'candidate_gloss': '', 'p5_version': 'v',
            'new_gloss': None, 'rule_after': None,
            'separator': 'none', 'gloss_word_count': 1,
        }]
        errs = _validate_ledger_structure(bad)
        assert any('unknown decision' in e for e in errs), errs

    def test_duplicate_guard_fails(self):
        e1 = {
            'word': 'w', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'a', 'decision': 'keep_current',
            'reason': 'r', 'risk_type': 'overgeneralized_synonym',
            'candidate_gloss': '', 'p5_version': 'v',
            'new_gloss': None, 'rule_after': None,
            'separator': 'none', 'gloss_word_count': 1,
        }
        bad = [e1, dict(e1)]
        errs = _validate_ledger_structure(bad)
        assert any('DUPLICATE ledger guard' in e for e in errs), errs


# === Apply-tool audit coverage ================================================

class TestCheckAuditCoverage:
    """Apply tool's cross-check between ledger and audit (synthetic
    pre-apply audit, since apply is one-shot and changes audit state)."""

    def _build_pre_apply_audit(self, ledger: list[dict]) -> list[dict]:
        """Synthetic pre-apply audit: each ledger row → audit row with
        gloss_after = old_gloss (pre-repair state)."""
        return [
            {
                'word': rec['word'],
                'pos': rec['pos'],
                'cefr': rec['cefr'],
                'rule_applied': rec['rule_applied'],
                'def_before': rec['def_before'],
                'gloss_after': rec['old_gloss'],
            }
            for rec in ledger
            if rec.get('decision') == 'repair_gloss'
        ]

    def test_real_ledger_covers_real_audit(self):
        """All repair rows match a synthetic pre-apply audit row.

        After P5D: 346 repair rows match (2 seed + 344 P5D v2 manual).
        Keep count = 644 (was 988 review_candidate before P5B flipped them,
        then P5D flipped 9 keep -> repair).
        """
        ledger = _load_ledger()
        audit = self._build_pre_apply_audit(ledger)
        matched, repair_recs, keep_recs, errors = _check_audit_coverage(audit, ledger)
        assert errors == [], f'unexpected errors: {errors}'
        assert len(matched) == 346
        assert len(repair_recs) == 346
        # 644 keep_current -> keep_recs = 644
        assert len(keep_recs) == 644

    def test_missing_repair_audit_row_fails(self):
        """If a repair key has no matching audit row, abort."""
        ledger = [{
            'word': 'nonexistent', 'pos': 'noun', 'cefr': 'C1',
            'rule_applied': 'concrete_1sense', 'def_before': 'x',
            'old_gloss': 'a', 'decision': 'repair_gloss',
            'reason': 'r', 'risk_type': 'contrast_pair',
            'candidate_gloss': 'phrase here', 'p5_version': 'v',
            'new_gloss': 'phrase here', 'rule_after': 'precision_phrase',
            'separator': 'none', 'gloss_word_count': 2,
        }]
        audit: list[dict] = []
        _matched, repair_recs, keep_recs, errors = _check_audit_coverage(audit, ledger)
        assert any('NO AUDIT MATCH' in e for e in errors), errors
        assert len(repair_recs) == 0


# === Apply-tool repair metadata ===============================================

class TestUpdateAuditRows:
    """repair_gloss audit row updates: gloss_after, rule_after, fix_status."""

    def test_repair_writes_new_gloss_and_rule_after(self):
        """A repair entry updates gloss_after to new_gloss, rule_applied
        to rule_after, separator/word_count derived from new_gloss."""
        audit_row = {
            'word': 'mediate', 'pos': 'verb', 'cefr': 'C2',
            'rule_applied': 'concrete_1sense',
            'def_before': 'to try to end a situation...',
            'gloss_after': 'arbitrate',
        }
        ledger = [{
            'word': 'mediate', 'pos': 'verb', 'cefr': 'C2',
            'rule_applied': 'concrete_1sense',
            'def_before': 'to try to end a situation...',
            'old_gloss': 'arbitrate', 'decision': 'repair_gloss',
            'reason': 'r', 'risk_type': 'contrast_pair',
            'candidate_gloss': 'help resolve a dispute', 'p5_version': 'v',
            'new_gloss': 'help resolve a dispute',
            'rule_after': 'precision_phrase',
            'separator': 'none', 'gloss_word_count': 4,
        }]
        new_rows = _update_audit_rows([audit_row], ledger)
        assert len(new_rows) == 1
        new = new_rows[0]
        assert new['gloss_after'] == 'help resolve a dispute'
        assert new['rule_applied'] == 'precision_phrase'
        assert new['separator'] == 'none'
        assert new['gloss_word_count'] == 4  # 4 words
        assert new['gate_status'] == 'pass'
        assert new['fix_status'] == 'p5_precision_phrase_repaired'


# === Apply-tool audit mutation ===============================================

class TestApplyAudit:
    """`_apply_audit` must update only repair rows, not other audit rows."""

    def test_apply_audit_replaces_only_repair_rows(self):
        """_apply_audit(audit, repair_originals, replacements) replaces
        only repair_originals, leaves other rows alone."""
        audit = [
            {'word': 'a', 'pos': 'noun', 'cefr': 'C1',
             'rule_applied': 'r1', 'def_before': 'd1', 'gloss_after': 'ga1'},
            {'word': 'b', 'pos': 'noun', 'cefr': 'C1',
             'rule_applied': 'r2', 'def_before': 'd2', 'gloss_after': 'gb1'},
            {'word': 'c', 'pos': 'noun', 'cefr': 'C1',
             'rule_applied': 'r3', 'def_before': 'd3', 'gloss_after': 'gc1'},
        ]
        originals = [audit[1]]  # only 'b'
        replacement = [dict(audit[1], gloss_after='NEW', rule_applied='precision_phrase')]
        out = _apply_audit(audit, originals, replacement)
        assert len(out) == 3
        assert out[0]['gloss_after'] == 'ga1'  # untouched
        assert out[1]['gloss_after'] == 'NEW'  # replaced
        assert out[2]['gloss_after'] == 'gc1'  # untouched


# === Apply-tool TXT mutation =================================================

class TestApplyTxt:
    """`_apply_txt` updates TXT def cells for keys present; skips missing
    keys (deferred reconciliation)."""

    def test_apply_txt_only_changes_present_keys(self, tmp_path):
        """For a small TXT fixture, only the key in new_gloss_by_key gets
        its def cell updated; other rows stay. Missing keys are skipped."""
        txt_path = tmp_path / 'test.txt'
        row_target = ['z1', 'a', 'b', 'mediate', 'verb', 'f', 'arbitrate',
                      'g', 'h', 'i', 'j', 'k', 'l', 'm', 'C2', 'o', 'p']
        row_other = ['z2', 'a', 'b', 'happy', 'verb', 'f', 'HAPPY_DEF',
                     'g', 'h', 'i', 'j', 'k', 'l', 'm', 'C2', 'o', 'p']
        txt_path.write_text(
            '\t'.join(row_target) + '\n' + '\t'.join(row_other) + '\n',
            encoding='utf-8',
        )
        import tools.archive.data_migrations._apply_p5_precision_phrase as m
        original_path = m.TXT_PATH
        m.TXT_PATH = txt_path
        try:
            new_gloss = {
                ('mediate', 'verb', 'C2'): 'help resolve a dispute',
                # solo|noun|C1 has no matching TXT row → skipped
                ('solo', 'noun', 'C1'): 'single-performer music',
            }
            lines, skipped = _apply_txt(new_gloss)
            assert ('solo', 'noun', 'C1') in skipped
            new_content = '\n'.join(lines)
            assert 'help resolve a dispute' in new_content
            assert 'HAPPY_DEF' in new_content  # untouched
            assert 'arbitrate' not in new_content  # replaced
        finally:
            m.TXT_PATH = original_path


# === Cross-cut invariants ===================================================

class TestCrossCutInvariants:
    """Properties that must hold for any applied P5 ledger."""

    def test_ledger_count_is_990(self):
        """Lock in scope: P5 has exactly 990 entries (337 repair + 653 keep).

        After P5B manual review pass: 2 seed repairs + 335 manual repairs = 337
        repair_gloss; 988 review_candidate flipped to 335 repair + 653 keep.
        Total = 337 + 653 = 990.
        """
        ledger = _load_ledger()
        assert len(ledger) == 990, f'P5 scope is 990, got {len(ledger)}'

    def test_repair_count_is_346(self):
        """After P5D: 346 repair_gloss (2 seed + 344 P5D v2 manual).

        P5B had 337 (2 seed + 335); P5D added 9 more by flipping keep -> repair.
        """
        ledger = _load_ledger()
        n = sum(1 for r in ledger if r.get('decision') == 'repair_gloss')
        assert n == 346, f'expected 346 repair_gloss, got {n}'

    def test_review_candidate_count_is_0(self):
        """After P5B: 0 review_candidate (all 988 are now repair or keep)."""
        ledger = _load_ledger()
        n = sum(1 for r in ledger if r.get('decision') == 'review_candidate')
        assert n == 0, f'expected 0 review_candidate, got {n}'

    def test_keep_count_is_644(self):
        """After P5D: 644 keep_current from manual review.

        P5B had 653; P5D removed 9 by flipping keep -> repair.
        """
        ledger = _load_ledger()
        n = sum(1 for r in ledger if r.get('decision') == 'keep_current')
        assert n == 644, f'expected 644 keep_current, got {n}'

    def test_seed_repairs_have_correct_metadata(self):
        """The 2 seed repairs (mediate, solo) have the expected metadata.

        After P5B, the ledger has 337 repair_gloss total, but the 2 seed
        repairs are still present at the top of the list with their
        original risk_type metadata.
        """
        ledger = _load_ledger()
        seed_keys = {('mediate', 'verb', 'C2'), ('solo', 'noun', 'C1')}
        seed_repairs = [
            r for r in ledger
            if r.get('decision') == 'repair_gloss'
            and (r['word'], r['pos'], r['cefr']) in seed_keys
        ]
        assert len(seed_repairs) == 2, (
            f'expected 2 seed repairs, got {len(seed_repairs)}'
        )
        for r in seed_repairs:
            key = (r['word'], r['pos'], r['cefr'])
            assert key in seed_keys, f'unexpected repair key {key}'
            assert r['rule_after'] == 'precision_phrase'
            assert r['risk_type'] in ('contrast_pair', 'type_narrowing')
            assert r['new_gloss']
            assert r['new_gloss'] != r['old_gloss']
            assert r['separator'] == 'none'

    def test_mediate_seed(self):
        ledger = _load_ledger()
        mediate = next(
            r for r in ledger
            if r['word'] == 'mediate' and r['pos'] == 'verb' and r['cefr'] == 'C2'
        )
        assert mediate['old_gloss'] == 'arbitrate'
        assert mediate['new_gloss'] == 'help resolve a dispute'
        assert mediate['gloss_word_count'] == 4
        assert mediate['risk_type'] == 'contrast_pair'

    def test_solo_seed(self):
        ledger = _load_ledger()
        solo = next(
            r for r in ledger
            if r['word'] == 'solo' and r['pos'] == 'noun' and r['cefr'] == 'C1'
        )
        assert solo['old_gloss'] == 'recital'
        assert solo['new_gloss'] == 'single-performer music'
        assert solo['gloss_word_count'] == 2
        assert solo['risk_type'] == 'type_narrowing'

    def test_review_candidates_have_no_mutation_fields(self):
        """After P5B: 0 review_candidate rows. keep_current rows have
        new_gloss=None and rule_after=None (they only mark reviewed, no
        audit change)."""
        ledger = _load_ledger()
        for rec in ledger:
            if rec.get('decision') == 'keep_current':
                assert rec.get('new_gloss') is None
                assert rec.get('rule_after') is None

    def test_p5b_provenance_present(self):
        """All post-P5B ledger rows (988 review_candidate flips) carry
        the `manual_decision` field. The 2 seed repairs pre-date P5B."""
        ledger = _load_ledger()
        seed_keys = {('mediate', 'verb', 'C2'), ('solo', 'noun', 'C1')}
        missing = []
        for rec in ledger:
            key = (rec['word'], rec['pos'], rec['cefr'])
            if key in seed_keys:
                continue  # seed repairs pre-date P5B
            assert rec.get('manual_decision') in (
                'repair_gloss', 'keep_current',
            ), f'missing manual_decision: {key}'

    def test_qa_normalized_rows_marked(self):
        """The 7 QA-normalized rows have qa_normalized=True with qa_original."""
        ledger = _load_ledger()
        qa_keys = {
            ('burst', 'verb', 'C1'),
            ('compromise', 'noun, verb', 'C1'),
            ('outrage', 'noun, verb', 'C1'),
            ('overwhelm', 'verb', 'C1'),
            ('pop', 'verb', 'C1'),
            ('punk', 'noun', 'B2'),
            ('whip', 'verb', 'C1'),
        }
        seen = 0
        for rec in ledger:
            if (
                rec.get('decision') == 'repair_gloss'
                and (rec['word'], rec['pos'], rec['cefr']) in qa_keys
            ):
                assert rec.get('qa_normalized') is True, rec
                assert rec.get('qa_original'), rec
                seen += 1
        assert seen == 7, f'expected 7 QA-normalized rows, got {seen}'


# === Audit policy tool classification =========================================

class TestAuditPolicyClassification:
    """precision_phrase must be classified as allowed_single_gloss by the
    audit policy tool."""

    def test_precision_phrase_is_single_allowed(self):
        from tools._audit_gloss_policy_coverage import _classify_row, SINGLE_ALLOWED
        assert 'precision_phrase' in SINGLE_ALLOWED
        # A row with rule=precision_phrase, single-chunk gloss → allowed_single_gloss
        row = {
            'rule_applied': 'precision_phrase',
            'gloss_after': 'help resolve a dispute',
            'separator': 'none',
        }
        bucket, _ = _classify_row(row)
        assert bucket == 'allowed_single_gloss', bucket

    def test_post_apply_mediate_audit_row_is_allowed_single(self):
        """The actual mediate audit row (post-apply) should classify
        cleanly as allowed_single_gloss."""
        from tools._audit_gloss_policy_coverage import _classify_row
        audit = _verify_load_audit()
        mediate_rows = [
            r for r in audit
            if r['word'].lower() == 'mediate'
            and r['pos'].lower() == 'verb'
            and r['cefr'].upper() == 'C2'
        ]
        assert len(mediate_rows) == 1
        bucket, reason = _classify_row(mediate_rows[0])
        assert bucket == 'allowed_single_gloss', (bucket, reason)

    def test_post_apply_solo_noun_audit_row_is_allowed_single(self):
        """The actual solo|noun audit row (post-apply) should classify
        cleanly as allowed_single_gloss."""
        from tools._audit_gloss_policy_coverage import _classify_row
        audit = _verify_load_audit()
        solo_rows = [
            r for r in audit
            if r['word'].lower() == 'solo'
            and r['pos'].lower() == 'noun'
            and r['cefr'].upper() == 'C1'
        ]
        assert len(solo_rows) == 1
        bucket, reason = _classify_row(solo_rows[0])
        assert bucket == 'allowed_single_gloss', (bucket, reason)


# === Gloss rule code registration =============================================

class TestPrecisionPhraseRuleCode:
    """precision_phrase must be registered as a VALID_RULE_CODE in the
    gloss pipeline schema."""

    def test_precision_phrase_in_valid_rule_codes(self):
        from src.deck_builder.gloss_llm import VALID_RULE_CODES
        assert 'precision_phrase' in VALID_RULE_CODES
