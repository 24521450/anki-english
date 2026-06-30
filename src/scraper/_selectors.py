"""CSS selector constants for Oxford + Cambridge scrapers.

Status of each selector (verified 2026-06-10 on Oxford + Cambridge HTML cache):

Oxford (oxford_full.jsonl schema v2):
- headword         : VERIFIED — h1.headword (1 match/file, e.g. "stay" in stay_(verb).html)
- pos              : VERIFIED — pos-g[pos] (multiple per file: top-level + idioms + related entries)
- ipa              : VERIFIED — .phon (12 matches in stay_(verb).html, first = UK IPA)
- sense            : VERIFIED — li.sense (14 in stay_(verb).html)
- def              : VERIFIED — span.def (one per sense)
- cefr             : VERIFIED — [cefr] attribute on li.sense (3 in stay_(verb).html)
- sensenum         : VERIFIED — [sensenum] attribute on li.sense (3 in stay_(verb).html)
- examples         : VERIFIED — .examples .x (46 in stay_(verb).html)
- cf               : VERIFIED — span.cf (10 in stay_(verb).html, e.g. "stay to do something")
- register_tags    : UNVERIFIED — .reg returned 0 matches in stay_(verb).html; may be on
                     other files only. Set null + flag in comment.
- register_top     : UNVERIFIED — same as above
- grammar          : VERIFIED — span.grammar (e.g. "[intransitive]")
- topics           : VERIFIED — span.topic (concatenated name+cefr, e.g. "Holidaysa1")
- topic_g          : VERIFIED — span.topic-g (wrapper around topic)
- idioms_block     : VERIFIED — span.idm-g (e.g. "be here to stay | have come to stay")
- idiom_phrase     : VERIFIED — span.idm (idiom phrase inside idm-g)
- collocations     : VERIFIED — [unbox='snippet'] (2 in stay_(verb).html — Verb Forms + Collocations)
- collocations_title: VERIFIED — span.box_title (e.g. "Oxford Collocations Dictionary")
- verb_forms_table : VERIFIED — table.verb_forms_table (1 in stay_(verb).html, 0 in nouns)
- oxford3000       : VERIFIED — [ox3000] attribute (4 in stay_(verb).html)
- oxford5000       : VERIFIED — [ox5000] attribute (3 in texture_(noun).html)
- see_also         : VERIFIED — link "see also" in run-in text

Cambridge (sources/cambridge.jsonl schema v2):
- headword         : VERIFIED — .headword (2-3 matches, first is canonical)
- pos              : VERIFIED — span.pos.dpos (1-3 matches, scoped correctly)
- ipa              : VERIFIED — .dipa (error on IPA chars in PowerShell, selector works in lxml)
- sense            : VERIFIED — .dsense_b (2-5 per file)
- def              : VERIFIED — .ddef_d (2-6 per file)
- cefr             : VERIFIED — .epp-xref (e.g. "B2", "C2")
- examples         : VERIFIED — .dexamp (7-15 per file)
- grammar          : VERIFIED — .gram (e.g. "[ C ]", "[ not gradable ]")
- register_tags    : VERIFIED — .usage (e.g. "approving")
- xref (see_also)  : VERIFIED — .xref (e.g. "Compare opaque translucent")
- topics           : UNVERIFIED — no .topic in 4 random samples
- idioms           : UNVERIFIED — no .idiom-body in 4 random samples
- collocations     : UNVERIFIED — no [unbox='snippet'] in 4 random samples
- verb_forms       : N/A — Cambridge does not have a verb_forms section
- oxford3000/5000  : N/A — Cambridge uses different list names; not modeled yet
- awl              : N/A — Cambridge does not have AWL tagging
"""
from __future__ import annotations

# Oxford
OXFORD = {
    "headword":         "h1.headword",
    "pos":              'span.pos, pos-g[hclass="pos"] pos',  # top-level POS label (span OR pos-g form); picks innermost <pos>
    "ipa":              ".phon",        # first match = UK IPA
    "sense":            "li.sense",     # also [hclass='sense']
    "def":              "span.def",     # also [hclass='def']
    "cefr_attr":        "li.sense[cefr]",
    "sensenum_attr":    "li.sense[sensenum]",
    "examples":         ".examples .x",
    "cf":               'span[hclass="cf"]',     # <span hclass="cf" htag="span">stay to do something</span>
    "grammar":          'span.grammar',          # <span class="grammar">[intransitive]</span>
    "register_top":     ".reg",         # top-level register tag, near pos
    "register_def":     "li.sense .reg",
    "topic":            "span.topic",
    "topic_g":          "span.topic-g",
    "idm_block":        "span.idm-g",   # idiom block (e.g. "be here to stay")
    "idm_phrase":       "span.idm",     # idiom phrase (inside idm-g)
    "collocations":     "[unbox='snippet']",  # Oxford Collocations Dictionary
    "collocations_title": "span.box_title",
    "verb_forms_table": "table.verb_forms_table",
    "ox3000_attr":      "[ox3000]",
    "ox5000_attr":      "[ox5000]",
    "oxford_badge":     'span[class*="ox3ksym_"], span[class*="ox5ksym_"]',
    "see_also":         "a[href*='definition/english/'][class*='Ref']",
}

# Cambridge
CAMBRIDGE = {
    "headword":      ".headword",
    "pos":           "span.pos.dpos",
    "ipa":           ".dipa",
    "sense":         ".dsense_b",
    "def":           ".ddef_d",
    "cefr":          ".epp-xref",
    "examples":      ".dexamp",
    "grammar":       ".gram",
    "register":      ".usage",
    "xref":          ".xref",
    "audio_uk":      "audio source[src*='uk_pron']",
    "audio_us":      "audio source[src*='us_pron']",
    # Topics, idioms, collocations, verb_forms, oxford_lists, awl: N/A or unverified
    # See header docstring.
}
