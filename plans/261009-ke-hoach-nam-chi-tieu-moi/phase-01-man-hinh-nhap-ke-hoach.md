# Giai đoạn 1 — Màn hình nhập Kế hoạch năm (DB · API · web · Excel mẫu)

Trạng thái: **ĐÃ DEPLOY lên prod, phiên bản 0.4.116 (09/10/2026)**. Bảng chỉ tiêu: [phase-00](phase-00-bang-chi-tieu-final.md) — đọc trước.
Không làm ở giai đoạn này: nạp từ file (phase-02), nút xác nhận (phase-03), % thực hiện trên Dashboard (phase-04).

## Kết quả cần có
Màn "Kế hoạch năm" hiện đủ **7 nhóm · 23 chỉ tiêu** (19 ô nhập/lưu + 4 dòng tổng chỉ đọc, tự cộng ngay khi gõ), mỗi chỉ tiêu một hàng.
Đơn vị chỉ nhập mục con. Mọi nơi đang đọc kế hoạch (Dashboard, báo cáo kỳ, cảnh báo, trợ lý AI) **chạy y như cũ**.

## Quyết định thiết kế (đã khảo sát code 09/10/2026)
1. **Cột lưu mới (11, `double precision` NULL)** trong `unit_purchase_plan`, tên ở phase-00. Bốn tổng (thu mua, chế biến, tiêu thụ, tồn kho) **không lưu**, web tự cộng.
2. **`plan_revenue_ty` vẫn là cột thật** nhưng do server cộng. LUẬT CUỐI (sau review 09/10), hàm `revenue_total_to_save` ở `year_plan_totals.py`:
   - Ghép body vào số đã lưu của 3 con (`plan_revenue_exploit_ty`, `_purchase_ty`, `_goods_ty`). **Còn con nào có số** → `plan_revenue_ty` = tổng các con (làm tròn 6 số lẻ);
     `plan_revenue_ty` gửi kèm bị **bỏ qua** (con thắng), kể cả khi body không có khoá con nào.
   - **Không còn con nào có số**: body vừa xoá nốt con cuối (con trong body khác số đang lưu) → `plan_revenue_ty` = NULL; ngược lại ghi `plan_revenue_ty` THEO BODY
     (đơn vị cũ chỉ có tổng; vắng mặt = giữ nguyên).
   - Vì vậy tab web CŨ gửi cả hàng 19 khoá (3 con = null) và chỉ sửa ô khác thì tổng cũ **không bị xoá**.
   - `set_year_plan` (hàm bọc cũ, đối số vị trí) **không đổi**, không được đưa khoá con vào dict của nó.
   - Khi lưu, server khoá theo (năm, đơn vị) bằng `pg_advisory_xact_lock` để 2 ô doanh thu gõ liền nhau không tính tổng thiếu.
3. **Loại nhập liệu** (`plan_field_type`): chỉ `plan_tonnes` là PURCHASE; 11 ô mới là CONTRACT như các ô còn lại → **không sửa** `core/entry_types.py` (xem Q8).
4. **Ô mới tuỳ chọn**: không vào `plan_missing`, checklist, cảnh báo, biểu gửi Tập đoàn.
5. **Đảo bảng ở web**: mỗi chỉ tiêu một hàng, nhóm có dòng tiêu đề. Đơn vị có một cột; Ban/admin có mỗi đơn vị một cột + cột "Tổng cộng" + cột nhãn cố định bên trái.
6. **Lưu theo ô đổi**: hiện rời ô là PUT cả hàng, không kiểm có đổi hay chưa. Đổi thành: chỉ lưu khi giá trị khác số đã lưu, và **chỉ gửi các khoá đã đổi** (`null` = xoá). Cần cho luật 2 (đơn vị cũ chỉ có tổng sẽ không bị xoá tổng khi sửa ô khác).
7. **Đề nghị sửa kế hoạch năm**: không dùng `ignore_changes`. Thêm `Op.before_fields` (19 khoá) cho op `year_plan`: khoá thiếu trong ảnh chụp `before`
   (đề nghị lập trước khi có cột mới) coi là `None` khi so → đề nghị cũ không bị 409 oan, đề nghị mới được bảo vệ đủ 19 ô. Bảng so sánh bên Ban có thêm dòng tổng doanh thu tính sẵn.
8. **Excel mẫu**: 11 cột mới ở cuối. File có ô "KH doanh thu" lệch tổng 3 mục con → báo lỗi dòng (không để mất số ngầm); mẫu cũ thiếu cột thì giữ số cũ.
9. **Triển khai: backend trước, web sau** (web mới gửi khoá mới; backend cũ sẽ bỏ qua khoá lạ nên không vỡ, nhưng người dùng tưởng đã lưu).

## Việc backend (chủ sở hữu file: nhóm API)
File được sửa/tạo (nhóm khác KHÔNG chạm):
- `apps/api/app/core/db.py` — thêm 11 `ALTER TABLE unit_purchase_plan ADD COLUMN IF NOT EXISTS … double precision` ngay sau khối ALTER kế hoạch hiện có.
- `apps/api/app/services/unit_daily_repo.py` — `PLAN_FIELDS`/`_PLAN_COLS` thêm 11 khoá (KHÔNG thêm tổng dẫn xuất); `save_year_plan` áp luật doanh thu.
- `apps/api/app/services/year_plan_totals.py` (**mới**, < 80 dòng) — hằng `REVENUE_CHILDREN` và hàm thuần `revenue_total(...)`; để test và dùng lại ở phase 4.
- `apps/api/app/schemas/unit_daily.py` — 11 field `PlanNum | None = None` trong `PurchasePlanEdit`.
- `apps/api/app/services/unit_daily_excel_io.py` — 11 `Col` thêm Ở CUỐI mẫu Excel kế hoạch, tiêu đề không trùng nhau (nhập dò theo tiêu đề); file mẫu cũ thiếu cột thì giữ số cũ (đã có hành vi này).
- `apps/api/app/services/edit_request_ops_plan.py` — thêm `ignore_changes=` 11 khoá mới trong `OPS["year_plan"]` (đề nghị đang chờ lập trước khi có cột mới không bị 409 oan).
- Test: `apps/api/tests/test_unit_daily.py` (so dict 8 khoá ở ~dòng 128 → 19 khoá), **mới** `apps/api/tests/test_year_plan_new_indicators.py`, thêm ca vào `apps/api/tests/test_unit_daily_excel.py`.
- Không đổi: routers `unit_daily.py`/`member_self.py` (tự nhận khoá mới), `data_lock_summary.py` (snapshot theo `PLAN_FIELDS`), `member_checklist.py`, `anomaly_rules.py`, dashboard/báo cáo.

Checklist backend
- [x] 11 ALTER trong db.py, chạy lại `ensure_schema` nhiều lần không lỗi.
- [x] `PLAN_FIELDS` + `year_plans()` trả đủ 19 khoá (None khi chưa nhập).
- [x] PUT admin và PUT member ghi/xoá được từng khoá mới; NaN/inf/âm → 422; khoá vắng mặt giữ nguyên.
- [x] Luật doanh thu: (a) gửi 1–3 con → tổng đúng; (b) gửi con rồi xoá hết → `plan_revenue_ty` NULL; (c) gửi chỉ `plan_revenue_ty` → như cũ; (d) gửi cả hai → con thắng; (e) sửa ô khác → không đụng `plan_revenue_ty`; (f) con có sẵn + gửi 1 con mới → cộng cả con cũ.
- [x] Member PUT: ô mới thuộc CONTRACT nên tài khoản chỉ có loại thu mua bị bỏ ô (403 nếu bỏ hết) — có test.
- [x] Đề nghị sửa kế hoạch năm: tạo + duyệt với khoá mới chạy; đề nghị chờ cũ không 409.
- [x] Excel: mẫu có 11 cột mới ở cuối; xuất rồi nhập lại giữ nguyên số; mẫu cũ không xoá ô mới.
- [x] Chạy đủ bộ test liên quan (lệnh ở mục Kiểm thử).

## Việc web (chủ sở hữu file: nhóm web)
File được sửa/tạo (nhóm khác KHÔNG chạm), thư mục gốc `apps/web/src`:
- `lib/unit-daily-client.ts` — `YearPlanRow` thêm 11 khoá `number | null`.
- `lib/audit-diff.ts` — thêm 11 nhãn (không thì nhật ký hiện khoá thô).
- `features/command-center/pages/year-plan-fields.ts` — `PLAN_FIELDS` +11 (giữ `plan_revenue_ty` trong danh sách để diff/chốt số liệu vẫn nhận, nhưng đánh dấu chỉ đọc), `EMPTY_PLAN` +11 null, `fieldEntryType` không đổi.
- `features/command-center/pages/year-plan-sections.ts` (**mới**) — 7 nhóm, thứ tự dòng, 4 tổng + tổng doanh thu (`PLAN_TOTALS`, **không** nằm trong `PLAN_FIELDS`/`YearPlanRow`/`EMPTY_PLAN`), hàm cộng trả `null` khi mọi mục con trống.
- `features/command-center/pages/YearPlanGrid.tsx` (**mới**) — bảng đảo (hàng = chỉ tiêu).
- `features/command-center/pages/YearPlanPage.tsx` — dùng `YearPlanGrid`, sửa đoạn mô tả, bỏ phụ thuộc bố cục cũ (hàng = đơn vị, `colSpan`).
- `features/command-center/pages/useYearPlan.ts` — lưu khi giá trị đổi + chỉ gửi khoá đã đổi.
- `features/command-center/sections/DataLockPlanBlock.tsx` — chỉ hiện ô có số, gom theo nhóm (khỏi thành 19 thẻ).
- `features/command-center/pages/components/YearPlanLockCell.tsx` — chuyển sang tiêu đề cột đơn vị nếu cần.
- Không đổi: `edit-request-diff.ts` (đọc `PLAN_LABELS` nên tự nhận), các trang báo cáo.

Checklist web
- [x] 7 nhóm, mỗi chỉ tiêu một hàng, đúng thứ tự phase-00; nhãn ghi rõ đơn vị (tấn / tỷ đồng); ô tiền ghi "(tỷ đồng)".
- [x] 5 dòng tổng chỉ đọc (thu mua, chế biến, tiêu thụ, tồn kho, doanh thu) cập nhật ngay khi gõ; mọi mục con trống → tổng hiện "—", không hiện 0.
- [x] Tổng doanh thu: có mục con thì = tổng các con; không có thì hiện số `plan_revenue_ty` đã lưu (đơn vị cũ chỉ có tổng).
- [x] Đơn vị: một cột. Ban/admin: mỗi đơn vị một cột + cột "Tổng cộng" + cột nhãn cố định; cuộn ngang được.
- [x] Trạng thái khoá (đã chốt / đề nghị sửa / hết hạn) vẫn đúng ở từng cột đơn vị; đề nghị sửa chỉ gửi các ô đổi.
- [x] Rời ô không đổi giá trị thì KHÔNG gọi API; ô đổi chỉ gửi khoá đó.
- [x] Ghi chú hướng dẫn trong form màu ĐỎ (class `.form-note`); không emoji, dùng icon vector.
- [x] Mỗi file < 200 dòng; `pnpm exec tsc --noEmit` sạch.
- [x] Nhãn nhóm Tồn kho ghi "cuối năm" (mặc định Q4); đổi nhãn nếu Q4 có đáp án khác.

## Kiểm thử
```bash
cd apps/api && uv run pytest tests/test_unit_daily.py tests/test_unit_daily_excel.py tests/test_year_plan_new_indicators.py \
  tests/test_plan_lock.py tests/test_member_entry_types.py tests/test_member_checklist.py tests/test_assistant_unit_plan_progress.py \
  tests/test_unit_dashboard.py tests/test_unit_dashboard_outlook.py tests/test_unit_targets_and_consumption_plan.py \
  tests/test_data_lock.py tests/test_data_lock_merged_units.py tests/test_auth.py tests/test_member_unit_merge.py \
  tests/test_leader_readonly.py tests/test_edit_request.py -q
cd apps/web && pnpm exec tsc --noEmit
```
Xem thật trên trình duyệt (dev server `.claude/launch.json`): màn Kế hoạch năm với tài khoản Ban/admin và tài khoản đơn vị; gõ thử, kiểm tổng, tải lại xem số còn.
Web không có test tự động; kiểm tay + ảnh chụp lưu ở `visuals/`.

## Rủi ro đã biết
- So sánh dict nguyên 8 khoá (`test_unit_daily.py` ~dòng 128) vỡ khi thêm khoá → sửa test.
- `set_year_plan` mà ghi khoá con = None sẽ làm `plan_revenue_ty` thành NULL, vỡ test cũ → giữ nguyên hàm này.
- Bản chốt số liệu (snapshot) cũ thiếu khoá mới → web chịu được `undefined`.
- Nhật ký hoạt động: `before`/`after` giờ 19 khoá; nhãn ở web.
- Đơn vị sáp nhập: cộng theo lá số, an toàn với `None`; tổng dẫn xuất tính sau khi gộp.
- Đơn vị cũ chỉ có `plan_revenue_ty` (27/62 đơn vị): khi họ nhập mục con đầu tiên, tổng đổi thành tổng các con — đúng ý, nhưng báo cho họ biết trong ghi chú trên màn.

## Ghi chú tiến độ
- 09/10/2026 (sáng): khảo sát code xong (backend 38 chỗ, web 28 chỗ).
- 09/10/2026: code xong bởi 2 agent song song (API và web, file tách biệt); test API 171 pass.
- Review code (2 reviewer độc lập) tìm ra **3 lỗi backend** và **6 điểm web**, đã sửa hết:
  - Nghiêm trọng: tab web cũ gửi cả hàng 19 khoá → xoá mất tổng doanh thu của đơn vị chỉ có tổng (27/62 đơn vị). Đã sửa bằng luật mới ở mục 2.
  - Tổng lệch mục con khi chỉ gửi tổng; `ignore_changes` làm mất cảnh báo 409 của đề nghị mới; Excel xem trước báo lỗi oan.
  - Web: gõ giật (1.100+ ô vẽ lại mỗi phím) → tách ô `memo`; đổi năm lúc đang lưu; bảng duyệt đề nghị chưa hiện tổng doanh thu đổi; CSS cột ghim; nhãn "tự cộng" sai với đơn vị cũ → «số cũ».
  - Thêm: cột «Tổng cộng» của màn Ban đưa lên ngay sau cột nhãn và ghim.
- **Gọn giao diện (09/10, theo góp ý chủ dự án: chữ đầu màn quá dài)**: bỏ 4 đoạn ghi chú đỏ + đoạn mô tả dài; còn 1 câu phụ đề. Nhãn dòng ngắn
  (ngữ cảnh do tiêu đề nhóm mang), đơn vị tính mờ ở mép phải, giải thích đưa vào biểu tượng ⓘ (hiện khi rê chuột/focus): khai thác gồm nhượng quyền ·
  thu mua nguyên liệu (> 0 mới có Báo cáo thu mua) · hàng hóa · tổng doanh thu («số cũ») · tồn kho cuối năm 31/12. Banner đơn vị đã chốt còn 1 câu.
  Chữ hiển thị nằm ở `year-plan-labels.ts` (sửa chữ ở đó, không đụng `PLAN_FIELDS`). Ảnh: `visuals/`.
- **Bảng xác nhận chốt số liệu (09/10, CHỜ CHỦ DỰ ÁN REVIEW)**: 23 chỉ tiêu phải nằm trong bảng đơn vị xem trước khi bấm «Xác nhận chốt số liệu». Bản cũ (thẻ KPI, chỉ hiện ô có số)
  dài và khó quét. Bản mới (`sections/DataLockPlanBlock.tsx` + `data-lock-plan-block.css`): bảng gọn hai cột, 7 nhóm, nhãn/đơn vị dùng chung với màn Kế hoạch năm,
  dòng tổng đậm, **hiện cả ô chưa khai («—»)** + nhãn «8/18 chỉ tiêu đã khai · còn 10 chưa khai»; tổng doanh thu của đơn vị cũ ghi «số cũ»;
  bản chụp trước 09/10 (thiếu khoá mới) chỉ hiện ô có số. Ảnh trước/sau ở `visuals/xac-nhan-chot-so-lieu-*.jpg`. **Chủ dự án đã chốt (09/10):** thiếu chỉ tiêu chỉ **cảnh báo** (không chặn chốt) · **chưa cần cột thực hiện/%** (chỉ chốt số chỉ tiêu; để Giai đoạn 4) · **có nút «Mở màn Kế hoạch năm»** trong bảng (đóng popup rồi sang màn nhập; chỉ hiện khi đơn vị đang xác nhận, ẩn khi chỉ xem lại).
- **Kiểm thử cuối (09/10, sau mọi sửa):** toàn bộ test API **1.061 pass, 8 skip, 0 fail** (7 phút 43 giây, DB test riêng); `ruff` sạch; `tsc --noEmit` sạch; web chạy thật trên bản sao.
- **Kiểm tay trên bản sao dữ liệu prod 06/10** (DB riêng, đã tắt gửi mail/thông báo; không đụng DB dev):
  gõ ô con → tổng đổi ngay · rời ô không đổi → không gọi API · chỉ gửi khoá đã đổi · đơn vị đã chốt xem được, nút «Đề nghị sửa» ở đầu cột ·
  gửi đề nghị với ô mới → Ban thấy dòng tổng doanh thu 2.124,092 → 40 → duyệt → ghi đúng · giả lập tab cũ gửi cả hàng → tổng giữ nguyên · gõ 1 phím với 1.134 ô mất ~7 ms.

- **09/10 chiều — thêm 2 tổng hợp đồng** (yêu cầu chủ dự án): nhóm Hợp đồng xếp theo loại (dài hạn: đã ký · năm trước chuyển sang · TỔNG; chuyến: KH tiêu thụ · năm trước chuyển sang · TỔNG); chỉ đổi web (`year-plan-sections.ts`, `year-plan-labels.ts`), không đổi API/DB vì tổng tính khi đọc. Chưa deploy.

## Đã đưa lên prod (09/10/2026)
- Commit: `cacd490` (code) · `acc96fe` (plan) · `12d4d72` (bump 0.4.116). Chưa push git.
- Build trên server 225 giây, deploy bằng `dokploy-redeploy.local.sh`; app khoẻ, openapi báo 0.4.116, bundle web không còn `localhost:8390`, log 0 lỗi.
- Prod đã có đủ 11 cột mới (migration tự chạy lúc khởi động). Chưa có đơn vị nào nhập chỉ tiêu mới; đơn vị cũ chỉ có tổng doanh thu vẫn hiện «số cũ».
- Người dùng cần Cmd+Shift+R để nạp web mới.
- [ ] Hướng dẫn người dùng cuối (sổ tay) cập nhật khi chốt Q2–Q4, không ghi chi tiết kỹ thuật vào đó.
- Nhập Excel kế hoạch năm trên web đang tắt (`EXCEL_IMPORT_ENABLED=false`) nên 5 test Excel qua endpoint bị skip; hàm đã được test trực tiếp.
- Hai file có sẵn đã vượt 200 dòng từ trước: `lib/unit-daily-client.ts` (359) và `lib/edit-request-diff.ts` (261) — chỉ thêm ít dòng, chưa tách.
