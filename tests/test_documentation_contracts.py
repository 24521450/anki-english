from __future__ import annotations

import inspect
import re
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote

from src.config import ProjectPaths


ROOT = Path(__file__).resolve().parents[1]
CURRENT_GUIDANCE = [
    ROOT / "AGENTS.md",
    ROOT / "CONTEXT.md",
    ROOT / "USER_NOTES.md",
    ROOT / "data" / "README.md",
    ROOT / "tools" / "README.md",
    ROOT / "design" / "README.md",
    ROOT / "design" / "EAVM" / "README.md",
    ROOT / "docs" / "README.md",
    *sorted((ROOT / "docs" / "adr").glob("*.md")),
]
MARKDOWN_LINK = re.compile(r"!?\[[^]]*]\(([^)]+)\)")
ADR_FILENAME = re.compile(r"^(\d{4})-")


def _link_destination(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        return target[1 : target.index(">")]
    return target.split(maxsplit=1)[0]


def test_adr_numbers_are_unique() -> None:
    by_number: dict[str, list[str]] = {}
    for path in (ROOT / "docs" / "adr").glob("*.md"):
        match = ADR_FILENAME.match(path.name)
        assert match, f"ADR filename does not start with NNNN-: {path.name}"
        by_number.setdefault(match.group(1), []).append(path.name)

    duplicates = {
        number: names for number, names in by_number.items() if len(names) > 1
    }
    assert not duplicates, f"Duplicate ADR numbers: {duplicates}"


def test_current_documentation_has_portable_working_links() -> None:
    violations: list[str] = []

    for document in CURRENT_GUIDANCE:
        text = document.read_text(encoding="utf-8")
        if "file://" in text.casefold():
            violations.append(f"{document.relative_to(ROOT)}: contains file:// link")

        for match in MARKDOWN_LINK.finditer(text):
            target = _link_destination(match.group(1))
            folded = target.casefold()
            if folded.startswith(("http://", "https://", "mailto:")) or target.startswith("#"):
                continue
            if folded.startswith("file:") or target.startswith("/") or PureWindowsPath(target).is_absolute():
                violations.append(
                    f"{document.relative_to(ROOT)}: non-portable link {target!r}"
                )
                continue

            relative_target = unquote(target.split("#", 1)[0])
            if relative_target and not (document.parent / relative_target).exists():
                violations.append(
                    f"{document.relative_to(ROOT)}: broken link {target!r}"
                )

    assert not violations, "Documentation link violations:\n" + "\n".join(violations)


def test_design_readme_has_one_document_body() -> None:
    text = (ROOT / "design" / "README.md").read_text(encoding="utf-8")
    h1_lines = [line for line in text.splitlines() if line.startswith("# ")]
    assert h1_lines == ["# IELTS Anki Deck — Design"]


def test_data_readme_covers_file_artifacts_exposed_by_project_paths() -> None:
    paths = ProjectPaths(ROOT)
    data_readme = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    assert "| Path | Authority / role | Canonical writer | Manual edits? |" in data_readme

    undocumented: list[str] = []
    for name, descriptor in inspect.getmembers(ProjectPaths):
        if not isinstance(descriptor, property):
            continue
        value = getattr(paths, name)
        if not isinstance(value, Path):
            continue
        relative = value.relative_to(ROOT)
        if relative.parts[0] != "data" or not value.suffix:
            continue
        documented_path = "/".join(relative.parts[1:])
        if f"`{documented_path}`" not in data_readme:
            undocumented.append(f"{name} -> {documented_path}")

    assert not undocumented, "ProjectPaths artifacts missing ownership docs:\n" + "\n".join(undocumented)
