from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
BUILD_JSONL = ROOT / "data" / "build" / "anki_notes.jsonl"


def _extract_function(src: str, func_name: str) -> str:
    match = re.search(rf"function\s+{func_name}\s*\([^)]*\)\s*\{{", src)
    if not match:
        raise ValueError(f"Function {func_name} not found")

    depth = 0
    in_string = None
    escaped = False
    for index in range(match.end() - 1, len(src)):
        char = src[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if in_string:
            if char == in_string:
                in_string = None
            continue
        if char in ("'", '"', "`"):
            in_string = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return src[match.start() : index + 1]
    raise ValueError(f"Unmatched braces in function {func_name}")


def _run_relation_cases(cases: list[dict[str, object]]) -> list[str]:
    template = BACK_TEMPLATE.read_text(encoding="utf-8")
    functions = "\n".join(
        _extract_function(template, name) for name in ("trim", "renderRelations")
    )
    runner = functions + """
const fs = require('fs');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const rendered = cases.map(c => renderRelations(c.example, c.synonyms, c.antonyms));
process.stdout.write(JSON.stringify(rendered));
"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        input=json.dumps(cases),
        env=env,
        timeout=15,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _relation_items(value: str) -> set[str]:
    return {
        item.strip().lower()
        for item in re.sub(r"^=\s*", "", value.strip()).split(",")
        if item.strip()
    }


def _metadata_items(value: str) -> set[str]:
    return {item.strip().lower() for item in value.split(",") if item.strip()}


def test_renderer_colors_relation_subsets_grouped_relations_and_equals_form():
    cases = [
        {
            "example": "Food passes through the gut (intestine).",
            "synonyms": ["intestine", "belly"],
            "antonyms": [],
        },
        {
            "example": "He had a bit of a gut (belly) on him.",
            "synonyms": ["intestine", "belly"],
            "antonyms": [],
        },
        {
            "example": "Fish are abundant (= plentiful, copious) in the lake.",
            "synonyms": ["plentiful", "copious"],
            "antonyms": [],
        },
        {
            "example": "The wings are transparent (opaque).",
            "synonyms": [],
            "antonyms": ["opaque"],
        },
    ]

    assert _run_relation_cases(cases) == [
        'Food passes through the gut <span class="relation-synonym">(intestine)</span>.',
        'He had a bit of a gut <span class="relation-synonym">(belly)</span> on him.',
        'Fish are abundant <span class="relation-synonym">(= plentiful, copious)</span> in the lake.',
        'The wings are transparent <span class="relation-antonym">(opaque)</span>.',
    ]


def test_renderer_leaves_natural_and_ambiguous_parentheticals_unchanged():
    cases = [
        {
            "example": "It can take up to 72 hours (or longer).",
            "synonyms": ["intestine"],
            "antonyms": [],
        },
        {
            "example": "The result was clear (plain).",
            "synonyms": ["plain"],
            "antonyms": ["plain"],
        },
    ]

    assert _run_relation_cases(cases) == [
        "It can take up to 72 hours (or longer).",
        "The result was clear (plain).",
    ]


def test_current_build_relation_metadata_is_renderable_by_the_actual_template():
    rows = [
        json.loads(line)
        for line in BUILD_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cases: list[dict[str, object]] = []
    expected: list[tuple[str, str, set[str], set[str]]] = []

    for row in rows:
        example_cells = row["example"].split("|")
        synonym_cells = row["synonyms"].split("|") if row["synonyms"] else []
        antonym_cells = row["antonyms"].split("|") if row["antonyms"] else []
        for index, example in enumerate(example_cells):
            synonym_cell = synonym_cells[index] if index < len(synonym_cells) else ""
            antonym_cell = antonym_cells[index] if index < len(antonym_cells) else ""
            synonyms = _metadata_items(synonym_cell)
            antonyms = _metadata_items(antonym_cell)
            if not synonyms and not antonyms:
                continue
            cases.append(
                {
                    "example": example,
                    "synonyms": sorted(synonyms),
                    "antonyms": sorted(antonyms),
                }
            )
            expected.append((row["word"], row["cefr"], synonyms, antonyms))

    rendered_cells = _run_relation_cases(cases)
    failures: list[str] = []
    for rendered, (word, cefr, synonyms, antonyms) in zip(rendered_cells, expected):
        rendered_synonyms: set[str] = set()
        rendered_antonyms: set[str] = set()
        for value in re.findall(
            r'<span class="relation-synonym">\(([^()]*)\)</span>', rendered
        ):
            rendered_synonyms.update(_relation_items(value))
        for value in re.findall(
            r'<span class="relation-antonym">\(([^()]*)\)</span>', rendered
        ):
            rendered_antonyms.update(_relation_items(value))
        if rendered_synonyms != synonyms or rendered_antonyms != antonyms:
            failures.append(
                f"{word}|{cefr}: expected syn={sorted(synonyms)} ant={sorted(antonyms)}, "
                f"rendered syn={sorted(rendered_synonyms)} ant={sorted(rendered_antonyms)}"
            )

    assert not failures, "\n".join(failures[:20])
