import json
from pathlib import Path

from tools.check_oxford_opal import audit_oxford_opal, inspect_cached_page, main


def _html(word: str, pos: str, *codes: str, senses: bool = True) -> bytes:
    attributes = []
    symbols = []
    if "W" in codes:
        attributes.append('opal_written="y"')
        symbols.append('<span class="opal_symbol" href="OPAL_Written::Sublist_1">OPAL W</span>')
    if "S" in codes:
        attributes.append('opal_spoken="y"')
        symbols.append('<span class="opal_symbol" href="OPAL_Spoken::Sublist_1">OPAL S</span>')
    senses_html = '<ol class="sense_single"><li class="sense"><span class="def">x</span></li></ol>' if senses else ""
    return (
        '<html><body><div class="entry"><div class="top-container">'
        '<div class="webtop">'
        f'<h1 class="headword" {" ".join(attributes)}>{word}</h1>'
        f'<span class="pos">{pos}</span><div class="symbols">{"".join(symbols)}</div>'
        f'</div>{senses_html}</div></div></body></html>'
    ).encode()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_inspect_cached_page_reads_scoped_membership_and_hub_pos():
    assert inspect_cached_page(_html("adapt", "verb", "W", "S")) == {
        "verb": ("W", "S")
    }
    assert inspect_cached_page(_html("derive", "verb", "W", "S", senses=False)) == {
        "verb": ("W", "S")
    }


def test_inspect_cached_page_handles_combined_pos_and_scoped_badge_fallback():
    combined = _html("OK", "adjective", senses=True).replace(
        b'<span class="pos">adjective</span>',
        b'<span class="pos">adjective<span class="sep">,</span> adverb</span>',
    ).replace(
        b'<div class="symbols"></div>',
        b'<div class="symbols"><span class="opal_symbol" '
        b'href="OPAL_Spoken::Sublist_1">OPAL S</span></div>',
    )

    assert inspect_cached_page(combined) == {"adjective": ("S",)}


def test_inspect_cached_page_ignores_unscoped_opal_symbol():
    raw = _html("plain", "adverb").replace(
        b"</body>",
        b'<div class="symbols"><span class="opal_symbol" '
        b'href="OPAL_Written::Sublist_1">OPAL W</span></div></body>',
    )

    assert inspect_cached_page(raw) is None


def test_audit_accepts_exact_single_and_merged_pos_maps(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "oxford_accordingly_(adv).html").write_bytes(_html("accordingly", "adverb", "W"))
    (cache / "oxford_need_1_(verb).html").write_bytes(_html("need", "verb", "S"))
    (cache / "oxford_need_2_(noun).html").write_bytes(_html("need", "noun", "W"))
    source = tmp_path / "oxford.jsonl"
    _write_jsonl(source, [
        {
            "word": "accordingly",
            "source_files": ["oxford_accordingly_(adv).html"],
            "opal": {"adverb": ["W"]},
        },
        {
            "word": "need",
            "source_files": ["oxford_need_1_(verb).html", "oxford_need_2_(noun).html"],
            "opal": {"verb": ["S"], "noun": ["W"]},
        },
    ])

    report = audit_oxford_opal(source, cache)

    assert report.ok
    assert report.labelled_pages == 3
    assert report.expected_opal_records == 2


def test_audit_reports_missing_extra_and_mismatched_metadata(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "oxford_missing_label.html").write_bytes(_html("missing-label", "adverb", "W"))
    (cache / "oxford_extra_label.html").write_bytes(_html("extra-label", "noun"))
    (cache / "oxford_wrong_label.html").write_bytes(_html("wrong-label", "verb", "S"))
    source = tmp_path / "oxford.jsonl"
    _write_jsonl(source, [
        {"word": "missing-label", "source_files": ["oxford_missing_label.html"], "opal": None},
        {"word": "extra-label", "source_files": ["oxford_extra_label.html"], "opal": {"noun": ["W"]}},
        {"word": "wrong-label", "source_files": ["oxford_wrong_label.html"], "opal": {"verb": ["W"]}},
    ])

    report = audit_oxford_opal(source, cache)

    assert not report.ok
    assert any("missing OPAL metadata" in issue for issue in report.issues)
    assert any("extra OPAL metadata" in issue for issue in report.issues)
    assert any("mismatch OPAL metadata" in issue for issue in report.issues)


def test_audit_reports_missing_cache_and_unaccounted_labelled_page(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "oxford_unaccounted.html").write_bytes(_html("unaccounted", "noun", "W"))
    source = tmp_path / "oxford.jsonl"
    _write_jsonl(source, [
        {"word": "gone", "source_files": ["oxford_gone.html"], "opal": None},
    ])

    report = audit_oxford_opal(source, cache)

    assert not report.ok
    assert any("missing cache file oxford_gone.html" in issue for issue in report.issues)
    assert any("not referenced by Oxford JSONL" in issue for issue in report.issues)


def test_cli_returns_nonzero_for_audit_failure(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "oxford_accordingly.html").write_bytes(_html("accordingly", "adverb", "W"))
    source = tmp_path / "oxford.jsonl"
    _write_jsonl(source, [
        {"word": "accordingly", "source_files": ["oxford_accordingly.html"], "opal": None},
    ])

    assert main(["--oxford-jsonl", str(source), "--cache-dir", str(cache)]) == 1
