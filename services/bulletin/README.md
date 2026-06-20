# services/bulletin — Bản tin thị trường cao su ngày

Tự động generate file PPTX bản tin ngày theo mẫu VRG, fill dữ liệu giá
từ crawlers và/hoặc input thủ công.

## Chạy

```bash
cd services/bulletin
uv sync

# 1. Chạy crawler + generate (tự động fill giá thế giới + physical):
uv run python -m bulletin

# 2. Không crawl, chỉ fill từ file JSON (giá sàn, phân tích):
uv run python -m bulletin --no-crawl --date 18-06-2026 --supplement sample-supplement.json

# 3. Chỉ định template + output khác:
uv run python -m bulletin --template path/to/template.pptx --out output.pptx
```

Output mặc định: `data/bulletins/Ban-tin-ngay-DD-MM-YYYY.pptx`

## Kiến trúc

```
bulletin/
├── __init__.py
├── __main__.py         # python -m bulletin
├── models.py           # BulletinData, WorldPriceRow, PhysicalPriceRow, VrgFloorRow
├── generator.py        # Core: fill data vào template PPTX (giữ nguyên format)
├── convert.py          # Quy đổi đơn vị: CNY/tonne, JPY/kg, cents/kg → USD/T
├── data_mapper.py      # Map crawler PriceRecord → BulletinData
└── run_generate.py     # CLI entry point
```

## Template

File mẫu gốc: `docs/bieu-mau/Tâm/Biểu mẫu - Bản tin ngày 09-06-2026/Bản tin ngày 09-06-2026.pptx`

Generator dùng file này làm template, tìm shape theo tên, fill data
vào đúng cell/paragraph mà **giữ nguyên toàn bộ formatting** (font, màu,
border, background).

## File supplement JSON

Dùng `--supplement` để bổ sung dữ liệu thủ công (giá sàn VRG, mủ nguyên liệu,
phân tích thị trường). Xem [sample-supplement.json](sample-supplement.json) làm mẫu.

Các field:
- `vrg_floor_prev_label` / `vrg_floor_curr_label` — label header bảng giá sàn
- `vrg_floor_prev` / `vrg_floor_curr` — data giá sàn [{grade, fob_usd, domestic_vnd}]
- `raw_material_regions` — giá mủ nguyên liệu {khu_vực: giá_text}
- `market_analysis` — danh sách đoạn phân tích thị trường
- `source_urls` — danh sách URL nguồn tin

## Quy đổi đơn vị

| Nguồn | Đơn vị gốc | → Đơn vị bản tin |
|---|---|---|
| SHFE | CNY/tonne | USD/T (÷ tỷ giá USD/CNY) |
| TOCOM/OSE | JPY/kg | USD/T (× 1000 ÷ tỷ giá USD/JPY) |
| LGM | US cents/kg | USD/T (× 10) |
| ANRPC | US$/kg | USD/T (× 1000) |
