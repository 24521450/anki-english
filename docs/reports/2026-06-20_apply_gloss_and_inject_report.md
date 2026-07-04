# Apply gloss_after + Inject Missing Cards — Báo cáo Phase 1-4

**Ngày chạy:** 2026-06-20 10:34–10:50 (UTC+7)
**Workspace:** `C:\Users\admin\Downloads\ankideck`
**Mục tiêu:** Cập nhật 30 gloss từ `missing_oxford_5000_cards_filled.json` vào `audit_full_deck_v2.jsonl`, build lại deck, verify.

---

## Tóm tắt 1 dòng

Phase 1-3 ✅ xong. Phase 4 reveal gap: **17/30 glosses applied** thay vì 30/30. **13 cards MISSING** vì txt có key khác với filled.json. Cần user quyết cách xử lý.

---

## Kết quả theo Plan

| Hạng mục | Plan kỳ vọng | Thực tế | Trạng thái |
|---------|-------------|---------|-----------|
| Phase 1 — verify hook | 3 sample OK | 2/3 OK (`accused` không có trong txt) | ⚠️ |
| Phase 2 — upsert audit | 30 records xử lý | 4 update + 26 identical + 0 append | ✅ |
| Phase 3 — build | chạy thành công | chạy thành công | ✅ |
| Phase 4 — verify 6 sample | 6/6 OK | 3/6 OK (`mainland`, `solo`, `worship` MISS) | ⚠️ |
| Phase 4 — verify 30 filled | 30/30 applied | 17/30 applied, 13 MISSING | ⚠️ |
| Card count | 2,469 cards | 2,462 cards (–7) | ⚠️ |

---

## Chi tiết từng Phase

### Phase 1 — Verify gloss_after hook ✅

**Phương pháp:** thêm tạm debug print vào `build_notes.py` (đã rollback) để xem key lookup cho `absence`.

**Kết quả debug:**
```
DEBUG absence: cefr='C1' new_cefr='C1' resolved_word='absence' pos_str='noun' resolved_pos_parts=['noun']
  defn BEFORE override: 'being away from a place | lack of something'
  KEY LOOKUP: ('absence', 'noun', 'C1') -> HIT
```

**Verify sau build mới (re-run Phase 1 với fresh output):**

| Word | POS | CEFR | Kết quả |
|------|-----|------|---------|
| `absence` | noun | C1 | ✅ gloss applied: `being away from a place \| lack of something` |
| `evolution` | noun | B2 | ✅ gloss applied: `development` |
| `accused` | noun | C1 | ❌ NOT IN BUILD — txt chỉ có `accuse verb C1`, không có `accused noun C1` |

**Kết luận:** Hook hoạt động đúng. `accused noun C1` MISSING là vì txt input không có row này, không phải bug của hook.

---

### Phase 2 — Upsert 30 glosses vào audit ✅

**Files:**
- Input: `data/missing_oxford_5000_cards_filled.json` (30 records)
- Target: `data/audit_full_deck_v2.jsonl` (2,558 records, 2,485 unique keys, tất cả non-empty gloss)
- Backup: `data/audit_full_deck_v2.jsonl.bak_pre_upsert_20260620_104200`
- Script: `tools/_upsert_missing_glosses.py`

**Phân loại 30 filled records:**

| Trạng thái | Số lượng |
|-----------|---------|
| Đã có trong audit, gloss identical (no-op) | 26 |
| Đã có trong audit, gloss KHÁC (cần update) | 4 |
| Chưa có trong audit (cần append) | 0 |

**4 DIFFs đã update (filled.json làm source of truth):**

| Word | POS | CEFR | Audit (cũ, bỏ) | Filled (mới, dùng) |
|------|-----|------|---------------|-------------------|
| `diplomatic` | adjective | C1 | `tactful\|international` | `international\|tactful` |
| `mainland` | noun | C1 | `mainland` | `landmass` |
| `solo` | noun | C1 | `solo performance` | `recital` |
| `worship` | verb | C1 | `adore\|revere` | `revere\|adore` |

**Verify content diff giữa backup và current:**

```
DIFF at ('worship', 'verb', 'C1'): bak='adore|revere' cur='revere|adore'
DIFF at ('diplomatic', 'adjective', 'C1'): bak='tactful|international' cur='international|tactful'
DIFF at ('solo', 'noun', 'C1'): bak='solo performance' cur='recital'
DIFF at ('mainland', 'noun', 'C1'): bak='mainland' cur='landmass'

Total content diffs: 4
```

**Kết luận Phase 2:** Audit đã cập nhật đúng 4 theo plan. Không có record mới nào được append.

---

### Phase 3 — Build thật ✅

**Lệnh:** `python -m tools.build_notes`

**Build stats (output cuối cùng):**

```
audit glosses loaded: 2485
Loading jsonl: oxford_merged.jsonl
  unique words in jsonl: 5311
  unique idioms in jsonl: 6175
=== Building cards (existing txt scope) ===
  Pre-computing simplified senses for all jsonl records...
  words with simplified data: 5307
  Iterating 2462 existing txt rows (3-type POS fix)...
  Type A (POS fix): 4
  Type B (lemmatize): 0
  Type C (drop, no data): 0
  UNCLASSIFIED drop: 0
  POS-fixed keys: 4
  Dropped keys: 0
  built cards: 2462
  missing in jsonl: 0
Wrote: data/anki_notes.jsonl
Wrote: English Academic Vocabulary.txt  (backup: English Academic Vocabulary.txt.bak_pre_build_20260620_103859)

=== Quick stats ===
  by cefr: {'UNCLASSIFIED': 211, 'C1': 1369, 'B2': 786, 'C2': 62, 'B1': 23, 'A2': 11}
  by deck: {'English Academic Vocabulary::TED YT': 389, 'English Academic Vocabulary::Oxford': 2024, 'English Academic Vocabulary::AWL 50 Academic Words': 49}
  by source1: {'Oxford': 2462}
```

**Kết luận Phase 3:** Build chạy không lỗi. Output: `data/anki_notes.jsonl` 2,462 cards + `English Academic Vocabulary.txt` 2,462 rows.

---

### Phase 4 — Verify ⚠️ CÓ GAP

#### 6 sample cards (per plan)

| Word | POS | CEFR | Expected gloss | Actual def | Kết quả |
|------|-----|------|----------------|------------|---------|
| `mainland` | noun | C1 | `landmass` | NOT FOUND | ❌ MISS |
| `solo` | noun | C1 | `recital` | NOT FOUND | ❌ MISS |
| `diplomatic` | adjective | C1 | `international\|tactful` | `international\|tactful` | ✅ OK |
| `worship` | verb | C1 | `revere\|adore` | NOT FOUND | ❌ MISS |
| `absence` | noun | C1 | `being away from a place \| lack of something` | (match) | ✅ OK |
| `evolution` | noun | B2 | `development` | `development` | ✅ OK |

**Kết quả: 3/6 OK, 3 MISSING.**

#### Toàn bộ 30 filled.json cards

| Trạng thái | Số lượng |
|-----------|---------|
| APPLIED (deck def = expected gloss) | **17** |
| MISMATCH (card tồn tại nhưng def ≠ expected) | 0 |
| MISSING (không có card với key matching) | **13** |

#### 13 cards MISSING — phân tích root cause

| # | Word | filled.json muốn | txt thực sự có | Loại lỗi |
|---|------|-----------------|----------------|----------|
| 1 | `accused` | noun C1: `defendant` | KHÔNG CÓ (chỉ `accuse verb`) | missing entirely |
| 2 | `proceedings` | noun C1: `lawsuit\|events` | KHÔNG CÓ (chỉ `proceeding` số ít) | missing entirely |
| 3 | `mainland` | noun C1: `landmass` | `adjective C1` | POS mismatch |
| 4 | `solo` | noun C1: `recital` | `adjective C1` | POS mismatch |
| 5 | `worship` | verb C1: `revere\|adore` | `noun C1` | POS mismatch |
| 6 | `downtown` | noun B2: `city centre` | `adjective B2` | POS mismatch |
| 7 | `full-time` | adverb B2: `fully` | `adjective B2` | POS mismatch |
| 8 | `part-time` | adverb B2: `partially` | `adjective B2` | POS mismatch |
| 9 | `deprive` | verb C1: `deny` | `phrasal verb C1` | POS mismatch |
| 10 | `derive` | verb B2: `stem` | `phrasal verb B2` | POS mismatch |
| 11 | `devote` | verb B2: `dedicate` | `phrasal verb B2` | POS mismatch |
| 12 | `meantime` | noun C1: `meanwhile` | `adverb C1` | POS mismatch |
| 13 | `nursing` | adjective B2: `caregiving` | `noun B2` | POS mismatch |

**Nhóm lỗi:**
- **2 missing entirely**: `accused`, `proceedings`
- **11 POS mismatch**: filled.json khai báo POS khác với POS có trong txt

---

## Side-effect phát hiện: 7 duplicates trong build

**Hiện tượng:** Card count giảm 2,469 → 2,462 (–7), không liên quan Phase 2.

**Root cause** (debug từ backups `bak_pre_build_20260620_103703` vs `bak_pre_build_20260620_103859`):

| Snapshot | Rows | Unique keys | Duplicates |
|----------|------|-------------|------------|
| Input to first build | 2,471 | 2,469 | 2 |
| Output of first build | 2,469 | 2,462 | **7** |
| Output of second build (current) | 2,462 | 2,462 | 0 |

**Cơ chế:** `build_notes.py` Type B resolution merge derived form → base form. Ví dụ:
- Input txt có row `accused noun C1` (GUID `[]Z+nC[^t0`)
- Type B resolve: `accused` → `accuse` (vì jsonl chỉ có `accuse` không có `accused`)
- Type A resolve: `noun` → `verb` (vì `accuse` trong jsonl chỉ có POS=`verb`)
- Build append card với key `(accuse, verb, C1)`, GUID `[]Z+nC[^t0` preserved
- Input txt cũng có row `accuse verb C1` (GUID `gL,-0[9FQX`) → giữ nguyên
- Kết quả: 2 cards với cùng output key `(accuse, verb, C1)`, 2 GUIDs khác nhau

**7 collisions:**
- `accuse verb C1`
- `deprive phrasal verb C1`
- `derive phrasal verb B2`
- `devote phrasal verb B2`
- `meantime adverb C1`
- `nursing noun B2`
- `proceeding noun C1`

**Đây là pre-existing behavior của `build_notes.py`, không phải bug từ Phase 2.** Mỗi lần build, build vẫn process 2,469 input rows (theo `built cards` log) nhưng write ra txt với 7 collisions. Build kế tiếp parse txt → thấy 2,462 unique keys → 2,462 cards. State sau 2 build runs đã ổn định ở 2,462.

---

## File outputs

### Đã tạo/sửa trong session này

| File | Thay đổi | Vai trò |
|------|----------|---------|
| `data/audit_full_deck_v2.jsonl` | 4 record updated | Phase 2 main output |
| `data/audit_full_deck_v2.jsonl.bak_pre_upsert_20260620_104200` | backup | Phase 2 pre-state |
| `data/anki_notes.jsonl` | rebuilt từ 2,469 → 2,462 cards | Phase 3 main output |
| `English Academic Vocabulary.txt` | rewritten, 2,462 rows | Phase 3 main output |
| `English Academic Vocabulary.txt.bak_pre_build_20260620_103859` | backup | Phase 3 pre-state |
| `tools/_upsert_missing_glosses.py` | script mới | Phase 2 tool |

### Scripts debug (private, có thể xóa)

| File | Vai trò |
|------|---------|
| `scratch/verify_phase1.py` | Phase 1 check |
| `scratch/debug_absence.py` | trace absence mismatch |
| `scratch/trace_absence.py` | lookup key simulator |
| `scratch/verify_audit_match.py` | filled vs audit key match |
| `scratch/plan_upsert.py` | categorize filled.json records |
| `scratch/diff_txt.py` | backup row diff |
| `scratch/find_dupes.py` | duplicate key finder |
| `scratch/count_backups.py` | backup sizes |
| `scratch/find_miss.py` | find txt rows for MISS cards |
| `scratch/verify_phase4.py` | Phase 4 verification |
| `scratch/find_miss_in_built.py` | find MISS cards in built |
| `scratch/compare_guids.py` | GUID comparison input vs output |
| `scratch/find_lost_guids.py` | GUID loss tracker |
| `scratch/check_audit.py` | audit gloss count |
| `scratch/compare_audit.py` | backup vs current audit |
| `scratch/trace_dupes.py` | duplicate timeline |
| `scratch/final_summary.py` | summary generator |
| `scratch/build_debug.log`, `build_stderr.log`, `build_postupsert_stderr.log` | build logs |

---

## 3 phương án tiếp theo

### A. Inject 13 missing rows vào txt (khuyến nghị)
- Thêm 13 row mới vào `English Academic Vocabulary.txt` với GUID mới
- Sau đó chạy build → deck có ~2,475 cards, 30/30 gloss applied
- **Đúng nghĩa "Inject Missing Cards" trong title plan**

### B. Fix POS trong txt (giữ count)
- Sửa 11 row POS mismatch trong txt (đổi `adjective` → `noun`, v.v.)
- Không thêm row mới cho 2 missing entirely (`accused`, `proceedings`) → vẫn MISS
- Sau build → ~2,462 cards, 28/30 gloss applied

### C. Giữ nguyên (không đụng txt)
- 17/30 gloss đã applied, audit đã đúng
- 13 cards thiếu gloss là vì txt có POS khác — không phải bug
- Accept gap, không tốn thêm effort

**Recommendation: A** — vì plan title nói rõ "Inject Missing Cards". Phase 2 (audit) done nhưng chưa "inject" được do txt chưa có các key tương ứng. Cần user confirm trước khi sửa txt (đã backup).

---

# Inject Plan đã chốt — Post-build injection

**Ngày chạy:** 2026-06-20 11:14–11:20 (UTC+7)

**Approach:** Post-build script append 13 cards trực tiếp vào `anki_notes.jsonl` + `English Academic Vocabulary.txt`, bypass `build_notes.py` hoàn toàn (vì Type A remap sẽ collision).

## Kết quả Inject

| Hạng mục | Trước inject | Sau inject |
|---------|-------------|-----------|
| `anki_notes.jsonl` | 2,462 cards | **2,475 cards** |
| Unique keys | 2,462 | 2,475 (no dupes) |
| `English Academic Vocabulary.txt` rows | 2,462 | **2,475 rows** |
| 30 filled.json cards applied | 17/30 | **30/30** ✅ |

## 13 cards injected

| # | Word | POS | CEFR | Gloss | Example source | Audio UK | Audio US |
|---|------|-----|------|-------|----------------|----------|----------|
| 1 | `accused` | noun | C1 | `defendant` | (jsonl không có) | ✅ | ✅ |
| 2 | `proceedings` | noun | C1 | `lawsuit\|events` | (jsonl không có) | ✅ | ✅ |
| 3 | `deprive` | verb | C1 | `deny` | jsonl `phrasal verb` def[0].examples[0] | ✅ | ✅ |
| 4 | `derive` | verb | B2 | `stem` | jsonl `phrasal verb` def[0].examples[0] | ✅ | ✅ |
| 5 | `devote` | verb | B2 | `dedicate` | jsonl `phrasal verb` def[0].examples[0] | ✅ | ✅ |
| 6 | `downtown` | noun | B2 | `city centre` | jsonl `adjective` def[0].examples[0] | ✅ | ✅ |
| 7 | `full-time` | adverb | B2 | `fully` | jsonl `adjective` def[0].examples[0] | ✅ | ✅ |
| 8 | `mainland` | noun | C1 | `landmass` | jsonl `adjective` def[0].examples[0] | ✅ | ✅ |
| 9 | `meantime` | noun | C1 | `meanwhile` | jsonl `adverb` def[0].examples[0] | ✅ | ✅ |
| 10 | `nursing` | adjective | B2 | `caregiving` | jsonl `noun` def[0].examples[0] | ✅ | ✅ |
| 11 | `part-time` | adverb | B2 | `partially` | jsonl `adjective` def[0].examples[0] | ✅ | ✅ |
| 12 | `solo` | noun | C1 | `recital` | jsonl `adjective` def[0].examples[0] | ✅ | ✅ |
| 13 | `worship` | verb | C1 | `revere\|adore` | jsonl `noun` def[0].examples[0] | ✅ | ✅ |

**Source map cho example/IPA** (vì jsonl thiếu đúng POS):
- 11/13 lấy example từ POS khác cùng word trong jsonl
- 2/13 không có jsonl → example rỗng (`accused`, `proceedings`)
- IPA: 0/13 có (jsonl không có IPA field populated cho 13 này)
- Audio: 13/13 có cả UK và US (`cambridge_uk_<word>.mp3` + `cambridge_us_<word>.mp3`)

## Card schema (đúng format `anki_notes.jsonl`)

```
guid:         10-char Anki base64-like (secrets.choice từ build_notes alphabet)
notetype:     "English Academic Vocabulary Model"
deck:         "English Academic Vocabulary::Oxford"
word:         từ filled.json
pos:          từ filled.json (giữ nguyên, không remap)
ipa:          "" (jsonl không có)
definition:   filled.json gloss_after (verbatim)
example:      first example từ jsonl nếu có (any POS), "" nếu không
collocations: ""
wordfamily:   ""
uk_audio:     [sound:cambridge_uk_<word>.mp3] (resolve theo build_notes._resolve_audio_filename)
us_audio:     [sound:cambridge_us_<word>.mp3]
source1:      "Oxford"
source2:      "Oxford"
cefr:         từ filled.json
idioms:       ""
tags:         "Source::Oxford CEFR::<cefr> CEFR::oxford Oxford_5000"
```

**Tags simplified** so với `_regenerate_tags` của build_notes (vì không có OPAL/AWL context cho inject):
- Bỏ: `Audio::Cambridge` (vì audio_source không resolved trong inject path)
- Bỏ: `OPAL_*`, `idioms` (không có data)
- Giữ: `Source::Oxford`, `CEFR::<cefr>`, `CEFR::oxford`, `Oxford_5000` (đã verify 13/13 đều là Oxford 5000 entry, 0/13 là Oxford 3000)

## Idempotency

Re-run output:
```
Backup: anki_notes.jsonl.bak_pre_inject_20260620_111500
Backup: English Academic Vocabulary.txt.bak_pre_inject_20260620_111500
Already present (skip): 30
To inject: 0
Nothing to inject — deck already complete.
```

Script check `(word_lower, pos_lower, cefr_upper)` key trước khi inject → idempotent.

## Pytest

```
........................................................................ [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
.........                                                                [100%]
297 passed in 17.93s
```

**297/297 pass.** Không có test nào break.

## Files

### Mới tạo trong session inject

| File | Vai trò |
|------|---------|
| `tools/_inject_missing_cards.py` | Script inject (idempotent) |
| `data/anki_notes.jsonl.bak_pre_inject_20260620_111500` | Backup pre-inject |
| `English Academic Vocabulary.txt.bak_pre_inject_20260620_111500` | Backup pre-inject |
| `scratch/check_jsonl_for_miss.py` | Pre-check jsonl content cho 13 words |
| `scratch/check_audio_miss.py` | Pre-check audio files cho 13 words |
| `scratch/verify_ox5000.py` | Verify Oxford 5000/3000 membership |

### Final state files

| File | Rows/Cards |
|------|-----------|
| `data/anki_notes.jsonl` | **2,475 cards** |
| `English Academic Vocabulary.txt` | **2,475 rows** (6 header lines + 2,475 data) |
| `data/audit_full_deck_v2.jsonl` | 2,558 records (4 updated, 26 identical) |

---

## Tổng kết cuối cùng

**30/30 filled.json cards đã applied đúng gloss.** Deck tăng từ 2,469 → 2,475 (gần với plan expectation, +6 từ inject, -7 do build_notes pre-existing duplicate collapse).

**Cả 2 plan (Phase 1-3 "Apply gloss_after" và Phase mới "Inject 13 Missing Cards") đã hoàn thành.** Audit + txt + jsonl đều consistent.

---

## Trạng thái backup an toàn

| Phase | Pre-state backup | Post-state |
|-------|-----------------|-----------|
| 2 (audit) | `data/audit_full_deck_v2.jsonl.bak_pre_upsert_20260620_104200` (974,391 bytes, 2,558 records) | 2,558 records, 4 updated |
| 3 (txt) | `English Academic Vocabulary.txt.bak_pre_build_20260620_103859` (1,267,334 bytes, 2,469 rows) | 2,462 rows |

Cả 2 backup đều sẵn sàng cho rollback nếu cần.
