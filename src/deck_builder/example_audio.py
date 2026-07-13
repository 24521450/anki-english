"""Pure planning and resumable Edge TTS generation for example audio."""
from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.deck_builder.build_contracts import BuiltCard


EDGE_TTS_VERSION = "7.2.8"
CLEANER_VERSION = 1
RATE = "-5%"
PITCH = "+0Hz"
VOLUME = "+0%"
VOICES = {"uk": "en-GB-RyanNeural", "us": "en-US-JennyNeural"}
HTML_AUDIO_TEMPLATE = '<audio preload="none" src="{filename}"></audio>'
HTML_AUDIO_RE = re.compile(r'<audio\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>\s*</audio>', re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_PAREN_RE = re.compile(r"\([^()]*\)")
_DOUBLE_BREAK_RE = re.compile(r"(?:<br\s*/?>\s*){2}", re.I)


@dataclass(frozen=True, slots=True)
class ExampleAudioTask:
    filename: str
    text: str
    accent: str
    voice: str


@dataclass(frozen=True, slots=True)
class GenerationReport:
    required: int
    generated: int
    reused: int
    pruned: int
    dry_run: bool


def clean_example_text(value: str) -> str:
    """Return the stable utterance sent to TTS without changing display text."""
    text = html.unescape(value or "")
    text = _TAG_RE.sub(" ", text)
    text = re.sub(r"\ba\s*\(n\)", "an", text, flags=re.I)
    previous = None
    while previous != text:
        previous = text
        text = _PAREN_RE.sub(" ", text)
    text = re.sub(r"\bsb/sth\b", "somebody or something", text, flags=re.I)
    text = re.sub(r"\bsth/sb\b", "something or somebody", text, flags=re.I)
    text = re.sub(r"\bsb\b", "somebody", text, flags=re.I)
    text = re.sub(r"\bsth\b", "something", text, flags=re.I)
    text = re.sub(r"\s*/\s*", " or ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return unicodedata.normalize("NFC", text)


def _filename(text: str, accent: str) -> str:
    payload = json.dumps(
        {
            "cleaner": CLEANER_VERSION,
            "edge_tts": EDGE_TTS_VERSION,
            "pitch": PITCH,
            "rate": RATE,
            "text": text,
            "voice": VOICES[accent],
            "volume": VOLUME,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"example_{accent}_{digest}.mp3"


def _task(text: str, accent: str) -> ExampleAudioTask | None:
    cleaned = clean_example_text(text)
    if not cleaned:
        return None
    return ExampleAudioTask(_filename(cleaned, accent), cleaned, accent, VOICES[accent])


def _main_examples(value: str) -> list[list[str]]:
    if not value:
        return []
    return [
        [part for part in _DOUBLE_BREAK_RE.split(segment) if part.strip()]
        for segment in value.split("|")
    ]


def _idiom_examples(value: str) -> list[list[str]]:
    if not value:
        return []
    groups: list[list[str]] = []
    for entry in value.split("$$"):
        parts = entry.split("::")
        examples = parts[2].strip() if len(parts) >= 3 else ""
        groups.append([part for part in examples.split("|") if part.strip()])
    return groups


def _render_groups(groups: list[list[str]], accent: str, outer_separator: str) -> tuple[str, list[ExampleAudioTask]]:
    rendered: list[str] = []
    tasks: list[ExampleAudioTask] = []
    for group in groups:
        refs: list[str] = []
        for example in group:
            task = _task(example, accent)
            if task is None:
                raise ValueError(f"non-empty example became empty after audio cleaning: {example!r}")
            tasks.append(task)
            refs.append(HTML_AUDIO_TEMPLATE.format(filename=task.filename))
        rendered.append("<br><br>".join(refs) if outer_separator == "|" else "|".join(refs))
    return outer_separator.join(rendered), tasks


def plan_card_example_audio(card: BuiltCard) -> tuple[BuiltCard, tuple[ExampleAudioTask, ...]]:
    main_uk, tasks1 = _render_groups(_main_examples(card.example), "uk", "|")
    main_us, tasks2 = _render_groups(_main_examples(card.example), "us", "|")
    idiom_uk, tasks3 = _render_groups(_idiom_examples(card.idioms), "uk", "$$")
    idiom_us, tasks4 = _render_groups(_idiom_examples(card.idioms), "us", "$$")
    planned = card._replace(
        example_audio_uk=main_uk,
        example_audio_us=main_us,
        idiom_example_audio_uk=idiom_uk,
        idiom_example_audio_us=idiom_us,
    )
    return planned, tuple(tasks1 + tasks2 + tasks3 + tasks4)


def plan_cards_example_audio(cards: Iterable[BuiltCard]) -> tuple[list[BuiltCard], tuple[ExampleAudioTask, ...]]:
    planned: list[BuiltCard] = []
    by_filename: dict[str, ExampleAudioTask] = {}
    for card in cards:
        new_card, tasks = plan_card_example_audio(card)
        planned.append(new_card)
        for task in tasks:
            previous = by_filename.setdefault(task.filename, task)
            if previous != task:
                raise ValueError(f"example audio filename collision: {task.filename}")
    return planned, tuple(by_filename[name] for name in sorted(by_filename))


def referenced_example_audio_names(cards: Iterable[BuiltCard]) -> set[str]:
    names: set[str] = set()
    for card in cards:
        for field in (
            card.example_audio_uk, card.example_audio_us,
            card.idiom_example_audio_uk, card.idiom_example_audio_us,
        ):
            names.update(HTML_AUDIO_RE.findall(field or ""))
    return names


def is_valid_example_mp3(path: Path) -> bool:
    try:
        if path.stat().st_size < 512:
            return False
        with path.open("rb") as fh:
            header = fh.read(3)
    except OSError:
        return False
    return header == b"ID3" or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0)


async def generate_example_audio(
    cards: Iterable[BuiltCard],
    audio_dir: Path,
    *,
    dry_run: bool = False,
    concurrency: int = 4,
    retries: int = 5,
    prune: bool = True,
) -> GenerationReport:
    """Generate missing/invalid files; failed batches never prune valid media."""
    planned, tasks = plan_cards_example_audio(cards)
    del planned
    audio_dir.mkdir(parents=True, exist_ok=True) if not dry_run else None
    missing = [task for task in tasks if not is_valid_example_mp3(audio_dir / task.filename)]
    reused = len(tasks) - len(missing)
    if dry_run:
        stale = set(path.name for path in audio_dir.glob("example_*.mp3")) - {task.filename for task in tasks} if audio_dir.exists() else set()
        return GenerationReport(len(tasks), len(missing), reused, len(stale) if prune else 0, True)

    try:
        import edge_tts
    except ImportError as exc:  # pragma: no cover - environment/configuration failure
        raise RuntimeError("edge-tts==7.2.8 is required for example audio generation") from exc

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def generate_one(task: ExampleAudioTask) -> None:
        target = audio_dir / task.filename
        temporary = target.with_suffix(target.suffix + ".tmp")
        async with semaphore:
            last_error: Exception | None = None
            for attempt in range(retries):
                try:
                    temporary.unlink(missing_ok=True)
                    communicator = edge_tts.Communicate(
                        task.text, task.voice, rate=RATE, pitch=PITCH, volume=VOLUME,
                        connect_timeout=10, receive_timeout=60,
                    )
                    await communicator.save(str(temporary))
                    if not is_valid_example_mp3(temporary):
                        raise RuntimeError(f"Edge TTS returned invalid MP3 for {task.filename}")
                    os.replace(temporary, target)
                    return
                except Exception as exc:  # retry network and protocol failures uniformly
                    last_error = exc
                    temporary.unlink(missing_ok=True)
                    if attempt + 1 < retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
            raise RuntimeError(f"failed to generate {task.filename} after {retries} attempts") from last_error

    await asyncio.gather(*(generate_one(task) for task in missing))

    pruned = 0
    if prune:
        required = {task.filename for task in tasks}
        for path in sorted(audio_dir.glob("example_*.mp3")):
            if path.name not in required:
                path.unlink()
                pruned += 1
    return GenerationReport(len(tasks), len(missing), reused, pruned, False)


def validate_example_audio_alignment(card: BuiltCard) -> list[str]:
    """Return field-level alignment errors without touching the filesystem."""
    errors: list[str] = []
    expected, _ = plan_card_example_audio(card._replace(
        example_audio_uk="", example_audio_us="",
        idiom_example_audio_uk="", idiom_example_audio_us="",
    ))
    for name in (
        "example_audio_uk", "example_audio_us",
        "idiom_example_audio_uk", "idiom_example_audio_us",
    ):
        if getattr(card, name) != getattr(expected, name):
            errors.append(name)
    return errors
