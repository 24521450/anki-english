from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACK_TEMPLATE = ROOT / "design" / "EAVM" / "back_template.txt"
STYLING = ROOT / "design" / "EAVM" / "styling.txt"
PREVIEW = ROOT / "design" / "index.html"


def test_source_backed_collocations_use_verified_palette_and_visible_marker():
    css = STYLING.read_text(encoding="utf-8")

    assert ".collocation-chip-source-backed {" in css
    assert "color: #d1fae5;" in css
    assert "background: #022c22;" in css
    assert "border-color: #065f46;" in css
    assert "font-weight: 600;" in css
    assert ".collocation-source-marker {" in css


def test_template_uses_aligned_source_field_and_dom_text_nodes():
    template = BACK_TEMPLATE.read_text(encoding="utf-8")
    render_start = template.index("  function renderCollocations(")
    render_end = template.index("  function renderPosChips(", render_start)
    renderer = template[render_start:render_end]

    assert '<div id="raw-collocation-sources-back">{{CollocationSources}}</div>' in template
    assert "document.createElement('span')" in renderer
    assert "document.createTextNode(item.text)" in renderer
    assert "setAttribute('role', 'list')" in renderer
    assert "setAttribute('role', 'listitem')" in renderer
    assert "setAttribute('aria-label', item.text + '; source: ' + sourceMeta.label)" in renderer
    assert "innerHTML" not in renderer


def test_curriculum_preview_distinguishes_oxford_from_curated_chips():
    preview = PREVIEW.read_text(encoding="utf-8")

    assert (
        '<span class="collocation-chip collocation-chip-source-backed" role="listitem" '
        'aria-label="on the curriculum; source: Oxford Dictionary">on the curriculum'
    ) in preview
    assert (
        '<span class="collocation-chip collocation-chip-source-backed" role="listitem" '
        'aria-label="in the curriculum; source: Oxford Dictionary">in the curriculum'
    ) in preview
    assert preview.count('<span class="collocation-source-marker" aria-hidden="true">OXF</span>') >= 2
    assert '<span class="collocation-chip" role="listitem">curriculum development</span>' in preview
