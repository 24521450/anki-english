# Tài Liệu Cấu Hình Mẫu Thẻ (Card Type Configuration) - EAVM

> **Xem trước**: [`../index.html`](../index.html) cho trang tổng quan design system (khuyến nghị bắt đầu ở đây).  
> **Tài liệu design cấp cao**: [`../README.md`](../README.md).

Thư mục này lưu trữ các tệp cấu hình thiết kế giao diện (mặt trước, mặt sau và kiểu dáng CSS) của loại thẻ **English Academic Vocabulary Model (EAVM)** trong bộ thẻ IELTS Anki.

Các tệp ở đây đã được sửa lỗi và phản ánh chính xác 100% thiết kế chuẩn hiển thị dạng thẻ hiện đại có tích hợp chips (cho Part of Speech, CEFR Level, Collocations) và phân tách đa định nghĩa.

## Danh sách tệp tin

1. **`front_template.txt`**: Mã nguồn HTML + JavaScript của **Mặt trước** thẻ.
2. **`back_template.txt`**: Mã nguồn HTML + JavaScript của **Mặt sau** thẻ.
3. **`production_front_template.txt`**: Mặt trước của card sibling
   `Production (VI -> EN)`, gồm native `{{type:ProductionAnswer}}`.
4. **`production_answer_prefix.txt`**: Phần đầu mặt sau Production, hiển thị
   `{{FrontSide}}` trước toàn bộ back Recognition.
5. **`styling.txt`**: Mã nguồn CSS quy định giao diện, màu sắc, font chữ và các hiệu ứng hiển thị (Chips, Badge, Definition Box,...).
6. **`README.md`**: Tệp tài liệu hướng dẫn này.

---

## Cơ chế hoạt động của Kịch bản Tự động hóa

Kịch bản đóng gói bộ thẻ [`update_anki_deck.py`](../../update_anki_deck.py) đọc trực tiếp các tệp tin trong thư mục này mỗi khi chạy:
* `front_template.txt` -> Đưa vào làm `qfmt` (Question Format) cho Note Types.
* `back_template.txt` -> Đưa vào làm `afmt` (Answer Format) cho Note Types.
* `production_front_template.txt` + `production_answer_prefix.txt` -> tạo
  sibling card Production ở ordinal 1.
* `styling.txt` -> Đưa vào làm CSS Styling cho Note Types.

> [!TIP]
> **Mọi thay đổi card CSS bắt đầu từ `../index.html` (vùng 2).** Chỉ
> `styling.txt` derive từ vùng này. Các template `.txt` khác là source trực tiếp
> của packager và được chỉnh trong chính file tương ứng. Sau khi sửa CSS, sync
> `styling.txt` rồi chạy `python -m tools.check_design_sync` để verify.

Audio câu ví dụ dùng bốn field nối cuối note type: `ExampleAudioUK`,
`ExampleAudioUS`, `IdiomExampleAudioUK`, và `IdiomExampleAudioUS`. Mặt sau hiển
thị một switch ngang trong Audio Row. Switch chỉ có một thumb mang nhãn accent
hiện tại: mặc định `UK`, bấm/tap thì thumb trượt và đổi nhãn thành `US`; không
hiện đồng thời accent còn lại và không lưu lựa chọn giữa các card. Nhấn trực
tiếp vào câu Example hoặc Idiom Example để phát accent đang chọn. Khi audio
thực sự phát, toàn bộ câu chuyển sang màu CEFR của card; từ vựng mục tiêu vẫn
giữ chữ đậm và underline. Hover không đổi màu, còn end, pause, lỗi hoặc đổi
clip sẽ trả câu về màu bình thường. Audio không autoplay và mỗi lần chỉ có một
clip phát. Main Example căn theo `|` rồi `<br><br>`; Idiom Example căn theo
`$$` rồi `|`.

`DefinitionVI` được append sau bốn field audio. Field này pipe-aligned với
`Definition` và render thành một Vietnamese Gloss Line luôn hiển thị bên dưới
English definition. `Definition` vẫn giữ payload `EN (VI)` để tương thích với
các audit/tool cũ; template ưu tiên `DefinitionVI` và có fallback cho note cũ.

`IdiomMeaningVI` được append sau `SensePOS` và căn theo `$$` với `Idioms`.
Mỗi cell có dạng `vi_equivalent :: <VI>` hoặc `bilingual_gloss :: <VI>`.
`vi_equivalent` giữ cụm idiom EN nhưng chỉ hiện câu Việt tương đương;
`bilingual_gloss` hiện nghĩa EN trước rồi Vietnamese Gloss Line. Nếu metadata
thiếu, sai mode, rỗng hoặc không căn đúng số idiom, template giữ giao diện EN
cũ để không làm mất nghĩa. Example và Example Audio của idiom không đổi.

---

## Đồng bộ vào Anki

Không sao chép hoặc chỉnh template thủ công trong Anki. Chỉnh các source trong
thư mục này, chạy packager, rồi dùng stage `import` của pipeline. Importer cập
nhật EAVM Note Type qua AnkiConnect và xác minh fields, template ordinals, GUID
coverage và media sau import. Quy trình chuẩn nằm trong [`AGENTS.md`](../../AGENTS.md#anki-package-import-workflow).

---

## Lưu ý quan trọng khi chỉnh sửa JavaScript

> [!WARNING]
> **Lỗi Xuống Dòng (Literal Newline Gotcha)**:
> Trình chạy JavaScript của Anki rất nhạy cảm với lỗi cú pháp. Khi viết mã JavaScript trong các tệp văn bản này, **tuyệt đối không được gõ phím Enter để xuống dòng bên trong một chuỗi ký tự được bao bọc bởi dấu nháy kép `""` hoặc nháy đơn `''`**. 
> * **Sai**: 
>   ```javascript
>   if (wf.indexOf("
>   ") !== -1)
>   ```
> * **Đúng**:
>   ```javascript
>   if (wf.indexOf("\n") !== -1)
>   ```
> Nếu gõ sai, toàn bộ JavaScript trên thẻ sẽ bị crash (không hoạt động), dẫn đến việc collocations hay định nghĩa chỉ hiện chữ thường thô kèm ký tự ngăn cách `|`.
## Production sibling card (VI -> EN)

`production_front_template.txt` is the ordinal-1 front and contains the
single native `{{type:ProductionAnswer}}` replacement. Its aligned Vietnamese
glosses and clozed examples come from the pipe-aligned `DefinitionVI` and
`Example` fields. Every gloss remains visible;
one safely masked example is shown per row and any additional safe examples
are collapsed behind a compact `+N` disclosure. The answer uses `{{FrontSide}}`
followed by the unchanged Recognition back. The appended `ProductionAnswer`
field is derived from the final displayed `Word`, and a card is generated only
when all three production fields are populated.

Design assumes the learner already knows the deck's purpose and direction.
Do not add visible direction banners, instructions, input labels, or fallback
explanations to card faces. Visible labels are reserved for learning metadata
or state (for example CEFR, POS, and `+N`); accessibility-only names remain.

Live migration uses the pipeline's dedicated `import` stage. Any real pipeline
run containing `deck` invokes it automatically; `python -m src.pipeline import`
remains available for a standalone re-import. The importer backs up the deck,
appends fields, renames ordinal 0 in place, and adds ordinal 1 without
removing/recreating the established template.
