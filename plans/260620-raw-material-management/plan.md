---
title: "Quản lý Giá mủ nguyên liệu (giá thu mua mủ nước theo công ty) + read-only trong bản tin"
description: "Trang quản lý riêng dưới Quản lý số liệu: lưới Công ty × Ngày (đồng/độ TSC), filter ngày, thêm/xoá ngày, sửa ô ghi fact_price (source=vrg). Bản tin Section III.2 chuyển read-only, đọc từ đây."
status: done
priority: P1
created: 2026-06-20
branch: feature/exchange-crawlers
---

# Raw material (latex purchase) management

## Quyết định
- Dữ liệu vẫn là `fact_price` source=`vrg`, price_type=`purchase`, grade=công ty, unit `đồng/độ TSC` (đã có).
- Trang mới `/quan-ly-so-lieu/gia-mu-nguyen-lieu`: lưới **hàng=công ty (13), cột=ngày (mới nhất trước)**; ô sửa → `PUT /api/prices/records`. "Thêm ngày" (date picker) + "Xoá ngày".
- Bản tin **Section III.2 read-only** (như Section III floor), đọc từ `_build_raw_materials`; bỏ nhập inline + nút Lưu; link sang trang quản lý.
- Dọn code chết: client `saveRawMaterials`, route `PUT /api/bulletins/draft/raw-materials`, `bulletin_service.save_purchase_prices`.

## Phase A — Backend
- [ ] `price_repo.purchase_sheet(date_from,date_to)` → {companies, dates, values}; `delete_purchase_date(as_of)`
- [ ] `prices.py`: GET `/purchase-sheet`, DELETE `/purchase`

## Phase B — Frontend
- [ ] `api-client.ts`: PurchaseSheet + fetchPurchaseSheet + deletePurchaseDate
- [ ] `sections/EditableCell.tsx` (ô số tự quản lý edit)
- [ ] `pages/RawMaterialPage.tsx` (lưới + filter + thêm/xoá ngày)
- [ ] nav `data/sample-data.ts` + route `App.tsx`

## Phase C — Bản tin
- [ ] `BulletinPage` Section III.2 read-only + link; bỏ edit/save inline
- [ ] Dọn: saveRawMaterials, PUT draft/raw-materials, save_purchase_prices

## Success
- Trang quản lý nhập/sửa/xoá giá thu mua theo công ty + ngày, filter ngày OK.
- Bản tin III.2 tự đọc giá mới nhất ≤ ngày báo cáo (read-only) + link quản lý.
- pytest xanh · web build OK.
