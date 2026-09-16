# Lịch sử truy cập (access log)

> Yêu cầu chủ dự án 16/09/2026: admin muốn biết **tài khoản lãnh đạo đơn vị dùng hệ thống ra sao —
> đăng nhập lúc nào, vào những trang nào**. Nhật ký hoạt động hiện có chỉ ghi **thay đổi số liệu**,
> mà vai trò `leader` chỉ-xem nên gần như không để lại dòng nào.

## Phạm vi (đã chốt: cả gói)
1. Ghi **đăng nhập** (thành công + thất bại) — `auth.login`.
2. Ghi **lượt vào trang** — web bắn 1 lời báo mỗi lần đổi route; server ánh xạ đường dẫn → **tên
   trang tiếng Việt** (không tin nhãn do client gửi).
3. Màn **Lịch sử truy cập** (`/quan-tri/truy-cap`, quyền `audit`): tab *Theo tài khoản* (đăng nhập
   gần nhất · số lần đăng nhập · số lượt xem · trang hay vào) + tab *Chi tiết* + xuất Excel.

KHÔNG làm: ghi mọi lời gọi API (log rác gấp ~5 lần), ghi tham số bộ lọc/nội dung đang xem.

## Thiết kế
- Bảng riêng `access_log` (append-only), **không** dùng chung `audit_log` để nhật ký thay đổi số
  liệu không bị loãng. Cột: `at · username · role · on_behalf · event · path · label · company · ip · user_agent`.
- `event`: `login` · `login_failed` · `page`.
- Chống rác: cùng người + cùng đường dẫn trong 30 giây → không ghi thêm (React render lại, F5).
- Đường dẫn động (`/ho-tro/123`) chuẩn hoá về `/ho-tro/:id` để gom nhóm.
- Lưu 400 ngày; dọn nền khi khởi động API.
- Beacon dùng `fetch(keepalive)` **không** qua `apiFetch`: lỗi beacon không được đăng xuất người
  dùng (apiFetch gặp 401 sẽ đá về /login) và không phát `DATA_SAVED_EVENT`.

## File
**Backend** — `core/db.py` (DDL) · `core/access_meta.py` (bảng đường dẫn→tên trang) ·
`services/access_repo.py` · `services/access_stats.py` · `services/access_export.py` ·
`routers/access_log.py` · `routers/auth.py` (móc đăng nhập) · `main.py` (đăng ký + dọn cũ).
**Web** — `lib/access-log-client.ts` · `features/command-center/use-access-beacon.ts` ·
`pages/AccessLogPage.tsx` + 2 section · `App.tsx` · `sidebar-menu-builders.tsx`.
**Test** — `tests/test_access_log.py` (+ dọn rác ở `conftest.py`).

## Lưu ý vận hành
- **Không hồi tố**: chỉ có dữ liệu kể từ ngày deploy.
- Nên báo trước cho lãnh đạo đơn vị rằng hệ thống có ghi vết truy cập.
- Hậu-deploy: tài khoản không phải admin muốn xem thì cấp quyền `audit`.

---

## Kết quả review (16/09/2026) — đã xử lý

| Phát hiện | Xử lý |
|---|---|
| 🔴 **Excel formula injection**: tên tài khoản ở lần ĐĂNG NHẬP SAI là chuỗi người ngoài nhập được (không cần mật khẩu đúng), lọt thẳng vào ô Excel quản trị mở | Thêm `services/xlsx_text.py::safe_cell` (chuẩn OWASP: thêm nháy đơn đầu ô) và áp cho **cả** `access_export` lẫn `audit_export` — bản tin nhật ký cũ cũng có lỗ này |
| 🟡 Beacon nhận `path` tuỳ ý → bơm rác | Chặn ở cửa: `PageView.path` chỉ nhận ký tự của đường dẫn thật (`^/[A-Za-z0-9\-_/.:%~]*$`) |
| 🟡 Chống trùng 30s là "hỏi trước, ghi sau" → 2 request đồng thời cùng lọt | Gộp thành MỘT lệnh `INSERT … WHERE NOT EXISTS`; đã thử bắn 3 request song song → đúng 1 dòng |
| 🟡 Gọi API kép do AntD giữ cả 2 tab trong DOM | Chỉ dựng bảng của tab đang mở |
| 🟡 Bảng chi tiết: đổi bộ lọc lúc đang ở trang > 1 sinh 1 lượt gọi thừa (có thể đè nhầm) | Đưa `page` lên màn cha, đổi bộ lọc là về trang 1 trong cùng một lần cập nhật state |

**Cố ý CHƯA làm** (ghi lại để khỏi tranh luận lại):
- *Giới hạn tần suất beacon theo phút*: người gọi phải đăng nhập rồi, lại lộ mặt ngay trong chính
  nhật ký này; thêm bộ đếm trong tiến trình là phức tạp không tương xứng. Chặn ký tự đường dẫn đã
  cắt phần lớn khả năng bơm rác.
- *Ép mặc định khoảng ngày khi gọi API không lọc*: ước lượng ~300 dòng/ngày × 400 ngày ≈ 120k dòng —
  Postgres gom nhóm mức này vẫn nhanh; giao diện luôn gửi sẵn 30 ngày. Nếu sau này bảng phình thì
  thêm mặc định 90 ngày ở `Filters`.

---

## Bổ sung theo yêu cầu chủ dự án (16/09/2026, sau khi xem bản đầu)

Câu hỏi: *"xem lịch sử của một user chỉ định thì làm sao?"* → lọc ở ô **Tài khoản**. Nhưng ô đó
trước chỉ liệt kê người ĐÃ có vết, nên **tài khoản chưa vào lần nào thì không chọn được**, mà đó lại
đúng là thứ cần biết. Đã sửa:
- `access_repo.known_users()` liệt kê **mọi tài khoản còn dùng được** (`app_user`) + tài khoản đã xoá
  nhưng từng đăng nhập **thành công**. Cố ý KHÔNG lấy tên gõ ở các lần đăng nhập hỏng (ai cũng gõ
  được chuỗi bất kỳ vào ô đăng nhập).
- `access_stats.summary()` ghép thêm dòng cho tài khoản chưa truy cập (mọi số 0), lọc theo đúng
  vai trò/đơn vị/tài khoản đang chọn; tài khoản **đã khoá** thì không liệt kê.
- Web: nhãn đỏ **"Chưa truy cập lần nào"** dưới tên tài khoản; bảng tổng hợp thêm phân trang 25 dòng
  (danh sách nay dài hơn hẳn).
