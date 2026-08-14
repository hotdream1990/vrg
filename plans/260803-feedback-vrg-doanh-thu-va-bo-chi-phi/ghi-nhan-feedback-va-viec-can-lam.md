# Ghi nhận feedback 03/08/2026 — Hợp đồng · Tiêu thụ · Doanh thu

> **Nguồn:** feedback người dùng (đơn vị) + **kết luận của Ban quản lý** trong cùng buổi.
> **Phạm vi:** phân hệ Hợp đồng & phụ lục · Báo cáo tiêu thụ · biểu Tồn kho (phần chi phí) · Kế hoạch năm.
> **Trạng thái (03/08/2026 — cuối ngày):** ✅ **ĐÃ LÀM XONG C1 · C2 · C4 · C5** (code + test + chạy
> thử trình duyệt + cập nhật hướng dẫn), **chưa deploy**. Còn treo: **E1 Latex** (giữ nguyên cách
> tính, KHÔNG đoán) và **E3 tàn dư nguồn mủ** (chờ khách chốt bỏ/giữ) → xem mục G.
> **Nền:** tiếp nối [[../260730-feedback-vrg-hop-dong-khach-hang/phan-tich-va-chot-y-khach-hang.md]].

---

## A. Kết luận một dòng

Ban quản lý **thu hẹp phạm vi**: hệ thống chỉ quản lý **doanh thu** — *sản lượng · giá bán ·
doanh thu*. **Bỏ chi phí, bỏ lãi lỗ, bỏ tách nguồn mủ.** Vì vậy **3/5 góp ý của đơn vị không làm**
(đã bị bác hoặc trở nên vô nghĩa). Cộng thêm yêu cầu bổ sung 03/08 về **Kế hoạch năm**, tổng cộng:
**4 việc làm thật** + **1 việc dọn tàn dư** + **8 câu cần chốt**.

---

## B. Đối chiếu: góp ý của đơn vị ↔ quyết định của quản lý

| # | Góp ý của đơn vị | Quyết định của quản lý | Kết luận |
|---|---|---|---|
| 1 | Hợp đồng/phụ lục cần tách **1 phần thu mua · 1 phần khai thác** | **Không còn phân** tiêu thụ thu mua / khai thác | ❌ **KHÔNG làm** — ngược lại còn phải **dọn tàn dư** của cơ chế cũ (mục C3) |
| 2 | Tiêu thụ cần **bộ lọc theo chủng loại** | (không nhắc → giữ) | ✅ **LÀM** (mục C1) |
| 3 | **Latex** nhập nhằng: sản lượng đã quy khô, nhưng có nghiệp vụ chia lẻ trên hợp đồng để ra đơn giá | (không nhắc → giữ) | ❓ **CHỜ CHỐT** — chưa đủ thông tin để làm (mục E1) |
| 4 | Hợp đồng và phụ lục cần thêm **thành tiền** | Quản lý doanh thu (SL · giá bán · doanh thu) | ✅ **LÀM** — trùng hướng quản lý (mục C2) |
| 5 | **Chi phí rất khó nhập**, là việc của kế toán; tính lãi lỗ rất khó | **Bỏ luôn phần chi phí · không cần lợi nhuận** | ✅ **LÀM** — bỏ chi phí toàn hệ thống (mục C4) |
| — | | **Bỏ doanh thu ở Công ty Mẹ** | ⏸ **TẠM GÁC** (khách chốt 03/08: “có gì tính sau”) — không làm gì đợt này (mục E2) |
| 6 | *(yêu cầu thêm 03/08)* Tắt cờ kế hoạch thu mua theo đơn vị · Kế hoạch năm luôn bật · có số kế hoạch thì mới bật Thu mua · thêm **Kế hoạch tiêu thụ (HĐ chuyến)** | — | ✅ **LÀM** (mục C5) |

---

## C. Việc phải làm

### C1. Bộ lọc chủng loại cho tiêu thụ  ·  *(góp ý #2)*

**Hiện trạng:** màn **Báo cáo tiêu thụ** (`/bao-cao-tieu-thu`) chỉ lọc được **kỳ · đơn vị · khách hàng**.
Chủng loại có trong số liệu (`by_grade`) nhưng **không có ô lọc và cũng không hiện bảng theo chủng loại**.
Màn **Thống kê số liệu → Tiêu thụ** (`/thong-ke/tieu-thu`) thì **đã lọc được chủng loại** rồi.

**Phải làm:**
- Thêm tham số `grades` cho `GET /api/sales-contracts/consumption` + `consumption.xlsx`
  (`apps/api/app/routers/sales_contracts.py`), lọc trong `sales_contract_report.deliveries()`.
- ⚠ **Bẫy tính trùng:** một lần giao có **nhiều dòng, nhiều chủng loại**. Lọc theo chủng loại phải
  tính lại sản lượng/doanh thu **theo từng dòng khớp**, KHÔNG được lấy trọn lần giao — lấy trọn là
  cộng cả sản lượng của chủng loại không được chọn.
- Web: thêm ô lọc (dùng lại `MultiSelect`), file Excel xuất theo **đúng bộ lọc đang xem**.
- Cân nhắc thêm luôn **bảng “Theo chủng loại”** cạnh bảng “Theo khách hàng” (số liệu đã có sẵn).

### C2. Thành tiền trên hợp đồng & phụ lục  ·  *(góp ý #4)*

**Hiện trạng:** backend **đã tính sẵn** `revenue` cho từng hợp đồng/phụ lục
(`sales_contract_calc.line_revenue_vnd` = **SL × đơn giá**, quy về đồng). Nhưng trên màn hình:
- Form nhập: mỗi dòng chỉ có SL · quy khô · đơn giá · loại tiền → **không thấy tiền của dòng, không
  thấy tổng tiền của hợp đồng**.
- Danh sách hợp đồng: **không có cột giá trị/thành tiền** nào.
- Màn chi tiết: chỉ hiện “Doanh thu (tỷ đ)” **ở bảng phụ lục**, hợp đồng mẹ không có.

**Phải làm:** thêm **Thành tiền** ở 3 chỗ — (a) từng dòng chi tiết trong form, (b) tổng của hợp
đồng/phụ lục trong form và ở hàng số liệu màn chi tiết, (c) một cột ở danh sách hợp đồng.

### C3. Dọn tàn dư “nguồn mủ” (thu mua / khai thác)  ·  *(quyết định “không còn phân”)*

Từ 30/07 tiêu thụ đã tính từ lần giao và **không tách 2 nguồn** nữa, nhưng còn sót:
- Bộ lọc **“Nguồn mủ”** ở màn Thống kê tiêu thụ (`analytics/ConsumptionStatsPage.tsx`) — nay chỉ còn
  giá trị với dữ liệu **trước 30/07**.
- 2 nhóm ô cũ trong payload báo cáo ngày: `purchased_sold_*` (mủ thu mua) và `finished_sold_*`
  (mủ thành phẩm) — form đã bỏ ô nhập, nhưng **kiểu dữ liệu và cột báo cáo kỳ vẫn còn**.
- 2 cột trong Excel báo cáo kỳ: *“Sản lượng tiêu thụ mủ thu mua”* · *“Doanh thu tiêu thụ mủ thu mua”*
  (`unit_period_excel.py`).

→ Cần chốt **bỏ hẳn hay giữ để tra dữ liệu cũ** (mục E3).

> **Đã xác nhận với khách 03/08:** “không phân nguồn mủ” **chỉ nói về TIÊU THỤ**. Phân hệ **THU MUA
> không liên quan** và **giữ nguyên** (mủ nước · mủ chén · ~~mủ NL chưa cán vắt · RSS đã cán vắt~~
> [bỏ 14/08/2026 — khách báo đơn vị không thu mua 2 loại này] ·
> thành phẩm thu mua · giá BQ · kế hoạch thu mua) — các loại đó là **loại hàng mua vào**, không phải
> “nguồn của lô hàng bán ra”. Bản đang chạy **đã không tách** tiêu thụ theo nguồn, nên phần này chỉ
> còn là **dọn tàn dư**, không phải sửa nghiệp vụ.

### C4. Bỏ chi phí toàn hệ thống  ·  *(góp ý #5 + quyết định)*

Danh sách **đầy đủ** chỗ đang có chi phí (bỏ sót chỗ nào là báo cáo lệch hoặc còn ô nhập mồ côi):

| Nơi | Cụ thể |
|---|---|
| Hợp đồng — dòng chi tiết | ô **Chi phí (tr.đ)** mỗi dòng: `schemas/sales_contract.py` · `sales_contract_calc` (`total_cost`) · `ContractLinesTable.tsx` |
| Hợp đồng — khối thanh toán | ô **Chi phí lần thanh toán**: `payment_cost` (`sales_contract_repo`, `ContractFormModal.tsx`) |
| Màn chi tiết hợp đồng | cột **Chi phí lô hàng (tr.đ)** ở bảng phụ lục |
| Báo cáo tiêu thụ (web) | thẻ **Chi phí dòng bán (tr.đ)** + cột **Chi phí (tr.đ)** |
| Báo cáo tiêu thụ (Excel) | cột **Chi phí dòng bán** trong `_XLSX_COLS` |
| Báo cáo kỳ (Excel + web) | 4 cột: Tổng chi phí dòng bán · Chi phí XK/UTXK · Chi phí trong nước · Chi phí nội bộ (`unit_period_excel.py`, `unit_period_report._cost_by_channel`) |
| Biểu Tồn kho | **khối “4. Chi phí cấp công ty mẹ”**: `cost_total` + `internal_purchase_cost` (`unit_daily_fields.py`, `ConsumptionForm.tsx`, `day_extras.parents`) |

**Lợi ích kèm theo:** bỏ khối chi phí công ty mẹ thì `day_extras` không cần trả `parents` nữa; cây
mẹ–con chỉ còn phục vụ **tiêu thụ nội bộ**.

### C5. Kế hoạch năm: bỏ cờ bật/tắt theo đơn vị, lấy CHÍNH SỐ KẾ HOẠCH làm công tắc  ·  *(yêu cầu 03/08)*

**Hiện trạng — 2 tầng, phải bật tay:**
- `member_unit.has_purchase_plan` = cờ bật/tắt **từng đơn vị** (ô chọn ở màn *Đơn vị thành viên*).
- Cờ này quyết định **2 việc**: (a) đơn vị có hiện ở màn *Kế hoạch năm* không (`plan_names()`),
  (b) tài khoản đơn vị thành viên **có thấy menu + màn “Thu mua”** không (`member_has_purchase_plan`
  trong `routers/auth.py` → `App.tsx`, `AdminLayout.tsx`).
- Số kế hoạch nằm ở bảng `unit_purchase_plan (year, company)`.

**Yêu cầu mới:**
1. **Bỏ ô bật/tắt kế hoạch thu mua** ở màn Đơn vị thành viên (không quản lý theo cờ nữa).
2. Màn **Kế hoạch năm luôn bật cho MỌI đơn vị** (danh sách = tất cả đơn vị đang hoạt động).
3. **Chức năng Thu mua tự bật** khi đơn vị **có số kế hoạch thu mua trong Kế hoạch năm**; không có
   số thì đơn vị đó không thấy màn Thu mua.
4. Thêm cột **“Kế hoạch tiêu thụ (HĐ chuyến) — tấn”** đứng **ngay sau** cột Kế hoạch thu mua
   (thêm cột `plan_sales_spot_tonnes` vào `unit_purchase_plan`, `ADD COLUMN IF NOT EXISTS` như 3 cột
   trước đó — không cần migration tay).

**⚠ Đo trên production hôm nay (03/08/2026):**

| | Số đơn vị |
|---|---|
| Đang BẬT cờ | 35 |
| Đang TẮT cờ | 32 |
| Có số kế hoạch thu mua 2026 (> 0) | 34 |
| **Bật cờ nhưng CHƯA có số 2026 → sẽ MẤT màn Thu mua** | **1** — *Công ty TNHH MTV VRG Oudomxay* (đang để `0`) |
| Chưa bật cờ nhưng có số 2026 → được bật thêm | 0 |

→ Đổi cơ chế gần như **giữ nguyên hiện trạng**, chỉ **1 đơn vị** bị ảnh hưởng. Trước khi bật cơ chế
mới phải hỏi Oudomxay: có tổ chức thu mua không → có thì nhập số kế hoạch, không thì để im.

### C6. Không cần lợi nhuận — **không có việc phải làm**

Hệ thống **chưa từng** tính lãi/lỗ ở bất kỳ đâu (không có công thức doanh thu − chi phí). Ghi lại
để sau này không ai hiểu nhầm là còn tồn đọng.

---

## D. Ảnh hưởng tới số liệu ĐÃ CÓ trên production *(đếm thật, 03/08/2026)*

| Số liệu sẽ bỏ | Bản ghi đang có trên prod |
|---|---|
| Chi phí trên dòng bán | **1** hợp đồng/phụ lục (trên tổng 13) |
| Chi phí lần thanh toán | **0** |
| Chi phí tổng cấp công ty mẹ | **0** |
| Tiêu thụ mủ thu mua / mủ thành phẩm (2 nhóm ô cũ) | **0** / **0** |
| Dòng bán LATEX | **0** |

→ **Bỏ chi phí gần như không mất số liệu nào.** Chỉ 1 hợp đồng có chi phí, đủ để hỏi lại đơn vị.

---

## E. Các điểm phải chốt — **đã chốt 3, còn 5** *(cập nhật 03/08/2026)*

**E1. Latex — sản lượng là ướt hay đã quy khô, và tiền tính trên số nào?**
Hiện tại: hợp đồng có **2 ô** (Số lượng · Quy khô), Latex **bắt buộc** nhập quy khô, và
**doanh thu = Số lượng × Đơn giá** (KHÔNG dùng quy khô). Đơn vị nói “sản lượng nhập vào đã là quy
khô” ⇒ nếu đúng thì hai ô đang **trùng nghĩa** và có thể đang tính tiền sai gốc.
→ Cần đơn vị nói rõ: (a) ô Số lượng của Latex là **mủ nước hay quy khô**; (b) đơn giá thoả thuận
theo **tấn ướt hay tấn khô**; (c) “**chia lẻ trên hợp đồng để ra đơn giá**” cụ thể là thao tác gì —
xin **1 hợp đồng Latex thật** để đọc.

**E2. “Bỏ doanh thu ở Công ty Mẹ” — ✅ CHỐT 03/08: TẠM GÁC, chưa làm gì.**
> Khách: *“phần bỏ qua doanh thu công ty mẹ thì cứ bỏ qua, có gì mình tính sau”.*
> ⇒ **Không có việc phải làm trong đợt này.** Giữ nguyên cách cộng doanh thu hiện tại (doanh thu
> tính theo từng đơn vị bán; tiêu thụ nội bộ vẫn ghi doanh thu ở bên bán). Khi nào Tập đoàn cần
> số liệu **hợp nhất** thì mới bàn lại — lúc đó vấn đề thật là **đếm trùng trong nhóm mẹ–con**.

*(Giữ lại 3 cách hiểu đã phân tích, để lần sau bàn tiếp không phải dựng lại từ đầu:)*
1. Bỏ **cả khối “Chi phí cấp công ty mẹ”** trong biểu Tồn kho (khối duy nhất dành riêng cho công ty
   mẹ — nhưng là **chi phí**, không phải doanh thu). ⇒ trùng luôn với quyết định bỏ chi phí.
2. Khi công ty con bán **nội bộ** cho công ty mẹ thì **không tính doanh thu đó** ở cấp mẹ / cấp Tập
   đoàn (chống **đếm trùng doanh thu** trong nhóm mẹ–con). ⇒ đây là thay đổi **cách cộng số liệu**.
3. Bỏ hẳn dòng tổng doanh thu của công ty mẹ trên một báo cáo cụ thể nào đó.
→ Nếu là (2) thì cần chốt tiếp: **loại hẳn** doanh thu nội bộ khỏi tổng, hay vẫn hiện nhưng **tách
riêng một dòng**?

**E3. Tàn dư “nguồn mủ” — CÒN TREO. Khách hỏi lại “nguồn mủ nào?” ⇒ phải chỉ đúng chỗ mới chốt được.**
“Nguồn mủ” là khái niệm của **cơ chế CŨ (trước 30/07)**: hồi đó biểu tiêu thụ nhập tay có **2 mảng**
— `sales` (bán mủ **thu mua**) và `sales_own` (bán mủ **tự khai thác**). Nay tiêu thụ tính từ lần
giao của hợp đồng nên **không còn tách**; số mới đều rơi vào nhãn *“Theo hợp đồng”*.

Còn sót đúng 3 chỗ:
1. **Ô lọc “Tất cả nguồn mủ”** ở màn *Thống kê số liệu → Tiêu thụ* (`/thong-ke/tieu-thu`), nằm cạnh
   các ô lọc chủng loại · loại HĐ · hình thức. 3 giá trị: **Mủ thu mua · Mủ khai thác · Theo hợp đồng**
   (`SOURCE_LABELS` trong `unit_report_rows.py:34`). Chọn 2 giá trị đầu = chỉ ra dữ liệu trước 30/07.
2. **Cách nhóm “Nguồn mủ”** ở cùng màn đó (nhóm số liệu theo nguồn).
3. **3 cột trong Excel báo cáo kỳ**: *Sản lượng tiêu thụ mủ thu mua* · *Sản lượng tiêu thụ mủ thành
   phẩm* · *Doanh thu tiêu thụ mủ thu mua* — nằm trong trang **Thu mua** của file nên dễ nhìn nhầm là
   của phân hệ Thu mua, thực chất là **tiêu thụ tách theo nguồn**.

→ Chốt: **bỏ hẳn** (màn hình gọn, mất đường tra dữ liệu cũ) hay **giữ** (không phải làm gì)?
Đề xuất: **bỏ ô lọc + cách nhóm** ở màn Thống kê, **giữ 3 cột báo cáo kỳ** cho dữ liệu trước 30/07.

**E4. Chi phí đã nhập: xoá hay chỉ ẩn? — ✅ CHỐT 03/08: XOÁ HẲN.**
Khách: *“chi phí xoá đi em nhé”.* ⇒ ngoài việc bỏ ô nhập và cột báo cáo, còn **xoá số đã lưu**:
- `sales_contract.lines[].cost` — **1 bản ghi** trên prod (xoá khoá `cost` khỏi jsonb).
- `sales_contract.payment_cost` — 0 bản ghi.
- `unit_daily_report.payload.cost_total` / `internal_purchase_cost` — 0 bản ghi.
⚠ Chạy SQL trên prod **bọc `BEGIN; … COMMIT;`**, `SELECT` lại đối chiếu, và **hỏi user trước khi ghi**
(xem [[production-deployment]]).

**E5. Thành tiền — ✅ CHỐT TÊN GỌI, còn treo loại tiền.**
Khách chốt: cột/ô tên đúng là **“Thành tiền”** (không gọi “doanh thu”, “giá trị hợp đồng”).
Phần loại tiền khách chưa nói ⇒ **giả định đang áp dụng** (sai thì sửa 1 dòng):
- **Từng dòng chi tiết:** thành tiền theo **NGUYÊN TỆ của dòng** (`SL × đơn giá`) — dòng VNĐ ra
  *triệu đồng*, dòng USD ra *USD*. Không quy đổi ở mức dòng vì đơn giá vốn nhập theo nguyên tệ.
- **Tổng hợp đồng / phụ lục và cột ở danh sách:** **quy VNĐ, đơn vị *triệu đồng*** (hợp đồng cỡ
  17 tấn × 40 tr.đ ≈ 680 triệu — để *tỷ đồng* sẽ ra 0,68 khó đọc).
- Dòng ngoại tệ **thiếu tỷ giá** thì tổng để **“—”**, KHÔNG coi là 0 (giữ đúng quy tắc đang có).

**E6. Bộ lọc chủng loại: thêm ở màn nào? — ✅ CHỐT 03/08: màn TỒN KHO và TIÊU THỤ.**
Khớp với 2 mục menu **Báo cáo tồn kho** (`/bao-cao-ton-kho`) và **Báo cáo tiêu thụ** (`/bao-cao-tieu-thu`)
— đúng 2 màn đang THIẾU. *(2 màn “Thống kê số liệu → Tiêu thụ / Tồn kho” đã có sẵn bộ lọc chủng loại.)*
- **Báo cáo tiêu thụ:** như mục C1.
- **Báo cáo tồn kho:** lưới tổng hợp mỗi đơn vị 1 dòng; tồn kho khối 1 & khối 2 vốn **đã lưu theo
  từng chủng loại** trong payload, nên lọc được — chọn chủng loại thì cột tồn kho chỉ cộng các
  chủng loại đó (`unit-daily-columns.tsx` + `UnitDailyOverview.tsx`).
- ⚠ Lọc chủng loại **không áp cho form nhập của đơn vị** (form phải nhập đủ mọi chủng loại).

**E7. Công tắc Thu mua lấy kế hoạch của NĂM NÀO? — ✅ CHỐT 03/08**
- Bật màn Thu mua khi đơn vị có kế hoạch thu mua ở **năm hiện tại**, HOẶC ở **năm gần nhất đã nhập**
  (không có số năm nay thì lấy năm gần nhất) → **01/01 không ai bị mất màn Thu mua**.
- **`0` = KHÔNG tổ chức thu mua** (coi như chưa giao kế hoạch). Chỉ `> 0` mới bật.

**E8. “Kế hoạch tiêu thụ (HĐ chuyến)” dùng để làm gì? — ✅ CHỐT 03/08**
- **Không gate màn nào** — chỉ là số kế hoạch, khác hẳn kế hoạch thu mua (kế hoạch thu mua còn làm
  công tắc bật màn Thu mua).
- Có tính **% thực hiện kế hoạch tiêu thụ**, hiện cạnh **% thực hiện kế hoạch thu mua** trong báo
  cáo kỳ.
- ⚠ **Giả định đang áp dụng** (khách chưa nói rõ, sai thì sửa 1 dòng): mẫu số là **sản lượng tiêu
  thụ của riêng HĐ CHUYẾN**, không phải tổng tiêu thụ — vì tên chỉ tiêu ghi rõ “dành cho hợp đồng
  chuyến”. Số tiêu thụ tách theo loại hợp đồng đã có sẵn (`by_type` trong `sales_contract_report`).

---

## F. Ghi chú cho lúc lập kế hoạch

- Thứ tự đề xuất: **C4 (bỏ chi phí)** → **C2 (thành tiền)** → **C5 (kế hoạch năm)** → **C1 (lọc
  chủng loại)** → **C3 (dọn tàn dư)**. C5 độc lập hẳn với 4 mục kia nên tách được thành một đợt riêng. C4 và C2 đụng cùng 2 file form/báo cáo nên làm liền nhau để chỉ sửa một lượt.
- C4 làm **giảm** ô nhập cho đơn vị (đúng điều họ than) → nên deploy sớm, không chờ trọn gói.
- **C5 đã chốt đủ** (E7 + E8) → làm được ngay, không phải chờ 5 câu còn lại.
- ⚠ Trước khi bật cơ chế mới của C5: hỏi **VRG Oudomxay** có tổ chức thu mua không (đơn vị duy
  nhất đang bật cờ mà kế hoạch = 0 → sẽ mất màn Thu mua).
- Hướng dẫn `docs/huong-dan/nhap-lieu-don-vi-thanh-vien/` có nhắc chi phí ở mục 8 và mục Báo cáo tiêu
  thụ → **phải cập nhật cùng đợt** (sửa `spec.json` + `README.md` rồi dựng lại file Word).
- Đợt này **không đụng dữ liệu**, không cần migration; chỉ bỏ trường khỏi màn hình và báo cáo.


---

## G. Đã làm gì trong ngày 03/08/2026

| Mục | Tình trạng | Ghi chú kiểm tra |
|---|---|---|
| **C4** Bỏ chi phí | ✅ Xong (7/7 nơi) | Thêm test `test_cost_is_gone_everywhere`: client cũ gửi `cost`/`payment_cost` lên **cũng không được lưu** |
| **C2** Thành tiền | ✅ Xong | Ô chỉ-đọc mỗi dòng (nguyên tệ) · tổng hợp đồng quy VNĐ (triệu đ) · cột ở danh sách · thẻ ở màn chi tiết. Thiếu tỷ giá → “—” |
| **C1** Lọc chủng loại | ✅ Xong | Báo cáo tiêu thụ (server, theo TỪNG DÒNG) + Báo cáo tồn kho (lọc tại máy). Đối chiếu: lọc SVR 3L ra **376,8 tấn** = đúng bằng `by_grade["SVR 3L"]` của bảng không lọc; số lần giao 168 → 18; cột chưa giao 6 → 2 |
| **C5** Kế hoạch năm | ✅ Xong | Bỏ cờ; màn mở cho **39/39** đơn vị; công tắc Thu mua suy từ số kế hoạch (năm nay hoặc năm gần nhất, `0` = tắt); thêm cột **Kế hoạch tiêu thụ — HĐ chuyến** + **% thực hiện** ở báo cáo kỳ |
| Hướng dẫn đơn vị | ✅ Cập nhật | `spec.json` + `README.md` + dựng lại file Word |

**Kiểm tra tổng:** 161 pytest pass · ruff sạch · `tsc` 0 lỗi · `vite build` OK · chạy thử trên trình
duyệt từng màn đã sửa.

### Việc còn phải làm khi deploy
1. **Xoá dữ liệu chi phí trên prod** (khách chốt “xoá đi”): 1 dòng `sales_contract.lines[].cost`.
   Chạy SQL bọc `BEGIN; … COMMIT;` rồi `SELECT` đối chiếu.
2. Hỏi **VRG Oudomxay** có tổ chức thu mua không → có thì nhập kế hoạch thu mua (đang để `0` nên
   sau khi lên bản mới đơn vị này **không còn màn Thu mua**).
3. Nhắc mọi người **hard-refresh** (Cmd/Ctrl+Shift+R).

### Vẫn giữ nguyên, KHÔNG đụng tới
- ~~**Latex (E1)**~~ → ✅ **ĐÃ CHỐT 04/08/2026 (PA1)**: ô SL = **mủ nước** (đổi nhãn *SL nước*),
  **thành tiền = SL nước × đơn giá** (đơn giá là giá theo tấn nước), còn **sản lượng tiêu thụ trên
  báo cáo lấy theo QUY KHÔ**. Cam kết/tiến độ của hợp đồng vẫn theo SL nước (số ghi trên hợp đồng).
- **Tàn dư nguồn mủ (E3)**: ô lọc “Nguồn mủ” + 3 cột báo cáo kỳ vẫn còn, chờ khách chốt bỏ/giữ.
