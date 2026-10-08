# Phản biện Dashboard đơn vị — nhánh THU MUA (29/09/2026)

Đo trên bản sao prod `vrg_prod_0929`, gọi thẳng hàm service (chỉ đọc: tắt `ensure_schema`, `year_plan`
không đọc cột `plan_goods_tonnes` vì prod CHƯA có cột này — số KH hàng hóa chưa đo được).
Kỳ: tháng 01/09–29/09/2026 và lũy kế 01/01–29/09/2026. Phạm vi: Toàn Tập đoàn · 4 khu vực
(Đông Nam Bộ, Tây Nguyên, Campuchia, Lào) · Tân Biên · Đồng Nai · Dầu Tiếng · Phước Hòa · Chư sê ·
Eah Leo · Lộc Ninh · Chư prông.

## A. Đã KHỚP (không cần sửa)

| Chỉ số | Dashboard | Thống kê thu mua | Chỉ số đơn vị | Báo cáo theo kỳ |
|---|---|---|---|---|
| Mủ NL Tập đoàn, tháng 9 | 5.976,752 t | 5.976,752 | 5.976,752 | 5.976,752 |
| Mủ NL Tập đoàn, lũy kế | 50.963,287 t | 50.963,287 | 50.963,287 | 50.963,287 |
| Giá mủ nước BQ Tập đoàn T9 | 556,785 đ/độ | 556,785 | 556,785 | (không hiện tổng) |
| % KH thu mua lũy kế Tập đoàn | 48,2% (35 đv có KH) | 48,215% | 48,215% | 48,215% |
| Từng khu vực (6) & 8 đơn vị trên | trùng từng số (SL, giá nước/chén, KH, %) | | | |

- Giá BQ mủ nước/chén/dây của MỌI đơn vị: dashboard = Báo cáo theo kỳ (chênh ≤ 0,01).
- Đơn vị nước ngoài: giá nội tệ × tỷ giá (dashboard) trùng giá lớp `vrg_unit` (Báo cáo theo kỳ).
- Hai lớp giá `vrg` / `vrg_unit` cùng đơn vị cùng ngày tháng 9: 198/198 ô trùng nhau.
- Đơn vị nhận sáp nhập gộp đủ số đơn vị cũ ở mọi màn (Chư sê gồm Mang Yang 126,7 t; Lộc Ninh gồm
  Bình Long; Eah Leo gồm Krông Buk).
- Rổ % chỉ tiêu (chỉ đơn vị được giao KH) hiện CHO CÙNG KẾT QUẢ với màn Thống kê vì mọi đơn vị có
  sản lượng đều đã có KH (`scope_done = done` ở mọi phạm vi). Lệch định nghĩa vẫn còn đó — đơn vị
  nào mua mà chưa có KH thì hai màn tách ra.

## B. Phát hiện

### 1. [Sai số] Trợ lý AI báo % KH thu mua theo ĐƠN VỊ sai cho 26/38 đơn vị
- Trợ lý (`get_unit_plan_progress`, group_by=company) vs Dashboard, lũy kế 29/09:
  Phú Thịnh **0%** vs 52,7% · Chư prông **0%** vs 132,0% · Quảng Trị **0%** vs 36,1% · Phú Riềng
  **0%** vs 15,0% · Bà Rịa **0%** vs 63,5% · Lộc Ninh 35,4% vs 40,4% · Eah Leo 46,7% vs 58,5% ·
  Chư sê 144,1% vs 153,2% · Kon Tum 161,9% vs 193,6% · Việt Lào 40,5% vs 53,1%.
  8.587 t bị dồn vào nhóm "Khác" (tổng Tập đoàn vẫn đúng 48,2%).
- Nguyên nhân: `assistant_tools/unit_tools.py:277-281` cộng `usp.purchase_volume_series(..., group_by)`
  — hàm vẽ biểu đồ, `series_of` (`unit_series.py:79-86`) gộp mọi đơn vị ngoài top 8 của TỪNG loại mủ
  vào "Khác", và không cộng đơn vị đã sáp nhập. Lỗi này đã được sửa ở `_unit_purchase` (hàm
  `_purchase_by_company`, dòng 79-86) nhưng `_unit_plan_progress` chưa dùng.
- Sửa: nhánh company dùng `_purchase_by_company(y_from, y_to, m)` thay `purchase_volume_series`.
  Tốt nhất là lấy thẳng `pur.purchase_report(..., group_by)["rows"][*]["qty_material"]` để cùng
  nguồn với dashboard.

### 2. [Lệch định nghĩa] Trợ lý AI gọi "đơn giá bình quân" là trung bình cộng, dashboard là BQ gia quyền
- Tháng 9, Tập đoàn: mủ nước trợ lý **549,9** vs dashboard **556,8** đ/độ TSC; mủ chén **527,8** vs
  **548,3** đ/độ DRC (lệch 3,7%).
- Nguyên nhân: `unit_tools.py:153-158` lấy trung bình các ngày của trung bình cộng giá các đơn vị
  "khai đều" (`unit_series_purchase.purchase_series`, `_stats` = mean không trọng số).
- Sửa: `avg` lấy `pur.purchase_report(...)["totals"]["price_<m>_avg"]`, giữ min/max làm dải.

### 3. [Lệch định nghĩa] KH thu mua của đơn vị nhận sáp nhập khác màn Kế hoạch năm
- Lộc Ninh: dashboard **4.647 / 11.500 t (40,4%)**; màn Kế hoạch năm của đơn vị hiện **8.500 t**
  (11.500 = 8.500 + Bình Long 3.000). Eah Leo 1.600 vs 1.100 (+Krông Buk 500); Chư prông 700 vs 500
  (+Chư păh 200). Tổng Tập đoàn: dashboard **105.700 t** vs dòng Tổng màn Kế hoạch năm **102.000 t**.
- Nguyên nhân: `unit_report_query.year_plan_by_group` (dòng 210-235) cộng KH đơn vị đã sáp nhập
  (đúng luật tử–mẫu cùng rổ), còn `routers/unit_daily.py:343` + `YearPlanPage.tsx:72` chỉ liệt kê
  đơn vị đang hoạt động; dashboard không nói 3.000 t kia từ đâu ra.
- Sửa: `targets_block` trả thêm phần KH của đơn vị đã sáp nhập và `TargetsCard` ghi "gồm KH Bình Long
  3.000 t" (hoặc màn Kế hoạch năm hiện dòng đơn vị đã sáp nhập, chỉ xem).

### 4. [Sai số nhỏ] "Ngày khai không thu mua" đếm trùng ở đơn vị nhận sáp nhập
- Lộc Ninh lũy kế: dashboard ghi "201 ngày có số liệu · **154** ngày khai không thu mua" = 355 ngày
  trong kỳ 272 ngày. Thực tế chỉ **84** ngày khác nhau (70 ngày cả Lộc Ninh và Bình Long cùng khai),
  và 14 ngày bên này khai "không mua" còn bên kia có mua. Eah Leo: 131 + 149 = 280 > 272.
- Nguyên nhân: `unit_report_purchase.py:115-125` cộng `no_purchase_days += 1` theo từng BẢN GHI sau
  khi gộp, không khử trùng (đơn vị, ngày), không bỏ ngày đã có sản lượng (`_days`, dòng 74). Cùng
  hàm này nuôi Thống kê thu mua và Chỉ số đơn vị.
- Sửa: gom `(key, as_of)` vào một set, bỏ các cặp đã có trong `_days`, rồi mới đếm.

### 5. [Khó hiểu-UX] "N ngày có số liệu" ở phạm vi Tập đoàn/khu vực là lượt đơn vị-ngày
- Tập đoàn tháng 9 (29 ngày): "**748** ngày có số liệu · **252** ngày khai không thu mua"; lũy kế
  "4.985 ngày".
- Nguyên nhân: `PurchaseSection.tsx:78-81` in thẳng `totals.days` (đếm cặp đơn vị × ngày).
- Sửa: ở phạm vi group/region, đổi nhãn thành "lượt khai (đơn vị × ngày)" hoặc hiện "số đơn vị có số".

### 6. [Khó hiểu-UX] Thẻ KPI "Giá mủ nước BQ" trống/không đại diện ở nơi chủ yếu mua mủ chén
- Chư sê: 2.144 t, 100% mủ chén (giá BQ 526,4 đ/độ DRC), thẻ KPI hiện **"—"**. Khu vực Campuchia:
  mủ chén 9.808 t, mủ nước 64,7 t (0,65%) → thẻ hiện **455,7**, là giá của riêng Tân Biên–Kampong Thom.
  Lào 96% mủ chén, Tây Nguyên 69% mủ chén. Biểu đồ theo đơn vị ghi "Giá mủ nước BQ: —" cho
  Chư sê, Bảo Lâm, Sa Thầy, Chưmomray và gần hết đơn vị Campuchia/Lào.
- Nguyên nhân: `DashboardKpiRow.tsx:35-38` cố định `price_latex_avg`.
- Sửa: thẻ hiện giá của loại mủ có sản lượng lớn nhất trong phạm vi (kèm tên loại), hoặc hiện cả hai giá nước/chén.

### 7. [Lệch định nghĩa] Giá thành phẩm mua ngoài: dashboard bỏ dòng thiếu giá, báo cáo ngày của đơn vị tính = 0 — và không có cảnh báo
- Phước Hòa tháng 9: thành phẩm 483,84 t, trong đó 241,92 t (20–21/09) để trống đơn giá.
  Dashboard **48,69** triệu đ/t (chỉ tính 241,92 t có giá). Dòng "Lũy kế" ở màn báo cáo ngày của đơn vị
  tính ra khoảng **24,34** triệu đ/t (dòng thiếu giá thành 0 rồi vẫn được tính trọng số). Cả năm: 574,5 t
  thành phẩm không có giá (Hòa Bình 332,6 · Phước Hòa 241,9), dashboard không cảnh báo gì.
- Nguyên nhân: `unit_report_purchase.py:162` loại `finished` khỏi cảnh báo "chưa có đơn giá";
  `web/src/lib/unit-daily-fields.ts:68-69` trả 0 thay vì null khi không dòng nào có giá.
- Sửa: thêm cảnh báo "N dòng thành phẩm chưa có đơn giá" ở `_purchase_warnings`, đồng thời chia cho
  số lượng CÓ GIÁ ở `finished_price_avg` (trả null khi không có dòng nào có giá).

### 8. [Khó hiểu-UX] Dòng Hàng hóa/Thu mua khi CHƯA giao KH: số thật bị giấu xuống dòng phụ
- Tân Biên (1 đơn vị): hàng hóa hiện "— tấn · Chưa giao chỉ tiêu · Cả phạm vi: 5.060 tấn (**gồm đơn
  vị chưa giao KH**)". Đồng Nai 2.349 t, Phước Hòa 2.533 t, Lộc Ninh 630 t cũng hiện kiểu này.
- Nguyên nhân: `TargetsCard.tsx:26` hiện `item.done` (bằng null khi rổ rỗng), dòng 52-56 là câu dành
  cho phạm vi nhiều đơn vị.
- Sửa: khi `plan == null` thì dòng tiêu đề hiện `scope_done`, bỏ câu "gồm đơn vị chưa giao KH" khi
  xem một đơn vị.

### 9. [Khó hiểu-UX, ưu tiên thấp]
- Vạch tiến độ thời gian chia đều theo năm (`unit_dashboard_targets.py:49-53`, 29/09 = 74,5%) trong khi
  thu mua theo mùa vụ: tháng 2–4 chỉ được 4.041 t (8% lũy kế). Gần như mọi đơn vị bị tô vàng "chậm".
- Màn Báo cáo theo kỳ ghi chú cột "Tổng SL thu mua = nước + chén" (`PeriodReportPage.tsx:31`), nhưng
  số thực tế đã cộng cả mủ dây (`unit_period_report.py:118`). Dashboard ghi đúng "nước · chén · dây".
- Mặc định kỳ khác nhau giữa các màn: Dashboard = tháng này, Thống kê thu mua = tuần này, nên hai màn
  mở lên ra hai con số "% KH" khác nhau (dashboard lũy kế 48,2%, Thống kê tuần/tháng 5,65%).
- Hàng hóa ở cấp Tập đoàn (14.122 t lũy kế) có thể lẫn thành phẩm mua của đơn vị khác trong Tập đoàn
  (tiêu thụ nội bộ lũy kế 4.260 t). Dòng thành phẩm không có trường nhà cung cấp nên chưa kiểm được,
  cần hỏi Ban TTKD.

## C. Số liệu bất thường (không phải lỗi công thức, nên hỏi lại KH đã nhập)
% KH thu mua lũy kế: Krông Buk–Ratanakiri 529,7% (KH 100 t) · Điện Biên 308,4% (KH 150 t) · Kon Tum
193,6% · Chư sê 153,2% (có 126,7 t Mang Yang mua trước sáp nhập, Mang Yang không có KH) · Bà Rịa–
Kampong Thom 152,3%. Vì vậy khu vực Tây Nguyên 121,4%, Miền núi phía Bắc 153,2%.

## Script đo (scratchpad, không commit)
`thumua_boot.py` (tắt ghi) · `thumua_m1.py` (dashboard) · `thumua_m2.py` (Thống kê/Báo cáo kỳ/Chỉ số)
· `thumua_m3.py` (so giá từng đơn vị) · `thumua_m5.py`/`m6.py` (trợ lý AI) · `thumua_q1/q2.sql`.
