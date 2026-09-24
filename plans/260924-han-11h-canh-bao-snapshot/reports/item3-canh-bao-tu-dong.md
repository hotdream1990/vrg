# Hạng mục 3 — Tự động gửi CẢNH BÁO cho đơn vị qua "Hỗ trợ & Thông báo"

Trạng thái: **xong** — job chạy được, test xanh (7 test mới + 23 test cũ liên quan), `tsc` sạch.
Mẫu nội dung thật (DB dev, chỉ đọc): [item3-mau-noi-dung.md](./item3-mau-noi-dung.md).

## 1. Thiết kế

Job `anomaly-notify` — "Gửi cảnh báo bất thường cho đơn vị (sau giờ chốt nhập liệu)", mặc định
**11:05 hằng ngày**, `catch_up=True`, đăng ký trong `scheduler.JOB_REGISTRY`, tự ghi `meta_crawl_run`
(nguồn `anomaly-notify`) nên trang Lịch chạy hiện lần chạy gần nhất + cơ chế chạy bù dùng được.

Mỗi lần chạy:
1. **Mốc**: `d0 = editable_from(member_window(), now) − 1` = ngày số liệu có hạn đúng bằng giờ chốt
   GẦN NHẤT ĐÃ QUA (chạy 11:05 ngày T ⇒ d0 = T − N). Chạy trước giờ chốt (chạy bù buổi sáng) ⇒ mốc là
   giờ chốt hôm qua. Chỉ dùng hàm của `edit_window` (`member_window`, `editable_from`, `deadline`,
   `now`, `cutoff_hour` gián tiếp) — không số 11 cứng; **không cần thêm hàm nào vào `edit_window.py`**.
2. **Quét 1 lần** bằng đúng hàm của trang (`routers.anomalies.scan_range`, cùng ngưỡng cấu hình), rồi
   thu hẹp theo TỪNG đơn vị đang hoạt động như màn lãnh đạo đơn vị:
   `anomaly_scope.for_units(result, member_unit_merge.expand([đơn vị]))` → bỏ `revenue_outlier`,
   gộp dòng của đơn vị đã sáp nhập vào đơn vị nhận (ghi rõ "(số liệu của …)").
3. Đơn vị có ≥1 cảnh báo → **một luồng riêng** (`kind='alert'`, tác giả `system` /
   "Hệ thống VRG (tự động)", phía `hq`). Mọi luồng cùng ngày chạy chung `batch_id = alert-YYYY-MM-DD`
   → phía Tập đoàn thấy gộp một đợt. Đơn vị sạch không nhận; đơn vị đã sáp nhập không nhận riêng.
4. Email (mỗi đơn vị một thư, dựng bằng `support_notify.unit_email`, gửi TUẦN TỰ cả đợt trong MỘT
   luồng nền `support_notify.send_batch`): bản tóm tắt tên các nhóm + link
   tuyệt đối `APP_BASE_URL/canh-bao-bat-thuong?...` (+ link vào đúng tin). Thiếu SMTP → `mailer.send`
   trả lỗi êm, job vẫn xong. Thiếu `APP_BASE_URL` → email ghi "vào mục Cảnh báo bất thường".
5. Kết quả (hiện ở trang Lịch chạy khi bấm "Chạy ngay"): số đơn vị đã gửi · bỏ qua vì đã nhận ·
   **chưa có tài khoản lãnh đạo** (kèm tên) · không có cảnh báo · đơn vị bỏ qua do lỗi dựng nội dung
   (nếu có). Có luật quét lỗi → **huỷ cả đợt**, lượt chạy `Lỗi` kèm tên luật (xem "Sửa sau review").

### Khoảng quét đã chọn: 01/01 năm của d0 → d0 (link mang đúng khoảng này)
- Trang Cảnh báo bất thường mặc định **01/01 → hôm qua**. Tin tính từ 01/01 giống trang, nhưng dừng ở
  **d0** chứ không phải hôm qua: mọi mục nêu trong tin đều ĐÃ quá hạn — không nhắc oan những ngày đơn
  vị còn được nhập (khi N > 1).
- Với N = 1 (đúng ví dụ của chủ dự án: 24/09 → hết hạn 23/09) thì d0 = hôm qua ⇒ **trùng khít khoảng
  mặc định của trang**.
- Để N khác 1 vẫn khớp: link là `/canh-bao-bat-thuong?date_from=YYYY-01-01&date_to=d0`, trang đã được
  sửa để đọc 2 tham số này làm khoảng ban đầu ⇒ đơn vị bấm link thấy ĐÚNG các số trong tin
  (vd "thiếu 33/266 ngày"). Mở trang thường (không tham số) vẫn như cũ.
- Ngày d0 được làm nổi bật: "Biểu Thu mua: chưa nộp ngày 23/09/2026 (vừa hết hạn). Từ 01/01/2026 đến
  23/09/2026 thiếu …: <các đoạn ngày>".

### Chống gửi trùng
`batch_id` tất định `alert-<ngày chạy>` chính là dấu vết bền (không thêm bảng/cột, không đụng `db.py`).
Trong MỘT giao dịch: `pg_advisory_xact_lock(hashtext(batch))` → đọc các đơn vị đã có luồng
`kind='alert'` của đợt → chỉ mở luồng cho đơn vị chưa có. Chạy bù + bấm "Chạy ngay" trùng lúc thì
lượt sau chờ lượt trước commit rồi mới đọc ⇒ không kẽ hở. Đơn vị mới phát sinh lỗi sau lần chạy đầu
vẫn được gửi (vào cùng đợt). Quản trị xoá tay một luồng thì lần chạy lại trong ngày sẽ gửi lại (chủ ý).

### Nội dung (người dùng cuối đọc, không mã luật)
Tiêu đề `Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026`; mở đầu "Tính đến 11:00 hôm nay (hết hạn
nhập số liệu ngày 23/09/2026), đơn vị {tên} còn các vấn đề sau:"; các nhóm theo thứ tự: Chưa nộp đủ
báo cáo ngày (Thu mua · Tiêu thụ – Tồn kho, gộp đoạn ngày như `vn_day_runs`, tối đa 6 đoạn gần nhất,
kèm "Đã N ngày không nộp biểu nào") · Giá mủ nguyên liệu nghi sai đơn vị tính · Giá bán hợp đồng nghi
sai đơn vị tính · Có sản lượng nhưng chưa nhập đơn giá · Kế hoạch năm khai thiếu · Chưa gộp tồn kho
sau sáp nhập; mỗi nhóm tối đa 3 dòng rồi "và N … khác"; luật mới chưa có câu riêng hiện "N mục".
Cuối tin: nhắc gửi "Đề nghị sửa số liệu" cho ngày đã quá hạn + "Xem chi tiết tại Cảnh báo bất
thường: /canh-bao-bat-thuong?…" + "trả lời ngay trong tin này".

### Web
- Loại tin mới `alert` → thẻ đỏ **"Cảnh báo tự động"** ở hộp thư, đợt gửi, chi tiết luồng (gom màu thẻ
  về `KIND_COLOR` dùng chung, thay 3 chỗ viết tay). Khay "Đã gửi đơn vị" của Tập đoàn có thêm các đợt
  cảnh báo (người gửi hiện "Hệ thống (tự động)"). Lãnh đạo đơn vị trả lời như luồng thường.
- `SupportMessageBody`: render chữ thuần, chỉ biến **đường dẫn nội bộ** (bắt đầu `/` + chữ/số; hoặc
  URL tuyệt đối CÙNG gốc với web) thành `<Link>`; chặn `//máy-khác`, `javascript:`, trang ngoài; không
  dùng `dangerouslySetInnerHTML`. Link hiện phần đường dẫn (bỏ tham số cho gọn), bấm mở đúng khoảng.
- `AnomalyPage` đọc `?date_from&date_to` (hàm `rangeFromQuery`, sai định dạng/ngược chiều → mặc định).

## 2. File sửa / tạo

| File | Việc |
|---|---|
| `apps/api/app/services/anomaly_notify.py` (mới, 177 dòng) | Job: mốc d0, quét + thu hẹp theo đơn vị, mở luồng chống trùng, email, `run_job` |
| `apps/api/app/services/anomaly_notify_content.py` (mới, 191) | Dựng nội dung thuần (không DB): `compose`, `sections`, `page_link` |
| `apps/api/tests/test_anomaly_notify.py` (mới) | 7 test (xem mục 3) |
| `apps/api/app/services/support_repo.py` | `KIND_ALERT` vào `KINDS`; tách `insert_thread(db, …)` dùng chung với `open_threads` |
| `apps/api/app/services/support_notify.py` | `notify_to_units(..., extra="")` — dòng bắt buộc tới tay (link) không bị cắt 600 ký tự |
| `apps/api/app/services/schedule_repo.py` | `seed_defaults(..., disabled=…)` — job mới tạo ở trạng thái TẮT (chỉ lúc tạo) |
| `apps/api/app/services/scheduler.py` (dùng chung) | Khối đăng ký job (sau khối snapshot của agent D) + `start()` truyền `disabled` theo cờ `seed_off` |
| `apps/api/app/routers/support.py` | Khay đợt gửi gồm cả `alert`; mô tả tham số `kind` |
| `apps/web/src/lib/support-client.ts` | `ThreadKind` thêm `alert` |
| `apps/web/src/features/command-center/sections/support-format.ts` | Nhãn "Cảnh báo tự động" + `KIND_COLOR` |
| `apps/web/src/features/command-center/sections/SupportMessageBody.tsx` (mới) | Render link nội bộ an toàn |
| `apps/web/src/features/command-center/pages/SupportThreadPage.tsx` · `SupportPage.tsx` | Dùng `KIND_COLOR`, `SupportMessageBody`, nhãn người gửi hệ thống |
| `apps/web/src/lib/anomaly-client.ts` · `pages/AnomalyPage.tsx` | `rangeFromQuery` + khoảng ban đầu từ URL |

KHÔNG sửa: `app/core/edit_window.py`, `app/core/db.py` (chú thích cột `support_thread.kind` trong
`db.py` vẫn ghi "request | announce | reminder" — agent chính có thể thêm "| alert" khi gộp).

## 3. Kiểm thử
- `DATABASE_URL=…/vrg_test_c uv run pytest -q tests/test_anomaly_notify.py tests/test_anomalies.py
  tests/test_support*.py tests/test_scheduler_catchup.py` → **31 passed**.
- Test mới: mốc d0 theo giờ chốt & N (kể cả chạy bù trước 11:00, N = 0) · nội dung không bao giờ có
  `revenue_outlier` · end-to-end trên DB thật: đúng 1 luồng cho đơn vị lỗi (thiếu biểu kể cả d0 + giá mủ
  sai + thiếu đơn giá + KH năm thiếu), đơn vị sạch không nhận, đơn vị đã sáp nhập không nhận riêng mà
  lỗi của nó vào tin đơn vị nhận, nội dung có ngày thiếu + link, email tới đúng lãnh đạo có link tuyệt
  đối và `mailer.send` báo "Chưa cấu hình SMTP" không nổ · chạy lại 3 lần không thêm luồng/email ·
  đơn vị không có lãnh đạo vẫn có luồng + ghi chú · lãnh đạo đọc & trả lời qua API, Tập đoàn thấy đợt
  `alert` có 1 phản hồi chưa đọc · job đăng ký đúng và seed ở trạng thái TẮT, admin bật rồi thì seed
  lại không tắt.
- `ruff` sạch các file Python đã sửa; `pnpm exec tsc --noEmit -p .` exit 0.
- DB dev `vrg_caosu`: chỉ chèn sẵn dòng lịch `anomaly-notify` enabled=false (theo lệnh agent chính)
  TRƯỚC khi đăng ký job; kiểm lại sau: `support_thread` = 0, `meta_crawl_run` nguồn `anomaly-notify` = 0.
  Mẫu nội dung chạy với `PGOPTIONS=default_transaction_read_only=on` + tắt DDL.

## 4. Hướng dẫn chụp ảnh (cho agent chính)
Nên chạy trên DB bản sao riêng; nếu chạy trên `vrg_caosu` job sẽ tạo ~64 luồng — dọn sau khi chụp:
`DELETE FROM support_message WHERE thread_id IN (SELECT id FROM support_thread WHERE kind='alert');
DELETE FROM support_thread WHERE kind='alert'; DELETE FROM meta_crawl_run WHERE sources='anomaly-notify';`
1. **Dữ liệu**: cần 1 tài khoản `leader` gán đơn vị có cảnh báo (vd Công ty TNHH MTV Cao su Lộc Ninh —
   có đủ 3 nhóm: chưa nộp · thiếu đơn giá · chưa gộp tồn kho sau sáp nhập), có email để thấy dòng
   "chưa có tài khoản lãnh đạo" giảm. Nên đặt `MEMBER_EDIT_WINDOW_DAYS=1` cho khớp ví dụ 23/09.
2. **Kích hoạt**: admin → `/quan-tri/lich-chay` → dòng "Gửi cảnh báo bất thường cho đơn vị (sau giờ
   chốt nhập liệu)" → **Chạy ngay** (chạy được cả khi job đang tắt; thông báo kết quả hiện ngay).
   ⚠ **"Chạy ngay" = GỬI THẬT ngay** (mở luồng + email tới lãnh đạo đơn vị), không phải xem thử — chỉ
   bấm trên DB kiểm thử. Hoặc
   dòng lệnh, ghim mốc 11:05 để tiêu đề ra "hôm nay":
   `uv run python -c "from datetime import datetime; from zoneinfo import ZoneInfo; from app.services import anomaly_notify as a; print(a.send_alerts(datetime(2026,9,24,11,5,tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))))"`
   (chạy trước 11:00 mà không ghim thì mốc là giờ chốt hôm qua — vẫn đúng, chỉ khác ngày).
3. **Màn cần chụp**: (a) `/quan-tri/lich-chay` dòng job mới (đang TẮT) + thông báo sau "Chạy ngay";
   (b) Tập đoàn `/ho-tro` → khay "Đã gửi đơn vị" → dòng đợt thẻ đỏ "Cảnh báo tự động", "N đơn vị nhận",
   "Người gửi: Hệ thống (tự động)"; (c) `/ho-tro/dot/alert-2026-09-24` danh sách đơn vị của đợt;
   (d) đăng nhập lãnh đạo đơn vị → `/ho-tro` hộp thư có tin thẻ đỏ; (e) `/ho-tro/<id>` nội dung tin, link
   "/canh-bao-bat-thuong" gạch chân bấm được, ô Phản hồi; (f) bấm link → `/canh-bao-bat-thuong?date_from=
   2026-01-01&date_to=2026-09-23`, dòng "Khoảng đang xem: 01/01/2026 → 23/09/2026" và số khớp tin.

## 5. Lưu ý deploy
- **Job mặc định TẮT** (`seed_off` — chỉ áp lúc tạo dòng lịch lần đầu). Lý do: (1) job gửi tin + email
  RA NGOÀI tới ~64 đơn vị MỖI NGÀY — lần đầu nên để chủ dự án duyệt mẫu rồi mới bật; (2) cơ chế chạy bù: deploy sau 11:05 mà job BẬT sẵn thì 30 giây sau khởi động đã phát cả
  loạt tin, không ai kịp duyệt; (3) dev server `reload=True` chạy scheduler trên bản sao prod — bật sẵn
  là tự sinh luồng trong DB dev. **Hậu deploy: admin vào `/quan-tri/lich-chay` bật job.**
- **"Chạy ngay" = GỬI THẬT ngay** tới mọi đơn vị có cảnh báo (kể cả khi job đang TẮT) — KHÔNG dùng
  để xem thử. Muốn xem mẫu trước khi bật: chạy `build_messages` (chỉ dựng nội dung, không ghi DB,
  không gửi): `uv run python -c "from app.services import anomaly_notify as a; r=a.build_messages();
  print(r['failed_rules'], len(r['messages'])); print(next(iter(r['messages'].values()))['body'])"`.
- Khai `APP_BASE_URL` (Cấu hình hệ thống → Email) để email có link tuyệt đối; SMTP chưa khai thì chỉ
  có tin trong app.
- `MEMBER_EDIT_WINDOW_DAYS` trên prod quyết định d0 (DB dev đang trống ⇒ mặc định 7 ⇒ hôm nay cảnh báo
  số liệu ngày 17/09). Muốn đúng ví dụ "24/09 hết hạn 23/09" thì đặt 1.
- Đổi giờ chốt `EDIT_CUTOFF_HOUR` thì chỉnh giờ job cho khớp (job chạy lệch giờ cũng không sai, chỉ
  gửi muộn/sớm theo mốc giờ chốt gần nhất đã qua).
- Không có migration; kind `alert` là giá trị mới trong cột text sẵn có.

## 6. Câu hỏi mở
1. **Biểu Thu mua tính thiếu từ 01/01** (luật `not_submitted`, dùng chung với trang): đơn vị mới dùng
   hệ thống từ tháng 7 bị nêu "thiếu 237/266 ngày: 01/01–23/07" — tin ngày nào cũng nhắc những tháng
   không thể bổ sung. Có nên đặt mốc bắt đầu cho biểu Thu mua như `STOCK_START` (24/07) của Tồn kho?
   Đổi ở `anomaly_rules` sẽ đổi cả trang — cần chủ dự án chốt.
2. Trên DB dev chỉ 1/64 đơn vị có tài khoản lãnh đạo ⇒ gần như không ai nhận email/đọc tin phía đơn
   vị cho tới khi cấp tài khoản lãnh đạo (tin vẫn lưu, Tập đoàn thấy). Cần kiểm số thật trên prod.
3. Với dữ liệu dev, cả 64/64 đơn vị đều có ít nhất một cảnh báo (chủ yếu "chưa nộp") ⇒ bật job là
   mỗi ngày ~64 tin. Có muốn chỉ gửi khi có vấn đề MỚI (vd ngày d0 thiếu / lỗi mới) thay vì nhắc lại
   tồn đọng hằng ngày không? Hiện làm đúng yêu cầu: có cảnh báo là gửi.

## Sửa sau review (24/09/2026, theo `review-item3.md`)
1. **Luật quét lỗi → huỷ cả đợt** (phát hiện 1). `anomaly_rules` gắn cờ tường minh `ERROR_FLAG`
   (`"error": True`) lên nhóm lỗi: luật ném exception (`_run`), và `not_submitted` + `silent_unit`
   khi đọc "đã nộp" lỗi. `anomaly_notify` đọc cờ (không dò chữ mô tả): có luật lỗi → không mở luồng,
   không email, batch trong ngày để trống; lượt chạy ghi `error` kèm tên luật → "Chạy ngay"/lần sau
   gửi lại được. Trang Cảnh báo bất thường hiển thị như cũ (chỉ thêm khoá `error` trong JSON).
2. **Email tuần tự** (phát hiện 3): cả đợt gửi lần lượt trong MỘT luồng nền
   (`support_notify.send_batch` → `send_sequential`); thư lỗi chỉ ghi log, không chặn thư sau.
3. **Lỗi dựng tin 1 đơn vị** (phát hiện 6): try/except từng đơn vị; đơn vị lỗi bị bỏ qua, ghi vào
   note ("bỏ qua do lỗi dựng nội dung …"), lượt chạy `Có cảnh báo` (warning) thay vì `ok`.
4. **Test không phá dữ liệu thật** (phát hiện 7): chỉ xoá `meta_crawl_run` có id > mốc lúc bắt đầu
   test; dòng `schedule_job` được chụp lại và trả NGUYÊN như cũ (enabled/giờ/updated_at).
5. Sửa hướng dẫn: "Chạy ngay" = gửi thật ngay; xem mẫu bằng `build_messages`.
- Test: `test_anomaly_notify.py` thêm 4 test (đọc "đã nộp" lỗi → huỷ đợt rồi chạy lại gửi được · một
  luật lỗi đánh dấu bằng cờ · một đơn vị dựng tin lỗi · thư tuần tự). `vrg_test_c`: 35 passed
  (anomaly_notify + anomalies + support* + scheduler_catchup). `ruff` sạch.
- Chưa làm (ngoài phạm vi giao): phát hiện 2 (nút xem trước/dry-run API), 4 (link thu hẹp theo đơn
  vị), 5 (giới hạn khoảng ngày từ link), 8 (truy vấn lặp).
