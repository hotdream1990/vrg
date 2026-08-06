# Thông báo cập nhật hệ thống — BẢN GỬI (06/08/2026)

> Hệ thống đã cập nhật xong (bản 0.4.3, chiều 06/08/2026). Copy nguyên phần trong khung, gửi kèm
> **file Word hướng dẫn đơn vị thành viên** đã cập nhật ảnh mới. Phần ghi chú nội bộ ở cuối KHÔNG gửi.

---

Kính gửi các anh chị phụ trách công tác báo cáo trên price.vrg.vn của các Công ty,

Ban Thị trường kinh doanh kính báo các anh chị như sau:

**1. Hệ thống có thêm bảng nhắc việc, hiện ngay khi các anh chị đăng nhập.**

+ Bảng nằm ở đầu màn hình, cho biết đơn vị mình **còn thiếu số liệu ngày nào, biểu nào** — không
  phải tự mở từng biểu ra dò.
+ **Bấm thẳng vào ngày màu cam** là mở luôn phiếu nhập của đúng ngày đó.
+ Ngày **màu xám** là đã quá hạn sửa, đơn vị không tự nhập được nữa — trường hợp này đề nghị báo
  Ban Thị trường kinh doanh để hỗ trợ nhập bổ sung.
+ Nhập xong bảng tự trừ việc đó ngay. Khi không còn thiếu gì, bảng chuyển thành dòng xanh
  **"Đã nhập đủ"**.
+ Bảng rà lại **14 ngày gần nhất**.

**2. Đề nghị các đơn vị rà soát và bổ sung số liệu trong tuần này.**

+ Qua rà soát, phần lớn các đơn vị còn thiếu số liệu **biểu Tồn kho** của nhiều ngày trong 2 tuần
  qua. Đề nghị các anh chị mở hệ thống, xem bảng nhắc và bổ sung cho đủ.
+ Ngày nào đơn vị **không phát sinh** thì vẫn phải vào phiếu và tích ô *"Hôm nay không phát sinh
  tồn kho để khai"* (biểu Thu mua có ô *"Hôm nay đơn vị KHÔNG tổ chức thu mua"*). Tích như vậy
  được tính là **đã nộp**, hệ thống không nhắc nữa. Bỏ trống thì vẫn tính là thiếu.

**3. Kế hoạch năm 2026 — đơn vị nào chưa khai, đề nghị bổ sung.**

+ Bảng nhắc có dòng *"Kế hoạch năm 2026 — chưa khai"* nếu đơn vị chưa có số kế hoạch của năm nay.
+ Đơn vị nào thấy dòng này mà **không mở được màn Kế hoạch năm**, đề nghị báo lại Ban Thị trường
  kinh doanh, chúng tôi sẽ nhập hỗ trợ số kế hoạch đầu tiên.

**4. Màn Khách hàng đổi cách nhập.**

+ Trang Khách hàng nay chỉ còn nút **"Thêm khách hàng"**; bấm vào mới hiện ô nhập trong một cửa sổ
  riêng. Nút **Sửa** ở mỗi dòng cũng mở cửa sổ đó.
+ Các quy tắc không đổi: khách hàng thuộc riêng từng đơn vị, không trùng tên trong cùng một đơn vị,
  khách đã gắn hợp đồng chỉ ẩn được chứ không xoá.

**5. Vào lại hệ thống nhớ bấm Ctrl + Shift + R** (máy Mac: Cmd + Shift + R) để lấy bản mới.

**6. Tài liệu hướng dẫn đã cập nhật theo giao diện mới, gửi kèm thông báo này.**

Trân trọng cảm ơn các anh chị đã đọc và phối hợp!

---

## Ghi chú nội bộ (KHÔNG gửi kèm)

**Số đo trên production lúc phát hành (06/08/2026):**

| Chỉ tiêu | Số liệu |
|---|---|
| Đơn vị có tài khoản | 66 |
| Trung bình thiếu (biểu Tồn kho, 14 ngày) | 7,3 ngày |
| Nhập đủ cả 14 ngày | 2 đơn vị |
| Chưa nhập ngày nào | 19 đơn vị |
| Chưa khai Kế hoạch năm 2026 | 31 đơn vị |
| Đợt giao treo quá 7 ngày | 0 |

- **Mục 2 và 3 cố ý KHÔNG gọi đích danh đơn vị nào** — để các đơn vị tự rà, giống cách xử ở thông
  báo 04/08. Nếu cần đốc thúc riêng, dùng skill `bao-cao-nhap-lieu` xuất ảnh bảng theo đơn vị.
- **Mục 3 là việc của Ban TTKD**: 31 đơn vị chưa khai kế hoạch 2026 thì *không tự khai được* —
  chính con số kế hoạch là công tắc mở màn đó (vòng luẩn quẩn có sẵn từ trước). Ban TTKD (tài khoản
  chuyên viên có quyền `unit_daily`) phải nhập hộ số đầu tiên, sau đó đơn vị tự sửa được.
- **Số ngày rà (14) chỉnh được**: Quản trị → Cấu hình hệ thống → tab *Cửa sổ nhập liệu* → ô
  "Cảnh báo thiếu số liệu — rà bao nhiêu ngày gần nhất". Đặt **0 = tắt hẳn cảnh báo**. Nếu 14 ngày
  làm các đơn vị thấy quá nhiều việc cùng lúc, hạ xuống 7 rồi nâng dần.
- **Đang nhắc cả ngày hôm nay** ngay từ đầu giờ sáng. Chờ phản hồi của các đơn vị; nếu thấy gắt thì
  đổi thành chỉ nhắc từ hôm qua trở về trước.
- File đính kèm: `docs/huong-dan/nhap-lieu-don-vi-thanh-vien/Huong-dan-nhap-lieu-don-vi-thanh-vien.docx`.
  Hướng dẫn quản trị (`Huong-dan-quan-tri-he-thong.docx`) cũng đã cập nhật ô cấu hình mới ở mục 10
  — gửi riêng cho Ban TTKD / quản trị viên, không gửi các đơn vị.
