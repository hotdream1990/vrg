# Review bảo mật / phân quyền — Chuông thông báo · Loại nhập liệu · Người nhận thẻ (01/10/2026)

Phạm vi: diff chưa commit trên `apps/api` (+ sw.js / push-client). Chỉ góc nhìn security / authz / cách ly dữ liệu.
Test: `test_member_entry_types.py test_support_audience.py test_web_push.py` → **32 passed**.

## Không có lỗi Critical / High

Đã kiểm, đều đúng:
- **Rule 1:** cả 12 route ghi của `member_self` đều có gác loại; `cap_or_member_scope(EDIT)` → contract cho customers / master / sales (kể cả `/file`, completion, delivery-type); ops đề nghị sửa dùng map đóng chặt (op lạ → KeyError); `PUT /plan` gác theo từng ô; `confirm` cố ý để ngỏ. Không còn router nào khác cho member ghi (member không có cap nào).
- **Rule 2:** mọi đường support (list, batches chỉ HQ, detail + mark_read, reply, status, unread, file_visible, reminders chỉ HQ) đều đi qua `_scope_sql(companies, audiences)`; thiếu audiences → ` AND false` (fail-closed). Lãnh đạo chỉ có `{"leader"}`. Bind param đúng; logic NOT EXISTS trên `support_read` đúng (cùng `now()` trong một transaction → tác giả coi như đã đọc); phía HQ không đổi.
- **Rule 3:** người nhận = active ∩ company ∈ units ∩ audience; mỗi đơn vị một thư; không gửi push cho chính tác giả; push không phụ thuộc SMTP.
- **Rule 4:** allowlist host chặt (đã thử các mẹo parser `\@`, `#@`, `%2f@` — urlsplit và httpx ra cùng host); không follow redirect; chặn token mạo danh; giới hạn 10 trình duyệt/tài khoản; private key VAPID không có trong `CONFIG_SPEC`, không vào log, không vào audit.
- **Rule 5:** `ProfileUpdate` chỉ nhận `full_name`; `/api/users` chỉ admin; danh sách loại rỗng/sai → 400.
- **Rule 6:** guard executive và chặn ghi theo method cho leader không bị ảnh hưởng.

## Medium

**M1. Bản ghi ngày `consumption` có ô ngoài loại Tồn kho mà không ai gác**
- Vị trí: `member_self.py:406,423` cùng op `daily_report` (`edit_request_ops.py:151`) gác toàn bộ `kind=consumption` là STOCK. Nhưng `unit_daily_fields.clean_fields("consumption")` (`unit_daily_fields.py:258-275`, `CONSUMPTION_FIELDS` 89-101) vẫn nhận `sales`/`sales_own`/`revenue`/`purchased_sold_*`/`finished_sold_*`.
- Kịch bản: tài khoản chỉ có loại Tồn kho gọi thẳng `PUT /api/member/daily-report` với `{"purchased_sold_qty":…, "purchased_sold_revenue":…}`. Hai ô này đang đổ vào cột tiêu thụ / doanh thu / giá bán BQ của **báo cáo kỳ Thu mua** (`unit_period_report.py:117-121`). Kết quả: loại Tồn kho sửa được số tiêu thụ. Không có màn nào gửi các ô này, chỉ gọi API trực tiếp mới làm được.
- Lệch thêm (đang ẩn vì Excel tắt): ở `member_self.py:52`, import `sales` gắn với CONTRACT mà vẫn ghi vào cùng bản ghi `consumption` (`unit_daily_excel_io.py:555`). Bật lại Excel thì hai đường gác ngược nhau.
- Sửa: với member, bỏ ô không phải tồn kho trước khi upsert, tức chỉ giữ `STOCK_TABLES` + `stock_material` + `stock_ccy` + `no_stock`. Làm cả ở web PUT lẫn op `daily_report`. Hoặc gác `purchased_sold_*` theo PURCHASE và `sales*`/`revenue` theo CONTRACT. Đổi `_IMPORT_ENTRY_TYPE["sales"]` cho khớp.

## Low

**L1. Cướp subscription chỉ cần biết endpoint** — `web_push.py:104`
- Upsert theo endpoint chuyển dòng sang tài khoản gọi sau cùng. Kẻ biết endpoint của nạn nhân (đây là capability URL, API không lộ ra) có thể làm nạn nhân mất push.
- Sửa rẻ: chỉ cho chuyển chủ khi khoá trùng, tức `ON CONFLICT … DO UPDATE … WHERE push_subscription.p256dh = EXCLUDED.p256dh AND push_subscription.auth = EXCLUDED.auth`.

**L2. Xoá user không dọn `push_subscription` / `support_read`** — `user_repo.py:193`
- Tạo lại tài khoản cùng username (username = email) thì trình duyệt của chủ cũ nhận push của chủ mới.
- Sửa: `DELETE FROM push_subscription WHERE username=:u` (và `support_read`) trong `delete_user`. Khi đổi role cũng nên làm.

**L3. Hết phiên (401) không gỡ push** — `apps/web/src/lib/http.ts:72`
- `detachOnLogout` chỉ chạy khi bấm Đăng xuất.
- Kịch bản: máy dùng chung, người sau không có chuông (executive / editor không có quyền support) nên không chạy `resubscribeIfGranted`. Máy vẫn hiện tiêu đề + 200 ký tự thẻ của đơn vị người trước.
- Sửa: gọi `detachOnLogout()` ở nhánh 401 trước khi về `/login`.

**L4. Huỷ đề nghị sửa không gác loại** — `member_edit_requests.py:66`
- Member chỉ có loại Thu mua huỷ được đề nghị `contract_save` đang chờ của đồng nghiệp cùng đơn vị.
- Sửa: `assert_entry_type(member, entry_type_of(req["op"], req["payload"]))`.

**L5. `localUrl` / `_local_url` chấp nhận `"/\evil.com"`** — `sw.js:20`, `web_push.py:133`
- WHATWG đọc thành `//evil.com`, nên `openWindow` mở trang ngoài.
- Hiện không khai thác được vì URL do server dựng. Hardening: chặn thêm `"/\\"`.

## Câu hỏi còn mở
- Đơn vị phản hồi / member mở yêu cầu chỉ báo cho HQ. Lãnh đạo và CV khác trong `audience` của thẻ không nhận email/push. Đó là cố ý hay sót?
- Phía đơn vị: thẻ có `last_side='unit'` luôn bị coi là "đã đọc" với mọi người trong đơn vị. Theo luật đọc theo TỪNG NGƯỜI thì lãnh đạo sẽ không thấy tin CV vừa nhắn là chưa đọc. Có chấp nhận không?
