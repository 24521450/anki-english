# sense_grouping_review

Nơi ghi nhận các review và quyết định về việc nhóm sense ở tầng hiển thị của Anki card, trong khi vẫn giữ các sense riêng biệt ở dữ liệu nguồn.

## `abstract` - Confirmed Error / group senses

Verdict hiện tại `Reviewed Keep` là quá bảo thủ và không nhất quán với mục tiêu của review này.

Hai sense được xem là cùng lõi nghĩa “trừu tượng”:

- vật hoặc ý tưởng không cụ thể;
- nghệ thuật không mô phỏng hiện thực.

Sense về nghệ thuật là một ứng dụng chuyên biệt trong nghệ thuật của ý “không cụ thể/không hiện thực”, chưa phải một hệ nghĩa độc lập.

Quyết định hiển thị:

- Đổi verdict thành `Confirmed Error / group senses`.
- Gộp thành một Sense Row: `abstract, not concrete or realistic` - `trừu tượng`.
- Giữ đủ hai ví dụ/ngữ cảnh trong một example segment, theo thứ tự:
  - ví dụ khái niệm chung;
  - `<br><br>`;
  - ví dụ trong nghệ thuật.

Dữ liệu nguồn vẫn giữ hai sense riêng để bảo toàn provenance và audit.

## `anticipate` - verb - B2

Quyết định hiển thị:

- Gộp sense 1-2 thành một Sense Row:
  - English gloss: `expect and prepare`
  - Vietnamese gloss: `lường trước/dự đoán`
- Giữ sense 3 thành Sense Row riêng:
  - English gloss: `look forward to`
  - Vietnamese gloss: `mong đợi`

Dữ liệu nguồn vẫn giữ ba sense riêng; grouping chỉ áp dụng ở tầng hiển thị.

## `breach` - noun, verb - C1

Vấn đề:

- Card build hiện tại chỉ có noun examples:
  - `a breach of contract/copyright/warranty`
  - `a breach in relations`
- POS trên card là `noun, verb`, và gloss đầu đã gộp noun với verb, nhưng verb chỉ xuất hiện gián tiếp trong collocation `breach an agreement/promise`.
- Đây là thiếu coverage thực sự: source Oxford có verb C1 examples, nhưng learner-facing card không minh họa cách dùng verb.

Quyết định hiển thị:

1. `violation/break an agreement (vi phạm)`
   - `a breach of contract`
   - `<br><br>`
   - `The company breached the agreement.`
2. `break in relations (rạn nứt quan hệ)`
   - `a breach in relations`

Nguồn ưu tiên cho verb example là Oxford C1, ví dụ `The government is accused of breaching the terms of the treaty.` hoặc `A doctor was sacked for allegedly breaching patient confidentiality.`. Câu `The company breached the agreement.` là phương án learner-facing ngắn gọn nếu cần curate lại example.

Trạng thái: `Confirmed Error / add verb example`

## `calculation`

Quyết định hiển thị:

- Sửa learner gloss từ `using judgement` thành `careful judgement`.
- Lý do: cụm mới tự nhiên và ngắn gọn hơn, vẫn giữ đúng nghĩa cần học.

## `carve` - group senses 1-2

Đánh giá:

- Sense 1 `shape by cutting` và sense 2 `cut words into a surface` cùng lõi nghĩa: tạo hình hoặc ký tự bằng cách khắc.
- Sense 3 `cut cooked meat` là thao tác thái/cắt thịt, cần giữ riêng.
- Audit tự động phát hiện cặp sense 2-3 do cùng có từ `cut`; không gộp chính cặp đó là đúng. Tuy vậy, verdict `Reviewed Keep` cho toàn card chưa tối ưu vì bỏ sót cặp 1-2 cần group.

Quyết định hiển thị:

1. `cut shapes or words (chạm/khắc)`
   - `a carved doorway`
   - `<br><br>`
   - `They carved their initials on the desk.`
2. `slice cooked meat (thái thịt)`
   - `Who's going to carve the turkey?`

Tuỳ chọn curate example:

- Có thể thay `a carved doorway` bằng `He carved a figure from wood.` để minh họa trực tiếp hơn hành động tạo hình bằng cách chạm/khắc.

Trạng thái: `Confirmed Error / group senses 1-2`

## `casualty` - Reviewed Keep

Quyết định:

- Không gộp ba sense.
- Sense 1 chỉ người chết hoặc bị thương trong chiến tranh/tai nạn.
- Sense 2 là nghĩa rộng/ẩn dụ: người hoặc sự vật chịu hậu quả của một sự kiện.
- Sense 3 là bộ phận trong bệnh viện, độc lập hoàn toàn.

Gloss hiển thị đề xuất:

1. `person killed or injured (người thương vong)`
2. `victim of an event (nạn nhân)`
3. `emergency department (khoa cấp cứu)`

Examples hiện tại phù hợp và giữ nguyên:

1. `Our primary objective is reducing road casualties.`
2. `She became a casualty of the reduction in part-time work.`
3. `The victims were rushed to casualty.`

## `charter` - Reviewed Keep

Quyết định:

- Giữ riêng hai sense dù đều là văn bản chính thức.
- Sense 1 quy định quyền và nguyên tắc; sense 2 trao quyền/cho phép thành lập tổ chức, thị trấn hoặc trường đại học.

Gloss hiển thị đề xuất:

1. `rights/principles document (hiến chương)`
2. `founding permission (giấy phép thành lập)`

Examples hiện tại phù hợp và giữ nguyên:

1. `the United Nations Charter`
2. `The Royal College received its charter as a university in 1967.`

Sửa gloss tiếng Việt hiện tại của sense 2: `đặc quyền thành lập` -> `giấy phép thành lập`.

## `contemplate` - split overloaded display row

Đánh giá:

- Không gộp sense 1 `think about doing sth` với sense 2; verdict không gộp hiện tại là đúng.
- Sense 1 là cân nhắc một hành động hoặc khả năng.
- Hàng sense 2 hiện tại lại gộp hai cách dùng khác nhau: suy nghĩ sâu và nhìn chăm chú.
- Example hiện có cho hàng sense 2 chỉ minh họa cách dùng `look carefully`.

Quyết định hiển thị:

1. `consider doing sth (cân nhắc)`
   - `You're too young to be contemplating retirement.`
2. `think deeply (suy ngẫm)`
   - Cần bổ sung example riêng.
3. `look carefully (ngắm nhìn)`
   - `She contemplated him in silence.`

Trạng thái: `Confirmed Error / split overloaded display row`

## `crown` - Reviewed Keep

Quyết định:

- Không gộp hai nhóm nghĩa.
- Sense 1 là vật thể đội trên đầu vua hoặc nữ hoàng.
- Sense 2 là chính quyền, địa vị hoặc quyền lực hoàng gia.

Gloss hiển thị đề xuất:

1. `royal headpiece (vương miện)`
2. `royal power (vương quyền)`

Examples:

1. Giữ `The crown was placed upon the new monarch's head.`
2. Giữ `land owned by the Crown`, rồi bổ sung cùng example segment:
   - `<br><br>`
   - `He gave up the crown.`

Lưu ý: `the Crown` viết hoa khi chỉ chính quyền hoặc nhà nước quân chủ.

## `crush` - Reviewed Keep

Quyết định:

- Không gộp hai nhóm nghĩa.
- Sense 1 ép mạnh làm đối tượng bị hỏng, biến dạng hoặc vỡ vụn.
- Sense 2 ép người/vật vào không gian chật hẹp, không nhất thiết làm đối tượng bị hỏng.

Gloss hiển thị đề xuất:

1. `damage by pressing (ép/nghiền nát)`
2. `force into a small space (nhét vào chỗ chật)`

Examples hiện tại phù hợp và giữ nguyên:

1. `The car was completely crushed under the truck.`
2. `Over twenty prisoners were crushed into a small dark cell.`

Tuỳ chọn bổ sung cho sense 1: `Crush the garlic.` để minh họa rõ thao tác nghiền nhỏ.

## `denial` - group senses 1 and 3

Quyết định:

- Đổi verdict từ `Reviewed Keep` thành `Confirmed Error / group senses 1 and 3`.
- Sense 1 và 3 cùng lõi nghĩa: không chấp nhận điều gì là đúng.
- Sense 2 liên quan đến việc không cho người khác hưởng một quyền, nên giữ riêng.

Quyết định hiển thị:

1. `reject the truth (phủ nhận/chối bỏ)`
   - `the prisoner's repeated denials of the charges`
   - `<br><br>`
   - `The patient is still in denial.`
2. `refuse a right (tước quyền)`
   - `The ban is a denial of freedom of speech.`

## `distort` - group senses 1-2

Quyết định:

- Đổi verdict từ `Reviewed Keep` thành `Confirmed Error / group senses 1-2`.
- Hai sense cùng lõi: làm thay đổi khiến bản gốc không còn chính xác hoặc rõ ràng; chỉ khác đối tượng là vật lý/âm thanh và thông tin/sự thật.

Quyết định hiển thị:

- `change shape, sound or facts (làm/bóp méo)`
  - `a fairground mirror that distorts your shape`
  - `<br><br>`
  - `Newspapers are often guilty of distorting the truth.`

## `distorted` - remove card

Quyết định:

- Xóa learner-facing card `distorted`.
- Không cần review grouping riêng cho derived adjective này khi card `distort` đã bao quát hai nghĩa cốt lõi.

Trạng thái: `Confirmed Error / remove card`

## `grocery` - Reviewed Keep

Quyết định:

- Không gộp hai cách dùng.
- `grocery store/shop` chỉ cửa hàng bán thực phẩm và đồ dùng gia đình.
- `groceries` chỉ các mặt hàng được mua tại cửa hàng, thường ở dạng số nhiều.

Gloss hiển thị đề xuất:

1. `food and household shop (tiệm tạp hóa)`
2. `food and household goods (hàng tạp hóa)`

Examples hiện tại phù hợp và giữ nguyên:

1. `the corner grocery store`
2. `He set the bag of groceries down on the floor.`

## `linear` - group senses 1-2

Quyết định:

- Đổi verdict từ `Reviewed Keep` thành `Confirmed Error / group senses 1-2`.
- Hai sense là cách dùng vật lý và trừu tượng của cùng lõi “một đường liên tục”.
- Không gộp chỉ vì trùng từ `in`; căn cứ group là quan hệ ngữ nghĩa chung.

Quyết định hiển thị:

- `in a line or series (theo đường thẳng/tuyến tính)`
  - `In his art he broke the laws of scientific linear perspective.`
  - `<br><br>`
  - `Students do not always progress in a linear fashion.`

## `modest` - Reviewed Keep

Quyết định:

- Không gộp hai sense.
- Sense 1 mô tả quy mô hoặc mức độ.
- Sense 2 mô tả tính cách hoặc thái độ không khoe khoang.
- Dù cùng có liên hệ rộng là “không quá mức”, cách dùng và bản dịch khác nhau rõ rệt.

Gloss hiển thị đề xuất:

1. `small or limited (nhỏ/vừa phải)`
2. `doesn't show off (khiêm tốn)`

Examples hiện tại phù hợp và giữ nguyên:

1. `modest improvements/reforms`
2. `She's very modest about her success.`

## `neutral` - Reviewed Keep

Quyết định:

- Không gộp hai nhóm nghĩa.
- Sense 1 nói về lập trường không ủng hộ bên nào trong tranh chấp, cạnh tranh hoặc chiến tranh.
- Sense 2 nói về sắc thái, cảm xúc hoặc màu sắc không mạnh.
- Dù cùng mang ý rộng “không nghiêng về cực nào”, cách dùng và bản dịch khác nhau.

Gloss hiển thị đề xuất:

1. `not taking sides (trung lập)`
2. `not strong or emotional (trung tính)`

Examples hiện tại phù hợp và giữ nguyên:

1. `Journalists are supposed to be politically neutral.`
2. `He said it in a neutral tone of voice.`

## `oblivion` - Reviewed Keep

Quyết định:

- Không gộp ba sense.
- Sense 1: bản thân người đó mất nhận thức.
- Sense 2: người/vật không còn được người khác nhớ đến.
- Sense 3: người/vật không còn tồn tại do bị phá hủy.
- Từ `state` lặp lại chỉ là cấu trúc định nghĩa, không phải căn cứ để group senses.

Gloss hiển thị đề xuất:

1. `unconsciousness (mất ý thức)`
2. `being forgotten (sự lãng quên)`
3. `complete destruction (hủy diệt hoàn toàn)`

Examples hiện tại phù hợp và giữ nguyên:

1. `He often drinks himself into oblivion.`
2. `An unexpected victory saved him from political oblivion.`
3. `Hundreds of homes were bombed into oblivion.`

## `prevail` - Reviewed Keep

Quyết định:

- Không gộp hai sense.
- Sense 1 mô tả điều kiện hoặc quan điểm đang tồn tại/phổ biến.
- Sense 2 mô tả kết quả thắng thế hoặc thành công sau tranh đấu/tranh luận.
- Cả hai definition bắt đầu bằng `be` chỉ là trùng cấu trúc ngữ pháp, không phải cùng nghĩa.

Gloss hiển thị đề xuất:

1. `be common (phổ biến)`
2. `finally succeed (thắng thế)`

Examples hiện tại phù hợp và giữ nguyên:

1. `We were horrified at the conditions prevailing in local prisons.`
2. `Justice will prevail over tyranny.`

## `query` - Reviewed Keep

Quyết định:

- Không gộp hai sense.
- Sense 1 là một câu hỏi hoặc thắc mắc thực tế cần được giải đáp.
- Sense 2 là ký hiệu `?` được ghi bên cạnh thông tin chưa chắc chắn/chưa quyết định.

Gloss hiển thị đề xuất:

1. `question or doubt (câu hỏi/thắc mắc)`
2. `question mark (dấu hỏi)`

Sửa gloss sense 2 từ `question-mark note` thành `question mark` để ngắn và dễ hiểu hơn.

Examples hiện tại phù hợp và giữ nguyên:

1. `Our assistants will be happy to answer your queries.`
2. `Put a query against Jack's name—I'm not sure if he's coming.`

## `slash` - Reviewed Keep

Quyết định:

- Không gộp hai sense.
- Sense 1 là hành động cắt vật lý bằng vật sắc, mạnh.
- Sense 2 là nghĩa bóng, thường dùng với giá cả, chi phí hoặc ngân sách.

Gloss hiển thị đề xuất:

1. `cut violently (rạch/chém)`
2. `reduce a lot (cắt giảm mạnh)`

Gloss `reduce a lot` tự nhiên và dễ hiểu hơn `cut greatly`.

Examples hiện tại phù hợp và giữ nguyên:

1. `Someone had slashed the tyres on my car.`
2. `to slash spending/prices/costs`

## `temporal` - reviewed identity variant: general/formal vs anatomy

Quyết định:

- Tách thành 2 card, không tách thành 3:
  1. `temporal — general/formal`
     - `worldly, not spiritual (thuộc thế tục)`
     - `related to time (thuộc thời gian)`
  2. `temporal — anatomy`
     - `near the temple (thuộc thái dương)`
- Nghĩa giải phẫu là một hệ nghĩa đồng hình hoàn toàn độc lập.
- Hai nghĩa đầu vẫn liên hệ qua ý “thuộc thế giới/thời gian hiện tại”; một card hai hàng không quá tải.

Yêu cầu triển khai:

- Ghi đây là `reviewed identity variant` trong Card Registry để cho phép hai card cùng identity cơ sở mà không vi phạm Card Identity.
- Hai variant cần GUID riêng và metadata variant rõ ràng.

Trạng thái: `ready-for-design`

## `tighten` - group senses 1 and 3

Quyết định:

- Đổi verdict từ `Reviewed Keep` thành `Confirmed Error / group senses 1 and 3`.
- Sense 1 và 3 cùng lõi vật lý: trở nên hoặc làm cho chặt/căng; khác nội động từ và ngoại động từ nhưng không cần thành hai hàng riêng.
- Không tách card.

Quyết định hiển thị:

1. `make or become tight (siết/căng chặt)`
   - `to tighten a lid/screw/rope/knot`
   - `<br><br>`
   - `The rope suddenly tightened and broke.`
2. `make stricter (thắt chặt)`
   - `to tighten security`

## `vacuum` - group senses 1-2

Quyết định:

- Đổi verdict từ `Reviewed Keep` thành `Confirmed Error / group senses 1-2`.
- Hai sense là nghĩa đen và nghĩa bóng của cùng lõi “không gian trống”.
- Không tách card.

Quyết định hiển thị:

- `empty space or gap (chân không/khoảng trống)`
  - `a vacuum pump`
  - `<br><br>`
  - `His resignation created a vacuum that could not easily be filled.`

## `existential` - remove card

Quyết định:

- Xóa learner-facing card `existential`.

Trạng thái: `Confirmed Error / remove card`
