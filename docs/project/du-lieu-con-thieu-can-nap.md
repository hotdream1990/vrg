# Dữ liệu còn thiếu cần nạp

> Cập nhật: 29/06/2026 · VRG AI Dự báo Giá Cao su (PoC — Đề án A)
>
> **Bối cảnh:** backfill từ Excel liền mạch đến **29/12/2025**; dữ liệu **2026 mới có một phần** (crawler live mỗi sàn bắt đầu ở thời điểm khác nhau) → còn **lỗ đầu–giữa 2026** ở nhiều series. Phạm vi cần: **từ 2024** (không cần ≤ 2023).

## 1. Ưu tiên cao — nuôi mô hình Gợi ý giá sàn

| Dữ liệu | Khoảng còn thiếu | Nguồn cần xin | Cách nạp |
|---|---|---|---|
| ★ **Giá sàn VRG** (target) | ✅ **ĐÃ NẠP 79 lần** (29/06/2026) — lấp T1–T5/2026 + gap 2024–2025; chỉ còn trống **01/10→19/11/2025** | Anh Tâm — file *Giá sàn 2024-2026.xlsx* | Đã có `import_floor_table.py` + file ở `docs/bieu-mau/` (chạy lại 1 lệnh khi cập nhật) |
| Tồn kho (tuần) | Đủ từ 2025 — chỉ cần **bổ sung tuần mới** đều đặn | Chị Hạnh — báo cáo tuần | Trang *Tồn kho* |

## 2. Giá thị trường — lỗ đầu/giữa 2026

| Sàn / loại | Khoảng còn thiếu | Ghi chú |
|---|---|---|
| Settlement SGX | T1–T5/2026 | chưa có nguồn live |
| Physical Malaysia (LGM) | T1–T5/2026 | |
| Settlement TOCOM/OSE | T1–T4/2026 | |
| Physical (Reuters) | T1–T4/2026 | marketscreener không tra bài cũ |
| Settlement SHFE | ~T1/2026 | nhỏ |
| Tỷ giá — JPY/CNY/MYR | ~T1/2026 | nhỏ |
| ★ Giá mủ nước (thu mua + theo KV) | **10/02 → 06/05/2026** (nửa cuối T2 + T3–T4); lặp lại ~**T2(cuối)–T4/2025** | File nguồn thiếu cột ngày — **không có crawler live**, chỉ lấp được bằng Excel |

→ **Lấp bằng:** file Excel cập nhật có dữ liệu đầu–giữa 2026 (Anh Tâm) **hoặc** để crawler live tự tích lũy tiếp theo thời gian.

> **Giá mủ nước chỉ đến từ file `docs/bieu-mau/Tâm/Mẫu file lấy giá các sàn, giá mủ nước...xlsx`** (2 sheet `GIÁ THU MUA MỦ NC` + `GIÁ MỦ NC THEO KV`, nạp qua `import_latex.py`) — **không có nguồn crawler thay thế**. Cả 2 sheet hiện nhảy thẳng từ 09/02/2026 sang 07/05/2026 (và 2025 cũng hổng Tết→T5 y hệt). Cần Anh Tâm điền bổ sung cột ngày rồi chạy lại `import_latex.py`.

> **Tỷ giá USD/THB & USD/VND — KHÔNG có lịch sử (không phải import sót).** Nguồn Excel chỉ có 3 cặp JPY/CNY/MYR; THB/VND chỉ mới được crawler live thu (THB từ 16/02/2026, VND từ 15/06/2026). Lịch sử 2 cặp này không tồn tại trong nguồn. **Ưu tiên thấp** — physical đã lưu sẵn USD, giá sàn đã lưu sẵn VNĐ nên ít cần quy đổi ngược; nếu muốn đủ thì xin Anh Tâm bổ sung cột THB/VND hoặc lấy từ nguồn tỷ giá công khai.

## 3. Chưa có bảng — chờ nguồn

| Dữ liệu | Trạng thái | Nguồn |
|---|---|---|
| Vĩ mô (dầu / USD Index / PMI) | chưa nạp | Bizino tự crawl (nguồn công khai) |
| Tiêu thụ (BCTM) | chưa có bảng | VRG cung cấp |
