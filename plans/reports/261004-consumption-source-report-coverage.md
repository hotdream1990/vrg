# Rà soát: màn/báo cáo nào đã tách tiêu thụ theo NGUỒN (khai thác / thu mua)

Ngày rà: 04/10/2026 · Bản code: `963d419` (0.4.108, gồm commit `4522afd`). Chỉ đọc code + tài liệu,
không sửa code, không ghi DB. Số liệu đo lấy từ **bản sao DB local** (dữ liệu tới 22/08/2026), chỉ đọc.

## 1. Phần lõi đã có sau `4522afd`

- Mỗi lần giao lưu cột `sales_contract.source`. Hàm `sales_contract_report.source_of()` trả về
  `exploit` khi ô trống (`sales_contract_report.py:136-140`).
- `sales_contract_report.consumption()` trả thêm `by_source`, nhưng **chỉ có SẢN LƯỢNG**, chưa có
  doanh thu theo nguồn (`:155,173-174`).
- `unit_report_rows._delivery_rows` gắn nguồn vào từng dòng bán (`:189`).
- `unit_report_consumption` có `qty_exploit` · `qty_purchase`, lọc được theo `source` (`:28,45,55-56`).
  `GROUPERS["source"]` nằm ở `unit_report_query.py:63`.
- Hệ quả: mọi màn gọi `consumption_report()` **đã nhận sẵn** `qty_exploit`/`qty_purchase`, chỉ là
  chưa hiển thị.

## 2. Bảng kiểm kê

| # | Màn/báo cáo | Route web | File backend chính | Đã tách nguồn? | Nên tách? | Ưu tiên | Ghi chú |
|---|---|---|---|---|---|---|---|
| 1 | Báo cáo tiêu thụ (web + Excel) | `/bao-cao-tieu-thu` | `sales_contract_report.consumption` · `sales_contract_consumption_summary.py:26-27,57,66` · `sales_contract_consumption_excel.py:108,154` | ✅ có SL (2 cột) · ❌ chưa có doanh thu/giá BQ theo nguồn · ❌ chưa lọc theo nguồn | Có: thêm doanh thu và giá BQ theo nguồn | **Trung** | `by_source` chỉ cộng tấn. Biểu (2) của khách cần cả doanh thu lẫn giá BQ của mủ thu mua (xem mục 3). |
| 2 | Lịch sử đợt giao | `/bao-cao-tieu-thu` (khối lịch sử) | `sales_contract_delivery_history.py:49,84` | ✅ có cột *Nguồn* · ❌ chưa lọc | Lọc theo nguồn có ích khi rà lại nguồn cũ | Thấp | |
| 3 | Thống kê tiêu thụ | `/thong-ke/tieu-thu` | `unit_report_consumption.py` · `unit_analytics_excel.py:50-51,96` | ✅ đủ: lọc, nhóm, 2 cột, Excel | — | Xong | ⚠ Lỗi có từ trước: lọc nguồn/hình thức/chủng loại thì % KH doanh thu đã để trống (`partial`, `:184`), nhưng **% KH HĐ chuyến vẫn tính** = chuyến *đã lọc* ÷ KH chuyến cả năm (`:142`), nên % thấp sai. |
| 4 | **Báo cáo tổng hợp — Biểu (2) Thu mua** (web + Excel) | `/bao-cao-tong-hop` (tab Thu mua) | `unit_period_report.py:116-121,148-152` · `unit_period_excel.py:42-45` · `PeriodReportPage.tsx:38-41` | ❌ 3 cột *SL tiêu thụ mủ thu mua · Doanh thu tiêu thụ mủ thu mua · Giá bán BQ* vẫn đọc ô nhập tay cũ `purchased_sold_*`. Form không còn ô này; DB local có **0 bản ghi** có số → cột luôn trống | **Có** — đúng chỉ tiêu 6-7-8 của mẫu khách | **CAO** | Lấy từ các lần giao `source=purchase`: SL + doanh thu + giá BQ. Cột *SL tiêu thụ mủ thành phẩm* (`finished_sold_qty`) cũng là ô chết, cần chốt nguồn "Hàng hóa" (Q1) mới nuôi được. |
| 5 | Báo cáo tổng hợp — Biểu (1) Tiêu thụ–Tồn kho | `/bao-cao-tong-hop` | `unit_period_report._consumption_rows` `:157-248` | ❌ | Không bắt buộc: mẫu Biểu (1) không có cột nguồn | Thấp | Nếu thêm 2 cột phụ thì Snapshot (#11) và Chốt số liệu (#12) tự có theo. |
| 6 | Biểu tổng hợp gửi Tập đoàn (Excel) | nút ở `/bao-cao-tong-hop` | `unit_consolidated_layout.py` · `unit_consolidated_excel.py` | ❌ | Không: phần Tiêu thụ của mẫu Ban TTKD chỉ chia HĐDH/chuyến × XK/nội tiêu | Thấp | D/E/F "KH Khai thác · Thu mua · Cộng" để trống theo quyết định 22/09. Đó là kế hoạch, không phải tiêu thụ. |
| 7 | Dashboard đơn vị — khối Tiêu thụ (KPI · xu hướng · phân rã) | `/dashboard-don-vi` | `unit_dashboard.py:34-39,120-135` · `ConsumptionSection.tsx:21-37` | ❌ `_CON_QTY` chưa lấy `qty_exploit/qty_purchase` dù API đã trả | Có | **Trung** | Làm rẻ: thêm 2 khoá và một kiểu chia "Nguồn" vào `SPLITS` (hiện có Loại HĐ · Hình thức). |
| 8 | **Dashboard đơn vị — Tiến độ bán hàng năm** | `/dashboard-don-vi` | `unit_dashboard_outlook.py:62-70` · `unit_dashboard_outlook_calc.py:25-60` | ❌ "Đã giao lũy kế" là 1 số chung. KH đã chia KT/TM/HH nhưng phần thực hiện chưa chia | **Có** — khách yêu cầu 26/09 *"tách khai thác / thu mua"* | **CAO** | Chỉ tách được phần ĐÃ GIAO: `sold[c]` đã có `qty_exploit/qty_purchase`. "Còn phải giao" chưa có nguồn (chỉ khai khi giao) → hiện "chưa phân nguồn". Cần chốt Q3. |
| 9 | Dashboard đơn vị — Chỉ tiêu năm | `/dashboard-don-vi` | `unit_dashboard_targets.py:35-43` | ❌ chưa có chỉ tiêu khai thác | Có thể thêm dòng "Bán nguồn khai thác / KH khai thác" (chờ Q3) | Trung | Hiện có: thu mua NL · hàng hóa · HĐ chuyến · doanh thu. |
| 10 | Chỉ số đơn vị | `/chi-so-don-vi` | `unit_scorecard.py:34-37` · `unit_scorecard_cols.py:75-95` · router nhận `source` (`routers/unit_scorecard.py:80`) | ❌ chưa có cột · web chưa gửi lọc nguồn | Có: thêm 2 cột ở tab Tiêu thụ (rẻ) | Trung | Bảng chéo chủng loại (`unit_scorecard_grade.py`) để nguyên. |
| 11 | Snapshot số liệu tuần | `/snapshot-so-lieu-tuan` | `unit_week_snapshot.py:103-109` (lưu nguyên `period_report`) · `UnitWeekSnapshotTable.tsx:16-37` | ❌ | Tự có theo #4 (và #5 nếu làm) | Trung (làm cùng #4) | Tuần đã chụp giữ số cũ, đúng thiết kế "không chụp đè". |
| 12 | Chốt số liệu (bảng đơn vị xác nhận) | `/chot-so-lieu` | `data_lock_summary.py:28-32,124` | ❌ | Có: đổi nguồn sau khi chốt phải gửi đề nghị sửa, nên đơn vị cần thấy số tách nguồn **trước** khi bấm chốt | Trung | Thêm `qty_exploit/qty_purchase` vào `CONSUMPTION_KEYS` khi `period_report` đã trả 2 khoá này. |
| 13 | Báo cáo tồn kho (nhóm cột "Tiêu thụ theo hợp đồng") | `/bao-cao-ton-kho` | `unit_daily_contract_consumption.py:27-50` | ❌ chỉ chia theo hình thức | Không bắt buộc | Thấp | |
| 14 | Báo cáo thu mua (theo ngày) | `/bao-cao-thu-mua` | `routers/unit_daily.py:76-78` | ❌ không có số tiêu thụ | Mẫu "Biểu (2)-ngày" có chỉ tiêu 6-8 theo ngày | Thấp (sau #4) | |
| 15 | Bản tin biến động — khối Tiêu thụ | `/ban-tin-bien-dong` | `unit_series_consumption.py:19-21` · `ConsumptionBlock.tsx:14-20` | ❌ `GROUPS` bỏ `source`; ghi chú cũ "đã bỏ từ 30/07" nay sai | Có thể (thêm 1 khoá ở backend và web) | Thấp | Sửa luôn câu ghi chú cũ. |
| 16 | Trợ lý AI — tiêu thụ / kế hoạch | `/tro-ly-ai` | `assistant_tools/contract_tools.py:113-177` · `unit_tools.py:85-92,180-225,321` · `unit_plan_progress.py:112-117` | ❌ `by_source` có sẵn nhưng không đưa vào summary | Có | Trung | Hỏi "tiêu thụ mủ thu mua bao nhiêu" thì hiện chưa trả lời được. Câu "chưa có số thực hiện khai thác" cần nói lại: đã có số BÁN từ nguồn khai thác, vẫn chưa có SẢN LƯỢNG khai thác. |
| 17 | Cảnh báo bất thường | `/canh-bao-bat-thuong` | `anomaly_rules.py` | ❌ | Có thể thêm luật (a) tiêu thụ nguồn thu mua > thu mua lũy kế; (b) KH khai thác = 0 mà có bán nguồn khai thác | Thấp–Trung | Có ích để dò lần giao bị gán nhầm (xem mục 4). |
| 18 | Bảng nhắc việc đơn vị | mọi màn của tài khoản đơn vị | `member_checklist.py:32-34` | n/a | Không: server đã chặn lần giao thiếu nguồn | Thấp | Có thể nhắc "rà lại nguồn của các lần giao trước 03/10". |
| 19 | Theo dõi nộp | `/thong-ke/tinh-trang-nop` | `unit_report_status.py` | n/a | Không | — | |
| 20 | Kế hoạch năm | `/ke-hoach-nam` | `unit_daily_repo.py:403-440` · `schemas/unit_daily.py:47-55` | n/a (đã có KH KT · TM · HH riêng) | Không: mẫu khách không có KH tiêu thụ theo nguồn | — | |
| 21 | Còn phải giao (contract_backlog) | trong #1 và #8 | `contract_backlog.py` | n/a | Hiện không làm được: nguồn chỉ khai khi giao | Thấp | Muốn dự báo theo nguồn thì phải khai nguồn DỰ KIẾN lúc ký; chưa ai yêu cầu. |
| 22 | Danh sách hợp đồng | `/hop-dong` | `routers/sales_contracts.py:137-150` | ✅ ở chi tiết và đợt giao · ❌ chưa lọc | Lọc theo nguồn giúp rà dữ liệu cũ | Thấp | |
| 23 | Dashboard chính | `/` | — | n/a | Không có số tiêu thụ của đơn vị | — | |
| 24 | Nhập Excel tiêu thụ cũ (`sales`/`sales_own`) | (đang tắt) | `unit_daily_excel_io.py:9,49,116-119,564` | tàn dư cơ chế cũ | Dọn bỏ | Thấp | |

**Có so lệch chỉ tiêu nào không?** Không tìm thấy chỗ nào đem *tổng tiêu thụ* so với *KH khai thác*,
hay ngược lại:
- Outlook so tổng bán (cả 3 nguồn) với KT + TM + HH.
- Dashboard và Thống kê so chuyến với KH chuyến.
- Biểu (2) so thu mua NL với KH thu mua.

Mẫu SXKD của Ban TTKD cũng so **tổng với tổng** (mục 3). Tách nguồn mở thêm 2 phép so mới, chưa có ở
đâu:
- bán nguồn khai thác ↔ KH khai thác;
- bán nguồn thu mua ↔ KH thu mua / thu mua thực hiện.

**Tồn kho "nhập – xuất":** không có. Tồn kho là số đơn vị tự khai tại một thời điểm (`unit_period_report._latest_stock`,
`inventory_auto.py`), không tính theo dòng nhập – xuất, nên không có phần "xuất" nào cần chia nguồn.

## 3. Bằng chứng từ tài liệu khách

1. **Mẫu báo cáo tuần 2026**, sheet "Biểu mẫu-Thu mua"
   (`docs/bieu-mau-bo-sung/Biểu mẫu-Báo cáo tuần-năm 2026 (new).xlsx`):
   - tiêu đề *"Về công tác Thu mua mủ nguyên liệu và Tiêu thụ mủ cao su nguyên liệu"*;
   - các cột *"Sản lượng tiêu thụ lũy kế mủ thu mua (tấn)"*, *"Doanh thu tiêu thụ lũy kế mủ thu mua (tỷ đồng)"*,
     *"Giá bán bình quân lũy kế (H=G/F)"*.
2. **Định nghĩa chỉ tiêu** (`... (new) (1).xlsx`, sheet "Chỉ tiêu Biểu (2)-ngày" và "(2)-Tuần"):
   - 6 *"Sản lượng tiêu thụ mủ thu mua"*;
   - 7 *"Doanh thu tiêu thụ mủ thu mua"* (ghi chú *"Doanh thu đã xuất hóa đơn"*);
   - 8 *"Giá bán bình quân mủ thu mua"* = (7)/(6).
3. **Biểu (1) Tiêu thụ – Tồn kho** (cùng file, sheet "Biểu mẫu Tiêu thụ -Tồn kho"): **không** có cột
   nguồn, chỉ HĐDH/chuyến × XK UTXK/nội tiêu. Biểu (1) và biểu Tập đoàn vì vậy không cần tách.
4. **File thu mua đơn vị tự gửi**
   (`docs/bieu-mau/Hạnh/DATA ĐẦU VÀO-BÁO CÁO TUẦN/BÁO CÁO TUẦN 20 (21-05-2026) CÁC CTY GỬI VỀ/Báo cáo thu mua/Bà Rịa-Thumua.xlsx`,
   sheet 19 và 20): cột *"Lũy kế tiêu thụ từ nguyên liệu mủ thu mua (tấn)"* · Giá bán · Doanh thu.
   `knowledge/business-process/quy-trinh-bao-cao-tuan.md:48` ghi cùng ý.
5. **Báo cáo SXKD của Ban TTKD**
   (`docs/bieu-mau/ Triều/Báo cáo Tuần/Mẫu và cách thực hiện/Báo cáo Tổng hợp SXKD VRG và Cty Mẹ tuần 22 LK 25-29.05-2026.xlsx`):
   - mục 1.2 lấy *tổng* tiêu thụ chia *"KH sản lượng năm gồm thu mua"*: 233.431 / 526.560 = 44,3%. Tức là
     tổng so tổng, không tách nguồn;
   - mục 1.1 "Khai thác – chế biến – thu mua NL" là **sản lượng**, lấy từ file của văn phòng, không phải
     tiêu thụ.
6. **Phản hồi khách 26/09/2026** (`plans/260926-hd-dai-han-phai-giao/plan.md:12-15`): Tiến độ bán hàng
   *"…so với KH bán hàng … (theo khu vực, Tập đoàn; tách khai thác / thu mua)"*. Lúc đó mới tách được
   phía kế hoạch.
7. **Lịch sử quyết định:**
   - 03/08 quyết *"không còn phân"* tiêu thụ thu mua/khai thác. Việc E3 (3 cột "tiêu thụ mủ thu mua" ở
     Excel báo cáo kỳ) còn treo (`plans/260803-feedback-vrg-doanh-thu-va-bo-chi-phi/ghi-nhan-feedback-va-viec-can-lam.md:25,64-76,175-190`).
   - Gap B7 ngày 26/07: *"không đối chiếu được với biểu Thu mua"* nếu tiêu thụ không có nguồn
     (`plans/260726-thong-ke-loc-bao-cao-don-vi/phan-tich-du-lieu-va-gap.md:58`).
   - 03/10 quyết định trên được đảo lại, nên E3 nay có lời giải là #4.

## 4. Rủi ro dữ liệu — phải xử lý TRƯỚC khi đưa lũy kế theo nguồn lên báo cáo

- **Mọi lần giao trước 03/10 đều đã bị gán "Khai thác"** (`core/db.py`, khối thêm cột `source`).
  Hệ quả: số lũy kế 2026 "tiêu thụ mủ thu mua" ở #4 và #8 sẽ ra **gần 0** cho đến khi dữ liệu cũ được sửa.
- **Một phần dữ liệu khôi phục được.** Hợp đồng do script chuyển đổi tạo ra có ghi chú nguồn cũ
  (`scripts/migrate-sales-contracts.py:43,135`: *"Chuyển từ dòng tiêu thụ cũ (mủ thu mua)"*). Bản sao
  local (tới 22/08) đang có:
  - **276 lần giao** gốc *mủ thu mua* (≈16.656 t, 11 đơn vị) mang nhãn khai thác;
  - **82 lần giao** gộp cả hai nguồn (≈6.034 t, 8 đơn vị).

  Cần đo lại trên prod.
- **Không khôi phục được:** các lần giao từ 30/07 đến 02/10 nhập thẳng vào hợp đồng, không còn dấu
  vết nguồn. Chỉ đơn vị tự rà lại được; lần giao đã chốt thì phải gửi đề nghị sửa.

## 5. Câu hỏi cần chủ dự án chốt

- **Q1 — Hàng hóa (thành phẩm mua ngoài để bán lại) khai nguồn gì?** Hiện chỉ có 2 giá trị (`market_meta.py:157-160`).
  - Thực tế: Tân Biên bán khoảng 5.000 t hàng hóa/năm, và KH bán hàng = KT + TM + HH.
  - Nếu hàng hóa dồn vào "Thu mua" thì chỉ tiêu 6–8 của Biểu (2) (mủ NGUYÊN LIỆU thu mua) bị sai.
  - Đề xuất: thêm giá trị thứ 3 **"Hàng hóa"**. Giá trị này khớp `plan_goods_tonnes` và cột cũ
    "SL tiêu thụ mủ thành phẩm".
  - Cần chốt thêm: hàng nhận nội bộ từ đơn vị khác rồi bán lại thì tính nguồn nào.
- **Q2 — Có sửa nguồn cho dữ liệu cũ không?** Mục 4 cho thấy cần sửa, nhưng hiện trái với ghi chú
  "khách chốt gán khai thác".
  - (a) Có khôi phục "Thu mua" theo ghi chú chuyển đổi không?
  - (b) Có yêu cầu đơn vị rà các lần giao 30/07–02/10 không?
  - (c) Với hợp đồng gộp 2 nguồn thì xử lý thế nào?
- **Q3 — Có so "đã bán từ nguồn khai thác" với KH khai thác không?** KH khai thác là sản lượng vườn
  cây; số bán ra khác số khai thác được vì còn chênh tồn kho. Chọn một trong hai: đem so, hay chỉ hiện
  số tuyệt đối.
- **Q4 — Doanh thu của chỉ tiêu 7 tính theo mốc nào?** Ghi chú của chỉ tiêu 7 là "Doanh thu đã xuất hóa
  đơn", còn hệ thống tính doanh thu theo ngày giao. Có giữ cách tính hiện tại không?

## 6. Thứ tự đề xuất

- **CAO**
  - Chốt Q1 và Q2, rồi làm sạch nguồn của dữ liệu cũ.
  - #4: Biểu (2) Thu mua lấy SL/DT/giá BQ từ các lần giao `purchase`; Snapshot (#11) tự có theo.
  - #8: Tiến độ bán hàng năm, tách phần đã giao theo nguồn.
- **TRUNG**
  - #1: doanh thu và giá BQ theo nguồn.
  - #7 Dashboard khối Tiêu thụ · #10 Chỉ số đơn vị · #12 Chốt số liệu · #16 Trợ lý AI.
  - #9: chỉ tiêu khai thác, sau Q3.
  - Sửa lỗi % KH chuyến khi lọc ở #3.
- **THẤP:** #2, #5, #6, #13, #14, #15, #17, #18, #21, #22, #24.
- **KHÔNG CẦN:** #19, #20, #23.
