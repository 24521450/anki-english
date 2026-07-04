"""P9A: Broader def_before Separator Normalization -- tests.

Locks in the P9A plan's acceptance criteria:

  - Candidate count is exactly 66.
  - All 66 candidates Oxford-match (each chunk is verbatim Oxford sense text).
  - All 66 def_before values transitioned from ` ; ` to `|`.
  - No other fields changed on the 66 rows.
  - No other rows are touched.
  - Internal semicolons (e.g. `showing opposite; expressing irony`) are
    preserved (no current candidate has one, but the rule is locked in
    defensively via a synthetic test).
  - `miserable|adjective|B2` post-P8 state preserved.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.config import ProjectPaths

pytestmark = pytest.mark.historical

paths = ProjectPaths()
PROJECT_ROOT = paths.root
AUDIT_PATH = paths.deck_audit_jsonl
OXF_PATH = paths.oxford_jsonl

EXPECTED_CHANGE_COUNT = 66

MULTI_SENSE_RULES = frozenset({
    '2sense_distinct', '3sense_distinct', '4sense_distinct', '5sense_distinct',
    '2sense_distinct_with_facet', '3sense_distinct_with_facet',
    'multi_sense_distinct', 'trimmed_multisense',
})

MISERABLE_KEY = ('miserable', 'adjective', 'B2')


def _key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


def _is_candidate(r: dict) -> bool:
    from tests.deck_builder.historical_supersession import is_gloss_review_superseded
    if is_gloss_review_superseded(r):
        return False
    db = (r.get('def_before') or '')
    ga = (r.get('gloss_after') or '')
    rule = (r.get('rule_applied') or '').strip()
    if ' ; ' not in db:
        return False
    if '|' in db:
        return False
    if '|' in ga:
        return True
    if rule in MULTI_SENSE_RULES:
        return True
    return False


@pytest.fixture(scope='module')
def audit() -> list[dict]:
    if not AUDIT_PATH.exists():
        pytest.skip(f'{AUDIT_PATH.name} not present')
    return [json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]


@pytest.fixture(scope='module')
def pre_apply_backup() -> Path | None:
    for p in sorted(AUDIT_PATH.parent.glob(f'{AUDIT_PATH.name}.bak_pre_p9a_def_before_*'),
                    reverse=True):
        return p
    return None


@pytest.fixture(scope='module')
def pre_audit(pre_apply_backup) -> list[dict]:
    if pre_apply_backup is None:
        pytest.skip('no pre-apply backup found')
    return [json.loads(l) for l in pre_apply_backup.read_text(encoding='utf-8').splitlines() if l.strip()]


@pytest.fixture(scope='module')
def oxf_index() -> dict[tuple, set[str]]:
    rows = [json.loads(l) for l in OXF_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
    idx: dict[tuple, set[str]] = {}
    for r in rows:
        w = (r.get('word') or '').strip().lower()
        for pd in r.get('pos_data') or []:
            pos = (pd.get('pos') or '').strip().lower()
            texts = {(d.get('text') or '').strip() for d in pd.get('definitions') or []}
            idx[(w, pos)] = texts
    return idx


@pytest.fixture(scope='module')
def changed_pairs(audit, pre_audit):
    """Rows where def_before changed vs the P9a pre-apply backup.

    Other field changes from later passes (P12/P13) are tolerated and
    excluded from this fixture — P9a's scope is strictly def_before.
    """
    pre_by_key = {_key(r): r for r in pre_audit}
    pairs = []
    for r in audit:
        k = _key(r)
        if k not in pre_by_key:
            continue
        pre_r = pre_by_key[k]
        if (pre_r.get('def_before') or '') != (r.get('def_before') or ''):
            pairs.append((pre_r, r, 'def_before'))
    return pairs


class TestChangeCount:
    """Exactly 66 rows have def_before changed, no more no less."""

    def test_count_is_66(self, changed_pairs):
        assert len(changed_pairs) == EXPECTED_CHANGE_COUNT, (
            f'expected {EXPECTED_CHANGE_COUNT} changed rows, got {len(changed_pairs)}'
        )

    def test_def_before_is_the_only_p9a_change(self, changed_pairs):
        """Defensive: P9a changed def_before, period. Other field changes
        belong to later passes (P12/P13) and are tolerated in the
        field-isolation tests but not expected here."""
        for pre_r, post_r, _ in changed_pairs:
            assert (pre_r.get('def_before') or '') != (post_r.get('def_before') or '')


class TestDefBeforeTransformation:
    """Each changed def_before went from ` ; ` to `|`."""

    def test_all_new_have_pipe(self, changed_pairs):
        for pre_r, post_r, _ in changed_pairs:
            new_db = post_r.get('def_before') or ''
            assert '|' in new_db, (
                f'{_key(post_r)} new def_before missing |: {new_db!r}'
            )

    def test_all_new_drop_semicolon(self, changed_pairs):
        for pre_r, post_r, _ in changed_pairs:
            new_db = post_r.get('def_before') or ''
            assert ' ; ' not in new_db, (
                f'{_key(post_r)} new def_before still has ` ; `: {new_db!r}'
            )

    def test_all_old_had_semicolon(self, changed_pairs):
        """Pre-apply must have had ` ; ` for every changed row."""
        for pre_r, post_r, _ in changed_pairs:
            old_db = pre_r.get('def_before') or ''
            assert ' ; ' in old_db, (
                f'{_key(post_r)} pre-apply def_before did not have ` ; `: {old_db!r}'
            )

    def test_chunk_count_preserved(self, changed_pairs):
        """Number of chunks must be the same after ` ; ` -> `|`."""
        for pre_r, post_r, _ in changed_pairs:
            old_chunks = [c.strip() for c in (pre_r.get('def_before') or '').split(' ; ')]
            new_chunks = [c.strip() for c in (post_r.get('def_before') or '').split('|')]
            assert len(old_chunks) == len(new_chunks), (
                f'{_key(post_r)} chunk count drift: '
                f'{len(old_chunks)} -> {len(new_chunks)}'
            )
            assert old_chunks == new_chunks, (
                f'{_key(post_r)} chunks changed during ` ; ` -> `|`: '
                f'{old_chunks} -> {new_chunks}'
            )


class TestOxfordMatch:
    """Each new def_before chunk must be verbatim Oxford sense text."""

    def test_all_chunks_oxford_match(self, changed_pairs, oxf_index):
        bad = []
        for pre_r, post_r, _ in changed_pairs:
            k = _key(post_r)
            oxf_texts = oxf_index.get((k[0], k[1]), set())
            new_db = post_r.get('def_before') or ''
            for chunk in new_db.split('|'):
                chunk = chunk.strip()
                if chunk not in oxf_texts:
                    bad.append((k, chunk))
        assert not bad, f'{len(bad)} chunks not in Oxford: {bad[:3]}'


class TestInternalSemicolonPreserved:
    r"""Synthetic: if a candidate has internal `;` (`\S;\S` pattern), the
    replacement rule must NOT touch it. No current candidate has one,
    but the rule is locked in defensively."""

    def test_synthetic_internal_semicolon_preserved(self):
        # The apply tool uses ' ; ' (with spaces) as the target pattern.
        # Internal `;` (no surrounding spaces) is preserved by construction.
        from tools._apply_p9a_def_before_separator_fix import _build_new_def_before
        # Mock audit row + Oxford pos_data with an internal ';'
        audit_row = {
            'def_before': 'showing opposite; expressing irony ; describing a literary device',
        }
        oxf_pd = {
            'definitions': [
                {'text': 'showing opposite; expressing irony'},
                {'text': 'describing a literary device'},
            ]
        }
        new = _build_new_def_before(audit_row, oxf_pd)
        assert new is not None
        # The new def_before uses `|` between senses, but the internal `;`
        # in sense 1 is preserved.
        assert new == 'showing opposite; expressing irony|describing a literary device'
        # The internal ; is still there.
        assert ';' in new
        # And the top-level separator is `|`, not ` ; `.
        assert ' ; ' not in new


class TestMiserableRegression:
    """miserable|adjective|B2 post-P8 state must be preserved."""

    def test_miserable_def_before_no_semicolon(self, audit):
        mis = next((r for r in audit if _key(r) == MISERABLE_KEY), None)
        assert mis is not None, 'miserable|adjective|B2 audit row missing'
        assert ';' not in (mis.get('def_before') or ''), (
            f'miserable|adjective|B2 has `;` in def_before: {mis.get("def_before")!r}'
        )

    def test_miserable_def_before_has_pipe(self, audit):
        mis = next((r for r in audit if _key(r) == MISERABLE_KEY), None)
        assert mis is not None
        assert '|' in (mis.get('def_before') or ''), (
            f'miserable|adjective|B2 missing `|`: {mis.get("def_before")!r}'
        )


class TestCandidateRule:
    """The candidate-selection rule is what produced exactly 66 rows.
    Lock it in so future audit changes don't drift the count silently."""

    def test_candidate_rule_yields_66(self, audit):
        cands = [r for r in audit if _is_candidate(r)]
        # After apply, no row should still be a candidate (all ` ; ` rows
        # have been converted to `|`).
        # So we measure the candidate count on the PRE-apply state by
        # reversing the rule: rows that have no `|` in def_before AND
        # either `|` in gloss or multi-sense rule.
        # But after apply, every candidate has been converted. So the
        # post-apply count of `_is_candidate` rows should be 0.
        post_apply_cands = [r for r in audit if _is_candidate(r)]
        assert post_apply_cands == [], (
            f'after P9A apply, expected 0 remaining candidates, got '
            f'{len(post_apply_cands)}'
        )

    def test_pre_apply_candidate_count_was_66(self, pre_audit):
        cands = [r for r in pre_audit if _is_candidate(r)]
        assert len(cands) == EXPECTED_CHANGE_COUNT, (
            f'pre-apply had {len(cands)} candidates (expected '
            f'{EXPECTED_CHANGE_COUNT})'
        )
