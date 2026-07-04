"""Audio-reference validation for canonical deck artifacts."""
from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from src.deck_builder.build_issues import BuildIssue
from src.deck_builder.build_contracts import BuiltCard


SOUND_RE = re.compile(r"\[sound:([^\]]+)\]")


@dataclass(frozen=True, slots=True)
class AudioGateReport:
    issues: tuple[BuildIssue, ...]
    reference_count: int
    audio_file_count: int
    tracked_audio_file_count: int | None

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def error_text(self) -> str:
        return "\n".join(issue.format() for issue in self.issues if issue.severity == "error")


def _audio_names(audio_dir: Path) -> set[str]:
    if not audio_dir.exists():
        return set()
    return {path.name for path in audio_dir.iterdir() if path.is_file() and path.suffix.lower() == ".mp3"}


def tracked_audio_names_from_git(audio_dir: Path) -> set[str] | None:
    repo_root = audio_dir.parent
    if not (repo_root / ".git").exists():
        return None

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "audio"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    tracked = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            tracked.add(Path(line).name)
    return tracked


def _ref_count(cards: list[BuiltCard]) -> Counter[str]:
    refs: Counter[str] = Counter()
    for card in cards:
        refs.update(SOUND_RE.findall(card.uk_audio or ""))
        refs.update(SOUND_RE.findall(card.us_audio or ""))
    return refs


def validate_audio_gate(
    cards: list[BuiltCard],
    audio_dir: Path,
    tracked_audio_names: set[str] | None = None,
) -> AudioGateReport:
    actual_names = _audio_names(audio_dir)
    if tracked_audio_names is None:
        tracked_audio_names = tracked_audio_names_from_git(audio_dir)

    tracked_casefold = {name.lower(): name for name in tracked_audio_names or set()}
    actual_casefold = {name.lower(): name for name in actual_names}
    refs = _ref_count(cards)
    issues: list[BuildIssue] = []

    for ref, count in sorted(refs.items()):
        if "\\" in ref or "/" in ref or ".." in ref:
            issues.append(BuildIssue(
                "error",
                "audio_path_traversal",
                f"audio reference {ref!r} contains path traversal characters",
            ))
            continue

        if ref.startswith("tts_"):
            issues.append(BuildIssue(
                "error",
                "audio_tts_reference",
                f"deprecated TTS audio is still referenced: {ref!r} ({count} occurrence(s))",
            ))

        if ref not in actual_names:
            if ref.lower() in actual_casefold:
                issues.append(BuildIssue(
                    "error",
                    "audio_case_mismatch",
                    f"audio reference {ref!r} differs only by case from an on-disk file",
                ))
            else:
                issues.append(BuildIssue(
                    "error",
                    "audio_missing_reference",
                    f"audio reference {ref!r} is missing from {audio_dir}",
                ))
            continue

        if tracked_audio_names is not None and ref not in tracked_audio_names:
            issues.append(BuildIssue(
                "error",
                "audio_referenced_but_untracked",
                f"audio file {ref!r} is referenced by canonical artifacts but not tracked by git",
            ))
            if ref.lower() in tracked_casefold:
                issues.append(BuildIssue(
                    "error",
                    "audio_case_mismatch",
                    f"audio file {ref!r} differs only by case from tracked file {tracked_casefold[ref.lower()]!r}",
                ))

    for name in sorted(name for name in actual_names if name.startswith("tts_")):
        issues.append(BuildIssue(
            "error",
            "audio_tts_file_present",
            f"deprecated TTS audio file still exists on disk: {name!r}",
            source=audio_dir / name,
        ))

    return AudioGateReport(
        issues=tuple(issues),
        reference_count=sum(refs.values()),
        audio_file_count=len(actual_names),
        tracked_audio_file_count=None if tracked_audio_names is None else len(tracked_audio_names),
    )
