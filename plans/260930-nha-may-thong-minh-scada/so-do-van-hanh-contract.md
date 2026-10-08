# Sơ đồ vận hành (mimic SCADA) — hợp đồng BE ↔ FE

Menu: Nhà máy thông minh → **Sơ đồ vận hành** (`/nha-may-thong-minh/so-do-van-hanh`, cap `smart_factory`).
Mẫu: màn RELCO "KHU MỦ VÀO" (ảnh `images/9.webp` trong phiên) — 4 khu: Khu mủ vào · Vít tải ngang · Hầm sấy · Đóng gói.
Tag thật Phú Riềng: `scratchpad/historian-tags.json` (209 tag). Quy ước tên: `<MÃ> - Frequence` (Hz), `<MÃ> - Current` (A),
`<MÃ> - Running Status` (0/1), nhiệt độ `<MÃ> - Main|Upper|Lower Left|Right Temperature` (có tag gõ sai "Temperture",
"BTCS1- Frequence", "SR- Frequence" → dùng ĐÚNG tên thật trong file tag). Không có tag Cosphi.

## Dữ liệu bố cục (backend, file JSON trong code)
`apps/api/app/services/plant_layouts/phu_rieng.json`; bảng `scada_factory` thêm cột `layout_key text` (null = không có sơ đồ).
```json
{ "key": "phu_rieng",
  "power": [ {"label": "Volt AB", "unit": "V", "tag": "PM - VoltAB"}, … "Current A/B/C" (A), "Power" (kW) ],
  "areas": [
    { "key": "khu-mu-vao", "label": "Khu mủ vào", "width": 1800, "height": 900,
      "nodes": [
        { "id": "MLM1", "kind": "mixer", "x": 150, "y": 330, "w": 90, "h": 90, "angle": 0,
          "label": "MLM1", "label_pos": "top",
          "metrics": [ {"key": "hz", "tag": "MLM1 - Frequence", "unit": "Hz"},
                       {"key": "a",  "tag": "MLM1 - Current",   "unit": "A"} ],
          "status_tag": "MLM1 - Running Status",
          "temps": [ {"label": "Trái", "tag": "CM1 - Main Left Temperature"} ] }
      ],
      "decor": [ { "kind": "basin|pipe|arrow_text", "x": 0, "y": 0, "w": 0, "h": 0, "points": [[x,y],…], "text": "Đến vít tải ngang" } ],
      "links": [ ["MLM3", "BTTL1"] ] } ] }
```
`kind` ∈ `mixer` (MLM, TKMM) · `conveyor` (BTTL, BTCS, BTCLM, TL; dùng `angle`, `w` = chiều dài) · `screw` (VT, VTN) ·
`crusher` (CM, CC, C3T, CCS) · `tank` (QM — hồ có cánh khuấy) · `pump` (BC) · `fan` (QC, QN, QHL, QK) · `zone` (Z01–Z12 — ô nhiệt độ buồng sấy) ·
`motor` (SR, XDT, khác) · `counter` (RobotTotalCount — số bành). Toạ độ theo khung `width × height` của khu.

## API
`GET /api/smart-factory/plant/layout?factory_id=1` → `{ "factory": {id,name}, "layout": <JSON trên> }`; nhà máy không có `layout_key` → 404.

`GET /api/smart-factory/plant/live?factory_id=1&area=khu-mu-vao` → số MỚI NHẤT của mọi tag trong khu + `power`:
```json
{ "area": "khu-mu-vao", "values": { "MLM1 - Frequence": {"value": 41.56, "at": "2026-09-30T22:47:39"}, … } }
```
Đọc qua truy vấn "số mới nhất" sẵn có (Cyclic 60000, vài phút gần nhất, lấy dòng cuối có số từng tag), cache 5 s dùng chung,
khoá theo nhà máy (429 khi bận), lỗi SCADA → 502 như `/meters/*`. Web hỏi lại mỗi 5 s (tab ẩn thì dừng; lần đầu luôn đọc).
Giá trị: số giữ 2 số lẻ; status 0/1 (≥ 0.5 = chạy).

## Hiển thị (frontend)
- Tabs 4 khu (như 4 nút KHU MỦ VÀO · VÍT TẢI NGANG · HẦM SẤY · ĐÓNG GÓI).
- Thanh trên: nhà máy · giờ đọc; thanh điện (Volt AB/BC/CA · Current A/B/C · Power); ô "Tiêu thụ trong ngày": Hôm qua / Hôm nay × Điện (kWh) · Nước (m³) · Bành — lấy từ `/meters/daily` kỳ 2 ngày (có sẵn).
- Khung SVG co giãn theo bề ngang (viewBox = width×height khu), nền sáng; thiết bị vẽ biểu tượng phẳng theo `kind`;
  đang chạy = xanh lá VRG, dừng = xám, không có số = viền nét đứt. Ô số trắng kiểu RELCO: `41.56 Hz` / `1.62 A`; nhiệt độ `°C` (≥ 70 °C tô cam).
- Không chữ giải thích dài (chủ dự án không thích); chỉ icon `@ant-design/icons`, không emoji.
