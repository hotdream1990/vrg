# Review bảo mật — Nhà máy thông minh (SCADA / OPENQUERY)

Ngày: 30/09/2026 · Phạm vi: chỉ đọc, không chạy test (DB dev dùng chung) · Nhánh `feature/master-contract` (chưa commit)

## Phạm vi
- BE: `services/scada_historian_sql.py`, `scada_client.py`, `scada_factory_repo.py`, `scada_daily_meters.py`, `scada_meters_excel.py`, `routers/smart_factory.py`, `smart_factory_admin.py`, `main.py` (include router), `core/permissions.py`, `core/security.py`, `core/executive_readonly_guard.py`, `core/db.py` (bảng `scada_factory`)
- FE: `lib/smart-factory-client.ts`, `pages/smart-factory/*`, `App.tsx`, `sidebar-menu-builders.tsx`, `lib/permissions.ts`
- Phụ: `scripts/scada-fake-historian/*` (mật khẩu dev mặc định, cổng bind `127.0.0.1` — không vấn đề)

## Kết luận nhanh
Không có Critical. **Không tìm thấy đường SQL injection nào** vào chuỗi OPENQUERY. Phân quyền đúng ma trận.
Hai vấn đề High đều quanh **mật khẩu SQL của SCADA**: lấy được mật khẩu đã lưu bằng cách đổi host (không cần nhập lại mật khẩu), và kết nối TDS không ép mã hoá trong khi kế hoạch có phương án mở 1433 ra internet.

---

## High

### H1. Đổi `host` mà giữ mật khẩu cũ → rút được mật khẩu SCADA về máy chủ giả
- **Chỗ**: `apps/api/app/services/scada_factory_repo.py:121-125` (mật khẩu trống = giữ), `:155-169` (`update_factory` cho đổi host/port/username mà không đòi mật khẩu); kích hoạt bằng `apps/api/app/routers/smart_factory_admin.py:72-75` (`/test`) hoặc chỉ cần một người có cap mở `/meters/daily`.
- **Khai thác**: người có quyền admin, hoặc ai đó lấy được JWT admin (token nằm ở `localStorage`, `lib/auth-token.ts:6`; chỉ cần một lỗi XSS ở bất kỳ màn nào) làm như sau:
  1. `PUT /api/smart-factory/admin/factories/1` với `host=<IP kẻ tấn công>`, `password=null` → bản ghi vẫn giữ mật khẩu cũ.
  2. `POST /admin/factories/1/test` → pymssql gửi LOGIN7 kèm `username` và mật khẩu đã lưu tới máy giả. Máy giả trả "không hỗ trợ mã hoá", hoặc đưa chứng chỉ tự ký (FreeTDS không kiểm chứng chỉ) → mật khẩu trong gói chỉ bị XOR nên giải được ngay (impacket/Responder làm sẵn việc này).
  3. `PUT` trả host cũ để xoá dấu vết (nhật ký vẫn ghi lại lần đổi host, nhưng không ai được cảnh báo).
  → Cam kết "API không bao giờ trả mật khẩu" bị vượt qua. Kẻ tấn công có login SQL thật của SCADA, dùng được với đủ quyền của login đó, không chỉ giới hạn trong câu OPENQUERY cố định của app.
- **Sửa** (ngắn): trong `update_factory`, nếu `host`, `port` hoặc `username` khác `before` mà không có `password` mới → `ValueError("Đổi máy chủ/cổng/tài khoản phải nhập lại mật khẩu.")` (400). Ở FE, form hiện gợi ý tương ứng. Kèm theo khi triển khai: login SQL của SCADA chỉ có quyền tối thiểu (CONNECT + ánh xạ linked server tới user Historian chỉ-đọc, không `sysadmin`, không đọc DB khác).

### H2. Kết nối TDS không ép mã hoá, trong khi kế hoạch có phương án "IP public/NAT 1433"
- **Chỗ**: `apps/api/app/services/scada_client.py:115-118` (`pymssql.connect` không truyền `encryption`, dù pymssql 2.4.2 / FreeTDS 1.5.19 có tham số này); `plans/260930-nha-may-thong-minh-scada/plan.md:37`.
- **Khai thác**: nếu đi đường NAT 1433 ra internet: (a) bên đứng giữa đường truyền (ISP, mạng trung chuyển) đọc được gói login (mật khẩu chỉ bị XOR) và toàn bộ dữ liệu, hoặc chủ động hạ cấp khi mã hoá chỉ ở mức "request"; (b) SQL Server của SCADA (thiết bị OT) lộ ra internet → bị dò mật khẩu hàng loạt (login SQL không tự khoá nếu tắt `CHECK_POLICY`).
- **Sửa**: truyền `encryption="require"` vào `pymssql.connect`. Ghi rõ vào plan/tài liệu triển khai: **chỉ đi qua VPN site-to-site**, không mở 1433 ra internet. Nếu buộc phải NAT thì chặn tường lửa chỉ cho đúng IP egress của server VRG.

## Medium

### M1. Người dùng thường (không phải admin) thấy chi tiết hạ tầng trong lỗi 502
- **Chỗ**: `apps/api/app/routers/smart_factory.py:62-65` trả `str(ScadaError)` nguyên văn; nội dung dựng ở `apps/api/app/services/scada_client.py:73-92`: `host:port` (`:73,:81`), tài khoản SQL (`:79`), tên database (`:77`), linked server (`:84`), cộng `raw[:400]` gồm thông điệp FreeTDS (có IP), "Login failed for user '…'" và thông điệp OLE DB của linked server.
- **Khai thác**: bất kỳ ai có cap `smart_factory` (Lãnh đạo Tập đoàn, editor được cấp) nhận được IP/cổng nội bộ và login SQL của SCADA. Nếu một tài khoản editor bị lộ, kẻ tấn công có ngay một nửa thông tin đăng nhập, cộng thêm H2 là đủ để dò mật khẩu. Phụ: che bằng `raw.replace(password, "***")` (`:69-71`) tạo ra kênh đoán mật khẩu yếu. Ví dụ mật khẩu `able` biến "Unable" thành "Un***" → nhìn là đoán ra.
- **Sửa**: `ScadaError` mang 2 phần (câu ngắn và chi tiết). `_report` chỉ trả câu ngắn cho người không phải admin, ví dụ "Không đọc được số từ SCADA của nhà máy — đã báo quản trị", còn chi tiết thì `logger.warning("[scada] factory=%s: %s", id, detail)`. Hiện lỗi 502 **không được ghi log phía server**, nên cần bổ sung dù có sửa phần trên hay không. Admin (và `/test`) vẫn thấy đủ chi tiết.

### M2. Không giới hạn đồng thời/không cache → treo cả API, dồn tải lên Historian
- **Chỗ**: `apps/api/app/routers/smart_factory.py:53-88` (`def` đồng bộ, mỗi lần gọi mở kết nối mới); `scada_client.py:118` (`login_timeout=10`, `timeout=60`) × 2 câu (`:154-156`) → một request giữ thread tới ~130 s. API chạy **1 worker uvicorn** (`Dockerfile:61`), threadpool AnyIO mặc định 40 luồng, dùng chung với ~370 endpoint `def` (kể cả `login`). FE bắn request mới mỗi lần đổi kỳ/nhà máy và không huỷ request cũ (`FactoryMetersPage.tsx:95-106`). Xuất `.xlsx` truy vấn lại SCADA từ đầu (`:79-82`).
- **Khai thác**: một tài khoản có cap (hoặc script dùng token của tài khoản đó) gửi khoảng 40 request `/meters/daily` song song với kỳ 92 ngày, nhằm lúc SCADA/VPN chậm. Kết quả: toàn bộ app (đăng nhập, mọi màn) treo khoảng 2 phút và lặp lại được. Đồng thời mỗi request đè một lượt truy xuất Historian 92 ngày lên hệ thống OT đang chạy thật của nhà máy.
- **Sửa**: (1) `threading.BoundedSemaphore` theo nhà máy (vd 2) và một semaphore chung (vd 4), dùng `acquire(timeout=0)`; không lấy được thì trả 429 "Đang đọc SCADA, thử lại sau giây lát". (2) Cache TTL ngắn khoảng 60 s theo khoá `(factory_id, d0, d1)`; kỳ đã qua hết có thể giữ lâu hơn. `.xlsx` dùng lại cache. (3) Hạ `timeout` truy vấn xuống khoảng 30 s (dưới ngưỡng 100 s của Cloudflare).

## Low

### L1. Admin khai host tuỳ ý → quét cổng mạng nội bộ từ container API
- **Chỗ**: `scada_factory_repo.py:100` (`host` chỉ cấm khoảng trắng); kích hoạt qua `/test`.
- **Khai thác**: admin (hoặc JWT admin bị lộ) khai `host` là `db`, `127.0.0.1`, IP trong mạng Docker/Dokploy, hoặc `169.254.169.254`, rồi bấm Kiểm tra. Kiểu lỗi trả về khác nhau (connection refused, timeout, lỗi giao thức) → vẽ được sơ đồ dịch vụ nội bộ. Chỉ admin làm được nên rủi ro thấp.
- **Sửa** (tuỳ chọn, KISS): biến môi trường `SCADA_ALLOWED_NETS` (CIDR của VPN nhà máy). Khi có biến này thì resolve host rồi kiểm IP nằm trong danh sách, và chặn loopback/link-local.

### L2. Mật khẩu SCADA lưu dạng rõ trong Postgres, và quy trình clone DB prod về máy dev kéo theo nó
- **Chỗ**: `apps/api/app/core/db.py:549`. Cùng mức lưu với secret của `app_config`, nhưng đây là thông tin đăng nhập vào **hạ tầng OT**. Quy trình "clone prod DB → local" copy toàn bộ bảng, nên mật khẩu này nằm trên laptop dev và trong các bản backup.
- **Sửa**: tối thiểu thì thêm bước sau clone: `UPDATE scada_factory SET password='x', enabled=false`. Tốt hơn: mã hoá cột bằng khoá lấy từ env (Fernet), lúc đọc ra để kết nối mới giải mã.

---

## Đã kiểm — KHÔNG có vấn đề
- **SQL injection**: tag bị ràng bằng `TAG_RE` (không có `'`, `]`, khoảng trắng) và luôn nằm trong `[...]`. Linked server phải khớp `IDENT_RE` (`[A-Za-z0-9_]`). Kiểm cả **lúc lưu** (`repo.clean`) lẫn **lúc dựng câu** (`_wrap`). Ngày giờ do `strftime` sinh từ `datetime` (gốc là `date.fromisoformat`); `wwResolution` là `int` hằng. Database/host/username đi qua tham số của `pymssql.connect`, không ghép vào chuỗi SQL. Tên nhà máy không bao giờ vào SQL.
- **Excel**: tên nhà máy chỉ nằm trong ô tiêu đề và bắt đầu bằng chữ cố định "CHỈ SỐ…" → không bị hiểu thành công thức; các ô còn lại là số hoặc nhãn cố định. **Content-Disposition**: tên file qua `_slug` (chỉ `a-z0-9-`) và ngày ISO → không chèn header được.
- **XSS**: FE render toàn bộ bằng text React (tên, tag, `detail`, `server_version`); không có `dangerouslySetInnerHTML`.
- **Mật khẩu ra API/log/audit**: `public_view` chỉ trả `password_set`. `build_report` chỉ trả `{id, name}`. Audit dùng `_AUDIT_FIELDS` (không có password) cộng cờ `password_changed`. `check_connection` log tên lớp lỗi, không log thông điệp. Handler 500 toàn cục không trả traceback. Traceback cũng không chứa biến cục bộ. FreeTDS và server không lặp mật khẩu trong thông điệp. **PUT giữ mật khẩu cũ đúng**: `None`/`""` → không có khoá `password` → câu `SET` không có cột này.
- **Phân quyền**: `/api/smart-factory/*` gác bằng `require_cap("smart_factory")`, `/admin/*` gác bằng `require_admin`; hai prefix không đè nhau. `member`/`leader`/`viewer` → `effective_caps` rỗng → 403. `executive` → mức Xem, chỉ gọi GET, đúng ý đồ. POST `/test` của executive bị cả guard lẫn `require_admin` chặn. FE: route chỉ số nằm trong `RequireCap`, route cấu hình nằm trong `RequireRole admin`, menu gác đúng như vậy. Test đã phủ 401/403 cho người không có cap và người không phải admin.

## Việc nên làm (theo thứ tự)
1. H1: bắt nhập lại mật khẩu khi đổi host/port/username (1 điều kiện trong `update_factory` + 1 test).
2. H2: thêm `encryption="require"`; chốt trong plan là **VPN, không NAT 1433 public**; dùng login SQL quyền tối thiểu.
3. M1: người không phải admin chỉ nhận câu ngắn; ghi log chi tiết lỗi 502.
4. M2: semaphore theo nhà máy + semaphore chung → 429; cache 60 s; hạ timeout.
5. L2 → L1 khi có thời gian.

## Câu hỏi còn treo
- Đường mạng tới SCADA đã chốt VPN hay NAT? Kết luận này quyết định H2 là High hay chỉ là hardening.
- Login SQL mà nhà máy cấp có quyền gì (chỉ đọc qua linked server hay rộng hơn)? Quyền càng rộng thì H1 càng nặng.
- Có cần giới hạn người xem theo nhà máy không? Hiện mọi người có cap xem được mọi nhà máy; nếu đúng chủ ý mức Tập đoàn thì giữ nguyên.
