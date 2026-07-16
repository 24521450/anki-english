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
| [`../../tools/check_design_sync.py`](../../tools/check_design_sync.py) | CLI drift check — so sánh vùng 2 của `index.html` với `EAVM/styling.txt`. | Trước khi commit thay đổi CSS, hoặc khi CI fail. |
| [`../../tests/design/test_design_sync.py`](../../tests/design/test_design_sync.py) | Pytest version — chạy cùng parser, fail nếu drift. | Tự động trong `pytest` / CI. |

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

> **Mọi thay đổi design bắt đầu từ `index.html` (vùng 2).**
> `EAVM/styling.txt` và `EAVM/*.txt` derive từ đó.

1. Sửa `index.html` vùng 2 (giữa `ANKI CARD STYLES` và `END ANKI CARD STYLES`). **Không đổi tên class** — class names là immutable contract.
2. Nếu thêm rule mà không muốn sync vào Anki (preview-only), đặt `/* @preview-only */` ngay phía trước rule.
3. Sync `EAVM/styling.txt` theo cùng selector + property.
4. Chạy `python -m tools.check_design_sync` — nếu OK, proceed; nếu drift, fix.
5. Chạy `update_anki_deck.py` để bake `.apkg`.

> [!WARNING]
> **JS newline gotcha**: Anki's JS engine crash nếu có literal newline trong string. Xem [EAVM/README.md § Lưu ý quan trọng khi chỉnh sửa JavaScript](./EAVM/README.md#lưu-ý-quan-trọng-khi-chỉnh-sửa-javascript).

## Card design rules

Hai quy tắc cứng khi **tạo card** (build stage — biến raw notes thành Anki-ready rows). Quy tắc này **không áp dụng khi scrape**: scraper giữ raw đầy đủ để debug/research, filter ở build.

### Rule 1 — Sense Sorting (no limit)

1 card giữ **tất cả** senses khớp CEFR — không giới hạn số lượng def. Senses được sắp xếp theo thứ tự logic, không filter.

Tiêu chí sắp xếp (xếp theo thứ tự ưu tiên):
1. **Sensenum_local từ Oxford** (thấp hơn = phổ biến hơn) — Oxford đã sẵn xếp theo tần suất.
2. **Example count** (nhiều hơn = well-attested hơn) — sense có nhiều ví dụ thường là nghĩa cốt lõi.

Lý do bỏ cap: audit 2026-06-19 cho thấy nhiều từ tần suất cao (vd `harm`, `cement`, `crucial`, `agreement`, `spread`) bị mất nghĩa học thuật quan trọng khi cap = 3. Sense Sorting giữ toàn bộ, người học tự quyết định focus nghĩa nào qua gloss.

Reference implementation: [`src/deck_builder/__init__.py::_apply_sense_sorting`](../../src/deck_builder/__init__.py) — pure sort, no truncation. Helper `_filter_top3_defs.py` được giữ lại cho future study-profile variants (vd "focused" deck cap=3) nhưng KHÔNG dùng trong pipeline chính nữa.

Ví dụ:
- `sick` (A1) có 16 senses raw → giữ tất cả 16 senses, sorted by sensenum_local
- `abandon` (B2) có 5 senses → giữ tất cả 5 senses
- `aggregate` (C2) có 4 senses → giữ tất cả 4 senses
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
| [`../../tools/check_design_sync.py`](../../tools/check_design_sync.py) | CLI drift check — so sánh vùng 2 của `index.html` với `EAVM/styling.txt`. | Trước khi commit thay đổi CSS, hoặc khi CI fail. |
| [`../../tests/design/test_design_sync.py`](../../tests/design/test_design_sync.py) | Pytest version — chạy cùng parser, fail nếu drift. | Tự động trong `pytest` / CI. |

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

> **Mọi thay đổi design bắt đầu từ `index.html` (vùng 2).**
> `EAVM/styling.txt` và `EAVM/*.txt` derive từ đó.

1. Sửa `index.html` vùng 2 (giữa `ANKI CARD STYLES` và `END ANKI CARD STYLES`). **Không đổi tên class** — class names là immutable contract.
2. Nếu thêm rule mà không muốn sync vào Anki (preview-only), đặt `/* @preview-only */` ngay phía trước rule.
3. Sync `EAVM/styling.txt` theo cùng selector + property.
4. Chạy `python -m tools.check_design_sync` — nếu OK, proceed; nếu drift, fix.
5. Chạy `update_anki_deck.py` để bake `.apkg`.

> [!WARNING]
> **JS newline gotcha**: Anki's JS engine crash nếu có literal newline trong string. Xem [EAVM/README.md § Lưu ý quan trọng khi chỉnh sửa JavaScript](./EAVM/README.md#lưu-ý-quan-trọng-khi-chỉnh-sửa-javascript).

## Card design rules

Hai quy tắc cứng khi **tạo card** (build stage — biến raw notes thành Anki-ready rows). Quy tắc này **không áp dụng khi scrape**: scraper giữ raw đầy đủ để debug/research, filter ở build.

### Rule 1 — Sense Sorting (no limit)

1 card giữ **tất cả** senses khớp CEFR — không giới hạn số lượng def. Senses được sắp xếp theo thứ tự logic, không filter.

Tiêu chí sắp xếp (xếp theo thứ tự ưu tiên):
1. **Sensenum_local từ Oxford** (thấp hơn = phổ biến hơn) — Oxford đã sẵn xếp theo tần suất.
2. **Example count** (nhiều hơn = well-attested hơn) — sense có nhiều ví dụ thường là nghĩa cốt lõi.

Lý do bỏ cap: audit 2026-06-19 cho thấy nhiều từ tần suất cao (vd `harm`, `cement`, `crucial`, `agreement`, `spread`) bị mất nghĩa học thuật quan trọng khi cap = 3. Sense Sorting giữ toàn bộ, người học tự quyết định focus nghĩa nào qua gloss.

Reference implementation: [`src/deck_builder/__init__.py::_apply_sense_sorting`](../../src/deck_builder/__init__.py) — pure sort, no truncation. Helper `_filter_top3_defs.py` được giữ lại cho future study-profile variants (vd "focused" deck cap=3) nhưng KHÔNG dùng trong pipeline chính nữa.

Ví dụ:
- `sick` (A1) có 16 senses raw → giữ tất cả 16 senses, sorted by sensenum_local
- `abandon` (B2) có 5 senses → giữ tất cả 5 senses
- `aggregate` (C2) có 4 senses → giữ tất cả 4 senses
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
