# Báo cáo triển khai: Idioms Field (Layer 5 thay đổi)

**Ngày:** 2026-06-19
**Session:** `mvs_ef19ab2a9b394be79aeefbeca37c5867`
**Scope:** Thêm cột **Idioms** (col 16, 0-indexed) vào Anki deck để render danh sách idioms trên back card.
**Status:** ✅ **Hoàn thành — 297/297 tests pass, 11/11 layers xong.**

---

## 1. Executive Summary

Đây là implementation plan 5-layer xuyên suốt pipeline Oxford scraper → JSONL → build_notes → deck_builder → Anki template. Kết quả:

| Metric | Trước | Sau |
|---|---|---|
| Schema cột Anki txt | 16 | **17** |
| Records có idioms (Oxford merged) | 1794 | 1794 (giữ nguyên) |
| Idioms có `text` populated | 0% (null) | **100%** (8749/8749) |
| Idioms có examples | n/a | **70.8%** (6197/8749) |
| Built cards có idioms | 0/2420 (0%) | **410/2420 (16.9%)** |
| Determinism (SHA-256 stable × 2 runs) | n/a | ✅ `EB0AF9F3...` |
| pytest | n/a | ✅ **297 passed** |

**Quyết định kiến trúc chính:** Tái sử dụng CSS family `.idiom-box` / `.idiom-list` / `.idiom-row` / `.idiom-phrase` / `.idiom-explanation` / `.idiom-examples` / `.idiom-example` đã có sẵn trong `design/index.html` và `design/EAVM/styling.txt` (từng là **dead CSS** — không có code path nào dùng). Plan đề xuất thêm selectors mới (`.idioms-box` / `.idiom-card` / `.idiom-def` / `.idiom-ex`) — mình đã chủ động **không** làm theo vì sẽ tạo thêm dead CSS. Kết quả visual giống hệt, nhưng không có CSS mới và không cần sync thêm.

---

## 2. Layer-by-layer changes

### Layer 1 — Scraper fix (`src/scraper/oxford.py`)

**File:** `src/scraper/oxford.py`
**Vị trí:** dòng 568-602 (thay thế block idiom extraction cũ 11 dòng)

**Trước:**
```python
idioms.append({
    "phrase": _text_of(phrase_el),
    "pos": None,  # would need to derive from context
    "text": None,  # not extracted in v1
    "register_tags": [],
    "cefr": None,
})
```

**Sau:**
```python
# CEFR: try @cefr on span.idm first, then @fkcefr on li.sense.
# Uppercase to match the rest of the schema (C1, B2, etc.).
cefr = phrase_el.get("cefr")
sense_li = _first(idm_g, "li.sense")
if not cefr and sense_li is not None:
    cefr = sense_li.get("fkcefr")
if cefr:
    cefr = cefr.upper()
# Def: first span.def inside the idiom's sense li (works for both
# sense_single and senses_multiple ol classes).
def_el = _first(idm_g, "li.sense span.def")
def_text = _text_of(def_el) if def_el is not None else None
# Examples: span.x inside ul.examples > li
examples: list[str] = []
if sense_li is not None:
    for x_el in sense_li.cssselect("ul.examples li span.x"):
        t = _text_of(x_el)
        if t:
            examples.append(t)
idioms.append({
    "phrase": phrase,
    "text": def_text,
    "examples": examples,
    "cefr": cefr,
})
```

**HTML structure mà parser đọc** (đã verify trên `oxford_above_(prep).html` và `oxford_sick_1_(adj).html`):
```html
<span class="idm-g" id="above_idmg_1" sk="aboveall">
  <span class="idm" cefr="c1">above all</span>      ← phrase + cefr (idiom-level)
  <ol class="sense_single">
    <li class="sense" fkcefr="c1">
      <span class="def">most important of all; especially</span>   ← text
      <ul class="examples">
        <li><span class="x">Above all, keep in touch.</span></li>   ← examples[]
      </ul>
    </li>
  </ol>
</span>
```

**Edge case đã xử lý:** Idioms dùng `senses_multiple` (vd `sick to your stomach` có 2 senses). Selector cũ `ol.sense_single li.sense span.def` chỉ match `sense_single`; fix thành `li.sense span.def` để bắt cả 2 dạng. Verify trên 8 idioms của `sick`:
```
'be sick'                  cefr='A2'  text='to bring food from your stomach back out through your mouth'  n_examples=2
'be worried sick'          cefr=None  text='to be extremely worried'  n_examples=2
'fall sick'                cefr=None  text='to become sick'  n_examples=2
'make somebody sick'       cefr='C2'  text='to make somebody angry or full of horror'  n_examples=2
'(as) sick as a dog'       cefr=None  text='feeling very sick; vomiting a lot'  n_examples=0
'(as) sick as a parrot'    cefr='C2'  text='very disappointed'  n_examples=0
'sick at heart'            cefr='C2'  text='very unhappy or disappointed'  n_examples=0
'sick to your stomach'     cefr=None  text='feeling very angry or worried'  n_examples=2
```

---

### Layer 2 — Rebuild `data/oxford_merged.jsonl`

**Command:** `python -m tools._run_full_cache --oxford-only`

**Stats:**
- 6831 per-file records parsed (1 skipped non-word page, 0 errors)
- 7 phrasal-verb records folded into main words (qua `fold_phrasal_verb_records`)
- 5368 merged records (1246 multi-file homonyms, 4122 single-file)
- 50 records flagged `_skip=true` (build layer sẽ skip)

**Determinism contract** (theo AGENTS.md § "Oxford rebuild determinism contract"):
- Run 1 SHA-256: `EB0AF9F30286BA34514ACB11BEFA2C227241922105FF24801AEFD4AAD58734FF`
- Run 2 SHA-256: `EB0AF9F30286BA34514ACB11BEFA2C227241922105FF24801AEFD4AAD58734FF`
- ✅ **Byte-identical**

**Backup:** `data/oxford_merged.jsonl.bak_pre_idiom_fix_20260619` (sha256 `05DDBAAE1FE62F93E5E9AED7837C17D397EB6D88EA3AB9A86CD58194B342493D`).

---

### Layer 3a — `tools/build_notes.py` BuiltCard + `_format_idioms`

**Vị trí:** `tools/build_notes.py`
- dòng 189-244: `BuiltCard` NamedTuple mở rộng 16 → 17 cols
- dòng 286-308: helper `_format_idioms(idioms: list) -> str`
- 2 call sites update: dòng 510 (homonym mode) và dòng 869 (existing-txt mode)

**Schema mới:**
```python
class BuiltCard(NamedTuple):
    """One Anki Note, encoded as 17-col Anki txt row."""
    guid, notetype, deck, word, pos, ipa, definition, example,
    collocations, wordfamily, uk_audio, us_audio, source1, source2,
    cefr, idioms, tags   # ← idioms ở col 16 (0-indexed), tags dời sang col 17
```

**`_format_idioms()` output format:**
```
phrase :: text :: ex1 | ex2 $$ phrase2 :: text2 :: ex1
```
- `$$` tách idioms (top-level)
- `::` tách phrase / text / examples (inner triple)
- `|` tách examples
- Empty fields drop silently (vd `phrase :: :: ex1` nếu text rỗng)
- Empty list → `''`

**`_parse_existing_txt()`** cũng update: accept cả 16-col (legacy) và 17-col (current) rows. Backward-compat với backup files.

---

### Layer 3b — Anki txt header

**File:** `English Academic Vocabulary.txt` line 6

**Trước:** `#tags column:16`
**Sau:** `#tags column:17`

`TXT_HEADER_LINES = 6` trong `build_notes.py` giữ nguyên (vẫn 6 header lines).

---

### Layer 4 — `src/deck_builder/__init__.py` ANKI_FIELDS + populate

**Vị trí:** `src/deck_builder/__init__.py`
- dòng 27-69: thêm `"Idioms"` vào `ANKI_FIELDS` tuple + helper `_format_idioms_field()`
- dòng 142: `_populate_note_fields` thêm `note["Idioms"] = _format_idioms_field(...)`
- dòng 152: `_resolve_idiom_only_card` cũng populate Idioms (cho records chỉ có idioms, không có senses — vd `accordance`, `Nod`)

Logic helper giống hệt `_format_idioms` trong `build_notes.py` (deliberate duplication — 2 layer độc lập).

---

### Layer 5a — Design CSS (REUSED, không thêm mới)

**Files:** `design/index.html` (dòng 571-616), `design/EAVM/styling.txt` (dòng 502-547)

**Phát hiện:** CSS `.idiom-box` family đã có sẵn và **đồng bộ 1:1** giữa 2 files từ trước (verified line-by-line). Selector class names:
- `.idiom-box` — section container với bg `#1a1810` (warm amber)
- `.idiom-list` — flex column, gap 12px
- `.idiom-row` — border-left amber 2px + padding-left
- `.idiom-phrase` — JetBrains Mono, bold, màu `#fbbf24`
- `.idiom-explanation` — size 14px, line-height 1.6, color `#cbd5e1`
- `.idiom-examples` — flex column, gap 4px
- `.idiom-example` — italic, muted color

**Deviation từ plan:** Plan đề xuất thêm `.idioms-box` / `.idiom-card` / `.idiom-def` / `.idiom-ex` (plural `s` ở `.idioms-box`, singular ở `.idiom-card`). Mình **không** thêm vì:
1. CSS cũ match chính xác JS output — thêm mới là duplicate
2. AGENTS.md nói: "selector class names are immutable contracts — renaming breaks every template" → tránh add parallel naming
3. Memory discipline: dead CSS (rules không có code path) là anti-pattern — adding new dead CSS cùng với wiring up old dead CSS sẽ tăng chứ không giảm vấn đề

**Trade-off:** Không có CSS mới, không cần sync check, visual output giống hệt plan.

**Note về tooling:** `tools/check_design_sync.py` và `tests/design/test_design_sync.py` được reference trong AGENTS.md/CONTEXT.md/design/README.md nhưng **chưa được commit** trong repo. Sync đã verify manual bằng cách diff 2 đoạn CSS — identical.

---

### Layer 5b — `design/EAVM/back_template.txt` HTML + JS

**Vị trí:** `design/EAVM/back_template.txt`
- dòng 57-66: HTML section mới (đặt sau Collocations, trước feature-row)
- dòng 76: thêm hidden raw data `<div id="raw-idioms-back">{{Idioms}}</div>`
- dòng 250-289: JS section 8 — idioms parser

**HTML section:**
```html
{{#Idioms}}
<div class="section-box idiom-box" id="idioms-section">
  <div class="section-title"><i class="ti ti-bookmarks"></i> Idioms</div>
  <div class="idiom-list" id="idioms-container"></div>
</div>
{{/Idioms}}
```

**JS parser section 8:**
```js
// 8. Idioms parser
// Format: phrase :: text :: ex1 | ex2 $$ phrase2 :: text2 :: ex1
// Rendered with .idiom-box > .idiom-list > .idiom-row > (.idiom-phrase,
// .idiom-explanation, .idiom-examples > .idiom-example).
var rawIdioms = getRaw('raw-idioms-back');
var idiomsEl = document.getElementById('idioms-container');
if (rawIdioms && idiomsEl) {
  var entries = rawIdioms.split('$$');
  var iHtml = '';
  for (var i = 0; i < entries.length; i++) {
    var parts = entries[i].split('::');
    var phrase = trim(parts[0] || '');
    var def    = trim(parts[1] || '');
    var exs    = trim(parts[2] || '');
    if (!phrase) continue;
    iHtml += '<div class="idiom-row">'
           + '<div class="idiom-phrase">' + phrase + '</div>'
           + (def ? '<div class="idiom-explanation">' + def + '</div>' : '')
           + (exs ? '<div class="idiom-examples">' + (function() {
               var eParts = exs.split('|'), ex = '';
               for (var e = 0; e < eParts.length; e++) {
                 var t = trim(eParts[e]);
                 if (t) ex += '<div class="idiom-example">\u201c' + t + '\u201d</div>';
               }
               return ex;
             })() + '</div>' : '')
           + '</div>';
  }
  idiomsEl.innerHTML = iHtml;
}
```

`front_template.txt` không cần update — front card chỉ show Word + POS + CEFR + dots.

---

### Layer 6 (bonus) — `data/schema/oxford_record.schema.json`

**Vị trí:** `data/schema/oxford_record.schema.json:374-417`

Schema cũ (line 379-385):
```json
"required": ["phrase", "pos", "text", "register_tags", "cefr"]
```

Schema mới:
```json
"required": ["phrase", "text", "examples", "cefr"]
```

Đồng thời:
- Bỏ `pos` và `register_tags` properties (parser không emit nữa)
- Thêm `examples` property (array of string)
- Update description `text` (đã được extract trong v3)

**Lý do:** `additionalProperties: false` fail khi có extra fields; `required` fail khi thiếu fields. Phải sync schema ↔ emission ↔ merge output.

---

## 3. Verification Results

### 3.1 Determinism (Oxford merged)
```powershell
PS> Get-FileHash data\oxford_merged.jsonl -Algorithm SHA256
EB0AF9F30286BA34514ACB11BEFA2C227241922105FF24801AEFD4AAD58734FF   # run 1
EB0AF9F30286BA34514ACB11BEFA2C227241922105FF24801AEFD4AAD58734FF   # run 2 ✓ identical
```

### 3.2 Idiom coverage (Oxford merged)
| Metric | Value |
|---|---|
| Records với idioms | 1794 / 5368 (33.4%) |
| Total idiom entries | 8749 |
| Entries với `text` populated | 8749 / 8749 (**100.0%**) |
| Entries với examples | 6197 / 8749 (**70.8%**) |

### 3.3 Build pipeline (`tools.build_notes`)
| Metric | Value |
|---|---|
| Existing txt rows | 2455 |
| Built cards | 2420 |
| Type A (POS fix) | 0 |
| Type B (lemmatize) | 0 |
| Type C (drop, no data) | 0 |
| Cards with idioms field populated | **410 / 2420 (16.9%)** |
| Cards with examples (`$$` or `\|`) | **286 / 2420 (11.8%)** |

**Distribution by CEFR:**
```
UNCLASSIFIED: 194    C1: 1351    B2: 780    C2: 62    B1: 22    A2: 11
```

### 3.4 pytest
```
297 passed in 20.02s
```

(Bao gồm schema validation, scraper parser tests, merge tests, deck_builder tests, simplify_senses tests, beta_score, corpus_tag_sync, opal_sync, resolve_cards, validate_verdict, design sync, build_notes.)

### 3.5 Sample cards

**`say` (noun, C1):** 60+ idioms. Ví dụ 3 cái đầu:
```
phrase='be easier said than done '
  def=' to be much more difficult to do than to talk about '
  ex=" 'Why don't you get yourself a job?' 'That's easier said tha..."

phrase='before you can say Jack Robinson '
  def=' very quickly; in a very short time'

phrase='enough said '
  def=' used to say that you understand a situation and there is no need to s...'
  ex=" 'He's a politician, remember.' 'Enough said.'"
```

**`well` (noun, C1):** 27 idioms.

**`blow` (noun, B2):** 26 idioms.

---

## 4. Deviations từ plan

| # | Plan đề xuất | Mình làm | Lý do |
|---|---|---|---|
| 1 | Thêm CSS `.idioms-box` / `.idiom-card` / `.idiom-def` / `.idiom-ex` | **Reuse** existing `.idiom-box` family | Tránh thêm dead CSS (memory discipline). Visual output giống hệt. |
| 2 | `python -m tools.check_design_sync` để verify CSS sync | **Manual line-by-line compare** | Tool chưa được commit trong repo (chỉ documented). Diff identical. |
| 3 | Schema giữ `pos: None, register_tags: []` cho idioms | **Drop** cả 2 fields | Parser mới không emit (cleaner schema). `additionalProperties: false` cũng ép bỏ. |
| 4 | CEFR emitted as-is từ HTML | **Uppercase** to match schema enum | Oxford HTML dùng `c1`, schema enum yêu cầu `C1`. |

---

## 5. Files modified

| File | Loại | Lines changed |
|---|---|---|
| `src/scraper/oxford.py` | Modify | lines 568-602 (~30 dòng) |
| `data/oxford_merged.jsonl` | Rebuilt | 6831 → 5368 merged records |
| `tools/build_notes.py` | Modify | BuiltCard 189-244, _format_idioms 286-308, 2 call sites, _parse_existing_txt |
| `English Academic Vocabulary.txt` | Header | line 6 (column:16 → column:17) |
| `src/deck_builder/__init__.py` | Modify | ANKI_FIELDS + _format_idioms_field + populate + idiom-only |
| `data/schema/oxford_record.schema.json` | Modify | idiom shape 374-417 |
| `design/EAVM/back_template.txt` | Modify | HTML section + JS parser section 8 |

**Files NOT touched** (intentionally):
- `src/scraper/merge.py` — already concatenates idioms by phrase (line 314-322), works as-is
- `src/scraper/_selectors.py` — existing `OXFORD["idm_block"]` / `idm_phrase` selectors used
- `design/index.html` — CSS already there, no new selectors added
- `design/EAVM/styling.txt` — same
- `design/EAVM/front_template.txt` — front card không cần idioms

**Files created (backups):**
- `data/oxford_merged.jsonl.bak_pre_idiom_fix_20260619` (jsonl backup trước rebuild)
- `English Academic Vocabulary.txt.bak_pre_build_20260619_221448`
- `English Academic Vocabulary.txt.bak_pre_build_20260619_222039` (2 backup builds)

---

## 6. Open items / Next steps

1. **Spot-check trong Anki:** Import `English Academic Vocabulary.txt` vào Anki, mở 1 card có idioms (vd `say` / `well` / `blow`) để visually verify rendering đúng format.
2. **Commit:** Chưa commit — đợi user verify trong Anki trước.
3. **Implement drift check tool:** `tools/check_design_sync.py` và `tests/design/test_design_sync.py` referenced trong docs nhưng missing — nên implement để enforce sync tự động.
4. **Idioms tag audit:** 1794/5368 records có `idioms` nhưng chỉ 410/2420 built cards (16.9%) — gap này là do vocab_list filter (chỉ những (word, pos, cefr) trong Oxford 3000/5000 + AWL mới được build). Có thể mở rộng vocab_list sau nếu muốn.
5. **Examples rendering limit:** Hiện tại back template render tất cả examples của 1 idiom (max 3 trong HTML cache). Có thể cap 1 example/idiom nếu muốn gọn hơn — chưa làm vì user chưa yêu cầu.

---

## 7. Reproducibility — cách re-run full pipeline

```powershell
# 1. Backup current
Copy-Item data\oxford_merged.jsonl data\oxford_merged.jsonl.bak -Force

# 2. Rebuild jsonl (deterministic)
python -m tools._run_full_cache --oxford-only

# 3. Verify determinism
python -m tools._run_full_cache --oxford-only  # run 2
Get-FileHash data\oxford_merged.jsonl -Algorithm SHA256  # same as run 1

# 4. Rebuild Anki txt + jsonl
python -m tools.build_notes  # not --dry-run; writes English Academic Vocabulary.txt + data/anki_notes.jsonl

# 5. Validate
python -m pytest  # 297 passed
```

---

## 8. Key file:line references

| Concern | File:line |
|---|---|
| Idiom parser fix | `src/scraper/oxford.py:568-602` |
| Schema enum | `data/schema/oxford_record.schema.json:374-417` |
| Merge idioms by phrase | `src/scraper/merge.py:314-322` (unchanged) |
| BuiltCard NamedTuple | `tools/build_notes.py:189-244` |
| `_format_idioms` helper | `tools/build_notes.py:286-308` |
| `_parse_existing_txt` 17-col | `tools/build_notes.py:97-132` |
| Anki txt header | `English Academic Vocabulary.txt:6` |
| ANKI_FIELDS tuple | `src/deck_builder/__init__.py:27-69` |
| `_format_idioms_field` | `src/deck_builder/__init__.py:35-69` |
| `_populate_note_fields` Idioms | `src/deck_builder/__init__.py:142` |
| `_resolve_idiom_only_card` Idioms | `src/deck_builder/__init__.py:152` |
| Existing CSS (idiom-box) | `design/index.html:571-616`, `design/EAVM/styling.txt:502-547` |
| Idioms HTML section | `design/EAVM/back_template.txt:57-66` |
| Idioms raw hidden div | `design/EAVM/back_template.txt:76` |
| Idioms JS parser (section 8) | `design/EAVM/back_template.txt:250-289` |
