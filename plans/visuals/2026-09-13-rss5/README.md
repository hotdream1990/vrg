# RSS 5 — các chỗ đang áp dụng (ghi nhận 13/09/2026, prod 0.4.64+)

RSS 5 nằm ngay dưới RSS 1 trong **danh mục chủng loại dùng chung của đơn vị thành viên**.
Mọi màn đọc danh mục này đều tự có RSS 5. Ảnh chụp trên bản code đã commit, RSS 5 có khung đỏ.

## Có RSS 5

| # | Màn hình | Chỗ xuất hiện | Ảnh |
|---|---|---|---|
| 1 | Báo cáo tồn kho → Thêm số liệu ngày | Ô Chủng loại của tồn kho thành phẩm (chưa nhập kho và đã nhập kho) | `01-ton-kho-chung-loai.png` |
| 2 | Báo cáo thu mua → Thêm số liệu ngày | Ô Chủng loại của bảng Thu mua thành phẩm | `02-thu-mua-thanh-pham-chung-loai.png` |
| 3 | Quản lý hợp đồng → Thêm hợp đồng | Ô Chủng loại ở Chi tiết hợp đồng | `03-hop-dong-ban-chung-loai.png` |
| 4 | Hợp đồng mẹ (HĐNT/HĐDH) → Thêm hợp đồng mẹ | Ô Chủng loại ở phần cam kết | `04-hop-dong-me-chung-loai.png` |
| 5 | Thống kê tồn kho | Bộ lọc Chủng loại | `05-thong-ke-ton-kho-loc-chung-loai.png` |
| 6 | Báo cáo tiêu thụ | Bộ lọc Chủng loại | `06-bao-cao-tieu-thu-loc-chung-loai.png` |
| 7 | Báo cáo tổng hợp → Tiêu thụ – Tồn kho | Thêm cột tồn kho RSS 5 (có cả trong Xuất Excel) | `07-bao-cao-tong-hop-cot-rss5.png` |
| 8 | Hợp đồng cũ (trước 30/07) | Bộ lọc Chủng loại | `08-thong-ke-hop-dong-loc-chung-loai.png` |
| 9 | Thống kê tiêu thụ | Bộ lọc Chủng loại | `09-thong-ke-tieu-thu-loc-chung-loai.png` |

Không chụp riêng:
- **Thống kê thu mua**: bộ lọc Chủng loại chỉ hiện khi chọn loại Thu mua thành phẩm. Dùng cùng danh mục.
- **File mẫu Excel nhập Thu mua / Tồn kho**: sheet Danh mục đã có RSS 5, nhưng nút "Tải mẫu Excel"
  hiện đang **tắt trên giao diện**. Khi bật lại thì ô chọn chủng loại trong file sẽ có RSS 5.
- **Kiểm tra khi lưu**: hợp đồng, hợp đồng mẹ và báo cáo ngày nhận RSS 5 là chủng loại hợp lệ.
  RSS 5 dùng như RSS 3: cảnh báo đơn giá theo cùng khoảng, **không** bắt nhập quy khô.

## Không có RSS 5 (cố ý)

Tập đoàn không ra giá sàn cho RSS 5, nên các màn sau giữ nguyên:
Giá sàn Tập đoàn · Bản tin ngày · Báo cáo tuần · Gợi ý giá sàn · Báo giá mủ thị trường · Tờ trình giá sàn.
