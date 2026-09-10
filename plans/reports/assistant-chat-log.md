# Báo cáo: Lịch sử hỏi–đáp Trợ lý AI (assistant_chat_log)

Ngày: 2026-09-10 · Nhánh: `feature/master-contract` · Phạm vi: `apps/api`

## 1. File đã tạo/sửa (đúng phạm vi được giao)

- TẠO `app/services/assistant_log_repo.py` (200 dòng)
- TẠO `app/routers/assistant_history.py` (101 dòng)
- SỬA `app/main.py` — chỉ thêm import `assistant_history` + 1 dòng `include_router`
- TẠO `tests/test_assistant_history.py` (150 dòng)
- KHÔNG tạo `app/schemas/assistant_history.py` — mọi endpoint dùng Query param + trả dict thô
  (đúng phong cách `app/routers/audit.py`), không cần Pydantic model riêng. YAGNI.
- KHÔNG đụng `app/routers/assistant.py`, `app/services/assistant_service.py`,
  `app/schemas/assistant.py`, `app/services/assistant_tools/`.

## 2. Phát hiện quan trọng: người khác ĐÃ wiring sẵn `log_turn`

Trong lúc làm việc, `assistant_service.py` / `assistant.py` / `schemas/assistant.py` đã được
đồng nghiệp khác cập nhật (thêm `advice` mode + `session_id`). Họ đã tự thêm sẵn helper
`_log_turn()` trong `assistant_service.py` gọi đúng:

```python
from app.services import assistant_log_repo  # nạp muộn trong _log_turn()

assistant_log_repo.log_turn(
    session_id=session_id, username=username, question=question, answer=answer,
    tools=tools, sources=sources, packs=packs, advice=advice, model=model,
    latency_ms=int((time.time() - started) * 1000))
```

Chữ ký khớp 100% với hợp đồng được giao (`log_turn(session_id, username, question, answer,
tools, sources, packs, advice, model, latency_ms)`), gọi ở cả 2 điểm return của `chat()`
(trả lời bình thường + fallback "quá nhiều bước"), và đã tự nuốt exception + log warning ở
tầng gọi (đúng tinh thần "log hỏng không chặn câu trả lời" — phòng thủ 2 lớp cùng tầng repo).
**Không cần sửa gì thêm ở phía họ** — chỉ cần `assistant_log_repo.py` tồn tại đúng chữ ký là chạy.

## 3. Thiết kế bảng `assistant_chat_log`

Bảng KHÔNG khai trong `app/core/db.py` (file đó có người khác sửa song song) — tự
`CREATE TABLE IF NOT EXISTS` độc lập, idempotent, ngay trong `assistant_log_repo.py`
(hàm nội bộ `_ensure_schema()`, cờ `_ready` cache trong process, gọi trước mỗi thao tác DB).

```
assistant_chat_log
  id          bigint IDENTITY PK
  session_id  text NOT NULL
  username    text NOT NULL
  created_at  timestamptz NOT NULL DEFAULT now()
  question    text NOT NULL DEFAULT ''
  answer      text NOT NULL DEFAULT ''
  tools       jsonb NOT NULL DEFAULT '[]'   -- tên tool đã gọi
  sources     jsonb NOT NULL DEFAULT '[]'
  packs       jsonb NOT NULL DEFAULT '[]'
  advice      text NOT NULL DEFAULT ''      -- mức tư vấn: data|model|adjusted
  model       text NOT NULL DEFAULT ''
  latency_ms  integer NOT NULL DEFAULT 0

Index: (username, created_at DESC), (session_id)
```

**KHÔNG lưu `artifacts`** (bảng/biểu đồ) — comment giải thích ngay trong code: đây là phần
nặng nhất mỗi lượt và luôn tính lại được từ đúng tool đã gọi (số liệu gốc không đổi).

Kiểm chứng trên DB local (`vrg-caosu-db-1`, `psql -U vrg -d vrg_caosu`):

```
                              Table "public.assistant_chat_log"
   Column   |           Type           | Collation | Nullable |           Default
------------+--------------------------+-----------+----------+------------------------------
 id         | bigint                   |           | not null | generated always as identity
 session_id | text                     |           | not null |
 username   | text                     |           | not null |
 created_at | timestamp with time zone |           | not null | now()
 question   | text                     |           | not null | ''::text
 answer     | text                     |           | not null | ''::text
 tools      | jsonb                    |           | not null | '[]'::jsonb
 sources    | jsonb                    |           | not null | '[]'::jsonb
 packs      | jsonb                    |           | not null | '[]'::jsonb
 advice     | text                     |           | not null | ''::text
 model      | text                     |           | not null | ''::text
 latency_ms | integer                  |           | not null | 0
Indexes:
    "assistant_chat_log_pkey" PRIMARY KEY, btree (id)
    "ix_assistant_chat_log_session" btree (session_id)
    "ix_assistant_chat_log_user" btree (username, created_at DESC)
```

## 4. API — `app/routers/assistant_history.py` (prefix `/api/assistant/history`)

Router-level gate ở `main.py`: `dependencies=[Depends(require_cap("assistant"))]` — giống hệt
cách `assistant.router` đang được gác, đăng ký ngay sau dòng include của nó.

| Method | Path | Quyền | Ghi chú |
|---|---|---|---|
| GET | `` | cap `assistant` (Xem) | Danh sách PHIÊN, phân trang server (`limit` mặc định 20, `offset`), lọc `date_from/date_to/q` cho mọi người; `username` filter CHỈ admin dùng được — non-admin gửi `username` khác chính mình → 403; non-admin bị ép `username = chính họ` (server tự set, không tin client) |
| GET | `/stats` | **chỉ admin** | Tổng số lượt/phiên + dòng cũ nhất — số liệu toàn hệ thống nên không cho tài khoản thường xem |
| GET | `/{session_id}` | cap `assistant` (Xem) | Toàn bộ lượt 1 phiên, cũ→mới; chủ phiên hoặc admin mới xem được (403 nếu không phải; 404 nếu phiên không tồn tại) |
| DELETE | `` (query `before=YYYY-MM-DD`) | **chỉ admin** | Xoá log CŨ HƠN ngày `before`, trả `{"deleted": N}` — cơ chế dọn cho DB không phình |
| DELETE | `/{session_id}` | **chỉ admin** | Xoá 1 phiên, 404 nếu không tồn tại |

Lưu ý kỹ thuật: `/stats` khai báo TRƯỚC `/{session_id}` trong file để tránh FastAPI khớp
"stats" vào path param `session_id` (đã bình luận rõ trong code).

## 5. Output test — `uv run pytest tests/test_assistant_history.py -q`

```
.....                                                                    [100%]
5 passed, 1 warning in 2.63s
```

5 test bao phủ:
- `test_log_turn_then_read_back` — ghi qua `log_turn()` → đọc lại đúng nội dung qua GET
  `/{session_id}` + xuất hiện trong danh sách phiên (lọc `q`).
- `test_regular_user_cannot_see_others_log` — user thường chỉ thấy log của mình; lọc
  `username` người khác → 403; xem thẳng `session_id` người khác → 403; admin xem được cả hai +
  lọc `username` hoạt động.
- `test_regular_user_cannot_delete` — user thường xoá phiên của CHÍNH MÌNH vẫn 403; xoá theo
  `before` cũng 403.
- `test_admin_delete_before_date_returns_count` — admin xoá theo `before` trả đúng số dòng đã
  xoá, tổng còn lại về 0.
- `test_pagination_limits_items` — `limit=2` trả đúng 2 item dù có ≥3 phiên khớp bộ lọc.

## 6. Toàn bộ test suite — `uv run pytest tests/ -q`

```
FAILED tests/test_sales_contract.py::test_customer_is_per_unit_and_unique
FAILED tests/test_sales_contract.py::test_customer_search_runs_on_server
FAILED tests/test_sales_contract.py::test_search_ignores_vietnamese_marks
3 failed, 373 passed, 5 skipped, 1 warning in 181.55s
```

3 fail **KHÔNG liên quan** tới việc của tôi: đều ở `test_sales_contract.py` (tìm khách hàng bỏ
dấu tiếng Việt), file tôi không đụng tới; lỗi kiểu test-pollution (search ra dư id
233/414/595 ngoài id mong đợi — dữ liệu khách hàng "Đồng Nai" trùng tên do dữ liệu tồn từ lần
chạy test khác trên DB dev dùng chung, khớp với "3 bẫy đếm-trùng" đã ghi nhận ở tính năng Hợp
đồng bán đang làm song song). Test của tôi (`test_assistant_history.py`) PASS 100%, không góp
phần vào 3 fail này.

## 7. Ruff

```
$ uv run ruff check app/services/assistant_log_repo.py app/routers/assistant_history.py \
    tests/test_assistant_history.py app/main.py
All checks passed!
```

## 8. Việc CÒN LẠI cho người khác (không tự sửa vì ngoài phạm vi được giao)

- Không cần thêm gì ở `assistant_service.py`/`assistant.py`/`schemas/assistant.py` — đã tự
  wiring đúng hợp đồng (xem mục 2).
- Frontend (`apps/web`) chưa có màn xem lịch sử — cần thêm trang gọi 4 endpoint trên (ngoài
  phạm vi backend của việc này).
- Hậu-deploy: không cần cấp cap mới (dùng chung cap `assistant` đã có).
