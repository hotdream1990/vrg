# Báo cáo tuần — so sánh TRƯỚC (v1) và SAU (v2), 13/09/2026

Căn cứ: `Logic viết Bản tin tuần 16.7.docx` (logic mới) · báo cáo thật `Tuần 35 & 36-2026` · `ANRPC Biweekly Report August issue 1 2026`.
Bản chụp v1: tag git `snapshot/weekly-report-v1-20260913` + `snapshot-v1/` (mô tả cơ chế, PDF + JSON tuần 34).
Bằng chứng v2: `after-v2/Bao-cao-tuan-35-36-2026-v2.pdf` (kỳ gộp, dữ liệu prod, AI + ANRPC) · `after-v2/Bao-cao-tuan-34-2026-v2.pdf`.
Trạng thái: chạy trên máy dev, **chưa commit, chưa deploy**.

## 1. Khác biệt chính

| Hạng mục | TRƯỚC (v1) | SAU (v2) |
|---|---|---|
| Kỳ báo cáo | Chỉ 1 tuần | 1, 2 hoặc 3 tuần gộp (vd 35–36 do lễ 02/09); tiêu đề "Tuần 35 và 36 năm 2026: 24/8/2026 – 4/9/2026" + ô ghi chú lý do gộp |
| Bảng 3.1 / 3.2 | Tuần trước · tuần này · +/- · % | Mọi kỳ (kể cả 1 tuần): mỗi tuần 1 cột + cột "+/- (T35/T34)" có dấu từng cặp, bỏ cột % — đúng mẫu 35–36 |
| Ghi chú dưới bảng | Không có | Tự sinh từ dữ liệu: "sàn MRE (SMR CV, SMR20, LATEX) không có giá ngày 25/8"; tách riêng "chưa quy đổi được USD ngày 3/9, 4/9 (thiếu tỷ giá USD/JPY)"; + ô ghi chú tay (vd "Giá physical tuần này tham khảo theo ANRPC") |
| Cao/thấp | Chỉ USD/tấn | USD/tấn + giá nội tệ (JPY/kg · CNY/tấn · US cent/kg) + ngày + tuần, tính cả kỳ |
| Giá 0 (No Trading) | Lọt vào trung bình (SGX tuần 33 bị kéo từ 2.737,0 xuống 2.189,6) | Loại khỏi mọi phép tính |
| Mủ nước 3.3 | Lớp giá `vrg`, không lọc khu vực | Căn đúng bản tin ngày (lớp `vrg`, đơn vị đã gán khu vực, bỏ giá 0); ô sửa tay không còn "lưu cứng" số tự tính |
| Phần IV | 4 tiêu đề cố định: Năng lượng · Cung–Cầu · Tỷ giá Nhật · TQ | Mặc định theo báo cáo thật 35–36: 1 Năng lượng, Địa chính trị & Butadiene · 2 Cung – Cầu · 3 Tỷ giá và Tài chính Nhật Bản · 4 Kinh tế TQ & yếu tố khác; **sửa được tiêu đề**; báo cáo cũ giữ tiêu đề cũ |
| Phần V | "Xu hướng chủ đạo / Tiêu điểm quan sát" | Đoạn mở + "Hỗ trợ giá / Kìm hãm đà tăng", tham khảo Kịch bản Tích lũy / Tiếp tục điều chỉnh |
| Nguồn tham khảo | Cố định trong code | **Danh mục cấu hình được** (14 nguồn mặc định theo mục SOURCE của logic): tên, vai trò, link, mục dùng, hướng dẫn cách lấy, cách dùng (dữ liệu hệ thống / tự lấy số / tự đọc tin / đính kèm / link tay), bật-tắt, khôi phục mặc định. Hiện dạng chip link ngay dưới từng phần viết |
| Tài liệu đính kèm | Không có | Tải PDF/DOCX theo từng báo cáo (vd ANRPC) → trích chữ (giữ bảng số) → "AI tóm tắt số liệu chính" theo đúng mục logic yêu cầu (sản lượng/tiêu thụ % YoY, cán cân, nhận định ngắn hạn, Baht/Ringgit, dầu/Butadien, thời tiết, TQ, bảng giá) → sửa tay → AI viết báo cáo đọc phần này |
| DXY · WTI · Brent | Không có | Tự lấy giá đóng cửa ngày (CNBC, dự phòng Yahoo Finance — đối chiếu TB tuần 34–36 trùng tuyệt đối), TB từng tuần + % + cao/thấp, nút đối chiếu Investing.com |
| Tỷ giá cho AI | JPY/CNY/MYR, 1 con số | USD/JPY · CNY · MYR · **THB** từng tuần + % + chú giải chiều ("USD/JPY tăng = Yên yếu") |
| Tin vietnambiz | 1 bài mới nhất (không theo kỳ) | Mọi bài "Giá cao su hôm nay" **đăng trong kỳ** (kỳ 35–36: 12 bài), hiện danh sách link trên màn |
| AI viết III.1 | AI tự viết cả số → có thể sai | **Số do hệ thống dựng** (giá TB, %, cao/thấp, ngày, nội tệ, ghi chú thiếu giá); AI chỉ viết cụm nguyên nhân theo logic tương quan từng sàn |
| Kiểm tra AI | Chỉ dặn trong prompt | Cảnh báo **số không đối chiếu được** với dữ liệu/tài liệu + cảnh báo **từ tuyệt đối** (hoàn toàn, 100%, đương nhiên, chắc chắn, tuyệt đối) ngay dưới ô |
| Tóm tắt tuần trước (I) | Chỉ có bảng số | Đọc thêm Phần II đã lưu của báo cáo tuần trước để viết nhất quán |
| PDF | Tiêu đề cố định, gạch 2 cấp | Tiêu đề theo kỳ, masthead có dòng kỳ + ghi chú, gạch 3 cấp, **đậm**/*nghiêng*, "Các yếu tố vĩ mô ảnh hưởng", bảng nhiều tuần vừa A4, escape HTML |

## 2. Đối chiếu số với báo cáo thật tuần 35–36 (dữ liệu prod)
- Bảng 3.1: **7/7 dòng × 2 tuần khớp tuyệt đối** (OSE 2.763,6 / 2.737,3 · SHANGHAI 2.772,6 / 2.801,4 · SGX RSS3 2.754,8 / 2.732,0 · TSR20 2.374,0 / 2.356,0 · SMR CV 2.938,4 / 2.948,4 · SMR20 2.426,1 / 2.417,6 · LATEX 1.701,2 / 1.705,3).
- Cao/thấp USD và ngày: khớp cả 7 chủng loại.
- **Chênh với báo cáo thật (hệ thống đúng theo dữ liệu):**
  - Giá nội tệ ở mẫu không khớp chính giá USD của mẫu: SGX cao nhất 2.780 USD/tấn = 278,0 US cent/kg (mẫu ghi 229,5); SHANGHAI 2.821 USD/tấn ≈ 18.960 CNY/tấn (mẫu 18.150); OSE 443,6 JPY/kg (mẫu 448,2).
  - Mẫu ghi "OSE và SHANGHAI không có giá ngày 3/9 và 4/9". Thực tế hai sàn **có giao dịch**; do **thiếu tỷ giá USD/JPY, USD/CNY** hai ngày đó nên không quy đổi được. v2 ghi đúng bản chất.
- Giá giao ngay (reuters) trên prod không có từ sau 20/8 → hệ thống ghi "chưa có giá giao ngay … cả tuần" (mẫu thật cũng phải lấy theo ANRPC).

## 3. Làm được
1. Snapshot v1 (tag git + tài liệu + PDF/JSON).
2. Kỳ gộp 1–3 tuần, xử lý cả tuần vắt năm (53/2026 → 1/2027).
3. Ghi chú thiếu giá / thiếu tỷ giá tự động; cao/thấp kèm nội tệ.
4. Danh mục nguồn tham khảo cấu hình được + gợi ý nguồn theo từng phần.
5. Đính kèm PDF/DOCX + AI tóm tắt + AI dùng khi viết (đã chạy thật với file ANRPC).
6. DXY/WTI/Brent tự động; tỷ giá THB/MYR theo logic SGX/MRE.
7. Tin vietnambiz đúng kỳ.
8. AI theo logic 16.7 (khung IV mới, logic tương quan, V theo kịch bản, tránh từ tuyệt đối), số III.1/III.2 dựng bằng code, cảnh báo số và từ tuyệt đối.
9. PDF + web theo mẫu 35–36.
10. Kiểm chứng:
    - Test: 92 test báo cáo tuần và 490/493 test toàn bộ đạt. 3 test lỗi thuộc module hợp đồng bán hàng, do dữ liệu DB dev, không liên quan đợt này.
    - Web: type-check và build sạch.
    - Rà soát code 3 góc (đúng/sai, bảo mật, web) và đã sửa hết lỗi Cao/Trung bình. Trong đó gồm: SSRF (chỉ cho tự đọc vietnambiz.vn), file DOCX/PDF độc, chống ghi nhầm tuần khi AI chạy, mất chữ khi đổi tuần.

## 4. Chưa làm được / giới hạn
1. **Investing.com chặn truy cập tự động (HTTP 403).** DXY/WTI/Brent lấy từ CNBC (Yahoo chặn IP máy chủ prod — HTTP 429), dự phòng Yahoo, có nút mở Investing.com để đối chiếu. Không làm ô nhập tay (đã chốt 13/09).
2. **Tin EUDR (Bộ Công Thương), SBV, CafeF, Tinnhanhchungkhoan: chỉ là link tham khảo.** Hệ thống không tự đọc (cấu trúc mỗi trang khác nhau, cần tìm theo từ khoá). Muốn AI dùng thì chuyên viên tải tài liệu vào mục đính kèm.
3. **IRSG phải đăng nhập:** không tự lấy.
4. **AI vẫn có thể lập luận ngược ở ca trái chiều.** Ví dụ trong một sàn có chủng loại tăng, chủng loại giảm (SGX tuần 35), AI từng viết "RSS3 giảm do Baht mạnh lên". Đã siết prompt, nhưng chuyên viên vẫn phải soát. Bộ kiểm tra số chỉ bắt số lạ; không bắt được sai chiều hay gán nhầm sàn.
5. **Giá giao ngay (reuters) trên prod đang trống từ 21/8.** Cần nhập bù qua màn "Giá Physical", nếu không III.2 các kỳ này vẫn trống.
6. ~~Tỷ giá prod thiếu 03–11/09~~ **Đã xử lý 13/09** (0.4.65–0.4.67: sửa nguồn tỷ giá + bù dữ liệu; 0.4.66 thêm cảnh báo tỷ giá cũ). OSE/SHANGHAI tuần 36 nay tính đủ 5 phiên nên số TB khác báo cáo thật (vd OSE 2.741,0 thay 2.737,3).
7. Tài liệu đính kèm gắn theo từng báo cáo, chưa có nút "dùng lại tài liệu tuần trước".
8. **PDF kỳ gộp 35–36 dài 7 trang;** mẫu Word không có số trang để so. Trang nhận định III.1 còn khoảng trống cuối trang.
9. Chưa commit/deploy. Khi deploy:
    - Image thêm `poppler-utils` (đã sửa Dockerfile).
    - 2 bảng mới tự tạo khi khởi động.
    - File đính kèm nằm trong volume `weekly-out` có sẵn.
    - Cần hard-refresh trình duyệt.

## 5. Quyết định cần anh chốt
1. ~~Phần IV theo logic mới hay báo cáo thật 35–36?~~ **Đã chốt 13/09: theo báo cáo thật 35–36** (Năng lượng trước).
2. ~~Bảng một tuần giữ cột %?~~ **Đã chốt 13/09: bỏ, dùng chung kiểu "+/-" có dấu như mẫu 35–36.**
3. ~~Có cần ô nhập tay đè số DXY/WTI/Brent?~~ **Đã chốt 13/09: không cần.**
