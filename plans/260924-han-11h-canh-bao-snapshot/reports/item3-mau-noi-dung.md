# Mẫu nội dung — Cảnh báo tự động gửi đơn vị (Hạng mục 3)

Nội dung dưới đây do hàm dựng nội dung thật (`anomaly_notify.build_messages`) sinh ra từ DB dev `vrg_caosu`, chạy ở chế độ **chỉ đọc** (không tạo luồng, không gửi email), giả định job chạy lúc **11:05 ngày 24/09/2026**.

> Lưu ý đọc số: DB dev là bản sao prod cũ — số liệu đơn vị chỉ tới khoảng **21–22/08/2026**, nên dòng "chưa nộp" / "Đã 33 ngày không nộp" bị phóng to so với thực tế. Trên prod với số liệu hiện hành, danh sách ngày thiếu sẽ ngắn hơn nhiều. Mẫu này để duyệt **câu chữ và bố cục**.

## Thống kê nếu chạy hôm nay

| Cửa sổ nhập N | Ngày vừa hết hạn | Đơn vị đang hoạt động | Đơn vị nhận tin | Chưa có tài khoản lãnh đạo |
|---|---|---|---|---|
| 7 (cấu hình dev để trống → mặc định 7) | 17/09/2026 | 64 | 64 | 63 |
| 1 (như ví dụ của chủ dự án) | 23/09/2026 | 64 | 64 | 63 |

Mẫu bên dưới lấy theo **N = 1** (hết hạn số liệu ngày 23/09/2026).

## Mẫu 1 — Công ty TNHH MTV Cao su Lộc Ninh

**Tiêu đề:** Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026

Nội dung trong mục Hỗ trợ & Thông báo (đường dẫn `/canh-bao-bat-thuong` hiện thành link bấm được):

```text
Tính đến 11:00 hôm nay (hết hạn nhập số liệu ngày 23/09/2026), đơn vị Công ty TNHH MTV Cao su Lộc Ninh còn các vấn đề sau:

1. Chưa nộp đủ báo cáo ngày
- Biểu Thu mua: chưa nộp ngày 23/09/2026 (vừa hết hạn). Từ 01/01/2026 đến 23/09/2026 thiếu 33/266 ngày: 22/08–23/09.
- Biểu Tiêu thụ – Tồn kho: chưa nộp ngày 23/09/2026 (vừa hết hạn). Từ 24/07/2026 đến 23/09/2026 thiếu 32/62 ngày: 23/08–23/09.
- Đã 32 ngày không nộp biểu nào (lần nộp gần nhất 22/08/2026).

2. Có sản lượng thu mua nhưng chưa nhập đơn giá
- Ngày 26/06/2026: Mủ nước (28,79 tấn).

3. Chưa gộp tồn kho sau sáp nhập
- Sau khi nhận Công ty TNHH MTV Cao su Bình Long (từ 21/08/2026), tồn kho khai 2.365,2 tấn — thấp hơn 81,9% so với tổng hai đơn vị trước sáp nhập (13.060 tấn).

Mục nào thuộc ngày đã quá hạn nhập, đơn vị gửi "Đề nghị sửa số liệu" ngay tại màn nhập liệu để Tập đoàn duyệt.
Xem chi tiết tại Cảnh báo bất thường: /canh-bao-bat-thuong?date_from=2026-01-01&date_to=2026-09-23

Tin gửi tự động sau giờ chốt nhập liệu. Đơn vị cần hỗ trợ thì trả lời ngay trong tin này.
```

## Mẫu 2 — Công ty TNHH MTV Cao su Hà Tĩnh

**Tiêu đề:** Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026

Nội dung trong mục Hỗ trợ & Thông báo (đường dẫn `/canh-bao-bat-thuong` hiện thành link bấm được):

```text
Tính đến 11:00 hôm nay (hết hạn nhập số liệu ngày 23/09/2026), đơn vị Công ty TNHH MTV Cao su Hà Tĩnh còn các vấn đề sau:

1. Chưa nộp đủ báo cáo ngày
- Biểu Thu mua: chưa nộp ngày 23/09/2026 (vừa hết hạn). Từ 01/01/2026 đến 23/09/2026 thiếu 237/266 ngày: 01/01–23/07, 22/08–23/09.
- Biểu Tiêu thụ – Tồn kho: chưa nộp ngày 23/09/2026 (vừa hết hạn). Từ 24/07/2026 đến 23/09/2026 thiếu 33/62 ngày: 22/08–23/09.
- Đã 33 ngày không nộp biểu nào (lần nộp gần nhất 21/08/2026).

2. Giá bán trong hợp đồng nghi nhập sai đơn vị tính (mức thường gặp 40–70 triệu đồng/tấn)
- 3 dòng giá bán, cao nhất 50.750.000 (VND), hợp đồng: 01, 1812-02, 34.

Mục nào thuộc ngày đã quá hạn nhập, đơn vị gửi "Đề nghị sửa số liệu" ngay tại màn nhập liệu để Tập đoàn duyệt.
Xem chi tiết tại Cảnh báo bất thường: /canh-bao-bat-thuong?date_from=2026-01-01&date_to=2026-09-23

Tin gửi tự động sau giờ chốt nhập liệu. Đơn vị cần hỗ trợ thì trả lời ngay trong tin này.
```

## Mẫu 3 — Công ty Cổ phần Cao Su Mường Nhé Điện Biên

**Tiêu đề:** Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026

Nội dung trong mục Hỗ trợ & Thông báo (đường dẫn `/canh-bao-bat-thuong` hiện thành link bấm được):

```text
Tính đến 11:00 hôm nay (hết hạn nhập số liệu ngày 23/09/2026), đơn vị Công ty Cổ phần Cao Su Mường Nhé Điện Biên còn các vấn đề sau:

1. Chưa nộp đủ báo cáo ngày
- Biểu Tiêu thụ – Tồn kho: chưa nộp ngày 23/09/2026 (vừa hết hạn). Từ 24/07/2026 đến 23/09/2026 thiếu 33/62 ngày: 22/08–23/09.
- Đã 33 ngày không nộp biểu nào (lần nộp gần nhất 21/08/2026).

2. Chưa khai đủ Kế hoạch năm 2026
- Còn trống: HĐ dài hạn đã ký, HĐ dài hạn năm trước chuyển sang, HĐ chuyến năm trước chuyển sang.

Mục nào thuộc ngày đã quá hạn nhập, đơn vị gửi "Đề nghị sửa số liệu" ngay tại màn nhập liệu để Tập đoàn duyệt.
Xem chi tiết tại Cảnh báo bất thường: /canh-bao-bat-thuong?date_from=2026-01-01&date_to=2026-09-23

Tin gửi tự động sau giờ chốt nhập liệu. Đơn vị cần hỗ trợ thì trả lời ngay trong tin này.
```

## Mẫu email gửi lãnh đạo đơn vị (Mẫu 1)

Email chỉ tóm tắt tên các nhóm vấn đề + link tuyệt đối tới trang Cảnh báo bất thường (và link vào đúng tin để phản hồi). `<APP_BASE_URL>` = địa chỉ web khai ở Cấu hình hệ thống; chưa khai thì email ghi "đăng nhập hệ thống VRG, vào mục Cảnh báo bất thường".

```text
Tiêu đề email: [VRG] Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026

Kính gửi Công ty TNHH MTV Cao su Lộc Ninh,
Hệ thống cảnh báo tự động (sau giờ chốt nhập liệu) vừa gửi một thông tin trên hệ thống VRG.

Tiêu đề: Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026

Tính đến 11:00 hôm nay (hết hạn nhập số liệu ngày 23/09/2026), đơn vị Công ty TNHH MTV Cao su Lộc Ninh còn các vấn đề sau:
1. Chưa nộp đủ báo cáo ngày
2. Có sản lượng thu mua nhưng chưa nhập đơn giá
3. Chưa gộp tồn kho sau sáp nhập

Xem chi tiết tại Cảnh báo bất thường: https://<APP_BASE_URL>/canh-bao-bat-thuong?date_from=2026-01-01&date_to=2026-09-23

Xem và phản hồi tại: https://<APP_BASE_URL>/ho-tro/123

Email tự động từ Hệ thống Dự báo & Quản trị Giá Cao su — vui lòng không trả lời email này.
```
