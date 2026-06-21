# ADR-0001: lxml + cssselect as the parser backend

- **Status:** Accepted
- **Date:** 2026-06-10
- **Deciders:** project owner
- **Reviewers:** n/a (single-owner project per AGENTS.md)

## Context

The Oxford + Cambridge scraper pipeline (`src/scraper/`, planned) re-parses
13,000+ cached HTML files at build time (sense extraction, audio ref lookup,
CEFR resolution). The dominant cost was reported as BS4 HTML traversal, but
the underlying number was anecdotal — no benchmark evidence existed on disk.

The candidate alternative is `lxml.html.fromstring()` + `lxml.Element.cssselect()`,
which is well-known to be faster than BeautifulSoup but requires care to keep
output semantically equivalent (whitespace handling, parent-chain termination).

## Decision

Use **`lxml.html.fromstring()` + `cssselect()` for forward queries** and
**`getparent()` (or `el.iterancestors()`) for the ~5% ancestor walks**
(idiom detection — 2 sites per CONTEXT.md `Idiom Detection`).

Skip threading for now — single-process is fast enough after the swap, and
threading's complexity (GIL release at both I/O and CPU per memory note
2026-06-10) is not worth the saved seconds.

Add `cssselect>=1.4.0` as a direct dependency (not just transitive) so the
CSS selector implementation contract is explicit and not at the mercy of
lxml's transitive resolution.

## Evidence

Benchmark harness: `tools/benchmark_parser.py`
Sample: 100 Oxford + 100 Cambridge stratified (seed=20260610)
Output: `tools/benchmark_results.csv` (200 rows, all fields)

### Speedup (median over 10 timed runs per file, 3 warmup runs discarded)

| Metric | BS4 | lxml | Speedup |
|---|---:|---:|---:|
| Median per-file (p50) | 63.3 ms | 14.5 ms | **4.51×** |
| Mean per-file | 64.2 ms | 14.4 ms | 4.49× |
| Min speedup | — | — | 3.22× |
| Max speedup | — | — | 5.36× |
| p95/p50 stability ratio | 1.29 | 1.28 | similar (no lxml regression) |

### Equivalence (per-record field compare, strict)

- **200 / 200 files pass** (100.0%)
- All 5 forward selectors match 1:1 (sense, def, ipa, pos, examples)
- All 2 ancestor selectors (Oxford `idioms`, Cambridge `idiom-body`,
  `phrase-di-body`) match after normalizing for the BS4-vs-lxml parent-chain
  termination difference (see "Parser artifact" below)

**Note on equivalence scope**: the 100% rate is for *generic traversal*
(counts of selector matches + ancestor depth). The full record-extraction
equivalence is a separate validation — see "Record-extraction equivalence
(golden fixtures)" below and `tests/scraper/test_parser_golden.py`.

### Stability across axes

- Per-source: Oxford 4.51×, Cambridge 4.52× — no source bias
- Per Oxford polymorphic form: main_page 5.05× (n=1), pos_suffix 4.51×
  (n=88), indexed_pos 4.56× (n=11) — flat
- Per file size: 4.41-4.54× across all size buckets (50kb-700kb)

### Extrapolation to 13,000 files

- BS4: 823 s (13.7 min)
- lxml: 189 s (3.1 min)
- **Time saved: ~10.6 min per full pipeline run**

## Parser artifact (correctness note)

BS4's `el.parent` of the outermost HTML element returns the `BeautifulSoup`
document object (which is not a tag). lxml's `el.getparent()` returns `None`.
This gives BS4 `len(el.parents) == 12` where lxml's `el.iterancestors()`
gives 11 for the same DOM.

**Resolution**: count `len(el.parents) - 1` for BS4, `sum(1 for _ in
el.iterancestors())` for lxml. Both yield the same number of real HTML tag
ancestors. The fix lives in `tools/benchmark_parser.py` (also a contract
example for the production scraper).

## Record-extraction equivalence (golden fixtures)

The generic-traversal benchmark above proves selectors find the same
elements. Full record-extraction equivalence — extracting `word`, `pos`,
`ipa`, `senses[]` per record — is validated separately by golden fixtures
(`tests/scraper/test_parser_golden.py`, 20 cases). This surfaced a
**second parser artifact** that generic counts do not catch:

**BS4 separator artifact.** `el.get_text(separator=" ", strip=True)` joins
text nodes with a single space. When an inline `<a>` tag wraps a word and
is immediately followed by punctuation in the source, BS4 inserts a
**spurious space** between the wrapped text and the punctuation:

```html
<!-- Source HTML -->
<a>directed</a>, or a circle

<!-- BS4 get_text(" ", strip=True)  -->  "directed , or a circle"   ← wrong
<!-- lxml text_content()             -->  "directed, or a circle"   ← source-faithful
```

This is an HTML-spec artifact: lxml reads `.text` and `.tail` of each
element, and the join happens naturally in the source. BS4 with a
" " separator inserts extra space at every text-node boundary that has
no original whitespace.

**Equivalence model after this finding**: golden fixtures freeze the
**lxml output** as ground truth. Re-running the production extractor
(lxml) against the lxml-generated fixtures must match 100% — this proves
the lxml extraction is self-consistent and reproducible. The ADR does
**not** claim lxml == BS4 for full record extraction; the BS4 separator
artifact is a known, expected divergence recorded here. Production
scraper code is built on lxml, so the BS4 path is a documented
historical reference, not a target.

If a future parser swap targets BS4 output, the extractor will need to
re-introduce the separator (or apply text-join logic that matches
whatever the target parser produces). The current contract is
**lxml-self-consistent** + **source-faithful**, not parser-agnostic.

## Consequences

### Positive

- ~4.5× speedup on the dominant pipeline cost (parse + traverse)
- 100% equivalence on generic traversal (200/200 files) — selectors find
  the same elements in both parsers
- 100% equivalence on full record extraction (20/20 files) — lxml
  extraction is self-consistent against the lxml-generated golden
- All 5 forward selectors + 2 ancestor selectors are 1:1 between parsers
  (at the count level; text extraction differs — see "Record-extraction
  equivalence" above)
- Single new dep (`cssselect>=1.4.0`) — minimal surface area
- No threading complexity (GIL, IO/CPU release points, ordering)
- Stays below the 6× memory claim; ADR is evidence-based, not aspirational

### Negative

- Original "6×" claim in prior memory was overstated. Actual is **4.5×**.
  ADR corrects this — the magnitude is smaller but still significant.
- Equivalence model is **lxml-self-consistent + source-faithful**, not
  parser-agnostic. The BS4 separator artifact is a known divergence;
  if a future parser swap needs BS4-compatible output, the extractor
  must re-introduce the join (or change the contract).
- The 4 files with largest absolute time savings (top BS4-slowest) are
  Cambridge pages 400-700kb. If Cambridge HTML structure changes (e.g.
  layout update), lxml/BS4 equivalence must be re-benchmarked.

## Alternatives considered

| Option | Why not |
|---|---|
| **Keep BS4** | 4.5× regression for no benefit. |
| **lxml + `xpath()` everywhere** | More verbose, no perf gain over cssselect for our selectors. |
| **lxml + threading (ProcessPool)** | GIL release needed at both IO and CPU (per memory 2026-06-10); complexity not justified by ~10 min savings at this scale. |
| **lxml + lxml-bundled cssselect (no separate dep)** | lxml's bundled implementation has feature gaps; explicit dep pins the contract. |

## Reversibility

Cost of reverting: low. The swap is in one module (scraper parse layer).
Wrapper can fall back to BS4 by checking an env var or feature flag if
lxml becomes a problem.

## Cross-references

- `CONTEXT.md` — new terms: `Parser Backend`, `Forward Query`, `Ancestor Walk`
- `tools/benchmark_parser.py` — generic-traversal benchmark harness (re-runnable)
- `tools/benchmark_results.csv` — generic-traversal evidence (200 rows)
- `tools/_golden_extract.py` — lxml-based extractor (the contract)
- `tools/_make_golden.py` — fixture generator (uses lxml, see header comment)
- `tests/fixtures/golden_oxford.json`, `golden_cambridge.json` — ground truth
- `tests/scraper/test_parser_golden.py` — 20/20 record-extraction equivalence test
- `pyproject.toml`, `requirements.txt` — `cssselect>=1.4.0`
- Memory note 2026-06-10 (`BS4 vs lxml whitespace normalization for
  golden-output tests`) — relevant for golden-fixture phase
