from __future__ import annotations

from src.scraper.cambridge import parse_cambridge
from src.scraper.merge import merge_word_records
from src.scraper.oxford import parse_oxford


def _cambridge_entry(
    entry_id: str,
    headword: str,
    pos: str,
    uk_ipa: str | None,
    us_ipa: str | None,
    *,
    uk_audio: str | None = None,
    us_audio: str | None = None,
) -> str:
    def accent_html(accent: str, ipa: str | None, audio: str | None) -> str:
        if ipa is None and audio is None:
            return ""
        source = (
            f'<audio><source type="audio/mpeg" src="{audio}"></audio>'
            if audio
            else ""
        )
        ipa_html = f'<span class="ipa dipa">{ipa}</span>' if ipa else ""
        return f'<span class="{accent} dpron-i">{source}{ipa_html}</span>'

    return f"""
    <div class="pr entry-body__el">
      <div class="cid" id="{entry_id}"></div>
      <div class="pos-header dpos-h">
        <span class="headword"><span class="hw dhw">{headword}</span></span>
        <div class="posgram dpos-g"><span class="pos dpos">{pos}</span></div>
        {accent_html("uk", uk_ipa, uk_audio)}
        {accent_html("us", us_ipa, us_audio)}
      </div>
    </div>
    """


def _cambridge_page(*entries: str) -> bytes:
    return (
        '<html><head><meta charset="utf-8"></head><body>'
        + "".join(entries)
        + "</body></html>"
    ).encode()


def _oxford_page(
    word: str,
    homonym: int,
    pos: str,
    uk_ipa: str,
    us_ipa: str,
    uk_audio: str,
    us_audio: str,
) -> bytes:
    return f"""
    <html><head><meta charset="utf-8"></head><body><div class="entry" id="{word}{homonym}_1">
      <div class="top-container"><div class="top-g"><div class="webtop">
        <h1 class="headword">{word}<span class="hm">{homonym}</span></h1>
        <span class="pos">{pos}</span>
        <span class="phonetics">
          <div class="phons_br"><div class="sound audio_play_button"
            data-src-mp3="{uk_audio}"></div><span class="phon">/{uk_ipa}/</span></div>
          <div class="phons_n_am"><div class="sound audio_play_button"
            data-src-mp3="{us_audio}"></div><span class="phon">/{us_ipa}/</span></div>
        </span>
      </div></div>
      <ol class="sense_single"><li class="sense"><span class="def">meaning</span></li></ol>
      </div>
    </div></body></html>
    """.encode()


def test_cambridge_diverse_keeps_entry_scoped_accents_and_dictionary_ranks():
    parsed = parse_cambridge(
        _cambridge_page(
            _cambridge_entry(
                "cald4-1",
                "diverse",
                "adjective",
                "daɪˈvɜːs",
                "dɪˈvɝːs",
                uk_audio="/media/english/uk_pron/diverse.mp3",
                us_audio="/media/english/us_pron/diverse.mp3",
            ),
            _cambridge_entry(
                "cacd-1",
                "diverse",
                "adjective",
                None,
                "dɪˈvɜrs",
                us_audio="/media/english/us_pron/diverse-us.mp3",
            ),
        ),
        source_files=["cambridge_diverse.html"],
    )

    assert parsed["pronunciations"] == [
        {
            "source_file": "cambridge_diverse.html",
            "dictionary_id": "cald4",
            "dictionary_rank": 0,
            "entry_id": "cald4-1",
            "entry_index": 1,
            "headword": "diverse",
            "pos": ["adjective"],
            "uk": {
                "ipa": "daɪˈvɜːs",
                "audio_url": "/media/english/uk_pron/diverse.mp3",
            },
            "us": {
                "ipa": "dɪˈvɝːs",
                "audio_url": "/media/english/us_pron/diverse.mp3",
            },
        },
        {
            "source_file": "cambridge_diverse.html",
            "dictionary_id": "cacd",
            "dictionary_rank": 1,
            "entry_id": "cacd-1",
            "entry_index": 2,
            "headword": "diverse",
            "pos": ["adjective"],
            "uk": {"ipa": None, "audio_url": None},
            "us": {
                "ipa": "dɪˈvɜrs",
                "audio_url": "/media/english/us_pron/diverse-us.mp3",
            },
        },
    ]


def test_cambridge_extract_keeps_pos_specific_entries():
    parsed = parse_cambridge(
        _cambridge_page(
            _cambridge_entry(
                "cald4-1", "extract", "verb", "ɪkˈstrækt", "ɪkˈstrækt",
                uk_audio="/media/english/uk_pron/extract-verb.mp3",
                us_audio="/media/english/us_pron/extract-verb.mp3",
            ),
            _cambridge_entry(
                "cald4-2", "extract", "noun", "ˈek.strækt", "ˈek.strækt",
                uk_audio="/media/english/uk_pron/extract-noun.mp3",
                us_audio="/media/english/us_pron/extract-noun.mp3",
            ),
        ),
        source_files=["cambridge_extract.html"],
    )

    assert [(item["pos"], item["uk"]["ipa"]) for item in parsed["pronunciations"]] == [
        (["verb"], "ɪkˈstrækt"),
        (["noun"], "ˈek.strækt"),
    ]


def test_oxford_bow_keeps_each_homograph_pronunciation_entry():
    bow_one = parse_oxford(
        _oxford_page(
            "bow", 1, "noun", "baʊ", "baʊ",
            "https://www.oxfordlearnersdictionaries.com/media/english/uk_pron/bow1.mp3",
            "https://www.oxfordlearnersdictionaries.com/media/english/us_pron/bow1.mp3",
        ),
        source_files=["oxford_bow1_(noun).html"],
    )
    bow_two = parse_oxford(
        _oxford_page(
            "bow", 2, "noun", "bəʊ", "boʊ",
            "https://www.oxfordlearnersdictionaries.com/media/english/uk_pron/bow2.mp3",
            "https://www.oxfordlearnersdictionaries.com/media/english/us_pron/bow2.mp3",
        ),
        source_files=["oxford_bow2_(noun).html"],
    )

    assert bow_one["pronunciations"][0]["uk"]["ipa"] == "/baʊ/"
    assert bow_two["pronunciations"][0]["us"]["ipa"] == "/boʊ/"
    assert bow_one["pronunciations"][0]["entry_id"] == "bow1_1"
    assert bow_two["pronunciations"][0]["entry_id"] == "bow2_1"


def test_oxford_merge_unions_entry_scoped_pronunciations_deterministically():
    verb = parse_oxford(
        _oxford_page(
            "extract", 1, "verb", "ɪkˈstrækt", "ɪkˈstrækt",
            "https://www.oxfordlearnersdictionaries.com/media/english/uk_pron/extract-v.mp3",
            "https://www.oxfordlearnersdictionaries.com/media/english/us_pron/extract-v.mp3",
        ),
        source_files=["oxford_extract_(verb).html"],
    )
    noun = parse_oxford(
        _oxford_page(
            "extract", 1, "noun", "ˈekstrækt", "ˈekstrækt",
            "https://www.oxfordlearnersdictionaries.com/media/english/uk_pron/extract-n.mp3",
            "https://www.oxfordlearnersdictionaries.com/media/english/us_pron/extract-n.mp3",
        ),
        source_files=["oxford_extract_1_(noun).html"],
    )

    merged = merge_word_records([verb, noun])
    assert [item["source_file"] for item in merged["pronunciations"]] == [
        "oxford_extract_(verb).html",
        "oxford_extract_1_(noun).html",
    ]
