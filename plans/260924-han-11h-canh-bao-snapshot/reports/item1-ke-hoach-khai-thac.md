# Hạng mục 1 — Chỉ tiêu "Kế hoạch khai thác" (agent A, 24/09/2026)

**Trạng thái:** xong. Pytest xanh trên `vrg_test_a`, trừ 1 test cửa sổ nhập liệu của agent B đang làm dở. `tsc` sạch.

## Quyết định
- Cột DB: `unit_purchase_plan.plan_exploit_tonnes double precision`. NULL = chưa khai. ALTER idempotent trong `ensure_schema`.
- Nhãn: **"Kế hoạch khai thác (tấn)"**. Ghi "tấn" cho khớp nhãn "Kế hoạch thu mua (tấn)" đang có. Không ghi "tấn quy khô", vì kế hoạch thu mua cũng không ghi.
- Vị trí: là cột ĐẦU của màn Kế hoạch năm và của file Excel mẫu (sau Đơn vị · Năm, trước Kế hoạch thu mua). Ở báo cáo kỳ biểu Thu mua, cột đứng ngay trước "Kế hoạch thu mua".
- Ô trống = xoá chỉ tiêu (ghi đè cả dòng, giống `plan_revenue_ty`).
- `set_year_plan(..., updated_by, *, plan_exploit_tonnes=None)` dùng tham số keyword, nên các chỗ gọi cũ không phải sửa.
- Không tính % thực hiện, không bật/tắt màn Thu mua. Không đụng `anomaly_rules`, `member_checklist` và `unit_consolidated_*`.
- Giữ nguyên các hàng rào đang có: HQ cap `unit_daily` sửa mọi đơn vị, member chỉ sửa đơn vị được gán, leader bị chặn ghi ở `get_unit_user`.

## File đã sửa
- `apps/api/app/core/db.py`: thêm ALTER cột.
- `apps/api/app/services/unit_daily_repo.py`:
  - `year_plan()` và `set_year_plan()` xử lý cột mới.
  - `_plan_snapshot()` chụp đủ 7 ô. Trước đây nó thiếu `plan_sales_spot_tonnes`/`plan_revenue_ty`, nên nhật ký báo sai "thêm mới" ở 2 ô này.
- `apps/api/app/schemas/unit_daily.py`: thêm trường vào `PurchasePlanEdit`.
- `apps/api/app/routers/unit_daily.py` và `apps/api/app/routers/member_self.py`: truyền trường mới ở PUT `/plan` (chỉ sửa đúng dòng đó).
- `apps/api/app/services/unit_daily_excel_io.py`: thêm cột SPECS `plan` ở vị trí đầu, và ghi cột này khi nhập file.
- `apps/api/app/services/unit_period_report.py`: dòng biểu Thu mua trả kèm `plan_exploit_tonnes`, không kèm %.
- `apps/api/app/services/unit_period_excel.py` và `apps/web/.../PeriodReportPage.tsx`: thêm cột "Kế hoạch khai thác" trước "Kế hoạch thu mua".
- `apps/api/app/services/assistant_tools/unit_tools.py`: `get_unit_plan_progress` trả thêm khối `khai_thac`, gồm tổng kế hoạch, số đơn vị đã khai và ghi chú "chưa có số thực hiện".
- `apps/web/src/lib/unit-daily-client.ts`: thêm trường vào `YearPlanRow`.
- `apps/web/.../YearPlanPage.tsx`: thêm cột đầu nhập được, dòng Tổng cộng và `colSpan`.
- `apps/web/src/lib/audit-diff.ts`: thêm nhãn "Kế hoạch khai thác năm" cho màn Nhật ký.
- Test:
  - `tests/test_unit_daily.py`: sửa phép so dict ở test luồng chính, và thêm `test_year_plan_stores_exploit_target_and_blank_clears_it`. Test này đi qua cả 2 cửa ghi, kiểm leader bị 403, xoá trắng thành NULL, không bật màn Thu mua, và báo cáo kỳ không có %.
  - `tests/test_unit_daily_excel.py`: thêm `test_plan_template_puts_exploit_first_and_blank_cell_clears_it`. Test kiểm thứ tự cột của file mẫu, nhập 2500 rồi nhập lại với ô trống thì thành NULL. Test gọi thẳng tầng service nên chạy được cả khi cờ nhập Excel đang tắt.

## Đơn vị bị ẩn do `has_purchase_plan`: KHÔNG có đơn vị nào
Tiền đề của đề bài đã cũ. Từ 03/08/2026, `/ke-hoach-nam` lấy `member_unit_repo.active_names()`, nên **hiện đủ 64/64 đơn vị đang hoạt động**. Đơn vị tự khai (`/api/member/plan`) thấy mọi đơn vị được gán. Cột `member_unit.has_purchase_plan` không còn code nào đọc để lọc.

Số đọc từ DB dev `vrg_caosu`:
- 30/64 đơn vị hoạt động có cờ cũ `has_purchase_plan = false`. Đó là các công ty miền Bắc, Lào, Campuchia và Viện Nghiên cứu Cao su.
- 30/64 đơn vị chưa có kế hoạch thu mua > 0. Công tắc thật của menu Thu mua là số này.
- Hai nhóm trùng nhau 27 đơn vị; mỗi bên có thêm 3 đơn vị không nằm ở bên kia.
- Không nhóm nào bị ẩn khỏi màn Kế hoạch năm. Chủ dự án có thể cân nhắc xoá hẳn cột cờ cũ.

## Kết quả test (`vrg_test_a`)
Các file chạy: `test_unit_daily`, `test_unit_daily_excel`, `test_member_checklist`, `test_auth`, `test_member_unit_merge`, `test_assistant`, `test_unit_consolidated_excel`.
- **Kết quả: 75 passed, 5 skipped, 1 failed.**
- Test đỏ là `test_daily_forms_get_extra_days_over_the_other_forms`, thuộc phần cửa sổ nhập liệu của agent B. Test này đã đỏ ngay ở lần chạy nền trước khi tôi sửa gì, và tôi không đụng vào.
- `ruff` sạch trên các file Python đã sửa. `pnpm exec tsc --noEmit -p .` sạch.

## Chưa làm / cần chủ dự án quyết
1. Màn **Thống kê thu mua**, **Chỉ số đơn vị** (`unit_scorecard_cols`) và Excel phân tích chưa có cột khai thác. Các màn này ghép cặp kế hoạch với thực hiện của THU MUA; thêm khai thác không có số thực hiện dễ gây hiểu nhầm. Nên làm khi có số thực hiện khai thác.
2. Nhập Excel kế hoạch bằng file mẫu CŨ (chưa có cột khai thác) sẽ xoá kế hoạch khai thác đã khai. Luật "ghi đè cả dòng" này giống hệt lúc thêm `plan_revenue_ty`. Chức năng nhập Excel hiện đang tắt.
3. Phát hiện ngoài phạm vi: cột "KH doanh thu" và "% thực hiện KH doanh thu" ở màn **Thống kê tiêu thụ** luôn trống. Lý do là `unit_report_consumption` không trả `plan_revenue_ty`; chỉ `unit_period_report` có trả.
4. Dev server 8390 đã tự nạp lại, nên DB dev `vrg_caosu` đã có cột mới (ALTER idempotent). Không có dữ liệu nào bị ghi.

## Sửa sau review (24/09/2026)
Theo `review-item1-item5.md` (phát hiện 1–4, 9, 10) và `review-item2.md` (phát hiện 3):
- **NaN/Infinity, số âm:** 7 ô kế hoạch năm ở `PurchasePlanEdit` chỉ nhận số hữu hạn ≥ 0 (422). `_as_num` của nhập Excel coi "nan"/"inf" là "không phải số" (lỗi dòng); lúc ghi kiểm lại lần nữa (client gửi lại dòng). Làm sạch NaN trong bản lưu tuần do agent F3 làm.
- **Khoá/cột vắng mặt = giữ số cũ:** repo có hàm mới `save_year_plan(values)`, chỉ ghi các ô có trong `values`. `set_year_plan` giữ nguyên chữ ký (ghi cả 7 ô) cho script/test. PUT `/plan` (2 cửa) chỉ ghi `model_fields_set`; `null` tường minh vẫn là xoá. File Excel mẫu cũ thiếu cột: dòng không mang khoá đó nên ô giữ nguyên, và màn xem trước chỉ hiện cột có trong file. Mục 2 ở phần "Chưa làm" phía trên **đã xử lý**.
- **Dòng Tổng cộng Excel báo cáo kỳ:** `_NO_SUM` thêm `price_lace_avg`, `pct_plan_sales_spot`, `pct_plan_revenue`.
- **Cửa sổ nhập liệu cho nhập Excel:** xem trước và ghi (`/import/*` ở 2 router) đánh lỗi hoặc bỏ dòng có ngày quá hạn. Đơn vị theo `member_window()`, chuyên viên theo `editor_window()`, admin không giới hạn, kế hoạch năm được miễn. Câu báo dùng `window_phrase`.
- Nhãn nhật ký cho `plan_sales_spot_tonnes` và `plan_revenue_ty`. Trợ lý AI: tử số của tỷ lệ "đã khai" chỉ đếm đơn vị đang hoạt động.
- **Test hồi quy:** 1 test ở `test_unit_daily.py` (khoá vắng mặt, null, NaN, số âm) và 4 test ở `test_unit_daily_excel.py` (NaN/số âm, mẫu cũ, Tổng cộng, cửa sổ nhập qua router với cờ mở tạm bằng dependency override). Sửa 1 dòng test cũ: muốn xoá thu mua thì phải gửi `plan_tonnes: null`.
- **Kết quả trên `vrg_test_a`:** 4 file được giao: 41 passed, 5 skipped. Các file liên quan (analytics · scorecard · leader/executive · merge · audit · assistant): 106 passed. `ruff` sạch, `tsc` sạch.
- **Còn lại, ngoài phạm vi:** body JSON có literal `NaN` (trình duyệt không bao giờ gửi) vẫn bị từ chối, nhưng trả **500** thay vì 422, vì handler 422 mặc định của FastAPI không JSON hoá được `nan`. Lỗi này chung cho mọi endpoint; nên thêm handler `RequestValidationError` ở `main.py`.
