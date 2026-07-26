# Phân tích dữ liệu & khoảng trống — Dashboard + biểu mẫu lọc báo cáo đơn vị

> Nguồn yêu cầu: khách hàng (Ban TTKD) — 26/07/2026. Mục đích: **theo dõi / kiểm tra số liệu các đơn vị nhập**.

## 1. Dữ liệu hiện có (nguồn sự thật)

| Bảng | Khoá | Nội dung |
|---|---|---|
| `unit_daily_report` | (as_of, company, kind) | `payload` **jsonb**; `kind` = `purchase` \| `consumption` |
| `unit_stock_contract` | id | HĐ đã ký chưa giao — bản ghi có **vòng đời riêng** (start_date → delivered_date) |
| `unit_purchase_plan` | (year, company) | KH thu mua năm, đã ký HĐ dài hạn, chuyển tiếp năm trước |
| `member_unit` | name | `region` (khu vực), `country`, `currency`, `has_factory`, `has_purchase_plan` |
| `member_region` | name | Danh mục khu vực |
| `fact_price` (source=`vrg`) | (as_of, grade=công ty, price_type) | Đơn giá mủ nước (`purchase`) / mủ chén (`purchase_cup`) — **đồng/độ TSC** |

### Cấu trúc payload (apps/api/app/services/unit_daily_fields.py)

**`kind='purchase'`** — ô phẳng + 1 bảng nhiều dòng:
- `latex_wet` (tấn), `coagulum` (tấn) — sản lượng mủ nước / mủ chén
- `finished[]` = thu mua **thành phẩm**: `{grade, qty(tấn), price, ccy(VND|USD), fx}`
- `cup_basis` = `tsc|drc`; `no_purchase` = cờ ngày không tổ chức thu mua
- Đơn vị nước ngoài: `price_latex_local`, `price_cup_local`, `fx_purchase`
- ⚠ **Đơn giá mủ nước/chén không nằm trong payload** — lấy từ `fact_price` theo (công ty, ngày)

**`kind='consumption'`** — 2 bảng bán + 2 khối tồn kho:
- `sales[]` (mủ **thu mua**) và `sales_own[]` (mủ **khai thác**) — mỗi dòng:
  `{code, contract: long_term|spot, channel: export|domestic, grade, qty, price, ccy, fx, warehouse_date, invoice_date, 3 ô đính kèm}`
- `revenue` (tổng doanh thu ngày, base = đồng), `purchased_sold_*`, `finished_sold_*`
- `stock_not_warehoused[]`, `stock_warehoused[]` = `{grade, qty}`; `stock_material` (tấn quy khô)
- Khối "đã ký HĐ chưa giao" **không lưu ở payload** → tính từ `unit_stock_contract`

## 2. Màn hình đang có

| Màn | Route | Khả năng lọc |
|---|---|---|
| Báo cáo thu mua / tiêu thụ / tồn kho | `/bao-cao-thu-mua`, `/bao-cao-tieu-thu`, `/bao-cao-ton-kho` | Nhập liệu + lưới **1 ngày** toàn đơn vị; timeline theo khoảng ngày |
| Thống kê hợp đồng | `/thong-ke-hop-dong` | Đơn vị · trạng thái · khoảng ngày · tìm số HĐ/chủng loại |
| Báo cáo tổng hợp | `/bao-cao-tong-hop` | **Chỉ** loại biểu + khoảng ngày; 1 dòng/đơn vị, cột cố định, xuất Excel |

## 3. Khoảng trống so với yêu cầu

1. **Không lọc được ở mức chi tiết.** `period_report` gộp thẳng lên mức đơn vị (`_purchase_rows` / `_consumption_rows`) — mất chủng loại, loại HĐ, hình thức HĐ. Muốn lọc phải **làm phẳng (flatten)** các mảng jsonb thành *dòng chi tiết* trước khi gộp.
2. **Không có bộ lọc khu vực** ở bất kỳ màn nào (dữ liệu đã có ở `member_unit.region`, mới chỉ hiển thị 1 cột).
3. **Tiêu thụ và tồn kho dính chung một bảng** ~30 cột — đúng như khách phản ánh "quá nhiều thông tin".
4. **Không có dòng tổng + bình quân theo bộ lọc** (hiện chỉ có Tổng cộng cột cố định, giá/% để trống).
5. **Chưa có màn kiểm tra tình trạng nộp** — mục đích chính "theo dõi kiểm tra số liệu các đơn vị nhập" cần biết *đơn vị nào chưa nhập ngày nào*, hiện phải mở từng ngày.

## 4. Bẫy nghiệp vụ phải xử lý (quan trọng)

| # | Vấn đề | Ảnh hưởng |
|---|---|---|
| B1 | **Đơn vị tính giá không đồng nhất**: mủ nước/chén = *đồng/độ TSC*; thành phẩm & giá bán = *triệu đ/tấn* (hoặc USD/tấn) | Không tồn tại **một** con số "đơn giá thu mua BQ" — phải tách ≥3 chỉ tiêu BQ |
| B2 | `cup_basis` có thể là **TSC hoặc DRC** tuỳ đơn vị | Gộp BQ mủ chén giữa 2 cơ sở tính là sai → tách hoặc ghi chú rõ |
| B3 | Dòng bán **ccy=USD thiếu `fx`** → doanh thu = null; code hiện tại cộng như 0 | Giá bán BQ bị kéo xuống âm thầm → phải **đếm & cảnh báo** số dòng thiếu tỷ giá |
| B4 | Đơn vị Lào/Campuchia dùng `price_*_local` + `fx_purchase`; `period_report` hiện **chỉ đọc giá VND** từ `fact_price` | BQ thu mua bỏ sót đơn vị nước ngoài |
| B5 | **Tồn kho là số THỜI ĐIỂM**, không cộng dồn | "Lọc theo thời gian" phải hiểu là *tồn tại một mốc* (mặc định ngày cuối kỳ **có số liệu** của từng đơn vị), không phải tổng các ngày |
| B6 | HĐ ký chưa giao **nằm trong** tồn kho thành phẩm | Không được cộng thêm cũng không trừ ra — chỉ báo riêng (đúng như khách yêu cầu tách tab) |
| B7 | `sales` (mủ thu mua) và `sales_own` (mủ khai thác) nhập riêng, tổng cộng chung | Bảng tiêu thụ cần cột/bộ lọc **Nguồn mủ**, nếu không sẽ không đối chiếu được với biểu Thu mua |
| B8 | Ngày `no_purchase=true` khác ngày mua được 0 tấn | Đếm "ngày không thu mua" riêng, không tính vào mẫu số BQ |

## 5. Hướng kỹ thuật đề xuất

**Backend** — thêm service `unit_report_query.py` (đọc, không ghi):
- `flatten_purchase(rows)` → dòng: `(as_of, company, region, material: latex|cup|finished, grade, qty, price, price_unit, ccy, fx, revenue_vnd)`
- `flatten_consumption(rows)` → dòng: `(as_of, company, region, source: sales|sales_own, code, contract, channel, grade, qty, price, ccy, fx, revenue_vnd, warehouse_date, invoice_date)`
- `stock_snapshot(...)` → tồn tại mốc ngày, theo (company, grade, block)
- Lọc + gộp (`group_by`) trên các dòng đã phẳng; dùng lại `unit_daily_repo.in_range()` (đã có sẵn, đã lọc payload rỗng).
- Quy đổi tiền dùng chung 1 hàm `line_revenue_vnd()` (mirror `lib/unit-daily-consumption.ts`) — **cùng quy tắc với form nhập**, tránh lệch số.
- Endpoint mới dưới `/api/unit-daily/analytics/*`, quyền `require_cap("unit_daily")` mức **Xem**; member giới hạn theo `member_units` như các router hiện tại.
- Quy mô dữ liệu nhỏ (≈30 đơn vị × 365 ngày) → flatten bằng Python là đủ, **không cần** `jsonb_array_elements` phức tạp (KISS).

**Frontend**:
- 1 component lọc dùng chung `ReportFilterBar` (đơn vị multi · khu vực multi · preset + khoảng ngày · các select đặc thù) — DRY cho cả 3 màn, mỗi file < 200 dòng.
- 3 trang riêng (Thu mua · Tiêu thụ · Tồn kho) + tab "HĐ ký chưa giao" tách riêng; mỗi bảng có **dòng tổng cuối** (Tổng SL + BQ) đúng theo bộ lọc.
- Dashboard: KPI theo bộ lọc + **ma trận tình trạng nộp** (đơn vị × ngày: đã nhập / chưa nhập / không thu mua).

## 6. Tái sử dụng được ngay
- `member_unit_repo.list_units()` → danh sách đơn vị + khu vực cho bộ lọc.
- `member_region_repo.active_names()` → danh mục khu vực.
- `UNIT_STOCK_GRADES` (backend) ↔ `GRADES` (web) → danh mục chủng loại.
- `unit_period_excel.build_period_xlsx` → khuôn xuất Excel (cần bản tổng quát theo cột động).
- `StockContractHistoryPage` + `/contracts/history` → dùng luôn cho tab HĐ ký chưa giao, chỉ bổ sung lọc **khu vực** + **chủng loại**.
