"""P7 Redundant Sense Trim -- tests.

Locks in P7 plan's acceptance criteria.

Required checks:
  - Canonical decisions file has 59 rows.
  - All decisions' rule_after is in {common_core_trimmed, trimmed_multisense}.
  - No v3 raw rule labels (3sense_distinct / 4sense_distinct / 5sense_distinct)
    appear in P7 decisions.
  - 42 single-chunk (common_core_trimmed) + 17 multi-chunk (trimmed_multisense)
    = 59 total.
  - All decisions' gloss_word_count matches actual count.
  - All decisions' new_gloss passes validate_verdict (post-P5D).
  - Audit row count is 2488 after the overlap POS split; no duplicate guards.
  - 59 audit rows synced with fix_status = p7_redundant_sense_trimmed.
  - 59 TXT cells synced; 0 deferred keys.
  - Rule codes are in VALID_RULE_CODES and KNOWN_RULES.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import ProjectPaths

paths = ProjectPaths()
PROJECT_ROOT = paths.root
DECISIONS_PATH = PROJECT_ROOT / 'data' / 'redundant_sense_trim_p7_decisions.jsonl'
AUDIT_PATH = paths.deck_audit_jsonl
TXT_PATH = paths.anki_notes_txt

from src.deck_builder.gloss_llm import validate_verdict  # noqa: E402
from tests.deck_builder.historical_supersession import DELETED_KEYS

ALLOWED_RULES = {'common_core_trimmed', 'trimmed_multisense'}
V3_RAW_LABELS = {'3sense_distinct', '4sense_distinct', '5sense_distinct'}


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
    """The P7 canonical decisions file matches the plan."""

    def test_count_is_59(self, decisions):
        assert len(decisions) == 59, f'expected 59, got {len(decisions)}'

    def test_rule_afters_in_allowed_set(self, decisions):
        rules = {(d.get('rule_after') or '').strip() for d in decisions}
        assert rules == ALLOWED_RULES, f'unexpected rules: {rules}'

    def test_no_v3_raw_labels_in_decisions(self, decisions):
        """P7 import normalizes rule_after; v3 raw labels must not leak through."""
        for d in decisions:
            rule = (d.get('rule_after') or '').strip()
            assert rule not in V3_RAW_LABELS, (
                f'v3 raw label leaked: {rule!r} for {d["word"]}'
            )

    def test_all_fix_status_p7(self, decisions):
        fix_statuses = {(d.get('fix_status') or '').strip() for d in decisions}
        assert fix_statuses == {'p7_redundant_sense_trimmed'}, (
            f'unexpected fix_statuses: {fix_statuses}'
        )

    def test_no_duplicate_guards(self, decisions):
        seen: dict[tuple, int] = {}
        for d in decisions:
            k = _key(d)
            seen[k] = seen.get(k, 0) + 1
        dups = [k for k, n in seen.items() if n > 1]
        assert not dups, f'duplicate guards: {dups}'

    def test_split_42_common_core_plus_17_trimmed_multisense(self, decisions):
        n_single = sum(1 for d in decisions if d.get('rule_after') == 'common_core_trimmed')
        n_multi = sum(1 for d in decisions if d.get('rule_after') == 'trimmed_multisense')
        assert n_single == 42, f'expected 42 common_core_trimmed, got {n_single}'
        assert n_multi == 17, f'expected 17 trimmed_multisense, got {n_multi}'
        assert n_single + n_multi == 59

    def test_new_gloss_differs_from_old(self, decisions):
        for d in decisions:
            new = (d.get('new_gloss') or '').strip()
            old = (d.get('old_gloss') or '').strip()
            if new and old:
                assert new != old, f'{d["word"]}|{d["pos"]}|{d["cefr"]} new==old'


class TestWordCountAndValidator:
    """P7 decisions' metadata is consistent."""

    def test_word_count_matches_actual(self, decisions):
        for d in decisions:
            gloss = (d.get('new_gloss') or '').strip()
            wc = d.get('gloss_word_count', 0) or 0
            chunks = [c.strip() for c in gloss.replace('|', ' ').replace(';', ' ').split() if c.strip()]
            # Compute chunks properly: split on | and ;
            import re as _re
            chunks = [c.strip() for c in _re.split(r'\s*[|;]\s*', gloss) if c.strip()]
            actual = sum(len(c.split()) for c in chunks)
            assert actual == wc, (
                f'{d["word"]}: wc={wc} actual={actual} gloss={gloss!r}'
            )

    def test_all_passes_validator(self, decisions):
        for d in decisions:
            gloss = (d.get('new_gloss') or '').strip()
            sep = (d.get('separator') or '').strip()
            import re as _re
            chunks = [c.strip() for c in _re.split(r'\s*[|;]\s*', gloss) if c.strip()]
            v = validate_verdict(d['word'], gloss, sep, len(chunks))
            assert v == [], f'{d["word"]}: validator failed: {v}'


class TestAuditReflection:
    """P7 decisions are reflected in the audit master."""

    def test_audit_count_is_2457(self, audit):
        assert len(audit) == 2457, f'expected 2457, got {len(audit)}'

    def test_all_p7_audit_rows_synced(self, decisions, audit):
        audit_by_key: dict[tuple, dict] = {}
        for r in audit:
            k = _key(r)
            audit_by_key.setdefault(k, []).append(r)
        for d in decisions:
            k = _key(d)
            if k in DELETED_KEYS:
                continue
            assert k in audit_by_key, f'audit missing {k}'
            rows = audit_by_key[k]
            assert len(rows) == 1, f'audit has {len(rows)} rows for {k}'
            r = rows[0]
            from tests.deck_builder.historical_supersession import should_tolerate_historical_drift
            if should_tolerate_historical_drift(r, 'p15_simple_gloss_repaired'):
                continue
            assert r.get('fix_status', '').strip() == 'p7_redundant_sense_trimmed'
            assert r.get('rule_applied', '').strip() == d.get('rule_after')
            assert r.get('gloss_after', '').strip() == (d.get('new_gloss') or '').strip()
            assert r.get('separator', '').strip() == (d.get('separator') or '').strip()
            assert r.get('gloss_word_count', -1) == d.get('gloss_word_count', -1)


class TestTXTReflection:
    """TXT cells updated for all 59 rows; no deferred."""

    def test_all_59_txt_synced_no_deferred(self, decisions, audit):
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
        missing = []
        for d in decisions:
            k = _key(d)
            if k not in txt_keys:
                missing.append(k)
                continue
            r = next((x for x in audit if _key(x) == k), None)
            from tests.deck_builder.historical_supersession import should_tolerate_historical_drift
            if r and should_tolerate_historical_drift(r, 'p15_simple_gloss_repaired'):
                continue
            assert txt_keys[k].strip() == (d.get('new_gloss') or '').strip()
        assert missing == [], f'missing TXT keys: {missing}'


class TestRuleCodeVocab:
    """VALID_RULE_CODES includes the new P7 codes."""

    def test_common_core_trimmed_in_valid_codes(self):
        from src.deck_builder.gloss_llm import VALID_RULE_CODES
        assert 'common_core_trimmed' in VALID_RULE_CODES

    def test_trimmed_multisense_in_valid_codes(self):
        from src.deck_builder.gloss_llm import VALID_RULE_CODES
        assert 'trimmed_multisense' in VALID_RULE_CODES

    def test_common_core_trimmed_is_single_allowed(self):
        from tools._audit_gloss_policy_coverage import SINGLE_ALLOWED
        assert 'common_core_trimmed' in SINGLE_ALLOWED

    def test_trimmed_multisense_is_pick_rule(self):
        from tools._audit_gloss_policy_coverage import PICK_RULES
        assert 'trimmed_multisense' in PICK_RULES

    def test_p7_codes_in_known_rules(self):
        from tools._full_audit import KNOWN_RULES
        assert 'common_core_trimmed' in KNOWN_RULES
        assert 'trimmed_multisense' in KNOWN_RULES


class TestNoP6Backdrift:
    """P7 must not silently undo P6 multi_sense_distinct rules."""

    def test_no_p7_fix_status_with_legacy_rule_code(self, audit):
        bad = [
            (r['word'], r['pos'], r['cefr'])
            for r in audit
            if (r.get('fix_status') or '').strip() == 'p7_redundant_sense_trimmed'
            and (r.get('rule_applied') or '').strip() in V3_RAW_LABELS
        ]
        assert not bad, f'P7 backdrifted P6 to legacy codes: {bad}'
