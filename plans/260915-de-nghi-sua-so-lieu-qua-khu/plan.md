---
title: Đề nghị sửa số liệu quá khứ (đơn vị thành viên → Ban duyệt)
created: 2026-09-15
branch: feature/master-contract
status: in-progress
---

# Đề nghị sửa số liệu quá khứ

Đơn vị bị chặn sửa ngày cũ bởi **cửa sổ sửa** (N ngày) và **chốt số liệu**. Tính năng mới: ở bản ghi
đang khoá, đơn vị bấm **"Đề nghị sửa"** → sửa trên đúng form cũ → popup nhập **lý do** + cảnh báo
chốt → gửi. Nội dung CHƯA ghi vào số liệu thật. Người có quyền **Duyệt đề nghị sửa số liệu**
(`edit_request`, cấp riêng; quản trị luôn có) nhận email, xem trước/sau, **Duyệt** (hệ thống mới ghi
thật + gỡ chốt của đơn vị từ ngày bị ảnh hưởng) hoặc **Từ chối** (bắt buộc ghi chú). Người gửi
nhận email kết quả.

## Quyết định đã chốt (chủ dự án, 15/09/2026)
- Người duyệt + nhận email = quyền riêng `edit_request` + quản trị. Menu chỉ hiện với người có quyền.
- Chỉ **tài khoản đơn vị thành viên** (`member`). Chuyên viên KHÔNG dùng luồng này.
- KHÔNG có file minh chứng riêng. File thay đổi trong chính bản ghi (hợp đồng scan, hoá đơn) đi kèm payload.
- Duyệt mà ngày sửa ≤ mốc chốt của đơn vị ⇒ gỡ xác nhận chốt của đơn vị ở MỌI đợt chưa huỷ có
  `lock_date ≥ ngày sửa sớm nhất` ⇒ đơn vị phải xác nhận chốt lại. Popup gửi đề nghị cảnh báo trước.

## Phạm vi thao tác (op)
| op | Màn | Hàng rào đang chặn | Áp dụng khi duyệt |
|---|---|---|---|
| `daily_report` | Biểu Thu mua / Tồn kho (gồm đơn giá thu mua) | cửa sổ + chốt | `unit_daily_repo.upsert` + giá lớp `vrg_unit` |
| `daily_move` | Đổi ngày bản ghi biểu ngày | cửa sổ + chốt (2 ngày) | `unit_daily_repo.move_day` |
| `market_demand` | Nhu cầu thị trường | cửa sổ | `market_demand_repo.upsert` |
| `contract_save` | Hợp đồng / đợt giao (thêm, sửa) | cửa sổ + chốt theo ngày giao | `sales_contract_repo.save` |
| `contract_delete` | Xoá hợp đồng / đợt giao | cửa sổ + chốt theo ngày giao | `sales_contract_repo.delete` |
| `contract_delivery_type` | Chuyển loại giao của hợp đồng (giao 1 lần ↔ giao nhiều lần) | chốt theo ngày giao (KHÔNG có cửa sổ) | `sales_contract_lifecycle.set_delivery_type` |
| `year_plan` | Kế hoạch năm (thêm 03/10/2026) | chốt số liệu — kế hoạch năm chốt CÙNG ĐỢT (KHÔNG có cửa sổ) | `unit_daily_repo.save_year_plan` + gỡ chốt các đợt của đúng năm đó |

Không nằm trong phạm vi (không bị hàng rào thời gian): Hợp đồng mẹ, Khách hàng,
Excel import (đang tắt), hợp đồng tồn kho cũ (không còn màn gọi).

## Phases
| # | File | Owner | Trạng thái |
|---|---|---|---|
| 1 | [phase-01-backend.md](phase-01-backend.md) | BE agent | ⏳ |
| 2 | [phase-02-web-core.md](phase-02-web-core.md) | FE-core agent | ⏳ |
| 3 | [phase-03-web-screens.md](phase-03-web-screens.md) | FE-screens agent | ⏳ |
| 4 | Kiểm thử đối kháng + review + verify UI thật | main | ⏳ |

Hợp đồng API dùng chung cho 3 phase: [api-contract.md](api-contract.md) — **nguồn sự thật**, không tự đổi.
