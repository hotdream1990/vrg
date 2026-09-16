# Phase 01 — Backend (apps/api)

Đọc trước: [plan.md](plan.md) · [api-contract.md](api-contract.md) (nguồn sự thật).

## File được phép sửa / tạo
Sửa: `app/core/edit_window.py` · `app/core/data_lock.py` · `app/core/permissions.py` · `app/core/db.py` ·
`app/core/audit_meta.py` · `app/main.py` (CORS expose + include router) · `app/routers/member_self.py`
(chỉ thêm include/endpoint đề nghị hoặc tách ra router riêng) · `app/routers/sales_contracts.py`
(chỉ chuyển `_assert_delivery_window` sang service) · `app/services/sales_contract_lock.py` ·
`app/services/data_lock_repo.py` (thêm hàm) · `app/services/support_notify.py` (nếu tách hàm địa chỉ email).
Tạo: `app/schemas/edit_request.py` · `app/services/edit_request_repo.py` · `app/services/edit_request_ops.py`
(+ tách `edit_request_ops_daily.py` / `edit_request_ops_contract.py` nếu > 200 dòng) ·
`app/services/edit_request_apply.py` (duyệt/từ chối + gỡ chốt) · `app/services/edit_request_notify.py` ·
`app/routers/edit_requests.py` (Ban) · `app/routers/member_edit_requests.py` (đơn vị, prefix `/api/member/edit-requests`) ·
`tests/test_edit_request.py`.
KHÔNG đụng `apps/web`.

## Việc cần làm
1. **Header chặn**: `edit_window.assert_editable` (nhánh 403) và `data_lock.assert_not_locked` ném kèm
   `headers={"X-Edit-Blocked": "window" | "lock"}`. CORS `expose_headers=["X-Edit-Blocked"]`.
2. **Quyền** `edit_request` — "Duyệt đề nghị sửa số liệu của đơn vị": 1 cấp (KHÔNG vào `SPLIT_CAPS`),
   KHÔNG vào `EXECUTIVE_CAPS`. Admin tự có qua `effective_caps`.
3. **Bảng** `edit_request` trong `db.py` (theo mẫu comment tiếng Việt các bảng khác, idempotent):
   `id bigserial PK, company, op, target_key, title, dates jsonb, payload jsonb, before jsonb, reason,
   blocked jsonb, status default 'pending', requested_by, requested_at, updated_at, reviewed_by,
   reviewed_at, review_note, unlocked jsonb`. Index `(status, requested_at DESC)`, `(company, requested_at DESC)`,
   UNIQUE partial `(company, target_key) WHERE status='pending'`.
4. **Registry op** (`edit_request_ops*.py`): mỗi op khai 1 chỗ: `label(payload)`, `validate(payload)`
   (pydantic schema gốc → dict đã chuẩn hoá; chạy lớp chuẩn hoá thuần nếu có, vd
   `unit_daily_fields.clean_fields`, `sales_contract_clean.clean` — ValueError ⇒ 400), `company`, `target_key`,
   `title`, `dates(payload, before)`, `snapshot(payload)` (before/current theo api-contract §2),
   `blocked(username, payload, before) -> list[str]` và `apply(payload, requester) -> dict`.
   - `blocked` phải **gọi chính các guard hiện có** và bắt `HTTPException` 403 có header `X-Edit-Blocked`
     → lấy `detail`; 400 (ngày tương lai…) ném lại. Không viết lại luật.
     `daily_report`/`daily_move`: `edit_window.assert_editable(d, member_window())` + `data_lock.assert_not_locked`.
     `market_demand`: chỉ cửa sổ. `contract_*`: chuyển `_assert_delivery_window` từ router sang
     `sales_contract_lock.assert_delivery_fences(...)` (router gọi lại hàm mới, hành vi y cũ); `contract_save`
     an toàn (`is_safe_edit`) ⇒ không bị chặn.
   - `apply`: ghi thẳng repo, **bỏ qua** hai hàng rào thời gian, `updated_by` = người GỬI đề nghị.
     Giá thu mua: dùng chung một hàm với `member_self.upsert_my_price` (tách ra, DRY) — source
     `PURCHASE_SOURCE_UNIT`, unit `PURCHASE_PRICE_UNIT[type]`, giá 0 ⇒ xoá.
     Quyền theo đơn vị KHÔNG bao giờ bỏ qua: hợp đồng phải thuộc đúng `company` của đề nghị.
5. **Gửi** (`POST /api/member/edit-requests`): `_assert_company` y như `member_self` (member_units +
   `assert_unit_can_enter`); với `contract_*` còn phải kiểm hợp đồng cũ thuộc đơn vị được gán. `blocked`
   rỗng ⇒ 409. Chống trùng ⇒ ghi đè đề nghị pending. Ghi `audit_repo.log("edit_request", "create"|"update", …)`.
   Email người duyệt (§7).
6. **Duyệt** (`edit_request_apply.approve`): khoá dòng (`SELECT … FOR UPDATE`) kiểm `pending`; chạy
   `apply` trong `request_ctx.use_note(f"Duyệt đề nghị sửa #{id} của {requested_by}")`; lỗi ⇒ ném lại,
   KHÔNG đổi trạng thái. Thành công ⇒ gỡ chốt: `min(dates)`; mọi đợt CHƯA HUỶ mà đơn vị đã xác nhận có
   `lock_date ≥ min(dates)` ⇒ `data_lock_repo.unlock(round_id, company)`; lưu `unlocked`. Cập nhật
   `approved`, `reviewed_*`, email người gửi.
   `GET /{id}` tính `will_unlock` bằng đúng hàm gỡ chốt dùng (dry), `still_blocked` bằng `blocked(...)`,
   `changed_since_submit` = so `snapshot` hiện tại với `before` (chuẩn hoá JSON, 5 vs 5.0 bằng nhau).
7. **Email** (`edit_request_notify.py`, dùng `mailer.send_async`, không bao giờ làm hỏng nghiệp vụ):
   người duyệt = user đang hoạt động có `has_cap(effective_caps(...), "edit_request")`; địa chỉ = cột email,
   rỗng thì username dạng email (tái dùng hàm của `support_notify`, tách public nếu cần). Nội dung: đơn
   vị, người gửi, tiêu đề, lý do, link. Kết quả duyệt/từ chối ⇒ email người gửi, kèm ghi chú và (nếu có)
   dòng "Chốt số liệu của đơn vị từ ngày … đã được gỡ — vui lòng rà lại và xác nhận chốt."
8. **Câu báo chặn**: `data_lock._MSG` và câu cửa sổ sửa ở `edit_window.assert_editable` đổi đuôi hướng dẫn
   thành "…Cần điều chỉnh, bấm «Đề nghị sửa» để gửi Ban duyệt." — CHỈ khi không làm vỡ test; grep test trước.
   (Cửa sổ sửa cũng áp cho chuyên viên — câu chung phải đúng cho cả hai: dùng câu trung tính
   "…Cần điều chỉnh số liệu ngày này, đơn vị gửi «Đề nghị sửa» để Ban duyệt." cho data_lock; câu cửa sổ giữ nguyên.)
9. **Audit meta**: thêm entity `edit_request` nhãn "Đề nghị sửa số liệu".

## Test bắt buộc (`tests/test_edit_request.py`, DB thật, tự dọn rác `_zz_*`)
- member gửi đề nghị Thu mua ngày ngoài cửa sổ ⇒ 200 pending, số liệu CHƯA đổi; PUT trực tiếp vẫn 403 + header.
- gửi cho ngày còn sửa được ⇒ 409; đơn vị không được gán ⇒ 403; lý do rỗng ⇒ 400; gửi lại ⇒ replaced.
- user không có quyền ⇒ 403 ở `/api/edit-requests`; editor được cấp `edit_request` ⇒ 200.
- duyệt ⇒ số liệu + giá lớp `vrg_unit` đổi, `updated_by` = người gửi, đơn vị có chốt ≥ ngày sửa bị gỡ chốt
  (đợt cũ hơn ngày sửa giữ nguyên), status approved; duyệt lần 2 ⇒ 409.
- từ chối không ghi chú ⇒ 400; có ghi chú ⇒ rejected, số liệu không đổi; huỷ bởi đơn vị ⇒ cancelled.
- `market_demand` + `contract_save` (đợt giao đã giao ngoài cửa sổ) + `contract_delete` + `daily_move`: mỗi op 1 ca đi hết vòng.
- file endpoint: tên file không nằm trong đề nghị ⇒ 404.
- leader POST ⇒ 403.
Chạy: `cd apps/api && uv run pytest tests/test_edit_request.py tests/test_edit_window.py tests/test_data_lock.py tests/test_sales_contract.py tests/test_unit_daily.py tests/test_market_demand.py -q` ⇒ xanh hết.

## Xong khi
Toàn bộ test trên xanh · `uv run python -c "import app.main"` không lỗi · mọi file mới < 200 dòng ·
báo cáo ngắn: file đã sửa/tạo, quyết định lệch khỏi api-contract (nếu có, kèm lý do).

## Trạng thái (15/09/2026)
✅ Xong 9/9 việc + test bắt buộc (`tests/test_edit_request.py` 4 ca, xanh). Lệch nhỏ: đơn giá thu mua
tách ra `app/services/unit_purchase_price.py` (file mới ngoài danh sách); op `contract_*` + danh sách
phía đơn vị dùng phạm vi đơn vị được gán + đơn vị đã sáp nhập vào (khớp `cap_or_member_scope` của
router hợp đồng); `will_unlock` trả `[]` khi đề nghị không còn `pending`.
