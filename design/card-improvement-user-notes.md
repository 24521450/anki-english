# Ghi chú ý tưởng cải thiện card Anki từ user

Ngày tạo: 2026-07-09

Mục đích: ghi lại trực tiếp các ý tưởng bạn nêu về cải thiện card Anki. File này tách riêng khỏi `design/card-improvement-notes.md`, là nơi chứa audit/khuyến nghị ban đầu từ repo.

Quy ước ghi chú:

- `Ý tưởng`: nội dung bạn nói, giữ sát wording gốc nhất có thể.
- `Mục tiêu`: vấn đề học tập hoặc UX mà ý tưởng muốn giải quyết.
- `Cần làm rõ`: câu hỏi nếu ý tưởng chưa đủ rõ để triển khai.
- `Gợi ý triển khai`: hướng kỹ thuật sơ bộ, chỉ thêm khi đã đủ ngữ cảnh.
- `Trạng thái`: `raw`, `needs-clarification`, `ready-for-design`, hoặc `implemented`.

## Ghi chú

### 2026-07-09 - `proposition`: tách primary senses và secondary senses

Ý tưởng:

- Card `proposition` hiện có 4 senses.
- 2 senses đầu liên quan nhiều hơn tới word chính theo hướng tham khảo Cambridge:
  - `suggested idea/plan`
  - `thing to deal with`
- 2 senses cuối ít liên quan hơn với trọng tâm học chính:
  - `vote law proposal`
  - `[formal] opinion statement`
- Không muốn xóa 2 senses cuối, nhưng muốn cân nhắc tách card thành 2 để card chính nhẹ hơn.

Mục tiêu:

- Giữ card chính tập trung vào nghĩa learner nhiều khả năng cần gặp trong IELTS/academic use.
- Không làm mất dữ liệu Oxford/C1 đã có.
- Tránh biến card chính thành quá tải vì nhồi cả legal/political và formal logic/philosophy sense.

Cần làm rõ:

- Nếu tách, card phụ chứa 2 senses cuối sẽ được học bình thường, hay chỉ là card phụ/supplement để review sau?
- Card phụ có nên ở cùng deck `Oxford 5000`, hay nên có tag/deck phụ kiểu `secondary_sense`, `low_priority`, hoặc suspend mặc định?
- Display headword của card phụ nên vẫn là `proposition`, hay nên ghi rõ domain như `proposition (law/formal)` để tránh learner tưởng đây là nghĩa chính?
- Làm sao để learner nhận ra đây là card phụ trong lúc review: chỉ thêm badge là đủ, hay cần cả subtitle/headword/domain label?

Gợi ý triển khai:

- Không nên tạo 2 card trùng hoàn toàn `proposition | noun | C1 | Oxford_5000` mà không có metadata, vì hiện Card Identity mặc định chỉ cho 1 card mỗi `(Word, CEFRLevel, LIST)` trừ reviewed variant.
- Phương án khuyến nghị:
  - Card chính giữ GUID hiện tại, headword `proposition`, gồm 2 senses:
    - `suggested idea/plan`
    - `thing to deal with`
  - Card phụ là reviewed semantic variant, có GUID mới, vẫn headword `proposition` nhưng có nhãn/domain rõ:
    - `proposition (law/formal)` hoặc metadata variant tương đương
    - gồm `vote law proposal` và `[formal] opinion statement`
  - Card phụ nên có tag/deck xử lý riêng như `secondary_sense` hoặc `low_priority` nếu mục tiêu là không ép review cùng nhịp với nghĩa chính.
- Nếu chưa muốn đụng Card Identity/registry, phương án UI nhẹ hơn là giữ 1 card nhưng tách visual thành 2 nhóm:
  - Primary meanings: 2 senses đầu.
  - Secondary/advanced meanings: 2 senses cuối, có thể collapse/reveal.
- Nếu tách card phụ, nên có tín hiệu UX rõ nhưng nhẹ:
  - Thêm badge nhỏ trên top bar như `secondary`, `specialized`, hoặc `domain`.
  - Thêm subtitle dưới headword như `secondary senses: law/formal logic`.
  - Giữ sense-level label cụ thể: `law/politics` cho `vote law proposal`, `formal` cho `opinion statement`.
  - Thêm tag dữ liệu như `SecondarySense` hoặc `LowPriority` để sau này có thể lọc/suspend/reschedule.

Trạng thái ban đầu: `needs-clarification`

Quyết định chốt 2026-07-09:

- Card phụ học bình thường, không suspend.
- Card phụ dùng deck phụ: `English Academic Vocabulary::Oxford::Oxford 5000::Secondary Senses`.
- Display headword của cả hai card giữ là `proposition`.
- UX nhận diện dùng deck phụ, tag `SecondarySense`, và sense-level label; không cần đổi template trong bước này.

Triển khai:

- Card chính giữ GUID `e/a@jzBur]`, variant `primary`, còn 2 senses:
  - `suggested idea/plan`
  - `thing to deal with`
- Card phụ dùng GUID `pR0pLawF1%`, variant `secondary_law_formal`, gồm 2 senses:
  - `[politics]vote law proposal`
  - `[formal]opinion statement`

Trạng thái sau chốt: `implemented`

### 2026-07-09 - `restrain`: dùng Cambridge C1 sense thay cho card UNCLASSIFIED nhiều chunk

Ý tưởng:

- Card `restrain` hiện đang là `UNCLASSIFIED`, dù nằm trong AWL Coxhead.
- Khi tham khảo Cambridge, `restrain` có một sense được gắn CEFR `C1`.
- Cambridge sense này bao quát đúng trọng tâm học:
  - control actions/behaviour by force, especially to stop someone doing something
  - limit the growth or force of something
- Vì Cambridge chỉ có 1 sense C1, card học chỉ cần lấy đúng sense đó là đủ.
- Không cần giữ 3 chunks Oxford-style hiện tại trên card:
  - `physically stop sb/sth`
  - `stop yourself doing sth`
  - `limit growth or increase`

Mục tiêu:

- Tránh card AWL bị `UNCLASSIFIED` khi Cambridge có CEFR C1 rõ ràng.
- Giảm cognitive load: 1 Cambridge C1 sense thay vì 3 sub-senses tách dòng.
- Dùng nguồn có CEFR rõ để quyết định nội dung card học.

Cần làm rõ:

- Khi dùng Cambridge override, definition trên card nên là bản learner-gloss ngắn như `control or limit sb/sth`, hay giữ gần Cambridge hơn?
- Ví dụ nên lấy từ Cambridge screenshot, hay giữ một số ví dụ/collocations hiện tại nếu chúng minh họa tốt?
- Source fields nên đổi sang Cambridge/Cambridge hay ghi rõ Oxford + Cambridge để giữ provenance?

Gợi ý triển khai:

- Treat as `Cambridge CEFR rescue` hoặc `Cambridge sense override` cho card `restrain`.
- Card output đề xuất:
  - `word`: `restrain`
  - `pos`: `verb`
  - `cefr`: `C1`
  - `definition`: một chunk duy nhất, ví dụ `control or limit sb/sth (kiềm chế/khống chế/hạn chế)`
  - `example`: chọn 1 ví dụ đại diện từ Cambridge hoặc ví dụ tốt nhất hiện có.
  - `tags`: giữ `AWL_Coxhead`, thêm/đổi CEFR `C1`, ghi provenance Cambridge nếu hệ thống tag/source hỗ trợ.
- Không xóa raw Oxford senses khỏi source data; chỉ override build/card content cho learner-facing card.

Trạng thái: `needs-clarification`

### 2026-07-10 - `forth`: ưu tiên idiom phổ biến, giới hạn Idiom Box ở 2 mục

Ý tưởng / quyết định:

- `forth` hầu như chỉ xuất hiện như một phần của các cụm cố định, nên card cần dùng idiom để tạo ngữ cảnh học thay vì cố nhồi thêm nội dung.
- Giữ tối đa 2 idioms phổ biến trên learner-facing card:
  - `and so forth`
  - `back and forth`
- Không hiển thị `from that day/time forth` trên card chính vì khá trang trọng và ít ưu tiên hơn.
- `from that day/time forth` có thể được đưa vào card phụ sau này, hoặc chỉ giữ trong dữ liệu nguồn/raw data.
- Badge `IDIOMS · 2` là đủ; không thêm idiom chỉ vì còn diện tích trống trên card.

Mục tiêu:

- Card `forth` tập trung vào các fixed expressions learner có khả năng gặp và dùng nhiều hơn.
- Tránh biến Idiom Box thành danh sách đầy đủ theo từ điển thay vì một lựa chọn có chủ đích cho học tập.
- Giữ idiom ít ưu tiên trong nguồn để còn khả năng audit hoặc phục hồi, không coi việc không render trên card là xóa dữ liệu.

Gợi ý triển khai:

- Thêm một curated display override cho `forth` để learner-facing `Idioms` chỉ gồm hai mục đã chốt.
- Không thay đổi raw Oxford idiom extraction; chỉ lọc ở manual payload/build layer.
- Chỉ tạo reviewed secondary card nếu sau này có lý do học tập rõ ràng cho idiom trang trọng; hiện tại không cần tạo card phụ chỉ để chứa một idiom.

Trạng thái: `implemented` (2026-07-10)

### 2026-07-10 - English learner gloss cho idioms trên toàn deck

Ý tưởng:

- Hầu như các idioms trong deck hiện chưa có learner gloss rõ ràng/nhất quán.
- Khi triển khai cải thiện Idiom Box, cần bổ sung một English learner gloss ngắn cho idioms.
- Ghi chú ban đầu "không cần Vietnamese gloss" đã được quyết định mới ngày
  2026-07-16 thay thế.

Mục tiêu:

- Learner hiểu nhanh nghĩa cốt lõi của idiom ngay trên card.
- English learner gloss là lớp tóm tắt nghĩa; English explanation và example vẫn giữ vai trò giải thích/ngữ cảnh.

Cần làm rõ trước khi triển khai:

- English learner gloss nên thay thế hay đặt cạnh English explanation hiện có trong Idiom Box?
- Cần xác định nguồn và workflow viết/review gloss để xử lý toàn bộ idioms nhất quán, thay vì sinh nội dung tự do trong template.

Gợi ý triển khai:

- Bổ sung một trường hoặc curated mapping dành riêng cho English idiom gloss ở build layer; không hard-code nội dung trong template.
- Ưu tiên idioms đang được render trên learner-facing cards trước, rồi mới mở rộng sang raw idioms chưa hiển thị.

Trạng thái: `superseded` (2026-07-16)

### 2026-07-16 - Thành ngữ/tục ngữ Việt cho Idiom Box

Quyết định:

- Luôn giữ cụm idiom tiếng Anh và example hiện có.
- Nếu có một thành ngữ, tục ngữ, câu nói hoặc cách nói hình tượng cố định trong
  tiếng Việt tương đương hoặc liên hệ rõ về ý, chỉ hiển thị câu Việt đó bên dưới
  cụm tiếng Anh. Không bắt buộc trùng hình ảnh, cấu trúc hay toàn bộ sắc thái.
- Ví dụ chuẩn: `get back on the rails` → `đâu lại vào đấy`; `be at odds ...`
  → `trống đánh xuôi, kèn thổi ngược`.
- Chỉ dùng English learner gloss đơn giản + dòng nghĩa Việt khi không tìm thấy
  cách nói Việt tự nhiên có liên hệ nghĩa rõ ràng, hoặc ứng viên sẽ gây hiểu sai.
- Với `bilingual_gloss`, cả EN và VI đều là learner gloss ngắn, tự nhiên và chỉ
  giữ nghĩa cốt lõi; VI không dịch theo cấu trúc câu EN. Không dùng giới hạn số
  từ cứng, nhưng chỉ giữ câu dài khi rút gọn sẽ làm mất điều kiện quan trọng.
- Ví dụ fallback chuẩn: `an old wives’ tale` → `an old belief that is not true`
  / `quan niệm dân gian sai lầm`; `shake/rock the foundations ...` →
  `seriously weaken something at its core` / `làm lung lay tận gốc`.
- Review một lần cho mỗi phrase + source meaning và tái sử dụng trên mọi card;
  không dịch toàn bộ idiom raw chưa được chọn cho learner-facing deck.
- Cutover chỉ diễn ra sau khi Bilingual Idiom Audit hoàn tất; example và UK/US
  Idiom Example Audio không đổi.

Trạng thái: `in-progress`

### 2026-07-10 - `concede`: nhóm hai sense “thừa nhận” trên card

Ý tưởng / quyết định:

- Có thể gộp hai sense đầu ở tầng hiển thị vì cùng thuộc ý nghĩa “thừa nhận”:
  - `admit sth is true`
  - `admit defeat`
- Cách hiển thị đề xuất: `admit sth / defeat (thừa nhận / chấp nhận thua)`.
- Giữ cả hai ví dụ và các collocations liên quan để learner thấy hai cách dùng:
  - `concede that + clause`
  - `concede defeat`
- Sense thứ ba phải tách riêng: `give up or allow sth (nhượng bộ/cho phép)`, vì đã chuyển sang nghĩa khác rõ rệt.
- Không gộp trong dữ liệu nguồn; chỉ nhóm ở tầng render/card để giảm cảm giác meanings bị chia nhỏ.

Mục tiêu:

- Card phản ánh quan hệ ngữ nghĩa giữa hai cách dùng “thừa nhận”, nhưng không mất ví dụ hoặc collocation đặc trưng.
- Giữ nguồn Oxford có thể audit theo từng sense và tránh ảnh hưởng Sense Sorting/Card Identity.

Gợi ý triển khai:

- Dùng metadata hoặc render grouping cho `concede` để hai source senses đầu chung một Sense Row/nhóm hiển thị.
- Example alignment vẫn phải bảo toàn: hai examples còn được liên kết với hai source senses tương ứng trong build data.
- Render sense `give up or allow sth` thành Sense Row độc lập phía sau nhóm “admit”.

Trạng thái: `implemented` (2026-07-10)

## Cập nhật triển khai 2026-07-10

Mục 2 - `restrain`: `implemented`

- Giữ GUID ``i/Mobs,`g1`` và Card Identity AWL hiện có.
- Chuyển `verb | UNCLASSIFIED` thành `verb | C1` theo Cambridge.
- Dùng một learner gloss: `control or limit sb/sth (kiềm chế/khống chế/hạn chế)`.
- Examples Cambridge cùng một sense được nối bằng `<br><br>`.

Mục 3 - bốn card thiếu: `implemented`

- `immigrate | verb | C1 | AWL`, nguồn Oxford, GUID `imm1GrAt3C1`.
- `offset | verb | C2 | AWL`, nguồn Cambridge, GUID `offs3tC2vB`.
- `percent | adjective, adverb | B1 | AWL`, nguồn Cambridge, GUID `p3rc3ntB1x`.
- `tense | adjective | C1 | AWL`, nguồn Oxford, GUID `tens3AdjC1`.

### 2026-07-09 - `equate`: gloss không nên dùng "coi là tương đương" nếu làm mờ nghĩa chính

Ý tưởng:

- Với card `equate`, gloss hiện có phần `(đánh đồng/coi là tương đương)`.
- User nhận xét không cần nghĩa `coi là tương đương`, vì dễ khiến learner hiểu như một cách nói trung tính/tương đương logic.
- Nghĩa learner nên học chủ yếu là `đánh đồng`: coi hai thứ là giống nhau hoặc quan trọng ngang nhau, thường trong ngữ cảnh có thể là một sự quy chiếu/đánh giá.

Mục tiêu:

- Gloss tiếng Việt phải làm nổi bật core meaning cần học, không chỉ paraphrase sát chữ.
- Tránh gloss khiến learner bỏ qua sắc thái quan trọng của `equate`, nhất là collocation `equate A with B`.

Gợi ý triển khai:

- Ưu tiên gloss ngắn: `(đánh đồng)`.
- Có thể dùng gloss mở rộng nếu cần: `(đánh đồng/xem như ngang nhau)`.
- Tránh dùng riêng `coi là tương đương` làm gloss chính, vì nó không nhấn đủ sắc thái học thuật/ngữ dụng của `equate`.

Trạng thái: `implemented` (2026-07-10)

### 2026-07-09 - Bổ sung 4 card thiếu trong AWL/Oxford/Cambridge data

Ý tưởng:

- Bổ sung 4 card thiếu được nêu trong ảnh audit:
  - `immigrate`
  - `offset`
  - `percent`
  - `tense`
- CEFR lần lượt theo thứ tự trên:
  - `immigrate` = `C1`
  - `offset` = `C2`
  - `percent` = `B1`
  - `tense` = `C1`

Nguồn tham khảo từ ảnh:

- `immigrate`: Oxford data có `verb = C1`.
- `offset`: Oxford có `adjective, noun, verb`; AWL hiện có `adj = UNCLASSIFIED` từ Oxford và `v = C2` từ Cambridge fallback. User chốt card cần bổ sung dùng CEFR `C2`.
- `percent`: không có Oxford record trong `data/sources/oxford.jsonl`; AWL hiện lấy Cambridge, trong đó `noun = UNCLASSIFIED`, `adjective/adverb = B1`. User chốt card cần bổ sung dùng CEFR `B1`.
- `tense`: Oxford data có `adjective = C1`, `noun = A1`, `verb = UNCLASSIFIED`. User chốt card cần bổ sung dùng CEFR `C1`.

Mục tiêu:

- Không để thiếu các AWL-relevant cards do CEFR/source-resolution hiện tại bỏ sót hoặc chọn nhầm POS/CEFR.
- Dùng CEFR đã chốt thủ công từ audit thay vì để `UNCLASSIFIED` hoặc thiếu card.

Cần làm rõ:

- `offset` nên bổ sung POS nào là card chính: `verb C2` theo Cambridge fallback, hay một card tổng hợp nếu Oxford/Cambridge đang lệch POS?
- `percent` nên render POS là `adjective/adverb`, hay normalize thành POS phù hợp với deck/card format hiện tại?
- `tense` card C1 nên lấy `adjective` בלבד, và không tạo card cho `noun A1`/`verb UNCLASSIFIED`, đúng không?

Gợi ý triển khai:

- Treat as manual AWL/CEFR rescue entries, not generic auto-merge.
- Add/adjust registry/manual payload so production build emits exactly these four cards with CEFR:
  - `immigrate | verb | C1`
  - `offset | <POS cần chốt> | C2`
  - `percent | <POS cần chốt> | B1`
  - `tense | adjective | C1`
- Preserve provenance in notes/tags where possible: Oxford for `immigrate`/`tense`, Cambridge fallback for `offset`/`percent` if that is the source actually used.

Trạng thái: `needs-clarification`
