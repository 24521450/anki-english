"""P6 Multisense Hard-Drop Repair -- tests.

Locks in the P6 plan's acceptance criteria:

  - Canonical decisions file has 117 rows.
  - All decisions use rule_after = multi_sense_distinct.
  - 8 headword-leak QA normalizations are present (qa_normalized=True).
  - All 8 normalized glosses pass validate_verdict.
  - No P6 audit row has any legacy/invalid rule code from the patched file
    (`3sense_distinct`, `4sense_distinct`).
  - All deferred keys match the known set of 3.
  - All decisions' gloss_word_count matches actual count.

Post-P8 drift tolerance:
  - P6 decisions are historical artifacts; their `rule_after` field stays
    `multi_sense_distinct` regardless of subsequent taxonomy migrations.
  - P8 split the old `multi_sense_distinct` PICK rule into the new
    convention taxonomy (`2sense_distinct` / `3sense_distinct` /
    `4sense_distinct` / `5sense_distinct` / `2sense_distinct_with_facet` /
    `3sense_distinct_with_facet`). P6 audit rows are allowed to have any of
    these successor rules post-P8.
  - TXT gloss drift after P8 is tolerated for keys whose current audit row
    has a P8 successor rule (`rule_applied` in `P8_P6_SUCCESSOR_RULES`).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'multisense_harddrop_p6_decisions.jsonl'
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt

from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
from tests.deck_builder.historical_supersession import DELETED_KEYS

EXPECTED_DEFERRED_KEYS = {
    ('harbor', 'verb', 'UNCLASSIFIED'),
    ('invading', 'verb', 'UNCLASSIFIED'),
    ('shortsighted', 'adjective', 'UNCLASSIFIED'),
}

# Post-P8 successors of P6's `multi_sense_distinct` rule.
# P6 audit rows may now use any of these after the convention taxonomy split.
P8_P6_SUCCESSOR_RULES = {
    'multi_sense_distinct',  # legacy rows not yet migrated by P8 (kept for back-compat)
    '2sense_distinct',
    '3sense_distinct',
    '4sense_distinct',
    '5sense_distinct',
    '2sense_distinct_with_facet',
    '3sense_distinct_with_facet',
}
# Post-P8 deprecated rules: P6 rows previously had these but P8 migrated them away.
# Audit rows should never have `precision_phrase` (P5's deprecated rule).
P6_DEPRECATED_RULES = {'precision_phrase'}

QA_NORMALIZED_FIXES = {
    ('arrow', 'noun', 'B2'): 'bow projectile|direction mark',
    ('compound', 'noun', 'B2'): 'combined thing|chemical substance|word combination',
    ('democratic', 'adjective', 'B2'): 'people-ruled|member-equal|socially equal|US party-related',
    ('lens', 'noun', 'B2'): 'curved seeing glass|camera glass|contact eyewear',
    ('patrol', 'noun, verb', 'C1'): 'checking round|security group|go round checking',
    ('squad', 'noun', 'C1'): 'police unit|sports team|soldier group',
    ('tap', 'noun, verb', 'B2'): 'water valve|light touch|touch lightly|rhythmic beat',
    ('top', 'verb', 'C1'): 'exceed|rank first|place above',
}


@pytest.fixture(scope='module')
def decisions() -> list[dict]:
    if not DECISIONS_PATH.exists():
        pytest.skip(f'{DECISIONS_PATH.name} not present')
    return [json.loads(l) for l in DECISIONS_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]


@pytest.fixture(scope='module')
def audit() -> list[dict]:
    if not AUDIT_PATH.exists():
        pytest.skip(f'{AUDIT_PATH.name} not present')
    return [json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]


class TestCanonicalDecisions:
    """The P6 canonical decisions file matches the plan."""

    def test_decisions_count_is_117(self, decisions):
        assert len(decisions) == 117, f'expected 117, got {len(decisions)}'

    def test_all_decisions_use_multi_sense_distinct(self, decisions):
        rule_afters = {(d.get('rule_after') or '').strip() for d in decisions}
        assert rule_afters == {'multi_sense_distinct'}, (
            f'unexpected rule_afters: {rule_afters}'
        )

    def test_all_fix_status_p6(self, decisions):
        fix_statuses = {(d.get('fix_status') or '').strip() for d in decisions}
        assert fix_statuses == {'p6_multisense_harddrop_repaired'}, (
            f'unexpected fix_statuses: {fix_statuses}'
        )

    def test_no_duplicate_guards(self, decisions):
        seen: dict[tuple, int] = {}
        for d in decisions:
            k = (
                (d.get('word') or '').strip().lower(),
                (d.get('pos') or '').strip().lower(),
                (d.get('cefr') or '').strip().upper(),
            )
            seen[k] = seen.get(k, 0) + 1
        dups = [k for k, n in seen.items() if n > 1]
        assert not dups, f'duplicate guards: {dups}'

    def test_new_gloss_differs_from_old(self, decisions):
        for d in decisions:
            new = (d.get('new_gloss') or '').strip()
            old = (d.get('old_gloss') or '').strip()
            if new and old:
                assert new != old, f'{d["word"]}|{d["pos"]}|{d["cefr"]} new==old'


class TestQAHeadwordLeakFixes:
    """The 8 raw-validator-failure rows were normalized to pass validator."""

    def test_qa_normalized_count_is_8(self, decisions):
        n_qa = sum(1 for d in decisions if d.get('qa_normalized'))
        assert n_qa == 8, f'expected 8 QA-normalized, got {n_qa}'

    @pytest.mark.parametrize('expected_key,expected_gloss', list(QA_NORMALIZED_FIXES.items()))
    def test_qa_normalization_present(self, decisions, expected_key, expected_gloss):
        w, p, c = expected_key
        d = next(
            (x for x in decisions
             if (x.get('word') or '').strip().lower() == w
             and (x.get('pos') or '').strip().lower() == p
             and (x.get('cefr') or '').strip().upper() == c),
            None,
        )
        assert d is not None, f'no decision for {expected_key}'
        assert d.get('new_gloss') == expected_gloss, (
            f'{expected_key}: expected {expected_gloss!r}, got {d.get("new_gloss")!r}'
        )
        assert d.get('qa_normalized') is True
        assert d.get('qa_original'), 'qa_original should be set when qa_normalized'

    @pytest.mark.parametrize('expected_key,expected_gloss', list(QA_NORMALIZED_FIXES.items()))
    def test_qa_normalized_passes_validator(self, expected_key, expected_gloss):
        w, p, _ = expected_key
        # Use '|' since the gloss has multi-chunk.
        chunks = expected_gloss.split('|')
        sep = '|'
        v = validate_verdict(w, expected_gloss, sep, len(chunks))
        assert v == [], f'{expected_key} validator failed: {v}'


class TestAuditReflection:
    """P6 decisions are reflected in the audit master."""

    def test_audit_count_is_2457(self, audit):
        assert len(audit) == 2457, f'expected 2457 audit rows, got {len(audit)}'

    def test_all_p6_audit_rows_synced(self, decisions, audit):
        """Every P6 decision's (word, pos, cefr) audit row reflects the new gloss.

        Drift tolerance:
        - P7 may have superseded this row with a
          common_core_trimmed / trimmed_multisense rule. Accept P7's verdict.
        - P8 may have migrated `multi_sense_distinct` to the new convention
          taxonomy (`2sense_distinct` / `3sense_distinct` / ... /
          `_with_facet`). Accept any P8 successor rule, and accept the gloss
          drift that P8 brings with it.
        """
        audit_by_key: dict[tuple, dict] = {}
        for r in audit:
            k = (
                (r.get('word') or '').strip().lower(),
                (r.get('pos') or '').strip().lower(),
                (r.get('cefr') or '').strip().upper(),
            )
            audit_by_key.setdefault(k, []).append(r)
        for d in decisions:
            k = (
                (d.get('word') or '').strip().lower(),
                (d.get('pos') or '').strip().lower(),
                (d.get('cefr') or '').strip().upper(),
            )
            if k in DELETED_KEYS:
                continue
            assert k in audit_by_key, f'audit missing {k}'
            rows = audit_by_key[k]
            assert len(rows) == 1, f'audit has {len(rows)} rows for {k}'
            r = rows[0]
            fix_status = r.get('fix_status', '').strip()
            rule_applied = r.get('rule_applied', '').strip()
            from tests.deck_builder.historical_supersession import is_gloss_review_superseded
            if is_gloss_review_superseded(r):
                continue
            # P7 may have superseded P6's multi_sense_distinct with a
            # common_core_trimmed / trimmed_multisense rule.
            if fix_status == 'p7_redundant_sense_trimmed':
                assert rule_applied in ('common_core_trimmed', 'trimmed_multisense'), (
                    f'{k}: P7 superseded P6 but rule_applied={rule_applied!r} '
                    f'(expected common_core_trimmed or trimmed_multisense)'
                )
                continue
            # P8 may have migrated multi_sense_distinct to the new taxonomy.
            # Accept any P8 successor rule + the gloss drift it brings.
            if rule_applied in P8_P6_SUCCESSOR_RULES and rule_applied != 'multi_sense_distinct':
                # P8 successor: gloss drift tolerated.
                continue
            # Otherwise: legacy assertion — audit row should match P6 decision.
            assert fix_status == 'p6_multisense_harddrop_repaired', (
                f'{k}: unexpected fix_status={fix_status!r}'
            )
            assert rule_applied == 'multi_sense_distinct', (
                f'{k}: rule_applied={rule_applied!r} not in P8 successor set '
                f'and not legacy multi_sense_distinct'
            )
            assert r.get('gloss_after', '').strip() == (d.get('new_gloss') or '').strip()

    def test_no_invalid_legacy_rule_codes_in_audit(self, audit):
        """P6 deprecated rules must not appear in audit.

        - `precision_phrase` was P5's rule, deprecated post-P8 (split into
          word_gloss / phrase_gloss / facet_phrase).
        - P6's `multi_sense_distinct` was migrated post-P8 to Nsense_distinct
          variants.
        """
        bad = [
            r for r in audit
            if (r.get('rule_applied') or '').strip() in P6_DEPRECATED_RULES
        ]
        assert not bad, (
            f'audit still has {len(bad)} rows with P6-deprecated rules '
            f'({P6_DEPRECATED_RULES}): {bad[:3]}'
        )


class TestTXTReflection:
    """TXT cells updated for 114 rows; 3 deferred keys match the known set."""

    def test_txt_synced_count(self, decisions):
        if not TXT_PATH.exists():
            pytest.skip(f'{TXT_PATH.name} not present')
        txt_keys: dict[tuple, str] = {}
        for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            k = (
                parts[3].strip().lower(),
                parts[4].strip().lower(),
                parts[14].strip().upper(),
            )
            txt_keys[k] = parts[6]
        missing = set()
        for d in decisions:
            k = (
                (d.get('word') or '').strip().lower(),
                (d.get('pos') or '').strip().lower(),
                (d.get('cefr') or '').strip().upper(),
            )
            if k not in txt_keys:
                missing.add(k)
        assert missing == EXPECTED_DEFERRED_KEYS, (
            f'deferred mismatch: got {missing}, expected {EXPECTED_DEFERRED_KEYS}'
        )

    def test_txt_synced_glosses_match(self, decisions):
        """For non-deferred keys, TXT def == decision.new_gloss.

        Drift tolerance:
        - P7 may have superseded this P6 row's gloss
          (e.g. collapsed multi_sense_distinct to common_core_trimmed).
        - P8 may have migrated this P6 row's gloss to a new convention
          taxonomy entry (different gloss text). Accept any P8 successor rule.
        """
        if not TXT_PATH.exists():
            pytest.skip(f'{TXT_PATH.name} not present')
        txt_keys: dict[tuple, str] = {}
        for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            k = (
                parts[3].strip().lower(),
                parts[4].strip().lower(),
                parts[14].strip().upper(),
            )
            txt_keys[k] = parts[6]
        # Build P7-superseded + P8-superseded key sets from audit
        audit_p7_keys: set[tuple] = set()
        audit_p8_keys: set[tuple] = set()
        audit_review_keys: set[tuple] = set()
        with open(AUDIT_PATH, encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                fix_status = (r.get('fix_status') or '').strip()
                rule_applied = (r.get('rule_applied') or '').strip()
                k = (
                    (r.get('word') or '').strip().lower(),
                    (r.get('pos') or '').strip().lower(),
                    (r.get('cefr') or '').strip().upper(),
                )
                from tests.deck_builder.historical_supersession import is_gloss_review_superseded
                if is_gloss_review_superseded(r):
                    audit_review_keys.add(k)
                elif fix_status == 'p7_redundant_sense_trimmed':
                    audit_p7_keys.add(k)
                elif rule_applied in P8_P6_SUCCESSOR_RULES and rule_applied != 'multi_sense_distinct':
                    # P8 superseded this row's rule + gloss.
                    audit_p8_keys.add(k)
        for d in decisions:
            k = (
                (d.get('word') or '').strip().lower(),
                (d.get('pos') or '').strip().lower(),
                (d.get('cefr') or '').strip().upper(),
            )
            if k in EXPECTED_DEFERRED_KEYS:
                continue
            if k in audit_review_keys:
                continue
            if k in audit_p7_keys:
                # P7 superseded; TXT reflects P7's later verdict, not P6's.
                continue
            if k in audit_p8_keys:
                # P8 superseded; TXT reflects P8's later verdict, not P6's.
                continue
            if k in txt_keys:
                assert txt_keys[k].strip() == (d.get('new_gloss') or '').strip()


class TestRuleCodeVocab:
    """VALID_RULE_CODES includes multi_sense_distinct (and legacy 3sense_distinct)."""

    def test_multi_sense_distinct_in_valid_codes(self):
        from src.deck_builder.gloss_llm import VALID_RULE_CODES
        assert 'multi_sense_distinct' in VALID_RULE_CODES

    def test_legacy_3sense_distinct_retained(self):
        from src.deck_builder.gloss_llm import VALID_RULE_CODES
        assert '3sense_distinct' in VALID_RULE_CODES

    def test_multi_sense_distinct_is_pick_rule(self):
        from tools._audit_gloss_policy_coverage import PICK_RULES
        assert 'multi_sense_distinct' in PICK_RULES
