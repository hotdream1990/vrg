# Phase 04 — Sửa theo kết quả rà đối kháng + kiểm thử UI thật

Nguồn: rà đối kháng backend + web (15/09/2026) và kiểm thử tay trên dev (Tây Ninh, biểu Thu mua 20/08:
gửi → duyệt → gỡ đợt chốt 31/08, giữ đợt 15/08 — đạt).

## Thay đổi hợp đồng API (cập nhật api-contract.md)
- `POST /api/edit-requests/{id}/approve` body: `{note?: string, expected_updated_at: string, accept_changed?: boolean}`.
- `POST /api/edit-requests/{id}/reject` body: `{note: string, expected_updated_at: string}`.
  `expected_updated_at` ≠ `updated_at` hiện tại ⇒ 409 "Đơn vị vừa cập nhật đề nghị này — tải lại để xem nội dung mới."
- Duyệt khi bản ghi đã đổi kể từ lúc gửi (`canon(snapshot hiện tại) != canon(before)`) mà không có
  `accept_changed: true` ⇒ 409 "Số liệu đã thay đổi kể từ lúc đơn vị gửi đề nghị — xem cột Hiện tại rồi xác nhận ghi đè."
- `GET /{id}`: `still_blocked: boolean | null` (null = không kiểm được, vd tài khoản người gửi bị khoá);
  thêm `labels: Record<field, Record<rawValue, label>>` — hợp đồng: `customer_id`→tên khách, `parent_id`/`master_id`→số HĐ,
  `delivery_type`/`contract_type`/`channel`→nhãn tiếng Việt, `to_company` giữ nguyên; op khác `{}`.
- Payload `daily_report` / `market_demand` nhận thêm `create_only?: boolean` (nút Thêm) ⇒ lúc gửi đã có số ⇒ 409 đúng câu của API ghi thẳng.
- `daily_move` đổi `target_key` → `daily_move:{kind}:{as_of}` (không đè đề nghị sửa nội dung cùng ngày).

## Backend
B1 version check (trên) · B2 accept_changed · B3 `Op.lockable` (nhu cầu thị trường = False ⇒ duyệt KHÔNG gỡ chốt,
`will_unlock` rỗng) · B4 ngày gỡ chốt lúc duyệt = hợp `row.dates` ∪ `op.dates(payload, snapshot hiện tại)` ·
B5 precheck hợp đồng: `assert_open` cho hợp đồng/đợt giao đang lưu và hợp đồng cha (400), khoá `contract:new` so chữ thường ·
B6 `mailer` làm sạch xuống dòng trong tiêu đề; `notify_result` bỏ tài khoản không hoạt động · B7 khoá `daily_move` ·
B8 `create_only` · B9 `still_blocked` null · B10 `labels` · B11 docstring `edit_request_apply` nói thật: các bước ghi
không chung một transaction (lỗi giữa chừng ⇒ đề nghị vẫn pending). Test bổ sung cho B1–B5, B7, B8.

## Web
W1 gửi `expected_updated_at` (+ `accept_changed` qua ô tick bắt buộc trong popup Duyệt khi `changed_since_submit`) ·
W2 giá 0 trong đề nghị hiện "(xoá)" và coi = trống khi so · W3 bảng so sánh dùng `labels` · W4 nhu cầu/biểu ngày
gửi kèm `create_only` khi thêm mới · W5 bỏ placeholder ô ghi chú duyệt; bộ đếm ký tự không đè nút · W6 câu "không còn bị
khoá" chỉ khi `still_blocked === false` · W7 bỏ `this.name = "ApiError"` · W8 "cập nhật" chỉ khi còn chờ duyệt ·
W9 nhãn cột biểu ngày chỉ áp cho op biểu ngày; bỏ qua `delivered` · W10 chế độ đề nghị mà lưu thẳng được ⇒ báo
"Đã lưu trực tiếp — nội dung sửa không ảnh hưởng số liệu đã khoá." · W11 huỷ dòng cuối trang ⇒ lùi trang ·
W12 icon/tiêu đề nhất quán (SendOutlined mọi nút gửi, DeleteOutlined "Đề nghị xoá", menu + tiêu đề cùng icon, tiêu đề đổi ngày "A → B") ·
W13 "Đề nghị xoá" trong ContractDetailModal · W14 số chờ duyệt chỉ tải lại khi đổi màn hoặc ghi vào `/api/edit-requests` ·
W15 nút "Tải lại"/"Huỷ đề nghị" không xuống dòng/cắt chữ.

## Để lại (báo chủ dự án)
- Hợp đồng cũ đã giao thường đã "Hoàn thành" ⇒ phải "Mở lại hợp đồng" rồi mới gửi được đề nghị.
- Giá thu mua duyệt cho đơn vị bật cầu tự động vẫn ghi sang lớp giá Tập đoàn (giống đơn vị tự nhập đúng hạn).
- Endpoint file hợp đồng cũ của đơn vị không kiểm chủ sở hữu (có từ trước) — đã tách việc riêng.
