"""P15: Full Simple Gloss Patch v2 -- unit tests."""
from __future__ import annotations

import json
import re
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
JSONL_PATH = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'
INPUT_PATH = Path(r"C:\Users\admin\Downloads\audit_full_deck_v2_p15_full_simple_gloss_patch_v2.jsonl")

EXPECTED_CHANGE_COUNT = 51

APPLY_FIELDS = (
    'gloss_after', 'separator', 'rule_applied', 'gloss_word_count',
    'fix_status', 'review_needed',
)


def _key(r: dict) -> tuple[str, str, str]:
    return (
        r['word'].strip().lower(),
        r['pos'].strip().lower(),
        r['cefr'].strip().upper(),
    )


@pytest.fixture(scope='module')
def audit() -> list[dict]:
    if not AUDIT_PATH.exists():
        pytest.skip(f'{AUDIT_PATH.name} not present')
    return [json.loads(l) for l in AUDIT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]


@pytest.fixture(scope='module')
def target() -> list[dict]:
    if not INPUT_PATH.exists():
        pytest.skip(f'{INPUT_PATH.name} not present')
    return [json.loads(l) for l in INPUT_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]


@pytest.fixture(scope='module')
def pre_apply_backup() -> Path | None:
    for p in sorted(AUDIT_PATH.parent.glob(f'{AUDIT_PATH.name}.bak_pre_p15_*'), reverse=True):
        return p
    return None


@pytest.fixture(scope='module')
def pre_audit(pre_apply_backup) -> list[dict]:
    if pre_apply_backup is None:
        pytest.skip('no pre-apply backup found')
    return [json.loads(l) for l in pre_apply_backup.read_text(encoding='utf-8').splitlines() if l.strip()]


@pytest.fixture(scope='module')
def target_keys(pre_audit, target) -> list[tuple[str, str, str]]:
    pre_by_key = {_key(r): r for r in pre_audit}
    target_by_key = {_key(r): r for r in target}
    keys = []
    for k in pre_by_key:
        c = pre_by_key[k]
        n = target_by_key[k]
        diffs = {f for f in APPLY_FIELDS if c.get(f) != n.get(f)}
        if 'review_needed' in diffs:
            if not c.get('review_needed') and not n.get('review_needed'):
                diffs.remove('review_needed')
        if diffs:
            keys.append(k)
    return keys


class TestP15ScopeLock:
    def test_exact_51_keys_changed(self, target_keys):
        assert len(target_keys) == EXPECTED_CHANGE_COUNT

    def test_no_def_before_mutation(self, target, pre_audit):
        target_by_key = {_key(r): r for r in target}
        pre_by_key = {_key(r): r for r in pre_audit}
        for k in target_by_key:
            assert target_by_key[k].get('def_before') == pre_by_key[k].get('def_before'), (
                f'{k} def_before mutated'
            )


class TestFitState:
    def test_fit_c1_state(self, audit):
        fit_c1 = next((r for r in audit if _key(r) == ('fit', 'noun', 'C1')), None)
        assert fit_c1 is not None
        if fit_c1.get('fix_status') == 'gloss_review_log_20260630':
            return
        assert fit_c1.get('gloss_after') == 'medical seizure|coughing or laughing you cannot stop|sudden strong feeling'
        assert fit_c1.get('rule_applied') == '3sense_distinct_with_facet'
        assert fit_c1.get('review_needed') is True
        assert fit_c1.get('fix_status') == 'p15_simple_gloss_repaired'

    def test_fit_b2_state_unchanged(self, audit):
        fit_b2 = next((r for r in audit if _key(r) == ('fit', 'noun', 'B2')), None)
        assert fit_b2 is not None
        assert fit_b2.get('gloss_after') == 'size or suitability'
        assert fit_b2.get('fix_status') == 'p12_equiv_sense_semantic_hotfix'


class TestOutputSync:
    def test_txt_synced(self, audit, target_keys):
        if not TXT_PATH.exists():
            pytest.skip('TXT not present')
        txt_lines = TXT_PATH.read_text(encoding='utf-8').splitlines()
        txt_keys: dict[tuple, str] = {}
        for line in txt_lines:
            if line.startswith('#') or not line.strip():
                continue
            parts = line.split('\t')
            if len(parts) < 17:
                continue
            txt_k = (
                parts[3].strip().lower(),
                parts[4].strip().lower(),
                parts[14].strip().upper(),
            )
            txt_keys[txt_k] = parts[6].strip()
            
        audit_by_key = {_key(r): r for r in audit}
        for k in target_keys:
            if k in txt_keys:
                expected = audit_by_key[k].get('gloss_after', '').strip()
                assert txt_keys[k] == expected

    def test_jsonl_synced(self, audit, target_keys):
        if not JSONL_PATH.exists():
            pytest.skip('JSONL not present')
        jsonl_rows = [json.loads(l) for l in JSONL_PATH.read_text(encoding='utf-8').splitlines() if l.strip()]
        jsonl_by_key = {
            (r.get('word', '').strip().lower(),
             r.get('pos', '').strip().lower(),
             r.get('cefr', '').strip().upper()): r
            for r in jsonl_rows
        }
        audit_by_key = {_key(r): r for r in audit}
        for k in target_keys:
            jsonl_r = jsonl_by_key.get(k)
            if jsonl_r is not None:
                expected = audit_by_key[k].get('gloss_after', '').strip()
                assert (jsonl_r.get('definition') or '').strip() == expected


class TestGuardRefusal:
    def test_refuse_on_def_before_mismatch(self, monkeypatch):
        # Test that _apply_p15_full_simple_gloss_patch returns 1 if def_before mismatches
        from tools import _apply_p15_full_simple_gloss_patch
        
        # Mock load_jsonl to return rows with a def_before mismatch
        def mock_load_jsonl(path):
            if path == _apply_p15_full_simple_gloss_patch.AUDIT_PATH:
                return [
                    {"word": "adequate", "pos": "adjective", "cefr": "B2", "def_before": "mismatched", "gloss_after": "sufficient"}
                ] + [{"word": "dummy", "pos": "noun", "cefr": "C1", "def_before": "foo", "gloss_after": "bar"}] * 2486
            elif path == _apply_p15_full_simple_gloss_patch.INPUT_PATH:
                return [
                    {"word": "adequate", "pos": "adjective", "cefr": "B2", "def_before": "correct", "gloss_after": "enough"}
                ] + [{"word": "dummy", "pos": "noun", "cefr": "C1", "def_before": "foo", "gloss_after": "bar"}] * 2486
            return []
            
        monkeypatch.setattr(_apply_p15_full_simple_gloss_patch, '_load_jsonl', mock_load_jsonl)
        monkeypatch.setattr("sys.argv", ["_apply_p15_full_simple_gloss_patch"])
        assert _apply_p15_full_simple_gloss_patch.main() == 1
