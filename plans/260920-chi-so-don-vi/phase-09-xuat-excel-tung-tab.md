# Phase 09 — Xuất Excel từng tab (+ sửa lỗi cột mủ dây)

**Context**: [plan.md](plan.md) (Đ7) · Phase 02–07

## Tổng quan
- Ưu tiên: **P2** · pending · Ước lượng 4h
- Phụ thuộc: **02 · 03 · 04 · 05** (cột đã chốt). Song song với 06 · 07 · 08.
- Mỗi tab một nút "Xuất Excel" xuất **đúng bảng đang xem** (đúng bộ lọc, đúng cây, đúng cột so sánh).

## Key insights — lỗi có sẵn phải sửa trong phạm vi này
`apps/api/app/services/unit_analytics_excel.py:24` (`PURCHASE_COLS`):
- **Thiếu cột `qty_lace`** (mủ dây) — mủ dây là chủng loại nguyên liệu thứ 3, màn web đã có cột
  nhưng file Excel thì không → người đối chiếu file thấy tổng không khớp các cột thành phần.
- **Nhãn `qty_material` ghi sai**: "Tổng mủ nguyên liệu (mủ nước + chén)" trong khi code cộng
  **cả mủ dây** (`_PLAN_MATERIALS = ("latex", "cup", "lace")` ở `unit_report_purchase.py`).
- Nhân tiện: `price_cup_avg` ghi cứng "đồng/độ" trong khi web dùng hằng `CUP_PRICE_UNIT` /
  `LACE_PRICE_UNIT` (`apps/web/src/lib/purchase-price-unit.ts`) — kiểm lại cho khớp.

Khác:
- `unit_analytics_excel.build_xlsx` đã dựng bảng từ danh sách cột động + hỗ trợ **sheet phụ**
  (`sheets=`) → dùng lại được cho cả 6 tab, **không** viết bộ dựng Excel mới.
- Bản xuất Excel **không cắt trang** (file phải đủ để đối chiếu) — giữ nguyên quy ước.

## Requirements
- 6 nút xuất, 6 tên file: `chi-so-don-vi-<tab>-<from>-den-<to>.xlsx`
  (tab Tồn kho: `…-ton-kho-ngay-<as_of>.xlsx`).
- **Cây xuất thành bảng phẳng có thụt lề**: cột đầu "Cấp" (`Tập đoàn` / `Khu vực` / `Đơn vị`) +
  cột "Khu vực" + cột "Đơn vị"; dòng khu vực có `(n đơn vị)`. Excel không có cây gập nên phải
  đọc được bằng mắt và lọc được bằng AutoFilter.
- Cột so sánh: có trong file **khi và chỉ khi** công tắc đang bật.
- Dòng ghi chú dưới tiêu đề nói rõ: kỳ · ngày chốt (nếu có) · bộ lọc đang áp · cảnh báo của báo cáo
  (dùng lại `_note(rep)`).
- Ô trống vẫn để **trống** trong file (không ghi 0) — Excel để trống là đúng nghĩa "không có số".

## Related code files
**Tạo**
- `apps/api/app/services/unit_index_excel.py` (~120 dòng — chuyển cây → hàng phẳng, dựng cột so sánh)

**Sửa**
- `apps/api/app/services/unit_analytics_excel.py` — thêm `("qty_lace", "Sản lượng mủ dây", "tấn quy khô")`,
  sửa nhãn `qty_material` → "Tổng mủ nguyên liệu (mủ nước + chén + dây)", rà đơn vị tính mủ chén/dây
- `apps/api/app/routers/unit_index.py` — 6 endpoint `*.xlsx`
- `apps/web/src/lib/unit-index-client.ts` — dùng lại `saveXlsx` (đã có trong `unit-analytics-client.ts`; **export** nó ra thay vì copy)
- `apps/web/src/features/command-center/pages/unit-index/IndexFilters.tsx` — nút xuất

## Implementation steps
1. Sửa `PURCHASE_COLS` (thêm `qty_lace`, sửa nhãn). Chạy `uv run pytest -q -k xlsx` — test
   `test_range_validation_and_xlsx` phải vẫn xanh. Mở thử file, đối chiếu với màn web.
2. `saveXlsx` trong `unit-analytics-client.ts`: đổi thành `export async function saveXlsx(...)`
   nhưng cho nhận **đường dẫn đầy đủ** (hiện đang ghép cứng `BASE`), để client mới dùng lại
   được — **không copy hàm sang file mới**.
3. `unit_index_excel.flatten(rows)`: đệ quy cây → list phẳng, mỗi dòng thêm
   `level` ("Tập đoàn"/"Khu vực"/"Đơn vị") · `region` · `unit_count`.
4. `unit_index_excel.compare_cols(cols, modes)`: sinh thêm `Col` cho `_prev`/`_yoy`/`_pct`
   (chỉ khi `modes` không rỗng), nhãn tiếng Việt như trên web.
5. 6 endpoint `*.xlsx` trong `routers/unit_index.py`: gọi đúng hàm báo cáo của tab (cùng tham số
   với endpoint JSON) rồi `xls.build_xlsx(...)`. Tab Tiêu thụ ở chế độ chi tiết: dùng
   `CONSUMPTION_DETAIL_COLS` + `flat=True` như hiện nay, **không cắt trang**.
6. Tab Tồn kho: `period_label="Ảnh chụp"` + dòng kỳ `"Ngày chốt dd/mm/yyyy"` (dùng lại `_stock_period`).
   Kèm **sheet phụ "Độ phủ"** liệt kê đơn vị chưa có số / khai trống.
7. Tab Tuân thủ chế độ ma trận: giữ đúng khả năng xuất hiện có (nếu màn cũ chưa có thì **không
   thêm** — YAGNI; ghi vào câu hỏi treo).
8. Nút xuất trên `IndexFilters`, `loading` trong lúc tải, `message.success` khi xong (như màn cũ).

## Todo
- [ ] Sửa `PURCHASE_COLS`: thêm `qty_lace`, sửa nhãn `qty_material`, rà đơn vị tính chén/dây
- [ ] `export` lại `saveXlsx` cho dùng chung (không copy)
- [ ] `unit_index_excel.py`: `flatten` + `compare_cols`
- [ ] 6 endpoint `*.xlsx`
- [ ] Sheet phụ "Độ phủ" cho tab Tồn kho
- [ ] Nút xuất trên thanh lọc, đủ 6 tab
- [ ] Mở từng file kiểm bằng mắt + đối chiếu với màn

## Success criteria
- File Thu mua có **đủ 3 cột mủ nguyên liệu** (nước · chén · dây) và nhãn tổng ghi đúng cả 3.
- Mở file bất kỳ: dòng "Tập đoàn" / "Khu vực" / "Đơn vị" phân biệt được; tổng các dòng đơn vị
  trong một khu vực = dòng khu vực (với cột cộng dồn).
- Bật/tắt công tắc so sánh → file có/không có cụm cột so sánh.
- Ô trống trên web cũng **trống** trong file (không thành 0).
- Tiêu thụ chế độ chi tiết: file có **toàn bộ** dòng khớp lọc, không chỉ 100 dòng của trang đang xem.
- `uv run pytest -q` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Thêm cột làm lệch vị trí cột trong file người dùng đã quen | Chèn `qty_lace` **ngay sau** `qty_cup`, đúng thứ tự màn web |
| Copy `saveXlsx` thành 2 bản | Bước 2 export lại, code review kiểm |
| File quá lớn khi xuất chi tiết cả năm | Giữ nguyên hành vi hiện tại (không cắt trang); nếu > 50k dòng thì cảnh báo trước khi tải |
| Cây xuất ra đọc không hiểu | Cột "Cấp" + AutoFilter; kiểm bằng mắt ở bước 8 |

## Security
Chỉ đọc, cap `unit_daily` mức Xem. Không nhúng công thức Excel từ dữ liệu người dùng
(bài học `access-log-feature` về Excel formula injection): mọi ô chữ ghi bằng `ws.cell(value=…)`
với chuỗi thuần; chuỗi bắt đầu bằng `= + - @` phải được thêm dấu nháy đơn.

## Next steps
Phase 10: đối chiếu file Excel với bảng trên web trong checklist nghiệm thu.
