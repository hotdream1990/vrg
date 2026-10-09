# Giai đoạn 4 — So sánh thực hiện trên Dashboard

Trạng thái: **chưa làm** (chờ Giai đoạn 1; nên làm sau khi đơn vị sửa xong nguồn tiêu thụ, hạn theo ghi chú dự án là 12/10/2026).

## Chỉ tiêu nào đã có số thực hiện (đối chiếu code 09/10/2026)
| Nhóm | Số thực hiện | Nguồn trong hệ thống |
|---|---|---|
| Thu mua (nguyên liệu · hàng hóa · tổng) | Có | Biểu Thu mua hằng ngày (`qty_material`, `qty_finished`); Dashboard đã so % thu mua và hàng hóa |
| Tiêu thụ (khai thác · thu mua · hàng hóa · tổng) | Có | Các lần giao hợp đồng, nguồn theo từng dòng (`lines[].source`, `qty_exploit/qty_purchase/qty_goods`) |
| Doanh thu (khai thác · thu mua · hàng hóa · tổng) | Có | Mỗi dòng giao có nguồn + `revenue_vnd`; màn Thống kê gộp theo nguồn được; Dashboard mới hiện tổng |
| Tồn kho thành phẩm | **Chỉ tổng** | Khối 1 + khối 2 của biểu Tồn kho (theo chủng loại, không theo nguồn) |
| KH tiêu thụ HĐ chuyến | Có | `qty_spot` |
| Khai thác · Chế biến · Tồn kho theo nguồn | **Chưa có** | Xem [phase-05](phase-05-bo-sung-so-thuc-hien.md) |

## Việc cần làm
- [ ] Mở rộng khối "Chỉ tiêu năm" của Dashboard đơn vị (`unit_dashboard_targets._ITEMS`) cho các chỉ tiêu có số.
- [ ] Luật rổ giữ nguyên: tử số và mẫu số cùng một rổ đơn vị ĐƯỢC GIAO chỉ tiêu đó.
- [ ] Doanh thu theo nguồn lên Dashboard; thiếu tỷ giá/đơn giá hoặc đơn giá vượt trần thì để trống %, không coi là 0.
- [ ] Tồn kho: số thời điểm, đơn vị thiếu ngày khai thì báo thiếu, không đắp số ngày khác (nguyên tắc `no-cross-date-data-substitution`).

## Cảnh báo
Lần giao nào chưa khai nguồn đều tự tính là "Khai thác" (`sales_contract_calc.line_source`), nên trước khi đơn vị sửa xong,
cột Khai thác bị đội lên và Thu mua/Hàng hóa bị thấp. Đừng công bố % theo nguồn trước thời điểm đó.
