# Báo cáo backend — HĐ dài hạn phải giao · cảnh báo đơn giá sai đơn vị tính (26/09/2026)

Trạng thái: **xong**. Chưa commit (theo yêu cầu).

## File đã sửa / tạo
| File | Việc |
|---|---|
| `apps/api/app/services/contract_backlog.py` (MỚI, 138 dòng) | `backlog_on(as_of, companies, grades, *, block3=None)`, `finalize()`, `roll()` |
| `apps/api/app/services/contract_backlog_sql.py` (MỚI, 51 dòng) | `MASTER_SQL` — cam kết + đã giao của mọi HĐ mẹ trong **1 truy vấn** |
| `apps/api/app/services/sales_contract_report.py` | `_BLOCK3_SQL` mang thêm `contract_type`, `master_id`; item của `undelivered_on` có thêm 2 khoá này. Cách tính số KHÔNG đổi |
| `apps/api/app/routers/sales_contracts.py` | `_consumption` thêm `backlog` + `backlog_as_of`; khối 3 chỉ quét 1 lần, dùng lại cho backlog |
| `apps/api/app/services/sales_contract_consumption_excel.py` | bỏ phần sheet tổng hợp sang file mới (237 → 201 dòng) + câu ghi chú phân biệt 2 khái niệm |
| `apps/api/app/services/sales_contract_consumption_summary.py` (MỚI, 73 dòng) | **ngoài danh sách được giao** — tách ra để file Excel không vượt 200 dòng. Cột tổng hợp + dòng Tổng cộng |
| `apps/api/app/services/unit_report_consumption.py` | `bad_price_lines`, cờ `bad_price` trên dòng chi tiết, cảnh báo, `sale_price_ceiling()`, `price_ceiling` trong kết quả |
| `apps/api/app/services/unit_dashboard.py` | `bad_price_lines` vào `_CON_TOTALS` + breakdown tiêu thụ |
| `apps/api/app/services/unit_dashboard_targets.py` | chặn % doanh thu khi có `bad_price_lines`, note nêu tên đơn vị, khoá `scope_done` trên mọi item |
| `apps/api/tests/test_contract_backlog.py` (MỚI) | 10 ca |
| `apps/api/tests/test_unit_dashboard.py` | +1 ca bad_price |

Không đụng `unit_report_query.py`, `unit_dashboard_outlook*`, `routers/unit_dashboard.py` (việc của agent chính) và cả `apps/web`.

## Shape thực tế so với api-contract.md
- `Backlog`: **khớp đủ khoá và đúng tên** như mục 1. Item HĐ mẹ: `id, code, master_type, customer_id, sign_date, expiry_date, committed, delivered, remaining, pct, expired`.
- `backlog_on` có thêm tham số keyword `block3=` (không bắt buộc, không phá chữ ký trong contract).
- `/consumption`: `by_company`, `undelivered` giữ nguyên; thêm `backlog` (đã gộp đơn vị sáp nhập, tính lại % sau khi gộp) + `backlog_as_of = date_to`. Item của `undelivered` có thêm `contract_type`, `master_id`.
- `consumption_report`: `totals`/từng dòng có `bad_price_lines` (int); dòng chi tiết (`group_by=none`) có `bad_price` (bool); **thêm** `price_ceiling` (số) ở gốc kết quả. Chỉ tiêu dashboard: mỗi item có thêm `scope_done`.
- Excel sheet "Đơn vị": cột cũ đổi tên thành **"Đã ký HĐ chưa giao (khối 3)"**; thêm "HĐ chuyến chưa giao", "HĐ dài hạn còn phải giao", **"HĐ chưa khai loại chưa giao"** (thêm để chuyến + dài hạn + chưa khai cộng ra đúng "Tổng phải giao"), "Tổng phải giao", "Cam kết HĐ mẹ", "Đã giao theo HĐ mẹ", "% thực hiện HĐ mẹ" (dòng Tổng cộng tính lại tỷ lệ, không cộng).

## Kiểm thử
- `ruff check` các file đã sửa: **All checks passed**. `import app.main`: ok.
- Docker kẹt nên chạy trên Postgres 14 sạch (không timescaledb):
  - DB của agent chính `127.0.0.1:5444/vrg_caosu`: `test_contract_backlog.py test_unit_dashboard.py test_master_contract.py` → **47 passed**. Lần chốt cuối: 3 file trên + `test_unit_analytics.py` → **76 passed, 0 failed**. Không có file `tests/test_unit_report*.py` (glob không khớp); `consumption_report` được test ở `test_unit_analytics.py` nên chạy file đó thay.
  - DB riêng (đã dọn): 4 file trên + `test_sales_contract.py` → **101 passed**; **cả bộ test → 737 passed, 1 failed, 8 skipped**.
  - Ca đỏ duy nhất: `test_edit_request_contract_rules.py::test_new_delivery_reusing_existing_number_is_refused_before_request` (nhận 403 hàng rào cửa sổ nhập liệu, chờ 400 báo trùng số). Chạy riêng file đó vẫn đỏ; đường đi là lưu hợp đồng + cửa sổ nhập liệu, **không qua file nào tôi sửa**. Không `git stash` để đối chứng vì các agent khác đang sửa cùng cây thư mục.
- Thử đột biến: bỏ luật "không đếm trùng" → 3 ca đỏ; bỏ "lấy max với phụ lục đã ký" → 1 ca đỏ. Test có giữ được luật.

## Điểm còn nghi ngờ / cần chốt
1. **Lọc chủng loại và HĐ mẹ "được tính"**: HĐ mẹ có được tính hay không xét trên cam kết CHƯA lọc (hồ sơ có cam kết là HĐ mẹ được tính, bất kể đang lọc gì). Lọc chỉ áp vào số cam kết/đã giao. Nếu xét theo số đã lọc thì phụ lục của nó sẽ nhảy sang ô "dài hạn ngoài HĐ mẹ" khi đổi bộ lọc. HĐ mẹ nào lọc xong không còn số nào thì không hiện trong `items` và không đếm vào `masters`.
2. **HĐ mẹ hết hạn trong năm**: phụ lục còn nợ giao bị "nuốt" (không vào ô nào, đúng Q2/Q3). Nếu khách muốn vẫn thấy phần phụ lục đã ký này thì cần thêm ô riêng.
3. `backlog` bỏ qua bộ lọc khách hàng (`customer_id`), giống cột `undelivered` hiện nay.
4. Trần đơn giá đọc qua `config_repo.get_value` + mặc định trong `anomaly_types.THRESHOLDS` (`sale_price_ceiling()`). Hàm đọc sẵn có (`_thresholds`) nằm trong router `anomalies.py`: service import router thì ngược tầng, nên tôi viết hàm nhỏ riêng. Nên dời `_thresholds` về `anomaly_types` sau này để còn một chỗ.
5. Chú thích cũ trong `core/db.py` và `master_contract_clean.py` ghi "master_contract KHÔNG vào báo cáo sản lượng nào". Nay khối phải giao đọc bảng này, nên câu đó đã lỗi thời. Tôi không sửa vì 2 file này ngoài phạm vi được giao.
6. Dashboard đơn vị chưa có endpoint trả `backlog` theo phạm vi khu vực/Tập đoàn; api-contract chỉ giao cho `/consumption`. Nếu web cần thì `contract_backlog.backlog_on(as_of, sc["units"])` + `roll()` dùng lại được ngay.
7. Container Docker `vrg-backlog-test` của tôi vẫn đứng ở "Created" (Docker kẹt nên không xoá được). Khi Docker chạy lại: `docker rm -f vrg-backlog-test`.
