---
title: "Quản lý Đơn vị thành viên (động) + đổi lưới Giá mủ nguyên liệu (hàng=ngày, cột=đơn vị)"
description: "Bỏ hardcode VRG_COMPANIES: bảng member_unit (CRUD + sắp xếp + active), seed từ VRG_COMPANIES. Lưới Giá mủ nguyên liệu chuyển hàng=ngày × cột=đơn vị (đồng bộ Bảng tính giá). Purchase + bản tin dùng đơn vị động."
status: done
priority: P1
created: 2026-06-20
branch: feature/exchange-crawlers
---

# Member units (dynamic) + transpose raw-material grid

## Quyết định
- Bảng **`member_unit (name PK, sort_order, is_active, note)`**; lazy-seed từ `VRG_COMPANIES` nếu trống.
- `member_unit_repo`: active_names (active, theo sort_order) dùng cho purchase_sheet + bản tin. CRUD: add / rename (migrate `fact_price.grade` source=vrg) / set_active / reorder([names]) / delete.
- `purchase_sheet.companies` + `bulletin._build_raw_materials` lấy từ `active_names()` (thay VRG_COMPANIES hardcode).
- Trang mới `/quan-ly-so-lieu/don-vi-thanh-vien` (MemberUnitPage): list + thêm/đổi tên/active/sắp xếp (↑↓)/xoá.
- **Lưới Giá mủ nguyên liệu**: chuyển **hàng=ngày, cột=đơn vị** (đồng bộ Bảng tính giá). "Thêm ngày" = thêm 1 hàng.

## Phase A — Member units backend
- [ ] db.py + 02-schema.sql: table member_unit
- [ ] member_unit_repo.py (seed, list, active_names, add, rename+migrate, set_active, reorder, delete)
- [ ] schemas/member_unit.py + routers/member_unit.py + đăng ký
- [ ] price_repo.purchase_sheet + bulletin_service._build_raw_materials dùng active_names()

## Phase B — Frontend
- [ ] member-unit-client.ts
- [ ] MemberUnitPage.tsx (CRUD + reorder)
- [ ] RawMaterialPage: lưới hàng=ngày × cột=đơn vị (Thêm ngày = thêm hàng)
- [ ] nav + route

## Phase C — Test
- [ ] Thêm nhiều ngày + giá → lưới đúng; thêm/đổi/sắp xếp đơn vị → grid + bản tin cập nhật
- [ ] pytest · tsc · build

## Success
- Đơn vị thành viên quản lý động; lưới giá mủ hàng=ngày cột=đơn vị; bản tin vẫn đọc đúng (mới nhất ≤ ngày/đơn vị).
