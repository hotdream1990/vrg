# Báo cáo nhánh A — Backend Nhà máy thông minh (SCADA)

Ngày 30/09/2026 · Trạng thái: **XONG** (chưa commit, theo yêu cầu)

## File
Tạo mới (`apps/api/`):
| File | Dòng | Vai trò |
|---|---|---|
| app/services/scada_historian_sql.py | 124 | regex định danh, dựng OPENQUERY (kỳ theo giờ · số mới nhất 10'), đọc kết quả (`map_rows`: khớp cột không phân biệt hoa thường, DateTime → tròn giây, nhận cả chuỗi datetime2) |
| app/services/scada_client.py | 176 | pymssql connect/close, `read_meters` (1 kết nối, 2 truy vấn), `probe`, `check_connection`, `friendly_error` |
| app/services/scada_daily_meters.py | 197 | ghép 4 thanh ghi, thuật toán ngày, summary, intensity, `build_report` (thuần, nhận `now`) |
| app/services/scada_factory_repo.py | 184 | CRUD `scada_factory`, kiểm hợp lệ, audit (`password_changed`, không bao giờ log mật khẩu) |
| app/services/scada_meters_excel.py | 151 | Excel: 4 cột/chỉ số (Đầu · Cuối · Tiêu thụ · Ghi chú cờ), 3 dòng tổng hợp |
| app/routers/smart_factory.py | 88 | `/factories`, `/meters/daily`, `/meters/daily.xlsx` |
| app/routers/smart_factory_admin.py | 75 | `/admin/factories` GET/POST/PUT/DELETE + `/{id}/test` |
| tests/test_scada_historian_sql.py | 85 | builder + chặn injection |
| tests/test_scada_daily_meters.py | 197 | mọi nhánh thuật toán |
| tests/test_smart_factory_api.py | 284 | API + map lỗi pymssql |

Sửa: `app/core/db.py` (+21, DDL `scada_factory`) · `app/core/permissions.py` (+3, cap `smart_factory` 1 cấp, có trong EXECUTIVE_CAPS) · `app/main.py` (+6, gắn 2 router) · `pyproject.toml` + `uv.lock` (`pymssql>=2.3` → 2.4.2, lock có wheel manylinux x86_64 cp312).

KHÔNG sửa `infra/db/init/02-schema.sql`: file chỉ có 9 bảng (thiếu audit_log, sales_contract, edit_request…), không đồng bộ với db.py.

## Kiểm thử
- Test mới: 29 (API) + 17 (ngày) + 28 (SQL) — xanh hết. `ruff check app tests`: sạch.
- Toàn suite: **860 pass · 3 fail · 5 skip**. 3 test fail đều ở `test_sales_contract.py` (tìm khách hàng) và **đã fail sẵn trên HEAD sạch** (đã chạy lại ở worktree HEAD để xác nhận). Nguyên nhân: DB dev là bản sao prod, có khách thật tên "Đồng Nai…", "Sintex…" lọt vào kết quả tìm kiếm. Không liên quan thay đổi này.
- Dữ liệu test được dọn hết (0 dòng scada_factory, 0 user `sf_*`, 0 dòng audit).
- Đã chạy thử pymssql THẬT với container `vrg-scada-fake` (SQL Server 2022): sai mật khẩu + cổng đóng. KHÔNG đọc file của nhánh C nên chưa chạy e2e qua linked server — để nhánh D làm.

## Phát hiện khi chạy pymssql thật (đã sửa)
1. `exc.args` là MỘT tuple `((mã, b"…"),)`. Phải mở lớp ngoài, nếu không thì mất mã lỗi và detail lộ repr bytes.
2. pymssql giữ mã lỗi của lần TRƯỚC trong cùng tiến trình: "Connection refused" vẫn mang mã 18456. Vì vậy ưu tiên CHỮ trong thông điệp hơn mã, và mã 18456 chỉ xét lúc đang kết nối.
3. FreeTDS mới báo "TDS server is unavailable" (không phải "Adaptive Server…"). Đã khớp theo "server is unavailable".
4. Lỗi sai database kèm luôn "Login failed" → nhánh database phải xét trước nhánh mật khẩu.

## Chỗ hợp đồng không nói rõ — đã chọn
- `summary.*.total` và `avg_per_day` = **null** khi `days_with_data = 0` (không trả 0, tránh hiểu nhầm là "không tiêu thụ").
- Ngày sai định dạng → 400. Sai kiểu JSON (vd `port: "abc"`) → 422 (chuẩn FastAPI).
- `POST /admin/factories/{id}/test` với id không tồn tại → 404. Nhà máy đang tắt vẫn thử được.
- Làm tròn: điện/nước 3 số lẻ, bành là số nguyên, `kwh_per_bale`/`m3_per_bale` 3 số lẻ. Tổng = cộng số đã làm tròn của từng dòng (khớp tổng cột trên bảng).
- `energy_tags`: bỏ phần tử rỗng trước khi đếm 0/1/4. Test kết nối: `values` chỉ có các chỉ số đã khai tag.
- Hôm nay: số mới nhất chỉ dùng nếu `open_at ≤ ts < D+1 00:00` (chặn trường hợp đồng hồ SCADA đã sang ngày mới).

## Việc còn treo
1. `app/core/audit_meta.py` (ngoài phạm vi file của nhánh này) chưa có `"scada_factory"`. Hệ quả: Nhật ký hoạt động hiện tên khoá thô, và lọc theo nhóm này bị 400. Đề nghị nhánh D thêm `"scada_factory": "Cấu hình SCADA nhà máy"`.
2. Nhánh D cần xác nhận với Historian thật/giả:
   - Cyclic + `wwResolution` có trả dòng ĐÚNG mốc 00:00 đầu kỳ không (thuật toán dựa vào điều này).
   - DateTime trả về dạng datetime hay chuỗi (đã xử lý cả hai).
3. Deploy: image vá phải `uv sync` lại để có pymssql, không chỉ thay app/web.
4. `plan.md` chưa đánh dấu nhánh A xong (file ngoài phạm vi file; để agent điều phối cập nhật).
