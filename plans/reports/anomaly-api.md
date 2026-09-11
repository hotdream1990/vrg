# API + cấu hình ngưỡng — màn "Cảnh báo bất thường" (chỉ ADMIN)

## Endpoint đã làm (`/api/anomalies`, `apps/api/app/routers/anomalies.py`)

| Method | Path | Phân quyền | Việc |
|---|---|---|---|
| GET | `/api/anomalies` | admin | Quét (`anomaly_rules.scan`) trong `date_from`..`date_to` (mặc định 01/01 năm hiện tại → hôm qua). Trả kết quả kèm `thresholds` đang áp dụng. |
| GET | `/api/anomalies/config` | admin | Danh sách ngưỡng: `{key, label, hint, value, default}` — `value` lấy từ `app_config`, thiếu thì lấy `default`. |
| PUT | `/api/anomalies/config` | admin | Lưu ngưỡng (`body.values: {key: số}`). Chỉ nhận khoá có trong `THRESHOLDS`; số ≤ 0 hoặc không phải số → 400 tiếng Việt; khoá lạ bỏ qua êm. |
| GET | `/api/anomalies/export.xlsx` | admin | Xuất Excel: 1 sheet mỗi nhóm cảnh báo + sheet "Tổng quan". |

Phân quyền: gác **2 lớp** — router tự gắn `Depends(require_admin)` trên từng route (tự chạy độc lập kể cả nếu quên wiring), **và** `apps/api/app/main.py` include với `dependencies=[Depends(require_admin)]` (đúng kiểu `users`/`config`/`schedules`). Không dùng bất kỳ `DATA_CAPS` nào — test xác nhận editor có **mọi** quyền dữ liệu vẫn 403.

## Sinh cấu hình từ `THRESHOLDS` (`app/services/config_repo.py`)

- Thêm nhóm `{"id": "anomaly", "label": "Cảnh báo bất thường"}` vào `CONFIG_GROUPS`.
- `CONFIG_SPEC` nối thêm bằng generator expression lặp `anomaly_types.THRESHOLDS.items()` → mỗi khoá thành `{"key", "group": "anomaly", "secret": False, "label": spec["label"], "placeholder": spec["hint"]}`. Không chép tay — thêm ngưỡng mới trong `anomaly_types.py` tự động lên form Cấu hình chung (`/api/config`) **và** form riêng (`/api/anomalies/config`) mà không phải sửa thêm chỗ nào.

## `app/services/anomaly_export.py`

Dựng thẳng bằng openpyxl (không tái dùng `unit_analytics_excel` vì khuôn cột khác nhau: `columns:[{key,label}]` so với `Col=(key,label,unit)`):
- `_overview_sheet`: sheet đầu "Tổng quan" — tổng/nghiêm trọng/trung bình/nhẹ/số đơn vị + bảng liệt kê từng nhóm (nhãn · mức độ tô màu · số dòng · số đơn vị).
- `_group_sheet`: 1 sheet/nhóm, cột động theo `group["columns"]`, có `auto_filter` + `freeze_panes`.
- `_sheet_name`: cắt 31 ký tự (giới hạn Excel) + thêm hậu tố `(2)`, `(3)`... nếu hai nhãn trùng nhau sau khi cắt.

## Import muộn `anomaly_rules` (đang viết song song)

`app/services/anomaly_rules.py` **chưa tồn tại** lúc code phiên này (xác nhận bằng `git status` — chỉ thấy `anomaly_types.py`, không có `anomaly_rules.py`). Router import muộn trong `_scan()`:
```python
try:
    from app.services import anomaly_rules
except ImportError as exc:
    raise HTTPException(503, "Bộ luật quét bất thường chưa sẵn sàng (app/services/anomaly_rules.py)") from exc
```
→ Cả app KHÔNG sập lúc khởi động dù `anomaly_rules.py` chưa có; `GET ""` và `GET /export.xlsx` trả 503 rõ ràng cho tới khi người viết luật xong. `GET/PUT /config` không phụ thuộc `anomaly_rules` nên chạy đầy đủ ngay.

## Test — `tests/test_anomalies.py`

Style giống `tests/test_assistant.py` (TestClient · `user_repo.seed_admin()` · `pytestmark = skipif(not db_healthy())`). 6 test, phủ đúng checklist:
1. `test_admin_can_scan` — admin gọi `GET ""` không bị 403; chấp nhận `200` (đã có luật) hoặc `503` (luật chưa có), kiểm hình dạng response khi 200.
2. `test_editor_with_full_data_caps_still_forbidden` — tạo editor với `permissions=list(DATA_CAPS)` (mọi quyền dữ liệu) → cả 4 endpoint đều 403.
3. `test_config_lists_every_threshold` — `len(GET /config) == len(THRESHOLDS)`, mỗi dòng đủ `label`/`hint`/`default` đúng.
4. `test_put_config_roundtrip_then_restore` — PUT rồi GET lại đúng giá trị mới, `finally` trả về giá trị gốc (DB dùng chung).
5. `test_put_config_rejects_invalid_values` — số âm / chuỗi không phải số → 400; khoá lạ → `updated: 0`, không lỗi.
6. `test_export_xlsx_content_type` — content-type đúng `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, byte đầu `PK` (zip), chấp nhận 503 nếu luật chưa có.

### Output `uv run pytest tests/test_anomalies.py -q`
```
......                                                                   [100%]
6 passed, 1 warning in 2.95s
```

### Output `uv run pytest tests/ -q` (toàn bộ)
```
3 failed, 381 passed, 5 skipped, 1 warning in 165.83s (0:02:45)
FAILED tests/test_sales_contract.py::test_customer_is_per_unit_and_unique
FAILED tests/test_sales_contract.py::test_customer_search_runs_on_server
FAILED tests/test_sales_contract.py::test_search_ignores_vietnamese_marks
```
Đúng 3 test fail-sẵn do dữ liệu local (đã cảnh báo trước trong đề bài) — không liên quan tới thay đổi phiên này. Toàn bộ 381 test còn lại (gồm 6 test mới) pass.

### `uv run ruff check`
```
All checks passed!
```
(chạy trên `anomalies.py`, `anomaly_export.py`, `config_repo.py`, `main.py`, `test_anomalies.py`)

## File đã sửa/tạo

- TẠO `apps/api/app/routers/anomalies.py` (108 dòng)
- TẠO `apps/api/app/services/anomaly_export.py` (129 dòng)
- TẠO `apps/api/tests/test_anomalies.py` (109 dòng)
- SỬA `apps/api/app/main.py` — thêm import `anomalies` + 1 dòng `include_router`
- SỬA `apps/api/app/services/config_repo.py` — thêm nhóm `anomaly` + generator sinh `CONFIG_SPEC` từ `THRESHOLDS`

## Việc người khác cần làm / phối hợp

1. **`anomaly_rules.py`** (đang viết song song) phải export đúng `def scan(date_from: str, date_to: str, thresholds: dict[str, float]) -> dict` với khuôn `{date_from, date_to, groups:[{key,label,desc,severity,columns:[{key,label}],rows,count,units}], summary:{total,high,medium,low,units}}` — đúng những gì `anomaly_types.group()` đã đóng gói. Khi file này xuất hiện, `test_admin_can_scan`/`test_export_xlsx_content_type` sẽ tự chuyển từ nhánh 503 sang kiểm đầy đủ response — không cần sửa lại test.
2. Frontend (nếu có ở phiên khác): `GET /api/anomalies/config` trả `value` là **số** (không phải chuỗi) để bind thẳng vào input number; `PUT` gửi `{"values": {"KEY": number}}`.
3. Chưa deploy — sau deploy không cần cấp quyền gì thêm (màn hoàn toàn thuộc admin, không đi qua `DATA_CAPS`/permissions của user thường).
