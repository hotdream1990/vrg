# Báo cáo backend — Sơ đồ vận hành (mimic SCADA)

Ngày 30/09/2026 · Trạng thái: **xong** · Không commit · Không sửa `apps/web` · Không chạm SCADA thật.

## File
| Loại | File |
|---|---|
| Mới | `apps/api/app/services/plant_layouts/phu_rieng.json` — bố cục 4 khu + `power` |
| Mới | `apps/api/app/services/scada_plant_layout.py` — loader (cache, `layout_keys`, `find_area`, `area_tags`); quy ước định dạng ghi ở docstring |
| Mới | `apps/api/app/services/scada_factory_validation.py` — tách `clean()` khỏi repo (repo sắp vượt 200 dòng) + kiểm `layout_key` |
| Mới | `apps/api/app/routers/smart_factory_shared.py` — `enabled_factory` + `guarded_read` (chuyển từ `smart_factory.py`, không copy) |
| Mới | `apps/api/app/routers/smart_factory_plant.py` — `GET /api/smart-factory/plant/layout`, `/plant/live` |
| Sửa | `scada_historian_sql.py` (TAG_RE cho dấu cách giữa tên; `latest_query(..., minutes)`), `scada_client.py` (`read_latest(factory, tags=None, minutes=10)`), `scada_read_guard.py` (`scope` trong khoá cache), `scada_factory_repo.py` (cột `layout_key`), `smart_factory.py` (dùng shared; `/factories` trả `layout_key`), `smart_factory_admin.py` (`layout_key` trong form), `core/db.py` (`ALTER TABLE scada_factory ADD COLUMN IF NOT EXISTS layout_key text`), `main.py` (gắn router, cap `smart_factory`), `core/access_meta.py` (nhãn trang `/nha-may-thong-minh/so-do-van-hanh`) |
| Test mới | `tests/test_scada_plant_layout.py`, `tests/test_smart_factory_plant_api.py`, `tests/fixtures/historian-tags-phu-rieng.json` (bản sao 209 tag thật — `plans/` chưa được track) |
| Test sửa | `test_scada_historian_sql.py`, `test_scada_read_guard.py`, `test_smart_factory_api.py` |
| Công cụ | `reports/plant-layout-preview/` — `gen_layout.py` (sinh JSON từ file tag), `fe_check.py` (dò chồng nhãn theo quy ước web), 4 ảnh xem trước `fe-*.png` |

## Hành vi
- `layout`: nhà máy tắt / không có / chưa gán `layout_key` → 404.
- `live?area=`: khu lạ → 404 **trước** khi đọc SCADA. Đọc tag của khu + 7 tag điện, cửa sổ 3 phút (Cyclic 1 phút), cache 5 s theo `(nhà máy, updated_at, scope="plant:<khu>")`, khoá theo nhà máy (429), lỗi 502 như `/meters/*`. Trả `{area, values: {tag: {value (2 số lẻ) | null, at | null}}}` — lấy dòng cuối **có số** của từng tag.
- Nhà máy không khai tag điện/nước/bành vẫn xem được sơ đồ (tag lấy từ bố cục).
- Admin: `layout_key` null / "" = gỡ; khoá không có file → 400. **Form không gửi `layout_key` thì giữ nguyên** (lưu từ form cũ không xoá mất sơ đồ).
- Kích thước câu OPENQUERY lớn nhất (khu mủ vào, 97 tag): 2.474 ký tự (< 8 KB).

## Test
- `pytest tests/test_scada_*.py tests/test_smart_factory*.py`: 161 passed.
- Toàn bộ `pytest -q`: 946 passed, 5 skipped, **3 failed có sẵn** ở `test_sales_contract.py` (không liên quan).
- `ruff check`: sạch.
- Thử driver trên SQL Server **giả lập** localhost:14330 (chỉ SELECT, đã tắt container sau khi thử): cột có dấu cách đi qua OPENQUERY + pymssql giữ nguyên tên (`MLM1 - Frequence`), `map_rows` khớp đúng.

## Điểm diễn giải (cần chủ dự án / nhà máy xác nhận)
1. **Quy ước toạ độ** đã khớp tin nhắn của FE: (x, y) = góc trên-trái khung, xoay quanh tâm, khối nhãn ở cạnh `label_pos` của khung CHƯA xoay, nhiệt độ ở cạnh đối diện, chữ `arrow_text` nối sau đầu mũi tên. Hệ quả:
   - Băng tải/vít tải nghiêng đặt nhãn **"left"** (đặt "top" theo khung chưa xoay sẽ đè thân nghiêng). Nếu web chuyển sang tính khối nhãn theo **hộp bao sau khi xoay** thì có thể đổi lại "top" cho giống RELCO (nhãn ở đầu trên băng tải).
   - Đoạn cuối mọi `arrow_text` hướng sang phải → "Từ vít tải ngang" vẽ dạng "▷ Từ vít tải ngang" đi vào BC1 từ bên trái (RELCO để ở mép phải).
   - `fe_check.py` báo 0 chồng lấn với cả cỡ khối nhỏ (~62 × 90) lẫn lớn (~80 × 100).
2. `PM - VoltAN/BN/CN` (điện áp pha) **không** đưa lên sơ đồ — hợp đồng chỉ có Volt AB/BC/CA · Current A/B/C · Power.
3. `QC01/QC02 - Vibration`: đơn vị **giả định `mm/s`**.
4. `XDT_bOutAuto` (chế độ Auto) dùng làm `status_tag` của XDT → "xanh" = đang Auto, không phải đang chạy.
5. 3 khu chưa có ảnh mẫu được **đoán** theo dòng chảy: VTN → C3T2 → BTCS4 → CCS3 → BTCS5 → CCS4 → BTCS6 → CCS5 → BTCS7 → CC2 (TL2) → BC2 → hầm sấy; TKMM1–2 → BTCLM1–4 → XDT → Z01–Z12, 6 quạt dưới hầm; SR → robot đếm bành. Vai trò TL1/TL2 chưa rõ → đặt cạnh CC, không nối `links`.
6. Khoá nhà máy dùng chung với `/meters/*`: SCADA chậm thì mỗi lượt hỏi 5 s có thể giữ luồng tới 15 s (`LOCK_WAIT_S`) rồi 429 — giữ như thiết kế cũ, chưa rút ngắn riêng cho sơ đồ (YAGNI).

## Còn phải làm khi deploy
- Cột `layout_key` tự thêm ở lần `ensure_schema` đầu tiên (DB dev đã có sau khi chạy test).
- Gán `phu_rieng` cho nhà máy Phú Riềng (Select trên web hoặc PUT admin).
- Lần đầu đọc SCADA thật với ~100 tag (có tag discrete + tên có dấu cách) nên có người theo dõi: tag sai → 502, admin thấy tên tag lỗi.
