import json
import pytest
from pathlib import Path
from src.deck_builder.audit_patch import (
    AuditPatchPaths,
    AuditPatchResult,
    load_jsonl,
    write_jsonl_text,
    parse_txt_rows,
    replace_txt_definition_cells,
    match_by_guard,
    backup_and_write,
)

def test_load_jsonl(tmp_path):
    p = tmp_path / "test.jsonl"
    p.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
    assert load_jsonl(p) == [{"a": 1}, {"b": 2}]

def test_write_jsonl_text():
    rows = [{"a": 1}, {"b": 2}]
    assert write_jsonl_text(rows) == '{"a": 1}\n{"b": 2}\n'
    assert write_jsonl_text([]) == ""

def test_parse_txt_rows():
    txt = (
        "#header\n"
        "\n"
        "a\tb\tc\td\te\tf\tg\th\ti\tj\tk\tl\tm\tn\to\tp\tq\n"
        "short_row\n"
    )
    rows = parse_txt_rows(txt)
    assert len(rows) == 4
    assert rows[0] == "#header"
    assert rows[1] == ""
    assert isinstance(rows[2], list)
    assert len(rows[2]) == 17
    assert rows[3] == "short_row"

def test_replace_txt_definition_cells():
    txt = (
        "#header\n"
        "z1\ta\tb\tconquer\tverb\tf\told_def\tg\th\ti\tj\tk\tl\tm\tC1\to\tp\n"
        "z2\ta\tb\tconquer\tnoun\tf\told_noun\tg\th\ti\tj\tk\tl\tm\tC1\to\tp\n"
    )
    new_gloss = {
        ("conquer", "verb", "C1"): "new_def"
    }
    updated_txt, replaced, deferred = replace_txt_definition_cells(txt, new_gloss)
    assert replaced == 1
    assert deferred == set()
    assert "new_def" in updated_txt
    assert "old_noun" in updated_txt
    assert "old_def" not in updated_txt

def test_replace_txt_definition_cells_deferred():
    txt = "#header\n"
    new_gloss = {
        ("conquer", "verb", "C1"): "new_def"
    }
    updated_txt, replaced, deferred = replace_txt_definition_cells(txt, new_gloss)
    assert replaced == 0
    assert deferred == {("conquer", "verb", "C1")}

def test_match_by_guard_success():
    audit = [
        {"word": "conquer", "pos": "verb", "cefr": "C1", "val": 10},
        {"word": "happy", "pos": "adj", "cefr": "B2", "val": 20}
    ]
    decisions = [
        {"word": "conquer", "pos": "verb", "cefr": "C1", "decision": "y"}
    ]
    def guard(r):
        return (r["word"], r["pos"], r["cefr"])
        
    matched = match_by_guard(audit, decisions, guard)
    assert len(matched) == 1
    assert matched[("conquer", "verb", "C1")]["val"] == 10

def test_match_by_guard_unmatched():
    audit = [
        {"word": "happy", "pos": "adj", "cefr": "B2", "val": 20}
    ]
    decisions = [
        {"word": "conquer", "pos": "verb", "cefr": "C1", "decision": "y"}
    ]
    def guard(r):
        return (r["word"], r["pos"], r["cefr"])
        
    with pytest.raises(ValueError) as excinfo:
        match_by_guard(audit, decisions, guard)
    assert "NO AUDIT MATCH" in str(excinfo.value)
    assert "conquer" in str(excinfo.value)

def test_match_by_guard_ambiguous():
    audit = [
        {"word": "conquer", "pos": "verb", "cefr": "C1", "val": 10},
        {"word": "conquer", "pos": "verb", "cefr": "C1", "val": 15}
    ]
    decisions = [
        {"word": "conquer", "pos": "verb", "cefr": "C1", "decision": "y"}
    ]
    def guard(r):
        return (r["word"], r["pos"], r["cefr"])
        
    with pytest.raises(ValueError) as excinfo:
        match_by_guard(audit, decisions, guard)
    assert "AMBIGUOUS" in str(excinfo.value)

def test_backup_and_write(tmp_path):
    audit_file = tmp_path / "audit.jsonl"
    audit_file.write_text('{"a": 1}\n', encoding="utf-8")
    
    txt_file = tmp_path / "vocab.txt"
    txt_file.write_text("orig_txt\n", encoding="utf-8")
    
    ledger_file = tmp_path / "ledger.jsonl"
    ledger_file.write_text("orig_ledger\n", encoding="utf-8")
    
    paths = AuditPatchPaths(
        audit_jsonl_path=audit_file,
        txt_path=txt_file,
        ledger_path=ledger_file
    )
    
    result = AuditPatchResult(
        updated_audit_text='{"a": 2}\n',
        updated_txt_text="new_txt\n",
        matched_count=1,
        replaced_count=1,
        deferred_count=0,
        validation_errors=[]
    )
    
    backup_and_write(paths, result, "test_label")
    
    # Check that new files are written
    assert audit_file.read_text(encoding="utf-8") == '{"a": 2}\n'
    assert txt_file.read_text(encoding="utf-8") == "new_txt\n"
    
    # Check that backups exist
    audit_backups = list(tmp_path.glob("audit.jsonl.bak_pre_test_label_*"))
    assert len(audit_backups) == 1
    assert audit_backups[0].read_text(encoding="utf-8") == '{"a": 1}\n'
    
    txt_backups = list(tmp_path.glob("vocab.txt.bak_pre_test_label_*"))
    assert len(txt_backups) == 1
    assert txt_backups[0].read_text(encoding="utf-8") == "orig_txt\n"
    
    ledger_backups = list(tmp_path.glob("ledger.jsonl.bak_pre_test_label_*"))
    assert len(ledger_backups) == 1
    assert ledger_backups[0].read_text(encoding="utf-8") == "orig_ledger\n"
