# Review độ đúng — chuông, Web Push, loại nhập liệu, người nhận thẻ (01/10/2026)

Nguồn: agent code-reviewer (không ghi được file nên agent chính lưu lại). Kiểm: `tsc -b` sạch;
`test_web_push` + `test_support` + `test_support_audience` 35 passed khi chạy riêng (lần đầu lỗi do
chạy chung DB dev với lượt pytest khác — trùng tài khoản fixture).

## Đã kiểm — đúng
Mã hoá RFC 8291 + VAPID (aud/exp/k=) · payload ≤ 3000 byte · race sinh khoá · đổi khoá thì huỷ rồi
đăng ký lại · requestPermission trong click · effect dọn listener · SQL chưa đọc (PK support_read) ·
backfill 1 lần · mặc định thẻ cũ/tài khoản cũ · route không vòng lặp · Kế hoạch năm lọc ô.

## Medium
1. Bấm thông báo chỉ focus tab, không mở thẻ khi tab đang ở `/login`/đang tải (`sw.js`) → ack qua
   MessageChannel, không ack thì `client.navigate(url)`.
2. Phản hồi thứ hai cùng thẻ thay thông báo im lặng (cùng `tag`, thiếu `renotify`).
3. Máy dùng chung: chỉ đăng xuất từ menu mới gỡ push; bị đá 401 hoặc người sau không có chuông thì
   vẫn nhận thông báo của người trước.

## Low
4. Mỗi đơn vị một luồng + một httpx.Client khi gửi "tất cả đơn vị" (~80 luồng) → gộp một luồng nền.
5. Push 403 (VAPID lệch sau khi đổi khoá) không bị xoá — khoá không bao giờ đổi trong thiết kế, bỏ qua.
6. Không có `pushsubscriptionchange` — SW không có token; mở app là tự đăng ký lại, bỏ qua.
7. CV Thu mua của đơn vị không có KH thu mua về `/ho-tro` — nên về Kế hoạch năm.
8. HQ poll `/api/support/unread` 60 s quét cả bảng — nhỏ, chưa cần index.

## Câu hỏi
- Đơn vị phản hồi/gửi yêu cầu chỉ báo Tập đoàn, không báo lãnh đạo/đồng nghiệp cùng thẻ (giữ như cũ).
- Nút tắt push lưu theo trình duyệt, không theo tài khoản → sửa thành theo tài khoản.
