# Giai đoạn 5 — Bổ sung số thực hiện còn thiếu

Trạng thái: **chưa làm, chưa quyết định hướng**. Chỉ làm khi chủ dự án muốn so được 3 nhóm này.

Kế hoạch của 3 nhóm này vẫn được nhập ở Giai đoạn 1 để làm mốc, nhưng hệ thống chưa có số thực hiện để so.

## 1. Khai thác (`plan_exploit_tonnes`)
Chưa có biểu nào ghi sản lượng khai thác; báo cáo kỳ chỉ hiện chỉ tiêu, không tính % (cố ý, đừng lấy số thu mua làm tử số).
Hướng: thêm ô nhập sản lượng khai thác (theo tháng hoặc theo ngày, cần chủ dự án chọn).

## 2. Chế biến (mủ khai thác · mủ thu mua · tổng)
Không biểu nào ghi sản lượng chế biến. Tồn kho thành phẩm "chế biến chưa nhập kho" là số tồn, không phải sản lượng ra.
SCADA nhà máy thông minh chỉ có 1 nhà máy (Phú Riềng) và đơn vị là bành.
Hướng (chọn một):
1. Thêm ô nhập sản lượng chế biến theo ngày, theo chủng loại. Chính xác nhất, nhưng đơn vị phải nhập thêm.
2. **Ước tính từ cân đối**: chế biến ≈ tiêu thụ + (tồn kho thành phẩm cuối kỳ − đầu kỳ) − thu mua thành phẩm. Không bắt đơn vị nhập thêm,
   nhưng chỉ là ước tính và cần tồn kho đủ ngày. **Chưa thử trên số thật** — nên thử trên vài đơn vị trước.
3. Đọc từ SCADA cho nhà máy đã kết nối.

## 3. Tồn kho thành phẩm theo nguồn (khai thác · thu mua · hàng hóa)
Tồn kho đang khai theo chủng loại (khối 1 chưa nhập kho + khối 2 đã nhập kho), không có nguồn; không suy được nguồn từ chủng loại.
Hướng: thêm trường "nguồn" vào dòng tồn kho, giống cách đã làm cho nguồn tiêu thụ ở từng dòng chủng loại (05/10/2026).
Đơn vị khai thêm 1 cột; số cũ chưa có nguồn thì để "chưa khai", không đoán.

## Việc cần làm
- [ ] Chủ dự án chọn hướng cho từng nhóm.
- [ ] Thử phương án cân đối (hướng 2 của chế biến) trên bản sao prod, báo độ lệch.
