# Phase 07 — Tab Tổng quan

**Context**: [plan.md](plan.md) · [decisions.md](decisions.md) (QĐ-1) · Phase 02–05

## Tổng quan
- Ưu tiên: **P2** · pending · Ước lượng 4h
- Phụ thuộc: **02 · 03 · 04 · 05**. Song song được với 06 · 08 · 09.
- Một dòng = một đơn vị, gom **chỉ số đầu bảng của cả 5 tab kia** — đúng mục đích "không phải mở
  4–5 màn nữa".

## Key insights
- Đây là tab **ghép**, không phải tab tính toán mới: mọi con số phải lấy **đúng từ service của tab
  gốc**, không viết lại công thức. Viết lại là tạo ra "hai cách tính" — đúng thứ màn này sinh ra để dẹp.
- Vì ghép nhiều nguồn, tab này nặng nhất → **không** bật cột so sánh mặc định ở đây (Phase 06 vẫn
  hỗ trợ, nhưng mặc định tắt cho riêng tab Tổng quan).
- Con số phải đối soát được với "Báo cáo tổng hợp" (QĐ-1) — đó là điều kiện để không mở rộng
  `period-report`.

## Requirements
Cột (dòng = đơn vị · khu vực · tập đoàn):
| Nhóm | Cột | Nguồn |
|---|---|---|
| Thu mua | Mủ nguyên liệu (tấn) · % KH năm | `unit_report_purchase` |
| | Đơn giá BQ mủ nước (đ/độ) | `unit_report_purchase` (BQ gia quyền) |
| Tiêu thụ | Sản lượng (tấn) · Doanh thu (tỷ đ) · % KH HĐ chuyến | `unit_report_consumption` |
| | Giá bán BQ (triệu đ/tấn) | `unit_report_consumption` (BQ gia quyền) |
| Tồn kho | Tổng tồn TP tại ngày chốt (tấn) · **Ngày lấy số** | `unit_report_stock` |
| Hợp đồng | Còn phải giao (tấn) · Đã ký chưa giao (tấn) | `unit_report_contract` |
| Tuân thủ | Tỷ lệ nộp (%) | `unit_report_compliance` |

- "Ngày lấy số" ở dòng khu vực/tập đoàn: **TRỐNG** (mỗi đơn vị một ngày).
- Bộ lọc: kỳ + ngày chốt + khu vực + đơn vị + `split_merged`. **Chủng loại mờ** (QĐ-6).
- Bấm dòng đơn vị → không drill sâu ở đây mà **nhảy sang tab tương ứng** đã lọc sẵn đơn vị đó
  (nút nhỏ trên mỗi nhóm cột, hoặc menu "Xem chi tiết → Thu mua / Tiêu thụ / …").

## Architecture
```
GET /api/unit-daily/index/overview?date_from&date_to&as_of&companies&regions&split_merged&compare=
  → { rows: cây 2 cấp (đã ghép), totals: {…}, warnings: [gộp của mọi nguồn], sources: {…} }
```
`services/unit_report_overview.py` (mới, ~120 dòng):
1. Gọi **song song không được** (đồng bộ, FastAPI sync) → gọi tuần tự 5 nguồn ở mức
   `group_by="company"` và `group_by="region"`.
2. Ghép theo `key` (tên đơn vị / tên khu vực) thành một dòng; ô thiếu = `None`.
3. **Không** tính lại bất kỳ bình quân/tỷ lệ nào — bê thẳng ô của service gốc.
4. Gộp `warnings` của 5 nguồn, khử trùng, thêm tiền tố nguồn (vd "Tồn kho: …").

## Related code files
**Tạo**
- `apps/api/app/services/unit_report_overview.py`
- `apps/web/src/features/command-center/pages/unit-index/tabs/OverviewTab.tsx`
- `apps/web/src/features/command-center/pages/unit-index/tabs/overview-cols.ts`
- `apps/api/tests/test_unit_index_overview.py`

**Sửa**
- `apps/api/app/routers/unit_index.py`
- `apps/web/src/lib/unit-index-client.ts`
- `apps/web/src/features/command-center/pages/unit-index/UnitIndexPage.tsx` (Tổng quan thành tab đầu)

## Implementation steps
1. `unit_report_overview.py`: hàm `overview(...)` gọi 5 nguồn, ghép; **mỗi ô kèm comment nguồn**.
   Ô không gộp được để `None` (ngày lấy số ở dòng cha).
2. Endpoint `/index/overview`; `compare` mặc định **rỗng** (tắt) cho riêng tab này.
3. `overview-cols.ts`: cột nhóm theo 5 khối, có `note` ghi rõ đơn vị tính + nguồn
   (vd "tại ngày chốt", "chỉ tiêu năm").
4. `OverviewTab.tsx`: `IndexTree` + KPI hàng đầu (5 thẻ: mủ NL · tiêu thụ · doanh thu · tồn TP ·
   tỷ lệ nộp) + nút "Xem chi tiết" mở tab tương ứng đã lọc sẵn đơn vị.
5. Test đối soát: với cùng kỳ, `overview` của 1 đơn vị **khớp từng ô** với endpoint của tab gốc,
   và `qty_material` + `% KH` khớp `/api/unit-daily/period-report` (kind=purchase) cùng kỳ.
6. Đo thời gian tab này riêng, ghi `reports/perf.md`. Vượt 2,5 s → cân nhắc tải nhóm cột theo
   từng khối (tải Thu mua+Tiêu thụ trước, Tồn kho/Hợp đồng/Tuân thủ đổ sau) thay vì tối ưu SQL.

## Todo
- [ ] `unit_report_overview.py` (ghép 5 nguồn, không tính lại)
- [ ] Endpoint `/index/overview` (compare mặc định tắt)
- [ ] `overview-cols.ts` (ghi rõ đơn vị tính + mốc thời gian mỗi cột)
- [ ] `OverviewTab.tsx` + nút nhảy sang tab chi tiết
- [ ] Test đối soát với 5 tab gốc **và** với `period-report`
- [ ] Đo hiệu năng

## Success criteria
- Mọi ô của một đơn vị trên Tổng quan **bằng đúng** ô tương ứng ở tab gốc (sai số 0).
- `qty_material` + `% KH thu mua` khớp `Báo cáo tổng hợp` cùng kỳ (điều kiện của QĐ-1).
- Ô "Ngày lấy số" của dòng khu vực **trống**; của dòng đơn vị hiện đúng ngày thật.
- Bấm "Xem chi tiết → Tiêu thụ" mở tab Tiêu thụ đã lọc sẵn đúng đơn vị, kỳ giữ nguyên.
- Đơn vị chưa nộp gì trong kỳ: mọi ô trống, **không** hiện 0 — và vẫn có dòng (để thấy ai chưa nộp).
- `uv run pytest -q` xanh · `pnpm build` xanh.

## Risk
| Rủi ro | Giảm thiểu |
|---|---|
| Tự tính lại số cho "gọn" → 2 cách tính lệch nhau | Cấm trong comment đầu file + test đối soát từng ô |
| Tab nặng nhất, mở đầu tiên → cảm giác chậm | Compare tắt mặc định; nếu vẫn chậm thì đổ theo khối (bước 6) |
| Lệch với Báo cáo tổng hợp làm mất niềm tin | Test bước 5 là **điều kiện chốt** của QĐ-1 |
| Ô trống bị hiểu là 0 | Hiện `—` + chú thích dưới bảng |

## Security
Chỉ đọc, cap `unit_daily` mức Xem.

## Next steps
Phase 09 thêm sheet "Tổng quan" vào file Excel.
