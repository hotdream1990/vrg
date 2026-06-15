---
title: Quy trình báo cáo ký kết hợp đồng theo Quý
type: process
tags: [hop-dong, hddh, hdnt, cong-thuc-gia, sgx, mrb, tsr20, smr, eudr]
source: docs/bieu-mau/Phụng/Báo cáo ký kết hợp đồng theo Quý/
updated: 2026-06-15
---

# Quy trình Báo cáo Ký kết Hợp đồng theo Quý

> Theo dõi tình hình ký kết & thực hiện hợp đồng bán mủ của các đơn vị thành viên, báo cáo
> theo **đợt/quý** (tính đến cuối kỳ, vd 31/03). Đính kèm CV số 827/CSVN. Gồm **04 biểu mẫu**.

## Phân loại hợp đồng
- **HĐDH** — Hợp đồng Dài hạn (cả năm, thường XKTT, có công thức giá gắn sàn).
- **HĐNT** — Hợp đồng Nguyên tắc (giá thỏa thuận, kỳ thực hiện dự kiến).

## 04 biểu mẫu
- **Biểu 1** — HĐDH ký kết trong năm hiện tại.
- **Biểu 2** — HĐDH năm trước **chuyển sang** năm hiện tại.
- **Biểu 3** — HĐNT ký kết trong năm hiện tại.
- **Biểu 4** — HĐNT năm trước **chuyển sang**.

## Cột dữ liệu — Biểu 1 & 2 (HĐDH)
- **Khách hàng**.
- **Chủng loại – số lượng** (trải cột, đơn vị Tấn): SVR CV50, SVR CV60, SVR L, SVR 3L,
  SVR 5S, SVR 10CV50/60, SVR 10, SVR 20, RSS 1, RSS 3, Latex (quy khô), **PEFC**, **EUDR**…
- **Tổng số lượng ký kết** · **Thực hiện (tấn)** · **Còn lại (tấn)**.
- **Thời gian thực hiện hợp đồng** (vd Tháng 1 – Tháng 12).
- **Thời gian tính giá bình quân** (vd "01 tháng", "15 ngày đầu").
- **Công thức giá** + **công thức giá chi tiết** (xem dưới).
- **Giảm hàng rời** · **Giảm trừ vận chuyển & bốc xếp** · **Chiết khấu áp dụng** (USD/tấn).
- **Hình thức HĐ** (NT, XKTT…) · Ghi chú.

## Công thức giá (rất quan trọng cho dự báo)
Giá bán HĐDH gắn với **giá sàn/physical quốc tế + chênh lệch (premium/discount)**:
- **Công thức 1 (MRB)**: tham chiếu **SMR** (Malaysian Rubber Board). Vd `SMR 10 + 0 USD/tấn`.
- **Công thức 2 (SGX)**: tham chiếu **TSR 20** (SGX/SICOM). Vd `TSR 20 + 270 USD/tấn`,
  `TSR 20 + 205 USD/tấn`.
- Phần `+ X USD/tấn` chính là **premium** của VRG so với giá tham chiếu quốc tế.

## Cột dữ liệu — Biểu 3 & 4 (HĐNT)
- Khách hàng · Chủng loại · **Số lượng ký kết (tấn)** · **Giá thỏa thuận** ·
  Thời gian thực hiện dự kiến · Số lượng đã thực hiện · Số lượng còn lại · Ghi chú.

## Liên hệ tri thức
- Tham chiếu sàn/physical: xem `data-sources/lay-gia-cac-san.md` (SGX TSR20=`TF`, SMR từ LGM/MRB).
- Khái niệm **Premium/Discount**: xem `glossary.md`.
- **EUDR/PEFC**: chứng chỉ truy xuất nguồn gốc — ngày càng là tiêu chí phân loại HĐ & giá.
