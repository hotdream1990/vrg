# Phase 03 — Tab Tồn kho (trục NGÀY CHỐT)

**Context**: [plan.md](plan.md) (Đ4) · [phase-01](phase-01-khung-man-va-cay-khu-vuc.md)

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 3h · Phụ thuộc: Phase 01
- **Chạy song song được** với Phase 02 · 04 · 05.
- Tab duy nhất đổi trục thời gian: ô "Kỳ" → ô **"Chốt ngày"** (mặc định = ngày cuối kỳ đang chọn),
  thêm cột **"Ngày lấy số"** và **dải độ phủ**.

## Key insights — vì sao phải khác
Tồn kho là **số thời điểm**. Cộng dồn theo kỳ là SAI và đã từng gây lệch nặng (xem comment trong
`unit_report_stock.py` và `unit_period_report._latest_stock`: vụ Chư păh 862,55 tấn, 27/08/2026).
Quy tắc lấy số (chốt 21/08/2026, **giữ nguyên**):
- Đơn vị khai ngày nào → lấy đúng ngày đó.
- Đơn vị tick "không phát sinh tồn kho để khai" → giữ số của **lần khai gần nhất**.
- Đơn vị không khai gì → **KHÔNG có số**, không mượn số ngày khác đắp vào; vào nhóm "chưa có số"
  của dải độ phủ.
- `_drop_superseded`: bỏ ảnh chụp cũ của đơn vị đã sáp nhập khi đơn vị nhận đã khai chung kho.

## Requirements
- Ô "Chốt ngày" thay ô Kỳ **chỉ trong tab này**; giá trị mặc định = `filters.to` của kỳ dùng chung.
  Người dùng đổi ngày chốt → ghi vào ngữ cảnh chung (`asOf`), **không** đụng `from`/`to`
  (chuyển sang tab khác vẫn còn nguyên kỳ cũ — Đ3).
- Ô "xem lại N ngày" chỉ hiện khi nhóm theo NGÀY (như `StockFilters` hiện nay).
- Cột: `as_of` (Ngày lấy số) · `age_days` · chưa nhập kho · đã nhập kho · tổng TP ·
  đã ký HĐ chưa giao · tồn có thể giao dịch · tồn nguyên liệu.
- **Dòng khu vực/tập đoàn: ô "Ngày lấy số" để TRỐNG** khi gộp nhiều ngày (mỗi đơn vị một ngày) —
  `_close()` đã làm đúng việc này (`as_of = dates[-1] if len(dates)==1 else None`), không được "sửa".
  `age_days` của dòng cha = **ngày cũ nhất** trong nhóm (đã có sẵn).
- `StockCoverageBar` hiện ngay dưới thanh lọc, đúng như màn cũ.
- Lọc chủng loại: **bật** (áp cho 2 khối thành phẩm; tồn nguyên liệu không có chủng loại).

## Architecture
```
GET /api/unit-daily/index/stock?as_of&days_back&companies&regions&grades&split_merged&group_by=tree|company|region|grade|day
  → { …như /analytics/stock…, "rows": cây 2 cấp khi group_by=tree, "coverage": {…} }
```
`coverage` lấy từ lượt `group_by="company"` (nó tính trên ảnh chụp trước khi lọc chủng loại) —
**không** lấy từ lượt `region` để khỏi đếm 2 lần.

## Related code files
**Tạo**
- `apps/web/src/features/command-center/pages/unit-index/tabs/StockTab.tsx`
- `apps/web/src/features/command-center/pages/unit-index/tabs/stock-cols.ts`

**Sửa**
- `apps/api/app/routers/unit_index.py` (endpoint `/stock`)
- `apps/web/src/features/command-center/pages/unit-index/IndexFilters.tsx` (nhận `periodSlot`)
- `apps/web/src/features/command-center/pages/unit-index/use-index-context.ts` (thêm `asOf`, `daysBack`)
- `apps/web/src/lib/unit-index-client.ts`

**Dùng lại nguyên**: `pages/analytics/StockCoverageBar.tsx`, `StockFilters.DAYS_BACK_OPTIONS`.

## Implementation steps
1. `use-index-context.ts`: thêm `asOf` (mặc định = `to`) + `daysBack` (mặc định 7) vào URL params.
   Khi người dùng đổi `to` mà **chưa** tự đặt `asOf` thì `asOf` bám theo `to`; đã tự đặt thì giữ
   nguyên (cờ `asOfPinned` trong URL).
2. `routers/unit_index.py`: `GET /stock` — `group_by="tree"` → `build_tree` với
   `call = lambda g: st.stock_report(as_of, days_back if g=="day" else 0, …, group_by=g)`;
   gắn `coverage` từ lượt `company`.
3. `stock-cols.ts`: bê `COLS` + `KPIS` từ `StockStatsPage.tsx` nguyên văn (kể cả `note`).
4. `StockTab.tsx`: `periodSlot` = ô "Chốt ngày" (+ ô "xem lại N ngày" khi nhóm theo NGÀY);
   `<StockCoverageBar asOf={asOf} coverage={data.coverage} />`; cây hoặc `StatsTable` như Phase 02.
   Nhóm theo NGÀY thì bỏ 2 cột mốc thời gian (giữ nguyên `COLS.slice(2)` như màn cũ).
5. Đối chiếu từng con số với `/thong-ke/ton-kho` ở cùng ngày chốt.

## Todo
- [ ] `asOf`/`daysBack` vào ngữ cảnh chung + URL, có cờ `asOfPinned`
- [ ] Endpoint `/index/stock` (tree + coverage lấy đúng một lượt)
- [ ] `stock-cols.ts` bê nguyên cột màn cũ
- [ ] `StockTab.tsx` + dải độ phủ
- [ ] Đối chiếu số với màn cũ (ảnh lưu `visuals/`)

## Success criteria
- Đổi sang tab Tồn kho: ô Kỳ biến thành "Chốt ngày" = ngày cuối kỳ; quay lại tab khác, kỳ **vẫn nguyên**.
- Dòng TOÀN TẬP ĐOÀN = dòng "Tổng cộng" của màn cũ tại cùng ngày chốt (sai số 0).
- Dòng khu vực gồm ≥ 2 ngày lấy số khác nhau → ô "Ngày lấy số" **trống**, `age_days` = ngày cũ nhất.
- Dải độ phủ: `x/y đơn vị có số` + danh sách đơn vị chưa có số khớp màn cũ.
- Đơn vị đã sáp nhập (mặc định gộp): không xuất hiện 2 lần, tổng không tăng vọt.
- `uv run pytest -q` xanh (các test `test_stock_*` hiện có phải vẫn xanh) · `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Ai đó "sửa" ô ngày trống của dòng cha thành ngày mới nhất | Ghi comment cảnh báo tại chỗ + criteria ở trên; test khoá |
| Cộng `coverage` 2 lần (region + company) | Chỉ lấy từ lượt `company`, ghi comment lý do |
| Người dùng tưởng tab này cũng theo kỳ | Dòng chú thích ngay dưới ô: "Tồn kho là số thời điểm — không cộng dồn theo kỳ" |
| `days_back` đi vào lượt `region` làm lệch | Chỉ truyền `days_back` khi `group_by="day"` (đã có luật ở service) |

## Security
Chỉ đọc, cap `unit_daily` mức Xem. `as_of` kiểm định dạng bằng `date.fromisoformat` như router cũ;
`days_back` giữ `ge=0, le=90`.

## Next steps
Phase 06 định nghĩa kỳ so sánh riêng cho tab này (dịch **ngày chốt**, không dịch kỳ).
