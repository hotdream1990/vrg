# Phản biện Dashboard đơn vị — nhánh TIÊU THỤ · DOANH THU · TIẾN ĐỘ BÁN HÀNG (29/09/2026)

Đo trên bản sao prod `vrg_prod_0929`, chỉ đọc (bỏ qua `ensure_schema`, không ghi DB). Kỳ: lũy kế 01/01–29/09 và tháng 09.
⚠ Bản sao prod CHƯA có cột `plan_goods_tonnes` (commit 4db4a41 chưa deploy) → đo với KH hàng hóa = trống, đúng như prod hôm nay.

## A. Đã KHỚP (không cần sửa)

| Cặp so | Kết quả |
|---|---|
| Tiêu thụ tổng / chuyến / dài hạn / XK / doanh thu: Dashboard ↔ Báo cáo tổng hợp, 8 đơn vị (Tân Biên, Tây Ninh, Dầu Tiếng, Đồng Nai, Chư sê, Eah Leo, Lộc Ninh, Chư prông) + 2 khu vực (ĐNB, Tây Nguyên), tháng 09 và lũy kế | 0 chênh |
| "Đã giao lũy kế" (thẻ Tiến độ) = cột P biểu Tập đoàn, 8 đơn vị trên | khớp (vd Tân Biên 7.727,988 t) |
| "Tiêu thụ HĐ chuyến" (Chỉ tiêu năm) = cột M, 8 đơn vị | khớp (Tân Biên 3.046,815) |
| % KH chuyến / % KH doanh thu mức đơn vị ↔ Báo cáo tổng hợp | khớp (TB 75,7/78,6 · TN 57,6/67,1 · ĐN 153,5/100,3 · DT 96,6 · CS 80,6 · EL 62,2 · LN 122,3 · CP 64,2) |
| Doanh thu đơn vị tỷ đồng: Dashboard = Báo cáo kỳ = Excel = Trợ lý | 21.919,602 tỷ lũy kế cả Tập đoàn |
| Sáp nhập: bảng khu vực cộng lại = tổng (407.910,2 t · phải giao 125.469,7 t · DT dự kiến 28.672,2 tỷ); Chư sê / Eah Leo / Lộc Ninh / Chư prông = dòng gộp ở Báo cáo tổng hợp | không trùng, không hụt |
| HĐ chuyến đã ký chưa giao = cột R (đơn vị không có HĐDH): Chư prông 2.151,95 · Chư sê 943,4 · Tây Ninh 1.492,535 | khớp |
| Quy khô ở tiêu thụ (latex/mủ NL/mủ dây lấy ô quy khô); 8 dòng latex cũ thiếu quy khô đều đã giao hết, không vào "phải giao" | đúng |
| Thiếu tỷ giá / đơn giá vượt trần năm 2026 | 0 dòng → hôm nay không lệch số |

## B. Sai số

**S1. Tập đoàn / khu vực Campuchia cộng TRÙNG bán nội bộ mẹ–con.**
Dashboard Tập đoàn "Tiêu thụ" & "Đã giao lũy kế" = 407.910,2 t; biểu Tập đoàn cột P = 403.649,9 t (−4.260,3 t). 4.260,3 t / 202,6 tỷ là HĐ chuyến kênh `internal` của DNKC (1.568 t → CS Đồng Nai-Kratie), DT–Campuchia (1.396,6 t → CPCS DT Campuchia), DT–Kratie (1.295,7 t → CPCS DT Kratie); ba bên mua là đơn vị thành viên và đã bán lại 1.582 / 2.187 / 2.293 t → đếm hai lần ở mức Tập đoàn. Cũng làm "Tiêu thụ HĐ chuyến cả phạm vi" 271.732,4 ≠ cột M 267.472,1.
Nguyên nhân: `unit_report_consumption.py:43-49` cộng mọi kênh vào `qty`; `unit_dashboard_outlook_calc.py:25` lấy thẳng. Biểu Excel `unit_consolidated_layout.py:85-86` P = SUM(H:K), không có kênh nội bộ.
Đề xuất: ở phạm vi Tập đoàn/khu vực, trừ kênh `internal` khỏi tổng (hoặc hiện "trong đó nội bộ" và trừ) — chốt với Ban TTKD cho cả hai màn một luật.

**S2. Thống kê tiêu thụ: cột "KH doanh thu" + "% thực hiện KH doanh thu" LUÔN TRỐNG.**
`ConsumptionStatsPage.tsx:38-40` khai cột, nhưng API `unit_report_consumption.py:118-121` (`_attach_plan`) chỉ gắn KH chuyến. Đề xuất: `_attach_plan` thêm `plan_revenue_ty` + `pct_plan_revenue` theo cùng luật rổ.

**S3. Trợ lý AI báo % doanh thu 213,2% — Dashboard 80,6%.**
`assistant_tools/unit_tools.py:310`: doanh thu CẢ Tập đoàn (21.919,6) ÷ KH của 27 đơn vị (10.279,6). Dashboard dùng rổ 27 đơn vị: 8.289,7 / 10.279,6. Đề xuất: trợ lý gọi `unit_dashboard_targets.targets_block` thay vì tự chia.

**S4. HĐDH latex không khai quy khô → trộn tấn nước với tấn khô.**
Đồng Nai 02/DH-CSĐN, 06/DH-CSĐN, 09/26/LT-DONA: cam kết 1.702,5 t NƯỚC; đã giao tính 1.025 t nước (khô thật 616,8) → "HĐDH đã giao" đội +408,2 t; còn lại 677,5 t nước vào "Tổng phải giao" và DT dự kiến. (Bình Long 05/BL/LTC-26 có dòng LATEX trống.)
Nguyên nhân: `contract_backlog.py:90` về gốc nước khi cam kết không có khô (dữ liệu nhập trước khi `master_contract_clean.py:88` bắt buộc quy khô).
Đề xuất: nhờ Đồng Nai lưu lại 3 HĐ mẹ có quy khô; thêm cảnh báo ở thẻ khi `_master_totals` phải về gốc nước.

## C. Lệch định nghĩa

**L1. "Tổng phải giao đến cuối năm" gồm cả HĐDH còn hiệu lực SAU 31/12.**
Tập đoàn: 29.623,8 t trong 125.469,7 t (23,6%) và 1.597,7 tỷ trong 6.752,6 tỷ "DT dự kiến phần còn lại"; Dầu Tiếng 4.219,8 / 8.840,1 t. Nhãn nói "đến cuối năm", "Bán cả năm (dự kiến)" cũng cộng phần này.
Nguyên nhân: `contract_backlog.py:127-130` (`to_deliver` gồm `master_remaining` trọn), `unit_dashboard_outlook_calc.py:39,55`. Cùng nhãn ở `ConsumptionKpiRow.tsx:19`.
Đề xuất: `projected`/`rest` dùng `to_deliver − master_remaining_after_year`, phần sau năm để dòng ghi chú.

**L2. % KH HĐ chuyến: Dashboard ≠ Thống kê tiêu thụ / Chỉ số đơn vị ở mức nhóm.**
Tập đoàn 70,1% (rổ) vs 74,5%; ĐNB 95,8% vs 108,6% (Phước Hòa bán 15.657 t chuyến, không có KH); Tây Nguyên 73,7% vs 74,3%. Mức đơn vị khớp.
Nguyên nhân: `unit_report_consumption.py:163-164` = Σ chuyến mọi đơn vị ÷ Σ KH; Dashboard `unit_dashboard_targets.py:56-64` = rổ đơn vị có KH.
Đề xuất: tổng/khu vực ở `consumption_report` tính % theo rổ (tử = đơn vị có KH) như Dashboard.

**L3. KH bán hàng = KT + TM + HH — rổ quá mỏng, lệch hẳn với KH mà đơn vị đã nhập.**
Chỉ 5 đơn vị có KH khai thác (30 đơn vị thiếu) → Tập đoàn 118,5% là số của 5 đơn vị. Trong khi 61 đơn vị đã nhập KH chuyến + KH ký HĐDH (cột G), và tổng này = KT+TM ở Tây Ninh (10.043), Đồng Nai (41.000,2 ≈ 41.000); Tân Biên 4.026,56 + 5.473,44 = 9.500 = 4.500 + 5.000 hàng hóa (thực mua 5.060 t thành phẩm). Hôm nay prod vẫn ra Tân Biên 226,5% (chưa có cột KH hàng hóa); theo KH chuyến + HĐDH là 10.191 / 9.500 = 107,3%.
Đề xuất: KH bán hàng lấy `plan_sales_spot_tonnes + signed_lt_tonnes` khi đơn vị chưa nhập KH khai thác (hoặc hiện cả hai và cảnh báo khi lệch > 5%).

**L4. Hai con số "HĐ dài hạn đã giao" trên cùng màn.**
Thẻ KPI "Dài hạn" (lũy kế năm, mọi HĐ loại dài hạn) vs khối HĐDH (trọn đời HĐ, chỉ HĐDH CÓ cam kết): Tân Biên 4.681,2 vs 3.838,8; Lộc Ninh 6.399 vs 141,1 / cam kết 403,2; Tập đoàn 136.178 vs 74.327. Có 13 HĐDH không nhập cam kết (đã giao 9.823 t năm 2026) bị loại (`contract_backlog_sql.py:52`); 13 phụ lục loại "chuyến" dưới HĐDH (481 t) nằm ở "chuyến" trong KPI nhưng ở HĐDH trong thẻ. Cột G biểu Tập đoàn 175.734 t ≠ cam kết HĐ mẹ 164.960 t (19 đơn vị lệch; Lộc Ninh 10.523,6 vs 403,2; Phước Hòa 0 vs 8.856,5).
Đề xuất: khối HĐDH hiện thêm "HĐ dài hạn giao năm nay: X t, trong đó Y t ngoài HĐDH có cam kết".

**L5. Xử lý doanh thu thiếu / sai khác nhau giữa các màn** (hôm nay 0 dòng nên chưa ra số lệch):
Dashboard cộng phần tính được + đếm dòng thiếu + trần 200 tr/t; Báo cáo tổng hợp/Excel để "—" cả đơn vị (`sales_contract_report.py:151-167`) và không soát trần; Trợ lý dùng trần 5.000 tỷ/ngày cả Tập đoàn (`unit_tools.py:33`). Đề xuất: một hàm `is_bad_price` + một luật "thiếu" cho cả 3 nơi.

**L6. HĐ chuyển từ 2025 (carry_\*)**: Dashboard không dùng carry; 435 HĐ ký 2025 đã nằm trong "Đã giao lũy kế"/"phải giao" nhất quán với cột P. Nhưng số nhập tay AE/AF (chuyến 34.888 · DH 14.439 t) ≠ hệ thống tại 31/12/2025 (chuyến 48.819 · DH-phụ lục 4.844 t); Chư prông khớp tuyệt đối, Chư sê 0 vs 2.757,7, Lộc Ninh 7.703,8 vs 4.242. Chỉ thông tin.

## D. Khó hiểu — UX

- **U1.** Cùng trang Tân Biên thấy 3 "kế hoạch": KH chuyến 4.026,56 (75,7%), KH bán hàng 4.500 (226%), cột G + KH chuyến 9.500 (không hiện). Gốc của phản ánh "không hiểu".
- **U2.** Nhãn cũ chưa theo hàng hóa: cột "KH (KT + TM)" `OutlookBreakdownTable.tsx:55`, câu "KH khai thác + KH thu mua" `unit_dashboard_outlook_calc.py:87`.
- **U3.** Lộc Ninh 122,3% HĐ chuyến là do dữ liệu Bình Long: KH chuyến 1.169,9 / KH HĐDH 10.201 nhưng khai giao 8.427 t "chuyến" và 6.258 t "dài hạn" (xem tách Bình Long ra 720,4%). Cần Lộc Ninh rà loại HĐ của Bình Long.

## Script đo
`/private/tmp/claude-502/…/scratchpad/m1.py … m11.py` (boot.py vá `year_plan` bỏ cột chưa có, `_schema_ready=True`).
