# Chuông thông báo + Web Push · Loại nhập liệu đơn vị · Người nhận thẻ hỗ trợ (01/10/2026)

## Yêu cầu (chủ dự án)
1. Chuông thông báo cho đơn vị và Tập đoàn, báo được qua notify của trình duyệt.
2. Tài khoản nhập liệu đơn vị chia 3 loại (chọn nhiều): Thu mua · Tồn kho · Hợp đồng & tiêu thụ.
3. Hỗ trợ & Thông báo chọn được người nhận: lãnh đạo đơn vị và/hoặc chuyên viên theo loại (chọn nhiều).

## Đã chốt (01/10/2026)
- Notify = **Web Push** (báo cả khi đã đóng trang; iPhone cần "Thêm vào màn hình chính").
- Lãnh đạo đơn vị **chỉ thấy thẻ khi được chọn** (phân luồng chặt).
- Chuyên viên đơn vị **được tự mở yêu cầu** gửi Tập đoàn; người nhận = lãnh đạo + loại của người gửi.
- Chốt số liệu: **mọi tài khoản nhập liệu của đơn vị** (giữ như cũ).

## Mặc định (không cần hỏi)
- Tài khoản member hiện có = đủ 3 loại (cột mặc định) → không ai mất quyền.
- Thẻ/lịch nhắc cũ + cảnh báo tự động = gửi lãnh đạo (như trước).
- Server chặn GHI ngoài loại; đọc số liệu chính đơn vị mình không chặn; web ẩn màn ngoài loại.
- Nhu cầu thị trường → Hợp đồng & tiêu thụ. Kế hoạch năm: `plan_tonnes` → Thu mua, các ô còn
  lại → Hợp đồng & tiêu thụ (ô ngoài loại giữ nguyên giá trị đã lưu, như mẫu Báo giá).
- "Đã đọc" phía đơn vị tính theo TỪNG NGƯỜI (`support_read`); phía Tập đoàn giữ hộp thư chung.

## Nền đã làm (agent chính)
- `core/db.py`: `app_user.entry_types`, `support_thread.audience`, `support_reminder.audience`,
  `support_read` (+ chép mốc đọc cũ cho lãnh đạo, 1 lần), `push_subscription`.
- `core/entry_types.py` + `web/src/lib/entry-types.ts` (danh mục, `assert_entry_type`, `user_audiences`).
- `core/security.py`: `cap_or_member_scope("sales_contract", LEVEL_EDIT)` đòi loại `contract`.
- `services/web_push.py`: khung `send_async(usernames, title, body, url, tag)`.

## Các nhánh song song (file không giao nhau)
| Nhánh | Phạm vi | Trạng thái |
|---|---|---|
| A | BE loại nhập liệu: user_repo · schemas/auth · auth/users router · member_self · edit_request_ops · member_checklist + test | ✅ |
| B | BE người nhận thẻ: support_* · schemas/support · edit_request_notify + test | ✅ |
| C | Web Push + chuông: web_push · routers/push · main · web_static · sw.js · manifest · NotificationBell · AdminLayout + test RFC 8291 | ✅ |
| D | Web: quản trị người dùng · AuthContext · menu · route · Kế hoạch năm · soạn thẻ/lịch nhắc chọn người nhận | ✅ |

## Kết quả (01/10/2026)
- 2 vòng review song song (phân quyền · độ đúng) → `plans/reports/261001-review-*.md`; đã sửa 1 Medium
  phân quyền (CV Tồn kho ghi được ô tiêu thụ cũ → giữ số đã lưu) + 3 Medium web push + các Low.
- Test API trên DB sạch `vrg_test_261001`; tsc + build web sạch; kiểm giao diện trên DB dev với 3
  tài khoản thử (đã xoá).
- CHƯA làm: thử push trên Chrome/iPhone thật (trình duyệt nhúng chặn Notification); sổ tay người dùng.
- Chưa deploy, chưa commit (chờ chủ dự án). Hậu deploy: cấp lại loại nhập liệu cho từng tài khoản
  nếu đơn vị chia người; báo đơn vị bấm "Nhận thông báo trên máy này".
