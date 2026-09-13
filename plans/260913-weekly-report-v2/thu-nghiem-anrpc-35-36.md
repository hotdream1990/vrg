# Thử nghiệm: AI tạo báo cáo tuần 35–36 có file ANRPC so với báo cáo thật

- Ngày chạy: 13/09/2026. Dữ liệu: bản sao prod mới nhất (đã có tỷ giá 03–11/09), code bản 0.4.68.
- Thao tác giống chuyên viên:
  1. Gộp 2 tuần, ghi lý do nghỉ lễ.
  2. Tải `ANRPC Biweekly Report August issue 1 2026.pdf`.
  3. Bấm "AI tóm tắt số liệu chính", rồi "AI hỗ trợ toàn bộ".
  4. Không sửa tay chữ nào.
- Thời gian: AI tóm tắt 8,5 giây, AI viết toàn bộ 21,6 giây. "Soát số liệu": 0 chỗ lệch.
- Kết quả: `Bao-cao-tuan-35-36-2026-ANRPC-test.pdf` (7 trang).

## 1. Số liệu

| Nội dung | Báo cáo thật | Hệ thống | Đánh giá |
|---|---|---|---|
| Bảng 3.1: SGX, MRE (5 dòng × 2 tuần) | vd TSR20 2.374,0 / 2.356,0 | Giống hệt | Khớp |
| Bảng 3.1: OSE, SHANGHAI tuần 36 | 2.737,3 · 2.801,4 | 2.741,0 · 2.797,5 | Lệch nhỏ. Hệ thống đúng hơn: nay đã có tỷ giá 3–4/9 nên tính đủ 5 phiên; bản thật thiếu tỷ giá |
| Ghi chú dưới bảng | "OSE và SHANGHAI không có giá ngày 3/9 và 4/9" | Chỉ còn MRE 25/8, 31/8 | Hệ thống đúng: OSE/SHANGHAI có giao dịch 3–4/9 |
| Cao/thấp USD và ngày (7 chủng loại) | vd OSE 2.784,5 (27/08) · 2.719,6 (02/09) | Giống hệt | Khớp |
| Giá nội tệ kèm cao/thấp | SGX 229,5 US cent/kg, SHANGHAI 18.150 CNY | 278,0 US cent/kg, 18.960 CNY | Bản thật tính sai (2.780 USD/tấn = 278 US cent/kg) |
| Giá giao ngay 3.2 | Có số, ghi "tham khảo theo ANRPC" | Trống, ghi "chưa có giá giao ngay cả tuần" | Thiếu: prod không có giá Reuters từ 21/08 |
| ANRPC: thâm hụt, sản lượng, tiêu thụ | 77.000 tấn · 15,279 triệu tấn (+2,1%) · 15,356 triệu tấn (+0,4%) | Giống hệt | Khớp |
| ANRPC: sản lượng tháng 7, Thái Lan, Trung Quốc | −5,2% · 31,9% · 45,8% | Giống hệt | Khớp |
| ANRPC: khối ANRPC +0,9%, ngoài ANRPC +6,5%, Côte d'Ivoire +8% | Có | Không có | Thiếu chi tiết |
| USD/JPY | Chỉ nêu định tính "JPY yếu", "JPY phục hồi" | +0,25% (T35), −0,78% (T36) | Khớp chiều, có thêm số |
| DXY, WTI, Brent | Nêu định tính | Có số trung bình tuần và % | Hệ thống chi tiết hơn |

## 2. Phần viết

| Phần | Báo cáo thật | Hệ thống | Mức sát |
|---|---|---|---|
| I. Tóm tắt tuần 34 | Tăng mạnh, OSE tăng mạnh nhất 5 tháng; El Niño, mưa Thái Lan, Butadiene, lốp xe +8,1% | Phục hồi đồng loạt nhờ kỳ vọng thiếu cung Đông Nam Á, dầu cao | Khá sát ý chính. Thiếu các chi tiết đặc trưng (5 tháng, lốp xe +8,1%) |
| II. Diễn biến 35–36 | T35 tăng nhẹ (mưa, Butadiene). T36 mở tăng rồi đảo chiều: OSE thấp nhất 2 tuần do JPY phục hồi và dầu yếu; SHANGHAI giữ tăng | Cùng mạch: T35 tăng rồi giằng co; T36 đầu tuần tăng, sau đó chốt lời, yên mạnh lên, dầu quay đầu | Sát. Chưa nêu "OSE thấp nhất 2 tuần" và SHANGHAI đi ngược chiều |
| III.1 Nhận định từng sàn | 3 cấp: % từng tuần + nguyên nhân + cao/thấp | Cùng khung 3 cấp, số tự điền đúng, nguyên nhân hợp lý | Sát định dạng. Nguyên nhân hơi chung chung |
| III.2 Giao ngay | Cao/thấp từng chủng loại theo ANRPC | AI chèn 2 ý về Trung Quốc 45,8%, Thái Lan 31,9%, không liên quan giao ngay | **Lỗi, cần sửa** |
| IV.1 Năng lượng & Butadiene | Butadiene Trung Quốc tăng mạnh, lốp xe chuyển sang cao su tự nhiên | Có số WTI/Brent; không nhắc Butadiene dù file ANRPC có | Thiếu ý chính |
| IV.2 Cung – Cầu | Đoạn mở + gạch sản lượng/tiêu thụ + gạch con | Cùng khung, số ANRPC đúng. Lọt 1 chữ tiếng Anh ("firm") | Sát. Có lỗi dịch nhỏ |
| IV.3 Tỷ giá Nhật Bản | JPY yếu T35 → phục hồi T36, OSE thấp nhất 2 tuần 04/09 | Có % USD/JPY, cùng lập luận, thêm DXY | Sát |
| IV.4 Trung Quốc & khác | PMI hạ nhiệt so đầu năm; lốp xe khả quan; tồn kho Thượng Hải tích lũy nhẹ | PMI tháng 8 tăng lên 52,1; tồn kho SHFE/INE giảm (theo ANRPC) | Khác. AI bám file ANRPC; bản thật lấy nguồn khác |
| V. Dự báo | Giằng co, tích lũy + "Hỗ trợ giá" / "Kìm hãm đà tăng" | Cùng khung, cùng các yếu tố chính. Lọt 1 từ tuyệt đối "hoàn toàn" (hệ thống đã cảnh báo đỏ) | Sát |
| VI. Kết luận | Thận trọng; theo dõi dầu/Butadiene, eo biển Hormuz, tồn kho & lốp xe TQ, BoJ–Fed | Thận trọng; theo dõi dầu/Butadien, tồn kho & ô tô TQ, USD/JPY–DXY, thời tiết | Sát. Thiếu Hormuz (ANRPC có nhắc) |

Ghi chú: tiêu đề phần V của báo cáo thật là "Tuần 36"; hệ thống ghi đúng "Tuần 37".

## 3. Kết luận
- **Số liệu:** sát hoặc đúng hơn báo cáo thật ở mọi chỗ có dữ liệu. Chỗ lệch đều do bản thật thiếu tỷ giá hoặc tính sai giá nội tệ.
- **Khung và văn phong:** bám mẫu 35–36 (gộp tuần, bảng, gạch 3 cấp, Phần IV, V "Hỗ trợ giá / Kìm hãm đà tăng").
- **Ước lượng:** nháp AI tương đương 70–80% nội dung bản thật. Chuyên viên cần bổ sung vài chi tiết đặc trưng trong tuần và sửa các lỗi ở mục 4.

## 4. Lỗi phát hiện, đề xuất sửa
1. **III.2 khi hệ thống không có giá giao ngay:** AI viết lan sang ý không liên quan. Sửa: nếu file đính kèm có bảng giá physical (ANRPC Table 1) thì dẫn đúng số kèm "theo ANRPC"; không có thì để trống.
2. **IV.1 không dùng thông tin Butadiene** có trong file đính kèm hoặc tin tức. Sửa: bắt buộc nêu nếu nguồn có.
3. **Lọt tiếng Anh** ("firm"). Sửa: dặn AI dịch hết thuật ngữ; tự dò chữ Latin thông dụng để cảnh báo.
4. **Từ tuyệt đối vẫn có thể lọt** (đã cảnh báo). Có thể cho AI tự viết lại câu chứa từ đó.
5. **Chi tiết ANRPC phụ bị bỏ** (khối ANRPC/ngoài ANRPC, Côte d'Ivoire). Sửa: nới yêu cầu tóm tắt để giữ các số này.

## 5. Sau khi sửa (bản 0.4.69) — chạy lại cùng dữ liệu, cùng file ANRPC
| Lỗi | Kết quả chạy lại |
|---|---|
| 1. III.2 lạc đề | Đã sửa. Còn đúng 1 dòng dẫn bảng ANRPC: "STR20 FOB Bangkok 238,6 US cent/kg (+1,4%); SMR20 FOB Kuala Lumpur 232,3 (+4,7%); RSS3 FOB Bangkok 279,9 (-4,2%); Latex 60% Kuala Lumpur 172,7 (-4,7%)" |
| 2. IV.1 thiếu Butadiene | Đã sửa. Có đoạn Butadien Trung Quốc tăng mạnh tháng 8, SBR/BR tăng theo |
| 3. Lọt tiếng Anh | Đã sửa. Bắt buộc dịch trong hướng dẫn AI + tự viết lại dòng còn sót → 0 từ |
| 4. Lọt từ tuyệt đối | Đã sửa. Tự viết lại dòng lỗi (chỉ nhận khi số giữ nguyên) → 0 từ |
| 5. Thiếu số ANRPC phụ | Đã sửa. Có khối ANRPC +0,9%, ngoài ANRPC +6,5%, Côte d'Ivoire +8%, Thái Lan 31,9% (+2,1%) |
| Phát sinh khi test: đọc nhầm biểu đồ ANRPC ("năm 2025 dư 31 nghìn tấn", sai) | Đã sửa. Cấm ghép số từ nhãn biểu đồ, cấm tự tính số mới; cán cân chỉ tính cho năm có đủ số trong văn bản |

Soát số liệu: 0 chỗ lệch. PDF: `after-v2/Bao-cao-tuan-35-36-2026-ANRPC-test-sau-sua.pdf`.
