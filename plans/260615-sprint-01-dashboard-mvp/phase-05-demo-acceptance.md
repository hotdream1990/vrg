# Phase 05 — Demo & Nghiệm thu Sprint 1

## Context Links
- [plan.md](plan.md) · [development-roadmap.md](../../docs/project/development-roadmap.md) · [data-checklist.md](../../docs/project/data-checklist.md)
- Phụ thuộc: [phase-01](phase-01-infra-database.md) · [phase-02](phase-02-crawlers-exchanges-macro.md) · [phase-03](phase-03-etl-historical-load.md) · [phase-04](phase-04-dashboard-mvp-react.md)

## Overview
- **Priority**: P1
- **Status**: ⚪ pending
- **Mô tả**: Đóng gói thành quả Sprint 1, chuẩn bị môi trường demo end-to-end, trình diễn với VRG, thu phản hồi và lấy nghiệm thu. Bàn giao theo roadmap: **Dashboard 4 sàn + dữ liệu lịch sử ~2 năm + kết nối BCTM**.

## Key Insights
- Demo phải chạy **end-to-end thật** (crawler → ETL → DB → Dashboard), không mock — chứng minh đường ống dữ liệu hoạt động.
- Nghiệm thu = đối chiếu với **bàn giao trong roadmap**, không phải "đẹp UI". Trọng tâm: độ phủ dữ liệu + tính Premium/Discount + tính ổn định crawler.
- Chuẩn bị sẵn câu trả lời cho 4 câu hỏi mở (giá VRG, AFET, mốc lịch sử 2 vs 3 năm, mức real-time).

## Requirements
**Chức năng**
- Kịch bản demo (script) chạy theo luồng: trigger crawl T-1 → ETL → mở Dashboard → giải thích Premium/Discount → xem lịch sử.
- Checklist nghiệm thu ánh xạ 1-1 với bàn giao roadmap + tiêu chí từng phase.
- Tài liệu vận hành tối thiểu (cách chạy compose, chạy DAG, chạy backfill) — đặt trong plan/handover, KHÔNG sửa repo docs.

**Phi chức năng**
- Môi trường demo ổn định (seed sẵn dữ liệu lịch sử + 1 lần crawl tươi).
- Có phương án dự phòng nếu site sàn lỗi đúng lúc demo (dùng dữ liệu đã nạp).

## Architecture
```
Luồng demo (end-to-end):
  run_crawl(T-1) ─► pipelines.ingest_daily ─► TimescaleDB ─► apps/api ─► apps/web (Dashboard)
                                              ▲
                              backfill_history (đã nạp ~2 năm trước demo)
Artifacts nghiệm thu:
  - reconciliation report (độ phủ lịch sử)  [từ Phase 03]
  - demo script + checklist nghiệm thu      [phase này]
  - biên bản phản hồi VRG                    [phase này]
```

## Related Code Files
> Phase này **không thêm code sản phẩm**; chỉ tài liệu/kịch bản trong `plans/`.

**Tạo (trong plans/)**
- `plans/260615-sprint-01-dashboard-mvp/reports/demo-script.md` (kịch bản demo từng bước)
- `plans/260615-sprint-01-dashboard-mvp/reports/acceptance-checklist.md` (checklist nghiệm thu)
- `plans/260615-sprint-01-dashboard-mvp/reports/sprint-1-handover.md` (tóm tắt bàn giao + cách vận hành)

**Tái dùng (đọc, không sửa)**
- DAG backfill/ingest (Phase 03), Dashboard (Phase 04), reconciliation report (Phase 03)

## Implementation Steps
1. Chuẩn bị môi trường demo: chạy `backfill_history` nạp ~2 năm trước; verify reconcile.
2. Thực thi 1 lần `ingest_daily` (T-1) để có dữ liệu tươi ngay trước demo.
3. Viết `demo-script.md`: thứ tự thao tác, câu thoại giải thích Premium/Discount, đa sàn, lịch sử.
4. Viết `acceptance-checklist.md`: ánh xạ từng mục bàn giao roadmap ↔ bằng chứng (screenshot/endpoint/bảng).
5. Viết `sprint-1-handover.md`: cách chạy compose, chạy DAG, chạy backfill, biến `.env` cần thiết.
6. Chạy thử demo nội bộ (dry-run) — bắt lỗi luồng, chuẩn bị fallback nếu site sàn down.
7. Trình diễn với VRG; ghi nhận phản hồi vào biên bản; chốt các câu hỏi mở.
8. Tổng hợp action items cho Sprint 2 (không thực hiện ở Sprint 1).

## Todo List
- [ ] Backfill ~2 năm + verify reconcile trước demo
- [ ] Chạy `ingest_daily` T-1 lấy dữ liệu tươi
- [ ] `demo-script.md` (kịch bản end-to-end)
- [ ] `acceptance-checklist.md` (ánh xạ bàn giao roadmap)
- [ ] `sprint-1-handover.md` (vận hành tối thiểu)
- [ ] Dry-run demo nội bộ + phương án fallback
- [ ] Demo với VRG + thu phản hồi + chốt câu hỏi mở
- [ ] Danh sách action items chuyển Sprint 2

## Success Criteria
- VRG xác nhận đủ 3 bàn giao: **Dashboard 4 sàn** + **dữ liệu lịch sử ~2 năm** + **kết nối BCTM**.
- Demo chạy end-to-end không lỗi chặn (hoặc fallback mượt).
- Checklist nghiệm thu được VRG ký/đồng thuận; câu hỏi mở được chốt.
- Phản hồi & action items ghi nhận đầy đủ cho Sprint 2.

## Risk Assessment
- **Site sàn down đúng lúc demo** → fallback dùng dữ liệu đã nạp + nói rõ cơ chế crawl.
- **VRG chưa bàn giao BCTM/giá tham chiếu** → demo phần giá sàn + nêu phụ thuộc còn chờ; tránh treo nghiệm thu.
- **Kỳ vọng lệch (real-time intraday)** → làm rõ phạm vi T-1 ngay đầu demo (câu hỏi mở #4).
- **Độ phủ lịch sử thiếu** → trình reconciliation report minh bạch phần thiếu + kế hoạch bù.

## Security Considerations
- Demo không hiển thị dữ liệu nội bộ nhạy cảm ngoài phạm vi cho phép (giá BCTM).
- Môi trường demo trên Cloud VN; tài khoản truy cập hạn chế; không chia sẻ secret.

## Next Steps
- Chuyển action items + câu hỏi đã chốt sang **Sprint 2** (AI Engine & Chatbot).
- Cập nhật trạng thái roadmap & changelog **sau** nghiệm thu (qua `docs-manager`, ngoài phạm vi plan này).
