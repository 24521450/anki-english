from pathlib import Path

OLD_BASENAMES = [
    "oxford_merged.jsonl",
    "cambridge_full.jsonl",
    "audit_full_deck_v2.jsonl",
    "gamma_all_verdicts.json",
    "missing_oxford_5000_cards_filled.json",
    "English Academic Vocabulary.txt",
]

# The basename remains canonical, so only the obsolete location is forbidden.
OLD_RELATIVE_PATHS = ["data/anki_notes.jsonl"]

HARDCODED_ROOT = "C:\\Users\\admin\\Downloads\\ankideck"


def test_no_old_paths_or_hardcoded_root_in_maintained_code():
    """Verify that no active source file contains the old hardcoded paths or roots.

    We scan `src/`, `tests/`, `update_anki_deck.py`, and non-archived files in `tools/`.
    """
    project_root = Path(__file__).resolve().parents[1]

    # Directories/files to scan
    scan_paths = [
        project_root / "src",
        project_root / "tests",
        project_root / "update_anki_deck.py",
    ]

    # Active tools (excluding the archive directory)
    tools_dir = project_root / "tools"
    if tools_dir.exists():
        for item in tools_dir.iterdir():
            if item.is_file():
                scan_paths.append(item)

    violations = []

    for path in scan_paths:
        if not path.exists():
            continue
        if path.is_file():
            files_to_scan = [path]
        else:
            files_to_scan = [f for f in path.rglob("*.py") if f.is_file()]

        for f in files_to_scan:
            # Exclude tests/test_drift_guard.py itself to avoid self-triggering
            if f.name == "test_drift_guard.py":
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue

            for basename in OLD_BASENAMES:
                if basename in content:
                    if basename == "English Academic Vocabulary.txt":
                        # Require path to be anchored under data/build/ or an explicit parent path.
                        for line in content.splitlines():
                            if basename in line and "data/build" not in line and "parent /" not in line and "parent/" not in line:
                                violations.append(
                                    f"{f.relative_to(project_root)}: contains unanchored basename '{basename}'"
                                )
                    else:
                        violations.append(
                            f"{f.relative_to(project_root)}: contains old basename '{basename}'"
                        )

            for old_path in OLD_RELATIVE_PATHS:
                if old_path in content or old_path.replace("/", "\\") in content:
                    violations.append(
                        f"{f.relative_to(project_root)}: contains old path '{old_path}'"
                    )

            if HARDCODED_ROOT.casefold() in content.casefold():
                violations.append(f"{f.relative_to(project_root)}: contains hardcoded root '{HARDCODED_ROOT}'")

    assert not violations, "Drift detected! Maintained code contains old paths or hardcoded root:\n" + "\n".join(violations)
