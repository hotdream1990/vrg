# Giai đoạn 0 — Bảng chỉ tiêu cuối cùng và ánh xạ cột file

Trạng thái: **xong** (còn Q2–Q4 ở [plan.md](plan.md)). Đây là NGUỒN SỰ THẬT: mọi giai đoạn sau bám bảng này.
Bản trình bày cho chủ dự án: tab "Kế hoạch final" trong `../reports/261007-doi-chieu-cot-ke-hoach-file-voi-phan-mem.xlsx`.

## Bảng 7 nhóm · 23 chỉ tiêu
"Lưu" = cột thật trong `unit_purchase_plan`. "Tính" = cộng khi đọc, không lưu. Cột file là chữ cái ở tab 1 của file Ban Kế hoạch.

| # | Nhóm | Chỉ tiêu | Khoá | Đơn vị | Cách nhập | Cột file | Tình trạng |
|---|---|---|---|---|---|---|---|
| 1 | Khai thác | KH khai thác (gồm nhượng quyền) | `plan_exploit_tonnes` | tấn | Nhập · lưu | E (= F + G) | Có sẵn |
| 2 | Thu mua | KH thu mua nguyên liệu | `plan_tonnes` | tấn | Nhập · lưu | I | Có sẵn |
| 3 | Thu mua | KH hàng hóa (thành phẩm mua ngoài) | `plan_goods_tonnes` | tấn | Nhập · lưu | J | Có sẵn |
| 4 | Thu mua | KH tổng thu mua | `purchase_total` | tấn | Tự cộng · tính | H (= I + J) | Mới |
| 5 | Chế biến | Chế biến mủ khai thác | `plan_process_exploit_tonnes` | tấn | Nhập · lưu | L (+ M) | Mới |
| 6 | Chế biến | Chế biến mủ thu mua | `plan_process_purchase_tonnes` | tấn | Nhập · lưu | N | Mới |
| 7 | Chế biến | Chế biến tổng | `process_total` | tấn | Tự cộng · tính | K (= L + N) | Mới |
| 8 | Tiêu thụ | Tiêu thụ khai thác | `plan_consume_exploit_tonnes` | tấn | Nhập · lưu | P (+ Q) | Mới |
| 9 | Tiêu thụ | Tiêu thụ thu mua | `plan_consume_purchase_tonnes` | tấn | Nhập · lưu | R − J (ước tính) | Mới |
| 10 | Tiêu thụ | Tiêu thụ hàng hóa | `plan_consume_goods_tonnes` | tấn | Nhập · lưu | J (ước tính) | Mới |
| 11 | Tiêu thụ | Tiêu thụ tổng | `consume_total` | tấn | Tự cộng · tính | O (= P + R) | Mới |
| 12 | Doanh thu | DT khai thác | `plan_revenue_exploit_ty` | tỷ đồng | Nhập · lưu | T (= U + V) ÷ 1.000 | Mới |
| 13 | Doanh thu | DT thu mua | `plan_revenue_purchase_ty` | tỷ đồng | Nhập · lưu | W × (R − J) ÷ R ÷ 1.000 (ước tính) | Mới |
| 14 | Doanh thu | DT hàng hóa | `plan_revenue_goods_ty` | tỷ đồng | Nhập · lưu | W × J ÷ R ÷ 1.000 (ước tính) | Mới |
| 15 | Doanh thu | KH doanh thu (tổng) | `plan_revenue_ty` | tỷ đồng | Tự cộng · **lưu** | S ÷ 1.000 | Có sẵn, đổi cách nhập |
| 16 | Tồn kho TP | Tồn kho thành phẩm — khai thác | `plan_stock_exploit_tonnes` | tấn | Nhập · lưu | — (file không có) | Mới |
| 17 | Tồn kho TP | Tồn kho thành phẩm — thu mua | `plan_stock_purchase_tonnes` | tấn | Nhập · lưu | — | Mới |
| 18 | Tồn kho TP | Tồn kho thành phẩm — hàng hóa | `plan_stock_goods_tonnes` | tấn | Nhập · lưu | — | Mới |
| 19 | Tồn kho TP | Tồn kho thành phẩm — tổng | `stock_total` | tấn | Tự cộng · tính | — | Mới |
| 20 | Hợp đồng | KH tiêu thụ HĐ chuyến | `plan_sales_spot_tonnes` | tấn | Nhập · lưu | — | Có sẵn |
| 21 | Hợp đồng | HĐ dài hạn đã ký | `signed_lt_tonnes` | tấn | Nhập · lưu | — | Có sẵn |
| 22 | Hợp đồng | HĐ dài hạn năm trước chuyển sang | `carry_lt_tonnes` | tấn | Nhập · lưu | — | Có sẵn |
| 23 | Hợp đồng | HĐ chuyến năm trước chuyển sang | `carry_spot_tonnes` | tấn | Nhập · lưu | — | Có sẵn |

Tổng: **19 cột lưu** (8 có sẵn + 11 mới) và **4 tổng tính khi đọc**. Đã kiểm trên số trong file:
H = I + J, K = L + N, O = P + R, S = T + W đều khớp ở cả 63 công ty có số.

## Quy tắc ánh xạ file → ô (dùng ở Giai đoạn 2)
- **Nhượng quyền** (G, M, Q, V) không là chỉ tiêu riêng; cộng vào khai thác tương ứng (E, L, P, T). M và Q toàn 0.
  G có số ở 4 công ty (1.627 tấn); V ở 4 công ty (255,1 tỷ). Hệ quả: KH khai thác của Dầu Tiếng +890, Tây Ninh +357,
  Chư Prông +300, Tân Biên +80 so với số đang nhập (cột F).
- **F, U** không còn là chỉ tiêu riêng (đã nằm trong E, T).
- **Tách hàng hóa** vì file chỉ có R (tiêu thụ thu mua gồm thành phẩm mua thêm) và W (doanh thu thu mua gồm hàng hóa):
  tiêu thụ hàng hóa = J (coi hàng hóa mua về bán hết trong năm), tiêu thụ thu mua = R − J (không âm ở cả 63 công ty).
  Doanh thu chia W theo tỷ lệ tấn. **Đây là ước tính** (Q3); R − N = J đúng ở 56/63 công ty.
- **Doanh thu**: file tính triệu đồng, phần mềm tính tỷ đồng → chia 1.000.
- **Cột tổng của file** (E, H, K, O, S) chỉ dùng để kiểm; không nạp riêng.

## Quy tắc tổng tự cộng
- Tổng thu mua, chế biến, tiêu thụ, tồn kho: tính khi đọc từ mục con; mục con trống coi như không có; **không có mục con nào → tổng trống** (không hiện 0).
- `plan_revenue_ty`: lưu thật để nơi đang đọc không phải sửa. Server **tự cộng 3 mục con mỗi lần lưu**.
  Đơn vị cũ chỉ có tổng (chưa có mục con) thì giữ số cũ cho tới khi nhập mục con.

## Dữ liệu tham chiếu (tab 1, 72 dòng công ty)
Tổng khối: E 441.311 · F 439.684 · G 1.627 · H 128.522 · I 102.602 · J 25.920 · K 524.302 · L 421.326 · N 102.976 ·
O 552.650 · P 423.603 · R 129.047 · S 26.936 tỷ · T 20.973 tỷ · V 255,1 tỷ · W 5.963 tỷ.
