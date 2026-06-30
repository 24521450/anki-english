"""Phase 1-2: Post-build injection of 13 missing Oxford 5000 cards.

Why post-build (not in build_notes):
- build_notes Type A resolution remaps POS to whatever's in jsonl,
  causing collisions with existing rows that the user wants to keep.
- The 13 missing cards are edge cases (POS in Oxford 5000 differs from
  POS in Oxford jsonl). Patching build_notes is too invasive for 13 cards.
- Post-build injection bypasses build_notes entirely, keeps the new POS
  verbatim from filled.json.

Idempotent: checks (word, pos, cefr) key in anki_notes.jsonl before inject.
"""
import json
import secrets
import string
from pathlib import Path

ROOT = Path(r"C:\Users\admin\Downloads\ankideck")
JSONL_PATH = ROOT / "data" / "anki_notes.jsonl"
TXT_PATH = ROOT / "English Academic Vocabulary.txt"
FILLED_PATH = ROOT / "data" / "missing_oxford_5000_cards_filled.json"
OX_JSONL_PATH = ROOT / "data" / "oxford_merged.jsonl"
AUDIO_DIR = ROOT / "audio"

NOTETYPE = "English Academic Vocabulary Model"
DECK = "English Academic Vocabulary::Oxford"

_GUID_ALPHABET = string.ascii_letters + string.digits + '!#$%&()*+,-./:;<=>?@[]^_`{|}~'


def new_guid() -> str:
    """Generate 10-char Anki-style base64-like GUID. Match build_notes._new_guid."""
    return ''.join(secrets.choice(_GUID_ALPHABET) for _ in range(10))


def _key(word: str, pos: str, cefr: str) -> tuple[str, str, str]:
    return (word.strip().lower(), pos.strip().lower(), cefr.strip().upper())


def _key_word_cefr(word: str, cefr: str) -> tuple[str, str]:
    """Per user (2026-06-20) Card Identity enforcement: 1 card per (word, cefr).

    Existence check is at the (word, cefr) level — POS is irrelevant for
    identity. If any card with this word+cefr already exists, skip injection
    regardless of POS. This prevents the post-build injection from re-creating
    duplicate cards that build_notes' Type A POS remap may have collapsed to
    a single (word, cefr) group already.
    """
    return (word.strip().lower(), cefr.strip().upper())


def _resolve_audio(word: str, accent: str, available: set[str]) -> str:
    """Match build_notes._resolve_audio_filename."""
    candidates = [
        f"cambridge_{accent}_{word}.mp3",
        f"cambridge_{accent}_{word.replace(' ', '_')}.mp3",
        f"cambridge_{accent}_{word.replace('-', '')}.mp3",
    ]
    for c in candidates:
        if c in available:
            return f"[sound:{c}]"
    return ""


def _load_jsonl_records(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                out.append(json.loads(line))
    return out


def _index_oxford_by_word() -> dict[str, list[dict]]:
    """Index oxford_merged.jsonl records by word_lower. For example/IPA lookup
    across all POS (since the missing cards' POS doesn't exist in jsonl,
    but other POS for the same word do)."""
    idx: dict[str, list[dict]] = {}
    with OX_JSONL_PATH.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            w = (r.get("word") or "").lower()
            if w:
                idx.setdefault(w, []).append(r)
    return idx


def _pick_example(records: list[dict]) -> str:
    """Return first non-empty example from any POS for this word."""
    for r in records:
        for pd in r.get("pos_data", []) or []:
            for d in pd.get("definitions", []) or []:
                ex = d.get("examples") or []
                if not ex:
                    continue
                first = ex[0]
                if isinstance(first, dict):
                    txt = (first.get("text") or "").strip()
                else:
                    txt = str(first).strip()
                if txt:
                    return txt
    return ""


def _pick_ipa(records: list[dict]) -> str:
    """Format IPA from uk_ipa/us_ipa at record top level (per 2026-06-20 plan).

    Both fields come from the parser wrapped in slashes. Output formats:
      - both present + DIFFERENT → "UK: /uk/ | US: /us/"
      - both present + IDENTICAL → "/uk/"
      - only one present → "/that/"
      - neither → ""

    The 13 injected cards typically have no IPA in jsonl (the words aren't
    in the live Oxford cache for the missing POS), but we keep this so the
    injection script is robust if some future batch has IPA data.
    """
    for r in records:
        uk = r.get("uk_ipa")
        us = r.get("us_ipa")
        if not uk and not us:
            continue
        uk_n = (uk or "").strip().strip("/").strip()
        us_n = (us or "").strip().strip("/").strip()
        if uk_n and us_n:
            if uk_n == us_n:
                return f"/{uk_n}/"
            return f"UK: /{uk_n}/ | US: /{us_n}/"
        if uk_n:
            return f"/{uk_n}/"
        if us_n:
            return f"/{us_n}/"
    return ""


def _build_tags(cefr: str) -> str:
    """Per build_notes._regenerate_tags, simplified — only the tags relevant
    to injected Oxford 5000 cards (no AWL/OPAL, no idioms)."""
    return f"Source::Oxford CEFR::{cefr} CEFR::oxford Oxford_5000"


def _make_card(
    filled: dict,
    audio_files: set[str],
    oxford_idx: dict[str, list[dict]],
) -> dict:
    word = filled["word"]
    pos = filled["pos"]
    cefr = filled["cefr"]
    definition = (filled.get("gloss_after") or "").strip()
    word_records = oxford_idx.get(word.lower(), [])
    example = _pick_example(word_records)
    ipa = _pick_ipa(word_records)
    uk = _resolve_audio(word.lower(), "uk", audio_files)
    us = _resolve_audio(word.lower(), "us", audio_files)
    tags = _build_tags(cefr)
    return {
        "guid": new_guid(),
        "notetype": NOTETYPE,
        "deck": DECK,
        "word": word,
        "pos": pos,
        "ipa": ipa,
        "definition": definition,
        "example": example,
        "collocations": "",
        "wordfamily": "",
        "uk_audio": uk,
        "us_audio": us,
        "source1": "Oxford",
        "source2": "Oxford",
        "cefr": cefr,
        "idioms": "",
        "tags": tags,
    }


def main():
    # Backup current outputs
    ts = "20260620_111500"
    jsonl_bak = JSONL_PATH.with_suffix(f".jsonl.bak_pre_inject_{ts}")
    txt_bak = TXT_PATH.with_suffix(f".txt.bak_pre_inject_{ts}")
    jsonl_bak.write_text(JSONL_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    txt_bak.write_text(TXT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Backup: {jsonl_bak.name}")
    print(f"Backup: {txt_bak.name}")

    # Load existing cards
    existing_cards = _load_jsonl_records(JSONL_PATH)
    print(f"Loaded existing cards: {len(existing_cards)}")

    # Per user (2026-06-20) Card Identity: existence check at (word, cefr) level.
    # POS is irrelevant for identity — if any card exists at (word, cefr),
    # don't inject another one (even at a different POS).
    existing_keys = {_key_word_cefr(c["word"], c["cefr"]) for c in existing_cards}
    print(f"Existing (word, cefr) keys: {len(existing_keys)}")

    # Load filled.json
    filled = json.load(FILLED_PATH.open(encoding="utf-8"))
    print(f"Filled records: {len(filled)}")

    # Load Oxford jsonl index (for example/IPA)
    oxford_idx = _index_oxford_by_word()
    print(f"Oxford jsonl words indexed: {len(oxford_idx)}")

    # Load audio files
    if AUDIO_DIR.exists():
        audio_files = {p.name for p in AUDIO_DIR.iterdir() if p.is_file()}
    else:
        audio_files = set()
    print(f"Audio files: {len(audio_files)}")

    # Categorize filled records using (word, cefr) for existence check
    to_inject = []
    already_present = []
    for r in filled:
        k_id = _key_word_cefr(r["word"], r["cefr"])
        k_full = _key(r["word"], r["pos"], r["cefr"])
        if k_id in existing_keys:
            already_present.append((k_full, r))
        else:
            to_inject.append((k_full, r))

    print()
    print(f"Already present (skip): {len(already_present)}")
    print(f"To inject: {len(to_inject)}")
    print()
    if to_inject:
        print("=== To inject ===")
        for k, r in to_inject:
            print(f"  {k}: gloss={r['gloss_after']!r}")

    if not to_inject:
        print("Nothing to inject — deck already complete.")
        return

    # Build new cards
    new_cards = []
    for k, r in to_inject:
        c = _make_card(r, audio_files, oxford_idx)
        new_cards.append(c)
        print(f"  built card for {k}: guid={c['guid']} example={c['example'][:50]!r} uk={'yes' if c['uk_audio'] else 'no'}")

    # Append to JSONL
    with JSONL_PATH.open("a", encoding="utf-8") as f:
        for c in new_cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"\nAppended {len(new_cards)} cards to {JSONL_PATH.name}")

    # Append to TXT (17-col tab-separated; preserve header lines)
    txt_lines = TXT_PATH.read_text(encoding="utf-8").splitlines()
    header_lines = []
    body_lines = []
    for line in txt_lines:
        if line.startswith("#"):
            header_lines.append(line)
        elif line.strip():
            body_lines.append(line)
    new_body_lines = []
    for c in new_cards:
        new_body_lines.append("\t".join([
            c["guid"], c["notetype"], c["deck"], c["word"], c["pos"], c["ipa"],
            c["definition"], c["example"], c["collocations"], c["wordfamily"],
            c["uk_audio"], c["us_audio"], c["source1"], c["source2"], c["cefr"],
            c["idioms"], c["tags"],
        ]))
    new_txt = "\n".join(header_lines + body_lines + new_body_lines) + "\n"
    TXT_PATH.write_text(new_txt, encoding="utf-8")
    print(f"Appended {len(new_cards)} rows to {TXT_PATH.name}")

    # Final stats
    final_jsonl = _load_jsonl_records(JSONL_PATH)
    final_keys = {_key(c["word"], c["pos"], c["cefr"]) for c in final_jsonl}
    print()
    print(f"Final anki_notes.jsonl: {len(final_jsonl)} cards, {len(final_keys)} unique keys")
    txt_rows = sum(1 for l in TXT_PATH.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#"))
    print(f"Final txt rows: {txt_rows}")


if __name__ == "__main__":
    main()
