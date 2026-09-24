# Review Hạng mục 3 — job `anomaly-notify` (cảnh báo tự động gửi đơn vị)

Ngày review: 24/09/2026. Phạm vi: thay đổi CHƯA COMMIT (anomaly_notify*, support_repo/notify,
schedule_repo, scheduler, routers/support, test mới; web SupportMessageBody, support-format,
SupportThreadPage, SupportPage, AnomalyPage, anomaly-client, support-client).
Chỉ review — không sửa code. Mọi phát hiện dưới đây đều đã tự kiểm (đọc code + chạy thử trên `vrg_test_c`).

## Đã chạy
- `pytest tests/test_anomaly_notify.py` trên `vrg_test_c` → 7 passed.
- Test liên quan (`test_anomalies`, `test_support`, `test_scheduler_catchup`) → 24 passed.
- `pnpm exec tsc --noEmit -p .` → exit 0 · `ruff check` các file Python đã sửa → sạch.
- 3 test kiểm chứng riêng của reviewer (file ở scratchpad, không vào repo) → cả 3 xác nhận đúng như mô tả bên dưới.

## Phát hiện

### 1. [Trung] Đọc dữ liệu "đã nộp" bị lỗi → gửi cảnh báo SAI "chưa nộp" cho MỌI đơn vị, job vẫn báo `ok`
- **Vị trí:** `apps/api/app/services/anomaly_rules.py:467-471` (`scan` bắt lỗi của `_submission_days` rồi dùng `submitted = {}`); `apps/api/app/services/anomaly_notify.py:65` (chỉ nhận ra luật lỗi khi mô tả bắt đầu bằng "Lỗi khi quét").
- **Kịch bản:** lúc 11:05, `unit_daily_repo.in_range` lỗi (DB chập chờn, statement timeout). `not_submitted` và `silent_unit` vẫn chạy "thành công" trên dữ liệu rỗng, nên ~64 đơn vị cùng nhận tin kèm email "chưa nộp … / Chưa nộp biểu nào từ 01/01". `failed_rules = []`, `run_job` ghi `ok`. Batch `alert-<ngày>` đã có nên khi chạy lại trong ngày, đơn vị bị bỏ qua: không gửi được bản đúng để thay.
- **Đã kiểm:** giả lập `in_range` ném lỗi → đơn vị CLEAN (nộp đủ) vẫn có tin, trong đó có "Biểu Tiêu thụ – Tồn kho: chưa nộp… thiếu 2/2" và "Chưa nộp biểu nào…". `failed_rules == []`.
- **Cùng gốc:** khi một luật lỗi thật (vd `wrong_raw_price` timeout), tin vẫn gửi nhưng thiếu nhóm đó. Chạy lại cũng không bổ sung được cho đơn vị đã nhận.
- **Đề xuất:**
  - `_run`/`group` gắn cờ rõ ràng `error: True`, và `scan` gắn cờ khi `_submission_days` lỗi. Không suy ra lỗi từ chuỗi mô tả.
  - `send_alerts` HUỶ cả đợt (không mở luồng) khi có luật lỗi; `finish_run(..., "error")` để admin bấm chạy lại sau.

### 2. [Trung] "Chạy ngay" là GỬI THẬT — không có cách xem mẫu trước khi bật; chạy trước 11:00 sinh 2 tin trong ngày
- **Vị trí:** `apps/api/app/routers/schedules.py:45-49` → `scheduler.run_now` → `anomaly_notify.run_job` → `_create` + `_email`. Chạy được cả khi job đang TẮT.
- **Kịch bản:** tài liệu deploy ghi "lần đầu admin bấm Chạy ngay một lần để xem mẫu rồi mới bật". Bấm như vậy là đã mở luồng và gửi email thật tới mọi đơn vị có cảnh báo, nên `seed_off` không cho được bước duyệt mẫu như mục đích đặt ra. Nếu bấm trước 11:00 thì tạo đợt `alert-<hôm qua>`. Đến 11:05 job (nếu đã bật) gửi tiếp đợt `alert-<hôm nay>`: đơn vị nhận 2 tin gần giống nhau cách vài giờ. Chạy bù buổi sáng sau một ngày lỡ lịch cũng gây ra đúng như vậy.
- **Đề xuất:**
  - Thêm chế độ xem trước (dry-run), chỉ gọi `build_messages` (hàm thuần, không ghi DB), vd `GET /api/schedules/anomaly-notify/preview`, hoặc nút "Xem trước" ở trang Lịch chạy. Sửa lại hướng dẫn deploy/chụp ảnh cho khớp.
  - Cân nhắc bỏ chạy bù cho mốc hôm qua khi còn trong cùng ngày và trước lần chạy 11:05.

### 3. [Thấp] Email gửi đồng loạt: mỗi đơn vị một luồng SMTP mở cùng lúc
- **Vị trí:** `apps/api/app/services/anomaly_notify.py:109-120` → `support_notify.notify_to_units` (`support_notify.py:78-88`) → `mailer.send_async` (mỗi thư một thread daemon).
- **Kịch bản:** khi đủ tài khoản lãnh đạo, lúc 11:05 có tới ~64 kết nối SMTP mở cùng lúc. Nhà cung cấp chặn (421/too many connections) thì thư mất, chỉ còn dòng log `warning`, không thử lại. `try/except` trong `_email` không bắt được lỗi này vì thư gửi bất đồng bộ.
- **Đề xuất:** với job, gửi TUẦN TỰ trong một thread nền (hoặc dùng chung một kết nối SMTP), đếm số thư lỗi và đưa vào `note`.

### 4. [Thấp] Link trong tin có thể mở trang KHÁC phạm vi tin
- **Vị trí:** `apps/api/app/services/anomaly_notify.py:71` (`expand([name])` theo TỪNG đơn vị) so với `apps/api/app/routers/member_anomalies.py:26-28` (`expand(leader.member_units)`, lấy mọi đơn vị được gán); `apps/web/src/App.tsx` (`RequireRole ["admin","leader"]`).
- **Kịch bản:**
  - Lãnh đạo gán 2 đơn vị A, B bấm link trong tin của A → trang hiện cả dòng của B, số tổng không khớp tin.
  - Chuyên viên HQ có quyền `support` (không phải admin) mở luồng cảnh báo và bấm link → bị route guard đẩy về trang chủ.
- **Đề xuất:** link mang thêm `&unit=<tên>` và trang thu hẹp theo tham số này (server kiểm tra tên thuộc `member_units`). Hoặc ghi rõ trong tin "trang hiện mọi đơn vị bạn phụ trách". Ẩn/biến link thành chữ với vai trò không vào được trang.

### 5. [Thấp] Khoảng ngày từ link không giới hạn → một cú bấm có thể chiếm CPU cả phút
- **Vị trí:** `apps/web/src/lib/anomaly-client.ts` `rangeFromQuery` (chỉ kiểm định dạng + `from<=to`). `SupportMessageBody.tsx` biến MỌI đường dẫn nội bộ thành link, kể cả trong tin do đơn vị tự gõ. Server `routers/anomalies.py:57-58` và `member_anomalies.py` không giới hạn độ dài khoảng.
- **Kịch bản:** đơn vị gửi trả lời chứa `/canh-bao-bat-thuong?date_from=1000-01-01&date_to=9999-12-31`, admin bấm vào. Đo `_missing_days` + `vn_day_runs` cho khoảng này: ~1,3 giây mỗi đơn vị có KH thu mua, tức ~1 phút CPU. Uvicorn chỉ chạy 1 worker (có cả scheduler) nên cả API chậm theo.
- **Phụ:** `Date.parse("2026-02-31")` hợp lệ trong V8 → được chấp nhận, dayjs tự đổi thành 03/03 mà không báo.
- **Lưu ý:** API vốn đã nhận khoảng tuỳ ý từ trước; điểm mới là giờ chỉ cần bấm một link.
- **Đề xuất:**
  - `rangeFromQuery`: parse chặt (`dayjs(s, "YYYY-MM-DD", true)`), bắt buộc cùng năm hoặc khoảng ≤ 366 ngày.
  - `scan_range`: chặn khoảng quá dài (400).

### 6. [Thấp] Lỗi dựng tin của MỘT đơn vị làm hỏng cả đợt
- **Vị trí:** `apps/api/app/services/anomaly_notify.py:82-85` (vòng `compose` không có try/except) và `:94-105` (mọi đơn vị trong một transaction).
- **Kịch bản:** một luật đổi sau này trả dòng thiếu field hoặc có `None`. Khi đó `vn_num(None)` / `_dec` / `r['…']` ném lỗi → `build_messages` ném lỗi → không đơn vị nào nhận tin trong ngày.
- **Đề xuất:** bọc try/except theo từng đơn vị khi `compose`, ghi log và đưa tên đơn vị lỗi vào `note`.

### 7. [Thấp] Test xoá cấu hình và lịch sử thật nếu chạy trên DB dùng chung
- **Vị trí:**
  - `apps/api/tests/test_anomaly_notify.py:214-224`: `DELETE FROM schedule_job WHERE name='anomaly-notify'` trong `finally`.
  - `:57-58`: `_wipe` xoá MỌI `meta_crawl_run` nguồn `anomaly-notify`.
- **Kịch bản:** `conftest.py` cho thấy bộ test hay chạy trên DB dev. Nếu admin đã BẬT job ở DB đó thì test xoá mất dòng lịch; lần khởi động sau, seed tạo lại ở trạng thái TẮT, tức job bị tắt mà không ai hay. Mốc "lần chạy gần nhất" cũng mất theo.
- **Đề xuất:** chụp lại dòng `schedule_job` trước test rồi khôi phục sau test. Chỉ xoá `meta_crawl_run` có `id` lớn hơn mốc lúc bắt đầu test.

### 8. [Thấp] Truy vấn lặp theo từng đơn vị
- **Vị trí:**
  - `anomaly_notify.py:71`: `member_unit_merge.expand` → `rollup_map` → `merge_map()` + `_merged_at_map()`, mỗi đơn vị 2 lần `list_units`, tổng ~130 truy vấn.
  - `support_notify.unit_recipients`: mỗi đơn vị 1 lần `list_users`.
- **Đánh giá:** hiện < 1 giây nên không gấp.
- **Đề xuất:** tính `rollup_map()` một lần rồi tự mở rộng cho từng đơn vị; lấy `list_users` một lần.

## Đã kiểm — KHÔNG có lỗi
- **Cách ly dữ liệu:**
  - `revenue_outlier` bị loại 2 lớp (`anomaly_scope.for_units` + `sections`).
  - Chạy thử trên `vrg_test_c`: tin của đơn vị DIRTY không chứa tên đơn vị nào khác ngoài chính nó và đơn vị đã sáp nhập vào nó (so với toàn bộ `member_unit`, `sales_contract.company`, `fact_price.grade`).
  - Email chỉ mang câu mở đầu + tiêu đề nhóm, không có dòng chi tiết nào.
- **Khớp với trang:** cùng `scan_range`, cùng ngưỡng, cùng `expand(as_of=None)`, cùng khoảng `01/01 → d0`. Cách tính "vừa hết hạn" (`with_year`) khớp với luật.
- **Chống gửi trùng:**
  - Session có transaction (không autocommit), nên `pg_advisory_xact_lock` giữ khoá tới lúc commit; lượt sau (READ COMMITTED) đọc lại thấy luồng đã có.
  - Test 2 thread chạy đồng thời (Barrier) → đúng 1 luồng, 1 email.
  - Đổi N giữa ngày vẫn ra cùng batch (`run_day` = ngày của giờ chốt), nên không trùng. Đổi lại: đơn vị đã nhận không được cập nhật nội dung theo N mới.
  - Email chỉ gửi cho luồng vừa tạo, sau khi commit, nên không thể gửi 2 lần.
- **Link / XSS:**
  - Không dùng `dangerouslySetInnerHTML`.
  - Regex `^\/[A-Za-z0-9]` chặn `//host`, `/\host`, `javascript:`, `/%2F%2F…`.
  - URL tuyệt đối phải cùng `origin`; mẹo `https://x@evil.com` bị chặn.
  - `/a/..//evil.com` vẫn nằm trên cùng máy chủ.
  - Mã hợp đồng do đơn vị gõ chỉ hiện dạng chữ (React tự escape).
- **`seed_off`:**
  - `ON CONFLICT` chỉ cập nhật `day_of_week`, không đụng `enabled`, nên không tắt job admin đã bật.
  - Job khác được chèn với `enabled=true`, trùng mặc định của cột.
- **AnomalyPage:** không có tham số → `rangeFromQuery` trả `null` → vẫn dùng khoảng mặc định như cũ.
- **Hiệu năng quét:** chỉ quét 1 lần rồi thu hẹp theo đơn vị. Transaction ghi ngắn, email gửi sau commit.

## Câu hỏi mở
- Tài khoản lãnh đạo gán nhiều đơn vị có thật trên prod không? Nếu có thì nên làm phát hiện 4.
- Có muốn thêm nút "Xem trước" (phát hiện 2) trước khi bật job trên prod không?

## Ghi chú
Không cập nhật plan.md: lệnh giao chỉ cho tạo đúng 1 file báo cáo.
