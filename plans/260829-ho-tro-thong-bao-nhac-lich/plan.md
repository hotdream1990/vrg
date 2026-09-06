# Hỗ trợ · Thông báo · Nhắc lịch (VRG)

Ngày chốt yêu cầu: **29/08/2026**

## Yêu cầu gốc (chủ dự án)
- Hỗ trợ / support ticket giữa **đơn vị thành viên ↔ Tổng công ty**, **chỉ dành cho lãnh đạo đơn vị**.
- **Lãnh đạo đơn vị** = vai trò MỚI, phải gán vào đơn vị thành viên.
- Đơn vị gửi lên Tổng công ty; Tổng công ty gửi xuống **1 đơn vị · một nhóm · tất cả**.
- Mỗi tin: nội dung · file đính kèm · hình ảnh · **phản hồi**.
- ⚠ Gửi nhóm nhưng **các đơn vị KHÔNG thấy tin và phản hồi của nhau**.
- Gửi tin thì **gửi kèm email** (có tiêu đề) dẫn đơn vị vào xem trên trang.
- Thêm **nhắc lịch**.

## Chốt thiết kế
1. **Cách ly tuyệt đối bằng dữ liệu, không bằng giao diện**: mỗi luồng (`support_thread`)
   thuộc về ĐÚNG MỘT đơn vị. Gửi cho N đơn vị = tạo N luồng cùng `batch_id`. Phản hồi
   nằm trong luồng nên không có đường nào để đơn vị A đọc được của đơn vị B.
2. **Vai trò `leader`** ("Lãnh đạo đơn vị thành viên"): dùng lại cột `member_units`,
   chỉ mở màn Hỗ trợ + Hồ sơ. Tài khoản `member` (nhập liệu) KHÔNG vào màn này.
3. **Quyền `support`** (2 cấp Xem/Sửa) cho phía Tập đoàn (admin mặc định đủ quyền).
4. **Email**: SMTP khai ở trang Cấu hình hệ thống (tab Email). Không cấu hình = tính năng
   vẫn chạy, chỉ không gửi mail (ghi log), tuyệt đối không làm hỏng luồng gửi tin.
5. **Nhắc lịch**: bản ghi `support_reminder` có `next_at`; job nội bộ 5 phút/lần phát
   thông báo tới các đơn vị đã chọn (đúng đường thông báo ở trên) rồi dời `next_at`.

## Bảng dữ liệu
- `support_thread` — luồng (1 đơn vị · kind request|announce|reminder · trạng thái · mốc đã đọc 2 bên)
- `support_message` — từng tin trong luồng (side hq|unit · nội dung · file)
- `support_reminder` — lịch nhắc (phạm vi · chu kỳ · `next_at`)
- `app_user.email` — địa chỉ nhận thông báo (trống thì lấy username nếu là email)

## Bổ sung 29/08 (yêu cầu sau khi review)
Lãnh đạo đơn vị **xem được số liệu của đơn vị mình** (chỉ xem):
- Dependency chung `get_unit_user` cho `/api/member/*` — chặn ghi theo **method HTTP** tại một chỗ
  duy nhất; `cap_or_member_scope` chặn lãnh đạo ở mức Sửa (màn hợp đồng dùng chung).
- Web: 2 cờ `isUnitAccount` (chọn endpoint) và `canEditUnitData` (bật/tắt sửa) thay cho việc rải
  `role === "member"` khắp các màn.
- ⚠ Bịt lỗ cũ: `/api/series/*` chỉ gác đăng nhập → tài khoản đơn vị đọc được số của đơn vị khác.

## Việc đã làm
- [x] Schema + migration idempotent
- [x] Kho file đính kèm dùng chung (`attachment_store`) — tách từ `contract_files`
- [x] Vai trò `leader` + quyền `support`
- [x] Repo/route/schema Hỗ trợ · Thông báo · Nhắc lịch
- [x] Gửi email (SMTP cấu hình trên UI) + nút gửi thử
- [x] Web: hộp thư · chi tiết luồng · soạn thông báo · lịch nhắc · menu · phân quyền
- [x] Test backend (9 test hộp thư + 6 test lãnh đạo chỉ-xem, gồm test cách ly chéo đơn vị)
- [x] Chạy thử thật trên trình duyệt (lãnh đạo A · lãnh đạo B · Tập đoàn)

## Hậu triển khai (BẮT BUỘC)
1. Thêm volume `support-files:/app/data/support-files` ở **3 nơi** (repo · compose trên đĩa · DB Dokploy)
   — thiếu là mất file đính kèm khi deploy lại.
2. Admin khai tab **Email** ở Cấu hình hệ thống + `APP_BASE_URL`, bấm **Gửi thử**.
3. Cấp quyền `support` cho chuyên viên phụ trách; tạo tài khoản `leader` cho từng đơn vị (có email).
