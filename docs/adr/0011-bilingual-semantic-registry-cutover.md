# ADR 0011 — ChatGPT-reviewed bilingual Semantic Registry

**Status:** accepted; production cutover completed 2026-07-15

The deck replaces the β/γ/M3 gloss pipeline and its layered semantic
overrides with one reviewed Semantic Registry. Oxford remains authoritative for
POS, CEFR, and source-sense identity; Cambridge English–Vietnamese is supporting
translation evidence only. Every active card and every relevant source sense
must be accounted, and unresolved or unapproved rows fail closed. The review
ledger and its XLSX view were introduced before cutover so example-audio and
release workflows were not broken mid-migration. A complete ledger is now
promoted deterministically to `data/curated/semantic_registry.jsonl`; production
build and example-audio commands fail closed without that promoted payload.

The trade-off is a larger up-front human/ChatGPT review in exchange for removing
heuristic semantic merges and multiple competing content owners. ADR 0005 stays
as historical context. Its legacy layers may still provide source indexing and
non-semantic metadata, but they no longer own final Definition/Example content.
