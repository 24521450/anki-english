# Deutsch Resources

This directory is a German Anki resource subproject inside the IELTS deck repo. It reuses the repo's Python environment and shared path configuration, but it is not part of the default IELTS build pipeline.

## Scope

- `sources/goethe/` contains source Goethe word lists and reference PDFs.
- `tools/` contains German A1 audio generation and Duden lookup tools.
- `audio/` is generated output. MP3s, logs, checkpoints, staging directories, and generated manifests are ignored by default.
- `review/duden_overrides.json` is the hand-reviewed Duden policy file.
- `docs/PLAN_A1_WORD_AUDIO.md` documents the current A1 word-audio plan.
- `tests/` contains German-resource tests. They are outside the default pytest suite because `pyproject.toml` limits default collection to root `tests/`.

## Current Workflows

Word audio:

```powershell
python deutsch/tools/a1_preflight.py
python deutsch/tools/a1_generate.py --pilot-only
python deutsch/tools/a1_generate.py
```

Example sentence audio:

```powershell
python deutsch/tools/a1_example_audio.py preflight
python deutsch/tools/a1_example_audio.py pilot
python deutsch/tools/a1_example_audio.py full
python deutsch/tools/a1_example_audio.py resume
```

Duden dictionary audio:

```powershell
python deutsch/tools/download_duden_a1_audio.py --help
```

Run German-resource tests explicitly:

```powershell
python -m pytest deutsch/tests
```

## Notes

The Matrix TTS scripts currently depend on a local `mavis mcp call matrix matrix_synthesize_speech` setup and several scripts still use the repo root from `src.config.ProjectPaths` or a hardcoded local root. Treat them as local resource tooling until they are made portable.

Do not add `deutsch/` back into the Understand architecture graph for IELTS-only work. When German resources become a primary milestone, generate a scoped German graph or intentionally update `.understandignore`.
