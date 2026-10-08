# Rà chéo Dashboard đơn vị với các màn khác — tổng hợp (29/09/2026)

Đo trên bản sao prod `vrg_prod_0929` (chỉ đọc). Chi tiết + file:dòng ở 3 báo cáo nhánh:
`260929-dashboard-crosscheck-thu-mua.md` · `260929-dashboard-crosscheck-tieu-thu.md` · `260929-dashboard-crosscheck-ton-kho.md`.

## Đã khớp (không phải lo)
- Thu mua: sản lượng, KH, %, giá BQ khớp Thống kê thu mua · Chỉ số đơn vị · Báo cáo theo kỳ (TĐ lũy kế 50.963 t, 48,2%).
- Tiêu thụ/doanh thu mức ĐƠN VỊ khớp Báo cáo tổng hợp (8 đơn vị, cả đơn vị nhận sáp nhập): "Đã giao lũy kế" = cột P,
  "Tiêu thụ HĐ chuyến" = cột M, % KH chuyến và % KH doanh thu bằng nhau.
- Tồn thành phẩm từng đơn vị khớp mọi màn; không cộng trùng đơn vị sáp nhập.

## A. Sai số — sửa được ngay, không đổi luật nghiệp vụ
| # | Chỗ sai | Số thật | Kiểm lại |
|---|---|---|---|
| A1 | Ngày chốt tồn kho mặc định = HÔM NAY, trong khi đơn vị được nhập tới 11:00 hôm sau | KPI tồn TĐ 29/09 = 6.113 t (12 đv có số) vs 28/09 = 52.271 t (51 đv); biểu đồ cạnh đó lại lấy 27/09 | ✅ đã kiểm |
| A2 | "Đã ký HĐ chưa giao" thiếu hợp đồng của đơn vị đã sáp nhập | Lộc Ninh 28/09: 1.295,7 vs 1.492,6 t ở Báo cáo tổng hợp (196,9 t của Bình Long) | ✅ đã kiểm |
| A3 | Trợ lý AI: % KH thu mua theo đơn vị lấy từ hàm vẽ biểu đồ (chỉ giữ nhóm lớn, còn lại dồn "Khác") | Sai 26/38 đơn vị: Phú Thịnh 0% (thật 52,7%), Chư prông 0% (132%) | ✅ đã kiểm |
| A4 | Trợ lý AI: % doanh thu = DT cả TĐ ÷ KH của 27 đơn vị; giá BQ tính trung bình cộng | 213,2% vs 80,6%; mủ nước 549,9 vs 556,8 đ/độ | |
| A5 | Thống kê tiêu thụ: cột KH doanh thu và % KH doanh thu luôn trống | — | |
| A6 | "Ngày lấy số" tồn kho hiện ngày chốt, không phải ngày đơn vị khai → số cũ không bị cảnh báo | Dầu Tiếng Lai Châu: số 30/08 hiện là "28/09" | |
| A7 | Ngày "không thu mua" đếm trùng ở đơn vị nhận sáp nhập | Lộc Ninh 201 + 154 ngày trong kỳ 272 ngày | |
| A8 | Nhãn cũ "KH (KT + TM)" ở bảng Tiến độ bán hàng | — | ✅ đã sửa, commit 58ca350 (chưa deploy) |

## B. Cần chủ dự án / Ban TTKD chốt luật
| # | Hai cách đang cho hai số | Số thật |
|---|---|---|
| B1 | Bán NỘI BỘ mẹ–con ở cấp Tập đoàn: Dashboard cộng, Báo cáo tổng hợp thì không | 407.910 vs 403.650 t — lệch 4.260 t (202,6 tỷ) ✅ đã kiểm |
| B2 | HĐDH còn hiệu lực sau 31/12 có tính vào "phải giao đến cuối năm" không | 29.624 t (23,6%) + 1.598 tỷ DT dự kiến |
| B3 | "Có thể giao dịch" có 3 công thức ngay trên Dashboard | KPI 15.214 t (cho âm) · biểu đồ 31.666 t · theo chủng loại 32.990 t; Dầu Tiếng −931 vs 0 |
| B4 | Luật ngày thiếu số tồn kho: mỗi màn một luật (đang chờ chốt từ trước) | Cùng Tập đoàn: 52.271 · 52.098 · 56.667 · 59.973 · 60.145 · 61.019 t |
| B5 | % KH cấp nhóm: Dashboard theo rổ đơn vị có KH, Thống kê/Chỉ số đơn vị chia tổng cho tổng | HĐ chuyến TĐ 70,1% vs 74,5%; Đông Nam Bộ 95,8% vs 108,6% |
| B6 | KH của đơn vị nhận sáp nhập: Dashboard cộng KH đơn vị cũ, màn Kế hoạch năm thì không | Lộc Ninh 11.500 vs 8.500 t; TĐ 105.700 vs 102.000 t |
| B7 | Nguồn KH bán hàng: mới 5–6 đơn vị có KH khai thác; "KH chuyến + HĐDH đã ký" có ở 61 đơn vị và trùng KH bán hàng ở Tân Biên (9.500), Tây Ninh, Đồng Nai | Có dùng làm dự phòng khi chưa nhập KH khai thác? |
| B8 | Hai số "đã giao dài hạn" trên cùng màn (KPI: mọi HĐ dài hạn trong năm; khối HĐDH: chỉ HĐ có cam kết HĐ mẹ) | Tân Biên 4.681 vs 3.839; Lộc Ninh 6.399 vs 141 t; 13 HĐDH chưa nhập cam kết (9.823 t) |

## C. Khó hiểu — gốc của câu "không hiểu"
- C1. Xem MỘT đơn vị vẫn ghi "Cả phạm vi … (gồm đơn vị chưa giao KH)", số chính hiện "—" (39/63 đơn vị). ✅ đã thấy trên giao diện.
- C2. Đơn vị khai tồn kho = 0 vẫn hiện "—" trong khi trang ghi "— là chưa có số" (10/50 đơn vị ngày 28/09).
- C3. Thẻ "Giá mủ nước BQ" cố định mủ nước: Chư sê (100% mủ chén) hiện "—"; Campuchia hiện giá của 64,7 t.
- C4. "748 ngày có số liệu" trong tháng 29 ngày (thực là lượt đơn vị × ngày).
- C5. Vạch tiến độ thời gian chia đều năm, trong khi tháng 2–4 chỉ ~8% sản lượng → đa số đơn vị bị tô vàng "chậm".
- C6. Tân Biên thấy 3 kế hoạch khác nhau: KH chuyến 4.026,56 (75,7%) · KH bán hàng 4.500 (226%) · còn 9.500 thì không hiện ở đâu.

## D. Dữ liệu cần đơn vị sửa (không phải lỗi công thức)
- Đồng Nai: 3 HĐDH latex không khai quy khô → HĐDH đã giao đội 408 t, 677,5 t nước lẫn vào tổng phải giao.
- Phước Hòa: 241,9 t thành phẩm mua ngoài tháng 9 không có đơn giá (giá BQ bỏ qua, không cảnh báo).
- KH nghi nhập sai: Krông Buk–Ratanakiri 529,7% (KH 100 t) · Điện Biên 308,4% (150 t) · Kon Tum 193,6%.
- Lộc Ninh 122,3% KH chuyến: KH 1.170 t nhưng giao 8.427 t (gồm phần Bình Long).
- Tân Biên · Đồng Nai · Hòa Bình: nhập KH hàng hóa (0.4.97).
