# Phase 01 — Khung màn · cây khu vực · luật gom

**Context**: [plan.md](plan.md) · [decisions.md](decisions.md) (QĐ-2, QĐ-3, QĐ-4, QĐ-6)

## Tổng quan
- Ưu tiên: **P1** (mọi phase khác phụ thuộc)
- Trạng thái: pending · Ước lượng 6h
- Dựng khung: route + 6 tab + thanh lọc dùng chung + **cây 2 cấp** + **service gom khu vực dùng chung**.
  Cuối phase: 6 tab đều mở được, nhưng chỉ tab Thu mua có số thật (làm mẫu), 4 tab kia còn rỗng.

## Key insights từ khảo sát
- `unit_report_query.py` đã có sẵn toàn bộ luật khó: `merge_scope/merge_view/merge_rollup`
  (sáp nhập), `year_plan_by_group` (mẫu số % KH lấy theo DANH SÁCH đơn vị khớp lọc, không theo đơn
  vị có phát sinh), `avg()` (BQ gia quyền), `NO_REGION_LABEL = "(Chưa gán khu vực)"`.
- Dòng `group_by="company"` **có sẵn** trường `region`; dòng `group_by="region"` dùng
  `NO_REGION_LABEL` khi đơn vị chưa gán. Khâu cây phải map `region=None → NO_REGION_LABEL`,
  **lệch một chữ là dòng con không chui vào dòng cha** (đúng bài học đã ghi trong file đó).
- `useStatsReport` (`use-stats.ts`) đã chống race (chỉ nhận lượt gọi mới nhất) — dùng lại nguyên.
- Web **không có test runner**; kiểm thử frontend bằng Playwright chụp màn (xem Phase 10).

## Requirements
**Chức năng**
- Route `/chi-so-don-vi` trong block `RequireCap caps={["unit_daily"]}` (`App.tsx` ~dòng 191).
- 6 tab theo Đ1, tab hiện hành nằm trong URL (`?tab=tong-quan|thu-mua|tieu-thu|ton-kho|hop-dong|tuan-thu`).
- Bộ lọc dùng chung **giữ nguyên khi chuyển tab** (Đ3): kỳ (from/to) · khu vực · đơn vị · chủng
  loại · `split_merged` · các ô riêng của tab. Lưu trong URL search params → link gửi đi mở lại y nguyên.
- Cây 2 cấp: **TOÀN TẬP ĐOÀN** (luôn hiện, đứng đầu) → **khu vực** (mở/gập, hiện `(n đơn vị)`) →
  **đơn vị**. Mặc định: các khu vực **gập**. Trạng thái mở/gập giữ khi đổi tab.
- Ô lọc chủng loại mờ/bật theo bảng ở QĐ-6.

**Phi chức năng**
- Mỗi file mới < 200 dòng, tên kebab-case (file `.tsx` component giữ PascalCase như phần còn lại của repo).
- Một lượt tải tab ≤ 2,5 s với kỳ 1 tháng, toàn bộ đơn vị (đo bằng `curl -w %{time_total}`).

## Architecture
```
GET /api/unit-daily/index/purchase?date_from&date_to&companies&regions&grades&materials
                                  &split_merged&group_by=tree
  → { "level": "tree",
      "rows": [ {key,label,level:"region",units:N, …chỉ tiêu…,
                 children:[{key,label,level:"company", …}]} ],
      "totals": {…}, "coverage"?: {…}, "warnings":[…] }
group_by ≠ "tree"  → trả y hệt endpoint `/analytics/*` cũ (bảng phẳng).
```

`services/unit_report_tree.py` (mới, ~70 dòng) — **dùng chung cho cả 5 tab**:
```python
def build_tree(report, *, call) -> dict:
    """Khâu 2 lượt gom (region + company) thành cây 2 cấp.
    call(group_by) → dict báo cáo của chính tab đó, nên file này KHÔNG biết tab nào là tab nào
    và KHÔNG tự cộng một con số nào — mọi phép cộng/bình quân vẫn nằm ở service của tab.
    """
```
Luật khâu (ghi thẳng comment trong file):
- Dòng con ghép vào cha theo `row["region"] or NO_REGION_LABEL`.
- Khu vực **không có đơn vị nào phát sinh** vẫn hiện nếu lượt `group_by="region"` trả dòng đó
  (vd chỉ có kế hoạch, chưa có sản lượng) → `children: []`, đếm `units` từ danh mục đơn vị.
- Dòng cha **luôn lấy nguyên từ lượt `group_by="region"`**, TUYỆT ĐỐI không cộng lại từ các dòng
  con (cộng lại là hỏng bình quân gia quyền + % tính-lại-từ-tổng).
- Ô cha không có nghĩa khi gom (vd `as_of` của tồn kho) → để `None`, **không** điền 0.

## Related code files
**Tạo**
- `apps/api/app/routers/unit_index.py` — router `/api/unit-daily/index` (endpoint Thu mua trước)
- `apps/api/app/services/unit_report_tree.py` — khâu cây (dùng chung)
- `apps/web/src/features/command-center/pages/unit-index/UnitIndexPage.tsx` — vỏ màn + 6 tab
- `apps/web/src/features/command-center/pages/unit-index/use-index-context.ts` — state lọc + đồng bộ URL
- `apps/web/src/features/command-center/pages/unit-index/IndexFilters.tsx` — thanh lọc dùng chung
- `apps/web/src/features/command-center/pages/unit-index/IndexTree.tsx` — bảng cây 2 cấp
- `apps/web/src/features/command-center/pages/unit-index/stats-cell.ts` — hàm định dạng ô (tách ra để dùng chung)
- `apps/web/src/features/command-center/pages/unit-index/tabs/PurchaseTab.tsx` — tab mẫu
- `apps/web/src/lib/unit-index-client.ts` — client của màn mới

**Sửa**
- `apps/web/src/App.tsx` — thêm route (chưa xoá route cũ; xoá ở Phase 08)
- `apps/web/src/features/command-center/pages/analytics/StatsTable.tsx` — rút hàm `cell()` sang
  `stats-cell.ts` rồi import lại (DRY; **không** copy hàm)

## Implementation steps
1. `stats-cell.ts`: chuyển nguyên hàm `cell(row, col)` + type `StatsCol` từ `StatsTable.tsx` sang;
   `StatsTable.tsx` import lại. Chạy `pnpm build` để chắc không vỡ 3 màn đang dùng.
2. `unit_report_tree.build_tree(call)`: gọi `call("region")` và `call("company")`, khâu theo luật ở
   trên, trả `{"level":"tree","rows":[…],"totals":…,"warnings":…}`. Gộp `warnings` của 2 lượt, khử trùng.
3. `routers/unit_index.py`: endpoint `GET /purchase` — `group_by="tree"` thì gọi `build_tree`
   với `call = lambda g: pur.purchase_report(..., group_by=g)`; `group_by` khác thì gọi thẳng.
   Import `assert_range` + `_require` từ `routers.unit_analytics` (không copy).
   Đăng ký router trong `apps/api/app/main.py`.
4. `use-index-context.ts`: hook đọc/ghi `useSearchParams` → `{tab, filters, setTab, patch}`.
   Kỳ mặc định = **Tháng này** (màn này để xem chỉ số, không phải dò ngày như màn cũ).
5. `IndexFilters.tsx`: dùng lại `MultiSelect` + `SplitMergedToggle` từ `AnalyticsFilters.tsx`
   (export sẵn). Nhận prop `gradesEnabled: boolean` + `gradesNote?: string` (QĐ-6);
   khi tắt thì `<Select disabled>` + `<div className="form-note">` ghi chú.
   Ô "Kỳ"/"Chốt ngày" nhận từ ngoài vào (`periodSlot`) để tab Tồn kho thay được (Phase 03).
6. `IndexTree.tsx`: bảng 3 loại dòng (tập đoàn · khu vực · đơn vị), cột đầu thụt lề theo cấp,
   nút mở/gập ở dòng khu vực kèm `(n đơn vị)`; ô số dùng `stats-cell.ts`.
   Dòng đơn vị bấm được → callback `onDrill(row)`.
7. `UnitIndexPage.tsx`: `<Tabs>` AntD, `items` là 6 tab; body tab lazy theo `tab` hiện hành
   (tab chưa mở thì **không gọi API** — 6 tab gọi cùng lúc là 6 lượt quét vô ích).
8. `PurchaseTab.tsx`: nối `useStatsReport` + `IndexTree`, dùng cột `COLS` bê từ `PurchaseStatsPage`.
9. Thêm route vào `App.tsx`. Chạy `cd apps/api && uv run pytest -q` + `cd apps/web && pnpm build`.
10. Đo thời gian: `curl -w "\n%{time_total}\n"` endpoint `/index/purchase?group_by=tree` kỳ 1 tháng.
    Ghi số đo vào `plans/260920-chi-so-don-vi/reports/perf.md`. Vượt 2,5 s → mở phương án B (QĐ-3).

## Todo
- [ ] Tách `stats-cell.ts`, `StatsTable.tsx` import lại, `pnpm build` xanh
- [ ] `unit_report_tree.py` + comment đủ 6 luật gom khu vực
- [ ] `routers/unit_index.py` + đăng ký ở `main.py`
- [ ] `use-index-context.ts` (URL giữ tab + bộ lọc)
- [ ] `IndexFilters.tsx` (có chế độ mờ ô chủng loại + ghi chú đỏ)
- [ ] `IndexTree.tsx` (3 cấp dòng, mở/gập, đếm đơn vị)
- [ ] `UnitIndexPage.tsx` 6 tab, tab chưa mở không gọi API
- [ ] `PurchaseTab.tsx` chạy thật
- [ ] Route `/chi-so-don-vi` trong `RequireCap caps={["unit_daily"]}`
- [ ] Đo hiệu năng, ghi `reports/perf.md`

## Success criteria
- Mở `/chi-so-don-vi`, đủ 6 tab; đổi tab **không** mất kỳ/bộ lọc; copy URL dán sang tab trình
  duyệt khác ra đúng màn đang xem.
- Tab Thu mua: dòng TOÀN TẬP ĐOÀN = `totals` của API; mở một khu vực, **tổng sản lượng** các dòng
  con = dòng cha; **đơn giá BQ** dòng cha KHÁC trung bình cộng các dòng con (chứng minh gia quyền).
- `% KH năm` dòng khu vực = Σ thực hiện ÷ Σ kế hoạch của các đơn vị trong khu vực (tính tay 1 khu vực để đối chiếu).
- Đơn vị chưa gán khu vực nằm dưới dòng "(Chưa gán khu vực)", không biến mất.
- Tài khoản không có cap `unit_daily` → 403 ở API và không thấy route.
- `uv run pytest -q` xanh, `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Lệch nhãn khu vực làm dòng con rơi ra ngoài | Một hằng `NO_REGION_LABEL` duy nhất, import từ `unit_report_query`; test có 1 đơn vị chưa gán khu vực |
| 2 lượt quét làm chậm | Đo ngay bước 10; phương án B đã viết sẵn ở QĐ-3 |
| Rút `cell()` khỏi `StatsTable` làm vỡ 3 màn cũ | Chỉ di chuyển, không sửa logic; `pnpm build` + mở lại 3 màn cũ |
| 6 tab cùng gọi API | Render body theo tab hiện hành (bước 7) |

## Security
Chỉ đọc. Quyền `unit_daily` mức Xem qua `require_cap` — **không** dùng `require_any_cap`
(bài học `cap-two-level-view-edit`). Không nhận `companies` từ client làm phạm vi quyền (ở đây
`companies` chỉ là bộ lọc hiển thị của người đã có quyền xem toàn bộ).

## Next steps
Mở khoá Phase 02 · 03 · 04 · 05 — chạy **song song**, file không giao nhau.
