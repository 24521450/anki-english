"""Structured build issues used by registry validation and future build gates."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.deck_builder.card_identity import CardIdentity


@dataclass(frozen=True, slots=True)
class BuildIssue:
    severity: str
    code: str
    message: str
    identity: CardIdentity | None = None
    source: Path | str | None = None

    def format(self) -> str:
        parts = [f"{self.severity}:{self.code}", self.message]
        if self.identity is not None:
            parts.append(f"identity={self.identity.as_key()}")
        if self.source is not None:
            parts.append(f"source={self.source}")
        return " | ".join(parts)


class BuildValidationError(RuntimeError):
    def __init__(self, issues: Iterable[BuildIssue]):
        self.issues = tuple(issues)
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        if not self.issues:
            return "Build validation failed"
        return "Build validation failed:\n" + "\n".join(
            f"- {issue.format()}" for issue in self.issues
        )
