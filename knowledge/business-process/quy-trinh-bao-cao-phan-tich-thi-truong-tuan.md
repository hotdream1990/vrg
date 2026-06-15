---
title: Quy trình báo cáo phân tích thị trường cao su tuần
type: process
tags: [bao-cao-tuan, phan-tich-thi-truong, ose, shfe, sgx, mre, vi-mo, du-bao]
source: docs/bieu-mau/Phụng/Báo cáo phân tích thị trường cao su - Hàng tuần/
updated: 2026-06-15
---

# Quy trình Báo cáo Phân tích Thị trường Cao su (hàng tuần)

> Ban TTKD phát hành bản tin phân tích thị trường **mỗi tuần** (Word + PDF), tổng hợp diễn
> biến giá các sàn, yếu tố vĩ mô và **dự báo xu hướng tuần kế tiếp**. Đây là nguồn tham chiếu
> chính cho mô-đun **nhận định / kịch bản Bull-Base-Bear** của hệ thống AI.

## Bố cục báo cáo (tuần N)
1. **Tóm tắt tuần N-1** — chốt lại diễn biến tuần liền trước.
2. **Diễn biến tuần N** — phân tích kỹ thuật chung (giằng co, đảo chiều, đỉnh/đáy tuần).
3. **Diễn biến giá** (3 bảng):
   - **3.1 Sàn giao dịch quốc tế** (USD/tấn) — so sánh tuần N-1 vs N, +/- , % thay đổi.
   - **3.2 Thị trường giao ngay** (physical, USD/tấn).
   - **3.3 Giá thu mua mủ nước trong nước** (VNĐ/độ TSC) — biên độ + biến động.
4. **Các yếu tố vĩ mô ảnh hưởng**.
5. **Dự báo xu hướng tuần N+1** — động lực hỗ trợ tăng / áp lực kìm hãm.
6. **Kết luận & khuyến nghị** cho các đơn vị.

## Bảng 3.1 — Sàn quốc tế theo dõi
| Sàn | Sản phẩm theo dõi |
|---|---|
| **OSE** (Osaka, ~JPX/TOCOM) | RSS3 (yết gốc Yên/kg → quy USD/tấn) |
| **SHANGHAI** (SHFE) | RSS3 (yết Nhân dân tệ/tấn → quy USD/tấn) |
| **SGX** (SICOM) | RSS3, **TSR20** |
| **MRE** (Malaysia) | **SMR CV**, **SMR20**, **LATEX** |

Mỗi dòng có: giá tuần N-1, giá tuần N, chênh lệch tuyệt đối, % thay đổi, kèm "Nhận định" từng sàn.

## Bảng 3.2 — Thị trường giao ngay (physical)
Sản phẩm: **RSS3, STR20, SMR20, LATEX** (USD/tấn). Khi không có giá giao dịch hiển thị
ghi `NON`/`NA` → không tính biên độ kỹ thuật (liên quan nguồn Reuters, xem file Physical).

## Bảng 3.3 — Giá thu mua mủ nước nội địa
- Sản phẩm: **Mủ nước**, đơn vị **VNĐ/độ TSC** (Total Solid Content).
- Báo cáo dạng biên độ (vd `525 – 580`) + biến động so với tuần trước.

## Nhóm yếu tố vĩ mô phân tích định kỳ
- **Năng lượng & địa chính trị**: giá dầu Brent, căng thẳng Trung Đông.
- **Cao su tổng hợp**: giá **Butadien** (sàn SHFE) — hàng thay thế cao su tự nhiên.
- **Cung – cầu cơ bản**: dự báo **ANRPC** (thâm hụt cung-cầu), thời tiết (mưa/khô vùng trồng
  Thái Lan, Indonesia), nguồn cung mới (Campuchia…).
- **Tỷ giá & tài chính**: JPY/USD, chỉ số **DXY**, Nikkei.
- **Lực cầu hạ nguồn**: ngành lốp xe Trung Quốc, **PMI sản xuất** Trung Quốc, thuế quan Mỹ.

## Lưu ý số hóa
- Báo cáo hiện do chuyên viên soạn thủ công (Word) → hệ thống AI cần **tự sinh phần 3.1–3.3
  (bảng giá so sánh tuần)** từ dữ liệu sàn đã crawl, và phần nhận định vĩ mô + dự báo từ RAG.
- Các con số trong file mẫu (tuần 23/2026) chỉ là **ví dụ cấu trúc**, không phải số liệu chuẩn.
