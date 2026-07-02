"""Build Anki Notes logic moved to src/deck_builder.

Exposes the clean public Interface:
- BuildNotesPaths
- BuildNotesResult
- build_notes(paths: BuildNotesPaths) -> BuildNotesResult
"""
from __future__ import annotations
import hashlib
import json
import re
import secrets
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from src.deck_builder.simplify_senses import simplify_record, TEXT_JOIN_SEPARATOR, _resolve_def
from src.scraper.cambridge_audio import resolve_audio_pos
from src.deck_builder.review_overrides import load_review_overrides, apply_review_overrides
from src.deck_builder.synonym_annotator import (
    load_relation_overrides,
    annotate_card_examples,
    get_relation_specs_for_card,
)

POS_NORM = {
    'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb',
    'prep': 'preposition', 'pron': 'pronoun', 'det': 'determiner',
    'conj': 'conjunction', 'num': 'number', 'modal': 'modal',
    'predet': 'predeterminer', 'aux': 'auxiliary', 'exclam': 'exclamation',
    'abbr': 'abbreviation', 'exclamation': 'exclamation',
    'indefinite article': 'indefinite article', 'definite article': 'definite article',
    'number': 'number',
}

DEF_SEPARATOR = '|'
EX_SEP = '|'
COLL_SEPARATOR = '|'

class BuildNotesPaths(NamedTuple):
    oxford_jsonl_path: Path
    notes_txt_path: Path
    deck_audit_jsonl_path: Path
    gamma_verdicts_path: Path
    oxford_3000_md: Path
    oxford_5000_md: Path
    awl_md: Path
    manual_card_fills_path: Path
    audio_dir: Path
    review_overrides_path: Path | None = None
    synonym_example_overrides_path: Path | None = None
    antonym_example_overrides_path: Path | None = None

class BuiltCard(NamedTuple):
    """One Anki Note, encoded as 19-col Anki txt row.

    Column layout (1-indexed):
        1 guid, 2 notetype, 3 deck, 4 word, 5 pos, 6 ipa, 7 definition,
        8 example, 9 collocations, 10 wordfamily, 11 uk_audio, 12 us_audio,
        13 source1, 14 source2, 15 cefr, 16 idioms, 17 tags,
        18 synonyms, 19 antonyms.

    `synonyms` and `antonyms` are pipe-aligned with `example` chunks
    (one cell per chunk, empty when no relation). The back template reads
    these to color the corresponding parentheticals.
    """
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
    synonyms: str
    antonyms: str

    def to_tsv(self) -> str:
        return '\t'.join([
            self.guid, self.notetype, self.deck, self.word, self.pos, self.ipa,
            self.definition, self.example, self.collocations, self.wordfamily,
            self.uk_audio, self.us_audio, self.source1, self.source2, self.cefr,
            self.idioms, self.tags, self.synonyms, self.antonyms,
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
            'synonyms': self.synonyms,
            'antonyms': self.antonyms,
        }

class BuildNotesResult(NamedTuple):
    built_cards: list[BuiltCard]
    jsonl_text: str
    txt_text: str
    type_a_count: int
    type_b_count: int
    type_c_count: int
    dup_emit_skip_count: int
    unclassified_drop_count: int
    built_cards_count: int
    missing_in_jsonl_count: int


def get_word_candidates(word: str) -> list[str]:
    word_clean = re.sub(r"\s*\(.*?\)\s*", "", word.lower()).strip()
    cands = [word_clean]
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
            if len(base) > 1 and base[-1] == base[-2] and base[-1] in "bdfglmnprstz":
                cands.append(base[:-1] + repl)
            if suf in ("ed", "ing"):
                cands.append(base + "e")
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
    irregular = {
        "criteria": "criterion",
        "vertebrae": "vertebra",
        "ligaments": "ligament"
    }
    if word_clean in irregular:
        cands.append(irregular[word_clean])
    seen = set()
    deduped = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


def resolve_primary_record(
    matched_records: list[dict],
    contributing_records: list[dict],
) -> dict:
    if not matched_records:
        raise ValueError("matched_records cannot be empty")

    unique_contributors: list[dict] = []
    seen_ids: set[int] = set()
    for record in contributing_records:
        record_id = id(record)
        if record_id not in seen_ids:
            seen_ids.add(record_id)
            unique_contributors.append(record)

    if len(unique_contributors) == 1:
        return unique_contributors[0]
    return matched_records[0]


def find_idioms_for_word(word_clean: str, idioms_db: dict) -> list[tuple[dict, dict]]:
    if word_clean in idioms_db:
        return idioms_db[word_clean]
    for phrase_clean, records in idioms_db.items():
        if word_clean in phrase_clean or phrase_clean in word_clean:
            return records
    return []


def _parse_vocab_list(path: Path) -> set[tuple[str, str, str]]:
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


def _parse_existing_txt(path: Path) -> dict[tuple[str, str, str], dict]:
    """Parse the existing notes TXT, accepting both legacy 17-col and current 19-col rows.

    Column layout (1-indexed):
        1 guid, 2 notetype, 3 deck, 4 word, 5 pos, 6 ipa, 7 definition,
        8 example, 9 collocations, 10 wordfamily, 11 uk_audio, 12 us_audio,
        13 source1, 14 source2, 15 cefr, 16 idioms, 17 tags,
        18 synonyms, 19 antonyms.

    Legacy 17-col rows have no Synonyms/Antonyms columns; we normalize them
    to empty strings so downstream code can always read `synonyms_orig` and
    `antonyms_orig`.
    """
    by_key: dict[tuple[str, str, str], dict] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('#') or not line.strip():
            continue
        parts = line.split('\t')
        if len(parts) < 16:
            continue

        # 19-col layout: take the new fields directly.
        if len(parts) >= 19:
            (guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf,
             uk, us, src1, src2, cefr, idioms, tags, synonyms, antonyms) = parts[:19]
        # 17-col layout: Tags still at column 17; Synonyms/Antonyms empty.
        elif len(parts) >= 17:
            guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf, uk, us, src1, src2, cefr, idioms, tags = parts[:17]
            synonyms = ''
            antonyms = ''
        # 16-col legacy layout (no idioms column).
        else:
            guid, notetype, deck, word, pos, ipa, defn, ex, coll, wf, uk, us, src1, src2, cefr, tags = parts[:16]
            idioms = ''
            synonyms = ''
            antonyms = ''

        word_lower = word.strip().lower()
        word_base = word_lower.split(' (')[0].strip()
        by_key[(word_lower, pos, cefr)] = {
            'guid': guid,
            'notetype': notetype,
            'deck': deck,
            'word_orig': word,
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
            'synonyms_orig': synonyms,
            'antonyms_orig': antonyms,
            'all_19': parts,
        }
    return by_key


def _load_gamma_verdicts(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    d = json.loads(path.read_text(encoding='utf-8'))
    for v in d.get('verdicts', []):
        out[v['cluster_hash']] = v
    return out


def _simplify_with_gamma(record: dict, gamma: dict) -> list:
    base = simplify_record(record)
    if not base:
        return base
    for i, ms in enumerate(base):
        src_texts = []
        for pd_idx, def_idx in zip(ms.source_pdd_idx, ms.source_def_idx):
            d = _resolve_def(record, pd_idx, def_idx)
            t = d.get('text', '')
            src_texts.append('' if t is None else t)
        key = f"{record.get('word', '').lower()}|{ms.pos}|" + '|'.join(sorted(src_texts))
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        v = gamma.get(h)
        if v and v.get('decision') == 'merge' and v.get('merged_text'):
            base[i] = ms._replace(text=v['merged_text'])
    return base


def _format_examples(examples: list, max_n: int = 1) -> str:
    parts = []
    for ex in (examples or [])[:max_n]:
        t = (ex.get('text') or '').strip()
        if t:
            parts.append(t)
    return EX_SEP.join(parts)


def _format_collocations(colls: dict) -> str:
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
        inner = ' :: '.join(p for p in [phrase, text, ex_str] if p)
        if inner:
            parts.append(inner)
    return '$$'.join(parts)


def _format_wordfamily(verb_forms: dict) -> str:
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
    if not s:
        return ""
    return str(s).strip().strip("/").strip()


def _format_ipa_field(uk_ipa, us_ipa) -> str:
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
    a = audio or {}
    return a.get('uk') or '', a.get('us') or ''


def _audio_dir_filenames(audio_dir: Path) -> set[str]:
    if not audio_dir.exists():
        return set()
    return {p.name for p in audio_dir.glob('*.mp3')}


def _resolve_audio_filename(word: str, pos_or_accent: str, accent_or_available: str | set[str], available: set[str] = None) -> str:
    if available is None:
        # Called with 3 arguments: (word, accent, available)
        pos = ""
        accent = pos_or_accent
        avail = accent_or_available
    else:
        # Called with 4 arguments: (word, pos, accent, available)
        pos = pos_or_accent
        accent = accent_or_available
        avail = available

    word_clean = re.sub(r"\s*\(.*?\)\s*", "", word).strip().lower()
    candidates = []

    if pos:
        pos = resolve_audio_pos(word, pos)
        pos_slug = "_".join([p.strip().lower() for p in pos.replace(",", " ").replace("/", " ").split() if p.strip()])
        if word_clean == 'sake' and pos_slug == 'noun':
            candidates.append(f'cambridge_{accent}_sake_noun_2.mp3')
        candidates.append(f'cambridge_{accent}_{word_clean}_{pos_slug}.mp3')

    candidates.extend([
        f'cambridge_{accent}_{word}.mp3',
        f'cambridge_{accent}_{word.replace(" ", "_")}.mp3',
        f'cambridge_{accent}_{word.replace("-", "")}.mp3',
    ])

    for c in candidates:
        if c in avail:
            return f'[sound:{c}]'
    return ''


def _source_label(source_files: list[str] | None) -> str:
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
    tags: list[str] = []
    if audio_source and audio_source != source1:
        tags.append(f'Audio::{audio_source}')
    tags.append(f'Source::{source1}')
    tags.append(f'CEFR::{cefr}')
    tags.append('CEFR::oxford')
    if is_in_vocab_3000:
        tags.append('Oxford_3000')
    if is_in_vocab_5000:
        tags.append('Oxford_5000')
    if opal in ('W', 'S'):
        tags.append(f'OPAL_{opal}')
    if has_idioms:
        tags.append('idioms')
    return ' '.join(tags)


def _deck_for_source(source1: str, is_awl: bool) -> str:
    if is_awl or source1 == 'AWL':
        return 'English Academic Vocabulary::AWL 50 Academic Words'
    if source1 == 'Cambridge':
        return 'English Academic Vocabulary::TED YT'
    return 'English Academic Vocabulary::Oxford'


def _new_guid() -> str:
    import string
    alphabet = string.ascii_letters + string.digits + '!#$%&()*+,-./:;<=>?@[]^_`{|}~'
    return ''.join(secrets.choice(alphabet) for _ in range(10))


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


def lookup_gloss(
    audit_glosses: dict[tuple[str, str, str], str],
    word: str,
    pos_str: str,
    cefr: str,
    resolved_word: str,
    resolved_pos_parts: list[str],
    new_cefr: str,
) -> str | None:
    word_lower = (word or '').strip().lower()
    word_base = word_lower.split(' (')[0].strip()
    has_disambiguator = word_base != word_lower
    pos_lower = pos_str.strip().lower()

    full_key = (word_lower, pos_lower, cefr)
    if full_key in audit_glosses:
        return audit_glosses[full_key]

    if has_disambiguator:
        sibling_present = any(
            k[0].startswith(word_base + ' (') and (k[1], k[2]) == (pos_lower, cefr)
            for k in audit_glosses
        )
        if sibling_present:
            if cefr != new_cefr:
                sib_cefr_present = any(
                    k[0].startswith(word_base + ' (') and (k[1], k[2]) == (pos_lower, new_cefr)
                    for k in audit_glosses
                )
                if sib_cefr_present:
                    return None
            return None

    base_candidate_keys = [
        (word_base, ', '.join(resolved_pos_parts) if resolved_pos_parts else pos_lower, new_cefr),
        (word_base, pos_lower, new_cefr),
        (word_base, ', '.join(resolved_pos_parts) if resolved_pos_parts else pos_lower, cefr),
        (word_base, pos_lower, cefr),
    ]
    for gk in base_candidate_keys:
        if gk in audit_glosses:
            return audit_glosses[gk]

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
                break

    if matched_glosses:
        return ' | '.join(matched_glosses)
    return None


def _load_audit_overrides(
    path: Path,
) -> tuple[
    dict[tuple[str, str, str], str],
    dict[tuple[str, str, str], str],
    dict[tuple[str, str, str], str],
]:
    """Load build-stage overrides from the audit ledger.

    `gloss_after` remains the historical Definition override. The optional
    `example_after` and `collocations_after` fields are used by manual gloss
    review passes that curate examples/collocations alongside the definition.
    """
    audit_glosses: dict[tuple[str, str, str], str] = {}
    audit_examples: dict[tuple[str, str, str], str] = {}
    audit_collocations: dict[tuple[str, str, str], str] = {}

    if not path.exists():
        return audit_glosses, audit_examples, audit_collocations

    with path.open(encoding='utf-8') as audit_file:
        for line in audit_file:
            if not line.strip():
                continue
            row = json.loads(line)
            key = (
                row.get('word', '').strip().lower(),
                row.get('pos', '').strip().lower(),
                row.get('cefr', '').strip().upper(),
            )
            gloss = (row.get('gloss_after') or '').strip()
            example = (row.get('example_after') or '').strip()
            collocations = (row.get('collocations_after') or '').strip()
            if gloss:
                audit_glosses[key] = gloss
            if example:
                audit_examples[key] = example
            if collocations:
                audit_collocations[key] = collocations

    return audit_glosses, audit_examples, audit_collocations


def build_notes(paths: BuildNotesPaths) -> BuildNotesResult:
    audio_files = _audio_dir_filenames(paths.audio_dir)
    review_overrides_file = getattr(paths, 'review_overrides_path', None)
    review_overrides = load_review_overrides(review_overrides_file)

    vocab_3000 = _parse_vocab_list(paths.oxford_3000_md)
    vocab_5000 = _parse_vocab_list(paths.oxford_5000_md)
    vocab_awl = _parse_vocab_list(paths.awl_md)
    target_keys = vocab_3000 | vocab_5000 | vocab_awl

    existing = _parse_existing_txt(paths.notes_txt_path)
    gamma = _load_gamma_verdicts(paths.gamma_verdicts_path)

    audit_glosses, audit_examples, audit_collocations = _load_audit_overrides(
        paths.deck_audit_jsonl_path
    )

    filled_keys = set()
    if paths.manual_card_fills_path.exists():
        try:
            filled_data = json.load(paths.manual_card_fills_path.open(encoding='utf-8'))
            for r in filled_data:
                filled_keys.add((
                    (r.get('word') or '').strip().lower(),
                    (r.get('pos') or '').strip().lower(),
                    (r.get('cefr') or '').strip().upper()
                ))
        except Exception:
            pass

    by_word: dict[str, list[dict]] = {}
    idioms_db: dict[str, list[tuple[dict, dict]]] = {}
    with paths.oxford_jsonl_path.open(encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            w = (r.get('word') or '').lower()
            if w:
                by_word.setdefault(w, []).append(r)
            for idiom in r.get("idioms") or []:
                phrase = idiom.get("phrase") or ""
                phrase_clean = re.sub(r"\s*\(.*?\)\s*", "", phrase.lower()).strip()
                if phrase_clean:
                    idioms_db.setdefault(phrase_clean, []).append((r, idiom))

    by_word_simplified: dict[str, list[tuple[dict, list]]] = {}
    for word_lower, records in by_word.items():
        items: list[tuple[dict, list]] = []
        for record in records:
            try:
                simplified = _simplify_with_gamma(record, gamma)
                if simplified:
                    items.append((record, simplified))
            except Exception:
                pass
        if items:
            by_word_simplified[word_lower] = items

    senses_index: dict[tuple[str, str, str], list] = {}
    sense_source_record: dict[tuple[str, str, str], dict] = {}
    for word_lower, items in by_word_simplified.items():
        for record, senses in items:
            for ms in senses:
                cefr = ms.cefr or 'UNCLASSIFIED'
                key = (word_lower, ms.pos, cefr)
                senses_index.setdefault(key, []).append(ms)
                sense_source_record.setdefault(key, record)

    word_pos_set: dict[str, set[str]] = {}
    for word_lower, records in by_word.items():
        ps: set[str] = set()
        for record in records:
            for pd in record.get('pos_data', []) or []:
                p = pd.get('pos')
                if p:
                    ps.add(p)
        word_pos_set[word_lower] = ps

    all_cards: list[BuiltCard] = []
    seen_keys: set[tuple[str, str, str]] = set()
    emitted_keys: set[tuple[str, str, str]] = set()
    missing_in_jsonl_count = 0

    type_a_count = 0
    type_b_count = 0
    type_c_count = 0
    dup_emit_skip_count = 0
    unclassified_drop_count = 0

    guid_to_synonyms_spec: dict[str, list[dict]] = {}

    for key in sorted(existing.keys()):
        word_lower, pos_str, cefr = key
        if key in seen_keys:
            continue
        old = existing[key]
        if key in filled_keys:
            filled_pos_parts = [p.strip().lower() for p in old['pos'].split(',') if p.strip()]
            g = lookup_gloss(audit_glosses, word_lower, old['pos'], cefr, word_lower, filled_pos_parts, cefr)
            ex_override = lookup_gloss(audit_examples, word_lower, old['pos'], cefr, word_lower, filled_pos_parts, cefr)
            coll_override = lookup_gloss(audit_collocations, word_lower, old['pos'], cefr, word_lower, filled_pos_parts, cefr)
            defn_override = g if g is not None else old['definition_orig']
            uk_res = _resolve_audio_filename(word_lower, old['pos'], 'uk', audio_files)
            us_res = _resolve_audio_filename(word_lower, old['pos'], 'us', audio_files)
            uk_audio = uk_res if uk_res else old['uk_audio']
            us_audio = us_res if us_res else old['us_audio']
            card = BuiltCard(
                guid=old['guid'],
                notetype=old['notetype'],
                deck=old['deck'],
                word=old['word_orig'],
                pos=old['pos'],
                ipa=old['ipa'],
                definition=defn_override,
                example=ex_override if ex_override is not None else old['example_orig'],
                collocations=coll_override if coll_override is not None else old['collocations_orig'],
                wordfamily=old['wordfamily_orig'],
                uk_audio=uk_audio,
                us_audio=us_audio,
                source1=old['source1'],
                source2=old['source2'],
                cefr=old['cefr'],
                idioms=old['idioms_orig'],
                tags=old['tags'],
                synonyms=old.get('synonyms_orig', ''),
                antonyms=old.get('antonyms_orig', ''),
            )
            guid_to_synonyms_spec[old['guid']] = get_relation_specs_for_card(card, senses_index)
            all_cards.append(card)
            emitted_keys.add(key)
            seen_keys.add(key)
            continue

        pos_parts = [p.strip() for p in pos_str.split(',') if p.strip()]

        cands = get_word_candidates(word_lower)
        matched_records = []
        resolved_word = word_lower
        for cand in cands:
            if cand in by_word:
                matched_records = by_word[cand]
                resolved_word = cand
                break

        avail = word_pos_set.get(resolved_word, set())

        has_overlap = any(p in avail for p in pos_parts)
        resolved_pos_parts = []
        if has_overlap:
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

        if resolved_word != word_lower:
            type_b_count += 1
        elif resolved_pos_parts != pos_parts:
            type_a_count += 1

        all_senses_for_row: list = []
        primary_record: dict | None = None
        used_fallback_cefr: str | None = None
        contributing_records: list[dict] = []

        if matched_records:
            for p in resolved_pos_parts:
                sense_key = (resolved_word, p, cefr)
                if sense_key in senses_index:
                    all_senses_for_row.extend(senses_index[sense_key])
                    contributing_records.append(sense_source_record[sense_key])
                else:
                    for (w, pos, c), senses in senses_index.items():
                        if w == resolved_word and pos == p:
                            all_senses_for_row.extend(senses)
                            contributing_records.append(sense_source_record[(w, pos, c)])
                            used_fallback_cefr = c
                            break
            primary_record = resolve_primary_record(matched_records, contributing_records)

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
            type_c_count += 1
            missing_in_jsonl_count += 1
            continue

        capped = all_senses_for_row
        seen_texts: set[str] = set()
        deduped: list = []
        for s in capped:
            t = (s.text or '').strip()
            if t and t not in seen_texts:
                seen_texts.add(t)
                deduped.append(s)
        capped = deduped
        if not capped:
            type_c_count += 1
            missing_in_jsonl_count += 1
            continue

        if used_fallback_cefr is not None:
            new_cefr = cefr
        else:
            new_cefr = capped[0].cefr or 'UNCLASSIFIED'

        rec = primary_record or {}
        defn = DEF_SEPARATOR.join((s.text or '') for s in capped if (s.text or ''))

        g = lookup_gloss(audit_glosses, word_lower, pos_str, cefr, resolved_word, resolved_pos_parts, new_cefr)
        if g is not None:
            defn = g
        ex = EX_SEP.join(_format_examples(s.examples or []) for s in capped)
        ex_override = lookup_gloss(audit_examples, word_lower, pos_str, cefr, resolved_word, resolved_pos_parts, new_cefr)
        if ex_override is not None:
            ex = ex_override
        coll = ''
        coll_override = lookup_gloss(audit_collocations, word_lower, pos_str, cefr, resolved_word, resolved_pos_parts, new_cefr)
        if coll_override is not None:
            coll = coll_override
        wf = ''
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

        audio_word = resolved_word
        uk = _resolve_audio_filename(audio_word, pos_str, 'uk', audio_files)
        us = _resolve_audio_filename(audio_word, pos_str, 'us', audio_files)
        if not uk and old.get('uk_audio'):
            uk = old['uk_audio']
        if not us and old.get('us_audio'):
            us = old['us_audio']
        source1 = _source_label(rec.get('source_files') or [])
        is_awl = any(sf.startswith('awl_') for sf in (rec.get('source_files') or []))
        resolved_pos = resolved_pos_parts[0] if resolved_pos_parts else pos_parts[0]

        word_lower_base = re.sub(r"\s*\(.*?\)\s*", "", word_lower).strip()
        if word_lower_base == resolved_word:
            card_word = old['word_orig']
        else:
            card_word = resolved_word

        is_in_3000 = (resolved_word, resolved_pos, new_cefr) in vocab_3000
        is_in_5000 = (resolved_word, resolved_pos, new_cefr) in vocab_5000
        is_in_awl = (
            (resolved_word, resolved_pos, new_cefr) in vocab_awl
            or (
                resolved_word == 'converse'
                and new_cefr == 'UNCLASSIFIED'
                and old['deck'] == 'English Academic Vocabulary::AWL 50 Academic Words'
            )
        )
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

        guid = old['guid']
        deck = old['deck']

        emit_pos = ', '.join(resolved_pos_parts) if resolved_pos_parts else pos_str
        emit_key = (resolved_word, emit_pos, new_cefr)
        if emit_key in emitted_keys:
            dup_emit_skip_count += 1
            seen_keys.add(key)
            continue
        emitted_keys.add(emit_key)

        specs = []
        for s in capped:
            if getattr(s, "relation_specs", None):
                specs.extend(s.relation_specs)
        guid_to_synonyms_spec[guid] = specs

        all_cards.append(BuiltCard(
            guid=guid,
            notetype='English Academic Vocabulary Model',
            deck=deck,
            word=card_word,
            pos=emit_pos,
            ipa=ipa,
            definition=defn,
            example=ex,
            collocations=coll,
            wordfamily=wf,
            uk_audio=uk,
            us_audio=us,
            source1=source1,
            source2='AWL' if is_in_awl else 'Oxford',
            cefr=new_cefr,
            idioms=_format_idioms(rec.get('idioms') or []),
            tags=tags,
            synonyms='',  # populated by the relation annotator below
            antonyms='',  # populated by the relation annotator below
        ))
        seen_keys.add(key)

    # Apply review overrides by GUID
    all_cards = apply_review_overrides(all_cards, review_overrides)

    # Load and apply relation annotations (synonyms AND antonyms).
    synonym_overrides_file = getattr(paths, 'synonym_example_overrides_path', None)
    antonym_overrides_file = getattr(paths, 'antonym_example_overrides_path', None)
    synonym_overrides = load_relation_overrides(synonym_overrides_file)
    antonym_overrides = load_relation_overrides(antonym_overrides_file)
    annotated_cards = []
    all_annotation_errors = []

    for c in all_cards:
        specs = guid_to_synonyms_spec.get(c.guid)
        if specs is None:
            specs = get_relation_specs_for_card(c, senses_index)

        annotated_ex, syn_meta, ant_meta, errors = annotate_card_examples(
            c, specs, synonym_overrides, antonym_overrides,
        )
        if errors:
            all_annotation_errors.extend(errors)

        c_new = c._replace(
            example=annotated_ex,
            synonyms=syn_meta,
            antonyms=ant_meta,
        )
        annotated_cards.append(c_new)

    # Validate unknown GUIDs in either override file (unknown GUIDs fail on all builds)
    built_guids = {c.guid for c in all_cards}
    for label, ov_map in (
        ("synonym", synonym_overrides),
        ("antonym", antonym_overrides),
    ):
        unknown_guids = set(ov_map.keys()) - built_guids
        if unknown_guids:
            all_annotation_errors.append(
                f"Unknown card GUIDs defined in {label} overrides: {sorted(unknown_guids)}"
            )

    if all_annotation_errors:
        import sys
        print(
            f"Relation example annotation has {len(all_annotation_errors)} warnings/errors:\n" +
            "\n".join(all_annotation_errors),
            file=sys.stderr
        )
        # Match legacy semantics: only raise when an overrides file was
        # actually loaded. A bare build (no overrides) gets warnings but
        # does not fail — the override is the user's explicit opt-in to
        # strict validation.
        if synonym_overrides_file is not None or antonym_overrides_file is not None:
            raise ValueError(
                f"Relation example annotation failed with {len(all_annotation_errors)} errors:\n" +
                "\n".join(all_annotation_errors)
            )
    all_cards = annotated_cards

    # Apply corpus routing and tag updates
    from src.deck_builder.corpus_tag_sync import apply_corpus_routing_and_tags
    all_cards = apply_corpus_routing_and_tags(all_cards, vocab_3000, vocab_5000)

    # Serialize outputs to string
    jsonl_lines = []
    for c in all_cards:
        jsonl_lines.append(json.dumps(c.to_dict(), ensure_ascii=False))
    jsonl_text = '\n'.join(jsonl_lines) + '\n'

    header_lines = []
    # Read headers if existing notes_txt_path exists, then upgrade tags column
    # to 17 (unchanged) and append synonym/antonym column hints for Anki importer.
    if paths.notes_txt_path.exists():
        for line in paths.notes_txt_path.read_text(encoding='utf-8').splitlines()[:6]:
            if line.startswith('#tags column:'):
                header_lines.append('#tags column:17')
            elif line.startswith('#'):
                header_lines.append(line)
    else:
        # Fallback default headers
        header_lines = [
            "#separator:tab",
            "#html:true",
            "#guid column:1",
            "#notetype column:2",
            "#deck column:3",
            "#tags column:17",
        ]
    body = [c.to_tsv() for c in all_cards]
    txt_text = '\n'.join(header_lines + body) + '\n'

    return BuildNotesResult(
        built_cards=all_cards,
        jsonl_text=jsonl_text,
        txt_text=txt_text,
        type_a_count=type_a_count,
        type_b_count=type_b_count,
        type_c_count=type_c_count,
        dup_emit_skip_count=dup_emit_skip_count,
        unclassified_drop_count=unclassified_drop_count,
        built_cards_count=len(all_cards),
        missing_in_jsonl_count=missing_in_jsonl_count
    )
