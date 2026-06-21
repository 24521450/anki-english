"""Build Anki Notes from Oxford jsonl + γ verdicts + vocab_list.

Output:
- data/anki_notes.jsonl: one record per card, 16-col schema matching existing txt
- English Academic Vocabulary.txt: rebuilt with same 16-col format, header preserved

Pipeline:
1. Load existing txt → (word_lower, pos, cefr) → GUID + tag set
   (word_lower preserves parenthetical disambiguators like "counter (argue against)"
   so audit glosses for homonym cards can be looked up exactly — see
   `_parse_existing_txt` and `lookup_gloss`.)
2. Load vocab_list/Oxford/{3000,5000}.md + AWL.md → set of (word, pos, cefr) target cards
3. For each jsonl record, run simplify_record (with γ merged_text override)
4. For each target (word, pos, cefr) in vocab_list:
   a. If jsonl has a record that produces a sense at this (pos, cefr) → emit card
   b. Reuse GUID from old txt
   c. Regenerate tags from data
   d. Use γ merged_text if available, else auto-concat

Card Identity contract (2026-06-21): a card is uniquely identified by
`(Word, CEFR, LIST)`. `LIST` is the primary corpus/list bucket derived from
the card's tags via `primary_list_from_tags` (Oxford_5000 > Oxford_3000 > AWL >
NO_LIST). This module is responsible for the Word + CEFR side of identity;
the LIST side is enforced by the P3B verifier (see
`tools/_verify_deck_output_p3b.py`).

Files modified:
- data/anki_notes.jsonl (new)
- English Academic Vocabulary.txt (rebuilt)

Run: python -m tools.build_notes --dry-run
"""
from __future__ import annotations
import argparse
import json
import re
import secrets
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(r'C:\Users\admin\Downloads\ankideck')

def get_word_candidates(word: str) -> list[str]:
    # Clean the word first (strip parentheticals)
    word_clean = re.sub(r"\s*\(.*?\)\s*", "", word.lower()).strip()
    
    cands = [word_clean]
    
    # 1. Suffix rules
    suffixes = [
        ("ies", "y"), ("ied", "y"), ("ying", "y"),
        ("ed", ""), ("ing", ""), ("ly", ""),
        ("es", ""), ("s", ""), ("er", ""), ("est", ""),
        ("al", ""),
    ]
    for suf, repl in suffixes:
        if word_clean.endswith(suf) and len(word_clean) > len(suf) + 2:
            base = word_clean[:-len(suf)]
            cands.append(base + repl)
            
            # Double consonant check (e.g. shunned -> shun)
            if len(base) > 1 and base[-1] == base[-2] and base[-1] in "bdfglmnprstz":
                cands.append(base[:-1] + repl)
                
            # If stripped ed or ing, try adding e (e.g. accused -> accuse)
            if suf in ("ed", "ing"):
                cands.append(base + "e")
                
    # 2. Spelling & Hyphenation
    if word_clean.endswith("or") and len(word_clean) > 3:
        cands.append(word_clean[:-2] + "our")
    if word_clean.endswith("our") and len(word_clean) > 4:
        cands.append(word_clean[:-3] + "or")
        
    if "wellbeing" in word_clean:
        cands.append("well-being")
    if "byproduct" in word_clean:
        cands.append("by-product")
    if "shortsighted" in word_clean:
        cands.append("short-sighted")
        
    # 3. Irregulars
    irregular = {
        "criteria": "criterion",
        "vertebrae": "vertebra",
        "ligaments": "ligament"
    }
    if word_clean in irregular:
        cands.append(irregular[word_clean])
        
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def find_idioms_for_word(word_clean: str, idioms_db: dict) -> list[tuple[dict, dict]]:
    if word_clean in idioms_db:
        return idioms_db[word_clean]
    for phrase_clean, records in idioms_db.items():
        if word_clean in phrase_clean or phrase_clean in word_clean:
            return records
    return []

JSONL_PATH = PROJECT_ROOT / 'data' / 'oxford_merged.jsonl'
GAMMA_VERDICTS_PATH = PROJECT_ROOT / 'data' / 'simplify_diff' / 'gamma_all_verdicts.json'
TXT_PATH = PROJECT_ROOT / 'English Academic Vocabulary.txt'
OUT_JSONL = PROJECT_ROOT / 'data' / 'anki_notes.jsonl'
OXFORD_3000_MD = PROJECT_ROOT / 'vocab_list' / 'Oxford' / 'Oxford_3000.md'
OXFORD_5000_MD = PROJECT_ROOT / 'vocab_list' / 'Oxford' / 'Oxford_5000.md'
AWL_MD = PROJECT_ROOT / 'vocab_list' / 'AWL' / 'AWL.md'
AUDIT_JSONL_PATH = PROJECT_ROOT / 'data' / 'audit_full_deck_v2.jsonl'

TXT_HEADER_LINES = 6  # 6 #separator/html/guid/notetype/deck/tags lines


# === Vocab list parsing (mirrors corpus_tag_sync.py) ============================

POS_NORM = {
    'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb',
    'prep': 'preposition', 'pron': 'pronoun', 'det': 'determiner',
    'conj': 'conjunction', 'num': 'number', 'modal': 'modal',
    'predet': 'predeterminer', 'aux': 'auxiliary', 'exclam': 'exclamation',
    'abbr': 'abbreviation', 'exclamation': 'exclamation',
    'indefinite article': 'indefinite article', 'definite article': 'definite article',
    'number': 'number',
}


def _parse_vocab_list(path: Path) -> set[tuple[str, str, str]]:
    """Parse vocab_list/Oxford/{Oxford_3000,5000}.md or AWL.md. Returns (word_lower, pos, cefr) tuples.

    AWL format: '| **word** | pos | CEFR |'  (same as Oxford)
    Oxford format: '| **word** | pos | CEFR |'
    Both use the same regex.
    """
    out: set[tuple[str, str, str]] = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.startswith('| **'):
            continue
        m = re.match(r'\| \*\*([^*]+)\*\* \| ([^|]+) \| ([^|]+) \|', line)
        if not m:
            continue
        word = m.group(1).strip()
        word_clean = word.split(' (')[0].strip().lower()
        pos_str = m.group(2).strip()
        cefr = m.group(3).strip().upper()
        if word_clean == 'a, an' or word_clean == 'a':
            pos_list = ['indefinite article']
        else:
            raw_parts = []
            for p in re.split(r',|/', pos_str):
                p = p.strip()
                if p:
                    raw_parts.append(p)
            pos_list = []
            for p in raw_parts:
                p_clean = p.rstrip('.')
                pos_list.append(POS_NORM.get(p_clean, p_clean))
        for p in pos_list:
            out.add((word_clean, p, cefr))
    return out


# === Existing txt parsing (mirror of opal_sync._parse_txt_card) ================

def _parse_existing_txt(path: Path) -> dict[tuple[str, str, str], dict]:
    """Return map (word_lower, pos, cefr) → {guid, source1, source2, deck, tags, uk_audio, us_audio, all_17_cols}.

    Card Identity contract (2026-06-21): the key's `word_lower` preserves the
    parenthetical disambiguator verbatim (lowercased). Examples:
        "counter (argue against)"  → key uses the full string, not "counter"
        "grave (serious)"         → full string
        "strip (long narrow piece)" → full string

    Rationale: audit glosses (`data/audit_full_deck_v2.jsonl`) are keyed by
    the FULL disambiguated word, so exact-match lookup requires preserving it
    here. Source lookup against the Oxford jsonl still uses
    `get_word_candidates()` which strips parentheticals, so word resolution
    is unaffected.

    A separate `word_base` field (the disambiguator-stripped base word) is
    stored on each row to ease downstream JSONL lookups. Multi-word forms
    like "a (an)" continue to split on ' (' for legacy reasons.

    Accepts both 16-col (legacy) and 17-col (current) rows; 16-col rows are
    read with idioms='' and tags=parts[15].
    """
    by_key: dict[tuple[str, str, str], dict] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 16:
            continue
        if len(parts) >= 17:
            guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf, uk, us, src1, src2, cefr, idioms, tags = parts[:17]
        else:
            # Legacy 16-col row: idioms field missing, tags in last col.
            guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf, uk, us, src1, src2, cefr, tags = parts[:16]
            idioms = ''
        word_lower = word.strip().lower()  # preserve parenthetical disambiguator
        word_base = word_lower.split(' (')[0].strip()  # base word for source lookup
        by_key[(word_lower, pos, cefr)] = {
            'guid': guid,
            'notetype': notetype,
            'deck': deck,
            'word_orig': word,  # keep original case/spelling (with disambiguator)
            'word_base': word_base,
            'pos': pos,
            'ipa': ipa,
            'definition_orig': defn,
            'example_orig': ex,
            'collocations_orig': coll,
            'wordfamily_orig': wf,
            'uk_audio': uk,
            'us_audio': us,
            'source1': src1,
            'source2': src2,
            'cefr': cefr,
            'idioms_orig': idioms,
            'tags': tags,
            'all_16': parts,
        }
    return by_key


# === γ verdict handling ======================================================

def _load_gamma_verdicts(path: Path) -> dict[str, dict]:
    """Load γ verdicts keyed by cluster_hash."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    d = json.loads(path.read_text(encoding='utf-8'))
    for v in d.get('verdicts', []):
        out[v['cluster_hash']] = v
    return out


# === Simplify record (apply γ merged_text) ===================================

def _simplify_with_gamma(record: dict, gamma: dict) -> list:
    """Run simplify_record, but override text on clusters with γ merge verdicts.

    For each MergedSense produced by simplify_record, check if its cluster_hash
    (hash of word + pos + sorted def_idx) has a γ merge verdict with merged_text.
    If yes, replace sense.text with the γ text.
    """
    import hashlib
    from src.deck_builder.simplify_senses import simplify_record, TEXT_JOIN_SEPARATOR, _resolve_def

    base = simplify_record(record)
    if not base:
        return base

    # Build cluster_hash map for this record: each MergedSense has source_pdd_idx,
    # source_def_idx. Its cluster_hash is computed by gamma_llm (word + pos + sorted texts).
    # We need to compute the same hash for each sense, then look up in gamma.
    for i, ms in enumerate(base):
        src_texts = []
        for pd_idx, def_idx in zip(ms.source_pdd_idx, ms.source_def_idx):
            d = _resolve_def(record, pd_idx, def_idx)
            t = d.get('text', '')
            src_texts.append('' if t is None else t)
        # γ uses sorted texts for stability
        key = f"{record.get('word', '').lower()}|{ms.pos}|" + '|'.join(sorted(src_texts))
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        v = gamma.get(h)
        if v and v.get('decision') == 'merge' and v.get('merged_text'):
            base[i] = ms._replace(text=v['merged_text'])
    return base


# === Card builder ============================================================

# Separator: '|' (pipe, no spaces) — matches template contract
# (back_template.txt:172 splits on '|', front_template.txt:82 same).
# Template pairs def[i] with ex[i] by index, so def and ex MUST have the
# same number of chunks. Within-sense `; ` (Oxford convention) is preserved
# by simplify_senses.TEXT_JOIN_SEPARATOR — template doesn't split on `;`
# so it doesn't break row separation.
# Collocations separator: '|' (no spaces) — keep existing convention from txt.
DEF_SEPARATOR = '|'
EX_SEP = '|'
COLL_SEPARATOR = '|'


class BuiltCard(NamedTuple):
    """One Anki Note, encoded as 17-col Anki txt row."""
    guid: str
    notetype: str
    deck: str
    word: str
    pos: str
    ipa: str
    definition: str
    example: str
    collocations: str
    wordfamily: str
    uk_audio: str
    us_audio: str
    source1: str
    source2: str
    cefr: str
    idioms: str
    tags: str

    def to_tsv(self) -> str:
        return '\t'.join([
            self.guid, self.notetype, self.deck, self.word, self.pos, self.ipa,
            self.definition, self.example, self.collocations, self.wordfamily,
            self.uk_audio, self.us_audio, self.source1, self.source2, self.cefr,
            self.idioms, self.tags,
        ])

    def to_dict(self) -> dict:
        """For jsonl output (1:1 with txt cols)."""
        return {
            'guid': self.guid,
            'notetype': self.notetype,
            'deck': self.deck,
            'word': self.word,
            'pos': self.pos,
            'ipa': self.ipa,
            'definition': self.definition,
            'example': self.example,
            'collocations': self.collocations,
            'wordfamily': self.wordfamily,
            'uk_audio': self.uk_audio,
            'us_audio': self.us_audio,
            'source1': self.source1,
            'source2': self.source2,
            'cefr': self.cefr,
            'idioms': self.idioms,
            'tags': self.tags,
        }


def _format_examples(examples: list, max_n: int = 1) -> str:
    """Format a list of example dicts into a single string (pipe-separated).

    Default max_n=1 ensures correct pairing with def[i] in the template
    (back_template.txt:172): both def and ex are pipe-separated, so
    def[i] pairs with ex[i] by index. If max_n=2, ex would have 2 chunks
    per sense, breaking the index pairing — def[1] would pair with
    sense-1's 2nd example instead of sense-2's 1st. Bump max_n only if
    the template is updated to handle 2 examples per cell.
    """
    parts = []
    for ex in (examples or [])[:max_n]:
        t = (ex.get('text') or '').strip()
        if t:
            parts.append(t)
    return EX_SEP.join(parts)


def _format_collocations(colls: dict) -> str:
    """Format collocations dict into pipe-separated string.

    Schema: Oxford (multi-bucket) and Cambridge (single bucket); both produce
    a list of (category, [words]) tuples. Flatten all words, dedupe.
    """
    from src.scraper._common import flatten_collocations
    flat = flatten_collocations(colls or {})
    seen: set[str] = set()
    out: list[str] = []
    for v in flat:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return COLL_SEPARATOR.join(out)


def _format_idioms(idioms: list) -> str:
    """Serialize idioms list to deck format.

    Per grill session decision (2026-06-19):
        phrase :: text :: ex1 | ex2 $$ phrase2 :: text2 :: ex1
    Delimiters:
        $$  separates idioms (top-level)
        ::  separates phrase / text / examples within an idiom
        |   separates examples within an idiom (mirrors other list fields)
    Empty / missing fields are dropped (e.g. "phrase :: :: ex1" if text empty).
    Empty input → ''.

    Filter (2026-06-20): only idioms with a CEFR level assigned (A1..C2 /
    UNCLASSIFIED) survive. Idioms with cefr=None are dropped — Oxford sometimes
    parses idioms without an explicit cefr attribute; we keep only the curated
    subset that has CEFR data.
    """
    if not idioms:
        return ''
    parts: list[str] = []
    for i in idioms:
        if i.get('cefr') is None:
            continue
        phrase = (i.get('phrase') or '').strip()
        text = (i.get('text') or '').strip()
        examples = i.get('examples') or []
        ex_str = '|'.join((e or '').strip() for e in examples if (e or '').strip())
        # Build the inner triple; drop empty trailing pieces
        inner = ' :: '.join(p for p in [phrase, text, ex_str] if p)
        if inner:
            parts.append(inner)
    return '$$'.join(parts)


def _format_wordfamily(verb_forms: dict) -> str:
    """Format verb_forms dict into a backslash-n joined string for the Anki template."""
    if not verb_forms:
        return ''
    pos_map = {
        'root': 'n', 'thirdps': 'v', 'past': 'v',
        'pastpart': 'v', 'prespart': 'v', 'neg': 'v',
        'short': 'v', 'rareshortform': 'v',
    }
    parts: list[str] = []
    for form_key, word_val in verb_forms.items():
        if word_val:
            pos_short = pos_map.get(form_key, 'n')
            parts.append(f"{word_val} ({pos_short})")
    return '\\n'.join(parts)


def _format_ipa(ipa: str | None) -> str:
    """IPA is stored as-is from the source."""
    return (ipa or '').strip()


def _normalize_ipa(s) -> str:
    """Strip whitespace + surrounding slashes. Returns bare IPA or ''."""
    if not s:
        return ""
    t = str(s).strip().strip("/").strip()
    return t


def _format_ipa_field(uk_ipa, us_ipa) -> str:
    """Format the IPA field per user decision (2026-06-20).

    - both UK and US present + DIFFERENT → "UK: /uk/ | US: /us/"
    - both present + IDENTICAL → "/uk/"
    - only one present → "/that/"
    - neither → ""
    """
    uk = _normalize_ipa(uk_ipa)
    us = _normalize_ipa(us_ipa)
    if uk and us:
        if uk == us:
            return f"/{uk}/"
        return f"UK: /{uk}/ | US: /{us}/"
    if uk:
        return f"/{uk}/"
    if us:
        return f"/{us}/"
    return ""


def _format_audio(audio: dict | None) -> tuple[str, str]:
    """Generate [sound:filename] references for UK and US audio.

    audio dict has 'uk' and 'us' fields (URLs or filenames from jsonl).
    Existing txt stores [sound:filename] form, so we mirror that.
    """
    a = audio or {}
    return a.get('uk') or '', a.get('us') or ''


def _audio_dir_filenames() -> set[str]:
    """Index all audio files in audio/ once at startup."""
    audio_dir = PROJECT_ROOT / 'audio'
    if not audio_dir.exists():
        return set()
    return {p.name for p in audio_dir.glob('*.mp3')}


# Module-level cache: filled on first call
_AUDIO_FILES: set[str] | None = None


def _resolve_audio_filename(word: str, accent: str, available: set[str]) -> str:
    """Resolve the [sound:filename] reference for a given (word, accent).

    Tries, in order:
    1. cambridge_<accent>_<word>.mp3
    2. cambridge_<accent>_<word-as-underscores>.mp3 (e.g. "set up" -> "set_up")
    3. cambridge_<accent>_<word-without-hyphens>.mp3
    4. '' (caller falls back to old txt audio)
    """
    candidates = [
        f'cambridge_{accent}_{word}.mp3',
        f'cambridge_{accent}_{word.replace(" ", "_")}.mp3',
        f'cambridge_{accent}_{word.replace("-", "")}.mp3',
    ]
    for c in candidates:
        if c in available:
            return f'[sound:{c}]'
    return ''


def _source_label(source_files: list[str] | None) -> str:
    """Determine primary source label from source_files."""
    if not source_files:
        return 'Oxford'
    first = source_files[0]
    if first.startswith('oxford_'):
        return 'Oxford'
    if first.startswith('cambridge_'):
        return 'Cambridge'
    if first.startswith('awl_'):
        return 'AWL'
    return 'Oxford'


def _regenerate_tags(
    word: str, pos: str, cefr: str, source1: str, audio_source: str,
    has_idioms: bool, oxford_lists: list[str], opal: str | None,
    awl_flag: bool, is_in_vocab_3000: bool, is_in_vocab_5000: bool,
) -> str:
    """Generate fresh tags from data, mirroring corpus_tag_sync + opal_sync.

    Per user decision (2026-06-16): full_regen, not preserve old.

    Tag categories (space-separated tokens):
      - Audio::<source>           (Audio::Cambridge if Cambridge audio present)
      - Source::<source1>          (Source::Oxford etc.)
      - CEFR::<level>              (CEFR::C1, CEFR::UNCLASSIFIED, etc.)
      - CEFR::oxford               (always — for audit)
      - Oxford_3000 / Oxford_5000   (per corpus_tag_sync)
      - OPAL_W / OPAL_S            (per opal_sync)
      - idioms                     (if has_idioms)
    """
    tags: list[str] = []

    # Audio source tag
    if audio_source and audio_source != source1:
        tags.append(f'Audio::{audio_source}')

    # Source tag
    tags.append(f'Source::{source1}')

    # CEFR tags
    tags.append(f'CEFR::{cefr}')
    tags.append('CEFR::oxford')

    # Oxford 3000/5000 (corpus_tag_sync logic)
    if is_in_vocab_3000:
        tags.append('Oxford_3000')
    if is_in_vocab_5000:
        tags.append('Oxford_5000')

    # OPAL tag
    if opal in ('W', 'S'):
        tags.append(f'OPAL_{opal}')

    # Idioms flag
    if has_idioms:
        tags.append('idioms')

    return ' '.join(tags)


def _deck_for_source(source1: str, is_awl: bool) -> str:
    """Determine deck name. Per existing txt:
    - Oxford source → 'English Academic Vocabulary::Oxford'
    - Cambridge source (TED YT) → 'English Academic Vocabulary::TED YT'
    - AWL → 'English Academic Vocabulary::AWL 50 Academic Words'
    """
    if is_awl or source1 == 'AWL':
        return 'English Academic Vocabulary::AWL 50 Academic Words'
    if source1 == 'Cambridge':
        return 'English Academic Vocabulary::TED YT'
    return 'English Academic Vocabulary::Oxford'


def _new_guid() -> str:
    """Generate a 10-char alphanumeric GUID in Anki's style."""
    # Anki uses 10-char base64-like. Use secrets for collision-free random.
    import string
    alphabet = string.ascii_letters + string.digits + '!#$%&()*+,-./:;<=>?@[]^_`{|}~'
    return ''.join(secrets.choice(alphabet) for _ in range(10))


def build_record_cards(
    record: dict,
    target_keys: set[tuple[str, str, str]],
    existing: dict[tuple[str, str, str], dict],
    gamma: dict,
    vocab_3000: set[tuple[str, str, str]],
    vocab_5000: set[tuple[str, str, str]],
    vocab_awl: set[tuple[str, str, str]],
) -> list[BuiltCard]:
    """Build all cards for one jsonl record, filtered by vocab_list membership.

    Returns a list of BuiltCard, one per (word, pos, cefr) in target_keys that
    matches a sense produced by simplify_with_gamma.
    """
    word = record.get('word', '').lower()
    source_files = record.get('source_files') or []
    source1 = _source_label(source_files)
    audio = record.get('audio') or {}
    is_awl = any(sf.startswith('awl_') for sf in source_files)

    # Run simplify with γ override
    simplified = _simplify_with_gamma(record, gamma)
    if not simplified:
        return []

    cards: list[BuiltCard] = []
    # Group by (pos, cefr) for a single card
    by_key: dict[tuple[str, str], list] = {}
    for ms in simplified:
        cefr = ms.cefr or 'UNCLASSIFIED'
        if ms.text and (word, ms.pos, cefr) in target_keys:
            by_key.setdefault((ms.pos, cefr), []).append(ms)

    for (pos, cefr), senses in by_key.items():
        if not senses:
            continue
        # Sense Sorting (replaces the legacy Sense Cap, 2026-06-21):
        # retain every CEFR-matching sense. The simplified list is already
        # ordered by β→γ priority (sensenum_local proxy), so no further
        # truncation or reordering is applied here.
        capped = senses

        # Definition text
        defn = DEF_SEPARATOR.join((s.text or '') for s in capped if (s.text or ''))
        # Example text
        ex = EX_SEP.join(_format_examples(s.examples or []) for s in capped)
        # Per user (2026-06-20): Collocations and WordFamily fields are emptied.
        coll = ''
        wf = ''
        # IPA: from uk_ipa / us_ipa at record top level (parser-emitted, 2026-06-20).
        ipa = _format_ipa_field(record.get('uk_ipa'), record.get('us_ipa'))
        # Audio
        uk, us = _format_audio(audio)

        # Tags regeneration
        has_idioms = bool(record.get('idioms'))
        is_in_3000 = (word, pos, cefr) in vocab_3000
        is_in_5000 = (word, pos, cefr) in vocab_5000
        is_in_awl = (word, pos, cefr) in vocab_awl
        # OPAL tag from jsonl
        opal = record.get('opal')
        # Audio source: if record has Cambridge audio URL, tag Audio::Cambridge
        audio_source = source1
        if audio.get('uk') and 'cambridge' in str(audio.get('uk', '')).lower():
            audio_source = 'Cambridge'
        elif audio.get('us') and 'cambridge' in str(audio.get('us', '')).lower():
            audio_source = 'Cambridge'
        # Per user: Cambridge only contributes audio tag. If primary source is
        # Oxford but Cambridge audio URLs are present, tag the audio as Cambridge.
        # (We infer this from the URL itself, which contains 'cambridge' or 'oxford'.)
        # Refined: use the existing txt's audio source as ground truth.
        # For new cards, default to source1.

        tags = _regenerate_tags(
            word=word, pos=pos, cefr=cefr, source1=source1, audio_source=audio_source,
            has_idioms=has_idioms, oxford_lists=record.get('oxford_lists') or [],
            opal=opal, awl_flag=is_in_awl, is_in_vocab_3000=is_in_3000, is_in_vocab_5000=is_in_5000,
        )

        # GUID: reuse from existing, else generate new
        key = (word, pos, cefr)
        old = existing.get(key)
        if old:
            guid = old['guid']
            deck = old['deck']  # preserve existing deck
        else:
            guid = _new_guid()
            deck = _deck_for_source(source1, is_awl)

        cards.append(BuiltCard(
            guid=guid,
            notetype='English Academic Vocabulary Model',
            deck=deck,
            word=record.get('word', ''),  # original case
            pos=pos,
            ipa=ipa,
            definition=defn,
            example=ex,
            collocations=coll,
            wordfamily=wf,
            uk_audio=uk,
            us_audio=us,
            source1=source1,
            source2='AWL' if is_in_awl else 'Oxford',
            cefr=cefr,
            idioms=_format_idioms(record.get('idioms') or []),
            tags=tags,
        ))
    return cards


def _merge_collocations_dicts(dicts: list[dict]) -> dict:
    """Merge multiple collocation dicts by key, union-ing values."""
    out: dict[str, list] = {}
    for d in dicts:
        for k, v in (d or {}).items():
            if isinstance(v, list):
                out.setdefault(k, [])
                for item in v:
                    if item not in out[k]:
                        out[k].append(item)
            else:
                out.setdefault(k, []).append(v)
    return out


# === Audit gloss lookup ======================================================

def lookup_gloss(
    audit_glosses: dict[tuple[str, str, str], str],
    word: str,
    pos_str: str,
    cefr: str,
    resolved_word: str,
    resolved_pos_parts: list[str],
    new_cefr: str,
) -> str | None:
    """Look up an audit gloss for `(word, pos, cefr)`.

    Card Identity contract (2026-06-21): the TXT word may carry a
    parenthetical disambiguator (e.g. "counter (argue against)") while
    the audit glosses are keyed by the FULL disambiguated word. Lookup
    order:

    1. Try the FULL TXT word (with disambiguator if any) first — this
       matches audit glosses for homonym cards exactly.
    2. If the FULL word has a disambiguator AND the audit gloss dict
       has disambiguated sibling keys at the same (pos, cefr) (e.g.
       "counter (long flat surface)" alongside "counter (argue against)"),
       REFUSE to fall back to the base word. The base word would be a
       ghost verdict from a different sense — applying it would emit
       wrong-meaning definitions for disambiguated cards.
    3. Otherwise, fall back to the base word (parens-stripped) and try
       the same chain.
    4. Finally, try individual POS parts (multi-POS cards like
       "noun, verb" → match either audit gloss and join with ' | ').

    The disambiguator guard logic mirrors the one in
    `tools/_apply_glosses_to_txt.py::_lookup_verdict` — both must agree
    on the same fallback semantics for a given card.

    Module-level (not nested in `main`) so tests can call it directly.
    """
    word_lower = (word or '').strip().lower()
    word_base = word_lower.split(' (')[0].strip()
    has_disambiguator = word_base != word_lower
    pos_lower = pos_str.strip().lower()

    # 1. Direct match on FULL TXT word (preserves parenthetical).
    full_key = (word_lower, pos_lower, cefr)
    if full_key in audit_glosses:
        return audit_glosses[full_key]

    # 2. Disambiguator guard: if the TXT word has a parenthetical AND
    # the audit has disambiguated siblings at this (pos, cefr), the
    # base-word key would be a ghost verdict from a different sense —
    # refuse to apply it.
    if has_disambiguator:
        sibling_present = any(
            k[0].startswith(word_base + ' (') and (k[1], k[2]) == (pos_lower, cefr)
            for k in audit_glosses
        )
        if sibling_present:
            # Try resolved-CEFR under same guard before giving up.
            if cefr != new_cefr:
                sib_cefr_present = any(
                    k[0].startswith(word_base + ' (') and (k[1], k[2]) == (pos_lower, new_cefr)
                    for k in audit_glosses
                )
                if sib_cefr_present:
                    return None
            return None

    # 3. Safe to try base word (no disambiguator, or no siblings).
    # Try base-word direct match at original CEFR, then resolved CEFR.
    _resolved_pos_str = ', '.join(resolved_pos_parts) if resolved_pos_parts else pos_lower
    base_candidate_keys = [
        (word_base, _resolved_pos_str, new_cefr),
        (word_base, pos_lower, new_cefr),
        (word_base, _resolved_pos_str, cefr),
        (word_base, pos_lower, cefr),
    ]
    for gk in base_candidate_keys:
        if gk in audit_glosses:
            return audit_glosses[gk]

    # 4. Multi-POS: try individual POS parts at base word (no
    # disambiguator case — disambiguated cards stop here at step 2).
    orig_pos_parts = [p.strip().lower() for p in pos_str.split(',') if p.strip()]
    res_pos_parts = [p.strip().lower() for p in resolved_pos_parts]

    all_parts = []
    seen_parts = set()
    for p in orig_pos_parts + res_pos_parts:
        if p not in seen_parts:
            all_parts.append(p)
            seen_parts.add(p)

    matched_glosses = []
    seen_glosses = set()
    for p in all_parts:
        _pos_lookup_keys = [
            (word_lower, p, cefr),
            (word_base, p, new_cefr),
            (word_lower, p, new_cefr),
            (word_base, p, cefr),
        ]
        for gk in _pos_lookup_keys:
            if gk in audit_glosses:
                g = audit_glosses[gk]
                if g not in seen_glosses:
                    matched_glosses.append(g)
                    seen_glosses.add(g)
                break  # found for this POS part

    if matched_glosses:
        return ' | '.join(matched_glosses)
    return None


# === Main =====================================================================

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true', help='Compute but do not write')
    ap.add_argument('--jsonl', type=Path, default=JSONL_PATH)
    ap.add_argument('--txt', type=Path, default=TXT_PATH)
    ap.add_argument('--out-jsonl', type=Path, default=OUT_JSONL)
    ap.add_argument('--gamma', type=Path, default=GAMMA_VERDICTS_PATH)
    args = ap.parse_args()

    # Load inputs
    sys.path.insert(0, str(PROJECT_ROOT))
    print('=== Loading inputs ===', file=sys.stderr)
    # Index audio files once for [sound:...] resolution
    global _AUDIO_FILES
    _AUDIO_FILES = _audio_dir_filenames()
    print(f'  audio files: {len(_AUDIO_FILES)}', file=sys.stderr)
    print(f'Vocab 3000: {OXFORD_3000_MD.name}', file=sys.stderr)
    print(f'Vocab 5000: {OXFORD_5000_MD.name}', file=sys.stderr)
    print(f'Vocab AWL:   {AWL_MD.name}', file=sys.stderr)
    vocab_3000 = _parse_vocab_list(OXFORD_3000_MD)
    vocab_5000 = _parse_vocab_list(OXFORD_5000_MD)
    vocab_awl = _parse_vocab_list(AWL_MD)
    print(f'  3000: {len(vocab_3000)} entries', file=sys.stderr)
    print(f'  5000: {len(vocab_5000)} entries', file=sys.stderr)
    print(f'  AWL:  {len(vocab_awl)} entries', file=sys.stderr)
    target_keys = vocab_3000 | vocab_5000 | vocab_awl
    print(f'  total target keys: {len(target_keys)}', file=sys.stderr)

    print(f'Loading existing txt: {args.txt.name}', file=sys.stderr)
    existing = _parse_existing_txt(args.txt)
    print(f'  existing cards: {len(existing)}', file=sys.stderr)

    print(f'Loading gamma verdicts: {args.gamma.name}', file=sys.stderr)
    gamma = _load_gamma_verdicts(args.gamma)
    print(f'  gamma verdicts: {len(gamma)}', file=sys.stderr)

    # Load audit glosses (gloss_after) — override raw defs during card building
    audit_glosses: dict[tuple[str, str, str], str] = {}
    if AUDIT_JSONL_PATH.exists():
        with AUDIT_JSONL_PATH.open(encoding='utf-8') as _af:
            for _line in _af:
                if not _line.strip():
                    continue
                _r = json.loads(_line)
                _ga = (_r.get('gloss_after') or '').strip()
                if not _ga:
                    continue
                _key = (
                    _r.get('word', '').strip().lower(),
                    _r.get('pos', '').strip().lower(),
                    _r.get('cefr', '').strip().upper(),
                )
                audit_glosses[_key] = _ga
        print(f'  audit glosses loaded: {len(audit_glosses)}', file=sys.stderr)
    else:
        print(f'  audit_full_deck_v2.jsonl not found — skipping gloss_after override', file=sys.stderr)

    # Load filled.json keys to preserve them verbatim in build_notes
    FILLED_PATH = PROJECT_ROOT / 'data' / 'missing_oxford_5000_cards_filled.json'
    filled_keys = set()
    if FILLED_PATH.exists():
        try:
            filled_data = json.load(FILLED_PATH.open(encoding='utf-8'))
            for r in filled_data:
                filled_keys.add((
                    (r.get('word') or '').strip().lower(),
                    (r.get('pos') or '').strip().lower(),
                    (r.get('cefr') or '').strip().upper()
                ))
            print(f'  filled keys loaded: {len(filled_keys)}', file=sys.stderr)
        except Exception as e:
            print(f'  error loading filled keys: {e}', file=sys.stderr)

    # Index jsonl by word_lower and idioms
    print(f'Loading jsonl: {args.jsonl.name}', file=sys.stderr)
    by_word: dict[str, list[dict]] = {}
    idioms_db: dict[str, list[tuple[dict, dict]]] = {}
    with args.jsonl.open(encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            w = (r.get('word') or '').lower()
            if w:
                by_word.setdefault(w, []).append(r)
            # Index idioms
            for idiom in r.get("idioms") or []:
                phrase = idiom.get("phrase") or ""
                phrase_clean = re.sub(r"\s*\(.*?\)\s*", "", phrase.lower()).strip()
                if phrase_clean:
                    idioms_db.setdefault(phrase_clean, []).append((r, idiom))
    print(f'  unique words in jsonl: {len(by_word)}', file=sys.stderr)
    print(f'  unique idioms in jsonl: {len(idioms_db)}', file=sys.stderr)

    # Build cards
    # Source of truth: existing txt rows (per user decision 2026-06-16).
    # For each row, find jsonl record(s) matching the word, run simplify+γ,
    # extract senses at (pos, cefr) and merge into 1 row.
    # Multi-POS like "noun, verb" → look up both POSes in jsonl, merge into 1 row.
    print('=== Building cards (existing txt scope) ===', file=sys.stderr)
    all_cards: list[BuiltCard] = []
    seen_keys: set[tuple[str, str, str]] = set()
    # emitted_keys tracks the RESOLVED (post-POS-fix) keys we've already emitted
    # a card for. Prevents the Type A bug (2026-06-20) where 2 old txt rows with
    # different POS at the same CEFR both remap to the same resolved key and
    # produce 2 cards at the same key. Keep first, skip rest.
    emitted_keys: set[tuple[str, str, str]] = set()
    missing_in_jsonl: set[tuple[str, str, str]] = set()

    # Pre-compute per-word simplified senses (jsonl record → list of MergedSense)
    print('  Pre-computing simplified senses for all jsonl records...', file=sys.stderr)
    by_word_simplified: dict[str, list[tuple[dict, list]]] = {}
    for word_lower, records in by_word.items():
        items: list[tuple[dict, list]] = []
        for record in records:
            try:
                simplified = _simplify_with_gamma(record, gamma)
                if simplified:
                    items.append((record, simplified))
            except Exception as e:
                print(f'    simplify error for {word_lower}: {e}', file=sys.stderr)
        if items:
            by_word_simplified[word_lower] = items
    print(f'  words with simplified data: {len(by_word_simplified)}', file=sys.stderr)

    # Index senses by (word_lower, pos, cefr) across all records
    # (a word may have multiple jsonl records: e.g. homonyms 'set' (n) and 'set' (v))
    senses_index: dict[tuple[str, str, str], list] = {}  # (word, pos, cefr) → list of MergedSense
    sense_source_record: dict[tuple[str, str, str], dict] = {}  # → first record that produced a sense at this key
    for word_lower, items in by_word_simplified.items():
        for record, senses in items:
            for ms in senses:
                cefr = ms.cefr or 'UNCLASSIFIED'
                key = (word_lower, ms.pos, cefr)
                senses_index.setdefault(key, []).append(ms)
                # Track the "primary" record for audio/verb_forms/idioms lookup
                sense_source_record.setdefault(key, record)

    # Now iterate existing txt rows
    # Per user decision (2026-06-16): handle 3 types of POS mismatch.
    # - Type A: word in jsonl, POS wrong → fix POS
    # - Type B: word is inflected form → lemmatize + fix POS
    # - Type C: word not in jsonl at all → drop
    # After fix, re-CEFR from jsonl. If still UNCLASSIFIED → drop.
    print(f'  Iterating {len(existing)} existing txt rows (3-type POS fix)...', file=sys.stderr)

    # Build word -> available POS set (from pos_data, not senses)
    word_pos_set: dict[str, set[str]] = {}
    for word_lower, records in by_word.items():
        ps: set[str] = set()
        for record in records:
            for pd in record.get('pos_data', []) or []:
                p = pd.get('pos')
                if p:
                    ps.add(p)
        word_pos_set[word_lower] = ps

    type_a_count = 0
    type_b_count = 0
    type_c_count = 0
    dup_emit_skip_count = 0  # 2026-06-20: Type A POS remap → same resolved key
    unclassified_drop_count = 0
    pos_fixed_keys: list[tuple] = []  # for audit
    dropped_keys: list[tuple] = []

    for key in sorted(existing.keys()):
        word_lower, pos_str, cefr = key
        if key in seen_keys:
            continue
        old = existing[key]
        if key in filled_keys:
            # Preserve injected card verbatim to prevent remapping/collisions
            # Overwrite definition if matched in audit_glosses
            filled_pos_parts = [p.strip().lower() for p in old['pos'].split(',') if p.strip()]
            g = lookup_gloss(audit_glosses, word_lower, old['pos'], cefr, word_lower, filled_pos_parts, cefr)
            defn_override = g if g is not None else old['definition_orig']
            card = BuiltCard(
                guid=old['guid'],
                notetype=old['notetype'],
                deck=old['deck'],
                word=old['word_orig'],
                pos=old['pos'],
                ipa=old['ipa'],
                definition=defn_override,
                example=old['example_orig'],
                collocations=old['collocations_orig'],
                wordfamily=old['wordfamily_orig'],
                uk_audio=old['uk_audio'],
                us_audio=old['us_audio'],
                source1=old['source1'],
                source2=old['source2'],
                cefr=old['cefr'],
                idioms=old['idioms_orig'],
                tags=old['tags']
            )
            all_cards.append(card)
            emitted_keys.add(key)
            seen_keys.add(key)
            continue
        # Split multi-POS: 'noun, verb' → ['noun', 'verb']
        pos_parts = [p.strip() for p in pos_str.split(',') if p.strip()]

        # Phase 1 & 2: Match senses/records (with candidates, POS resolution and idioms)
        cands = get_word_candidates(word_lower)
        matched_records = []
        resolved_word = word_lower
        for cand in cands:
            if cand in by_word:
                matched_records = by_word[cand]
                resolved_word = cand
                break
        
        # Determine available POS for the matched word
        avail = word_pos_set.get(resolved_word, set())

        # POS resolution (Type A / B equivalent)
        # If the card has any valid POS part in avail, keep all original parts (no remap)
        # to preserve mixed/merged POS (e.g. phrasal verb, verb). Otherwise, fall back
        # to remapping the parts.
        has_overlap = any(p in avail for p in pos_parts)
        resolved_pos_parts = []
        if has_overlap:
            # Keep original order, but clean it up
            resolved_pos_parts = pos_parts
        else:
            seen_pos: set[str] = set()
            for p in pos_parts:
                if p in avail:
                    if p not in seen_pos:
                        resolved_pos_parts.append(p)
                        seen_pos.add(p)
                elif avail:
                    cand = next(iter(sorted(avail)))
                    if cand not in seen_pos:
                        resolved_pos_parts.append(cand)
                        seen_pos.add(cand)
        # Audit POS modifications
        if resolved_word != word_lower:
            type_b_count += 1
            pos_fixed_keys.append((key, 'B', resolved_word, tuple(resolved_pos_parts)))
        elif resolved_pos_parts != pos_parts:
            type_a_count += 1
            pos_fixed_keys.append((key, 'A', tuple(resolved_pos_parts)))
            
        all_senses_for_row: list = []
        primary_record: dict | None = None
        used_fallback_cefr: str | None = None
        
        if matched_records:
            primary_record = matched_records[0]
            # Collect senses
            for p in resolved_pos_parts:
                sense_key = (resolved_word, p, cefr)
                if sense_key in senses_index:
                    all_senses_for_row.extend(senses_index[sense_key])
                else:
                    # Sibling CEFR fallback
                    for (w, pos, c), senses in senses_index.items():
                        if w == resolved_word and pos == p:
                            all_senses_for_row.extend(senses)
                            used_fallback_cefr = c
                            break
                            
        # Senses empty or not found in headwords -> try idioms
        if not all_senses_for_row:
            word_clean = cands[0]
            matched_idioms = find_idioms_for_word(word_clean, idioms_db)
            if matched_idioms:
                primary_record, idiom_dict = matched_idioms[0]
                idiom_cefr = idiom_dict.get("cefr") or "UNCLASSIFIED"
                from src.deck_builder.simplify_senses import MergedSense
                mock_sense = MergedSense(
                    pos=pos_parts[0],
                    cefr=idiom_cefr,
                    text=idiom_dict.get("text") or "",
                    register_tags=[],
                    topics=[],
                    collocations={},
                    examples=[{"text": ex} for ex in idiom_dict.get("examples") or []],
                    countability=None,
                    domain=None,
                    is_phrase=True,
                    is_idiom=True,
                    source_pdd_idx=[0],
                    source_def_idx=[0],
                    cefr_originals=[idiom_cefr],
                    cefr_sources=["idiom"]
                )
                all_senses_for_row = [mock_sense]
                resolved_word = word_lower


        if not all_senses_for_row:
            # Per user (2026-06-16): drop only when JSONL truly has no entry for this word+pos.
            # pos_data=[] or word not in JSONL → drop. The 3-type POS fix above already
            # exhausted both the exact match AND the lemmatize-then-Type-A retry paths.
            type_c_count += 1
            dropped_keys.append((key, 'C'))
            missing_in_jsonl.add(key)
            continue
        # Sense Sorting (replaces the legacy Sense Cap, 2026-06-21):
        # retain every CEFR-matching sense — no [:3] truncation. The order
        # is preserved as-is from the upstream β→γ pipeline (sensenum_local proxy).
        capped = all_senses_for_row
        # Dedupe identical texts
        seen_texts: set[str] = set()
        deduped: list = []
        for s in capped:
            t = (s.text or '').strip()
            if t and t not in seen_texts:
                seen_texts.add(t)
                deduped.append(s)
        capped = deduped
        if not capped:
            # All senses have empty text after dedup — no real def to show
            type_c_count += 1
            dropped_keys.append((key, 'C-empty'))
            missing_in_jsonl.add(key)
            continue
        # Phase 3: Re-CEFR from jsonl.
        # Per user (2026-06-16): only drop when JSONL has no senses (already handled
        # above). If senses exist but cefr is None, KEEP the card with UNCLASSIFIED.
        # The user explicitly said: "Word có senses nhưng không có CEFR badge
        # có def null ✅ Keep → UNCLASSIFIED"
        # CRITICAL: If we used a fallback to a different CEFR (Phase 1), KEEP the OLD
        # key's CEFR for this card — preserving Card Identity (1 CEFR = 1 card).
        # The sibling key at the fallback's CEFR (if it exists in old) will emit its own
        # card with its own CEFR, so no duplicates.
        if used_fallback_cefr is not None:
            new_cefr = cefr  # keep old key's CEFR
        else:
            new_cefr = capped[0].cefr or 'UNCLASSIFIED'
        # Build card
        rec = primary_record or {}
        defn = DEF_SEPARATOR.join((s.text or '') for s in capped if (s.text or ''))

        # Apply gloss_after override from audit_full_deck_v2.jsonl
        g = lookup_gloss(audit_glosses, word_lower, pos_str, cefr, resolved_word, resolved_pos_parts, new_cefr)
        if g is not None:
            defn = g
        ex = EX_SEP.join(_format_examples(s.examples or []) for s in capped)
        # Per user (2026-06-20): Collocations and WordFamily fields are emptied.
        coll = ''
        wf = ''
        # IPA: from uk_ipa / us_ipa at record top level. Fall back to Cambridge
        # record (resolved_word may match) when the primary record has no IPA.
        ipa = _format_ipa_field(rec.get('uk_ipa'), rec.get('us_ipa'))
        if not ipa:
            for camb_rec in by_word.get(resolved_word, []):
                if camb_rec is rec:
                    continue
                uk2 = camb_rec.get('uk_ipa')
                us2 = camb_rec.get('us_ipa')
                if uk2 or us2:
                    ipa = _format_ipa_field(uk2, us2)
                    break
        # Audio resolution: prefer local cambridge_<accent>_<word>.mp3, fall back to old txt's audio.
        # The Oxford jsonl has full URLs that don't match local files; Anki requires [sound:filename] form.
        # Use the resolved word (post-lemmatize) so e.g. 'setbacks' (Type B → 'setback') still finds audio.
        # card_word is assigned just below, so compute audio_word from resolved_word here.
        audio_word = resolved_word
        uk = _resolve_audio_filename(audio_word, 'uk', _AUDIO_FILES)
        us = _resolve_audio_filename(audio_word, 'us', _AUDIO_FILES)
        if not uk and old.get('uk_audio'):
            uk = old['uk_audio']
        if not us and old.get('us_audio'):
            us = old['us_audio']
        source1 = _source_label(rec.get('source_files') or [])
        is_awl = any(sf.startswith('awl_') for sf in (rec.get('source_files') or []))
        # Resolved POS: use the first resolved POS (single value for tag matching)
        resolved_pos = resolved_pos_parts[0] if resolved_pos_parts else pos_parts[0]
        # Resolved word: use the new word (lemmatized) only when the
        # change is a true inflection rewrite, not just parenthetical
        # stripping. Card Identity contract (2026-06-21): parenthetical
        # disambiguators like "counter (argue against)" must be preserved
        # in the card's display word — see the firm / yield / counter /
        # grave / strip worked examples in CONTEXT.md § Card Identity.
        word_lower_base = re.sub(r"\s*\(.*?\)\s*", "", word_lower).strip()
        if word_lower_base == resolved_word:
            # word_lower differs from resolved_word only because of the
            # parenthetical — keep the original (which preserves case +
            # disambiguator) verbatim.
            card_word = old['word_orig']
        else:
            # True lemmatization rewrite (e.g. "setbacks" → "setback").
            # Use the lemmatized base word; no parenthetical applies here
            # because Type B words are inflected forms, not homonyms.
            card_word = resolved_word

        # Tags — use resolved word+pos+cefr
        is_in_3000 = (resolved_word, resolved_pos, new_cefr) in vocab_3000
        is_in_5000 = (resolved_word, resolved_pos, new_cefr) in vocab_5000
        is_in_awl = (resolved_word, resolved_pos, new_cefr) in vocab_awl
        opal = rec.get('opal')
        audio_source = source1
        for accent in ('uk', 'us'):
            url = (rec.get('audio') or {}).get(accent) or ''
            if 'cambridge' in str(url).lower():
                audio_source = 'Cambridge'
                break
        tags = _regenerate_tags(
            word=resolved_word, pos=resolved_pos, cefr=new_cefr, source1=source1,
            audio_source=audio_source, has_idioms=bool(rec.get('idioms')),
            oxford_lists=rec.get('oxford_lists') or [], opal=opal, awl_flag=is_in_awl,
            is_in_vocab_3000=is_in_3000, is_in_vocab_5000=is_in_5000,
        )

        # GUID and deck: preserve from existing (per user: keep Anki review state)
        guid = old['guid']
        deck = old['deck']

        # Per user (2026-06-20): emit-key dedup. After Type A POS remap, multiple
        # old rows can resolve to the same (word, pos, cefr) key. Keep first,
        # skip subsequent duplicates. First-seen wins so existing GUIDs are
        # preserved (review state stays intact).
        emit_pos = ', '.join(resolved_pos_parts) if resolved_pos_parts else pos_str
        emit_key = (resolved_word, emit_pos, new_cefr)
        if emit_key in emitted_keys:
            print(
                f'    SKIP dup emit: old={key!r} → resolved={emit_key!r} '
                f'(kept earlier card with GUID {guid!r})',
                file=sys.stderr,
            )
            dup_emit_skip_count += 1
            seen_keys.add(key)
            continue
        emitted_keys.add(emit_key)

        all_cards.append(BuiltCard(
            guid=guid,
            notetype='English Academic Vocabulary Model',
            deck=deck,
            word=card_word,
            pos=emit_pos,  # use fixed POS (now deduped)
            ipa=ipa,
            definition=defn,
            example=ex,
            collocations=coll,
            wordfamily=wf,
            uk_audio=uk,
            us_audio=us,
            source1=source1,
            source2='AWL' if is_in_awl else 'Oxford',
            cefr=new_cefr,  # NEW: re-CEFR from jsonl
            idioms=_format_idioms(rec.get('idioms') or []),
            tags=tags,
        ))
        seen_keys.add(key)

    print(f'  Type A (POS fix): {type_a_count}', file=sys.stderr)
    print(f'  Type B (lemmatize): {type_b_count}', file=sys.stderr)
    print(f'  Type C (drop, no data): {type_c_count}', file=sys.stderr)
    print(f'  Dup emit skipped: {dup_emit_skip_count}', file=sys.stderr)
    print(f'  UNCLASSIFIED drop: {unclassified_drop_count}', file=sys.stderr)
    print(f'  POS-fixed keys: {len(pos_fixed_keys)}', file=sys.stderr)
    print(f'  Dropped keys: {len(dropped_keys)}', file=sys.stderr)

    print(f'  built cards: {len(all_cards)}', file=sys.stderr)
    print(f'  missing in jsonl: {len(missing_in_jsonl)}', file=sys.stderr)
    if missing_in_jsonl:
        # Show first 10
        sample = sorted(missing_in_jsonl)[:10]
        print(f'  sample missing: {sample}', file=sys.stderr)

    # Write jsonl
    if not args.dry_run:
        args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.out_jsonl.open('w', encoding='utf-8') as f:
            for c in all_cards:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + '\n')
        print(f'Wrote: {args.out_jsonl}', file=sys.stderr)

        # Re-emit txt (preserve header, but update tags column index)
        header_lines = []
        for line in args.txt.read_text(encoding='utf-8').splitlines()[:TXT_HEADER_LINES]:
            if line.startswith('#tags column:'):
                header_lines.append('#tags column:17')
            else:
                header_lines.append(line)
        body = [c.to_tsv() for c in all_cards]
        new_txt = '\n'.join(header_lines + body) + '\n'
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = args.txt.with_suffix(f'.txt.bak_pre_build_{ts}')
        backup.write_text(args.txt.read_text(encoding='utf-8'), encoding='utf-8')
        args.txt.write_text(new_txt, encoding='utf-8')
        print(f'Wrote: {args.txt}  (backup: {backup.name})', file=sys.stderr)

    # Quick stats
    print('\n=== Quick stats ===', file=sys.stderr)
    by_cefr = Counter(c.cefr for c in all_cards)
    by_deck = Counter(c.deck for c in all_cards)
    by_source = Counter(c.source1 for c in all_cards)
    print(f'  by cefr: {dict(by_cefr)}', file=sys.stderr)
    print(f'  by deck: {dict(by_deck)}', file=sys.stderr)
    print(f'  by source1: {dict(by_source)}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
