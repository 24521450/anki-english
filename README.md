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
installed `anki-english` command. Generate missing speech with
`python -m src.pipeline example-audio`; after packaging, import explicitly into
the running Anki collection with `python -m src.pipeline import`. See
`AGENTS.md` for the complete workflow and `CONTEXT.md` for canonical project
terminology.
