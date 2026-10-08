# Hợp đồng API — Nhà máy thông minh (SCADA)

Mọi ngày dạng `YYYY-MM-DD`, mọi thời điểm dạng `YYYY-MM-DDTHH:MM:SS` (giờ nhà máy, UTC+7, KHÔNG kèm múi).
Lỗi theo chuẩn FastAPI hiện có: `HTTPException(status, detail: str)` — FE hiện `detail`.

## 1. Nhà máy (người có cap `smart_factory`)
`GET /api/smart-factory/factories` → chỉ nhà máy `enabled`, KHÔNG lộ thông tin kết nối
```json
{ "factories": [ { "id": 1, "name": "Nhà máy Phú Riềng",
                   "metrics": ["energy", "water", "bales"] } ] }
```
`metrics` = các chỉ số đã khai tag (tag trống → không có chỉ số đó).

## 2. Chỉ số theo ngày (cap `smart_factory`)
`GET /api/smart-factory/meters/daily?factory_id=1&date_from=2026-09-01&date_to=2026-09-30`
- Thiếu `date_from/date_to` → mặc định 30 ngày gần nhất tính cả hôm nay.
- `date_to` > hôm nay → kẹp về hôm nay. `date_from > date_to` hoặc kỳ > 92 ngày → 400.
- Nhà máy không tồn tại/tắt → 404. SCADA lỗi kết nối/truy vấn → **502** `detail` = lý do đọc được (không chứa mật khẩu).

```json
{
  "factory": { "id": 1, "name": "Nhà máy Phú Riềng" },
  "date_from": "2026-09-01", "date_to": "2026-09-30",
  "fetched_at": "2026-09-30T15:40:12",
  "metrics": [
    { "key": "energy", "label": "Điện năng", "unit": "kWh" },
    { "key": "water",  "label": "Nước",      "unit": "m³" },
    { "key": "bales",  "label": "Số bành",   "unit": "bành" }
  ],
  "rows": [
    { "date": "2026-09-01",
      "energy": { "open": 182575.997, "open_at": "2026-09-01T00:00:00",
                  "close": 184841.346, "close_at": "2026-09-02T00:00:00",
                  "used": 2265.349, "flag": null },
      "water":  { "...": "cùng cấu trúc" },
      "bales":  { "...": "cùng cấu trúc" } }
  ],
  "summary": {
    "energy": { "latest": 253616.98, "latest_at": "2026-09-30T15:39:00",
                "total": 70123.4, "avg_per_day": 2337.4, "days_with_data": 30 },
    "water":  { "...": "cùng cấu trúc" },
    "bales":  { "...": "cùng cấu trúc" }
  },
  "intensity": { "kwh_per_bale": 5.12, "m3_per_bale": 0.34 }
}
```
- Mỗi dòng chỉ có key của các chỉ số trong `metrics`.
- Một ô chỉ số: `open/close/used` là số hoặc `null`. `flag`:
  - `null` — đủ số, đúng mốc 00:00.
  - `"partial"` — mốc đầu/cuối không có số, đã dùng mẫu có số gần nhất TRONG ngày (open_at/close_at cho biết giờ thật).
  - `"reset"` — cuối < đầu (đồng hồ bị đặt lại / đọc lỗi) → `used = null`.
  - `"no_data"` — cả ngày không có số → open/close/used đều null.
  - `"in_progress"` — ngày hôm nay (close = số mới nhất).
- `summary.*.total` = tổng `used` (bỏ null); `avg_per_day` = total / `days_with_data`; `latest` = số mới nhất (null nếu truy vấn phụ không có số).
- `intensity`: tổng điện (nước) / tổng số bành, chỉ cộng những ngày CẢ HAI chỉ số có `used`; `null` nếu thiếu chỉ số hoặc tổng bành = 0.
- Mỗi dòng còn có `kwh_per_bale`, `m3_per_bale` (cùng quy tắc, theo ngày; `null` khi bành = 0/thiếu).
- Hàng sắp theo ngày TĂNG DẦN.

`GET /api/smart-factory/meters/daily.xlsx?...cùng tham số` → file Excel (tên `chi-so-dien-nuoc-banh_<slug-nha-may>_<from>_<to>.xlsx`).

## 3. Cấu hình kết nối (CHỈ admin)
`GET /api/smart-factory/admin/factories`
```json
{ "factories": [ {
  "id": 1, "name": "Nhà máy Phú Riềng", "host": "10.0.0.5", "port": 1433,
  "username": "scada_ro", "password_set": true,
  "database": "Runtime", "linked_server": "INSQL",
  "energy_tags": ["PM_EnergyReal0", "PM_EnergyReal1", "PM_EnergyReal2", "PM_EnergyReal3"],
  "water_tag": "Water_TotalVolume", "bales_tag": null,
  "enabled": true, "updated_at": "2026-09-30T15:00:00", "updated_by": "admin" } ] }
```
`POST /api/smart-factory/admin/factories` · `PUT /api/smart-factory/admin/factories/{id}` — body:
```json
{ "name": "...", "host": "...", "port": 1433, "username": "...", "password": "...",
  "database": "Runtime", "linked_server": "INSQL",
  "energy_tags": ["..."], "water_tag": "...", "bales_tag": "...", "enabled": true }
```
- `password`: POST bắt buộc; PUT bỏ trống/`null` = giữ mật khẩu cũ.
- `energy_tags`: 0, 1 hoặc 4 phần tử (4 = thanh ghi R0..R3 theo thứ tự cao→thấp; 1 = tag đã là kWh). Khác → 400.
- Tag / linked server / database phải khớp `^[A-Za-z0-9_.$#-]{1,128}$` (linked server & database: `^[A-Za-z0-9_]{1,128}$`) → sai = 400. `water_tag`/`bales_tag` rỗng = không dùng.
- Trùng tên → 409. Trả về `{ "factory": {...như GET...} }`.

`DELETE /api/smart-factory/admin/factories/{id}` → `{ "ok": true }`

`POST /api/smart-factory/admin/factories/{id}/test` → luôn 200:
```json
{ "ok": true, "detail": "Kết nối thành công",
  "server_version": "Microsoft SQL Server 2016 ...",
  "latest_at": "2026-09-30T15:39:00",
  "values": { "energy_kwh": 253616.98, "water_m3": 12473.64, "bales": 21397 },
  "raw": { "PM_EnergyReal0": 0, "PM_EnergyReal1": 0, "PM_EnergyReal2": 3869, "PM_EnergyReal3": 55812,
           "Water_TotalVolume": 12473.64 } }
```
Lỗi → `{ "ok": false, "detail": "<lý do>" }` (các khoá còn lại có thể vắng).

## Sửa đổi sau review (30/09/2026)
- `summary.<m>.days_complete` (mới) = số ngày có ô `flag == null`. `avg_per_day` = tổng `used` của CÁC NGÀY ĐỦ SỐ / `days_complete` (null nếu 0). `total` vẫn cộng mọi ngày có `used` (kể cả hôm nay, partial). `days_with_data` giữ nguyên nghĩa (số ngày có `used`).
- `intensity` và `kwh_per_bale`/`m3_per_bale` theo ngày: chỉ tính khi CẢ HAI ô có `flag == null`.
- Cờ `reset` còn gắn khi trong ngày có bất kỳ lần giảm nào giữa hai mẫu kề nhau (không chỉ cuối < đầu).
- `/meters/daily` (+ `.xlsx`): nhà máy chưa khai tag → **400**; đang có lượt đọc khác của cùng nhà máy quá lâu → **429**; lỗi SCADA → 502 — admin nhận `detail` đầy đủ, người khác nhận câu ngắn "Chưa đọc được số liệu SCADA của nhà máy … — đã ghi nhận, vui lòng báo quản trị viên." (chi tiết ghi log).
- PUT `/admin/factories/{id}`: đổi `host`/`port`/`username` mà `password` rỗng → **400** "Đổi máy chủ, cổng hoặc tài khoản thì phải nhập lại mật khẩu." Tag trùng nhau (không phân biệt hoa thường) → 400.
- POST `/admin/factories/{id}/test`: thêm `server_time` (chuỗi `YYYY-MM-DDTHH:MM:SS±HH:MM` giờ máy SQL Server) và `warnings: string[]` (vd múi giờ khác +07:00, đồng hồ lệch > 5 phút, 10 phút gần nhất không có số, chỉ số nào đó null). `values` lấy số MỚI NHẤT có giá trị của TỪNG chỉ số.

## Số lũy kế thời gian thực (30/09/2026 — theo góp ý chủ dự án)
`GET /api/smart-factory/meters/live?factory_id=1` (cap `smart_factory`) → số lũy kế MỚI NHẤT của từng chỉ số:
```json
{ "factory": { "id": 1, "name": "Nhà máy Phú Riềng" },
  "metrics": [ { "key": "energy", "label": "Điện năng", "unit": "kWh" } ],
  "values": { "energy": { "value": 253844.749, "at": "2026-09-30T21:57:49" } } }
```
Web hỏi lại mỗi 10 giây (tab ẩn thì dừng); server cache 5 giây dùng chung. Lỗi như `/meters/daily` (400 · 404 · 429 · 502).
Màn chỉ số bỏ dòng giải thích, thẻ TB/ngày và thẻ Định mức/bành — thẻ KPI chỉ còn số lũy kế + giờ đọc.
