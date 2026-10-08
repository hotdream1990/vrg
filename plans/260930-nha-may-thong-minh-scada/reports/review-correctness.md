# Review đúng/sai nghiệp vụ — Nhà máy thông minh (SCADA) · 30/09/2026

Tóm tắt từ code-reviewer (bản đầy đủ nằm trong phiên làm việc). Không có Critical.

## High
- H1 Múi giờ Historian không ghim (không wwTimeZone; GetDate() là giờ máy SCADA) → máy SCADA không ở UTC+7 thì mọi mốc ngày lệch không cờ. Xử lý: Kiểm tra kết nối đọc SYSDATETIMEOFFSET(), cảnh báo nếu offset ≠ +07:00 hoặc lệch đồng hồ > 5 phút.
- H2 Giả định bộ đếm chỉ tăng nhưng không kiểm trong ngày → đặt lại về 0 / đặt lại theo ca cho số sai không cờ. Xử lý: có lần giảm trong [open_at, close_at] → cờ reset, used null.

## Medium
- M1 Ngày cuối phụ thuộc Historian có trả dòng đúng mốc `<= end` → truy vấn tới end + 1h (code đã bỏ mẫu sau end).
- M2 Ghép 4 thanh ghi lệch nhịp đọc (R3 quay vòng mỗi 65,536 kWh) → ±65,536 kWh ở mốc ngày; phép kiểm H2 bắt được. Cần xem dữ liệu thật.
- M3 BQ/ngày + suất tiêu hao cộng cả ngày chưa trọn (in_progress/partial) → chỉ tính ngày flag None, thêm days_complete.

## Low
L1 đồng hồ lệch quanh nửa đêm · L2 hôm nay no_data dù đã có mẫu phút · L3 reset giả do dấu phẩy động · L4 latest_at không tròn phút · L5 số hôm nay/hôm qua có thể đổi khi hỏi lại · L6 định dạng ngày giờ phụ thuộc ngôn ngữ · L7 không chặn tag trùng · L8 nhà máy chưa khai tag → 502 · L9 date_from tương lai báo sai câu · L10 chú giải Excel, cột suất tiêu hao luôn hiện, check_connection dùng rows[-1].

## Câu hỏi cho nhà máy
1. Múi giờ + NTP máy SCADA. 2. Tag bành cộng dồn hay đặt lại theo ca/lô. 3. IO đọc 4 thanh ghi cùng khối? có tag kWh số thực? 4. Cyclic có trả dòng tại mốc đầu/cuối? 5. BQ/ngày tính ngày nào (nghiệp vụ).
