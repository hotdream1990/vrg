# Mục 4 — Tồn kho khi ngày được chọn KHÔNG có số (các báo cáo phía Tập đoàn)

> Rà ngày 24/09/2026. Chỉ đọc code và DB dev (bản sao prod). Số tồn kho trong DB dev dừng ở **sáng 22/08/2026**,
> nên ví dụ bên dưới dùng ngày 21/08 và 22/08.

## 1. Kết luận

- Chức năng **"lùi về ngày gần nhất có số" VẪN CÒN**, nhưng mỗi màn làm một kiểu. Hiện có **3 luật khác nhau**:
  - **Lùi, không giới hạn số ngày** (chỉ giới hạn bởi đầu kỳ): Báo cáo tổng hợp, Biểu tổng hợp gửi Tập đoàn, dòng Lũy kế ở Báo cáo tồn kho.
  - **Không lùi**: Thống kê tồn kho, Chỉ số đơn vị, Tồn kho Tập đoàn theo tuần, lưới 1 ngày, Trợ lý AI. Đơn vị không khai ngày đó thì bị tính là "chưa có số" và **không cộng** vào tổng. Riêng đơn vị tick "không phát sinh tồn kho" thì được giữ số lần khai trước (tối đa 30 ngày).
  - **Lùi cả khung hình**: biểu đồ Dashboard không vẽ những ngày cuối còn dưới 85% đơn vị, nên cột cuối là ngày đủ số gần nhất.
- Vì 3 luật này mà **cùng một ngày chốt, các màn ra số rất khác nhau**. Ví dụ ngày 22/08: một màn ra 9.479 tấn, màn khác ra 53.681 tấn.
- Luật "lùi tối đa 7 ngày" (`max_age_days`) của màn Thống kê tồn kho **đã gỡ từ 21/08/2026**, nên hiện không còn màn nào có giới hạn 7 ngày.

## 2. Từng màn làm gì khi ngày chọn không có số tồn

| Màn / báo cáo | Ai xem | Khi ngày chọn (hoặc ngày cuối kỳ) đơn vị chưa khai tồn | Lùi tối đa | Có hiện ngày lấy số / cảnh báo không |
|---|---|---|---|---|
| **Báo cáo tổng hợp** `/bao-cao-tong-hop` (màn hình + Excel) | Admin, chuyên viên, lãnh đạo TĐ (quyền "Báo cáo đơn vị") | Lấy **lần khai tồn gần nhất trong kỳ** của từng đơn vị | Tới **ngày đầu kỳ**. Kỳ tuần: ≤ 6 ngày, kỳ tháng: ≤ 30 ngày, kỳ năm: tới 01/01. **Không lùi sang kỳ trước**, nên sáng thứ Hai chọn "Tuần này" thì gần như trống | Có cột "Ngày lấy số tồn". Ô chỉ **tô vàng** khi đơn vị đã có bản ghi mới hơn mà để trống tồn. Đơn vị **không nộp gì** thì **không tô**. Excel có cột ngày nhưng không tô màu |
| **Biểu tổng hợp gửi Tập đoàn** (Excel, nút ở Báo cáo tổng hợp) | Admin, chuyên viên, sau đó gửi lãnh đạo | Như trên, kỳ luôn là 01/01 → ngày chốt | **Không giới hạn** (tới 01/01) | **Không** có cột ngày lấy số, **không** cảnh báo |
| **Báo cáo tồn kho** `/bao-cao-ton-kho`, dòng "Lũy kế" | Admin, chuyên viên, lãnh đạo TĐ (quyền "Báo cáo đơn vị") | Lấy lần khai gần nhất trong khoảng đang xem (mặc định 90 ngày) | ≤ 90 ngày | Có ghi "số mới nhất ngày…", kèm dòng đỏ "N đơn vị số đã cũ hơn 7 ngày (cũ nhất …)". Các số cũ đó **vẫn được cộng** vào tổng |
| Báo cáo tồn kho, tab "Tổng hợp toàn đơn vị" (lưới 1 ngày) | Admin, chuyên viên, lãnh đạo TĐ (quyền "Báo cáo đơn vị") | Chỉ lấy số của đúng ngày đó. Đơn vị chưa nhập hiện dòng trống. Dòng Tổng cộng chỉ cộng đơn vị đã nhập | 0 ngày (đơn vị tick "không phát sinh" cũng để trống) | Không có cảnh báo riêng. Ngày mặc định là **hôm nay** |
| **Thống kê tồn kho** `/thong-ke/ton-kho` (+ Excel) | Admin, chuyên viên, lãnh đạo TĐ (quyền "Báo cáo đơn vị") | Chỉ lấy số khai **đúng ngày chốt**. Không khai thì báo "chưa có số" và **không cộng** | 0 ngày. Đơn vị tick "không phát sinh" được giữ số cũ tối đa **30 ngày** | Có cột "Ngày lấy số" và "Số cũ (ngày)", dải "x/y đơn vị có số · N đơn vị chưa có số" kèm tên. Ngày mặc định là **hôm nay** |
| **Chỉ số đơn vị** `/chi-so-don-vi`, tab Tồn kho | Admin, chuyên viên, lãnh đạo TĐ (quyền "Báo cáo đơn vị") | Giống Thống kê tồn kho. Khi **không đơn vị nào** có số thì hiện gợi ý "Ngày gần nhất có số là …" kèm nút để người xem tự chuyển sang ngày đó | 0 ngày. Gợi ý tìm lùi tối đa 60 ngày | Có dải độ phủ và gợi ý chuyển ngày |
| **Dashboard / Bản tin biến động**, biểu đồ tồn kho theo ngày | Mọi tài khoản Tập đoàn | Mỗi ngày tính theo luật của Thống kê. Những **ngày cuối** có dưới 85% số đơn vị của ngày đủ nhất thì **không vẽ**, nên khung hình lùi về ngày đủ số | Không giới hạn (cắt tới khi gặp ngày đủ số) | Có dòng chú thích "Chưa vẽ 21/08, 22/08 vì đang nhập dở (mới 44, 15 đơn vị)" |
| **Tồn kho Tập đoàn theo tuần** (tự tính, chốt thứ Sáu 19:00; dùng cho Command Center, Gợi ý giá sàn, Trợ lý AI) | Chuyên viên, lãnh đạo | Tính theo luật của Thống kê tại ngày thứ Sáu. Đơn vị chưa khai thì không cộng | 0 ngày (tick "không phát sinh": 30 ngày) | Có ghi chú "Tự tính từ x/y đơn vị — chưa có số: …". Công tắc hiện đang **TẮT** |
| Trợ lý AI, câu hỏi "tồn kho ngày X" | Người có quyền dùng Trợ lý AI | Theo luật của Thống kê. Không đơn vị nào có số thì trả lời không có, không lấy ngày khác | 0 ngày | Có câu "N đơn vị có số liệu ngày này" |
| Bảng xác nhận khi khoá sổ số liệu | Đơn vị, admin khoá hộ | Theo luật của Báo cáo tổng hợp, tính trong kỳ chốt | Tới ngày đầu kỳ chốt | Có ghi "(ngày dd/mm)" |
| Snapshot tuần (mục 5, đang làm) | — | Theo luật của Báo cáo tổng hợp (lùi trong tuần) | ≤ 6 ngày | Có lưu ngày lấy số |

**Đơn vị đã sáp nhập:** mọi màn áp **cùng một luật**. Khi đơn vị nhận đã khai tồn kể từ ngày sáp nhập thì bỏ ảnh chụp cũ của đơn vị bị sáp nhập, để khỏi cộng trùng. Biểu đồ và bảng theo ngày xét luật này cho từng ngày.

## 3. Ví dụ bằng số thật (DB dev)

**Ngày chốt 21/08/2026 (thứ Sáu, cũng là ngày chốt của Tồn kho Tập đoàn theo tuần):**

| Màn | Tồn thành phẩm | Số đơn vị có số |
|---|---:|---|
| Thống kê tồn kho / Chỉ số đơn vị | **47.224 t** | 52/63. Có 11 đơn vị "chưa có số": Bà Rịa, Phước Hòa, Chư Prông, Eah Leo, Dầu Tiếng Việt Lào, Quảng Nam, Sơn La… |
| Tồn kho Tập đoàn tuần (chỉ tính phần "đã nhập kho") | 45.954 t | 52 đơn vị |
| Báo cáo tổng hợp "Tuần này" (17–21/08) | **55.261 t** | 59 đơn vị. 9 đơn vị lấy số của ngày 20/08 hoặc 18/08, **không ô nào tô vàng** |
| Biểu tổng hợp gửi Tập đoàn (01/01–21/08) | 55.288 t | 61 đơn vị, không có cột ngày lấy số |
| Báo cáo tồn kho, dòng Lũy kế (90 ngày) | 55.288 t | 62 đơn vị, "2 đơn vị số đã cũ hơn 7 ngày (cũ nhất 28/07)" |
| Dashboard | cột cuối là **20/08: 65.901 t** | Không vẽ 21/08 vì mới có 44 đơn vị |

- Phần chênh khoảng **8.000 tấn** giữa Thống kê và Báo cáo tổng hợp là tồn kho của 9 đơn vị chưa khai ngày 21/08. Ví dụ: Phước Hòa 3.118 t, Eah Leo 1.561 t, Bà Rịa 1.423 t, Chư Prông 1.285 t (số ngày 20/08).
- Đơn vị Dầu Tiếng Lai Châu (27,5 t, tick "không phát sinh" từ 28/07) được tính ở Thống kê và ở Biểu gửi Tập đoàn, nhưng **để trống** ở Báo cáo tổng hợp kỳ tuần.
- Riêng khoảng 10.700 tấn chênh giữa 20/08 và 21/08 là do sáp nhập, không phải do luật ngày. Lộc Ninh khai 2.365 t kể từ ngày nhận Bình Long, chưa gộp kho của Bình Long. Lỗi này đã có luật "chưa gộp tồn kho sau sáp nhập" ở màn Cảnh báo bất thường.

**Ngày chốt 22/08/2026 (thứ Bảy, đơn vị đang nhập dở, mới có 22 bản ghi):**

- Thống kê tồn kho: **9.479 t**, 20 đơn vị có số, 43 đơn vị "chưa có số".
- Báo cáo tổng hợp tuần 17–22/08: **53.681 t**, 59 đơn vị. 40 đơn vị lấy số của 21/08, 20/08 hoặc 18/08, và **0 ô tô vàng**.
- Dashboard: không vẽ 21/08 và 22/08, cột cuối vẫn là 20/08.

## 4. Điểm không nhất quán, rủi ro và đề xuất

**Điểm không nhất quán / rủi ro**

1. **Hai luật ngược nhau**: "lùi không giới hạn trong kỳ" và "không lùi". Cùng một ngày chốt mà các màn lệch nhau 8.000 t (ngày 21/08) đến 44.000 t (ngày 22/08). Người xem không biết nên tin màn nào.
2. **Biểu gửi Tập đoàn** lùi tới tận 01/01 và không có cột ngày lấy số. Số cũ bị cộng vào tổng Tập đoàn mà không ai nhìn thấy.
3. **Ô tô vàng ở Báo cáo tổng hợp bỏ sót trường hợp nguy hiểm nhất** là đơn vị ngừng nộp: 9 đơn vị (21/08) và 40 đơn vị (22/08) lấy số ngày cũ mà không ô nào vàng. Ngược lại, ô lại tô vàng oan cho đơn vị đã tick "không phát sinh".
4. **Cờ "không phát sinh tồn kho" được xử lý khác nhau**: Thống kê giữ số cũ tối đa 30 ngày, Báo cáo tổng hợp kỳ ngắn để trống, lưới 1 ngày cũng để trống.
5. **Ngày mặc định rơi vào lúc số chưa đủ**: Thống kê và lưới 1 ngày mặc định là hôm nay; Báo cáo tổng hợp và Chỉ số đơn vị mặc định là cuối tuần/tháng. Với hạn nhập 11:00 ngày D+N, "hôm nay" luôn đang nhập dở, nên mở màn buổi sáng sẽ thấy tồn kho tụt mạnh. Sáng thứ Hai, "Tuần này" ở Báo cáo tổng hợp gần như trống.
6. **Tồn kho tuần tự tính** chạy lúc 19:00 thứ Sáu theo luật không lùi, nên đơn vị nộp muộn bị thiếu cho tới lần chạy tuần sau. Trong khi đó Biểu gửi Tập đoàn ghi "chốt thứ 5".

**Đề xuất 1 luật thống nhất — anh chọn OK / không OK**

> **Tồn kho của một đơn vị tại ngày chốt X = lần khai tồn gần nhất tính đến ngày X, lùi tối đa 7 ngày.**
> - Khai đúng ngày X: dùng số đó, không tô màu.
> - Không khai ngày X nhưng có số trong 7 ngày trước: dùng số đó, **hiện "Ngày lấy số" và tô vàng**. Biểu gửi Tập đoàn cũng thêm cột này.
> - Tick "không phát sinh tồn kho": coi như đã khai lại số cũ, không tô vàng, giữ tối đa 30 ngày như hiện nay.
> - Số cũ hơn 7 ngày hoặc chưa từng khai: là **"chưa có số"**, không cộng vào tổng, nêu tên đơn vị ở đầu báo cáo.
> - Đơn vị đã sáp nhập: giữ nguyên luật hiện hành.
> - Ngày chốt mặc định = **ngày gần nhất đã hết hạn nhập** (11:00 ngày D+N), thay cho "hôm nay".
> - Áp cho **mọi** màn ở bảng mục 2, kể cả Snapshot tuần (mục 5). Dashboard vẫn giữ việc không vẽ những ngày đang nhập dở.
>
> Áp vào ví dụ ngày 21/08: mọi màn cùng ra khoảng **55.290 t, 61 đơn vị**, trong đó 9 đơn vị tô vàng lấy số của 20/08 hoặc 18/08.
> Nếu **không OK**, phương án còn lại là áp luật "không lùi" cho mọi màn. Khi đó Báo cáo tổng hợp và Biểu gửi Tập đoàn ngày 21/08 sẽ chỉ còn 47.224 t và để trống 11 đơn vị.

---

## Phụ lục kỹ thuật (cho lập trình viên)

| Nơi | File:dòng | Ghi chú |
|---|---|---|
| Luật "có nhập tồn" dùng chung | `apps/api/app/services/unit_report_rows.py:201-208` `has_stock` | khối 1/2 có dòng hoặc `stock_material` khác None |
| Luật không lùi + mang số theo `no_stock` | `unit_report_rows.py:214` `CARRY_LOOKBACK_DAYS = 30`; `:217-301` `stock_rows` | chốt 21/08/2026, commit `6d4be25` (gỡ `max_age_days` 7 ngày) |
| Thống kê tồn kho | `services/unit_report_stock.py:166-225`; sáp nhập `:73-104`; độ phủ `:116-144`; cảnh báo `:153-163` | API `routers/unit_analytics.py:173-200` chỉ còn `days_back` (dùng khi nhóm theo ngày) |
| Báo cáo tổng hợp | `services/unit_period_report.py:59-80` `_latest_stock` (lùi tới đầu kỳ, không xét `no_stock`), `:173`, `:219` `stock_as_of` | Excel `services/unit_period_excel.py:63` |
| Biểu gửi Tập đoàn | `services/unit_consolidated_excel.py:88-91` (kỳ 01/01 → ngày chốt); cột `unit_consolidated_layout.py:72-77` | không có cột ngày lấy số |
| Lũy kế Báo cáo tồn kho | `services/unit_daily_timeline_totals.py:27` `STALE_DAYS = 7`; `:42-93` | gọi từ `routers/unit_daily.py:56-83` |
| Lưới 1 ngày | `routers/unit_daily.py:115-141`; web `pages/UnitDailyOverview.tsx:17-20, 43-47`; ngày mặc định `pages/UnitDailyPage.tsx:63` | |
| Dashboard | `services/unit_series_stock.py:40` `MIN_COVERAGE_RATIO = 0.85`, `:55-67` `_trim_pending`, `:129`; web `sections/InventoryBalanceSection.tsx:76-79` | |
| Chỉ số đơn vị | `services/unit_scorecard.py:48` `_STOCK_HINT_DAYS = 60`, `:51-66`, `:187-188`; web `pages/scorecard/UnitScorecardPage.tsx:33-36, 116-122` | ngày mặc định = cuối "Tháng này" |
| Tồn kho tuần tự tính | `services/inventory_auto.py:42` (thứ Sáu), `:47` `MAX_AGE_DAYS = 7` (chỉ là cửa sổ tính lại), `:117-138` `compute`; lịch `services/scheduler.py:63-70` (19:00 thứ Sáu) | `INVENTORY_AUTO = off` trên DB dev |
| Trợ lý AI | `services/assistant_tools/unit_tools.py:226-252` | |
| Khoá sổ | `services/data_lock_summary.py:43-55` | |
| Snapshot tuần (mục 5) | `services/unit_week_snapshot.py:12-13` (file mới) | theo luật của Báo cáo tổng hợp |
| Sáp nhập | `services/member_unit_merge.py:104-118` `superseded_in` / `stock_superseded` | |
| Web Báo cáo tổng hợp | `apps/web/src/features/command-center/pages/PeriodReportPage.tsx:69-86` | tô vàng khi `stock_as_of < last_day` (so với bản ghi cuối của đơn vị, **không** so với ngày cuối kỳ) |
| Web Thống kê tồn kho | `pages/analytics/StockStatsPage.tsx:26-27`; `StockFilters.tsx:24-25` (ngày mặc định hôm nay); `StockCoverageBar.tsx:26-44` | |

**Chưa kiểm sâu (rủi ro phụ):** hàm `anomaly_rules.py:207-223` `_latest_stock` của luật "chưa gộp tồn kho sau sáp nhập" lấy bản ghi gần mốc nhất **mà không lọc `has_stock`**. Nếu bản ghi đó chỉ có cờ `no_stock` thì tồn = 0, có thể báo oan là "hụt 100%".

Cách đo: gọi thẳng các hàm service ở chế độ chỉ đọc (`default_transaction_read_only = on`, bỏ `ensure_schema`) trên `vrg_caosu`. Tổng "Tồn thành phẩm" = khối 1 + khối 2.
