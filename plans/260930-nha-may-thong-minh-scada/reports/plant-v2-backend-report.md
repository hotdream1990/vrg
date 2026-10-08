# Báo cáo backend — Sơ đồ vận hành v2 (bám ảnh RELCO) · 01/10/2026

Trạng thái: **xong** · Không commit · Không sửa `apps/web` · Không chạm SCADA thật.

## File
| File | Dòng | Việc |
|---|---|---|
| `apps/api/app/services/plant_layouts/phu_rieng.json` | 139 | Khu mủ vào vẽ lại theo ảnh RELCO; 3 khu còn lại thêm `"hidden": true` (dữ liệu giữ nguyên, đã so từng node) |
| `apps/api/app/services/scada_plant_layout.py` | 121 | `visible_areas`, `public_layout` (bản sao nông, không sửa cache); `find_area`/`area_tags`/`all_tags` bỏ khu ẩn; docstring ghi trường v2 |
| `apps/api/app/routers/smart_factory_plant.py` | 64 | `/plant/layout` trả `public_layout` (chỉ khu hiện) |
| `apps/api/tests/test_scada_plant_layout.py` | 199 | test khu ẩn, trường v2, RELCO (variant · cột nhiệt · badge · mũi tên chỉ trái · chữ không đè chữ · vùng `usage_box` trống thiết bị) |
| `apps/api/tests/test_smart_factory_plant_api.py` | 177 | layout chỉ còn `khu-mu-vao`; live khu ẩn → 404, không chạm SCADA; câu đọc không có tag khu ẩn |

Công cụ (không nằm trong app): `reports/plant-layout-preview/gen_khu_mu_vao_v2.py` (sinh khu mủ vào từ toạ độ ẢNH,
chạy lại được) · `preview_v2.py` (phủ khung/khối chữ lên ảnh RELCO + dò chồng) · ảnh `v2-khu-mu-vao-nho.png`, `v2-khu-mu-vao-lon.png`.

## Hành vi
- `/plant/layout` → `areas` = `["khu-mu-vao"]`, không có trường `hidden`. `/plant/live?area=<khu ẩn>` → 404 trước khi đọc SCADA.
- `all_tags` chỉ gồm tag khu hiện + điện: **97 tag**, câu OPENQUERY 2.474 ký tự (bật lại cả 4 khu vẫn < 8 KB — có test).
- Test "mọi tag thật nằm đúng 1 khu" vẫn tính cả khu ẩn → bật lại chỉ cần bỏ `hidden`.

## Bố cục Khu mủ vào (quy đổi X = x − 110 · Y = (y − 140) × 1.047)
- Đo trên ảnh phóng to có lưới (webp; ảnh nét hơn cùng khung, đã đối chiếu). Mọi node có `info_xy`; nhiệt độ có `temps_xy`
  (CM1–3, CC1: 1 cột; C3T1, CCS1, CCS2: 2 cột). `variant`: `mill` CM1–3 · `creper` CCS1–2, C3T1 · CC1 để mặc định.
- Decor: 3 máng/bàn (`basin`), ống C3T1 → vòng dưới → BTCS1, ống ngắn đầu VT2 → phễu C3T1, 7 badge `pID`, 2 `arrow_text`
  có `text_xy` ("Từ vít tải ngang" chỉ TRÁI, đầu mũi tên ở (1145, 793) — đúng mô tả giao việc). `links: []`. `usage_box` giữ nguyên
  (web tạm tắt), không thiết bị/chữ nào nằm trong vùng này (có test).
- Thứ tự node: băng tải đứng SAU máy nó đè lên (BTCS2 sau CCS1…) để vẽ đè đúng như RELCO; TL1 trước CC1.
- Dò chồng với 2 cỡ khối chữ (cỡ RELCO ~80×55 và cỡ web ước ~105×64): **0 chỗ chồng** chữ–chữ / chữ–thân (máy khuấy tính theo
  hình chân vịt + hộp motor của icon web hiện tại).

## Lệch có chủ đích so với ảnh RELCO (để không đè chữ ở cỡ web)
- QM1/QM2: khối số lùi ~18 px lên trên (khối rộng hơn sẽ chạm vít tải VT1/VT2).
- C3T1: khối số lên ~35 px (tránh góc trên-phải thân máy).
- TL1: khối số dời xuống-trái (~40 px), nằm dưới băng BTCS3 thay vì chen giữa băng và bàn.
- CC1: nhiệt độ dời trái-lên ~12 px; MLM1–6 khối số lên 4–10 px; badge pID dời trái vài px khỏi thân máy.
- Chữ mũi tên giữ kiểu viết thường của app ("Đến vít tải ngang"), RELCO viết hoa từng chữ.

## Kiểm tra
- `uv run pytest -q tests/test_scada_*.py tests/test_smart_factory*.py`: **164 passed** (có DB).
- `ruff check app/ tests/test_scada_plant_layout.py tests/test_smart_factory_plant_api.py`: sạch.
- Toàn bộ `pytest -q`: 949 passed, 5 skipped, **4 failed không liên quan** (`test_sales_contract.py` ×3, `test_unit_series.py` ×1 — dữ liệu DB dev; báo cáo trước đã ghi 3 lỗi sales_contract có sẵn).

## Câu hỏi mở (cho FE / chủ dự án)
1. Quy ước điểm neo mà web cần khớp: `badge` (x, y) = **góc trên-trái** (như basin/info_xy); `text_xy` y = **giữa dòng chữ**.
   FE hiểu khác (vd tâm) thì báo để đổi số.
2. `info_xy` = góc trên-trái cả khối, tính cả cột đèn "R" bên trái; nhãn in đậm nằm trên hàng ô số.
3. BC1 không có Hz/A → khối chỉ gồm nhãn + đèn (ước 60 rộng).
