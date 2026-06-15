---
title: Quy trình báo cáo tiêu thụ năm toàn Tập đoàn
type: process
tags: [bao-cao-nam, tieu-thu, xuat-khau, noi-tieu, uy-thac-xk, svr, latex]
source: docs/bieu-mau/Mẫu Báo cáo Tiêu thụ năm - Triều/
updated: 2026-06-15
---

# Quy trình Báo cáo Tiêu thụ Năm (toàn Tập đoàn)

> Báo cáo tổng kết tình hình **tiêu thụ mủ cao su cả năm** (tính đến 31/12), tổng hợp từ
> các đơn vị thành viên theo **04 biểu mẫu** chuẩn do Tập đoàn ban hành.

## Căn cứ & quy trình (theo CV 3476/CSVN-TTKD ngày 30/12/2025)
- Tổng giám đốc Tập đoàn yêu cầu các đơn vị thành viên báo cáo tiêu thụ năm theo 4 biểu mẫu.
- **Đầu mối tổng hợp**: Ban Thị trường Kinh doanh (TTKD).
- **Nộp về**: email `xnk-giasan@vrg.vn`, **bằng file Excel**, giữ nguyên biểu mẫu để tổng hợp nhanh & chính xác.
- **Hạn nộp** (năm 2025): trước **16:00 ngày 10/01/2026**.

## 04 biểu mẫu đầu vào (đơn vị thành viên gửi)
1. **Biểu 1** — Xuất khẩu trực tiếp (XKTT): theo từng khách hàng, chủng loại, số lượng, trị giá.
2. **Biểu 2** — Ủy thác xuất khẩu (UTXK): theo từng khách hàng, chủng loại, số lượng, trị giá.
3. **Biểu 3** — Nội tiêu: tiêu thụ nội tiêu tại Việt Nam, và nội tiêu tại Campuchia/Lào.
4. **Biểu 4** — Xuất khẩu cao su tự nhiên theo **quốc gia**, cho từng chủng loại, số lượng, trị giá.

### Quy ước trị giá & chủng loại
- Cột **Trị giá = USD** trong biểu 1, 2, 4.
- **Nội tiêu Việt Nam** (biểu 3): trị giá **VNĐ**; **nội tiêu Campuchia/Lào**: trị giá **USD**.
- Các cty khu vực Lào/Campuchia có mở tờ khai hải quan XK mủ về Việt Nam → báo cáo theo biểu 1.
- Chủng loại **Latex**: quy về **"đã quy khô"**.

## Cấu trúc file tổng hợp (Output)
File `Mẫu Tổng hợp Báo cáo tiêu thụ năm toàn Tập đoàn.xlsx` gồm các sheet:
- **NỘI TIÊU (Chi tiết) 3.1** & **NỘI TIÊU (Tổng hợp) 3.1** — Bảng 1.1/1.2 theo khu vực & khách hàng.
- **NỘI TIÊU tại Cam và Lào 3.2**.
- **TỔNG HỢP XK, UTXK, NT** — 2 chiều: theo **khách hàng** và theo **khu vực/đơn vị**.
- **XUẤT KHẨU (Chi tiết)** · **ỦY THÁC XK (Chi tiết)** · **XKTT qua các QG (chi tiết)**.
- **Tổng hợp TTXK – VN/Lào/CPC** (Biểu 4: thị trường xuất khẩu theo quốc gia).
- **Cty Lào, Cam xk qua VN (chi tiết)**.

## Ma trận chủng loại × giá trị
Các sheet tổng hợp trải cột theo **từng loại mủ**, mỗi loại có cặp cột **Tấn | Trị giá**:
CV50, CV60, SVRL, SVR3L, SVR3L MIX, SVR5S, SVR5, SVR10, SVR10 MIX, SVR10 CV60, SVR20,
RSS1, RSS3, RSS4, RSS5, Latex (khô), Mủ đông NLỆ/Skim tận thu, Skim block → cột **TỔNG**.

## Khác biệt so với báo cáo tuần
- Báo cáo tuần: nhanh, lũy kế, theo **tồn kho + thu mua + tiêu thụ thô**, 6 khu vực địa lý.
- Báo cáo năm: chi tiết theo **khách hàng + quốc gia + kênh bán** (XKTT/UTXK/Nội tiêu),
  có **trị giá tiền tệ** (USD/VNĐ), phục vụ quyết toán & phân tích thị trường cả năm.
