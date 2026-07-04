"""Pure support helpers for Anki note building."""
from __future__ import annotations

import json
import hashlib
import re
import secrets
from collections import Counter
from pathlib import Path

from src.deck_builder.build_contracts import (
    BuiltCard,
    COLL_SEPARATOR,
    DEF_SEPARATOR,
    EX_SEP,
    POS_NORM,
)
from src.deck_builder.simplify_senses import simplify_record, TEXT_JOIN_SEPARATOR, _resolve_def
from src.scraper.cambridge_audio import resolve_audio_pos
from src.deck_builder.synonym_annotator import get_relation_specs_for_card

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
    by_lower = {name.lower(): name for name in avail}
    allow_case_insensitive_audio = word == word.lower()

    def _first_available(names: list[str]) -> str:
        for name in names:
            if name in avail:
                return f'[sound:{name}]'
            if allow_case_insensitive_audio:
                actual = by_lower.get(name.lower())
                if actual is not None:
                    return f'[sound:{actual}]'
        return ''

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

    found = _first_available(candidates)
    if found:
        return found

    if allow_case_insensitive_audio:
        raw_word_variants = (
            word_clean,
            word_clean.replace(" ", "_"),
            word_clean.replace("-", ""),
            word.replace(" ", "_").lower(),
        )
    else:
        raw_word_variants = (
            word,
            word.replace(" ", "_"),
            word.replace("-", ""),
        )

    word_variants = []
    for candidate in raw_word_variants:
        if candidate and candidate not in word_variants:
            word_variants.append(candidate)
    if allow_case_insensitive_audio and word_clean.endswith("e") and len(word_clean) > 2:
        ing_stem = word_clean[:-1]
        if ing_stem and ing_stem not in word_variants:
            word_variants.append(ing_stem)

    prefix_rank = {"cambridge": 0, "oxford": 1}
    exact_candidates = [
        f"{prefix}_{accent}_{variant}.mp3"
        for variant in word_variants
        for prefix in ("cambridge", "oxford")
    ]
    found = _first_available(exact_candidates)
    if found:
        return found

    if not allow_case_insensitive_audio:
        return ''

    fuzzy_matches: list[tuple[int, int, str]] = []
    for name in avail:
        name_lower = name.lower()
        for variant in word_variants:
            for prefix, rank in prefix_rank.items():
                stem = f"{prefix}_{accent}_{variant}"
                if name_lower.startswith(stem) and name_lower.endswith(".mp3"):
                    fuzzy_matches.append((rank, len(name), name))
    if fuzzy_matches:
        fuzzy_matches.sort()
        return f"[sound:{fuzzy_matches[0][2]}]"
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

def _get_senses_for_card(card: BuiltCard, senses_index: dict) -> list:
    word_clean = card.word.split(" (")[0].strip().lower()
    cands = get_word_candidates(word_clean)
    pos_parts = [p.strip().lower() for p in card.pos.split(",") if p.strip()]
    card_cefr = card.cefr.strip().upper() if card.cefr else "UNCLASSIFIED"

    senses = []
    for cand in cands:
        for p in pos_parts:
            key = (cand, p, card_cefr)
            if key in senses_index:
                senses.extend(senses_index[key])
        if senses:
            break

    if not senses:
        for cand in cands:
            for (w, p, _), s_list in senses_index.items():
                if w == cand and p in pos_parts:
                    senses.extend(s_list)
            if senses:
                break
    return senses

def _build_source_label_specs_index(
    by_word: dict[str, list[dict]],
) -> dict[tuple[str, str], list[dict]]:
    """Index raw Oxford definition provenance independently of CEFR filtering."""
    index: dict[tuple[str, str], list[dict]] = {}
    for word, records in by_word.items():
        for record in records:
            for pos_data in record.get("pos_data") or []:
                pos = (pos_data.get("pos") or "").strip().lower()
                if not pos:
                    continue
                for definition in pos_data.get("definitions") or []:
                    source_definition = (definition.get("text") or "").strip()
                    if not source_definition:
                        continue
                    index.setdefault((word, pos), []).append({
                        "source_definition": source_definition,
                        "register_tags": list(definition.get("register_tags") or []),
                        "domain": definition.get("domain"),
                        "examples": [
                            (example.get("text") or "").strip()
                            for example in (definition.get("examples") or [])
                            if (example.get("text") or "").strip()
                        ],
                        "synonyms": list(definition.get("synonyms") or []),
                        "antonyms": list(definition.get("antonyms") or []),
                    })
    return index

def _get_source_label_specs_for_card(
    card: BuiltCard,
    source_label_specs_index: dict[tuple[str, str], list[dict]],
) -> list[dict]:
    word_clean = card.word.split(" (")[0].strip().lower()
    positions = [part.strip().lower() for part in card.pos.split(",") if part.strip()]
    for candidate in get_word_candidates(word_clean):
        specs: list[dict] = []
        for pos in positions:
            specs.extend(source_label_specs_index.get((candidate, pos), []))
        if specs:
            return specs
    return []

parse_vocab_list = _parse_vocab_list
resolve_audio_filename = _resolve_audio_filename
