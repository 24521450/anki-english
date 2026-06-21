# Tài Liệu Cấu Hình Mẫu Thẻ (Card Type Configuration) - EAVM

> **Xem trước**: [`../index.html`](../index.html) cho trang tổng quan design system (khuyến nghị bắt đầu ở đây).  
> **Tài liệu design cấp cao**: [`../README.md`](../README.md).

Thư mục này lưu trữ các tệp cấu hình thiết kế giao diện (mặt trước, mặt sau và kiểu dáng CSS) của loại thẻ **English Academic Vocabulary Model (EAVM)** trong bộ thẻ IELTS Anki.

Các tệp ở đây đã được sửa lỗi và phản ánh chính xác 100% thiết kế chuẩn hiển thị dạng thẻ hiện đại có tích hợp chips (cho Part of Speech, CEFR Level, Collocations) và phân tách đa định nghĩa.

## Danh sách tệp tin

1. **`front_template.txt`**: Mã nguồn HTML + JavaScript của **Mặt trước** thẻ.
2. **`back_template.txt`**: Mã nguồn HTML + JavaScript của **Mặt sau** thẻ.
3. **`styling.txt`**: Mã nguồn CSS quy định giao diện, màu sắc, font chữ và các hiệu ứng hiển thị (Chips, Badge, Definition Box,...).
4. **`README.md`**: Tệp tài liệu hướng dẫn này.

---

## Cơ chế hoạt động của Kịch bản Tự động hóa

Kịch bản đóng gói bộ thẻ [update_anki_deck.py](file:///c:/Users/admin/Downloads/ielts-deck/update_anki_deck.py) đã được cập nhật để đọc trực tiếp các tệp tin trong thư mục này mỗi khi chạy:
* `front_template.txt` -> Đưa vào làm `qfmt` (Question Format) cho Note Types.
* `back_template.txt` -> Đưa vào làm `afmt` (Answer Format) cho Note Types.
* `styling.txt` -> Đưa vào làm CSS Styling cho Note Types.

> [!TIP]
> **Mọi thay đổi design bắt đầu từ `../index.html` (vùng 2).** Các tệp `.txt` trong thư mục này derive từ đó. Sau khi sửa `index.html`, sync tương ứng vào `styling.txt` rồi chạy `python -m tools.check_design_sync` để verify.

---

## Hướng dẫn Tái sử dụng & Đồng bộ hóa thủ công trong Anki

Khi bạn nhập tệp `.apkg` mới, nếu Anki không tự động ghi đè giao diện cũ của loại thẻ `English Academic Vocabulary Model` (đây là cơ chế bảo vệ của Anki), bạn có thể áp dụng thủ công như sau:

1. **Mở cài đặt thẻ trong Anki**:
   * Nhấn tổ hợp phím **`Ctrl + Shift + N`** (hoặc vào menu **Tools** -> **Manage Note Types**).
   * Chọn loại thẻ **`English Academic Vocabulary Model`**.
   * Nhấn nút **Cards** ở menu bên phải để mở cửa sổ chỉnh sửa giao diện thẻ.
2. **Cập nhật Mặt trước (Front)**:
   * Mở tệp [front_template.txt](file:///c:/Users/admin/Downloads/ielts-deck/design/EAVM/front_template.txt).
   * Sao chép toàn bộ nội dung và dán đè vào ô **Front Template** trong Anki.
3. **Cập nhật Mặt sau (Back)**:
   * Mở tệp [back_template.txt](file:///c:/Users/admin/Downloads/ielts-deck/design/EAVM/back_template.txt).
   * Sao chép toàn bộ nội dung và dán đè vào ô **Back Template** trong Anki.
4. **Cập nhật Kiểu dáng (Styling CSS)**:
   * Mở tệp [styling.txt](file:///c:/Users/admin/Downloads/ielts-deck/design/EAVM/styling.txt).
   * Sao chép toàn bộ nội dung và dán đè vào ô **Styling** ở giữa cửa sổ Anki.

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
