---
title: Các loại sản phẩm cao su & phạm vi dự báo
type: domain
tags: [svr10, svr20, svr-cv, rss3, latex, phan-loai]
source: Kế hoạch Triển khai (Đề án A)
updated: 2026-06-15
---

# Các loại sản phẩm cao su

## Phạm vi dự báo
- **PoC**: tập trung **SVR 10** (mặt hàng chủ lực, thanh khoản tốt).
- **Mở rộng** (kiến trúc sẵn sàng): SVR CV, SVR L, SVR 3L, SVR 20, RSS3, Latex.
- **Dài hạn**: chuối, gỗ (ngoài phạm vi PoC).

## Phân nhóm chính
| Nhóm | Mã | Mô tả ngắn |
|---|---|---|
| Cao su định chuẩn kỹ thuật (TSR) | SVR 10, SVR 20 | Từ mủ tạp/đông; SVR = Standard Vietnamese Rubber |
| Cao su ly tâm / độ nhớt ổn định | SVR CV (CV50/CV60) | Constant Viscosity |
| Cao su cao cấp | SVR L, SVR 3L | Từ mủ nước, màu sáng |
| Cao su tờ xông khói | RSS3 | Ribbed Smoked Sheet — tham chiếu sàn TOCOM/SGX |
| Mủ latex | Latex (HA/LA) | Mủ ly tâm 60% DRC |

## Tham chiếu sàn theo mặt hàng
- **RSS3** → TOCOM (JPX), SGX (cột `RT`).
- **TSR20 / SVR20** → SGX (cột `TF`).
- **Natural Rubber** → SHFE.
- **SMR CV / SMR20 / Latex** (physical) → LGM Malaysia.

Cách lấy giá chi tiết: [../data-sources/lay-gia-cac-san.md](../data-sources/lay-gia-cac-san.md).

## Yếu tố mùa vụ
- **Cao điểm khai thác: Tháng 8 – Tháng 12** (sản lượng cao).
- Mưa nhiều → giảm ngày cạo → ảnh hưởng nguồn cung. Là biến số đầu vào của model dự báo.
