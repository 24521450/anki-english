from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"


def _template() -> str:
    return BACK_TEMPLATE.read_text(encoding="utf-8")


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


def _run_highlight_cases(cases: list[list[str]]) -> list[str]:
    template = _template()
    functions = "\n".join(
        _extract_function(template, name)
        for name in (
            "trim",
            "escapeRegExp",
            "buildHeadwordForms",
            "highlightHeadword",
        )
    )
    runner = (
        functions
        + "\nconst cases = "
        + json.dumps(cases)
        + ";\nconsole.log(JSON.stringify(cases.map(c => highlightHeadword(c[0], c[1], c[2]))));"
    )
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _highlight(surface: str) -> str:
    return f'<span class="word-highlight">{surface}</span>'


def test_template_uses_morphological_highlighter_at_the_example_call_site():
    template = _template()

    assert "exLine = highlightHeadword(exLine, rawWord, rawPos);" in template
    assert "var wordRe = rawWord ? new RegExp" not in template


def test_regular_inflections_highlight_the_complete_surface_word():
    cases = [
        ["The wind had snapped the tree in two.", "snap", "verb"],
        ["They are snapping branches.", "snap", "verb"],
        ["This tax should be abolished.", "abolish", "verb"],
        ["Thousands migrated and are migrating.", "migrate", "verb"],
        ["She studies and studied hard.", "study", "verb"],
        ["The allies changed their capabilities.", "ally", "noun"],
        ["A bigger room was the biggest option.", "big", "adjective"],
    ]

    assert _run_highlight_cases(cases) == [
        f"The wind had {_highlight('snapped')} the tree in two.",
        f"They are {_highlight('snapping')} branches.",
        f"This tax should be {_highlight('abolished')}.",
        f"Thousands {_highlight('migrated')} and are {_highlight('migrating')}.",
        f"She {_highlight('studies')} and {_highlight('studied')} hard.",
        f"The {_highlight('allies')} changed their capabilities.",
        f"A {_highlight('bigger')} room was the {_highlight('biggest')} option.",
    ]


def test_current_deck_irregular_forms_are_highlighted_completely():
    irregulars = [
        ("bind", "bound", "verb"),
        ("breed", "bred", "verb"),
        ("cling", "clung", "verb"),
        ("creep", "crept", "verb"),
        ("equip", "equipped", "verb"),
        ("flee", "fled", "verb"),
        ("forbid", "forbade", "verb"),
        ("leap", "leapt", "verb"),
        ("mimic", "mimicking", "verb"),
        ("overcome", "overcame", "verb"),
        ("oversee", "oversaw", "verb"),
        ("phenomenon", "phenomena", "noun"),
        ("shrink", "shrank", "verb"),
        ("spoil", "spoilt", "verb"),
        ("swing", "swung", "verb"),
        ("tread", "trod", "verb"),
        ("uphold", "upheld", "verb"),
        ("weave", "woven", "verb"),
    ]
    cases = [[f"They used {surface} here.", word, pos] for word, surface, pos in irregulars]

    assert _run_highlight_cases(cases) == [
        f"They used {_highlight(surface)} here." for _, surface, _ in irregulars
    ]


def test_reviewed_spelling_variants_match_production_forms():
    cases = [
        ["The senator has the floor.", "have the floor", "phrase"],
        ["The amount of labour involved was high.", "labor", "noun"],
        ["Only 40 per cent voted.", "percent", "adjective, adverb"],
        ["St John was a saint.", "saint", "noun"],
        ["Billions of people were affected.", "billion", "number"],
    ]

    assert _run_highlight_cases(cases) == [
        f"The senator {_highlight('has the floor')}.",
        f"The amount of {_highlight('labour')} involved was high.",
        f"Only 40 {_highlight('per cent')} voted.",
        f"{_highlight('St')} John was a {_highlight('saint')}.",
        f"{_highlight('Billions')} of people were affected.",
    ]


def test_highlighter_rejects_prefixed_compound_and_derived_words():
    cases = [
        ["snap snapshot", "snap", "verb"],
        ["adequate inadequate", "adequate", "adjective"],
        ["counter counteract", "counter", "verb"],
        ["intent intention", "intent", "noun"],
        ["linear non-linear", "linear", "adjective"],
    ]

    assert _run_highlight_cases(cases) == [
        f"{_highlight('snap')} snapshot",
        f"{_highlight('adequate')} inadequate",
        f"{_highlight('counter')} counteract",
        f"{_highlight('intent')} intention",
        f"{_highlight('linear')} non-linear",
    ]


def test_sense_qualifier_is_removed_only_for_single_word_highlighting():
    cases = [
        ["the counter and a counteract example", "counter (long flat surface)", "noun"],
        ["Rules derive from evidence.", "derive from", "phrasal verb, verb"],
        ["The term is derived from Greek.", "derive from", "phrasal verb, verb"],
    ]

    assert _run_highlight_cases(cases) == [
        f"the {_highlight('counter')} and a counteract example",
        f"Rules {_highlight('derive from')} evidence.",
        "The term is derived from Greek.",
    ]


def test_relation_rendering_remains_compatible_with_strict_highlighting():
    template = _template()
    functions = "\n".join(
        _extract_function(template, name)
        for name in (
            "trim",
            "escapeRegExp",
            "buildHeadwordForms",
            "highlightHeadword",
            "renderRelations",
        )
    )
    runner = functions + """
const highlighted = highlightHeadword('adequate (inadequate)', 'adequate', 'adjective');
console.log(JSON.stringify(renderRelations(highlighted, [], ['inadequate'])));
"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout) == (
        f'{_highlight("adequate")} '
        '<span class="relation-antonym">(inadequate)</span>'
    )
