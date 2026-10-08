# Phản biện Dashboard đơn vị — nhánh TỒN KHO + khung chung (29/09/2026)

Đo trên bản sao prod `vrg_prod_0929` (hôm nay = 29/09/2026), gọi thẳng hàm service (không qua HTTP, không ghi DB).
Phạm vi đo: Toàn Tập đoàn · Đông Nam Bộ · Tây Nguyên · Tân Biên · Dầu Tiếng · Đồng Nai · Chư sê · Eah Leo · Lộc Ninh; ngày chốt 28/09 và 29/09.

## 0. Tóm tắt

| # | Mức | Vấn đề | Số thật |
|---|---|---|---|
| 1 | **Sai số (hiển thị)** | Ngày chốt mặc định = HÔM NAY (đang nhập dở) | KPI Tập đoàn 29/09 = **6.113 t** (11/63 đv) so với 28/09 = **52.271 t** |
| 2 | **Lệch định nghĩa (cùng màn)** | "Tồn có thể giao dịch" có 3 công thức | 27/09 Tập đoàn: KPI **15.214 t** · biểu đồ "Tồn tự do" **31.666 t** · "Tự do theo chủng loại" **32.990 t** |
| 3 | **Lệch định nghĩa** | 5 luật "ngày thiếu số" cho ra 5 con số tồn Tập đoàn | 52.271 / 52.098 / 59.973 / 60.145 / 56.667 / 61.019 t |
| 4 | **Sai số** | "Đã ký HĐ chưa giao" bỏ sót HĐ của đơn vị cũ đã sáp nhập | Lộc Ninh **1.295,7** so với Báo cáo tổng hợp/Excel **1.492,7** (thiếu 196,9 t của Bình Long) |
| 5 | **Sai (hiển thị)** | "Ngày lấy số" là ngày ảnh chụp, không phải ngày khai → số mang sang từ ngày cũ bị giấu | DT Lai Châu: số khai 30/08 hiện là "28/09" (Số cũ 29 ngày) |
| 6 | **Khó hiểu** | Đã khai 0 vẫn hiện "—" (trang ghi "— = chưa có số") | 10/50 đơn vị có số ngày 28/09 hiện "—" |
| 7 | **Khó hiểu** | Cùng một ngày lúc vẽ lúc ẩn tùy kỳ chọn; mỗi chỗ đếm độ phủ một kiểu | 28/09: vẽ khi chọn "Tuần này", ẩn khi chọn "Tháng này"; "40 đơn vị" so với "50/62 có số" |
| 8 | **Khó hiểu (khung chung)** | Xem MỘT đơn vị vẫn ghi "Cả phạm vi … (gồm đơn vị chưa giao KH)" | 44 dòng / 39 trên 63 đơn vị |
| 9 | Lệch định nghĩa (nhẹ) | Chú thích mâu thuẫn · đơn vị tính · luật sáp nhập của trang cảnh báo | xem mục 9 |

---

## 1. Ngày chốt mặc định = hôm nay → KPI tồn kho sai lệch cả buổi sáng — **Sai số (hiển thị)**

- Mặc định "Tháng này" → `as_of = min(30/09, hôm nay) = 29/09`. Đơn vị được nhập tới 11:00 ngày D+1, nên hôm nay hầu như chưa ai khai.
- Số thật ngày 29/09:
  - **Toàn Tập đoàn**: Tồn thành phẩm **6.113,2 t**, Có thể giao dịch 3.243,2 t, 11/63 đơn vị. Hôm trước (28/09) là **52.270,6 t** (50/63 đơn vị).
  - **Đông Nam Bộ**: KPI "—" và **không có nút gợi ý ngày**. Lý do: Hàng Gòn khai toàn số 0 nên `units_counted = 1`, trong khi gợi ý chỉ hiện khi `units_counted == 0`.
  - **Cả 6 đơn vị** đều ra "—", kèm câu gợi ý "Ngày gần nhất có số là 28/09".
- Trên cùng trang, biểu đồ diễn biến lại tự bỏ các ngày nhập dở (dừng ở 27/09 = 56.667 t). Nghĩa là thẻ KPI và biểu đồ cạnh nhau lệch **9 lần**.
- Nguyên nhân:
  - `apps/api/app/routers/unit_scorecard.py:36-37` (`stock_day` lấy min với hôm nay).
  - `apps/api/app/services/unit_dashboard.py:139` không áp `trim_pending`.
  - `unit_dashboard.py:142-143`: gợi ý chỉ khi 0 đơn vị.
- Đề xuất: khi để trống ngày chốt thì lấy **ngày cuối còn lại sau `trim_pending`** (Tập đoàn/khu vực) hoặc **ngày khai gần nhất** (đơn vị); đồng thời hiện "x/y đơn vị có số" ngay trên thẻ KPI.

## 2. "Tồn có thể giao dịch" — 3 công thức trên cùng một màn — **Lệch định nghĩa**

| Nơi hiển thị | Công thức | Tập đoàn 27/09 | Dầu Tiếng 27/09 |
|---|---|---|---|
| KPI + ô "Có thể giao dịch" (dashboard, Thống kê tồn kho) | tồn − đã ký, **không cắt trần, được âm** (`unit_report_stock.py:63-66`) | **15.214,5** (đã ký 41.452,3) | **−931,3** (đã ký 3.688,6) |
| Biểu đồ "Cơ cấu hợp đồng" (dashboard + Dashboard Tập đoàn) | cắt trần **theo đơn vị** (`unit_series_stock.py:166-169`) | 31.666,0 (đã ký 25.000,8) | 0 (đã ký 2.757,3) |
| Biểu đồ "Tự do theo chủng loại" | cắt trần **theo chủng loại** (`unit_series_stock.py:73-80`) | 32.990,3 | — |
| Giá sàn + Trợ lý AI (`inventory_daily.py:63-70`) | cắt trần theo đơn vị | `ton_free` 31.666 | — |
| Excel gửi Tập đoàn, cột S…AB (`unit_consolidated_layout.py:89-101`) | cắt trần theo chủng loại, HĐ lấy tại ngày chốt | — | — |

- Có 17 đơn vị ra số âm, cộng lại −16.451 t. Đây là lý do KPI chỉ bằng một nửa số trên biểu đồ.
- Đề xuất: chốt MỘT định nghĩa với chủ dự án. Nếu giữ KPI được âm thì đổi nhãn biểu đồ thành "Tồn tự do (cắt trần theo đơn vị)" và nêu tổng phần thiếu hàng.

## 3. Luật "ngày thiếu số" — mỗi màn một luật (chưa màn nào dùng "lùi ≤ 7 ngày")

Số tồn thành phẩm Toàn Tập đoàn:

| Màn | Luật lấy số của đơn vị | Tồn TP (t) | Đã ký (t) | Nguyên liệu (t) |
|---|---|---|---|---|
| Dashboard đơn vị / Thống kê tồn kho / Chỉ số đơn vị / tồn kho tuần tự tính (`inventory_auto`) | Khai đúng ngày; tick "không phát sinh" thì mang số cũ sang, tối đa 30 ngày (`unit_report_rows.py:214`) | **52.270,6** (28/09, 50 đv) | 34.483,4 | 17.835,4 |
| Báo cáo tổng hợp, kỳ "Tuần này" (28/09–04/10; mặc định của màn) | Ngày cuối có tồn trong kỳ (`unit_period_report.py:59-80`) | 52.098,0 (trộn ngày 28 và 29/09) | 43.179,2 | 17.897,0 |
| Báo cáo tổng hợp, kỳ "Tháng này" | Như trên, lùi tới 01/09 | 59.972,6 (các ngày 25→29/09) | 43.179,2 | 24.300,8 |
| **Excel gửi Tập đoàn**, chốt 28/09 | Như trên nhưng kỳ **01/01 → ngày chốt**: lùi tới 9 tháng (`unit_consolidated_excel.py:90-91`) | **60.145,2** (có số từ 02/08, 30/08) | 43.402,7 | 24.239,2 |
| Diễn biến tồn kho (dashboard + Dashboard Tập đoàn + Bản tin biến động) | Khai đúng ngày; bỏ các ngày cuối có độ phủ < 85% | cột cuối 27/09 = **56.666,9** (48 đv) | 25.000,8 (cắt trần) | — |
| Giá sàn + Trợ lý AI (`inventory_daily.at`) | Như trên, rồi lấy "ngày có số gần nhất ≤ ngày hỏi" | 56.667 (27/09) | 25.001 | — |
| Snapshot tuần 38 (21–27/09, chụp 28/09 lúc 11:10) | Ngày cuối có tồn trong tuần (đóng băng) | 61.019,1 | 43.999,2 | 23.946,7 |
| Cảnh báo bất thường, luật sáp nhập (`anomaly_rules.py:214-230`) | Bản ghi gần mốc nhất, **không lọc** "có khai tồn", không giới hạn ngày | — | — | — |

- Phần chênh 60.145,2 − 52.270,6 = **7.874,6 t** khớp tuyệt đối với 11 đơn vị chưa khai ngày 28/09. Lớn nhất là Krông Buk–Ratanakiri 3.978,2 t (số 25/09), Phước Hòa Kampongthom 1.169,9 t, VKETI 675,4 t, Sa Thầy 630,7 t (số 27/09).
- Theo khu vực:
  - Đông Nam Bộ: 26.015,6 (dashboard) so với 26.244,8 (Excel). Chênh chính là Phú Thịnh 229,1 t (số 27/09).
  - Tây Nguyên: 6.211,6 so với 6.842,3. Chênh chính là Sa Thầy 630,7 t.
- Đề xuất: chủ dự án chốt MỘT luật (ví dụ lùi ≤ 7 ngày và luôn hiện ngày lấy số), rồi đưa vào `unit_report_rows.stock_rows` cho tất cả các màn dùng chung.

## 4. "Đã ký HĐ chưa giao" bỏ sót HĐ của đơn vị đã sáp nhập — **Sai số**

- Lộc Ninh:
  - 28/09: dashboard **1.295,7** so với Báo cáo tổng hợp/Excel R **1.492,7**.
  - 27/09: 1.526,9 so với 1.723,8.
  - Phần thiếu **196,9 t** chính là HĐ còn mở của Bình Long: `contracts_on(28/09, Bình Long) = 196,9`.
- Toàn Tập đoàn 28/09: dashboard 34.483,4 so với Excel R 43.402,7, **lệch 8.919 t**. Lý do: dashboard chỉ lấy HĐ của đơn vị CÓ ảnh chụp tồn ngày đó. Đơn vị cũ đã bị bỏ ảnh chụp, và 12 đơn vị chưa khai, đều mất phần HĐ.
- Nguyên nhân: `unit_report_rows.py:281` và `304-318` (`_undelivered_by_snapshot` chỉ hỏi HĐ cho các bản ghi còn lại trong ảnh chụp).
- Đề xuất: khi hỏi HĐ cho đơn vị nhận, dùng `member_unit_merge.lineage(đơn vị nhận)` rồi cộng về đơn vị nhận.

## 5. "Ngày lấy số" hiển thị sai, số mang sang không bao giờ lộ — **Sai (hiển thị)**

- `_feed` ghi `r["as_of"]`, tức ngày ảnh chụp (`unit_report_stock.py:41`). Trường `source_as_of` (`unit_report_rows.py:286`) được tính nhưng **không nơi nào đọc**.
- Hệ quả:
  - `datesNote` ở `StockSection.tsx:24-30` và dòng "Số lấy ngày …" trong tooltip **không bao giờ hiện**.
  - Dashboard cũng không hiện `age_days`.
- Ví dụ: Dầu Tiếng Lai Châu ngày 28/09 dùng số khai 30/08 (29 ngày). Màn Thống kê tồn kho hiện cùng một dòng "Ngày lấy số 28/09" nhưng "Số cũ 29 ngày".
- Sửa: `g["_dates"].add(r["source_as_of"])`.

## 6. Đã khai 0 vẫn hiện "—" — **Khó hiểu**

- `_close` đổi 0 thành None (`unit_report_stock.py:62,67-68`). Trong khi đó trang ghi "Ô '—' là chưa có số, không phải bằng 0" (`UnitDashboardPage.tsx:78`).
- Ngày 28/09 có 10 đơn vị ĐÃ khai mà tồn thành phẩm vẫn hiện "—", ví dụ:
  - Hàng Gòn: khai 0 cho 3 chủng loại.
  - Hà Giang, Bình Phước Kratie 1, Best Royal: chỉ có tồn nguyên liệu.
  - Yên Bái: đã nhập kho 0 nhưng đã ký 839,9 t, nên "có thể giao dịch" −839,9.
- Đề xuất: đơn vị đã có dòng khai thì giữ 0; chỉ để None khi không có dòng nào.

## 7. Cắt đuôi phụ thuộc kỳ chọn; mỗi chỗ đếm độ phủ một kiểu — **Khó hiểu**

- `trim_pending` lấy mốc "ngày phủ tốt nhất" **trong cửa sổ = kỳ đang chọn** (`unit_dashboard.py:170`, `unit_series_stock.py:62`). Hệ quả:

| Phạm vi | Chọn "Tuần này" | Chọn "Tháng này" / "Năm nay" |
|---|---|---|
| Toàn Tập đoàn | vẽ 28/09 = 52.270,6 (40 đv) | ẩn 28/09 ("đang nhập dở"), cột cuối 27/09 = 56.666,9 |
| Tây Nguyên | vẽ 28/09 = 6.211,6 | ẩn 28/09, cột cuối 27/09 = 6.914,2 |

- Cùng ngày 28/09, biểu đồ ghi "mới **40** đơn vị" (chỉ đếm đơn vị có tồn thành phẩm > 0, `unit_series_stock.py:96-98,186`), còn dải độ phủ ghi "**50**/62 đơn vị có số" (đếm mọi bản ghi, `unit_report_stock.py:135-143`).
- Cảnh báo "12 đơn vị chưa có số" gộp cả 3 đơn vị không có nhà máy mà không ghi chú (dải độ phủ ở màn Thống kê thì có ghi chú).
- Đề xuất: tính `best` trên một cửa sổ cố định (ví dụ 30 ngày trước ngày cuối), không theo kỳ đang chọn.

## 8. Khung chung — xem MỘT đơn vị vẫn ghi "Cả phạm vi … (gồm đơn vị chưa giao KH)" — **Khó hiểu**

- Có 44 dòng chỉ tiêu trên 39/63 đơn vị bị hiện câu này:
  - Doanh thu: 35 dòng.
  - Hàng hóa: 7 dòng.
  - Tiêu thụ HĐ chuyến: 2 dòng.
- Ví dụ Dầu Tiếng, dòng Doanh thu:
  - Số chính hiện "**—**".
  - Dòng dưới ghi "Chưa giao chỉ tiêu".
  - Rồi "Cả phạm vi: 1.561,8 tỷ đồng (gồm đơn vị chưa giao KH)".
- Như vậy số thật của chính đơn vị đó lại hiện thành "chưa có số".
- Nguyên nhân: `TargetsCard.tsx:26,52-56` không xét cờ `single`; `unit_dashboard_targets.py:61` trả `done = None` khi chưa có kế hoạch.
- Đề xuất: khi xem MỘT đơn vị thì dùng `scope_done` làm số chính ("Thực hiện: X") và bỏ câu "Cả phạm vi".

## 9. Lệch nhỏ

- Chú thích mâu thuẫn:
  - `unit_period_report.py:187-188` ghi "khối đã ký KHÔNG nằm trong tồn kho".
  - Ngược lại, `unit_report_stock.py:10-11`, nhãn ở `PeriodReportPage.tsx:60` và ghi chú Excel đều ghi "nằm trong".
- Đơn vị tính của "Đã ký HĐ chưa giao": dashboard ghi "tấn", màn Thống kê/Báo cáo ghi "tấn quy khô".
- Cột Excel AD có tiêu đề "Tồn kho nguyên liệu … (đơn vị chưa có nhà máy)" nhưng số lấy của mọi đơn vị (ví dụ Đồng Nai 1.802 t).
- Luật cảnh báo sáp nhập lấy bản ghi gần nhất mà không lọc `has_stock`: Krông Buk ngày 31/07 bị tính 0,0 t. Hiện chưa gây cảnh báo sai.

## Các điểm ĐÃ KHỚP

- Dashboard đơn vị, Thống kê tồn kho và tab Tồn kho của Chỉ số đơn vị gọi cùng `stock_report` → luôn khớp.
- Tồn thành phẩm ngày 28/09 của từng đơn vị khớp giữa Dashboard, Thống kê, Báo cáo tổng hợp và Excel:

| Đơn vị | Tồn TP (t) |
|---|---|
| Tân Biên | 1.933,8 |
| Dầu Tiếng | 2.408,4 |
| Đồng Nai | 9.058,4 |
| Chư sê | 1.759,1 |
| Eah Leo | 2.070,8 |
| Lộc Ninh | 3.252,0 |

  Không có cộng trùng đơn vị sáp nhập.
- "Đã ký chưa giao" khớp cho Tân Biên 1.510,7 · Dầu Tiếng 3.204,8 · Đồng Nai 3.876,3 · Chư sê 943,4 · Eah Leo 417,5.
- Độ phủ ngày 28/09: 50 đơn vị có số + 1 đơn vị "không phát sinh" = 51 đơn vị đã nộp ở màn Theo dõi nộp báo cáo (51 đã nộp / 12 chưa nộp).
- Biểu đồ Tập đoàn trên Dashboard đơn vị trùng với Dashboard Tập đoàn (cùng `stock_series`, cùng cửa sổ khoảng 60 ngày → cùng dừng ở 27/09).
- Cảnh báo "chưa gộp tồn kho sau sáp nhập": 0 cảnh báo. Các cặp đã gộp đủ:
  - Bình Long + Lộc Ninh: 13.060 t → 13.065 t.
  - Chư păh + Chư prông: 1.284,6 t → 1.284,6 t.
  - Krông Buk + Eah Leo: 1.398,7 t → 1.446,7 t.
- Trong ảnh chụp, tổng hai lớp "đã nhập kho" + "chưa nhập kho" đúng bằng tổng tồn thành phẩm.
