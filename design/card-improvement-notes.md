# Ghi chú cải thiện Anki card

Ngày ghi chú: 2026-07-09

Phạm vi: các ý tưởng cải thiện EAVM card, chưa phải contract hiện hành. Khi triển khai, bắt đầu từ `design/index.html` vùng 2, đồng bộ `design/EAVM/styling.txt`, rồi chạy `python -m tools.check_design_sync` và slice test phù hợp.

Nguồn kiểm tra nhanh:

- `design/index.html`
- `design/EAVM/front_template.txt`
- `design/EAVM/back_template.txt`
- `design/EAVM/styling.txt`
- `data/build/anki_notes.jsonl`
- `.understand-anything/knowledge-graph.json`

Số liệu hiện tại từ `data/build/anki_notes.jsonl`:

- 2457 cards.
- Definition chunks: 1745 cards có 1 sense, 582 có 2, 116 có 3, 13 có 4.
- Idioms: 112 cards có idiom data; card dài nhất khoảng 1104 ký tự idiom.
- WordFamily: 0 cards có `wordfamily` non-empty.
- Audio: 2 cards thiếu cả UK và US audio.
- Multi-POS: 130 cards.

## 1. Làm rõ `@preview-only` trước khi tin production CSS

Quan sát: `tools/check_design_sync.py` bỏ qua rule có `/* @preview-only */` khi so sánh drift, nhưng `update_anki_deck.py` đọc nguyên `design/EAVM/styling.txt` và bake thẳng vào `.apkg`. Trong `styling.txt`, `.anki-card-container` vẫn có `width: 800px`, và `.card-content-front` vẫn có `min-height: 220px` kèm comment preview-only.

Câu hỏi grill: `@preview-only` chỉ là nhãn cho drift check, hay thật sự không được vào `.apkg`?

Khuyến nghị: chốt contract này trước mọi đổi layout. Nếu preview-only thật sự không được vào production, packager hoặc bước sync phải strip rule đó. Nếu vẫn được bake, đổi tên comment để không gây hiểu nhầm.

Kiểm chứng khi sửa:

- Unit test cho packager hoặc helper strip preview-only.
- Inspect CSS trong generated `.apkg`/model để đảm bảo production width đúng.
- `python -m tools.check_design_sync`

## 2. Responsive/narrow layout cho L3 Sense Row

Quan sát: `.sense-row` là grid cố định `55fr 45fr`, không có `@media` trong `styling.txt`. Trên viewport hẹp hoặc Anki mobile, definition + example dễ bị bóp ngang, nhất là cards có register tag, Vietnamese gloss button, hoặc ví dụ dài.

Câu hỏi grill: ở mobile, example có cần nằm cùng hàng với definition không?

Khuyến nghị: cho màn hình hẹp stack example dưới definition. Giữ desktop 2 cột vì scan nhanh, nhưng thêm mobile rule như `.sense-row { grid-template-columns: 1fr; }`, bỏ `border-left` của `.sense-ex`, giảm padding ngang.

Kiểm chứng khi sửa:

- Preview trên width hẹp với các cards `critical`, `gut`, `alert`, `notwithstanding`.
- Test selector contract để chắc không đổi class.
- Nếu có browser test, chụp desktop + mobile preview.

## 3. Progressive disclosure cho Idiom Box dài

Quan sát: idiom box render full-expanded. Hiện có 112 cards có idioms; các cards như `say`, `terms`, `well` có idiom field rất dài. Với spaced repetition, phần này có thể đẩy nội dung chính xuống quá xa.

Câu hỏi grill: idiom là nội dung học chính của card, hay là enrichment sau khi đã nhớ nghĩa cơ bản?

Khuyến nghị: mặc định hiển thị 1-2 idioms đầu, thêm nút reveal phần còn lại. Riêng idiom-only cards vẫn có thể mở rộng toàn bộ vì idiom là headword chính.

Kiểm chứng khi sửa:

- Fixture cho card nhiều idioms và idiom-only card.
- Visual check với `say`, `terms`, `well`.
- Regression cho parser format `phrase :: text :: ex1 | ex2 $$ ...`.

## 4. Front-card sense indicator nên bounded và có nghĩa rõ hơn

Quan sát: front template tạo một dot cho mỗi Definition chunk. Hiện max production là 4 chunks, nhưng Sense Sorting contract không đặt hard cap vĩnh viễn. Dot không nói rõ đó là số sense, số definition chunk, hay độ khó.

Câu hỏi grill: learner cần biết "card này nhiều nghĩa" ở mức định lượng chính xác hay chỉ cần cảnh báo cognitive load?

Khuyến nghị: đổi dots thành indicator bounded, ví dụ `4 senses` hoặc tối đa 5 dots + `4`. Nếu vẫn dùng dots, đặt cap để không overflow khi sau này card có nhiều senses hơn.

Kiểm chứng khi sửa:

- Fixture 1, 2, 4, 8 sense chunks.
- Đảm bảo front card không dịch layout khi số sense tăng.

## 5. Word Family là component đẹp nhưng chưa có dữ liệu production

Quan sát: design system có `Word Family Box`, sample cards có word-family chips, nhưng build hiện tại có 0/2457 cards có `wordfamily` non-empty. Trong code cũ cũng có comment user decision 2026-06-20 là để trống field này.

Câu hỏi grill: WordFamily là mục tiêu sắp làm hay component legacy nên hạ xuống preview/reference?

Khuyến nghị: một trong hai hướng:

- Nếu muốn học word family: định nghĩa nguồn dữ liệu, rule chọn word forms, và validator cho `WordFamily`.
- Nếu chưa làm: ghi rõ trong design README rằng component này là dormant/preview-only để tránh người đọc tưởng deck đang render nó.

Kiểm chứng khi sửa:

- Nếu bật dữ liệu: thêm tests cho parser/render word-family.
- Nếu hạ cấp component: cập nhật sample/README để phản ánh production thật.

## 6. Missing audio state đã chốt: ẩn audio thiếu

Trạng thái: đã chọn contract ẩn audio thiếu. Template production chỉ render audio button khi `AudioUK`/`AudioUS` tồn tại; preview và CSS không nên có disabled audio placeholder.

Lý do: số card thiếu audio rất ít, và ẩn nút thiếu audio giữ mặt sau gọn hơn trong lúc học.

Contract: thiếu UK thì không render nút UK; thiếu US thì không render nút US; thiếu cả hai thì không render `audio-row` trong preview/sample.

Kiểm chứng cần giữ:

- Fixture card thiếu UK, thiếu US, thiếu cả hai.
- Visual check không làm top/back header rối.

## 7. Vietnamese gloss reveal cần thao tác nhanh hơn cho multi-sense cards

Quan sát: `vi-reveal` reveal từng gloss một và disable button sau khi mở. Cách này tốt cho active recall, nhưng cards có 3-4 senses sẽ cần nhiều click nếu learner muốn kiểm tra nhanh toàn bộ nghĩa Việt.

Câu hỏi grill: sau khi lật back card, ưu tiên là self-test từng sense hay kiểm tra nhanh toàn bộ card?

Khuyến nghị: giữ per-sense reveal, nhưng cân nhắc thêm một control nhỏ ở senses box để reveal all Vietnamese glosses. Không auto-show gloss mặc định.

Kiểm chứng khi sửa:

- Regression cho `tests/design/test_vietnamese_gloss.py`.
- Kiểm tra literal newline gotcha trong Anki JS.

## 8. Màu relation synonym/antonym đang dựa chủ yếu vào màu

Quan sát: `.relation-synonym` xanh và `.relation-antonym` hồng giúp nhìn nhanh, nhưng không có shape/text distinction ngoài màu. Với màn hình kém hoặc color-vision difference, learner có thể không phân biệt được.

Câu hỏi grill: relation parenthetical có cần đọc được khi không phân biệt màu không?

Khuyến nghị: thêm dấu hiệu không chỉ bằng màu, ví dụ synonym dùng underline dotted, antonym dùng underline wavy hoặc prefix nhẹ trong title/aria nếu Anki hỗ trợ an toàn. Tránh thêm text quá nặng vào example.

Kiểm chứng khi sửa:

- `tests/design/test_render_relations.py`
- Visual sample với synonym-only, antonym-only, cả hai.

## 9. External font/icon dependencies nên có fallback rõ

Quan sát: card CSS import Google Fonts và Tabler Icons qua CDN. Font body có fallback hệ thống, nhưng icon `<i class="ti ...">` có thể biến mất khi offline hoặc khi Anki không load external CSS ổn định.

Câu hỏi grill: deck có cần render đẹp hoàn toàn offline không?

Khuyến nghị: nếu offline là requirement, giảm phụ thuộc CDN cho icon bằng text fallback hoặc baked assets. Nếu CDN được chấp nhận, ghi rõ đây là best-effort enhancement và kiểm tra card khi offline.

Kiểm chứng khi sửa:

- Render preview khi network blocked.
- Kiểm tra audio button và section-title vẫn hiểu được khi icon font không load.

## 10. Cần bộ visual regression mẫu cho các card "nặng"

Quan sát: design/index.html có sample cards, nhưng production data hiện có các stress cases khác: long idioms, multi-POS, missing audio, long examples, 4-sense cards, UNCLASSIFIED cards.

Câu hỏi grill: sample cards đang đại diện cho design system hay đại diện cho production risk?

Khuyến nghị: thêm một nhóm stress samples vào preview hoặc một script tạo fixture preview từ `data/build/anki_notes.jsonl`. Nên cover ít nhất:

- `critical` hoặc `gut`: long examples + 4 senses.
- `terms` hoặc `say`: long idioms.
- `notwithstanding`: long POS list.
- `blink of an eye` hoặc `have the floor`: no audio.
- một `UNCLASSIFIED` card.

Kiểm chứng khi sửa:

- `pytest tests/design/`
- Manual/browser screenshots desktop + narrow viewport.

## Thứ tự nên làm

1. Chốt và sửa contract `@preview-only`/production CSS.
2. Thêm responsive rule cho `.sense-row`.
3. Thêm stress samples hoặc visual check script.
4. Quyết định WordFamily: bật dữ liệu thật hoặc đánh dấu dormant.
5. Làm progressive disclosure cho idioms và optional reveal-all gloss.
6. Dọn audio missing contract và offline icon fallback.
