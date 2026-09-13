# Snapshot cơ chế tạo Báo cáo tuần — PHIÊN BẢN 1 (trước cập nhật 13/09/2026)

- **Tag git:** `snapshot/weekly-report-v1-20260913` (trỏ commit `44476a7`, bản 0.4.63). Khôi phục code cũ: `git checkout snapshot/weekly-report-v1-20260913 -- <đường dẫn>`.
- **Tài liệu logic áp dụng:** `docs/bieu-mau-bo-sung/huong-dan-bao-cao-tuan/Logic viết Bản tin tuần.docx` (bản cũ) + mẫu PDF tuần 26.
- **Bằng chứng đầu ra v1:** `Bao-cao-tuan-34-2026-v1.pdf` + `tuan-34-build-report-v1.json` (cùng thư mục).

## 1. Luồng
1. Chuyên viên chọn một ngày → hệ thống quy về **1 tuần** (khoá = Thứ 2 ISO). Không gộp được nhiều tuần.
2. Bảng số liệu tự tính mỗi lần mở (không lưu):
   - III.1 sàn quốc tế: OSE RSS3 · SHANGHAI RSS3 · SGX RSS3/TSR20 · MRE SMR CV/SMR20/LATEX — **trung bình tuần USD/tấn** từ `price_sheet.build_sheet` (quy đổi như bản tin ngày). Cột: tuần trước · tuần này · +/- (kế toán, âm trong ngoặc) · %.
   - III.2 giao ngay: RSS3/STR20/SMR20/LATEX từ nguồn `reuters` — TB tuần.
   - III.3 mủ nước: biên độ min–max giá `vrg` (đ/độ TSC), loại đơn vị lệch ±15% trung vị; **sửa tay được** (lưu đè).
   - Cao/thấp nhất tuần: chỉ **USD/tấn** + ngày (không có giá nội tệ JPY/kg, CNY/tấn, US cent/kg).
3. Phần viết (I, II, nhận định III.1–3, IV.1–4, V, VI) lưu jsonb bảng `weekly_report`; tự lưu 0,9 giây.
4. AI (OpenAI qua `llm.complete`): nút từng phần + "AI hỗ trợ toàn bộ" (1 lượt). Ngữ cảnh = bảng số + đỉnh/đáy + tỷ giá TB tuần (JPY/CNY/MYR) + **đúng 1 bài vietnambiz mới nhất** (không theo ngày tuần báo cáo).
5. Xuất PDF (Chromium): bìa collage · header chữ xanh · masthead · I–VI · Lời cảm ơn · Khuyến cáo · bìa sau.

## 2. Khung nội dung v1
| Phần | Nội dung v1 |
|---|---|
| I | Tóm tắt tuần trước (1 đoạn) |
| II | Diễn biến tuần (2 đoạn) |
| III.1 | "Sàn X (±%): nhận định" + gạch phụ Cao/Thấp nhất tuần (USD) — góc SGX/MRE = găng tay & chi phí Malaysia |
| III.2 | 1 đoạn giao ngay |
| III.3 | Bảng + 1 đoạn mủ nước |
| IV | 1. Năng lượng & Butadien · 2. Cung–Cầu · 3. Tỷ giá & TC Nhật Bản · 4. Kinh tế TQ & khác (tiêu đề cố định trong code) |
| V | "Xu hướng chủ đạo" / "Tiêu điểm quan sát" |
| VI | 1 đoạn khuyến nghị |

## 3. Nguồn dữ liệu v1
- Có tự động: giá sàn, giao ngay (reuters), mủ nước, tỷ giá JPY/CNY/MYR, 1 bài vietnambiz.
- **Không có:** DXY, WTI, Brent; USD/THB trong ngữ cảnh AI; báo cáo ANRPC; tin EUDR/SBV/CafeF; danh mục nguồn tham khảo; file đính kèm.
- Nguồn cố định trong code — không cấu hình được.

## 4. Giới hạn đã biết của v1
- Không gộp 2 tuần (tuần lễ Quốc khánh 35–36 phải làm tay ngoài hệ thống).
- Không có ghi chú "sàn không có giá ngày …" dưới bảng.
- AI không có quy tắc tránh từ tuyệt đối ("hoàn toàn", "chắc chắn"…); văn phong còn khuyến khích từ mạnh.
- Không kiểm tra số AI viết có nằm trong dữ liệu hay không (chỉ dặn trong prompt).
- Tài liệu vĩ mô (ANRPC) phải đọc tay; AI không đọc được.

## 5. File code v1
`apps/api/app/services/weekly_report_service.py` (364 dòng) · `weekly_ai.py` (226) · `routers/weekly_reports.py` · `schemas/weekly_report.py` · `services/weekly_report/weekly/{models,html_template,pdf_export}.py` · web `features/command-center/pages/WeeklyReportPage.tsx` + `components/WeeklyTables.tsx` + `lib/weekly-report-client.ts`.
