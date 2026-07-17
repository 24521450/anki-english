# IELTS Academic Vocabulary Deck

Registry-driven IELTS / Academic English Anki deck builder with Oxford and
Cambridge ingestion, review data, deterministic validation, and EAVM card
packaging.

## Development

```powershell
pip install -r requirements.txt
pip install -e .
pytest
```

Run the default production stages with `python -m src.pipeline` or the
installed `anki-english` command. Every real pipeline run containing the
`deck` stage automatically imports and verifies the package in the running
Anki collection through AnkiConnect; Anki must therefore be running. Generate
missing speech with `python -m src.pipeline example-audio`, use `--dry-run` for
non-writing checks, or run `python -m src.pipeline import` for a standalone
re-import. See `AGENTS.md` for the complete workflow and `CONTEXT.md` for
canonical project terminology.
