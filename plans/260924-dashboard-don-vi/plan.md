---
title: "Dashboard đơn vị — một trang tổng quan theo phạm vi Tập đoàn / khu vực / đơn vị"
status: done
priority: P2
branch: feature/master-contract
created: 2026-09-24
---

# Dashboard đơn vị

Yêu cầu chủ dự án (24/09/2026): trang dashboard của MỘT đơn vị — thu mua · tồn kho · tiêu thụ · chỉ
tiêu, có chia theo chủng loại và các "type" khác. Admin chọn phạm vi: **toàn Tập đoàn · một khu vực ·
một đơn vị**.

Khác màn "Chỉ số đơn vị" (bảng SO SÁNH các đơn vị, dòng = đơn vị): đây là bức tranh của MỘT phạm vi,
KPI + biểu đồ. Hai màn song song, không thay nhau.

## Quyết định
| # | Nội dung |
|---|---|
| Q1 | Route `/dashboard-don-vi`, API `/api/unit-dashboard/*` (chỉ GET). |
| Q2 | Tài khoản có quyền `unit_daily` (admin · chuyên viên · lãnh đạo Tập đoàn) chọn được mọi phạm vi. |
| Q3 | Tài khoản đơn vị (`member`, `leader`) chỉ xem đơn vị được gán — ép ở server, không tin client. |
| Q4 | KHÔNG tự cộng lại số: mọi con số lấy từ `unit_report_{purchase,consumption,stock}` và `unit_series_stock` — cùng luật BQ gia quyền, % = Σ TH ÷ Σ KH, gộp sáp nhập, không mượn số ngày khác. |
| Q5 | Chủng loại chỉ có ở thành phẩm (thu mua thành phẩm · tiêu thụ · tồn kho). Mủ nước/chén/dây chia theo LOẠI MỦ, không chia chủng loại (luật 22/09/2026). |
| Q6 | Chỉ tiêu năm tính LŨY KẾ 01/01 → ngày cuối kỳ (không so tháng với chỉ tiêu cả năm). Doanh thu có lần giao thiếu tỷ giá → % để trống, giống Báo cáo tổng hợp. |
| Q7 | Phạm vi đơn vị ĐÃ SÁP NHẬP → xem TÁCH (chỉ số của chính nó), không kéo số của đơn vị nhận. |
| Q8 | % chỉ tiêu tính trên RỔ đơn vị được giao chỉ tiêu (tử + mẫu cùng rổ). Lý do: trên bản sao prod mới 1/64 đơn vị có KH doanh thu — cộng doanh thu cả Tập đoàn chia KH một đơn vị ra 1.340.609%. Màn Thống kê cũ vẫn cộng tử số cả đơn vị chưa giao KH (chưa đổi, chờ chủ dự án). |

## Nhánh
| # | Việc | File (sở hữu) |
|---|---|---|
| B | Backend: scope · 6 endpoint · test | `services/unit_dashboard*.py`, `routers/unit_dashboard.py`, `tests/test_unit_dashboard.py` + 2 chỗ nhỏ ở `unit_series_stock.py`, `unit_report_query.py`, `unit_report_consumption.py` |
| F | Web: trang + client | `lib/unit-dashboard-client.ts`, `pages/unit-dashboard/*` |
| I | Ghép: route, menu, main.py | `App.tsx`, `sidebar-menu-builders.tsx`, `main.py` (chỉ hunk của mình) |

Hợp đồng API: [api-contract.md](api-contract.md).
