import copy

from tools import ci_hydrate_parser_fixtures as hydrator


def test_hydrate_oxford_ignores_pos_source_url(tmp_path, monkeypatch):
    record = {
        "file": "oxford_linger_(verb).html",
        "word": "linger",
        "source_url": None,
        "pos_data": [
            {
                "pos": "verb",
                "definitions": [],
                "register_tags": [],
            }
        ],
    }
    parsed = copy.deepcopy(record)
    parsed["source_url"] = (
        "https://www.oxfordlearnersdictionaries.com/definition/english/linger"
    )
    parsed["pos_data"][0]["source_url"] = parsed["source_url"]

    monkeypatch.setattr(hydrator, "OXFORD_CACHE", tmp_path)
    monkeypatch.setattr(hydrator, "_fetch", lambda _url: b"valid Oxford HTML")
    monkeypatch.setattr(hydrator, "parse_oxford", lambda *_args, **_kwargs: parsed)

    result = hydrator._hydrate_oxford_record(record, force=False)

    assert result.startswith("ok oxford_linger_(verb).html <- ")
    assert (tmp_path / record["file"]).read_bytes() == b"valid Oxford HTML"
