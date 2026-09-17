# Nhu cầu thị trường — chuyển từ ô chữ tự do sang phiếu có trường

> Yêu cầu chủ dự án 17/09/2026. Dữ liệu prod lúc khảo sát: 34 bản ghi chữ / 6 đơn vị (23/07 → 17/09)
> ≈ 62 nhu cầu; tách tự động được 52, 10 mục làm tay (Đồng Phú tiếng Anh/container · Best Royal mua
> mủ nguyên liệu theo kỳ).

## Quyết định đã chốt (17/09/2026)
1. **Mỗi nhu cầu là một PHIẾU**, cập nhật kết quả về sau — không nhập lại mỗi ngày. Cập nhật
   **kết quả · ghi chú** được MIỄN cửa sổ nhập liệu (cửa sổ đơn vị đang = 0).
2. **Mỗi dòng MỘT chủng loại** (khách hỏi 2 loại → 2 dòng, có nút Nhân bản).
3. **Chuyển hết dữ liệu cũ sang trường**, giữ nguyên văn cũ trong Ghi chú; gửi chủ dự án bảng đối
   chiếu TRƯỚC khi ghi prod (đã ghi prod ở 0.4.74: 67 phiếu).
4. **RÚT GỌN** (chủ dự án chốt sau khi xem bản 0.4.74 — thấy tình trạng/số HĐ/ngày ký/từ–đến ngày quá
   rắc rối): **Thời gian giao** và **Kết quả** là Ô CHỮ tự do; bỏ tình trạng, số HĐ, ngày ký, giá
   tạm tính, cặp ngày giao, dải tổng hợp và bộ lọc theo tình trạng. Dữ liệu đã có được gộp thành chữ
   khi khởi động (`db.py`), phiếu chuyển đổi được ghi lại theo lời gốc bằng `convert.py --refresh`.

## Trường
Ngày nhận* · Khách hàng* · Chủng loại* (danh mục `UNIT_GRADES`) · Số lượng + đơn vị (tấn/container)
· Đơn giá + loại tiền (VND = triệu đ/tấn · USD/tấn) · Giao tại · Thời gian giao (chữ) · Kết quả
(chữ, trống = chưa có) · Ghi chú.

## Nhánh làm song song (file KHÔNG giao nhau)
| Nhánh | Người làm | File |
|---|---|---|
| A. Backend | agent | xem `api-contract.md` §Backend |
| B. Web | agent | xem `api-contract.md` §Web |
| C. Chuyển dữ liệu cũ | agent chính | `scripts/migrate-market-demand/*` |
| D. Tích hợp · kiểm thử · review · deploy · sổ tay | agent chính | — |

Bảng chữ cũ `market_demand` GIỮ NGUYÊN (chỉ đọc lịch sử, không còn màn nào ghi).
