# Biểu mẫu "Báo giá mủ thị trường" (Market Quote)

Nguồn: `docs/bieu-mau-bo-sung/Báo giá mủ ngày 03.07.2026.xlsx`. Mỗi ngày 1 phiếu.

## Quyết định (chốt với user)
- **1 phiếu/ngày trọn vẹn** → trang mới `/quan-ly-so-lieu/bao-gia-mu` (nhóm "thủ công").
- **Đồng bộ phần trùng**: Mục 4 (giá mủ nước khu vực) ghi vào kho *Giá mủ nguyên liệu*
  (`fact_price` source=`vrg`, price_type=`purchase`, đồng/độ TSC) — Mục 4 = slice theo ngày
  của danh mục **đơn vị thành viên** (7/8 khu vực đã trùng). Tỷ giá VCB (3 giá) lưu trong
  phiếu + hiển thị tham chiếu USD/VND từ tính năng *Tỷ giá*.
- **Mục đích**: lưu trữ theo ngày + số liệu SVR làm đầu vào Bản tin/dự báo (mirror `market`).

## Cấu trúc phiếu
- Header: ngày + tỷ giá VCB (mua_tm / mua_ck / bán).
- Mục 1 — Giá NĐ tư nhân (VNĐ/tấn) · Mục 2 — Giá XK VRG (USD/tấn) · Mục 3 — Giá NĐ VRG
  (VNĐ/tấn) + tình trạng/loại. Grade cố định: SVR CV 50, SVR CV 60, SVR 3L, SVR 10, LATEX.
  Mỗi mục có ghi chú tự do.
- Mục 4 — Giá mủ nước theo đơn vị thành viên (đồng/độ TSC) → sync kho Giá mủ nguyên liệu.
- Ghi chú chung (footer).

## Lưu trữ
- Bảng mới `market_quote(as_of PK, payload jsonb, updated_at)` — payload = tỷ giá + Mục 1-3 + notes.
- Mục 4: KHÔNG lưu trong payload — đọc/ghi thẳng `fact_price` (source=vrg, purchase).
- Mirror Mục 1-3 → `fact_price` source=`market`, price_type ∈
  {market_domestic_private, market_export_vrg, market_domestic_vrg} (chuỗi cho dự báo).

## Files
Backend: market_meta (+MARKET_QUOTE_GRADES), db.py DDL + 02-schema.sql, schemas/market_quote.py,
services/market_quote_repo.py, routers/market_quote.py, main.py (register).
Web: lib/market-quote-client.ts, pages/MarketQuotePage.tsx + components (GradePriceTable,
RegionLatexTable, VcbRateBar), App.tsx route, AdminLayout menu, DataSourceNote (manual entry).

## Trạng thái
- [x] Backend (schema + repo + router + sync) — verified qua API (save/get/list, purchase-sheet + market series)
- [x] Web (form + sync Mục 4) — trang MarketQuotePage + components, menu + route + note
- [x] Verify trên trình duyệt — load phiếu 03/07 đủ VCB/Mục 1-4/status, regions sync, build xanh
- [ ] (sau) Wire số liệu SVR (source=market) vào Bản tin ngày / mô hình dự báo
