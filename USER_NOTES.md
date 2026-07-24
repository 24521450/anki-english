# User Notes

> **Vai trò:** nhật ký theo thời gian về yêu cầu trực tiếp của người dùng. Các
> mục cũ có thể đã được thực hiện, sửa lại hoặc supersede; không dùng file này
> làm current specification. Trạng thái hiện hành thuộc canonical ledgers/data,
> thuật ngữ trong `CONTEXT.md`, quyết định trong `docs/adr/`, và executable
> contracts trong tests. `AGENTS.md` giữ workflow vận hành.

Ghi lại các yêu cầu, câu hỏi và định hướng do người dùng trực tiếp nêu. Các
kết luận hoặc đề xuất của agent không được tự động xem là quyết định của người
dùng.

## 2026-07-14

- Kiểm tra gloss của card `ideal` có hợp lý không.
- Xem xét khả năng gộp hai sense của card `ideal`.
- Kiểm tra liệu các sửa đổi trong
  `C:\Users\admin\Downloads\gloss_after_audit_vi.xlsx` đã từng được áp dụng
  vào deck hay chưa.
- Review các đề xuất trong workbook trên và xác định những đề xuất hợp lý.
- Duy trì một file Markdown để ghi note những điều người dùng nói.
- Khi người dùng nêu tên card và nội dung đề xuất, chỉ ghi nội dung đó vào file
  note. Không tự sửa dữ liệu, rebuild, xóa media hoặc áp dụng thay đổi cho đến
  khi người dùng ra lệnh thực hiện rõ ràng; nếu có điểm chưa rõ thì hỏi thẳng.
- Sửa card `implicate` thành:
  `to show involvement in something bad (dính líu)` và bỏ example thứ hai.
- Trường hợp card `pledge` (`noun, verb`, C1): Oxford source có noun examples,
  nhưng curated override từ đợt review 2026-06-30 chỉ giữ verb example
  `Japan has pledged $100 million in humanitarian aid.`, khiến noun example
  không xuất hiện trong deck. Hướng xem xét là giữ gloss chung
  `serious promise (cam kết)` và minh họa cả hai từ loại trong cùng Sense Row,
  chẳng hạn
  `a pledge of support<br><br>Japan has pledged $100 million in humanitarian aid.`
  Chưa áp dụng thay đổi này; chỉ thực hiện khi người dùng ra lệnh rõ ràng.
- Card `interactive`:
  - Thay Example bằng `The school believes in interactive teaching methods.`
  - Bỏ nhãn của Definition.
  - Chưa áp dụng; chỉ thực hiện khi người dùng ra lệnh rõ ràng.

## 2026-07-16

- Nghĩa Việt trên card không cần dịch sát cấu trúc câu tiếng Anh một cách máy
  móc. Ưu tiên cách diễn đạt tự nhiên, rõ nghĩa, ngắn gọn và dễ nhớ; một nghĩa
  giải thích dài vẫn được giữ khi rút gọn sẽ làm hẹp hoặc sai nghĩa.
- Dùng ngưỡng từ 8 từ trở lên để tạo hàng đợi kiểm tra DefinitionVI, không dùng
  ngưỡng này như giới hạn độ dài hay quy tắc tự động rút gọn.
- Có thể dùng Cambridge English–Vietnamese làm bằng chứng tham khảo:
  `https://dictionary.cambridge.org/dictionary/english-vietnamese/`.
- Áp dụng `contender` thành `đối thủ nặng ký`.
- Áp dụng sense động từ của `venture` thành `mạo hiểm, cả gan`; giữ sense danh
  từ `dự án mạo hiểm`.
- Người dùng đã ra lệnh tiếp tục thực hiện việc kiểm tra các nghĩa Việt dài dòng,
  cập nhật dữ liệu và đưa kết quả vào deck; đây không còn là đề xuất chỉ để ghi
  chú.
- Làm lại toàn bộ `bilingual_idiom_audit`: khi chọn `vi_equivalent`, chỉ cần
  thành ngữ/tục ngữ/câu nói Việt tương đương hoặc liên hệ rõ về ý; không bắt
  buộc khớp sát hình ảnh, cấu trúc hay toàn bộ sắc thái dụng học.
- Hai mapping chuẩn do người dùng chỉ định:
  - `get back on the rails` → `đâu lại vào đấy`.
  - `be at odds (with somebody) (over/on something)` →
    `trống đánh xuôi, kèn thổi ngược`.
- Loại thẳng tay các sense quá hẹp hoặc quá chuyên ngành so với nhu cầu học
  IELTS / Academic English, nhưng không tự động xóa chỉ vì source gắn nhãn
  domain hoặc `specialized`.
- `agile`: chỉ giữ nghĩa `quick-thinking`; loại hai nghĩa jargon về quản lý dự
  án Agile và mô hình Agile working.
- Dùng quyết định cũ của `domain` (loại nghĩa computing về tên miền) làm tiền
  lệ và kiểm tra toàn bộ ledger để tìm các trường hợp tương tự.

## 2026-07-17

- Rà soát lại toàn bộ Definition EN và DefinitionVI dài dòng; không chỉ sửa một
  vài ví dụ riêng lẻ.
- `transcribe` không nên giữ câu VI dài
  `chép lại lời nói, suy nghĩ hoặc dữ liệu, hoặc chuyển nội dung sang dạng chữ viết khác`;
  cần tìm một lexical gloss ngắn, tự nhiên và vẫn bao quát đúng sense.
- Ghi quy tắc chống tái phạm vào tài liệu và quy trình review: không được coi
  việc chỉ đổi dấu câu hoặc đảo trật tự từ là đã xử lý xong một gloss dài nếu có
  từ/cụm từ tương đương ngắn gọn, rõ nghĩa.
- Chốt quy tắc `bilingual_gloss`: cả EN và VI đều phải là learner gloss ngắn,
  tự nhiên, giữ đúng ý cốt lõi; đây không phải bản dịch đầy đủ của source.
- VI phải được viết tự nhiên theo tiếng Việt, không bám cấu trúc câu EN hoặc giữ
  các cụm máy móc như “một… mà nay đã được biết là…”.
- Không áp đặt giới hạn số từ cứng; chỉ giữ dài khi rút gọn sẽ làm sai nghĩa hoặc
  mất một điều kiện quan trọng.
- Mapping chuẩn: `an old wives’ tale` → `an old belief that is not true` /
  `quan niệm dân gian sai lầm`; `shake/rock the foundations ...` → `seriously
  weaken something at its core` / `làm lung lay tận gốc`.
- Rà soát lại toàn bộ 79 mục `bilingual_gloss` theo quy tắc này.
- Đã áp dụng `transcribe` sense 1 thành
  `write down or convert into another written form` / `chép lại, chuyển tự`;
  giữ sense riêng `phiên âm` vì trực tiếp hữu ích cho người học ngôn ngữ.
- Audit Definition cuối không còn mục EN nào đạt ngưỡng dài 12 token; các tín
  hiệu còn lại chỉ do dấu nối sense và đều đã được review. Audit VI từ 204 mục
  còn 5 trường hợp giải thích có lý do giữ cụ thể trong ledger.
- Đã loại sense tố giác chính trị hẹp của `denounce`, nhánh nguyên nhân của
  `implicate`, phần găng tay của `thumb`, và nhánh computing của `valid`; không
  được phục hồi các source này trong lần scaffold/promote sau.
- Không coi 28 `bilingual_gloss` từng giữ nguyên là đã được duyệt; phải mở lại
  toàn bộ và tiếp tục bỏ chủ thể/tân ngữ giữ chỗ cùng các mệnh đề phụ không cần
  thiết khi phrase đã mang sẵn `somebody`, `something`, v.v.
- `twist somebody’s arm` dùng learner gloss `persuade/pressure` /
  `thuyết phục/nài ép`, không lặp `hoặc`, người chịu tác động hay mệnh đề hành
  động đã có trong pattern.
- Cambridge định nghĩa `put somebody to the sword` bằng nghĩa cốt lõi `to kill
  someone`; dùng `kill` / `giết`, không lặp chi tiết “bằng kiếm” trong gloss.
- Quy tắc chống tái diễn: `unchanged` không đồng nghĩa với `reviewed`. Mỗi gloss
  được giữ nguyên phải ghi riêng phương án ngắn hơn đã cân nhắc và phần nghĩa
  quan trọng sẽ mất nếu dùng phương án đó, hoặc dẫn đúng cặp canonical do người
  dùng khóa. Không được dùng một lý do chung để bulk-pass cả nhóm giữ nguyên.
- Mapping chuẩn do người dùng khóa cho `compel` là `ép buộc`; không nối thêm
  `khiến trở nên cần thiết` chỉ vì source Definition EN có vế “to make something
  necessary”. Có thể thêm từ gần nghĩa như `bắt buộc` hoặc `thúc ép` khi chúng
  thật sự giúp người học, nhưng không dùng từ gần nghĩa để kéo dài gloss.
- `DefinitionVI` phải là lexical equivalent tiếng Việt tự nhiên, rõ nghĩa và
  súc tích, không phải bản dịch từng mệnh đề của Definition EN. Việc bao phủ đầy
  đủ source sense bảo đảm đúng nghĩa, nhưng không buộc VI phải lặp mọi vế giải
  thích tiếng Anh. Cambridge English–Vietnamese là bằng chứng tham khảo, không
  phải wording bắt buộc.
- Rà soát naturalness cho mọi promoted Semantic Sense, không chỉ các gloss dài.
  Một wording không đổi chỉ được xem là đã review khi có verdict riêng được
  duyệt; verdict cũ được giữ lại khi fingerprint của chính sense đó không đổi,
  còn sense mới hoặc thay đổi phải chặn promotion cho đến khi được duyệt.

## 2026-07-18

- Dựa trên toàn bộ lỗi nghĩa EN/VI dài dòng, dịch máy móc, sense quá hẹp/chuyên
  ngành, và lỗi release/CI đã xác định và sửa, thiết lập ghi chú cùng hàng rào
  bền vững để những lỗi này không tái diễn ở lần scaffold, promote, build,
  package, import hoặc push sau.
- Rà lại cả các dòng từng được bulk-pass bằng cùng một mẫu lý do. Bằng chứng VI
  phải bám đúng nghĩa EN và ví dụ/source của từng sense; chỉ thay headword hoặc
  final VI trong một câu mẫu không được tính là review riêng.
- Audit nội dung đã phát hiện và sửa thêm 22 card/sense bị gộp sai, diễn giải
  dài, hoặc giữ sense quá chuyên biệt. Mọi split/remap/exclude phải đi qua
  Bilingual Semantic Audit và giữ đầy đủ source coverage; không sửa tay Registry
  hay build output.
- Release guard phải kiểm tra nội dung thật bên trong `.apkg`, byte media sau
  import, và trạng thái sạch của cả card Recognition lẫn Production mới; sidecar,
  filename và note count không tự chứng minh package/import là đúng.
- GUID có dấu ngoặc kép do quoting của TSV cũ phải được chuẩn hóa về đúng giá trị
  Anki khi bootstrap, nhưng registry đã tồn tại phải từ chối GUID không canonical
  hoặc collision thay vì tự sửa âm thầm.
- Không được xem `notesInfo` là bằng chứng GUID vì API này không trả trường GUID.
  Sau import phải export deck qua AnkiConnect, đọc SQLite trong APKG, đối chiếu
  chính xác GUID với Card Identity/card ordinal và chỉ sau đó mới ghi receipt.
- Media cùng filename nhưng khác byte phải được xem là stale: sync ghi đè từ file
  canonical rồi verifier đọc lại độc lập. Chỉ kiểm tra filename tồn tại là chưa đủ.
- Làm nổi bật các collocation đã được review và có bằng chứng Oxford/Cambridge;
  marker phải ghi rõ `OXF`, `CAM`, hoặc `OXF+CAM`, còn collocation curated/default
  giữ kiểu xám. Ví dụ `curriculum` phải xem xét cả `on the curriculum` và
  `in the curriculum`, không chỉ giữ danh sách mặc định hiện có.
- Audit hai chiều toàn bộ collocation của deck: review từng chip đang hiển thị và
  từng source candidate gắn với example. Oxford Collocations Dictionary snippet,
  Cambridge bare `.lu`, và grammar `.cl` chỉ là bằng chứng hỗ trợ, không tự động
  trở thành candidate bắt buộc hay content production.
- Mỗi quyết định collocation phải được duyệt ở cấp item; không bulk-pass. Tối đa
  năm chip/card, không cắt ngầm. Source phrase phải là chip chính xác riêng biệt,
  không nén bằng dấu `/`; item curated vẫn có thể giữ dạng slash đã review.
- Chỉ cut over production khi toàn bộ Collocation Audit đã hoàn tất và promote
  byte-deterministic. Sau cutover phải fail closed trên exact active-card coverage,
  không fallback legacy theo từng card.

## 2026-07-19

- Oxford xác nhận `accordingly` (adverb, C1) có nhãn `OPAL W`; sửa parser và
  ingestion để bảo toàn OPAL W/S theo đúng POS, rebuild source/card tags, audit
  toàn bộ Oxford JSONL, và thêm regression cho source lẫn build output.
- Tag production giữ contract hiện có `OPAL_W` / `OPAL_S`; không đổi sang
  namespace `Corpus::`. Không được union OPAL ở cấp headword nếu các POS hoặc
  homonym có membership khác nhau.

## 2026-07-22

- Áp dụng toàn bộ ghi chú trong `scratch/takenote.md` qua các authority review,
  promotion và build hiện hành; không sửa tay Semantic/Collocation Registry hay
  build output.
- Chốt quy tắc Example/POS ở cấp card: card có `N` POS khác nhau phải có ít
  nhất `N` main Example trên toàn bộ senses. Idiom Example không được tính và
  không bắt buộc từng sense riêng lẻ phải có số Example bằng số POS.
- Sửa payload semantic đã review: `abuse` sense 3 → `sỉ nhục`; thêm noun Example
  cho `reform`; `militant` → `quá khích/cực đoan` và thêm noun Example; gộp
  `mature` thành `fully developed physically or emotionally` / `trưởng thành;
  chín chắn`; sửa `trace` C1, `thesis`, `inspiration`, `confine`, `cooperate`,
  `drown`, và `discretion`; loại các sense đã chỉ định của `exclusive`,
  `cooperate`, và `dairy` với source coverage được ghi rõ.
- Tách atomically ba Card Identity C1 đã review, mỗi từ chỉ tạo một card
  secondary: `denial` (sense 1 | senses 2+3), `alien` adjective (senses 1+2 |
  senses 3+4), và `sensitivity` (social/emotional | art/physical). Card
  secondary đi vào `Oxford 5000::Secondary Senses`, có GUID/variant ổn định và
  tag `SecondarySense`; card primary giữ GUID cũ.
- Sửa Idiom Vietnamese Gloss `squeeze somebody dry` thành `vắt kiệt`; phục hồi
  Unicode cho `(as) sound as a bell` thành `hoàn toàn khỏe mạnh/nguyên vẹn`.
  Review/build phải chặn `U+FFFD` và dấu `?` kiểu mất dấu đứng trước chữ, nhưng
  vẫn cho phép dấu hỏi kết thúc câu hợp lệ.
- IPA và headword audio phải được chọn theo cùng một entry Oxford/Cambridge cho
  từng accent. Cambridge được ưu tiên, nhưng tên file cũ không phải authority;
  ambiguity/alias/absence đi qua Pronunciation Selection Lock và mọi media được
  ràng buộc byte bằng Headword Audio Manifest.
- Tách fingerprint của entry selection khỏi fingerprint của media payload.
  Nhiều entry identity chỉ được dùng chung filename khi media fingerprint và
  byte attestation trùng chính xác; lock/manifest thừa ngoài active selection
  phải làm production fail closed. Migration schema v2 giữ nguyên byte audio,
  attest rõ các ambiguity cùng payload, rồi loại bỏ command one-shot khỏi HEAD.
- Transaction tách Card Identity phải có durable journal và old-value backups;
  lỗi thường rollback ngay, còn lần non-dry-run kế tiếp phải recover một hard
  interruption trước khi đọc hoặc ghi authority mới.
- Sửa provenance collocation `incur`: `anger`, `wrath`, `costs`, `expenses` có
  marker CAM; nhóm `losses/damage/penalties` giữ curated. Với `portion`, tách
  `generous portion` thành chip Cambridge riêng và giữ `individual portion`
  neutral curated. Matching evidence phải exact-first; chỉ cho phép biến thể
  số ít/số nhiều đều đặn của chính headword khi không có exact evidence, và
  provenance luôn thuộc từng chip thay vì cả cụm slash-compressed.
- Trước mọi lần push, phải đọc workflow CI tại revision hiện tại và
  chạy đúng tất cả blocking command liên quan; full `pytest` xanh không tự
  nó cho phép push. Thay đổi parser/schema/fixture bắt buộc chạy
  `python -m tools.ci_hydrate_parser_fixtures` theo đường clean-checkout và
  không được để cache local che lấp lỗi. Không push hoặc báo "ready"
  khi còn lệnh bắt buộc chưa chạy hay đang fail.
- Đổi deck `English Academic Vocabulary::AWL 50 Academic Words` thành
  `English Academic Vocabulary::AWL_Coxhead`, giữ nguyên 57 GUID/identity,
  card IDs, lịch học và deck config khi migrate qua AnkiConnect; chỉ xóa shell
  cũ sau khi chứng minh nó rỗng và không có deck con.
- Rà soát lại toàn bộ collocation. Cambridge `.cl` nằm trong example phải giữ
  tọa độ example; ordinary example chỉ được sinh pattern có kiểm soát và vẫn
  phải review từng item. Riêng `portion` dùng chip chính xác `portion of`, không
  dùng `portion of sth`, với provenance Oxford + Cambridge.
- Tách `contend with sb/sth` thành Secondary Sense Card riêng và khóa chính xác
  Vietnamese Gloss là `đối phó`; card chính `contend` chỉ giữ `contend that`,
  `contend for sth`, và `contend against sb` theo provenance đã chỉ định.

## 2026-07-24

- Thiết kế lại headword audio thành Pronunciation Cluster: UK luôn bên trái,
  US bên phải; IPA khác nhau dùng hai pill có nhãn, IPA giống nhau chỉ hiển thị
  một pill chia hai vùng bấm 50/50. Shared pill không hiện nhãn hay icon khi
  nghỉ; icon chỉ hiện trong lúc đang phát. Recognition answer autoplay UK, `R`
  phát lại accent gần nhất; Example Accent Toggle nằm cùng hàng ở góc phải và
  không có nhãn `Examples`.

- Áp dụng `scratch/takenote.md` qua các review authority hiện hành: tách card
  secondary cho `worthy` (typical-of), `provision` (legal condition), và
  `allowance` (tiền tiêu vặt); tách riêng nghĩa plural-only `provisions`; sửa
  `conserve`, `tolerate`, `federal`; loại đúng các sense/example đã chỉ định.
- Rà soát Definition EN trên toàn bộ deck theo từng batch 100 sense. Threshold
  độ dài chỉ dùng để triage; mọi sense phải có review fingerprint-bound, và mọi
  rewrite phải giữ register, điều kiện, giới hạn cùng đối lập nghĩa quan trọng.
- Bổ sung snapshot Cambridge English–Vietnamese cho exact active Card Identity
  coverage tại `data/sources/cambridge_english_vietnamese.jsonl` để làm bằng
  chứng giải nghĩa hiện tại và nguồn tham chiếu lâu dài. Lỗi HTTP/parser phải
  fail closed; không được ghi thành `no_entry`, tự động stemming, hay override
  Semantic Registry.
- Chỉ import deck cuối qua pipeline/AnkiConnect sau khi toàn bộ batch review,
  promotion, build, Release Guard, package provenance và post-import GUID/media
  verification đều hoàn tất.
