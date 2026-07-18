# IELTS Anki Deck — Design

Thư mục này chứa toàn bộ **design system** cho bộ thẻ IELTS Anki:
file preview trực quan, tokens (màu, font, spacing), layout rules, và
template thật được bake vào `.apkg`.

## File map

| File | Vai trò | Khi nào mở |
| --- | --- | --- |
| **[`index.html`](./index.html)** | **Source of truth** — trang tổng quan 5 vùng (xem bên dưới). Class names là immutable contract. Vùng 2 (CSS giữa 2 boundary comments) là card CSS được sync vào `EAVM/styling.txt`. | **Bắt đầu ở đây** khi muốn xem hoặc sửa design. |
| [`EAVM/`](./EAVM/) | **Implementation** — `styling.txt`, `front_template.txt`, `back_template.txt`, `README.md`. Đây là những file được pack vào `.apkg`. | Khi muốn sửa template HTML/JS hoặc sửa CSS thẳng (không qua design review). |
| [`reference/oxford_labels.html`](./reference/oxford_labels.html) | Taxonomy mẫu Oxford (cũ) — đã được inline vào vùng 5 của `index.html`. File này còn lại làm quick-lookup snippet. | Khi cần một snippet nhỏ share được. |
| [`../tools/check_design_sync.py`](../tools/check_design_sync.py) | CLI drift check — so sánh vùng 2 của `index.html` với `EAVM/styling.txt`. | Trước khi commit thay đổi CSS, hoặc khi CI fail. |
| [`../tests/design/test_design_sync.py`](../tests/design/test_design_sync.py) | Pytest version — chạy cùng parser, fail nếu drift. | Tự động trong `pytest` / CI. |

## Cấu trúc `index.html` (5 vùng)

`index.html` chia thành 5 vùng rõ ràng, từ abstract → concrete:

| Vùng | Nội dung | Sync vào `.apkg`? |
| --- | --- | --- |
| **Vùng 1** — Tokens | Color swatches (bg/text/accent/CEFR/POS), typography (Hanken/JetBrains/Charis SIL), spacing & border-radius scale | ❌ preview only |
| **Vùng 2** — Card CSS | Toàn bộ rule trong `EAVM/styling.txt` nguyên xi, giữa boundary comments | ✅ **PHẢI khớp 1:1** (drift check enforce) |
| **Vùng 3** — Components | Mini-previews cho từng thành phần (POS chip, CEFR badge, audio btn, sense row, register tag, feature tag, collocation chip, wf chip, corpus badge, divider, idiom box) | ❌ preview only |
| **Vùng 4** — Sample Cards | 8 thẻ mẫu thật từ `data/notes.json` + `data/oxford_samples.json` (abolish, absent, absence, aggregate, paradigm, sick, abandon, acid) — render đầy đủ front+back | ❌ preview only |
| **Vùng 5** — Reference Data | Oxford labels taxonomy inline (12 register, 5 usage restrictions, 5 corpus symbols, 23 subject labels) | ❌ preview only |

Boundary markers vùng 2:
- Mở: `/* ANKI CARD STYLES — must match EAVM/styling.txt exactly */` (trong `<style>` block)
- Đóng: `/* END ANKI CARD STYLES */` (trong `<style>` block)

Mọi CSS giữa 2 markers này sẽ được parser extract ra và so sánh với `EAVM/styling.txt`. Nếu lệch → drift check fail. Nếu rule nào muốn preview-only (vd `.anki-card-container` width=800px chỉ cho preview tile), thêm `/* @preview-only */` ngay trước rule đó.

## Quick start

1. Mở [`index.html`](./index.html) trong browser → xem toàn bộ design system.
2. Muốn sửa design → sửa `index.html` (vùng 2) trước, sync `EAVM/styling.txt` cho khớp.
3. Chạy `python -m tools.check_design_sync` (hoặc `pytest tests/design/`) để confirm không drift.
4. Chạy `update_anki_deck.py` (root) để bake `.apkg`.

## Design tokens (quick reference)

Giá trị dưới đây là **sau khi sync** (mirror vùng 2 của `index.html` + `EAVM/styling.txt`).
Để refresh, đọc thẳng từ `EAVM/styling.txt` — drift check sẽ flag nếu lệch.

### Color palette

| Token | Hex | Dùng cho |
| --- | --- | --- |
| `bg-card` | `#141313` | Nền card |
| `bg-section` | `#181717` | Nền section box |
| `bg-elevated` | `#1e1d1d` | Nền collocation chip |
| `collocation-source-bg` | `#022c22` | Nền collocation có dictionary evidence |
| `collocation-source-text` | `#d1fae5` | Chữ và marker collocation có dictionary evidence |
| `collocation-source-border` | `#065f46` | Viền collocation có dictionary evidence |
| `bg-word-family` | `#131226` | Nền word-family box |
| `border-default` | `#2a2929` | Viền card |
| `border-subtle` | `#252424` | Viền section |
| `border-word-family` | `#2d2460` | Viền word-family box |
| `text-primary` | `#f1f5f9` | Word (front + back) |
| `text-def` | `#e2e8f0` | Definition, sense-def |
| `text-secondary` | `#c4c7c7` | POS chip, top-badge (CEFR) |
| `text-meta` | `#94a3b8` | IPA pill, audio btn |
| `text-muted` | `#64748b` | Sense-ex, usage-tag |
| `text-section-title` | `#4b5563` | Section title |
| `accent-purple` | `#a78bfa` | Số thứ tự POS (`pos-chip-num`) |
| `accent-amber` | `#fb923c` | Register tag — attitude (`rt-amber`) |
| `accent-warm` | `#fbbf24` | Register tag — slang/specialist (`rt-warm`) |
| `accent-red` | `#fca5a5` | Register tag — offensive/taboo (`rt-red`) |
| `accent-subject` | `#c4b5fd` | Subject label (`rt-subject`), word-family-word |
| `cefr-A1` | `#5eead4` | CEFR A1 |
| `cefr-A2` | `#67e8f9` | CEFR A2 |
| `cefr-B1` | `#93c5fd` | CEFR B1 |
| `cefr-B2` | `#c4b5fd` | CEFR B2 |
| `cefr-C1` | `#fcd34d` | CEFR C1 |
| `cefr-C2` | `#fda4af` | CEFR C2 |
| `cefr-UNCLASSIFIED` | `#c4c7c7` | Không phân loại |
| `wf-pos-n` (teal) | `#5eead4` | Word-family chip — noun |
| `wf-pos-v` (blue) | `#93c5fd` | Word-family chip — verb |
| `wf-pos-adj` (purple) | `#a78bfa` | Word-family chip — adjective |
| `wf-pos-adv` (amber) | `#fbbf24` | Word-family chip — adverb |
| `wf-pos-phr` (orange) | `#fb923c` | Word-family chip — phrase |
| `wf-pos-prep` (green) | `#86efac` | Word-family chip — preposition |

### Typography

- **Sans** (body, word, definition, register-tag): `Hanken Grotesk`, fallback `-apple-system, sans-serif`
- **Mono** (chip, label, badge, corpus, wf, audio btn, section title): `JetBrains Mono`, fallback `monospace`
- **IPA** (`.ipa-text` only): `Charis SIL`, `Doulos SIL`, `Segoe UI`, `Lucida Sans Unicode`, `Arial Unicode MS`, `sans-serif` — dùng cascade font hệ thống + font SIL chuyên IPA. Không embed base64; phụ thuộc font user đã cài (Charis/Doulos SIL nếu có, fallback Segoe UI/Lucida/Arial Unicode MS nếu không). Cross-platform an toàn, IPA glyphs (ɪ/ʃ/ˈ) render đúng ở hầu hết môi trường.
- **Icons**: `Tabler Icons` (CDN)

### Spacing

- Card content padding: `28px 20px` (back) / `40px` (front)
- Section gap (back content): `20px`
- Border radius: `20px` (card), `14px` (section box), `9999px` (chip/badge), `6px` (corpus badge), `3px` (`pos-chip-num`)
- Card width: `440px` fixed (preview) / `100%` (Anki, max 540px) — marked `/* @preview-only */` cho width

## Quy tắc chỉnh sửa

> **Mọi thay đổi card CSS bắt đầu từ `index.html` (vùng 2).**
> Chỉ `EAVM/styling.txt` derive từ vùng này. Các template `EAVM/*.txt` khác
> là source trực tiếp của packager và được chỉnh trong chính file tương ứng.

1. Sửa `index.html` vùng 2 (giữa `ANKI CARD STYLES` và `END ANKI CARD STYLES`). **Không đổi tên class** — class names là immutable contract.
2. Nếu thêm rule mà không muốn sync vào Anki (preview-only), đặt `/* @preview-only */` ngay phía trước rule.
3. Sync `EAVM/styling.txt` theo cùng selector + property.
4. Chạy `python -m tools.check_design_sync` — nếu OK, proceed; nếu drift, fix.
5. Chạy `update_anki_deck.py` để bake `.apkg`.

> [!WARNING]
> **JS newline gotcha**: Anki's JS engine crash nếu có literal newline trong string. Xem [EAVM/README.md § Lưu ý quan trọng khi chỉnh sửa JavaScript](./EAVM/README.md#lưu-ý-quan-trọng-khi-chỉnh-sửa-javascript).

## Card design rules

### Principle — implicit deck context

Assume the learner already knows the deck's direction and interaction model.
Card faces must not repeat that context with visible direction banners,
instructions, input labels, or empty-state explanations. Keep visible labels
only when they distinguish learning content or state, such as CEFR, POS, and
the compact `+N` disclosure count. Non-visible accessibility names remain
required for controls and semantic regions.

### Idiom Vietnamese meaning

The appended `IdiomMeaningVI` field is `$$`-aligned with `Idioms`; each cell is
either `vi_equivalent :: <VI>` or `bilingual_gloss :: <VI>`. Both modes keep
the English idiom phrase. A valid `vi_equivalent` cell hides the English
explanation and shows only the equivalent Vietnamese saying; a valid
`bilingual_gloss` cell shows the simplified English explanation followed by
the same purple Vietnamese Gloss Line used in Sense Rows. Missing, empty,
unknown, or globally misaligned metadata falls back to the legacy English
explanation. Idiom examples and their UK/US Example Audio alignment are
unchanged.

### Collocation source provenance

`CollocationSources` được pipe-align với `Collocations`. Bốn token hợp lệ là
`oxford`, `cambridge`, `oxford+cambridge`, và `curated`. Ba token dictionary
render chip xanh có marker chữ `OXF`, `CAM`, hoặc `OXF+CAM`; `curated` giữ chip
xám mặc định. Marker chữ và `aria-label` truyền đạt provenance độc lập với màu.

Source-backed collocations giữ từng phrase chính xác thành chip riêng. Nếu
metadata thiếu, lệch số ô, có ô rỗng, hoặc chứa token lạ, template không suy
đoán provenance: toàn bộ collocations trên card render theo kiểu curated/default.
Production Card dùng chung Recognition back nên nhận cùng cách render này.

### Production sibling card (VI -> EN)

The EAVM note type emits two sibling cards from the same note. Ordinal 0 is
`Recognition`; ordinal 1 is `Production (VI -> EN)`. The production front is
loaded from `EAVM/production_front_template.txt` and uses Anki's native
`{{type:ProductionAnswer}}` control. Its prompt pairs each pipe-aligned
`DefinitionVI` gloss with the corresponding `Example`, masking the reviewed
English answer while retaining every sense. Each row shows one
safe masked example; further safe examples stay in a native collapsed
`<details>` region whose only visible summary is `+N`. The answer template is
`{{FrontSide}}` followed by the unchanged Recognition back.

`ProductionAnswer` is an appended model field. It is derived at build time
from the final displayed `Word` by removing only a trailing display
qualifier; learning-pattern slots such as `devote sth to sth` remain intact.
A production card is generated only when `DefinitionVI`, `Example`, and
`ProductionAnswer` are all populated. Notes that do not meet that predicate
still receive the Recognition card.

When changing the production layout, keep the sibling template name/order,
the single native type-answer replacement, and the exact CSS sync contract.
Live collections are migrated through `python -m src.pipeline import`, which
backs up the deck and appends fields/templates in place.

Ba quy tắc cứng áp dụng trong semantic review/build. Scraper vẫn giữ raw đầy đủ để debug/research.

### Rule 0 — Learner Relevance Filter (reviewed only)

Bilingual Semantic Audit có thể loại một sense quá hẹp hoặc quá chuyên ngành
khi card vẫn còn nghĩa cốt lõi hữu ích. Nhãn domain/`specialized` chỉ dùng để
đưa vào hàng đợi review, không tự động xóa. Mỗi source bị ảnh hưởng phải được
remap hoặc exclude có lý do; không được làm card rỗng.

### Rule 1 — Sense Sorting (no limit)

1 card giữ **tất cả** senses khớp CEFR còn lại sau Learner Relevance Filter — không giới hạn số lượng def. Sense Sorting chỉ sắp xếp, không tự filter hay truncate.

Tiêu chí sắp xếp (xếp theo thứ tự ưu tiên):
1. **Sensenum_local từ Oxford** (thấp hơn = phổ biến hơn) — Oxford đã sẵn xếp theo tần suất.
2. **Example count** (nhiều hơn = well-attested hơn) — sense có nhiều ví dụ thường là nghĩa cốt lõi.

Lý do bỏ cap: audit 2026-06-19 cho thấy nhiều từ tần suất cao (vd `harm`, `cement`, `crucial`, `agreement`, `spread`) bị mất nghĩa học thuật quan trọng khi cap = 3. Sense Sorting giữ toàn bộ, người học tự quyết định focus nghĩa nào qua gloss.

Reference implementation: [`src/deck_builder/__init__.py::_apply_sense_sorting`](../src/deck_builder/__init__.py) — pure sort, no truncation. Không có helper cap hoặc truncate nào thuộc production path.

Ví dụ: nếu không có quyết định learner-relevance, `sick`, `abandon`, hoặc
`aggregate` vẫn giữ toàn bộ senses khớp CEFR và chỉ sort theo
`sensenum_local`.
- `tackle` (C1) có 4 senses → giữ tất cả 4 senses (legacy cap sẽ drop 1)

### Rule 2 — Card Identity (Word, CEFR, LIST = 1 card by default)

Cùng `(Word, CEFRLevel, LIST)` = cùng card. Khác bất kỳ thành phần nào trong 3 = khác card. **LIST** là bucket corpus/list primary, lấy từ tags theo priority cố định:

```text
Oxford_5000 > Oxford_3000 > AWL_Coxhead > NO_LIST
```

Card chỉ mang **1** list tag duy nhất — list cao nhất mà nó sở hữu. Card không có `Oxford_5000` / `Oxford_3000` / `AWL_Coxhead` → `NO_LIST` (vẫn là identity bucket hợp lệ).

Hệ quả:
- Multi-POS word (vd `absent` = adjective/verb/preposition, `yield` = noun/verb) → mặc định 1 card duy nhất cho mỗi `(CEFR, LIST)`, POS chips list tất cả POS trong top-bar (xem [Vùng 4 sample card](#cấu-trúc-indexhtml-5-vùng) — card ② `absent` minh hoạ).
- Identity variants đã review:
  - `converse|UNCLASSIFIED|AWL_Coxhead` tách `verb` và `adjective, noun` vì hai Oxford homonym có stress, nghĩa và audio khác nhau.
  - `trail|C1|Oxford_5000` tách `noun`/`verb` vì từng POS có hệ sense, example và collocation độc lập sau review thủ công; `torture|C1|Oxford_5000` đã được review lại và merge thành một card `noun, verb` theo quy tắc mặc định.
  - Đây là allowlist ngoại lệ, không phải rule tách mọi multi-POS word.
  - `(firm, B2, Oxford_5000)` — adjective ("solid|unlikely to change")
  - `(firm, B2, Oxford_3000)` — noun ("a business or company")
  Hai cards hợp lệ, **không merge**, vì chúng đến từ 2 curriculum khác nhau.
- 1 raw note có CEFR trống → 1 card với `cefr-badge-UNCLASSIFIED` (xem Vùng 4 card ⑤ `paradigm`).
- **Lý do đổi rule (2026-06-21)**: rule cũ `(Word, CEFRLevel)` ép merge các cards cùng CEFR kể cả khi chúng ở 2 list khác nhau → mất thông tin curriculum. Rule mới giữ đúng ranh giới list.

**Hard contract**: P3B verifier fail nếu phát hiện duplicate `(Word, CEFRLevel, LIST)` không nằm trong allowlist identity variant đã review. Verifier cũ vẫn báo duplicate `(Word, CEFRLevel)` nhưng chỉ mang tính tham khảo.

### Tại sao không filter ở scrape?

Scrape stage giữ raw data đầy đủ vì:
- **Debug**: nếu card hiển thị sai, cần xem lại senses gốc để verify Oxford source.
- **Re-build**: nếu sau này đổi sense-selection heuristic (vd từ sensenum_local sang frequency corpus thật), chỉ cần re-run build, không scrape lại.
- **Multi-profile**: tương lai có thể có profile "intensive" (giữ 5 senses) vs "focused" (giữ 3) — scrape giữ raw, build chọn profile.

## Drift check

- **CLI**: `python -m tools.check_design_sync` — exit 0 nếu sync, exit 1 nếu drift (in ra diff).
- **Pytest**: `pytest tests/design/test_design_sync.py` — chạy cùng parser, fail nếu drift.
- **CI**: thêm `pytest tests/design/` vào workflow. Drift = red build.

> **Preview-only selectors** (`.anki-card-container`, `.card-content-front`): đánh dấu `/* @preview-only */` trong `index.html` vì chúng có property cố ý khác production (width, min-height). Drift check sẽ skip cả rule.

## Liên kết

- Source code Python: [`update_anki_deck.py`](../update_anki_deck.py) (ở root, owned by `developer` rein)
- Vocab lists: [`../vocab_list/`](../vocab_list/) (owned by `scraper` rein)
- Data: [`../data/`](../data/) (owned by `deck-builder` rein)
- Top-level team conventions: [`../AGENTS.md`](../AGENTS.md)
