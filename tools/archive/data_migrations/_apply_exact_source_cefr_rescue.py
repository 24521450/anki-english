#!/usr/bin/env python3
"""Apply the reviewed 2026-07-10 exact-source CEFR rescue batch.

This is a guarded one-shot migration. It defaults to dry-run and refuses to
operate unless every target still has the reviewed pre-migration identity.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from src.config import ProjectPaths


FIX_STATUS = "exact_source_cefr_rescue_20260710"


@dataclass(frozen=True, slots=True)
class Target:
    word: str
    cefr: str
    pos: str
    list_name: str | None = None
    cefr_source: str = "Cambridge"


TARGETS: dict[str, Target] = {
    ">~QKj=Q$p": Target("ambiguous", "C2", "adjective"),
    "wt$pZz9NPt": Target("analytical", "C1", "adjective"),
    "q-l2t)2u|/": Target("approximate", "B2", "adjective"),
    "j![cFqp~_h": Target("congestion", "C1", "noun"),
    "H,4REe[^|B": Target("constrain", "C2", "verb"),
    '"L-#l1@LS<>"': Target("criterion", "B2", "noun", "Oxford_3000", "Oxford"),
    "Nq0vHY[;L[": Target("drastic", "C1", "adjective"),
    "im<>bB.q[Z": Target("eminent", "C2", "adjective"),
    "Qmol/ya1&P": Target("equate", "C2", "verb"),
    "Iv]k{29v<Z": Target("finite", "C2", "adjective"),
    "A+peMs_(9f": Target("ignorant", "C2", "adjective"),
    "JuM]Z&Z(:x": Target("impulse", "C2", "noun"),
    "d;l>KR!+pq": Target("impulsive", "C2", "adjective"),
    "fs1zU:N5+^": Target("intolerance", "C2", "noun"),
    '"Gfj8Dk#&ld"': Target("intrinsic", "C2", "adjective"),
    "x5ieT3(SXY": Target("irrational", "C2", "adjective"),
    "z*XS[(GsLb": Target("irreversible", "C2", "adjective"),
    "y!3QQTKL)V": Target("longevity", "C2", "noun"),
    "oEhpj[-ax}": Target("mediocre", "C2", "adjective"),
    "q}27BMm.K": Target("mortality", "C2", "noun"),
    "iwe/z3s.)i": Target("mundane", "C1", "adjective"),
    "hpkL}4L<pw": Target("notwithstanding", "C1", "adverb, conjunction, preposition"),
    "guTlhX[lR[": Target("outweigh", "C1", "verb"),
    "v]-?BtDLm|": Target("overlap", "C2", "noun, verb"),
    "fHFQHXzU[=": Target("paradigm", "C2", "noun"),
    "N>}]p1Ts84": Target("pleasurable", "C1", "adjective"),
    "elcEz)x&S^": Target("predominant", "C2", "adjective"),
    "bLFX$65T|u": Target("retention", "C2", "noun"),
    '"->QeS;7#8"': Target("scarcity", "C2", "noun"),
    "B]W5lu(W:}": Target("sedentary", "C2", "adjective"),
    "kc@oR5YcW*": Target("short-sighted", "C2", "adjective"),
    "i1T:kW],J.": Target("superficially", "C2", "adverb"),
    "bNRK?=21~*": Target("tangible", "C2", "adjective"),
    "G|4Zda2]}o": Target("tread", "C2", "verb"),
    "w_0qU|$!&h": Target("trivial", "B2", "adjective"),
    '"tryCfn[9#6"': Target("unavoidable", "C1", "adjective"),
    "tvkimHzLgs": Target("utmost", "C1", "adjective"),
}

APPROXIMATE_PAYLOAD = {
    "Definition": "not completely accurate but close (gần đúng/xấp xỉ)",
    "Example": (
        "The train's approximate time of arrival is 10.30.<br><br>"
        "The approximate cost will be about $600."
    ),
    "Collocations": (
        "approximate time/date/number|approximate cost/value/amount|"
        "approximate size/age"
    ),
}


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _index(rows: list[dict], field: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        key = (row.get(field) or "").strip()
        if key in result:
            raise ValueError(f"duplicate {field} {key!r}")
        result[key] = row
    return result


def _manual_key(row: dict) -> tuple[str, str, str, str]:
    return (
        row.get("word") or "",
        (row.get("cefr") or "").upper(),
        row.get("list") or "",
        row.get("variant") or "",
    )


def validate_preconditions(
    registry_rows: list[dict],
    override_rows: list[dict],
    manual_rows: list[dict],
    built_rows: list[dict],
    audio_dir: Path,
) -> None:
    if len(TARGETS) != 37:
        raise ValueError(f"expected 37 targets, got {len(TARGETS)}")
    registry = _index(registry_rows, "guid")
    overrides = _index(override_rows, "guid")
    built = _index(built_rows, "guid")
    manual_keys = {_manual_key(row) for row in manual_rows}
    registry_keys = {
        _manual_key(row): row.get("guid")
        for row in registry_rows
    }

    for guid, target in TARGETS.items():
        reg = registry.get(guid)
        override = overrides.get(guid)
        card = built.get(guid)
        if not reg or not override or not card:
            raise ValueError(f"target {guid!r} is missing from a canonical input")
        for label, row in (("registry", reg), ("override", override), ("build", card)):
            if row.get("word") != target.word:
                raise ValueError(f"{label} word drift for {guid!r}: {row.get('word')!r}")
            if (row.get("cefr") or "").upper() != "UNCLASSIFIED":
                raise ValueError(f"{label} CEFR drift for {guid!r}: {row.get('cefr')!r}")

        expected_old_pos = "verb" if target.word == "approximate" else target.pos
        if reg.get("pos") != expected_old_pos or card.get("pos") != expected_old_pos:
            raise ValueError(f"POS drift for {guid!r}")
        if override.get("input_pos") != expected_old_pos:
            raise ValueError(f"override POS drift for {guid!r}")

        new_list = target.list_name or reg.get("list") or ""
        new_key = (target.word, target.cefr, new_list, reg.get("variant") or "")
        existing_guid = registry_keys.get(new_key)
        if existing_guid not in (None, guid):
            raise ValueError(f"registry identity collision {new_key!r}: {existing_guid!r}")
        if new_key in manual_keys:
            raise ValueError(f"manual payload already exists for {new_key!r}")

        for field in ("uk_audio", "us_audio"):
            reference = card.get(field) or ""
            filename = reference.removeprefix("[sound:").removesuffix("]")
            if not filename or not (audio_dir / filename).is_file():
                raise ValueError(f"missing {field} for {guid!r}: {reference!r}")

    harbour = registry.get("m}g1cKg({G")
    if not harbour or harbour.get("pos") != "verb" or harbour.get("cefr") != "UNCLASSIFIED":
        raise ValueError("harbour verb must remain UNCLASSIFIED")


def build_manual_row(registry: dict, card: dict, target: Target) -> dict:
    list_name = target.list_name or registry.get("list") or ""
    definition = card.get("definition") or ""
    example = card.get("example") or ""
    collocations = card.get("collocations") or ""
    synonyms = card.get("synonyms") or ""
    antonyms = card.get("antonyms") or ""
    if target.word == "approximate":
        definition = APPROXIMATE_PAYLOAD["Definition"]
        example = APPROXIMATE_PAYLOAD["Example"]
        collocations = APPROXIMATE_PAYLOAD["Collocations"]
        synonyms = ""
        antonyms = ""

    if target.cefr_source == "Oxford":
        source1, source2 = "Oxford", "Oxford"
        tags = f"Source::Oxford CEFR::{target.cefr} CEFR::oxford Oxford_3000"
    else:
        source1 = "Cambridge"
        source2 = "AWL" if list_name == "AWL" else "Oxford"
        tags = f"Source::Cambridge CEFR::{target.cefr} CEFR::cambridge"
        if list_name == "AWL":
            tags += " AWL_Coxhead"

    return {
        "word": target.word,
        "cefr": target.cefr,
        "list": list_name,
        "variant": registry.get("variant") or "",
        "definition": definition,
        "example": example,
        "collocations": collocations,
        "wordfamily": card.get("wordfamily") or "",
        "ipa": card.get("ipa") or "",
        "uk_audio": card.get("uk_audio") or "",
        "us_audio": card.get("us_audio") or "",
        "source1": source1,
        "source2": source2,
        "idioms": card.get("idioms") or "",
        "provenance": {
            "source": "manual_card_fills",
            "cefr_source": target.cefr_source,
            "review_batch": FIX_STATUS,
            "ledger_pos": target.pos,
        },
        "synonyms": synonyms,
        "antonyms": antonyms,
        "tags": tags,
    }


def prepare_updates(
    registry_rows: list[dict],
    override_rows: list[dict],
    built_rows: list[dict],
    targets: dict[str, Target] | None = None,
) -> tuple[dict[str, dict], dict[str, dict], list[dict]]:
    targets = TARGETS if targets is None else targets
    registry = _index(registry_rows, "guid")
    overrides = _index(override_rows, "guid")
    built = _index(built_rows, "guid")
    registry_updates: dict[str, dict] = {}
    override_updates: dict[str, dict] = {}
    manual_additions: list[dict] = []

    for guid, target in targets.items():
        reg = dict(registry[guid])
        reg["cefr"] = target.cefr
        reg["pos"] = target.pos
        if target.list_name:
            reg["list"] = target.list_name
        registry_updates[guid] = reg

        override = dict(overrides[guid])
        override["cefr"] = target.cefr
        override["fix_status"] = FIX_STATUS
        if target.word == "approximate":
            override["output_pos"] = "adjective"
            override.update(APPROXIMATE_PAYLOAD)
        override_updates[guid] = override

        manual_additions.append(build_manual_row(reg, built[guid], target))

    return registry_updates, override_updates, manual_additions


def rewrite_jsonl(path: Path, updates: dict[str, dict], *, key_field: str = "guid") -> None:
    output = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = row.get(key_field)
        if key in updates:
            output.append(json.dumps(updates[key], ensure_ascii=False, separators=(",", ":")))
            seen.add(key)
        else:
            output.append(line)
    missing = set(updates) - seen
    if missing:
        raise ValueError(f"updates not found in {path}: {sorted(missing)!r}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")


def append_jsonl(path: Path, rows: list[dict]) -> None:
    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    text += "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def replace_target_manual_rows(path: Path, rows: list[dict]) -> None:
    """Replace migrated target payloads and remove obsolete old identities."""
    target_words = {target.word for target in TARGETS.values()}
    target_new_keys = {_manual_key(row) for row in rows}
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = _manual_key(row)
        if key in target_new_keys:
            continue
        if row.get("word") in target_words and row.get("cefr") == "UNCLASSIFIED":
            continue
        output.append(line)
    output.extend(
        json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        for row in rows
    )
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--repair-applied-manual",
        action="store_true",
        help="Normalize manual rows after an interrupted/applied migration.",
    )
    args = parser.parse_args(argv)
    paths = ProjectPaths(args.root)

    if args.repair_applied_manual:
        registry = _index(load_jsonl(paths.card_registry), "guid")
        built = _index(load_jsonl(paths.anki_notes_jsonl), "guid")
        additions = [
            build_manual_row(registry[guid], built[guid], target)
            for guid, target in TARGETS.items()
        ]
        replace_target_manual_rows(paths.manual_cards, additions)
        print(f"Normalized {len(additions)} applied manual payloads.")
        return 0

    registry_rows = load_jsonl(paths.card_registry)
    override_rows = load_jsonl(paths.non_oxford_non_c2_overrides)
    manual_rows = load_jsonl(paths.manual_cards)
    built_rows = load_jsonl(paths.anki_notes_jsonl)
    validate_preconditions(
        registry_rows, override_rows, manual_rows, built_rows, paths.audio_dir
    )
    registry_updates, override_updates, manual_additions = prepare_updates(
        registry_rows, override_rows, built_rows
    )
    levels = {level: 0 for level in ("B2", "C1", "C2")}
    for target in TARGETS.values():
        levels[target.cefr] += 1
    print(f"Validated {len(TARGETS)} targets: {levels}")
    if not args.apply:
        print("Dry-run only; pass --apply to mutate canonical inputs.")
        return 0

    rewrite_jsonl(paths.card_registry, registry_updates)
    rewrite_jsonl(paths.non_oxford_non_c2_overrides, override_updates)
    replace_target_manual_rows(paths.manual_cards, manual_additions)
    print("Updated registry/review overrides and appended manual payloads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
