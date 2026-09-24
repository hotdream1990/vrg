# Review hạng mục 1 (Kế hoạch khai thác) + hạng mục 5 (Snapshot số liệu tuần)

Ngày 24/09/2026 · chỉ review thay đổi CHƯA COMMIT · không sửa code.

## Phạm vi & cách kiểm
- A (hạng mục 5): `core/db.py` (bảng), `services/unit_week_snapshot*.py`, `routers/unit_week_snapshots.py`, `main.py`, `scheduler.py`, `tests/test_unit_week_snapshot.py`; web `UnitWeekSnapshotPage/Table.tsx`, `unit-week-snapshot-client.ts`, `App.tsx`, `sidebar-menu-builders.tsx`.
- B (hạng mục 1): `db.py`, `unit_daily_repo.py`, `schemas/unit_daily.py`, `routers/unit_daily.py`, `routers/member_self.py`, `unit_daily_excel_io.py`, `unit_period_report.py`, `unit_period_excel.py`, `assistant_tools/unit_tools.py`; web `YearPlanPage.tsx`, `PeriodReportPage.tsx`, `unit-daily-client.ts`, `audit-diff.ts`.
- Đã chạy:
  - `test_unit_week_snapshot.py` trên `vrg_test_d`: **4 passed**.
  - `test_unit_daily.py` + `test_unit_daily_excel.py` trên `vrg_test_a`: **19 passed, 5 skipped** (5 test bị skip vì cờ nhập Excel đang tắt).
  - `ruff`: sạch. `tsc --noEmit`: sạch.
- Viết script tạm trong scratchpad, chạy trên `vrg_test_d`/`vrg_test_a` rồi đã dọn dữ liệu. Không đụng `vrg_caosu`. Mỗi phát hiện dưới đây đều đã chạy thử hoặc đọc code để xác nhận.

## Phát hiện

### Trung — A+B · giá trị NaN/Infinity trong kế hoạch năm làm hỏng việc chụp snapshot mãi mãi
- **Vị trí:**
  - `apps/api/app/schemas/unit_daily.py:39` (cùng các ô `float | None` khác của `PurchasePlanEdit`)
  - `apps/api/app/services/unit_daily_excel_io.py:275-289` (`_as_num`: `float("nan")`, `float("inf")` đều chạy)
  - `apps/api/app/services/unit_week_snapshot_repo.py:56-58` (`json.dumps(..., default=str)` vẫn in ra `NaN`)
- **Kịch bản (đã chạy thử):**
  - `PUT /api/unit-daily/plan {"plan_exploit_tonnes": "NaN"}` trả 200 và DB lưu `nan`. `/api/member/plan` dùng cùng schema nên tài khoản đơn vị cũng làm được. File Excel có ô chữ "nan" hoặc "inf" cũng vậy (khi bật cờ nhập Excel).
  - Sau đó `period_report("purchase", …)` trả `NaN`. `json.dumps` ra chuỗi có `NaN`, và `CAST(… AS jsonb)` báo lỗi `invalid input syntax for type json`.
  - Hệ quả: job `unit-week-snapshot` lỗi mỗi ngày, "Chụp ngay" trả 500. Hệ thống không chụp bù, nên mọi tuần của năm đó mất bản lưu vĩnh viễn.
  - Kèm theo: nhật ký hoạt động cũng không ghi được. Đã thấy cảnh báo `[audit] Không ghi được nhật ký … Token "NaN" is invalid`.
  - Mức Trung: khả năng xảy ra thấp nhưng hậu quả cao.
- **Đề xuất sửa:**
  - Các ô kế hoạch dùng `Field(default=None, ge=0, allow_inf_nan=False)`.
  - `_as_num` trả None hoặc báo lỗi khi gặp giá trị không hữu hạn.
  - Ở `unit_week_snapshot_repo.insert`, chuẩn hoá số không hữu hạn thành `None` trước khi `json.dumps(allow_nan=False)`, để một ô bẩn không làm mất cả tuần.

### Trung — B · file Excel mẫu CŨ (thiếu cột "Kế hoạch khai thác") âm thầm XOÁ số đã khai
- **Vị trí:**
  - `apps/api/app/services/unit_daily_excel_io.py:314-316`: tìm cột theo tiêu đề; thiếu cột thì `idx = None`, giá trị thành `None`.
  - `:445-449`: truyền `None` vào `set_year_plan`.
  - `unit_daily_repo.py:448`: `plan_exploit_tonnes = EXCLUDED…`.
- **Kịch bản (đã chạy thử):**
  - Kế hoạch khai thác đang là 2500.
  - Nhập file theo tiêu đề cũ (Đơn vị · Năm · Kế hoạch thu mua…). Màn xem trước báo `ok=1, error=0, _action=update` và không có cảnh báo nào.
  - Sau khi ghi, `plan_exploit_tonnes = None`.
  - Áp dụng cho cả chuyên viên lẫn đơn vị. Mức độ: nghiêm trọng ngay khi bật lại cờ Excel, vì người dùng thường giữ file mẫu cũ. `plan_revenue_ty` đang có cùng lỗi.
- **Đề xuất sửa:**
  - Chỉ ghi đè những cột CÓ trong file: truyền tập khoá có mặt vào commit, và những ô không có trong file thì giữ giá trị cũ bằng `COALESCE`/`EXCLUDED`.
  - Ô trống trong cột có mặt vẫn là "xoá".
  - Tối thiểu: màn xem trước phải cảnh báo "File thiếu cột X — ô X của N đơn vị sẽ bị xoá".

### Trung — B · PUT `/plan` thiếu khoá `plan_exploit_tonnes` thì XOÁ luôn chỉ tiêu (trình duyệt còn bản web cũ)
- **Vị trí:**
  - `apps/api/app/schemas/unit_daily.py:39` (mặc định `None`)
  - `apps/api/app/routers/unit_daily.py:344-347`
  - `apps/api/app/routers/member_self.py:270-273`
  - `unit_daily_repo.py:423-427` và `:448`
- **Kịch bản (đã chạy thử):**
  - Kế hoạch khai thác đang là 2500.
  - Gửi PUT với body y hệt bản web trước khi deploy (6 ô, không có khoá mới): trả 200, và `plan_exploit_tonnes` thành `None`.
  - Dự án đã từng gặp chuyện trình duyệt giữ JS cũ, phải tải lại cứng (hard-refresh). Sau khi deploy, chỉ cần một đơn vị hoặc chuyên viên đang mở tab cũ sửa BẤT KỲ ô nào là kế hoạch khai thác người khác vừa khai bị xoá, và nhật ký ghi thành "sửa". Lời bình trong docstring ("các chỗ gọi cũ không phải sửa") mô tả đúng chỗ gây lỗi này.
- **Đề xuất sửa:**
  - Router chỉ truyền những khoá có trong `body.model_fields_set`; khoá không gửi thì giữ giá trị trong DB (dựng câu `SET` theo tập khoá, hoặc đọc `before` rồi trộn vào).
  - Gửi `null` tường minh vẫn là xoá. Áp dụng luôn cho 6 ô cũ.

### Trung — A (lỗi có sẵn, lan sang snapshot) · dòng Tổng cộng của file Excel cộng cả % và giá
- **Vị trí:** `apps/api/app/services/unit_period_excel.py:82`. `_NO_SUM` thiếu `price_lace_avg` và `pct_plan_sales_spot`.
- **Kịch bản (đã chạy thử):**
  - 2 đơn vị có `pct_plan_sales_spot` 40% và 70%: ô Tổng cộng trong Excel = **110**.
  - 2 đơn vị có giá mủ dây BQ 30.000 và 32.000: ô Tổng cộng = **62.000**.
  - `unit_week_snapshot_excel` dựng file bằng chính hàm này, nên file bản lưu gửi đi có số sai. Trong khi đó bảng web (`totals`, dùng `_NO_SUM` đầy đủ ở `unit_week_snapshot.py:39-40`) để trống ô này, nên hai nơi lệch nhau.
- **Đề xuất sửa:** thêm `price_lace_avg`, `pct_plan_sales_spot`, `pct_plan_revenue` vào `_NO_SUM`. Tốt hơn nữa là dùng chung một hằng số với `unit_week_snapshot._NO_SUM`.

### Thấp — A · giờ job cố định 11:10, không theo `EDIT_CUTOFF_HOUR` (admin đổi được ở trang Cấu hình)
- **Vị trí:** `apps/api/app/services/unit_week_snapshot.py:34`, `config_repo.py:77`.
- **Kịch bản:**
  - Admin đặt giờ chốt 14. Job 11:10 thứ Hai thấy hạn 14:00 chưa tới nên trả "empty".
  - Tới 11:10 thứ Ba mới chụp (trễ khoảng 21 giờ). Bản lưu bị gắn nhãn "chụp sau hạn — số có thể gồm cả phần sửa sau hạn".
  - Ngược lại, đặt giờ chốt 9 thì tuần nào cũng bị gắn nhãn "chụp sau hạn" (lệch 2 giờ 10 phút, vượt ngưỡng 1 giờ).
- **Đề xuất sửa:** job chạy mỗi giờ (bước kiểm `get_summary` rất nhẹ), hoặc tính giờ chạy = giờ chốt + 10 phút khi gieo/đồng bộ lịch.

### Thấp — A · hạn chụp chỉ dựa vào cửa sổ của ĐƠN VỊ, trong khi chuyên viên vẫn được sửa hợp lệ sau lúc chụp
- **Vị trí:**
  - `apps/api/app/services/unit_week_snapshot.py:48-60`
  - Chuyên viên (editor) ghi số liệu ngày theo `assert_editor_window(...)` với `EDITOR_EDIT_WINDOW_DAYS`, ở `routers/unit_daily.py:229`.
- **Kịch bản:** `MEMBER=1`, `EDITOR=7`. Bản lưu chụp lúc 11:00 thứ Hai, nhưng chuyên viên vẫn sửa số tuần đó hợp lệ tới hết Chủ nhật tuần sau. Dòng chữ "sửa số liệu sau thời điểm này không làm đổi bản lưu" đúng, nhưng bản lưu không phải "số chốt" của Ban.
- **Đề xuất sửa:** làm đúng như spec đã nêu. Cần chủ dự án xác nhận chọn `max(member, editor)` hay giữ `member`.

### Thấp — A · dòng của đơn vị chỉ có hợp đồng (không có bản ghi ngày) bị làm mờ
- **Vị trí:** `apps/web/src/features/command-center/pages/UnitWeekSnapshotTable.tsx:88`. `days` chỉ đếm bản ghi `unit_daily_report` (`unit_period_report.py:297`), còn tiêu thụ và khối 3 lấy từ `sales_contract`.
- **Kịch bản:** đơn vị có đợt giao trong tuần nhưng không nhập biểu ngày hiện mờ 45%, trông như "không có số". `totals.reporting_units` cũng không đếm đơn vị này.
- **Đề xuất sửa:** `hasData` xét thêm các ô số khác null (`total_consumption`, `stock_finished_hd`…).

### Thấp — A · `due_week(ref)` văng TypeError khi `ref` không kèm múi giờ
- **Vị trí:** `apps/api/app/services/unit_week_snapshot.py:55-58`.
- **Kịch bản (đã chạy thử):**
  - `due_week(datetime(2026,9,28,11,0))` báo `can't compare offset-naive and offset-aware datetimes`.
  - `edit_window._vn` lại quy ước giờ không kèm múi giờ là giờ VN. Hiện không nơi nào gọi kiểu này (job và router đều truyền None), nhưng test hoặc script sau này dễ vấp.
- **Đề xuất sửa:** `n = edit_window._vn(ref)`, hoặc tách thành hàm công khai.

### Thấp — B · Nhật ký hiện tên khoá thô `plan_sales_spot_tonnes` / `plan_revenue_ty`
- **Vị trí:** `apps/web/src/lib/audit-diff.ts:25-27`.
- **Kịch bản:** `_plan_snapshot` nay chụp đủ 7 ô (sửa đúng), nhưng `LABELS` chưa có nhãn cho 2 ô này. Màn Nhật ký hiện tên khoá tiếng Anh.
- **Đề xuất sửa:** thêm "Kế hoạch tiêu thụ (HĐ chuyến)" và "Kế hoạch doanh thu (tỷ đồng)".

### Thấp — B · Trợ lý AI: tỷ lệ `so_don_vi_da_khai` có thể vượt 100%
- **Vị trí:** `apps/api/app/services/assistant_tools/unit_tools.py:268-271`.
- **Kịch bản:** tử số đếm mọi dòng `year_plan(year)`, gồm cả đơn vị đã sáp nhập hoặc ngừng hoạt động. Mẫu số `report_units()` chỉ đếm đơn vị đang hoạt động, nên có thể ra dạng "65/64". Đây là cùng kiểu đang có với `n_rev_plan`.
- **Đề xuất sửa:** chỉ đếm tên nằm trong `report_units()`.

## Đã kiểm — KHÔNG lỗi
- **Ranh giới tuần** (đã chạy thử):
  - 11:00 đúng thứ Hai: N=1 thì chụp tuần vừa hết (hạn 28/09 11:00); lúc 10:59 thì chưa.
  - N=0: 11:00 Chủ nhật chụp chính tuần đó; lúc 10:59 thì chưa.
  - N=7: tới 11:00 Chủ nhật tuần sau mới chụp.
  - Khớp `editable_from` ở đúng 11:00:00 (lúc đó ngày đã khoá).
- **Đổi năm ISO:** 28/12/2026 → "Tuần 53/2026"; 29/12/2025 → "Tuần 1/2026 (29/12/2025 – 4/1/2026)"; tên file dùng năm ISO.
- **Tranh chấp 2 tiến trình** (2 luồng qua bước `get_summary=None` cùng lúc, đã chạy thử): chỉ 1 dòng được ghi, luồng kia nhận `exists` và giữ bản của luồng thắng. `ON CONFLICT DO NOTHING` + commit trong `session_scope` hoạt động đúng.
- **JSON hoá số và ngày:** mọi số đi qua `_num` hoặc được cộng dồn từ `0.0` (Decimal sẽ văng lỗi ngay), `as_of`/`stock_as_of` là chuỗi ISO. Test so khớp `rows` sau khi đọc lại từ DB y hệt. Lỗi duy nhất là NaN/Infinity (mục 1).
- **Quyền:**
  - Tài khoản đơn vị (member) gọi thẳng API: 403 (đã có test). Lãnh đạo đơn vị: caps rỗng nên 403.
  - Lãnh đạo Tập đoàn (executive): thấy menu (`buildExecutiveMenu`), vào được route (`RequireCap unit_daily`), xem 200, `POST /take` 403.
  - Chuyên viên (editor) có quyền sửa `unit_daily`: `POST /take` 403 nhờ `require_admin`.
- **Đổi tên hoặc sáp nhập đơn vị sau này:** bản lưu là jsonb tự đủ, web và Excel không tra lại danh mục, nên không đổi.
- **B — đường dây:** khớp và đủ so với `plan_revenue_ty` (DB · repo · schema · 2 router · Excel mẫu và ghi · period report + Excel · trợ lý AI · web client/màn/nhật ký).
  - Xoá trắng = NULL đúng ở cả 2 cửa (test + script).
  - Thứ tự cột: mẫu Excel là Đơn vị · Năm · **Khai thác** · Thu mua; màn Kế hoạch năm: khai thác là cột đầu, `colSpan=9` khớp 9 cột. Ở báo cáo kỳ (web + Excel), cột khai thác đứng ngay trước "Kế hoạch thu mua".
  - Lãnh đạo đơn vị ghi: 403.

## Việc nên làm (theo thứ tự)
1. Chặn NaN/Infinity ở schema và `_as_num`; làm sạch trước khi `json.dumps` ở repo snapshot.
2. Sửa PUT `/plan` và commit Excel để chỉ ghi những khoá hoặc cột có mặt (giữ luật "để trống = xoá").
3. Sửa `_NO_SUM` của `unit_period_excel` trước khi phát file snapshot.
4. Các mục Thấp tuỳ ưu tiên.

## Câu hỏi còn mở
- Hạn chụp tính theo cửa sổ đơn vị (`member_window`) hay `max(member, editor)`?
- Có muốn job snapshot tự bám `EDIT_CUTOFF_HOUR` không?
