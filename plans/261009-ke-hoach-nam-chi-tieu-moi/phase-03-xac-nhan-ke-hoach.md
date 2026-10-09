# Giai đoạn 3 — Đơn vị xác nhận kế hoạch

Trạng thái: **chưa làm** (chờ Giai đoạn 2 và Q7 ở [plan.md](plan.md)).

## Mục tiêu
Sau khi Ban nạp, đơn vị vào xem, thấy đúng thì **xác nhận**; thấy sai thì gửi đề nghị điều chỉnh. Kế hoạch đã xác nhận mới là mốc chính thức để so thực hiện.

## Hiện trạng
- Chưa có thao tác "xác nhận kế hoạch" riêng. Kế hoạch chỉ bị khoá gián tiếp khi đơn vị bấm "Chốt số liệu" một đợt trong năm
  (65/67 đơn vị đã chốt); muốn sửa phải gửi đề nghị. Tài khoản Ban vẫn ghi đè được.
- Đã có luồng đề nghị sửa số liệu quá khứ, có thao tác `year_plan` (0.4.108).

## Đã có sẵn từ Giai đoạn 1
Kế hoạch năm đã nằm trong bảng «Xác nhận chốt số liệu» (xem phase-01, mục «Bảng xác nhận chốt số liệu»): đơn vị thấy đủ 23 chỉ tiêu trước khi chốt.
Nút «Xác nhận kế hoạch» riêng ở dưới là việc thêm, chỉ làm nếu chủ dự án vẫn muốn tách khỏi chốt số liệu.

## Việc cần làm (đề xuất, chờ Q7)
- [ ] Nút **"Xác nhận kế hoạch"** trên màn Kế hoạch năm của đơn vị; lưu thời điểm + người xác nhận.
- [ ] Thấy sai: gửi **đề nghị điều chỉnh** qua luồng đề nghị sẵn có, Ban duyệt.
- [ ] Checklist đơn vị thêm mục "chưa xác nhận KH 2026".
- [ ] Màn Ban có cột trạng thái xác nhận từng đơn vị.
- [ ] Thông báo qua Hỗ trợ & Thông báo (email + chuông, đã có sẵn).
- [ ] Ban nạp lại số mới thì xác nhận cũ tự huỷ, đơn vị phải xác nhận lại.
- [ ] Chốt luật % thực hiện: tính trên mọi KH đã nạp hay chỉ đơn vị đã xác nhận.
