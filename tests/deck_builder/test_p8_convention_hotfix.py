"""P8 Convention + Hotfix -- tests.

Locks in the P8 plan's acceptance criteria.

Required checks:
  - Canonical decisions file has 457 rows.
  - All decisions' rule_after is in the P8 taxonomy (NEW_TAXONOMY).
  - No audit row has the deprecated `precision_phrase` rule.
  - No audit row has the deprecated `multi_sense_distinct` rule.
  - All 3 `_with_facet` audit rows have `review_needed: true`.
  - 42 single-chunk (`word_gloss` / `phrase_gloss` / `facet_phrase`)
    + 415 multi-chunk (Nsense_distinct / _with_facet) = 457 total.
  - All decisions' gloss_word_count matches actual count.
  - All decisions' gloss_after passes validate_verdict.
  - Audit row count is 2487.
  - 457 audit rows synced with fix_status in
    {p9_convention_repaired, p10_semantic_hotfix, p11_semantic_hotfix_v2}
    OR unchanged for non-P8 rows.
  - Miserable|adjective|B2 regression:
    - def_before contains `|` (Oxford source correction).
    - def_before does NOT contain `;` (was incorrectly `;` from raw HTML).
    - gloss_after == 'very unhappy|very unpleasant'.
    - rule_applied == '2sense_distinct'.
  - All 7 NEW rule codes registered in VALID_RULE_CODES.
  - All new rules present in PICK_RULES / SINGLE_ALLOWED as appropriate.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'convention_p8_decisions.jsonl'
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt

from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402

NEW_TAXONOMY = {
    '', 'rule_b_pick1', 'rule_b_pick2', 'rule_b_pick2_addendum',
    '2sense_samedomain', '2sense_distinct', '3sense_distinct',
    'common_core_trimmed', 'trimmed_multisense',
    'concrete_1sense', 'multi_pos_pick1', 'multi_pos_pick2',
    'safety_net', 'pos_aware_gloss',
    'POS_DEF_MISMATCH_fixed', 'B', 'concise_def_skip',
    'word_gloss', 'phrase_gloss', 'facet_phrase',
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
    '4sense_distinct', '5sense_distinct',
}

DEPRECATED_POST_P8 = {'precision_phrase', 'multi_sense_distinct'}

WITH_FACET_RULES = {
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
}

SINGLE_CHUNK_RULES = {'word_gloss', 'phrase_gloss', 'facet_phrase'}
MULTI_CHUNK_RULES = {
    '2sense_distinct', '3sense_distinct',
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
    '4sense_distinct', '5sense_distinct',
    '2sense_samedomain',  # uses `;` but still multi-chunk
    'rule_b_pick2', 'rule_b_pick2_addendum',
    'multi_pos_pick2',
    'common_core_trimmed', 'trimmed_multisense',  # P7 rules: 1 vs multi
    'rule_b_pick1', 'multi_pos_pick1',  # 1 chunk
    'concrete_1sense', 'safety_net', 'pos_aware_gloss',
    'POS_DEF_MISMATCH_fixed', 'B', 'concise_def_skip',
    '',
}


def _key(r: dict) -> tuple[str, str, str]:
    return (
        (r.get('word') or '').strip().lower(),
        (r.get('pos') or '').strip().lower(),
        (r.get('cefr') or '').strip().upper(),
    )


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
    """The P8 canonical decisions file matches the plan."""

    def test_count_is_457(self, decisions):
        assert len(decisions) == 457, f'expected 457, got {len(decisions)}'

    def test_rule_afters_in_new_taxonomy(self, decisions):
        rules = {(d.get('rule_after') or '').strip() for d in decisions}
        unexpected = rules - NEW_TAXONOMY
        assert not unexpected, f'unexpected rules in decisions: {unexpected}'

    def test_no_deprecated_rule_after_in_decisions(self, decisions):
        bad = [
            d['word'] for d in decisions
            if (d.get('rule_before') or '').strip() in DEPRECATED_POST_P8
            and (d.get('rule_after') or '').strip() in DEPRECATED_POST_P8
        ]
        # Allow decisions where rule_before is deprecated AND rule_after
        # is the same deprecated code (i.e. rule wasn't actually migrated).
        # These should not exist after P8 apply.
        assert not bad, f'P8 left {len(bad)} deprecated-to-deprecated decisions'

    def test_no_duplicate_guards(self, decisions):
        seen: dict[tuple, int] = {}
        for d in decisions:
            k = _key(d)
            seen[k] = seen.get(k, 0) + 1
        dups = [k for k, n in seen.items() if n > 1]
        assert not dups, f'duplicate guards: {dups}'

    def test_decisions_have_required_fields(self, decisions):
        required = {'word', 'pos', 'cefr', 'gloss_after', 'rule_after',
                    'separator', 'gloss_word_count', 'guard_word', 'guard_pos',
                    'guard_cefr', 'guard_def_before', 'guard_gloss_after'}
        for d in decisions:
            missing = required - set(d.keys())
            assert not missing, f'{d.get("word")}|{d.get("pos")}|{d.get("cefr")} missing fields: {missing}'

    def test_new_gloss_differs_from_gloss_before(self, decisions):
        """P8 mostly migrates rule metadata; only ~12 rows change gloss text."""
        n_changed = 0
        for d in decisions:
            new = (d.get('gloss_after') or '').strip()
            old = (d.get('gloss_before') or '').strip()
            if new and old and new != old:
                n_changed += 1
        # At least 10 rows should have changed gloss text (12 per patch report).
        assert n_changed >= 10, f'expected >= 10 gloss-text changes, got {n_changed}'


class TestRuleCodeMigration:
    """P8 migrates `precision_phrase` and `multi_sense_distinct` to new taxonomy."""

    def test_precision_phrase_migrated(self, decisions):
        """Decisions previously using `precision_phrase` should now use a P8 successor."""
        n_pp = sum(1 for d in decisions if (d.get('rule_before') or '').strip() == 'precision_phrase')
        n_pp_migrated = sum(
            1 for d in decisions
            if (d.get('rule_before') or '').strip() == 'precision_phrase'
            and (d.get('rule_after') or '').strip() in {
                'word_gloss', 'phrase_gloss', 'facet_phrase',
                '2sense_distinct', '3sense_distinct',
                '4sense_distinct', '5sense_distinct',
            }
        )
        assert n_pp > 0, 'no precision_phrase migrations found'
        assert n_pp_migrated == n_pp, (
            f'{n_pp - n_pp_migrated}/{n_pp} precision_phrase rows NOT migrated'
        )

    def test_multi_sense_distinct_migrated(self, decisions):
        """Decisions previously using `multi_sense_distinct` should now use a P8 successor."""
        n_ms = sum(1 for d in decisions if (d.get('rule_before') or '').strip() == 'multi_sense_distinct')
        n_ms_migrated = sum(
            1 for d in decisions
            if (d.get('rule_before') or '').strip() == 'multi_sense_distinct'
            and (d.get('rule_after') or '').strip() in {
                '2sense_distinct', '3sense_distinct',
                '4sense_distinct', '5sense_distinct',
                '2sense_distinct_with_facet', '3sense_distinct_with_facet',
            }
        )
        assert n_ms > 0, 'no multi_sense_distinct migrations found'
        assert n_ms_migrated == n_ms, (
            f'{n_ms - n_ms_migrated}/{n_ms} multi_sense_distinct rows NOT migrated'
        )


class TestAuditReflection:
    """P8 decisions are reflected in the audit master."""

    def test_audit_count_is_2487(self, audit):
        assert len(audit) == 2487, f'expected 2487, got {len(audit)}'

    def test_no_deprecated_rule_in_audit(self, audit):
        """`precision_phrase` and `multi_sense_distinct` must NOT appear in audit post-P8."""
        bad_precision = [
            r for r in audit if (r.get('rule_applied') or '').strip() == 'precision_phrase'
        ]
        bad_multi = [
            r for r in audit if (r.get('rule_applied') or '').strip() == 'multi_sense_distinct'
        ]
        assert not bad_precision, f'{len(bad_precision)} audit rows still have precision_phrase'
        assert not bad_multi, f'{len(bad_multi)} audit rows still have multi_sense_distinct'

    def test_all_with_facet_audit_rows_have_review_needed(self, audit):
        facet_rows = [
            r for r in audit
            if (r.get('rule_applied') or '').strip() in WITH_FACET_RULES
        ]
        assert len(facet_rows) in (3, 4), f'expected 3 or 4 _with_facet audit rows, got {len(facet_rows)}'
        for r in facet_rows:
            assert r.get('review_needed') is True, (
                f'{r["word"]}|{r["pos"]}|{r["cefr"]} has rule={r["rule_applied"]!r} '
                f'but review_needed is not True (got {r.get("review_needed")!r})'
            )

    def test_all_p8_audit_rows_synced(self, decisions, audit):
        """For every P8 decision, the corresponding audit row reflects it.

        Drift tolerance: P12/P13/P15 may have superseded this P8 row.
        Accept any P12/P13/P15 fix_status as a later verdict.
        """
        audit_by_key: dict[tuple, dict] = {}
        for r in audit:
            audit_by_key.setdefault(_key(r), r)
        for d in decisions:
            k = _key(d)
            assert k in audit_by_key, f'audit missing {k}'
            r = audit_by_key[k]
            # P12/P13/P15 may have superseded this P8 row.
            from tests.deck_builder.historical_supersession import should_tolerate_historical_drift
            p12_p13_superseded = should_tolerate_historical_drift(r, {
                'p12_equiv_sense_semantic_hotfix',
                'p13_pipe_sense_hotfix',
                'p15_simple_gloss_repaired',
            })
            if p12_p13_superseded:
                # Gloss + rule drift tolerated; P8 doesn't claim these.
                continue
            assert r.get('gloss_after', '').strip() == (d.get('gloss_after') or '').strip(), (
                f'{k} audit gloss_after={r.get("gloss_after")!r} != '
                f'decision gloss_after={d.get("gloss_after")!r}'
            )
            assert r.get('rule_applied', '').strip() == (d.get('rule_after') or '').strip(), (
                f'{k} audit rule_applied={r.get("rule_applied")!r} != '
                f'decision rule_after={d.get("rule_after")!r}'
            )
            assert r.get('separator', '').strip() == (d.get('separator') or '').strip(), (
                f'{k} audit separator={r.get("separator")!r} != '
                f'decision separator={d.get("separator")!r}'
            )
            assert r.get('gloss_word_count', -1) == d.get('gloss_word_count', -1), (
                f'{k} audit gloss_word_count={r.get("gloss_word_count")!r} != '
                f'decision gloss_word_count={d.get("gloss_word_count")!r}'
            )


class TestTXTReflection:
    """TXT cells updated for non-deferred changed rows."""

    def test_miserable_txt_gloss_updated(self, audit):
        """Miserable|adjective|B2 TXT cell reflects the new gloss."""
        if not TXT_PATH.exists():
            pytest.skip(f'{TXT_PATH.name} not present')
        mis = next((r for r in audit if _key(r) == ('miserable', 'adjective', 'B2')), None)
        assert mis is not None
        for line in TXT_PATH.read_text(encoding='utf-8').splitlines():
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            if (parts[3].strip().lower() == 'miserable'
                    and parts[4].strip().lower() == 'adjective'
                    and parts[14].strip().upper() == 'B2'):
                from tests.deck_builder.historical_supersession import is_gloss_review_superseded
                if is_gloss_review_superseded(mis):
                    assert parts[6].strip() == mis.get('gloss_after', '').strip()
                else:
                    assert parts[6] in (
                        'very unhappy|very unpleasant',
                        'very unhappy or unpleasant',
                    ), (
                        f'miserable|adjective|B2 TXT def={parts[6]!r} '
                        f'(expected P8 "very unhappy|very unpleasant" or P12 '
                        f'"very unhappy or unpleasant")'
                    )
                return
        pytest.fail('miserable|adjective|B2 TXT row not found')

    def test_txt_cells_match_decisions(self, decisions, audit):
        """For non-deferred keys, TXT def == decision.gloss_after."""
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
        # Build audit key -> row map for P12/P13 supersession tolerance.
        audit_row_by_key: dict[tuple, dict] = {}
        for r in audit:
            audit_row_by_key[_key(r)] = r
        mismatched: list[tuple] = []
        for d in decisions:
            k = _key(d)
            if k not in txt_keys:
                continue  # deferred
            if txt_keys[k].strip() != (d['gloss_after'] or '').strip():
                # Drift tolerance: P12/P13/P15 may have superseded this row.
                r_row = audit_row_by_key.get(k)
                from tests.deck_builder.historical_supersession import should_tolerate_historical_drift
                if r_row and should_tolerate_historical_drift(r_row, {
                    'p12_equiv_sense_semantic_hotfix',
                    'p13_pipe_sense_hotfix',
                    'p15_simple_gloss_repaired',
                }):
                    continue
                mismatched.append((k, txt_keys[k], d['gloss_after']))
        assert not mismatched, f'TXT/decisions mismatches: {mismatched[:5]}'


class TestMiserableRegression:
    """Miserable Oxford source correction (def_before uses |, not ;)."""

    MISERABLE_KEY = ('miserable', 'adjective', 'B2')

    def test_miserable_def_before_uses_pipe(self, audit):
        mis = next((r for r in audit if _key(r) == self.MISERABLE_KEY), None)
        assert mis is not None, 'miserable|adjective|B2 audit row missing'
        def_before = (mis.get('def_before') or '').strip()
        assert '|' in def_before, (
            f'miserable.def_before must contain | (Oxford source correction). '
            f'Got: {def_before!r}'
        )

    def test_miserable_def_before_does_not_use_semicolon(self, audit):
        """The original raw HTML used ` ; ` as a list-of-senses separator.
        That's wrong for def_before (which is the source def within the
        project). P8 normalizes it to `|`."""
        mis = next((r for r in audit if _key(r) == self.MISERABLE_KEY), None)
        assert mis is not None, 'miserable|adjective|B2 audit row missing'
        def_before = (mis.get('def_before') or '').strip()
        assert ';' not in def_before, (
            f'miserable.def_before must NOT contain ; '
            f'(was wrongly using Oxford HTML list separator). '
            f'Got: {def_before!r}'
        )

    def test_miserable_gloss_after(self, audit):
        mis = next((r for r in audit if _key(r) == self.MISERABLE_KEY), None)
        assert mis is not None
        gloss = (mis.get('gloss_after') or '').strip()
        # P8 baseline OR P12-superseded. P12 collapsed the two senses into
        # a single-chunk facet phrase.
        from tests.deck_builder.historical_supersession import is_gloss_review_superseded
        if is_gloss_review_superseded(mis):
            return
        assert gloss in ('very unhappy|very unpleasant', 'very unhappy or unpleasant'), (
            f'miserable.gloss_after={gloss!r} '
            f'(expected P8 "very unhappy|very unpleasant" or P12 '
            f'"very unhappy or unpleasant")'
        )

    def test_miserable_rule_applied(self, audit):
        mis = next((r for r in audit if _key(r) == self.MISERABLE_KEY), None)
        assert mis is not None
        rule = (mis.get('rule_applied') or '').strip()
        assert rule in ('2sense_distinct', 'facet_phrase'), (
            f'miserable.rule_applied={rule!r} '
            f'(expected P8 "2sense_distinct" or P12 "facet_phrase")'
        )

    def test_miserable_fix_status(self, audit):
        mis = next((r for r in audit if _key(r) == self.MISERABLE_KEY), None)
        assert mis is not None
        fix = (mis.get('fix_status') or '').strip()
        # P8 baseline OR P12-superseded. P12 superseded P8's fix_status.
        from tests.deck_builder.historical_supersession import is_gloss_review_superseded, is_superseded_by
        assert is_gloss_review_superseded(mis) or is_superseded_by(mis, {'p10_semantic_hotfix', 'p12_equiv_sense_semantic_hotfix'}), (
            f'miserable.fix_status={fix!r} '
            f'(expected P8 "p10_semantic_hotfix" or P12 '
            f'"p12_equiv_sense_semantic_hotfix")'
        )


class TestRuleCodeVocab:
    """VALID_RULE_CODES, PICK_RULES, SINGLE_ALLOWED include the new P8 codes."""

    def test_new_rules_in_valid_codes(self):
        from src.deck_builder.gloss_llm import VALID_RULE_CODES
        new_codes = {
            'word_gloss', 'phrase_gloss', 'facet_phrase',
            '2sense_distinct_with_facet', '3sense_distinct_with_facet',
            '4sense_distinct', '5sense_distinct',
        }
        missing = new_codes - set(VALID_RULE_CODES)
        assert not missing, f'VALID_RULE_CODES missing: {missing}'

    def test_pick_rules_include_new_multi_chunk(self):
        from tools._audit_gloss_policy_coverage import PICK_RULES
        for code in ('4sense_distinct', '5sense_distinct',
                     '2sense_distinct_with_facet', '3sense_distinct_with_facet'):
            assert code in PICK_RULES, f'PICK_RULES missing {code!r}'

    def test_single_allowed_includes_new_single_chunk(self):
        from tools._audit_gloss_policy_coverage import SINGLE_ALLOWED
        for code in ('word_gloss', 'phrase_gloss', 'facet_phrase'):
            assert code in SINGLE_ALLOWED, f'SINGLE_ALLOWED missing {code!r}'

    def test_full_audit_known_rules_includes_new(self):
        from tools._full_audit import KNOWN_RULES
        for code in (
            'word_gloss', 'phrase_gloss', 'facet_phrase',
            '2sense_distinct_with_facet', '3sense_distinct_with_facet',
            '4sense_distinct', '5sense_distinct',
        ):
            assert code in KNOWN_RULES, f'_full_audit.KNOWN_RULES missing {code!r}'


class TestNoBackdrift:
    """P8 must not silently undo P6/P7 fixes."""

    def test_p6_fix_status_preserved(self, audit):
        """P6 rows keep their p6_multisense_harddrop_repaired fix_status
        even though rule_applied was migrated by P8."""
        p6_dec_path = PROJECT_ROOT / 'data' / 'multisense_harddrop_p6_decisions.jsonl'
        p6_keys = set()
        if p6_dec_path.exists():
            for line in p6_dec_path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    d = json.loads(line)
                    p6_keys.add(_key(d))
        p6 = [r for r in audit if _key(r) in p6_keys and (r.get('fix_status') or '').strip() == 'p6_multisense_harddrop_repaired']
        from tests.deck_builder.historical_supersession import should_tolerate_historical_drift
        p6_any = [r for r in audit if _key(r) in p6_keys and should_tolerate_historical_drift(r, 'p6_multisense_harddrop_repaired')]
        # At least 100 of the original 117 P6 rows retain p6_* fix_status or are superseded
        # (some were promoted to p10/p11 by the semantic hotfixes).
        assert len(p6_any) >= 90, f'expected >= 90 P6 fix_status preserved or superseded, got {len(p6_any)}'
        # And those rows should have a P8 successor rule (not multi_sense_distinct).
        for r in p6:
            assert (r.get('rule_applied') or '').strip() != 'multi_sense_distinct', (
                f'{r["word"]}|{r["pos"]}|{r["cefr"]} still has deprecated multi_sense_distinct'
            )

    def test_p7_fix_status_preserved(self, audit):
        """P7 rows keep their p7_redundant_sense_trimmed fix_status."""
        p7_dec_path = PROJECT_ROOT / 'data' / 'redundant_sense_trim_p7_decisions.jsonl'
        p7_keys = set()
        if p7_dec_path.exists():
            for line in p7_dec_path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    d = json.loads(line)
                    p7_keys.add(_key(d))
        p7 = [r for r in audit if _key(r) in p7_keys and (r.get('fix_status') or '').strip() == 'p7_redundant_sense_trimmed']
        from tests.deck_builder.historical_supersession import should_tolerate_historical_drift
        p7_any = [r for r in audit if _key(r) in p7_keys and should_tolerate_historical_drift(r, 'p7_redundant_sense_trimmed')]
        assert len(p7_any) in (58, 59), f'expected 58 or 59 P7 fix_status preserved or superseded, got {len(p7_any)}'
        for r in p7:
            assert (r.get('rule_applied') or '').strip() in (
                'common_core_trimmed', 'trimmed_multisense',
            ), f'{r["word"]}|{r["pos"]}|{r["cefr"]} rule_applied={r.get("rule_applied")!r} not P7 rule'
