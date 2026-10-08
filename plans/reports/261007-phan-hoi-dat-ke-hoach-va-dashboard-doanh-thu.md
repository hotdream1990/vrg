# Phân tích phản hồi anh Đạt (VRG) — 07/10/2026

Nguồn: tin nhắn Zalo + file `KH_UTH_2026_chuan_phan_mem_QLDT_V1_061026.xlsx` (lấy sheet **"1. KH 2026 Phan mem"**).
Số liệu hệ thống đo trên bản sao prod ngày **06/10/2026** (`vrg_prod_1006`).

Hai yêu cầu:
1. **Kế hoạch**: Ban nạp KH 2026 vào phần mềm → **đơn vị vào xác nhận** → làm mốc so sánh thực hiện.
2. **Dashboard**: chia **doanh thu** theo nguồn (mủ khai thác · thu mua · hàng hóa) và theo loại HĐ
   (dài hạn · nguyên tắc · **BBGN** · chuyến).

---

## 1. Kế hoạch 2026 — file anh Đạt gửi

### 1.1 File có gì
- 72 công ty × 19 chỉ tiêu, nguồn file QLĐT của Ban Kế hoạch; file đã tự đối chiếu, tổng chênh 0.
- 5 nhóm: Khai thác (tổng · tự KT · nhượng quyền) · Thu mua (tổng · NL · TP) · Chế biến (4 cột) ·
  Tiêu thụ (tổng · KT · NQ · thu mua gồm TP) · Doanh thu **triệu đồng** (tổng · KT · tự KT · NQ · thu mua).
- Tổng khối: tự KT **439.684 t** (khớp KH giao) · thu mua NL **102.602 t** · thu mua TP **25.920 t** ·
  tiêu thụ **552.650 t** · doanh thu **26.936 tỷ**.
- Doanh thu tổng (cột S) = DT khai thác + DT thu mua, **không gồm** bán mủ NL và DT khác — thấp hơn
  "DT bán hàng" dòng 57 (27.902 tỷ).

### 1.2 Khớp tên công ty với phần mềm
- **60/72** công ty khớp được với đơn vị trên phần mềm (bảng ở Phụ lục A — cần anh Đạt duyệt nhanh).
- **9** dòng toàn số 0 → bỏ qua (Phước Hoà Đắk Lắk 02TV và 8 công ty "(VN)" ở Campuchia).
- **3** dòng có số nhưng phần mềm **chưa có đơn vị**: Quanvan (KT 120 t) · CP Quasa Geruco (VN)
  (TP 5.020 t, DT 231,3 tỷ) · CP Cao su Việt Lào (VN) (TP 2.800 t, DT 126,3 tỷ).
- Ngược lại **3** đơn vị đang hoạt động trên phần mềm **không có trong file**: CP Cao su Hàng Gòn ·
  Viện Nghiên cứu Cao su · CP Cao su Dầu Tiếng Việt Lào (đơn vị tự nhập DT 331,2 tỷ).
- Sáp nhập: file gộp 7 cặp; phần mềm có 4 cặp (Bình Long→Lộc Ninh, Chư Păh→Chư Prông,
  Krông Buk→Eah Leo, Mang Yang→Chư Sê). 3 cặp còn lại (Quảng Ngãi, Hương Khê, Nam Giang) không có
  đơn vị riêng trên phần mềm → không ảnh hưởng.
  ⚠ Bình Long (3.000 t), Chư Păh (200 t), Krông Buk (500 t) **vẫn còn dòng KH 2026 riêng** → khi nạp
  số gộp vào đơn vị nhận phải xoá dòng cũ, nếu không dễ đếm 2 lần.

### 1.3 So với số đơn vị đã tự nhập (60 công ty khớp)

| Chỉ tiêu | Khớp file | Lệch | Đơn vị chưa nhập |
|---|---:|---:|---:|
| KH khai thác (tự KT, cột F) | 7 | 2 | 51 |
| KH thu mua (NL, cột I) | 49 | 11 | 0 |
| KH hàng hóa (TP, cột J) | 1 | 0 | 59 |
| KH doanh thu (cột S) | 18 | 8 | 34 |

Nguyên nhân lệch chính (chi tiết Phụ lục B):
- **Thu mua**: 4 đơn vị nhập NL **cộng** TP, trong khi KH thu mua trên phần mềm chỉ là NL
  (đã chốt 29/09 theo phản ánh Tân Biên): Lộc Ninh + Bình Long 11.500 · Phước Hòa 14.500 ·
  Hà Tĩnh 1.650 · Hòa Bình 1.500.
- **Doanh thu**: mỗi đơn vị lấy một gốc khác nhau. Có đơn vị lấy DT bán hàng (dòng 57), có đơn vị
  chỉ lấy DT khai thác (Hà Tĩnh 183,4 thay vì 259,3), Tân Biên 549,4 thay vì 460,5.
- 3 công ty CP "(VN)" ở Campuchia nhập thu mua 0, file ghi 3.100 / 3.100 / 3.200 t.

⇒ Nạp từ file là cách **chuẩn hoá một nguồn**, đúng ý anh Đạt.

### 1.4 Phần mềm hiện nay
- KH năm có 8 ô: khai thác · thu mua · hàng hóa · tiêu thụ HĐ chuyến · HĐDH đã ký · 2 ô chuyển
  năm trước · doanh thu (tỷ đồng). **Chưa có** KH tiêu thụ tổng/theo nguồn, DT tách nguồn, chế biến.
- **Chưa có thao tác "xác nhận kế hoạch"** riêng. KH chỉ bị khoá gián tiếp khi đơn vị bấm
  "Chốt số liệu" một đợt trong năm: **65/67 đơn vị đã chốt** ⇒ KH 2026 đã khoá với đơn vị (muốn sửa
  phải gửi đề nghị). Tài khoản Ban vẫn ghi đè được.

### 1.5 Đề xuất
1. **Nạp KH**: công cụ cho Ban nạp sheet 1 theo bảng tên Phụ lục A (ghi nhật ký hoạt động), ghi đè:
   KH khai thác ← F · KH thu mua ← I · KH hàng hóa ← J · KH doanh thu ← S ÷ 1.000 (tỷ). Xoá KH 2026
   của 3 đơn vị đã sáp nhập (số đã gộp vào đơn vị nhận).
2. **Thêm 5 chỉ tiêu để so thực hiện** — chỉ những ô **có số thực hiện tương ứng** trên phần mềm:
   - KH tiêu thụ tổng (O) · KH tiêu thụ khai thác (P) · KH tiêu thụ thu mua gồm TP (R).
   - KH DT khai thác (T) · KH DT thu mua (W).
   - So: thực hiện "Khai thác" ↔ P/T; thực hiện "Thu mua" + "Hàng hóa" ↔ R/W (file không tách TP).
   - **Không nạp** chế biến (4 cột) và nhượng quyền: phần mềm chưa có số thực hiện để so.
3. **Xác nhận**: màn Kế hoạch năm của đơn vị có nút **"Xác nhận kế hoạch"**. Thấy sai thì gửi
   **đề nghị điều chỉnh**, dùng luồng đề nghị sửa sẵn có, Ban duyệt.
   - Lưu thời điểm và người xác nhận.
   - Checklist đơn vị thêm mục "chưa xác nhận KH 2026".
   - Màn Ban có cột trạng thái xác nhận từng đơn vị.
   - Thông báo qua Hỗ trợ & Thông báo (email + chuông, đã có sẵn).
   - Ban nạp lại số mới thì xác nhận cũ tự huỷ, đơn vị phải xác nhận lại.
4. **So sánh**: khối Chỉ tiêu ở Dashboard thêm các dòng mới (tiêu thụ theo nguồn, doanh thu theo nguồn).

---

## 2. Dashboard — chia doanh thu

### 2.1 Hiện trạng
- Tách theo **nguồn** (KT/TM/HH) và **loại HĐ** (chuyến/HĐNT/dài hạn) đã có nhưng **chỉ theo tấn**.
  Doanh thu mới có 1 số tổng (theo đơn vị, theo chủng loại).
- Phía máy chủ đã có sẵn cách gom doanh thu theo nguồn và theo loại HĐ (màn Thống kê dùng) → thêm
  vào Dashboard là việc **nhỏ**.

### 2.2 Số thật 01/01–06/10/2026

| Theo loại HĐ | Tấn | Doanh thu (tỷ) |
|---|---:|---:|
| HĐ chuyến | 275.759 | 14.714 |
| HĐ dài hạn | 132.508 | 7.265 |
| HĐ nguyên tắc | 13.718 | 770 |

| Theo nguồn | Tấn | Doanh thu (tỷ) |
|---|---:|---:|
| Khai thác | 413.813 (98%) | 22.277 |
| Thu mua | 6.940 | 403 |
| Hàng hóa | 1.231 | 69 |

⚠ **Số theo nguồn chưa dùng được**: KH tiêu thụ thu mua (gồm TP) cả năm là 129.047 t (**23%**),
thực hiện mới ghi 8.172 t (**2%**). Phần lớn lần giao đang để mặc định "Khai thác". Hạn đơn vị tự sửa
nguồn là **08/10**; còn 394 lần giao ghi chú "(mủ thu mua)" (~22.500 t) chờ quyết định có khôi phục
bằng SQL hay không. Lên Dashboard trước khi sửa thì cột Thu mua sai rõ.

### 2.3 BBGN
- Phần mềm **chưa có** loại này.
- Trong dữ liệu chỉ **4 lần giao (322,6 t)** có mã "BBGN": Dầu Tiếng `01-86/BBGN-VRG-DT`,
  `02-86/BBGN-VRG-DT`; Bà Rịa `76/BBGN-PL01` (file đính kèm ghi "Tập đoàn").
- Có vẻ là **hàng giao cho Tập đoàn theo HĐ do Tập đoàn ký** (số 76, 86…), hiện đang lưu là
  **HĐ chuyến**. Đơn vị khác có thể đang khai loại này dưới tên khác → cần định nghĩa trước khi làm.

---

## 3. Câu hỏi cần anh Đạt chốt

1. **BBGN** là gì chính xác? Có phải giao cho Tập đoàn theo HĐ Tập đoàn ký? Có hồ sơ mẹ chung không
   (như HĐ 76, 86)? Doanh thu tính cho đơn vị giao như bán thường?
2. **KH doanh thu** lấy cột S "DT tổng" (26.936 tỷ) hay "DT bán hàng" dòng 57 (27.902 tỷ)?
   Thực hiện trên phần mềm = mọi lần giao hàng cao su (gần cột S).
3. **3 công ty chưa có trên phần mềm** (Quanvan, CP Quasa Geruco (VN), CP Cao su Việt Lào (VN)):
   có tạo đơn vị không? "CP Cao su Việt Lào (VN)" có phải "CP Cao su Dầu Tiếng Việt Lào" không?
   Hàng Gòn, Viện NC, Dầu Tiếng Việt Lào không có trong file → giữ KH đơn vị đã nhập?
4. Đơn vị thấy KH sai khi xác nhận: **gửi đề nghị để Ban duyệt** (đề xuất) hay được tự sửa?
5. **Chế biến + nhượng quyền**: không nạp vì chưa có số thực hiện để so — đồng ý?
6. % thực hiện: tính trên **mọi KH đã nạp** hay **chỉ đơn vị đã xác nhận**?

## 4. Thứ tự đề xuất
1. **Dashboard doanh thu theo loại HĐ** (3 loại sẵn có) — làm ngay được.
2. **Doanh thu theo nguồn** — làm cùng, nhưng chỉ có ý nghĩa sau khi đơn vị sửa nguồn (sau 08/10).
3. **Nạp KH + xác nhận + 5 chỉ tiêu mới** — sau khi anh Đạt trả lời câu 2–6.
4. **BBGN** — sau khi có định nghĩa (câu 1).

---

## Phụ lục A — Bảng khớp tên (60 công ty)

| # | Tên trong file | Đơn vị trên phần mềm |
|---|---|---|
| 1 | CS Dầu Tiếng | Công ty TNHH MTV Cao su Dầu Tiếng |
| 2 | CS Đồng Nai | Công ty TNHH MTV Tổng Công ty Cao su Đồng Nai |
| 3 | CS Lộc Ninh | Công ty TNHH MTV Cao su Lộc Ninh |
| 4 | CS Phú Riềng | Công ty TNHH MTV Cao su Phú Riềng |
| 5 | CP CS Bà Rịa | Công ty Cổ phần Cao Su Bà Rịa |
| 6 | CP CS Hòa Bình | Công ty Cổ phần Cao Su Hòa Bình |
| 7 | CP CS Đồng Phú | Công ty Cổ phần Cao Su Đồng Phú |
| 8 | CP CS Phú Thịnh | Công ty Cổ phần Đầu tư Xây dựng Cao su Phú Thịnh |
| 9 | CP CS Phước Hòa | Công ty Cổ phần Cao Su Phước Hòa |
| 10 | CP CS Tân Biên | Công ty Cổ phần Cao Su Tân Biên |
| 11 | CP CS Tây Ninh | Công ty Cổ phần Cao Su Tây Ninh |
| 12 | CS Chư prông | Công ty TNHH MTV Cao su Chư prông |
| 13 | CS Chư sê | Công ty TNHH MTV Cao su Chư sê |
| 14 | CS Eahleo | Công ty TNHH MTV Cao su Eah Leo |
| 15 | CS Kon Tum | Công ty TNHH MTV Cao su Kon Tum |
| 16 | CP CS Bảo Lâm | Công ty Cổ phần Cao Su Bảo Lâm |
| 17 | Chưmom rây | Công ty TNHH MTV Cao su Chưmomray |
| 18 | CS Phước Hòa Đắc Lắc | Công ty TNHH Cao su Phước Hòa - Đăk Lăk |
| 19 | CP CS Sa Thầy | Công ty Cổ phần Cao Su Sa Thầy |
| 20 | CS Bình Thuận | Công ty TNHH MTV Cao su Bình Thuận |
| 21 | CS Hà Tĩnh | Công ty TNHH MTV Cao su Hà Tĩnh |
| 22 | CS Quảng Nam | Công ty TNHH MTV Cao su Quảng Nam |
| 23 | CS Quảng Trị | Công ty TNHH MTV Cao su Quảng Trị |
| 24 | CS Thanh Hóa | Công ty TNHH MTV Cao su Thanh Hóa |
| 25 | CP CS Nghệ An | Công ty Cổ phần Đầu tư Phát triển Cao su Nghệ An |
| 26 | CP CS D.Tiếng Lai Châu | Công ty Cổ phần Cao Su Dầu Tiếng Lai Châu |
| 27 | CP CS D.Tiếng Lào Cai | Công ty Cổ phần Cao Su Dầu Tiếng Lào Cai |
| 28 | CP CS Điện Biên | Công ty Cổ phần Cao Su Điện Biên |
| 29 | CP CS Hà Giang | Công ty Cổ phần Cao Su Hà Giang |
| 30 | CP CS Lai Châu | Công ty Cổ phần Cao Su Lai Châu |
| 31 | CP CS Lai Châu 2 | Công ty Cổ phần Cao Su Lai Châu II |
| 32 | CP CS M.Nhé Điện Biên | Công ty Cổ phần Cao Su Mường Nhé Điện Biên |
| 33 | CP CS Sơn La | Công ty Cổ phần Cao Su Sơn La |
| 34 | CP CS Yên Bái | Công ty Cổ phần Cao Su Yên Bái |
| 35 | TNHH Bà Rịa Kampong Thom | Công ty TNHH Phát triển Cao su Bà Rịa - Kampong Thom |
| 36 | TNHH CRCK Chưpăh | Công ty Phát triển Cao su C.R.C.K |
| 37 | TNHH Bình Phước 1 | Công ty TNHH Cao su Bình Phước Kratie 1 |
| 38 | TNHH Chưsê K (CRCK2) | Công ty TNHH Phát triển Cao su C.R.C.K.2 |
| 39 | TNHH Bean Heack (CPC) | Công ty TNHH Đầu tư Bean Heack |
| 40 | TNHH D.Tiếng Campuchia | Công ty TNHH Phát triển Cao su Dầu Tiếng – Campuchia |
| 41 | TNHH D.Tiếng Kratie | Công ty TNHH Phát triển Cao su Dầu Tiếng – Kratie |
| 42 | TNHH Đ.Nai Kratie | Công Ty TNHH PTCS Đồng Nai Kratie (DNKC) |
| 43 | TNHH Đồng Phú Kratie | Công ty TNHH Phát triển Cao su Đồng Phú - Kratie |
| 44 | TNHH Krông Buk Ratanakiri | Công ty TNHH Phát triển Cao su Krông Buk - Ratanakiri |
| 45 | TNHH Lộc Ninh Vketi | Công ty TNHH Thương mại Việt Nam Campuchia - VKETI |
| 46 | TNHH H.Anh Mang Yang K | Công ty TNHH Phát triển Cao su Hoàng Anh - Mang Yang K |
| 47 | Eahleo BM | Công ty Cổ phần Cao su KauSu Eahleo BM |
| 48 | TNHH Mê Kông (K) | Công ty TNHH Cao su MeKong |
| 49 | TNHH Phước Hòa K | Công ty TNHH Phước Hòa Kampongthom |
| 50 | TNHH Tân Biên K | Công ty TNHH Phát triển Cao su Tân Biên – Kampong Thom |
| 51 | TNHH T.Ninh Siêmriệp | Công ty Tây Ninh Siêm Riệp Phát triển Cao su |
| 52 | Best Royal | Công ty TNHH MTV Best Royal (K) |
| 53 | CP Đồng Nai Kratie (VN) | Công ty Cổ phần Cao su Đồng Nai - Kratie |
| 54 | CP Chưprông Strung treng (VN) | Công ty Cổ phần Cao su Chư Prông-Stung Treng (VN) |
| 55 | CP Dầu Tiếng Capuchia (VN) | Công ty Cổ phần Cao su Dầu Tiếng Campuchia |
| 56 | CP Dầu Tiếng Kratie (VN) | Công ty Cổ phần Cao su Dầu Tiếng Kratie |
| 57 | TNHH CS Bolykhamxay H.Tĩnh | Công ty TNHH Cao su Hà Tĩnh - Bolikhamxai |
| 58 | TNHH Quasa Geruco | Công ty TNHH Cổ phần Quasa - Geruco |
| 59 | TNHH CS Việt Lào | Công ty TNHH Cao su Việt Lào |
| 60 | TNHH VRG Oudomxay | Công ty TNHH MTV VRG Oudomxay |

## Phụ lục B — Chi tiết lệch giữa số đơn vị đã nhập và file

| Công ty | Chỉ tiêu | Đơn vị đã nhập | Theo file | Ghi chú |
|---|---|---:|---:|---|
| CS Lộc Ninh | KH thu mua (t) | 8.500 | 6.500 | + Bình Long 3.000 = 11.500 = NL + TP (cột H) |
| CP CS Bà Rịa | KH doanh thu (tỷ) | 517,33 | 532,67 |  |
| CP CS Hòa Bình | KH thu mua (t) | 1.500 | 350 | đơn vị nhập NL + TP (cột H) |
| CP CS Hòa Bình | KH doanh thu (tỷ) | 246,53 | 241,36 | đơn vị nhập DT bán hàng (dòng 57) |
| CP CS Phước Hòa | KH thu mua (t) | 14.500 | 10.000 | đơn vị nhập NL + TP (cột H) |
| CP CS Tân Biên | KH khai thác (t) | 3.500 | 3.470 |  |
| CP CS Tân Biên | KH doanh thu (tỷ) | 549,35 | 460,47 |  |
| CP CS Tây Ninh | KH doanh thu (tỷ) | 480,70 | 484,70 |  |
| CS Chư prông | KH thu mua (t) | 500 | 700 |  |
| CS Eahleo | KH khai thác (t) | 7.250 | 8.500 |  |
| Chưmom rây | KH thu mua (t) | 10 | 12 |  |
| CS Hà Tĩnh | KH thu mua (t) | 1.650 | 850 | đơn vị nhập NL + TP (cột H) |
| CS Hà Tĩnh | KH doanh thu (tỷ) | 183,41 | 259,31 | đơn vị nhập DT khai thác (cột T) |
| TNHH Đồng Phú Kratie | KH thu mua (t) | 200 | 100 |  |
| TNHH Đồng Phú Kratie | KH doanh thu (tỷ) | 329,19 | 365,70 |  |
| TNHH Mê Kông (K) | KH doanh thu (tỷ) | 458,11 | 457,00 |  |
| TNHH Phước Hòa K | KH thu mua (t) | 150 | 0 |  |
| CP Đồng Nai Kratie (VN) | KH thu mua (t) | 0 | 3.100 |  |
| CP Dầu Tiếng Capuchia (VN) | KH thu mua (t) | 0 | 3.100 |  |
| CP Dầu Tiếng Kratie (VN) | KH thu mua (t) | 0 | 3.200 |  |
| TNHH VRG Oudomxay | KH doanh thu (tỷ) | 24,48 | 0,00 |  |
