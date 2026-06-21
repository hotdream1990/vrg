---
title: "Quản lý số liệu (tách sub-menu) + Giá sàn Tập đoàn (biểu giá theo lần) ánh xạ bản tin"
description: "Bỏ bảng records phẳng; tách Bảng tính giá / Tỷ giá thành 2 trang riêng có filter ngày; thêm Giá sàn Tập đoàn nhập tay theo 'lần' (số tự nhảy) → ánh xạ Section III bản tin (tự lấy lần hiện tại + lần trước theo ngày báo cáo)."
status: done
priority: P1
created: 2026-06-20
branch: feature/exchange-crawlers
---

# Data management + VRG floor

## Quyết định
- **Nav:** thêm section sidebar "Quản lý số liệu" với 3 mục → 3 route:
  `/quan-ly-so-lieu/bang-gia-san` · `/ty-gia` · `/gia-san-tap-doan`. Mỗi trang có filter khoảng ngày.
- **Bỏ** bảng "Chi tiết bản ghi (nâng cao)" (flat CRUD). `RecordsPage` xoá; redirect `/quet-da-san/records` → bang-gia-san. Link ở ScanPage/BulletinPage trỏ lại.
- **PriceSheetGrid** refactor: prop `view: "exchange"|"fx"` + `dateFrom/dateTo`. `/api/prices/sheet` thêm `date_from/date_to`.
- **Giá sàn Tập đoàn:** bảng **riêng** `vrg_floor_price (lan, as_of, grade, fob_usd, domestic_vnd)` PK (lan, grade). Nhập tay; mỗi biểu giá = 1 **lần** (số = max(lan)+1 tự nhảy khi tạo). Grades = VRG_FLOOR_GRADES.
- **Bản tin Section III:** đọc từ floor — `floor_for_bulletin(report_date)` lấy 2 lần mới nhất ≤ ngày (curr+prev) → label "Giá sàn lần {n} ({date})". Section III thành **read-only** trong editor (bỏ nhập tay + bỏ khỏi handleSave).

## Phase A — Tách trang + nav + filter ngày
- [ ] `data/sample-data.ts`: section nav "Quản lý số liệu" (3 mục)
- [ ] `App.tsx`: routes mới + redirect records
- [ ] `routers/prices.py` + `price_sheet.py` + `price_repo.prices_since`: nhận date_from/date_to
- [ ] `PriceSheetGrid.tsx`: view + dateRange; tách fx ra
- [ ] `pages/PriceSheetPage.tsx`, `pages/FxRatePage.tsx` (filter ngày)
- [ ] Xoá `RecordsPage`; sửa link ScanPage/BulletinPage

## Phase B — Giá sàn Tập đoàn (mới)
- [ ] `core/db.py` + `infra/db/init/02-schema.sql`: table vrg_floor_price
- [ ] `core/market_meta.py`: VRG_FLOOR_GRADES
- [ ] `services/floor_repo.py`: next_lan, list_schedules(date_from,date_to), get_schedule, save_schedule, delete_schedule, floor_for_bulletin
- [ ] `schemas/floor.py` + `routers/floor.py` (GET list/{lan}/next, POST create, PUT, DELETE) + đăng ký router
- [ ] `pages/VrgFloorPage.tsx` + `lib/floor-client.ts`

## Phase C — Ánh xạ bản tin
- [ ] `bulletin_service.create_draft`: Section III từ floor_for_bulletin (label lần+ngày); fallback nếu trống
- [ ] `BulletinPage.tsx`: Section III read-only (bỏ edit + bỏ khỏi handleSave)

## Success
- 3 trang Quản lý số liệu chạy, filter ngày OK. Tạo lần mới tự nhảy số, nhập giá → lưu DB.
- Tạo bản tin ngày X → Section III tự hiện 2 lần mới nhất ≤ X (curr/prev) + nhãn lần.
- pytest xanh · web build OK.
