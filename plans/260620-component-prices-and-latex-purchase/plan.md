---
title: "Giá sàn dạng thành phần (native+tỷ giá+USD) + Exchange Rate + Giá thu mua mủ nước theo công ty"
description: "Theo file Excel gốc VRG: dashboard hiện breakdown từng sàn (giá nội tệ · tỷ giá · USD/T) + mục Exchange Rate; thêm Giá thu mua mủ nước theo công ty thành viên (đồng/độ TSC) lưu vào fact_price (source=vrg), đổ vào mục 'Giá mủ nguyên liệu' của bản tin ngày."
status: done
priority: P1
created: 2026-06-20
branch: feature/exchange-crawlers
---

# Component prices + Latex purchase

## Quyết định (KISS/YAGNI/DRY)
- **Vị trí breakdown:** trang **Quét Đa sàn** (giống sheet Excel để soát). Bản tin PPTX **giữ template USD/T** (8 cột cố định).
- **Exchange Rate:** dữ liệu FX đã có sẵn (`USD/{VND,CNY,THB,JPY,MYR}` trong source `fx`) — chỉ gom hiển thị, KHÔNG crawl thêm.
- **Quy đổi 1 nguồn (DRY):** `services/bulletin/bulletin/convert.py` thêm `to_usd_tonne_detail()` trả `(usd_tonne, fx_pair, fx_rate)`. Cả bản tin lẫn dashboard dùng chung.
- **Map sàn dùng chung:** trích các hằng (WORLD_GRADE_MAP, EXCHANGE_NAMES, CANON_*) từ `bulletin_service` → `app/core/market_meta.py`.
- **Giá thu mua mủ nước:** tái dùng `fact_price` — `source="vrg"`, `grade`=công ty, `unit="đồng/độ TSC"`, `price_type="purchase"`, `currency="VND"`. 1 nguồn sự thật; sau auto-fetch ghi cùng chỗ; Records CRUD + history dùng lại.
- **Mục 'Giá mủ nguyên liệu' bản tin:** đọc thẳng từ `fact_price` source=`vrg`; editor nhập tay → lưu DB; PPTX render text gộp 1 dòng (giữ template), PDF/HTML render bảng theo công ty.

## Phase 1 — Exchange Rate + Phase 2 — Breakdown (dashboard)
- [ ] `convert.py`: `to_usd_tonne_detail()`
- [ ] `app/core/market_meta.py` (mới): WORLD_GRADE_MAP, EXCHANGE_NAMES, CANON_WORLD/PHYS, PHYSICAL_GRADE_MAP, FX_PAIRS, VRG_COMPANIES
- [ ] `app/services/price_board.py` (mới): `build_board()` từ `latest()` + convert
- [ ] `app/schemas/price.py`: ExchangeComponent, FxRateItem, PriceBoard
- [ ] `app/routers/prices.py`: `GET /board`
- [ ] `bulletin_service.py`: import từ market_meta (bỏ literal trùng)
- [ ] Web: `api-client.ts` board types + `fetchBoard`; `sections/ExchangeBoard.tsx`; gắn vào `ScanPage.tsx`

## Phase 3 — Giá thu mua mủ nước theo công ty (fact_price + bản tin)
- [ ] `app/schemas/bulletin.py`: `RawMaterialRegion` + `price`,`unit`; input schema `RawMaterialPurchase`
- [ ] `app/services/price_repo.py`: `latest_purchase_by_company()`
- [ ] `bulletin_service.py`: raw_materials build từ DB (source=vrg) + `save_purchase_prices()`
- [ ] `app/routers/bulletins.py`: `PUT /draft/raw-materials`
- [ ] `html_template.py`: bảng công ty; `generator.py`: gộp 1 dòng giữ template
- [ ] Web: `bulletin-client.ts` (+price, saveRawMaterials); `BulletinPage.tsx` Section III.2 bảng công ty + Lưu; `RecordsPage.tsx` +source `vrg`

## Success
- Dashboard hiện đủ Native·Tỷ giá·USD/T per sàn + bảng Exchange Rate.
- Nhập giá thu mua công ty → lưu fact_price (source=vrg) → bản tin 'Giá mủ nguyên liệu' đọc lại đúng, xuất PDF có bảng.
- `uv run pytest` xanh; build web ok.
