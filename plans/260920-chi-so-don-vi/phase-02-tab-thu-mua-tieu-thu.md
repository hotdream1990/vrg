# Phase 02 — Tab Thu mua · Tab Tiêu thụ

**Context**: [plan.md](plan.md) · [phase-01](phase-01-khung-man-va-cay-khu-vuc.md) · [decisions.md](decisions.md) (QĐ-4, QĐ-6)

## Tổng quan
- Ưu tiên: **P1** · pending · Ước lượng 5h · Phụ thuộc: Phase 01
- **Chạy song song được** với Phase 03 · 04 · 05.
- Đưa trọn 2 màn `/thong-ke/thu-mua` và `/thong-ke/tieu-thu` vào 2 tab: giữ **đủ** bộ lọc,
  drill-down, bảng chi tiết có phân trang.

## Key insights
- `purchase_report` / `consumption_report` đã trả đúng mọi thứ cần, chỉ thiếu trục cây (Phase 01 lo).
- **Lỗi có sẵn phải sửa luôn**: `ConsumptionStatsPage.tsx:38-40` hiện 2 cột `plan_revenue_ty` +
  `pct_plan_revenue` nhưng `unit_report_consumption.py` **không hề trả 2 trường này** → 2 cột luôn
  trống. `unit_period_report.py:204` đã có công thức, bê sang.
- Thu mua: `grades` chỉ áp cho mủ thành phẩm; lọc theo loại mủ/chủng loại thì backend **cố ý bỏ**
  % kế hoạch và kèm cảnh báo — giữ nguyên hành vi đó, đừng "sửa" thành 0%.
- Tiêu thụ chế độ chi tiết (`group_by="none"`) cắt trang ở server (`page`/`page_size`, trả `total`).

## Requirements
- Tab Thu mua: cột y như `PurchaseStatsPage.COLS` (13 cột), KPI y như `KPIS`, biểu đồ cột
  (`DrillHeader`), ô lọc **loại mủ**, ô chủng loại bật khi đã chọn "thành phẩm" (giữ luật cũ:
  bỏ chọn thành phẩm thì xoá `grades`).
- Tab Tiêu thụ: cột y như `SUMMARY_COLS` + 4 cột kế hoạch, cột chi tiết y như `DETAIL_COLS`,
  ô lọc **loại HĐ** + **hình thức**, phân trang chi tiết giữ nguyên.
- Drill theo QĐ-4: bấm dòng đơn vị trên cây → lớp NGÀY của riêng đơn vị đó (bảng phẳng
  `StatsTable`), có breadcrumb quay lại cây.
- Ô "Nhóm theo" giữ đủ lựa chọn cũ, thêm mục **"Cây khu vực → đơn vị"** làm mặc định.

## Architecture
```
GET /api/unit-daily/index/purchase      (Phase 01 đã dựng)
GET /api/unit-daily/index/consumption   ?…&contract&channel&page&page_size&group_by=tree|…
```
Frontend mỗi tab là **một file panel** nhận `{filters, patch}` từ vỏ màn, tự giữ drill state của
riêng mình (reset khi `filters` đổi). Cột + KPI bê nguyên từ page cũ để số liệu không đổi nghĩa.

## Related code files
**Tạo**
- `apps/web/src/features/command-center/pages/unit-index/tabs/ConsumptionTab.tsx`
- `apps/web/src/features/command-center/pages/unit-index/tabs/purchase-cols.ts` (COLS + KPIS tách ra, < 80 dòng)
- `apps/web/src/features/command-center/pages/unit-index/tabs/consumption-cols.ts`
- `apps/web/src/features/command-center/pages/unit-index/use-tab-drill.ts` (drill rút gọn theo QĐ-4)

**Sửa**
- `apps/web/src/features/command-center/pages/unit-index/tabs/PurchaseTab.tsx` (hoàn thiện từ Phase 01)
- `apps/api/app/routers/unit_index.py` (thêm endpoint consumption)
- `apps/api/app/services/unit_report_consumption.py` (bổ sung `plan_revenue_ty` + `pct_plan_revenue`)
- `apps/web/src/lib/unit-index-client.ts`

**Không đụng** (Phase 08 mới xoá): `pages/analytics/PurchaseStatsPage.tsx`, `ConsumptionStatsPage.tsx`.

## Implementation steps
1. `unit_report_consumption.py`: trong `_attach_plan`, thêm
   `g["plan_revenue_ty"] = plan_rev or None` và
   `g["pct_plan_revenue"] = (revenue_ty / plan_rev * 100) if plan_rev else None`.
   Lấy chỉ tiêu bằng `year_plan_by_group("plan_revenue_ty", …)` — gọi thêm **một** lượt, cùng
   kiểu với `_PLAN_KEY` hiện có. Giữ nguyên quy ước: chưa giao kế hoạch → **trống**, không 0%.
2. Thêm test `test_consumption_reports_revenue_plan_percent` vào `apps/api/tests/test_unit_analytics.py`.
3. `routers/unit_index.py`: endpoint `GET /consumption` (đủ tham số như `/analytics/consumption`,
   thêm `group_by=tree`). Chế độ `group_by="none"` **không** đi qua cây (chi tiết là dòng chứng từ).
4. `use-tab-drill.ts`: state `steps: {dim:"company"|"day", value}[]`, `applyToFilters()` thu hẹp
   `companies`/`from`/`to`. Reset khi `filters` (ngoài drill) đổi.
5. `purchase-cols.ts` / `consumption-cols.ts`: bê `COLS`/`KPIS`/`DETAIL_COLS`/`PLAN_COLS` từ 2 page cũ
   (copy nguyên văn kể cả comment giải thích thứ tự cột — đó là quyết định nghiệp vụ 14/08/2026).
6. `PurchaseTab.tsx` + `ConsumptionTab.tsx`: cây khi `groupBy==="tree"`, ngược lại `StatsTable`;
   `DrillHeader` giữ nguyên cho KPI + biểu đồ; phân trang chi tiết bê từ `ConsumptionStatsPage`.
7. `pnpm build` + mở 2 tab, đối chiếu **từng con số** với 2 màn cũ trên cùng kỳ.

## Todo
- [ ] Backend trả `plan_revenue_ty` + `pct_plan_revenue` cho tiêu thụ (+ test)
- [ ] Endpoint `/index/consumption` (tree + phẳng + chi tiết phân trang)
- [ ] `use-tab-drill.ts`
- [ ] `purchase-cols.ts` · `consumption-cols.ts`
- [ ] `PurchaseTab.tsx` hoàn thiện · `ConsumptionTab.tsx`
- [ ] Đối chiếu số với 2 màn cũ (ảnh chụp 2 bên, lưu `visuals/`)

## Success criteria
- Với **cùng kỳ + cùng bộ lọc**, mọi ô của tab mới khớp màn cũ (sai số 0).
- 2 cột kế hoạch doanh thu ở tab Tiêu thụ **có số** (trước đây luôn trống).
- Lọc loại mủ/chủng loại ở Thu mua: `% KH` chuyển sang trống + hiện đúng câu cảnh báo cũ.
- Chi tiết tiêu thụ: `total` và số trang khớp màn cũ; dòng Tổng cộng vẫn tính trên **cả kỳ**,
  không phải trang đang xem.
- `uv run pytest -q` xanh · `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Bê cột thiếu/sai thứ tự làm người dùng đọc nhầm | Copy nguyên văn kèm comment; đối chiếu ảnh 2 màn |
| Thêm 1 lượt `year_plan_by_group` làm chậm | Cùng dữ liệu đã nạp, chi phí không đáng kể — vẫn đo lại |
| Drill rút gọn làm mất đường "khu vực → đơn vị" cũ | Cây đã thay thế; breadcrumb ghi rõ đang ở nhánh nào |

## Security
Chỉ đọc, cap `unit_daily` mức Xem. Không nhận `page_size` tuỳ ý (giữ `le=500` như router cũ).

## Next steps
Phase 06 (cột so sánh) và Phase 09 (Excel) dùng lại cột của 2 tab này.
