from __future__ import annotations

from tools import sync_cambridge_pos_audio


def test_download_audio_requests_identity_encoding(monkeypatch, tmp_path):
    content = b"ID3" + (b"\x00" * 997)
    observed: dict[str, object] = {}

    class Response:
        status_code = 200

        def __init__(self) -> None:
            self.content = content

    def fake_get(url, *, headers, timeout):
        observed.update(url=url, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(sync_cambridge_pos_audio.requests, "get", fake_get)
    destination = tmp_path / "cambridge_us_word.mp3"

    assert sync_cambridge_pos_audio.download_audio(
        "/media/english/us_pron/w/wor/word/word.mp3",
        destination,
        apply=True,
    )
    assert observed == {
        "url": (
            "https://dictionary.cambridge.org"
            "/media/english/us_pron/w/wor/word/word.mp3"
        ),
        "headers": {
            "User-Agent": sync_cambridge_pos_audio.USER_AGENT,
            "Accept-Encoding": "identity",
        },
        "timeout": 30,
    }
    assert destination.read_bytes() == content
