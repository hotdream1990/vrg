---
title: Quy trình báo cáo tiêu thụ tuần toàn Tập đoàn
type: process
tags: [bao-cao-tuan, tieu-thu, ton-kho, thu-mua, svr, latex, rss]
source: docs/bieu-mau/Hạnh/1-BÁO CÁO TUẦN/
updated: 2026-06-15
---

# Quy trình Báo cáo Tiêu thụ Tuần (toàn Tập đoàn)

> Ban Thị trường Kinh doanh (TTKD) tổng hợp số liệu **tiêu thụ – tồn kho – thu mua** từ
> ~68 đơn vị thành viên thành 1 báo cáo toàn Tập đoàn mỗi tuần.

## Luồng dữ liệu (Input → Output)
- **Input**: mỗi công ty thành viên gửi 1 file Excel (`<Tên cty>.xlsx`) + 1 file thu mua
  (`<Tên cty>-Thumua.xlsx`) trong thư mục con `Báo cáo thu mua/`. Một số đơn vị gửi PDF.
- **Tổng hợp**: TTKD gộp toàn bộ vào file `TỔNG HỢP BC TIÊU THỤ TOÀN TẬP ĐOÀN (DD.MM.YYYY).xlsx`.
- **Output** có 2 sheet: `(NN) TT&TK` (Tiêu thụ & Tồn kho) và `(NN) THUMUA` — `NN` là số tuần.

## Tần suất & mốc thời gian
- **Chốt số liệu**: thứ 5 hàng tuần.
- **Gửi báo cáo**: thứ 6 hàng tuần.
- Số liệu là **lũy kế** từ 01/01 đến ngày chốt, kèm cột tăng/giảm so với tuần trước.

## Sheet 1 — Tiêu thụ & Tồn kho (TT&TK)
Đơn vị tính: **Tấn**. Mỗi dòng = 1 đơn vị thành viên; có dòng tổng theo khu vực + dòng TẬP ĐOÀN.
Nhóm cột chính:
- **KH Sản xuất + Thu mua**: Khai thác / Thu mua / Cộng.
- **Tổng số lượng đã ký** theo HĐ Dài hạn (HĐDH) và HĐ Chuyến.
- **Tiêu thụ** tách 4 luồng: HĐDH (XK&UTXK / Nội tiêu) và HĐ Chuyến (XK&UTXK / Nội tiêu).
- **Tồn kho thành phẩm**: tổng, phần *đã có HĐ* và *chưa có HĐ*.
- **Tồn kho chi tiết theo loại mủ**: CV50/60 · SVR10CV/20CV · SVRL/3L & 3L Mix · RSS ·
  SVR5/5S · SVR10/20 · Latex (quy khô) · Ngoại lệ · Skim · SVR10 Mix.
- **Tồn kho Nguyên liệu** (không tính là thành phẩm tồn kho).
- Tiêu thụ HĐDH / HĐ Chuyến + Ghi chú.

### Quy ước tồn kho (ghi chú trong file)
- *Tồn kho thành phẩm* = số lượng gồm cả **chưa có HĐ** và **đã có HĐ** (đã ký nhưng chưa giao;
  với HĐDH là lượng ký đã xác định giá bán).
- *Tổng tồn kho thực tế* = tổng tồn kho các loại mủ thành phẩm liệt kê ở trên.
- *Nguyên liệu*: không phải sản phẩm tồn kho.

## Sheet 2 — Thu mua (THUMUA)
Báo cáo **sản lượng thu mua lũy kế**, đơn vị Tấn. Cột chính:
- Địa điểm thu mua (chi tiết theo NM/NT của từng đơn vị).
- Mủ nước quy khô · Mủ tạp các loại quy khô · **Tổng lượng mủ quy khô**.
- Tăng/Giảm so với tuần trước · Lũy kế thực hiện · **% Kế hoạch thực hiện** · KH thu mua năm.
- File thu mua đầu vào của từng cty còn có: lũy kế tiêu thụ từ nguyên liệu, **giá bán
  (đồng/tấn) & doanh thu** theo chủng loại (SVR CV60, SVR 3L, SVR 10, CSR 10…).

## Phân vùng & đơn vị thành viên (68 cty, 6 khu vực)
Báo cáo nhóm theo khu vực địa lý:

| Mã | Khu vực | Đơn vị (rút gọn) |
|---|---|---|
| I | Đông Nam Bộ | Bà Rịa, Bình Long, Dầu Tiếng, Đồng Nai, Đồng Phú, Hàng Gòn, Hòa Bình, Lộc Ninh, Phước Hòa, Phú Riềng, Phú Thịnh, Tân Biên, Tây Ninh, Trường CĐCS, Viện NCCS VN |
| II | Tây Nguyên | Bảo Lâm, Chư Mom Ray, Chư Păh, Chư Prông, Chư Sê, Đồng Phú–Đăk Nông, Eah'Leo, Kon Tum, Krông Buk, Mang Yang, Phước Hòa Đắk Lắk, Sa Thầy |
| III | DHMT (Duyên hải Miền Trung) | Bình Thuận, Hà Tĩnh, Hương Khê–Hà Tĩnh, Nam Giang–Quảng Nam, Nghệ An, Phú Yên, Quảng Nam, Quảng Ngãi, Quảng Trị, Thanh Hóa |
| IV | MNPB (Miền núi phía Bắc) | Điện Biên, Dầu Tiếng–Lai Châu, Dầu Tiếng–Lào Cai, Hà Giang, Lai Châu, Lai Châu 2, Mường Nhé–ĐB, Sơn La, Yên Bái |
| V | Campuchia | Bean Heack, Bà Rịa–Kamp, Chư Pah K (CRCK), Chư Prông–Stung Treng, CRCK2, Đồng Nai–Kratie, Đồng Phú–Kratie, Dầu Tiếng–Camp, Dầu Tiếng–Kratie, EaH'Leo BM, Krông Buk–Ratanakiri, Mê Kông, Hoàng Anh HAMY.K, Phước Hòa–Kamp, Tân Biên–Kamp, Tây Ninh–Siêm Riệp, VKETI–Lộc Ninh |
| VI | Lào | VRG Oudomxay, Dầu Tiếng–Việt Lào, Bolykhamsay–Hà Tĩnh, Quasa–Geruco, Việt–Lào |

### Ghi chú sáp nhập đơn vị (2025–2026)
- Bình Long → **Lộc Ninh**; Quảng Ngãi → **Kon Tum**; Hương Khê Hà Tĩnh → **Hà Tĩnh**;
  Nam Giang Quảng Nam → **Quảng Nam**; Mang Yang → **Chư Sê**.

## Lưu ý số hóa
- Tên đơn vị input không đồng nhất (vd `Eahleo BM` vs `Cty Kausu EaHLeo BM`) → cần bảng
  ánh xạ chuẩn hóa khi tự động hóa ingest.
- File `.xls` cũ (nhiều đơn vị Lào/Campuchia/Tây Nguyên) cần convert sang `.xlsx` để đọc.
