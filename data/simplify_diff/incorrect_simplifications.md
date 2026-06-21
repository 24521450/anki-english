# Báo cáo Kiểm tra Dữ liệu Đơn giản hóa (Incorrect Simplification Audit Report)

Dưới đây là danh sách chi tiết các lỗi đơn giản hóa sai làm mất/méo mó nghĩa nghiêm trọng (Semantic Loss/Distortion) được phát hiện khi đối chiếu dữ liệu trong [audit_full_deck.jsonl](file:///C:/Users/admin/Downloads/ankideck/data/simplify_diff/audit_full_deck.jsonl) với dữ liệu gốc [oxford_merged.jsonl](file:///C:/Users/admin/Downloads/ankideck/data/oxford_merged.jsonl).

## Tiêu chí Đánh giá & Phân tích POS
1. **Semantic Loss/Distortion:** Bản đơn giản hóa (`gloss_after`) bị co gọn quá mức hoặc chọn sai nét nghĩa học thuật.
2. **POS Alignment & Sense Cap Audit:** Đối chiếu cụ thể trên từng Từ loại (Part of Speech) xem có bị lược bỏ định nghĩa cùng mức CEFR trên thẻ do cơ chế **Sense Cap = 3** hay không. Việc lược bỏ này khiến thẻ ghi nhận POS (ví dụ: `noun, verb`) nhưng nội dung chỉ chứa nghĩa của một POS (như chỉ chứa Noun).
3. **Recommended replacement gloss:** Đề xuất cụm giải nghĩa mới (1-6 từ) bao quát tốt hơn các nét nghĩa quan trọng hoặc khôi phục nét nghĩa của POS bị mất.

---

### 1. `configuration` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `an arrangement of the parts of something or a group of things; the form or shape that this arrangement produces`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `arrangement`
- **Lý do sai lệch ngữ nghĩa:** arrangement (sắp xếp) là quá rộng, làm mất nét nghĩa cấu trúc/cấu hình (sắp xếp các bộ phận tạo thành hình dáng cụ thể).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `structural layout`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 1 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (1):*
      - "an arrangement of the parts of something or a group of things; the form or shape that this arrangement produces"

### 2. `abuse` (noun, verb) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `the use of something in a way that is wrong or harmful|unfair, cruel or violent treatment of somebody|rude and offensive remarks, usually made when somebody is very angry`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `harm`
- **Lý do sai lệch ngữ nghĩa:** harm (gây hại) là quá chung chung, làm mất nghĩa đặc trưng như lạm dụng (substance/power abuse) và sỉ vả/lăng mạ (verbal abuse). Do Sense Cap = 3, toàn bộ 4 nghĩa Động từ (Verb) của C1 đã bị lược bỏ khỏi thẻ, chỉ còn giữ lại nghĩa Danh từ (Noun).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `misuse | mistreatment`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "the use of something in a way that is wrong or harmful"
      - "unfair, cruel or violent treatment of somebody"
      - "rude and offensive remarks, usually made when somebody is very angry"
  - **Từ loại `verb`** (Tổng cộng 4 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (0):*
    - *Bị lược bỏ do Sense Cap (4):*
      - "to make bad use of something, or to use so much of something that it harms your health"
      - "to use power or knowledge unfairly or wrongly"
      - "to treat a person or an animal in a cruel or violent way, especially sexually"
      - "to make rude or offensive remarks to or about somebody"

### 3. `bug` (noun) - CEFR: `B2`
- **Định nghĩa trên Card (`def_before`):** `any small insect|an illness that is usually fairly mild but spreads easily from person to person|a fault in a machine, especially in a computer system or program`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `insect`
- **Lý do sai lệch ngữ nghĩa:** insect (côn trùng) quá hẹp, bỏ qua hai nghĩa cực kỳ phổ biến là lỗi phần mềm và bệnh dịch nhẹ (stomach bug).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `insect | minor illness | software error`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (3):*
      - "any small insect"
      - "an illness that is usually fairly mild but spreads easily from person to person"
      - "a fault in a machine, especially in a computer system or program"

### 4. `concrete` (adjective, noun) - CEFR: `B2`
- **Định nghĩa trên Card (`def_before`):** `made of concrete|building material that is made by mixing together cement, sand, small stones and water`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `cement`
- **Lý do sai lệch ngữ nghĩa:** cement (xi măng) chỉ là thành phần chế tạo bê tông chứ không phải bê tông. Ngoài ra còn bỏ sót nghĩa tính từ 'cụ thể' (concrete evidence) do Sense Cap giới hạn 3 nghĩa nên nghĩa tính từ 'vật thể hữu hình' bị loại bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `tangible; real | building material`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `adjective`** (Tổng cộng 2 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (1):*
      - "made of concrete"
    - *Bị lược bỏ do Sense Cap (1):*
      - "a concrete object is one that you can see and feel"
  - **Từ loại `noun`** (Tổng cộng 1 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (1):*
      - "building material that is made by mixing together cement, sand, small stones and water"

### 5. `domestic` (adjective) - CEFR: `B2`
- **Định nghĩa trên Card (`def_before`):** `of or inside a particular country; not foreign or international|used in the home; connected with the home or family|kept on farms or as pets; not wild`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `household`
- **Lý do sai lệch ngữ nghĩa:** household (gia đình) bỏ sót nét nghĩa quan trọng nhất trong học thuật/kinh tế là quốc nội/trong nước (domestic flight/market). Sense Cap = 3 loại bỏ nghĩa tính từ 'thích ở nhà, tươm tất dọn dẹp'.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `national; internal | household | tamed`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `adjective`** (Tổng cộng 4 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (3):*
      - "of or inside a particular country; not foreign or international"
      - "used in the home; connected with the home or family"
      - "kept on farms or as pets; not wild"
    - *Bị lược bỏ do Sense Cap (1):*
      - "liking home life; enjoying or good at cooking, cleaning the house, etc."

### 6. `critical` (adjective) - CEFR: `B2`
- **Định nghĩa trên Card (`def_before`):** `saying what you think is bad about somebody/something|extremely important because a future situation will be affected by it|serious, uncertain and possibly dangerous`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `crucial`
- **Lý do sai lệch ngữ nghĩa:** crucial (quan trọng) bỏ sót nghĩa gốc là chỉ trích/phê bình (critical comments) và tình trạng nguy kịch (critical condition). Thẻ bị thiếu 2 nghĩa liên quan đến phê bình nghệ thuật và phán xét do giới hạn Sense Cap.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `criticizing | crucial | dangerous`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `adjective`** (Tổng cộng 5 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (3):*
      - "saying what you think is bad about somebody/something"
      - "extremely important because a future situation will be affected by it"
      - "serious, uncertain and possibly dangerous"
    - *Bị lược bỏ do Sense Cap (2):*
      - "involving making fair, careful judgements about the good and bad qualities of somebody/something"
      - "according to the judgement of critics of art, music, literature, etc."

### 7. `curse` (noun) - CEFR: `UNCLASSIFIED`
- **Định nghĩa trên Card (`def_before`):** `a rude or offensive word or phrase that some people use when they are very angry|a word or phrase that has a magic power to make something bad happen|something that causes harm or evil`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `swear word`
- **Lý do sai lệch ngữ nghĩa:** swear word (chửi thề) bỏ sót nghĩa siêu nhiên là lời nguyền và nghĩa tai họa/hiểm họa chung.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `swear word | magic spell | plague`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 0 nghĩa có cùng mức CEFR `UNCLASSIFIED`):
    - *Được hiển thị trên Card (0):*

### 8. `dictate` (verb) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `to tell somebody what to do, especially in an annoying way|to control or influence how something happens|to say words for somebody else to write down or to be recorded`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `command; transcribe`
- **Lý do sai lệch ngữ nghĩa:** transcribe (chép lại) là vai trò của người nghe, trong khi dictate là người đọc cho viết. Hơn nữa, nó bỏ sót nghĩa học thuật chính là chi phối/quyết định (demand dictates supply).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `order | determine | read aloud for writing`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `verb`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "to tell somebody what to do, especially in an annoying way"
      - "to control or influence how something happens"
      - "to say words for somebody else to write down or to be recorded"

### 9. `assembly` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `a group of people who have been elected to meet together regularly and make decisions or laws for a particular region or country|the meeting together of a group of people for a particular purpose; a group of people who meet together for a particular purpose|a meeting of the teachers and students in a school, usually at the start of the day, to give information, discuss school events or say prayers together`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `gathering`
- **Lý do sai lệch ngữ nghĩa:** gathering (tụ tập) quá thông tục, làm mất đi tính chính thức của cơ quan lập pháp (National Assembly - Quốc hội) hoặc buổi chào cờ trường học. Nghĩa 'sự lắp ráp linh kiện' (vehicle assembly) bị loại bỏ bởi Sense Cap.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `legislative body | gathering`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 4 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "a group of people who have been elected to meet together regularly and make decisions or laws for a particular region or country"
      - "the meeting together of a group of people for a particular purpose; a group of people who meet together for a particular purpose"
      - "a meeting of the teachers and students in a school, usually at the start of the day, to give information, discuss school events or say prayers together"
    - *Bị lược bỏ do Sense Cap (1):*
      - "the process of putting together the parts of something such as a vehicle or piece of furniture"

### 10. `barrier` (noun) - CEFR: `B2`
- **Định nghĩa trên Card (`def_before`):** `an object like a fence that prevents people from moving forward from one place to another|a problem, rule or situation that prevents somebody from doing something, or that makes something impossible|something that exists between one thing or person and another and keeps them separate`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `obstacle`
- **Lý do sai lệch ngữ nghĩa:** obstacle (trở ngại) chỉ bao hàm nghĩa bóng, làm mất đi nghĩa đen vật lý cực kỳ phổ biến là rào chắn/vách ngăn. Nghĩa rào chắn tự động ở ga tàu/bãi đỗ xe và định mức khó vượt qua bị loại bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `physical fence | obstacle`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 5 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (3):*
      - "an object like a fence that prevents people from moving forward from one place to another"
      - "a problem, rule or situation that prevents somebody from doing something, or that makes something impossible"
      - "something that exists between one thing or person and another and keeps them separate"
    - *Bị lược bỏ do Sense Cap (2):*
      - "a gate at a car park or railway station that controls when you may go through by being raised or lowered"
      - "a particular amount, level or number that it is difficult to get past"

### 11. `allowance` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `an amount of money that is given to somebody regularly or for a particular purpose|the amount of something that is allowed in a particular situation|a small amount of money that parents give their children, usually every week or every month`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `stipend`
- **Lý do sai lệch ngữ nghĩa:** stipend (tiền trợ cấp) bỏ sót nghĩa về giới hạn định mức cho phép như baggage allowance (hành lý ký gửi tối đa) hay tax allowance. Nghĩa 'định mức miễn thuế' bị loại bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `stipend | allowed limit`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 4 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "an amount of money that is given to somebody regularly or for a particular purpose"
      - "the amount of something that is allowed in a particular situation"
      - "a small amount of money that parents give their children, usually every week or every month"
    - *Bị lược bỏ do Sense Cap (1):*
      - "an amount of money that can be earned or received before you start paying tax"

### 12. `compensation` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `something, especially money, that somebody gives you because they have hurt you, or damaged something that you own; the act of giving this to somebody|money that an employee receives for doing their job|a thing or things that make a bad situation better`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `payment`
- **Lý do sai lệch ngữ nghĩa:** payment (thanh toán) quá rộng, làm mất nghĩa bồi thường thiệt hại (damages) hoặc thù lao/chế độ lương thưởng (salary package).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `damages payout | salary package`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "something, especially money, that somebody gives you because they have hurt you, or damaged something that you own; the act of giving this to somebody"
      - "money that an employee receives for doing their job"
      - "a thing or things that make a bad situation better"

### 13. `compromise` (noun, verb) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `an agreement made between two people or groups in which each side gives up some of the things they want so that both sides are happy at the end ; a solution to a problem in which two or more things cannot exist together as they are, in which each thing is reduced or changed slightly so that they can exist together ; the act of reaching a compromise|to give up some of your demands in order to reach an agreement after disagreeing with somebody|to do something that is against your principles or does not reach standards that you have set`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `agreement`
- **Lý do sai lệch ngữ nghĩa:** agreement (thỏa thuận) bỏ sót hoàn toàn nghĩa động từ quan trọng là làm tổn hại, làm yếu đi hoặc gây nguy hiểm cho nguyên tắc/an toàn. Do Sense Cap = 3, 2 nghĩa verb quan trọng về làm suy yếu/nguy hại bị loại bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `concession | put in danger; weaken`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "an agreement made between two people or groups in which each side gives up some of the things they want so that both sides are happy at the end"
      - "a solution to a problem in which two or more things cannot exist together as they are, in which each thing is reduced or changed slightly so that they can exist together"
      - "the act of reaching a compromise"
  - **Từ loại `verb`** (Tổng cộng 4 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (2):*
      - "to give up some of your demands in order to reach an agreement after disagreeing with somebody"
      - "to do something that is against your principles or does not reach standards that you have set"
    - *Bị lược bỏ do Sense Cap (2):*
      - "to cause somebody/something/yourself to be in danger or to be suspected of something, especially by acting in a way that is not very sensible"
      - "to cause something to be in danger of attack or of working less well"

### 14. `correspondence` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `the letters, emails, etc. a person sends and receives|the activity of writing letters|a connection between two things; the fact of two things being similar`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `mail`
- **Lý do sai lệch ngữ nghĩa:** mail (thư từ) bỏ sót nghĩa học thuật quan trọng là mối tương quan/sự tương ứng giữa hai thực thể (correspondence between two things).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `written letters | similarity`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "the letters, emails, etc. a person sends and receives"
      - "the activity of writing letters"
      - "a connection between two things; the fact of two things being similar"

### 15. `dimension` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `a measurement in space, for example how high, wide or long something is|the size and extent of a situation|an aspect, or way of looking at or thinking about something`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `measurement`
- **Lý do sai lệch ngữ nghĩa:** measurement (kích thước vật lý) bỏ sót nghĩa trừu tượng học thuật cực kỳ phổ biến là khía cạnh/chiều hướng của vấn đề.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `measurement | aspect`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "a measurement in space, for example how high, wide or long something is"
      - "the size and extent of a situation"
      - "an aspect, or way of looking at or thinking about something"

### 16. `donor` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `a person or an organization that makes a gift of money, clothes, food, etc. to a charity, etc.|a person who gives blood or a part of his or her body to be used by doctors in medical treatment`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `giver`
- **Lý do sai lệch ngữ nghĩa:** giver (người cho) quá thông tục, mất nét nghĩa chuyên ngành/học thuật như nhà tài trợ/hiến tặng hoặc người hiến máu/tạng.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `charity contributor | medical giver`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 2 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (2):*
      - "a person or an organization that makes a gift of money, clothes, food, etc. to a charity, etc."
      - "a person who gives blood or a part of his or her body to be used by doctors in medical treatment"

### 17. `agile` (adjective) - CEFR: `C2`
- **Định nghĩa trên Card (`def_before`):** `able to think quickly and in an intelligent way|used to describe a way of managing projects in which work is divided into a series of short tasks, with regular breaks to review the work and adapt the plans|used to describe a way of working in which the time and place of work, and the roles that people carry out, can all be changed according to need, and the focus is on the goals to be achieved, rather than the exact methods used`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `quick-thinking`
- **Lý do sai lệch ngữ nghĩa:** quick-thinking (nhanh trí) bỏ sót nghĩa chuyên môn phổ biến trong quản trị dự án là phương pháp quản trị linh hoạt (Agile) và cách làm việc linh hoạt.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `quick-thinking | flexible project style`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `adjective`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C2`):
    - *Được hiển thị trên Card (3):*
      - "able to think quickly and in an intelligent way"
      - "used to describe a way of managing projects in which work is divided into a series of short tasks, with regular breaks to review the work and adapt the plans"
      - "used to describe a way of working in which the time and place of work, and the roles that people carry out, can all be changed according to need, and the focus is on the goals to be achieved, rather than the exact methods used"

### 18. `circulation` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `the movement of blood around the body|the passing or spreading of something from one person or place to another|the usual number of copies of a newspaper or magazine that are sold each day, week, etc.`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `spread | sales`
- **Lý do sai lệch ngữ nghĩa:** spread | sales (phát hành/doanh số) bỏ sót nghĩa sinh học cốt lõi là tuần hoàn máu (blood circulation). Nghĩa 'luồng khí/nước tuần hoàn' và 'tham gia hoạt động xã hội' bị loại bỏ bởi Sense Cap.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `blood flow | spreading | newspaper sales`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 5 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "the movement of blood around the body"
      - "the passing or spreading of something from one person or place to another"
      - "the usual number of copies of a newspaper or magazine that are sold each day, week, etc."
    - *Bị lược bỏ do Sense Cap (2):*
      - "the movement of something (for example air, water, gas, etc.) around an area or inside a system or machine"
      - "the fact that somebody takes part in social activities at a particular time"

### 19. `net` (adjective) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `a net amount of money is the amount that remains when nothing more is to be taken away|the net weight of something is the weight without its container or the material it is wrapped in|final, after all the important facts have been included`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `after-tax`
- **Lý do sai lệch ngữ nghĩa:** after-tax (sau thuế) quá hẹp, không thể áp dụng cho net weight (khối lượng tịnh - không tính bao bì) hoặc net effect (hiệu ứng cuối cùng).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `remaining after deductions`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `adjective`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "a net amount of money is the amount that remains when nothing more is to be taken away"
      - "the net weight of something is the weight without its container or the material it is wrapped in"
      - "final, after all the important facts have been included"

### 20. `operator` (noun) - CEFR: `B2`
- **Định nghĩa trên Card (`def_before`):** `a person who operates equipment or a machine|a person or company that runs a particular business|a person who works on the phone switchboard of a large company or organization, especially at a telephone exchange`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `worker`
- **Lý do sai lệch ngữ nghĩa:** worker (công nhân) quá rộng, mất nét nghĩa vận hành máy móc thiết bị (machine operator) hay nhân viên tổng đài (switchboard operator). Nghĩa bóng 'kẻ mưu mẹo đạt lợi ích' bị lược bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `machine operator | business runner`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 4 nghĩa có cùng mức CEFR `B2`):
    - *Được hiển thị trên Card (3):*
      - "a person who operates equipment or a machine"
      - "a person or company that runs a particular business"
      - "a person who works on the phone switchboard of a large company or organization, especially at a telephone exchange"
    - *Bị lược bỏ do Sense Cap (1):*
      - "a person who shows skill at getting what they want, especially when this involves behaving in a dishonest way"

### 21. `overlook` (verb) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `to fail to see or notice something|to see something wrong or bad but decide to ignore it|if a building, etc. overlooks a place, you can see that place from the building`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `miss`
- **Lý do sai lệch ngữ nghĩa:** miss (bỏ lỡ) bỏ sót nghĩa khoan dung/bỏ qua lỗi lầm (overlook mistakes) và nghĩa không gian là trông ra/hướng ra (window overlooks the garden). Nghĩa 'không cân nhắc ai vào vị trí' bị loại bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `fail to notice | turn a blind eye | view from above`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `verb`** (Tổng cộng 4 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "to fail to see or notice something"
      - "to see something wrong or bad but decide to ignore it"
      - "if a building, etc. overlooks a place, you can see that place from the building"
    - *Bị lược bỏ do Sense Cap (1):*
      - "to not consider somebody for a job or position, even though they might be suitable"

### 22. `physiological` (adjective) - CEFR: `UNCLASSIFIED`
- **Định nghĩa trên Card (`def_before`):** `connected with the scientific study of the normal functions of living things|connected with the way in which a particular living thing functions`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `biological`
- **Lý do sai lệch ngữ nghĩa:** biological (sinh học) quá rộng, làm mất tính đặc thù liên quan đến chức năng thể chất/cơ thể (sinh lý học) đối lập với tâm lý học (psychological).
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `of bodily functions`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `adjective`** (Tổng cộng 0 nghĩa có cùng mức CEFR `UNCLASSIFIED`):
    - *Được hiển thị trên Card (0):*

### 23. `pirate` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `(especially in the past) a person on a ship who attacks other ships at sea in order to steal from them|a person who makes illegal copies of books, computer programs, etc., in order to sell them|a person or an organization that broadcasts illegally`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `thief`
- **Lý do sai lệch ngữ nghĩa:** thief (kẻ trộm) quá chung chung, làm mất nghĩa đặc trưng của cướp biển (sea robber) hoặc kẻ vi phạm bản quyền/sao chép lậu.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `sea robber | copyright infringer`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 3 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "(especially in the past) a person on a ship who attacks other ships at sea in order to steal from them"
      - "a person who makes illegal copies of books, computer programs, etc., in order to sell them"
      - "a person or an organization that broadcasts illegally"

### 24. `portfolio` (noun) - CEFR: `C1`
- **Định nghĩa trên Card (`def_before`):** `a thin flat case used for carrying documents, drawings, etc.|a collection of photographs, drawings, etc. that you use as an example of your work, especially when applying for a job|a set of shares owned by a particular person or organization`
- **Giải nghĩa rút gọn hiện tại (`gloss_after`):** `case | collection`
- **Lý do sai lệch ngữ nghĩa:** case | collection (kẹp tài liệu/sưu tập) bỏ sót nghĩa tài chính/đầu tư cực kỳ quan trọng là danh mục đầu tư (investment portfolio). Nghĩa 'lĩnh vực của bộ trưởng' và 'danh mục sản phẩm công ty' bị lược bỏ.
- **Đề xuất sửa đổi (`Recommended replacement gloss`):** `document case | work samples | investment list`
- **Chi tiết Phân tích Từ loại (POS Level Analysis):**
  - **Từ loại `noun`** (Tổng cộng 5 nghĩa có cùng mức CEFR `C1`):
    - *Được hiển thị trên Card (3):*
      - "a thin flat case used for carrying documents, drawings, etc."
      - "a collection of photographs, drawings, etc. that you use as an example of your work, especially when applying for a job"
      - "a set of shares owned by a particular person or organization"
    - *Bị lược bỏ do Sense Cap (2):*
      - "the particular area of responsibility of a government minister"
      - "the range of products or services offered by a particular company or organization"
