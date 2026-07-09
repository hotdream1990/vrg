# services/bulletin — Bản tin thị trường cao su ngày

Render bản tin ngày theo mẫu VRG ra **PDF** (HTML → Chromium), fill dữ liệu giá
từ DB (`fact_price`) qua `apps/api` (`bulletin_service`). Đầu ra chỉ còn PDF
(đã bỏ xuất PPTX).

## Sinh bản tin

Bản tin được tạo qua API (không còn CLI `python -m bulletin`):

- `POST /api/bulletins/draft` — dựng draft từ giá thật trong DB.
- `POST /api/bulletins/generate-pdf` — xuất PDF (bìa + ruột nhảy trang + header/footer).

Output: `data/bulletins/Ban-tin-ngay-DD-MM-YYYY.pdf` (+ `.json` snapshot cho trang chi tiết).

## Kiến trúc

```
bulletin/
├── __init__.py
├── models.py           # BulletinData, WorldPriceRow, PhysicalPriceRow, VrgFloorRow
├── convert.py          # Quy đổi đơn vị: CNY/tonne, JPY/kg, cents/kg, Sen/kg → USD/T
├── html_template.py    # Dựng HTML ruột bản tin (bố cục theo mẫu) + đo/xếp trang
└── pdf_export.py       # HTML → Chromium (Playwright) → PDF, ghép bìa đầu/cuối
```

Dữ liệu vào `BulletinData` do `apps/api/app/services/bulletin_service.py` dựng từ
`fact_price` (giá sàn, physical, giá sàn Tập đoàn, giá mủ nguyên liệu theo khu vực).

## Template

Bố cục ruột (Section I–IV) bám mẫu thật:
`docs/bieu-mau-bo-sung/mau_ban_tin_ngay/Bản tin ngày *.pdf`.
Bìa đầu/cuối + banner header/footer lấy từ `data/bulletin-assets/`
(custom ghi đè default nếu có — xem trang "Cấu hình hình ảnh").

## Quy đổi đơn vị

| Nguồn | Đơn vị gốc | → Đơn vị bản tin |
|---|---|---|
| SHFE | CNY/tonne | USD/T (÷ tỷ giá USD/CNY) |
| TOCOM/OSE | JPY/kg | USD/T (× 1000 ÷ tỷ giá USD/JPY) |
| SGX/LGM | US cents/kg | USD/T (× 10) |
| LGM Latex | Sen/kg | USD/T (× 10 ÷ tỷ giá USD/MYR) |
| Reuters (physical) | US$/kg | USD/T (× 1000) |
