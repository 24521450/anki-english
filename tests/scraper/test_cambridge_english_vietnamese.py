from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time

import jsonschema
import pytest

from src.scraper.cambridge_english_vietnamese import (
    CambridgeEnglishVietnameseParseError,
    lookup_headword_for,
    normalize_lookup_headword,
    parse_snapshot as _parse_snapshot,
    requested_url,
    validate_snapshot_rows,
)
from tools import sync_cambridge_english_vietnamese as sync


def parse_snapshot(*args, **kwargs):
    kwargs.setdefault(
        "response_url",
        requested_url(kwargs["lookup_headword"]),
    )
    return _parse_snapshot(*args, **kwargs)


FOUND_HTML = b"""
<html>
  <head>
    <meta charset="utf-8">
    <link rel="canonical"
      href="https://dictionary.cambridge.org/dictionary/english-vietnamese/abolish">
  </head>
  <body>
    <aside>
      <div class="entry-body__el">
        <span class="hw dhw">page furniture</span>
        <div class="def-block ddef_block">
          <div class="def ddef_d">must not be parsed</div>
          <span class="trans dtrans">khong duoc doc</span>
        </div>
      </div>
    </aside>
    <div class="pr dictionary">
      <div class="entry-body__el">
        <div class="pos-header dpos-h">
          <span class="hw dhw">abolish</span>
          <span class="pos dpos">verb</span>
          <span class="gram dgram">[ T ]</span>
        </div>
        <div class="def-block ddef_block" id="wordlist-sense-1">
          <div class="def ddef_d">to end a law or custom officially</div>
          <span class="trans dtrans">bai bo</span>
          <div class="examp dexamp">
            <span class="eg deg">They abolished the tax.</span>
            <span class="trans dtrans">Ho da bai bo thue.</span>
          </div>
        </div>
        <div class="def-block ddef_block">
          <div class="def ddef_d">to put an end to something</div>
          <div class="examp dexamp">
            <span class="eg deg">The rule was abolished.</span>
          </div>
        </div>
      </div>
    </div>
  </body>
</html>
"""
FETCH_HTML = FOUND_HTML.replace(
    b"/english-vietnamese/abolish",
    b"/english-vietnamese/test",
).replace(b">abolish<", b">test<")

REAL_SHAPE_HTML = """
<html>
  <head>
    <meta charset="utf-8">
    <link rel="canonical"
      href="https://dictionary.cambridge.org/dictionary/english-vietnamese/worthy">
  </head>
  <body>
    <div class="entry-body">
      <span class="link dlink">
        <div class="pr dictionary">
          <div class="d pr di english-vietnamese kdic">
            <div class="dpos-h di-head normal-entry">
              <h2 class="tw-bw dhw dpos-h_hw di-title">worthy</h2>
              <span class="pos dpos">adjective</span>
            </div>
            <div class="di-body normal-entry-body">
              <div class="pos-body">
                <div class="sense-block pr dsense dsense-noh">
                  <div class="cid" id="k-en-vi-pw-1-3"></div>
                  <div class="def-block ddef_block"
                    data-wl-senseid="PS00038380">
                    <div class="def ddef_d">
                      (with of) typical of, suited to, or in keeping with
                    </div>
                    <span class="trans dtrans">tiêu biểu cho</span>
                    <div class="examp dexamp">
                      <span class="eg deg">
                        a performance worthy of a champion.
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </span>
    </div>
  </body>
</html>
""".encode("utf-8")

DICTIONARY_HOME_FALLBACK_HTML = """
<html>
  <head>
    <meta charset="utf-8">
    <title>Cambridge English–Vietnamese Dictionary: Translate from English to Vietnamese</title>
    <link rel="canonical"
      href="https://dictionary.cambridge.org/dictionary/english-vietnamese/">
  </head>
  <body>
    <form id="searchForm">
      <input id="searchword" name="q">
    </form>
    <h1>English–Vietnamese Dictionary</h1>
    <section>
      <h2>Key features</h2>
      <p>Short, simple English definitions with Vietnamese translations.</p>
    </section>
  </body>
</html>
""".encode("utf-8")


def _request(**overrides):
    request = {
        "guid": "guid-1",
        "word": "abolish",
        "variant": "",
        "pos": "verb",
        "card_status": "active",
        "reason": "card_identity",
    }
    request.update(overrides)
    return request


def test_lookup_normalization_uses_only_reviewed_aliases():
    assert normalize_lookup_headword("  Grave (serious) ") == "grave"
    assert lookup_headword_for("Contend with sb/sth") == ("contend", "lookup_alias")
    assert lookup_headword_for("provisions") == ("provisions", "card_identity")
    assert lookup_headword_for("derived") == ("derived", "card_identity")


def test_parser_is_dictionary_scoped_and_retains_missing_translation():
    row = parse_snapshot(
        FOUND_HTML,
        lookup_headword="abolish",
        coverage_requests=[_request(guid="z"), _request(guid="a")],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
    )

    assert row["status"] == "found"
    assert row["resolved_headword"] == "abolish"
    assert [request["guid"] for request in row["coverage_requests"]] == ["a", "z"]
    assert len(row["entries"]) == 1
    entry = row["entries"][0]
    assert entry["pos"] == "verb"
    assert [sense["translation_status"] for sense in entry["senses"]] == [
        "found",
        "missing",
    ]
    assert entry["senses"][1]["translation_vi"] is None
    assert entry["senses"][0]["source_wordlist_sense_id"] == "wordlist-sense-1"
    assert row["record_fingerprint"] == parse_snapshot(
        FOUND_HTML,
        lookup_headword="abolish",
        coverage_requests=[_request(guid="a"), _request(guid="z")],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
    )["record_fingerprint"]


def test_parser_supports_the_live_k_dictionary_entry_shape():
    row = parse_snapshot(
        REAL_SHAPE_HTML,
        lookup_headword="worthy",
        coverage_requests=[_request(word="worthy", pos="adjective")],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
    )

    assert len(row["entries"]) == 1
    entry = row["entries"][0]
    assert entry["headword"] == "worthy"
    assert entry["pos"] == "adjective"
    assert len(entry["senses"]) == 1
    sense = entry["senses"][0]
    assert sense["source_wordlist_sense_id"] == "PS00038380"
    assert sense["definition_en"] == (
        "(with of) typical of, suited to, or in keeping with"
    )
    assert sense["translation_vi"] == "tiêu biểu cho"
    assert sense["examples"] == [{
        "text_en": "a performance worthy of a champion.",
        "translation_vi": None,
    }]


def test_example_translation_never_becomes_definition_translation():
    html = b"""
    <html><head><link rel="canonical"
      href="https://dictionary.cambridge.org/dictionary/english-vietnamese/test">
    </head><body><div class="pr dictionary">
      <div class="d pr di english-vietnamese kdic">
        <div class="dpos-h"><h2 class="dhw">test</h2><span class="pos">noun</span></div>
        <div class="sense-block">
          <div class="def ddef_d">a definition without a Vietnamese gloss</div>
          <div class="examp dexamp">
            <span class="eg deg">A translated example.</span>
            <span class="trans dtrans">Mot vi du da dich.</span>
          </div>
        </div>
      </div>
    </div></body></html>
    """
    row = parse_snapshot(
        html,
        lookup_headword="test",
        coverage_requests=[_request(word="test", pos="noun")],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
    )
    sense = row["entries"][0]["senses"][0]
    assert sense["translation_vi"] is None
    assert sense["translation_status"] == "missing"
    assert sense["examples"] == [{
        "text_en": "A translated example.",
        "translation_vi": "Mot vi du da dich.",
    }]


def test_duplicate_content_senses_keep_unique_ordinal_source_ids():
    html = b"""
    <html><head><link rel="canonical"
      href="https://dictionary.cambridge.org/dictionary/english-vietnamese/test">
    </head><body><div class="pr dictionary">
      <div class="d pr di english-vietnamese kdic">
        <div class="dpos-h"><h2 class="dhw">test</h2><span class="pos">noun</span></div>
        <div class="sense-block"><div class="def">same</div><span class="trans">giong</span></div>
        <div class="sense-block"><div class="def">same</div><span class="trans">giong</span></div>
      </div>
    </div></body></html>
    """
    row = parse_snapshot(
        html,
        lookup_headword="test",
        coverage_requests=[_request(word="test", pos="noun")],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
    )
    senses = row["entries"][0]["senses"]
    assert [sense["sense_order"] for sense in senses] == [1, 2]
    assert senses[0]["sense_fingerprint"] == senses[1]["sense_fingerprint"]
    assert senses[0]["source_sense_id"] != senses[1]["source_sense_id"]
    validate_snapshot_rows([row])

    duplicate_entry = json.loads(json.dumps(row["entries"][0]))
    duplicate_entry["entry_order"] = 2
    row["entries"].append(duplicate_entry)
    with pytest.raises(ValueError, match="duplicate source_entry_id"):
        validate_snapshot_rows([row])


def test_parser_requires_positive_no_entry_evidence():
    row = parse_snapshot(
        b"""
        <html><head><link rel='canonical'
          href='https://dictionary.cambridge.org/dictionary/english-vietnamese/zzz'>
        </head><body><div class='no-results'>No results for zzz</div></body></html>
        """,
        lookup_headword="zzz",
        coverage_requests=[_request()],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
        http_status=404,
    )
    assert row["status"] == "no_entry"
    assert row["entries"] == []

    with pytest.raises(CambridgeEnglishVietnameseParseError):
        parse_snapshot(
            b"<html><body>temporary upstream challenge</body></html>",
            lookup_headword="abolish",
            coverage_requests=[_request()],
            cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
        )

    with pytest.raises(CambridgeEnglishVietnameseParseError):
        parse_snapshot(
            b"<html><body>not found</body></html>",
            lookup_headword="abolish",
            coverage_requests=[_request()],
            cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
            http_status=404,
        )


@pytest.mark.parametrize(
    "lookup_headword",
    ["additionally", "arguably", "automate", "enquire", "footage", "impactful"],
)
def test_parser_recognizes_strict_dictionary_home_fallback(lookup_headword):
    row = parse_snapshot(
        DICTIONARY_HOME_FALLBACK_HTML,
        lookup_headword=lookup_headword,
        coverage_requests=[_request(word=lookup_headword)],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
        response_url=(
            "https://dictionary.cambridge.org/dictionary/english-vietnamese/"
        ),
    )
    assert row["status"] == "no_entry"
    assert row["canonical_url"] == (
        "https://dictionary.cambridge.org/dictionary/english-vietnamese/"
    )
    assert row["entries"] == []


def test_home_like_or_challenge_page_without_exact_signature_still_fails():
    wrong_canonical = DICTIONARY_HOME_FALLBACK_HTML.replace(
        b"/dictionary/english-vietnamese/\">",
        b"/dictionary/english-vietnamese/unknown\">",
    )
    with pytest.raises(CambridgeEnglishVietnameseParseError):
        parse_snapshot(
            wrong_canonical,
            lookup_headword="unknown",
            coverage_requests=[_request(word="unknown")],
            cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
        )


def test_response_url_allows_only_canonical_redirect_bound_to_requested_slug():
    redirected_html = FOUND_HTML.replace(
        b"/english-vietnamese/abolish",
        b"/english-vietnamese/accuse",
    ).replace(b">abolish<", b">accuse<")
    row = parse_snapshot(
        redirected_html,
        lookup_headword="accused",
        coverage_requests=[_request(word="accused")],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
        response_url=(
            "https://dictionary.cambridge.org/dictionary/"
            "english-vietnamese/accuse?q=accused"
        ),
    )
    assert row["response_url"].endswith("/accuse?q=accused")
    assert row["canonical_url"].endswith("/accuse")

    with pytest.raises(
        CambridgeEnglishVietnameseParseError,
        match="does not bind",
    ):
        parse_snapshot(
            redirected_html,
            lookup_headword="accused",
            coverage_requests=[_request(word="accused")],
            cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
            response_url=(
                "https://dictionary.cambridge.org/dictionary/"
                "english-vietnamese/accuse?q=someone-else"
            ),
        )


def test_pure_snapshot_validation_recomputes_fingerprints_and_exact_coverage():
    request = _request()
    row = parse_snapshot(
        FOUND_HTML,
        lookup_headword="abolish",
        coverage_requests=[request],
        cache_file="cambridge_english_vietnamese_1234567890abcdef.html",
    )
    plan = [{
        "lookup_headword": "abolish",
        "requested_url": row["requested_url"],
        "coverage_requests": [request],
    }]
    validate_snapshot_rows([row], expected_plan=plan)

    stale = json.loads(json.dumps(row))
    stale["entries"][0]["senses"][0]["translation_vi"] = "stale"
    with pytest.raises(ValueError, match="sense_fingerprint"):
        validate_snapshot_rows([stale], expected_plan=plan)

    with pytest.raises(ValueError, match="exact active Card Registry coverage"):
        validate_snapshot_rows([row], expected_plan=[])


def test_plan_groups_aliases_and_adds_bound_provisions(tmp_path: Path):
    registry = tmp_path / "registry.jsonl"
    rows = [
        {
            "guid": "guid-contend",
            "word": "contend",
            "variant": "",
            "pos": "verb",
            "status": "active",
        },
        {
            "guid": "guid-with",
            "word": "contend with sb/sth",
            "variant": "secondary",
            "pos": "phrasal verb",
            "status": "active",
        },
        {
            "guid": "guid-provision",
            "word": "provision",
            "variant": "",
            "pos": "noun",
            "status": "active",
        },
        {
            "guid": "retired",
            "word": "old",
            "variant": "",
            "pos": "adjective",
            "status": "retired",
        },
    ]
    registry.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    plan = sync.build_plan(registry)
    by_lookup = {item["lookup_headword"]: item for item in plan}
    assert set(by_lookup) == {"contend", "provision", "provisions"}
    assert [r["guid"] for r in by_lookup["contend"]["coverage_requests"]] == [
        "guid-contend",
        "guid-with",
    ]
    supplemental = by_lookup["provisions"]["coverage_requests"]
    assert supplemental == [{
        "guid": "guid-provision",
        "word": "provision",
        "variant": "",
        "pos": "noun",
        "card_status": "active",
        "reason": "lexicalized_plural_source_evidence",
    }]


def test_supplemental_provisions_stays_with_primary_after_split(tmp_path: Path):
    registry = tmp_path / "registry.jsonl"
    rows = [
        {
            "guid": "primary-guid",
            "word": "provision",
            "variant": "primary",
            "pos": "noun",
            "status": "active",
        },
        {
            "guid": "000-secondary",
            "word": "provision",
            "variant": "secondary_legal_condition",
            "pos": "noun",
            "status": "active",
        },
    ]
    registry.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    plan = sync.build_plan(registry)
    provisions = next(
        item for item in plan if item["lookup_headword"] == "provisions"
    )
    assert provisions["coverage_requests"] == [{
        "guid": "primary-guid",
        "word": "provision",
        "variant": "primary",
        "pos": "noun",
        "card_status": "active",
        "reason": "lexicalized_plural_source_evidence",
    }]


@pytest.mark.parametrize(
    "rows",
    [
        [
            {"guid": "a", "word": "provision", "variant": "primary", "pos": "noun", "status": "active"},
            {"guid": "b", "word": "provision", "variant": "primary", "pos": "noun", "status": "active"},
        ],
        [
            {"guid": "a", "word": "provision", "variant": "secondary", "pos": "noun", "status": "active"},
        ],
        [
            {"guid": "a", "word": "provision", "variant": "", "pos": "noun", "status": "active"},
            {"guid": "b", "word": "provision", "variant": "secondary", "pos": "noun", "status": "active"},
        ],
    ],
)
def test_supplemental_provisions_rejects_missing_or_ambiguous_owner(rows):
    with pytest.raises(ValueError, match="exactly one active"):
        from src.scraper.cambridge_english_vietnamese import build_lookup_plan

        build_lookup_plan(rows)


def test_plan_without_provision_does_not_invent_supplemental_owner():
    from src.scraper.cambridge_english_vietnamese import build_lookup_plan

    plan = build_lookup_plan([
        {
            "guid": "guid-abolish",
            "word": "abolish",
            "variant": "",
            "pos": "verb",
            "status": "active",
        },
    ])

    assert [item["lookup_headword"] for item in plan] == ["abolish"]


def test_build_apply_check_and_schema_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    registry = tmp_path / "registry.jsonl"
    registry.write_text(
        json.dumps({
            "guid": "guid-1",
            "word": "abolish",
            "variant": "",
            "pos": "verb",
            "status": "active",
        }) + "\n",
        encoding="utf-8",
    )
    cache_dir = tmp_path / "cache"
    cache_path = sync._cache_path(cache_dir, "abolish")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(FOUND_HTML)
    item = {
        "lookup_headword": "abolish",
        "requested_url": requested_url("abolish"),
        "coverage_requests": [_request()],
    }
    sync._metadata_path(cache_path).write_text(
        json.dumps(sync._cache_metadata(
            item,
            response_url=requested_url("abolish"),
            http_status=200,
            body=FOUND_HTML,
        )),
        encoding="utf-8",
    )
    monkeypatch.setattr(sync, "build_plan", lambda _path: [item])
    source = tmp_path / "snapshot.jsonl"
    schema = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "schema"
        / "cambridge_english_vietnamese_record.schema.json"
    )
    common = [
        "--registry", str(registry),
        "--cache-dir", str(cache_dir),
        "--source", str(source),
        "--schema", str(schema),
    ]

    assert sync.main([*common, "build", "--apply"]) == 0
    assert sync.main([*common, "build", "--check"]) == 0
    assert sync.main([*common, "validate"]) == 0
    row = json.loads(source.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(
        json.loads(schema.read_text(encoding="utf-8"))
    ).validate(row)

    source.write_text("{}\n", encoding="utf-8")
    assert sync.main([*common, "build", "--check"]) == 1


def test_transient_http_failure_never_writes_absence_cache(tmp_path: Path):
    class Response:
        status = 503
        url = "https://dictionary.cambridge.org/dictionary/english-vietnamese/test"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def read(self):
            return b"temporary"

    class Session:
        def get(self, _url):
            return Response()

    item = {
        "lookup_headword": "test",
        "requested_url": Response.url,
        "coverage_requests": [_request()],
    }
    with pytest.raises(RuntimeError, match="transient HTTP 503"):
        asyncio.run(sync._fetch_one(
            Session(),
            asyncio.Semaphore(1),
            item,
            tmp_path,
            max_attempts=1,
        ))
    assert list(tmp_path.iterdir()) == []


def test_fetch_retries_429_honoring_retry_after_then_caches_success(tmp_path: Path):
    class Response:
        def __init__(self, status, body, headers=None):
            self.status = status
            self.body = body
            self.headers = headers or {}
            self.url = "https://dictionary.cambridge.org/dictionary/english-vietnamese/test"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def read(self):
            return self.body

    class Session:
        def __init__(self):
            self.responses = [
                Response(429, b"rate limited", {"Retry-After": "7"}),
                Response(200, FETCH_HTML),
            ]

        def get(self, _url):
            return self.responses.pop(0)

    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    item = {
        "lookup_headword": "test",
        "requested_url": Response(200, b"").url,
        "coverage_requests": [_request()],
    }
    result = asyncio.run(sync._fetch_one(
        Session(),
        asyncio.Semaphore(1),
        item,
        tmp_path,
        max_attempts=3,
        backoff_base=1,
        backoff_max=10,
        sleep=fake_sleep,
    ))

    assert result == "fetched"
    assert delays == [7.0]
    cache_path = sync._cache_path(tmp_path, "test")
    assert cache_path.read_bytes() == FETCH_HTML
    assert json.loads(sync._metadata_path(cache_path).read_text(encoding="utf-8"))[
        "http_status"
    ] == 200


def test_fetch_uses_bounded_exponential_backoff_for_5xx(tmp_path: Path):
    class Response:
        url = "https://dictionary.cambridge.org/dictionary/english-vietnamese/test"
        headers = {}

        def __init__(self, status):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def read(self):
            return FETCH_HTML

    class Session:
        def __init__(self):
            self.responses = [Response(503), Response(502), Response(200)]

        def get(self, _url):
            return self.responses.pop(0)

    delays = []

    async def fake_sleep(delay):
        delays.append(delay)

    item = {
        "lookup_headword": "test",
        "requested_url": Response.url,
        "coverage_requests": [_request()],
    }
    assert asyncio.run(sync._fetch_one(
        Session(),
        asyncio.Semaphore(1),
        item,
        tmp_path,
        max_attempts=4,
        backoff_base=2,
        backoff_max=3,
        sleep=fake_sleep,
    )) == "fetched"
    assert delays == [2, 3]
    assert sync._retry_delay(
        20,
        {},
        backoff_base=2,
        backoff_max=3,
    ) == 3


def test_fetch_resume_reuses_complete_cache_without_network(tmp_path: Path):
    item = {
        "lookup_headword": "test",
        "requested_url": "https://dictionary.cambridge.org/dictionary/english-vietnamese/test",
        "coverage_requests": [_request()],
    }
    cache_path = sync._cache_path(tmp_path, "test")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(FETCH_HTML)
    sync._metadata_path(cache_path).write_text(
        json.dumps(sync._cache_metadata(
            item,
            response_url=item["requested_url"],
            http_status=200,
            body=FETCH_HTML,
        )),
        encoding="utf-8",
    )

    class Session:
        def get(self, _url):
            raise AssertionError("network must not be called for complete cache")

    assert asyncio.run(sync._fetch_one(
        Session(),
        asyncio.Semaphore(1),
        item,
        tmp_path,
    )) == "cached"


def test_legacy_cache_metadata_migrates_only_after_body_url_proof(tmp_path: Path):
    item = {
        "lookup_headword": "abolish",
        "requested_url": requested_url("abolish"),
        "coverage_requests": [_request()],
    }
    cache_path = sync._cache_path(tmp_path, "abolish")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(FOUND_HTML)
    sync._metadata_path(cache_path).write_text(json.dumps({
        "requested_url": item["requested_url"],
        "response_url": item["requested_url"],
        "http_status": 200,
    }), encoding="utf-8")

    body, metadata = sync._validate_cache_pair(
        cache_path,
        item,
        allow_legacy_migration=True,
    )
    assert body == FOUND_HTML
    assert set(metadata) == sync._CACHE_METADATA_KEYS
    assert metadata["lookup_headword"] == "abolish"
    assert metadata["html_sha256"] == hashlib.sha256(FOUND_HTML).hexdigest()


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"state": "publishing"},
        {
            "lookup_headword": "wrong",
            "requested_url": "https://dictionary.cambridge.org/dictionary/english-vietnamese/test",
            "response_url": "https://dictionary.cambridge.org/dictionary/english-vietnamese/test",
            "http_status": 200,
            "html_sha256": hashlib.sha256(FOUND_HTML).hexdigest(),
        },
        {
            "lookup_headword": "test",
            "requested_url": "https://dictionary.cambridge.org/dictionary/english-vietnamese/test",
            "response_url": "https://evil.example/dictionary/english-vietnamese/test",
            "http_status": 200,
            "html_sha256": hashlib.sha256(FOUND_HTML).hexdigest(),
        },
    ],
)
def test_cache_pair_rejects_partial_or_mismatched_metadata(tmp_path: Path, metadata):
    item = {
        "lookup_headword": "test",
        "requested_url": requested_url("test"),
        "coverage_requests": [_request(word="test")],
    }
    cache_path = sync._cache_path(tmp_path, "test")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(FOUND_HTML)
    sync._metadata_path(cache_path).write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    with pytest.raises((ValueError, CambridgeEnglishVietnameseParseError)):
        sync._validate_cache_pair(
            cache_path,
            item,
            allow_legacy_migration=False,
        )


def test_pair_publication_invalidates_metadata_before_replacing_html(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    item = {
        "lookup_headword": "test",
        "requested_url": requested_url("test"),
        "coverage_requests": [_request(word="test")],
    }
    cache_path = sync._cache_path(tmp_path, "test")
    original_write = sync._atomic_write
    calls = 0

    def interrupted_write(path, payload):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated interruption before final metadata")
        original_write(path, payload)

    monkeypatch.setattr(sync, "_atomic_write", interrupted_write)
    with pytest.raises(OSError, match="simulated interruption"):
        sync._publish_cache_pair(
            cache_path,
            item,
            response_url=requested_url("test"),
            http_status=200,
            body=FOUND_HTML,
        )
    assert json.loads(
        sync._metadata_path(cache_path).read_text(encoding="utf-8")
    ) == {"state": "publishing"}
    with pytest.raises(ValueError, match="partial or unsupported"):
        sync._validate_cache_pair(
            cache_path,
            item,
            allow_legacy_migration=False,
        )


def test_retry_after_http_date_and_operational_maximum():
    now = datetime(2026, 7, 24, tzinfo=timezone.utc)
    retry_at = now + timedelta(seconds=120)
    assert sync._retry_after_seconds(
        {"Retry-After": retry_at.strftime("%a, %d %b %Y %H:%M:%S GMT")},
        now=now,
    ) == 120
    with pytest.raises(RuntimeError, match="exceeds operational maximum"):
        sync._retry_after_seconds(
            {"Retry-After": str(sync.MAX_RETRY_AFTER + 1)}
        )


def test_request_pacer_applies_deferred_cooldown_to_multiple_workers():
    async def exercise():
        pacer = sync._RequestPacer(0)
        await pacer.defer(0.04)
        started = time.monotonic()
        await asyncio.gather(pacer.wait(), pacer.wait())
        return time.monotonic() - started

    assert asyncio.run(exercise()) >= 0.03
