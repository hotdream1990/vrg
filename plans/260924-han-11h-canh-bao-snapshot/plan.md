# 24/09/2026 — 5 yêu cầu của chủ dự án

| # | Hạng mục | Trạng thái | Agent |
|---|---|---|---|
| 1 | Chỉ tiêu **Kế hoạch khai thác** (cột ĐẦU của Kế hoạch năm) | xong · review · sửa | A |
| 2 | Cửa sổ nhập liệu = **hạn 11:00 ngày D + N** cho mọi biểu (bỏ 2 ô cộng ngày riêng) | xong · review · sửa | B |
| 3 | **Cảnh báo tự động** qua Hỗ trợ & Thông báo sau giờ chốt, có link tới Cảnh báo bất thường + ảnh mẫu | xong · review · sửa — job seed TẮT | C |
| 4 | Rà logic **tồn kho khi ngày không có số** ở báo cáo admin → báo chủ dự án xác nhận | ⏸ chờ chủ dự án OK/không OK | E |
| 5 | **Snapshot số liệu tuần** (thu mua · tiêu thụ · tồn kho từng đơn vị) tự chụp khi hết hạn nhập ngày cuối tuần | xong · review · sửa | D |

## Hợp đồng dùng chung (đã có trong `apps/api/app/core/edit_window.py`)
- `cutoff_hour()` — khoá `EDIT_CUTOFF_HOUR`, mặc định 11.
- `deadline(as_of, window)` → datetime VN = giờ chốt của ngày `as_of + window`.
- `editable_from(window, ref=None)` → ngày cũ nhất còn sửa được (có thể > hôm nay).
- `is_editable(as_of, window)`, `window_phrase(window)`, `member_window()`, `editor_window()` (bỏ tham số `kind`).
- GET trả `edit_window_days` kèm `editable_from` (ISO) — web so `d >= editable_from`.

## Quy tắc chạy song song
- Mỗi agent 1 DB test riêng (`vrg_test_a|b|c|d`), không đụng DB dev `vrg_caosu` khi chạy pytest.
- File dùng chung (db.py, scheduler.py, member_self.py, unit_daily.py, test_unit_daily.py,
  unit-daily-client.ts) chỉ sửa bằng Edit tool, đọc lại nếu Edit báo file đã đổi.
- KHÔNG git add/commit/stash/checkout/reset — main agent commit cuối.

## Kết quả kiểm tra cuối (24/09/2026 ~10:15)
- pytest toàn bộ trên DB sạch: **668 passed, 6 skipped**; web `tsc` + `pnpm build` OK; ruff sạch các file của đợt này.
- Ảnh mẫu: `visuals/1..8`. Review: `reports/review-*.md`. Chưa commit (có phiên khác đang sửa song song floor-suggest/inventory_daily — commit phải add theo đường dẫn).
