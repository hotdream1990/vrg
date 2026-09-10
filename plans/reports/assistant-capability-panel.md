# Bảng "Trợ lý làm được gì?" — báo cáo

## Mục đích
Chủ dự án yêu cầu người dùng mở được một bảng cho biết Trợ lý đang chạm tới nhóm dữ liệu nào,
**làm được gì và chưa làm được gì** — để không kỳ vọng nhầm rồi tưởng hệ thống trả lời sai.

## Backend
- `assistant_tools.pack_summary()` trả thêm `cap` (quyền cần có) và `items[{name, label, desc}]`
  cho **mọi gói**, kể cả gói tài khoản không đủ quyền — người dùng biết là CÓ tính năng đó.
- `desc` = câu đầu của mô tả công cụ (mô tả gốc viết cho mô hình nên dài, cắt ở 200 ký tự).
- `TOOL_LABELS` (24 mục) đặt **ở server**, cạnh registry: đổi tên hay thêm công cụ chỉ sửa một nơi,
  không trôi giữa backend và frontend. Test `test_tool_labels_cover_every_tool` khoá điều này.
- `assistant_tools.LIMITS` — 6 việc Trợ lý **chưa làm được**, trả kèm trong `GET /api/assistant/packs`.
  ⚠ Mở thêm khả năng mới thì phải cắt bớt danh sách này, không thì bảng nói sai.

## Frontend
- Nút "Trợ lý làm được gì?" cạnh nút "Nâng cao", mở `Drawer` 560px (chọn Drawer thay Modal vì nội
  dung dài 2–3 màn và vẫn thấy khung chat bên trái).
- Hai phần: **"Trợ lý tra cứu được"** (mỗi gói một thẻ, liệt kê công cụ theo nhãn tiếng Việt) và
  **"Chưa làm được"** (từ `limits`, icon cảnh báo màu dịu).
- Bốn trạng thái gói, mỗi cái một lý do rõ: *Luôn bật* (gói nền) · *Đang bật* · *Đã tắt trong phiên
  này* (kèm nhắc bật lại ở Nâng cao) · *Cần quyền "…"* (hiện tên màn hình, mã quyền để ở tooltip).
- `/packs` lỗi → nút vẫn hiện, mở ra báo "chưa lấy được danh sách khả năng"; khung chat không vỡ.
- Nhãn công cụ lấy từ `item.label` của server, chỉ tự rút gọn `desc` khi server chưa đặt nhãn —
  không bao giờ hiện tên hàm kiểu `get_exchange_prices` cho người dùng nghiệp vụ.

## Kiểm tra
`tsc --noEmit` và `pnpm build` sạch. Test backend phủ: `limits` khác rỗng, số `items` khớp số công
cụ mỗi gói, gói `unit` khai đúng `cap = unit_daily`, và mọi công cụ đều có nhãn.

## Còn lại
Chưa soi bằng mắt trên trình duyệt (trạng thái "Cần quyền" cần tài khoản không có `unit_daily`/
`sales_contract`). Đáng kiểm tra sau khi deploy: hàng nút xuống dòng ở màn hình hẹp.
