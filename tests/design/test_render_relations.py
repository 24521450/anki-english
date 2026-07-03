"""Regression tests for renderRelations in design/EAVM/back_template.txt.

Executes the actual JavaScript renderRelations function from back_template.txt using Node.js.
Verifies:
- Grouped synonyms (e.g. `(guarantee, promise)`) -> .relation-synonym (teal).
- Single relations (e.g. `(confidence)`) -> .relation-synonym (teal).
- Grouped antonyms (e.g. `(uncertainty, doubt)`) -> .relation-antonym (pink).
- Optional `=`, extra whitespace, and case-insensitivity.
- Partial, mixed, or ambiguous lists are NOT colored.
- JavaScript code syntax check via `node --check <file>` on tmp_path.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

BACK_TEMPLATE = Path(__file__).resolve().parent.parent.parent / "design" / "EAVM" / "back_template.txt"


def _extract_function(src: str, func_name: str) -> str:
    """Extract full JS function definition using a balanced-brace scanner."""
    pattern = rf"function\s+{func_name}\s*\([^)]*\)\s*\{{"
    match = re.search(pattern, src)
    if not match:
        raise ValueError(f"Function {func_name} not found in template source.")

    start_pos = match.start()
    brace_start = match.end() - 1  # Index of '{'

    depth = 0
    in_string = None  # None, "'", '"', or '`'
    escaped = False

    for i in range(brace_start, len(src)):
        char = src[i]

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
                return src[start_pos : i + 1]

    raise ValueError(f"Unmatched braces in function {func_name}.")


def _extract_render_relations_js() -> str:
    src = BACK_TEMPLATE.read_text(encoding="utf-8")
    trim_js = _extract_function(src, "trim")
    render_js = _extract_function(src, "renderRelations")
    return f"{trim_js}\n\n{render_js}"


def _run_node_render_relations(ex_html: str, syn_words: list[str] | None, ant_words: list[str] | None) -> str:
    js_code = _extract_render_relations_js()
    runner = f"""
{js_code}
const exHtml = {json.dumps(ex_html)};
const synWords = {json.dumps(syn_words)};
const antWords = {json.dumps(ant_words)};
console.log(renderRelations(exHtml, synWords, antWords));
"""
    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    res = subprocess.run(
        ["node", "-e", runner],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout.rstrip("\r\n")


def test_node_check_javascript_syntax(tmp_path):
    """Verify that the extracted JavaScript is syntactically valid via `node --check <file>`."""
    js_code = _extract_render_relations_js()
    js_file = tmp_path / "extracted_render_relations.js"
    js_file.write_text(js_code, encoding="utf-8")

    env = os.environ.copy()
    env.pop("NODE_OPTIONS", None)
    res = subprocess.run(
        ["node", "--check", str(js_file)],
        env=env,
        timeout=5,
        capture_output=True,
        text=True,
        check=True,
    )
    assert res.returncode == 0, f"JS syntax check failed:\n{res.stderr}"


def test_grouped_synonyms_assurance():
    """`assurance`: `(guarantee, promise)` -> teal (.relation-synonym)."""
    ex = "She gave assurance (guarantee, promise)."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert '<span class="relation-synonym">(guarantee, promise)</span>' in out


def test_single_relation_confidence():
    """`confidence`: single relation -> teal (.relation-synonym)."""
    ex = "He has confidence (trust)."
    out = _run_node_render_relations(ex, ["trust"], [])
    assert '<span class="relation-synonym">(trust)</span>' in out


def test_grouped_antonyms_controversial():
    """`controversial`: grouped antonyms -> pink (.relation-antonym)."""
    ex = "A controversial topic (uncertainty, doubt)."
    out = _run_node_render_relations(ex, [], ["uncertainty", "doubt"])
    assert '<span class="relation-antonym">(uncertainty, doubt)</span>' in out


def test_optional_equals_whitespace_case():
    """Optional `=`, whitespace, and uppercase/lowercase matching."""
    ex = "She gave assurance (= GUARANTEE , Promise )."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert '<span class="relation-synonym">(= GUARANTEE , Promise )</span>' in out


def test_partial_match_not_colored():
    """Partial match (only 1 word matches metadata) is NOT colored."""
    ex = "She gave assurance (guarantee, extra)."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert "relation-synonym" not in out
    assert out == ex


def test_mixed_match_not_colored():
    """Mixed match (synonym + antonym in same paren) is NOT colored."""
    ex = "She gave assurance (guarantee, uncertainty)."
    out = _run_node_render_relations(ex, ["guarantee"], ["uncertainty"])
    assert "relation-synonym" not in out
    assert "relation-antonym" not in out
    assert out == ex


def test_ambiguous_match_not_colored():
    """Ambiguous list (matches both synWords and antWords) is NOT colored."""
    ex = "Ambiguous test (same)."
    out = _run_node_render_relations(ex, ["same"], ["same"])
    assert "relation-synonym" not in out
    assert "relation-antonym" not in out
    assert out == ex


def test_subset_guarantee_not_colored():
    """Metadata `guarantee, promise`, paren `(guarantee)` -> NOT colored."""
    ex = "She gave assurance (guarantee)."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert "relation-synonym" not in out
    assert out == ex


def test_subset_promise_not_colored():
    """Metadata `guarantee, promise`, paren `(promise)` -> NOT colored."""
    ex = "She gave assurance (promise)."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert "relation-synonym" not in out
    assert out == ex


def test_reordered_set_equality_promise_guarantee():
    """Metadata `guarantee, promise`, paren `(promise, guarantee)` -> teal (.relation-synonym)."""
    ex = "She gave assurance (promise, guarantee)."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert '<span class="relation-synonym">(promise, guarantee)</span>' in out


def test_duplicate_items_not_colored():
    """Paren `(guarantee, guarantee)` -> NOT colored."""
    ex = "She gave assurance (guarantee, guarantee)."
    out = _run_node_render_relations(ex, ["guarantee", "promise"], [])
    assert "relation-synonym" not in out
    assert out == ex
