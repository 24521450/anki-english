from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


TEMPLATE = Path("design/EAVM/production_front_template.txt")


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _script() -> str:
    template = _template()
    return template.split("<script>", 1)[1].split("</script>", 1)[0]


def _function_source() -> str:
    script = _script()
    start = script.index("(function() {") + len("(function() {")
    end = script.index("  var rawAnswer =")
    return script[start:end]


def _run_node(expression: str):
    runner = f"{_function_source()}\nconsole.log(JSON.stringify({expression}));"
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    result = subprocess.run(
        ["node"],
        input=runner,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        env=env,
    )
    return json.loads(result.stdout)


def test_production_template_javascript_is_valid():
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    subprocess.run(
        ["node", "--check"],
        input=_script(),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
        env=env,
    )


def test_reviewed_irregular_and_spelling_forms_are_clozed():
    cases = [
        ["The rabbits are bred for their coats.", "breed", "noun, verb"],
        ["The court upheld the conviction.", "uphold", "verb"],
        ["The amount of labour involved was high.", "labor", "noun"],
        ["Only 40 per cent voted.", "percent", "adjective, adverb"],
        ["St John was a saint.", "saint", "noun"],
        ["She has enough time.", "have", "verb"],
        ["Billions of germs are present.", "billion", "number"],
    ]
    results = _run_node(
        f"{json.dumps(cases)}.map(c => clozeProductionText(c[0], c[1], c[2]))"
    )

    assert results == [
        {"text": "The rabbits are […] for their coats.", "complete": True, "maskCount": 1},
        {"text": "The court […] the conviction.", "complete": True, "maskCount": 1},
        {"text": "The amount of […] involved was high.", "complete": True, "maskCount": 1},
        {"text": "Only 40 […] voted.", "complete": True, "maskCount": 1},
        {"text": "[…] John was a […].", "complete": True, "maskCount": 2},
        {"text": "She […] enough time.", "complete": True, "maskCount": 1},
        {"text": "[…] of germs are present.", "complete": True, "maskCount": 1},
    ]


def test_learning_patterns_and_hyphenated_compounds_are_clozed():
    cases = [
        ["The term is <em>derived</em> from Greek.", "derive from", "phrasal verb, verb"],
        ["I <strong>devote</strong> two hours to the work.", "devote sth to sth", "phrasal verb"],
        ["a decision-making process", "decision-making", "noun"],
        ["a decision-making process", "making", "noun"],
    ]
    results = _run_node(
        f"{json.dumps(cases)}.map(c => clozeProductionText(c[0], c[1], c[2]))"
    )

    assert results == [
        {"text": "The term is <em>[…]</em> […] Greek.", "complete": True, "maskCount": 2},
        {"text": "I <strong>[…]</strong> two hours […] the work.", "complete": True, "maskCount": 2},
        {"text": "a […] process", "complete": True, "maskCount": 1},
        {"text": "a decision-[…] process", "complete": True, "maskCount": 1},
    ]


def test_example_markup_is_preserved_and_attributes_are_not_masked():
    rows = _run_node(
        "buildProductionRows("
        "'bắt nguồn từ', "
        "'<em>derived</em> from Greek.<br><br><span data-answer=\"derive\">derive</span> from this.', "
        "'derive from', "
        "'phrasal verb, verb'"
        ")"
    )

    assert rows == [
        {
            "vi": "bắt nguồn từ",
            "examples": [
                "<em>[…]</em> […] Greek.",
                '<span data-answer="derive">[…]</span> […] this.',
            ],
        }
    ]
    assert "example.innerHTML = rows[i].examples[j];" in _template()
    assert "example.textContent = rows[i].examples[j];" not in _template()


def test_vietnamese_cue_masks_reviewed_english_surface_forms():
    result = _run_node(
        "maskVietnameseLeaks('dùng labour (labor) trong tiếng Anh', 'labor', 'noun')"
    )

    assert result == "dùng […] ([…]) trong tiếng Anh"


def test_vietnamese_letters_are_word_characters_for_mask_boundaries():
    result = _run_node(
        "maskVietnameseLeaks("
        "'dành toàn bộ; từ to trong tiếng Anh', "
        "'devote sth to sth', "
        "'phrasal verb'"
        ")"
    )

    assert result == "dành toàn bộ; từ […] trong tiếng Anh"

    decomposed = _run_node(
        "maskVietnameseLeaks('to\\u0301 và to', 'to', 'preposition')"
    )
    assert decomposed == "tó và […]"


def test_incomplete_learning_pattern_example_is_not_shown():
    rows = _run_node(
        "buildProductionRows("
        "'bắt nguồn từ', "
        "'The conclusion was derived carefully.', "
        "'derive from', "
        "'phrasal verb, verb'"
        ")"
    )

    assert rows == [{"vi": "bắt nguồn từ", "examples": []}]
