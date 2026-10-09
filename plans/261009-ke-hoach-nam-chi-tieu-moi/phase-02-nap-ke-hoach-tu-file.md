# Giai đoạn 2 — Ban nạp kế hoạch từ file Excel

Trạng thái: **chưa làm** (chờ Giai đoạn 1 xong và Q1, Q3, Q5, Q6 ở [plan.md](plan.md)).

## Mục tiêu
Tài khoản Ban nạp tab 1 của file Kế hoạch (72 công ty) vào các ô Kế hoạch năm của từng đơn vị, một lần, ghi nhật ký hoạt động.
Là cách "chuẩn hoá một nguồn" chủ dự án muốn: đơn vị khỏi tự nhập, số khỏi lệch nhau.

## Việc cần làm
- [ ] Công cụ nạp: nhận file → **xem trước** (mỗi công ty: số cũ ↔ số mới, ô nào đổi) → bấm xác nhận mới ghi. Ghi đè.
- [ ] Bảng khớp tên công ty ↔ đơn vị phần mềm: 60/72 đã khớp (Phụ lục A của `../reports/261007-phan-hoi-dat-ke-hoach-va-dashboard-doanh-thu.md`). Cần anh Đạt duyệt nhanh.
- [ ] Bỏ 9 dòng toàn số 0 (Phước Hoà Đắk Lắk 02TV và 8 công ty "(VN)" ở Campuchia).
- [ ] 3 dòng có số nhưng phần mềm chưa có đơn vị (Quanvan · CP Quasa Geruco (VN) · CP Cao su Việt Lào (VN)): báo, không ghi (Q6).
- [ ] 3 đơn vị trên phần mềm không có trong file (Hàng Gòn · Viện NC Cao su · Dầu Tiếng Việt Lào): giữ số đơn vị đã nhập.
- [ ] Sáp nhập: file gộp 7 cặp, phần mềm có 4 cặp (Bình Long→Lộc Ninh, Chư Păh→Chư Prông, Krông Buk→Eah Leo, Mang Yang→Chư Sê).
  Số gộp ghi vào đơn vị nhận; **xoá KH 2026 riêng** của Bình Long (3.000 t), Chư Păh (200 t), Krông Buk (500 t) để không đếm hai lần.
- [ ] Áp quy tắc ánh xạ ở [phase-00](phase-00-bang-chi-tieu-final.md): nhượng quyền cộng vào khai thác, tách hàng hóa (ước tính), doanh thu ÷ 1.000.
- [ ] Kiểm tổng trước khi ghi: H = I + J, K = L + N, O = P + R, S = T + W (chênh quá 0,5 thì báo, không ghi).
- [ ] Chỉ ghi đè các ô có trong file; ô tồn kho thành phẩm và nhóm Hợp đồng **không đụng** (file không có).
- [ ] Ghi nhật ký hoạt động (audit log) từng đơn vị đổi gì.

## Số cần biết khi xem trước (đo trên bản sao prod 06/10)
- Đơn vị đã nhập: khai thác 9/60 (7 khớp, 2 lệch) · thu mua 49 khớp, 11 lệch · hàng hóa chỉ 1 đơn vị · doanh thu 18 khớp, 8 lệch, 34 chưa nhập.
- 4 đơn vị đang nhập thu mua gồm cả thành phẩm (Lộc Ninh + Bình Long 11.500 · Phước Hòa 14.500 · Hà Tĩnh 1.650 · Hòa Bình 1.500): nạp sẽ ghi đè về nguyên liệu.
- KH khai thác đổi từ cột F sang E nên 4 công ty có nhượng quyền tăng số.

## Rủi ro
- 65/67 đơn vị đã "Chốt số liệu" nên kế hoạch đang khoá với đơn vị; tài khoản Ban vẫn ghi đè được. Kiểm trước khi nạp có làm vỡ bản chốt/ảnh chụp tuần nào không.
