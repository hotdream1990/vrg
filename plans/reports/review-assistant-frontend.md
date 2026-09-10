# Review — Frontend "Trợ lý AI mở rộng" (trước khi deploy)

Ngày: 2026-09-10 · Phạm vi: 6 file frontend (AssistantPage, AssistantHistoryPage, assistant-client,
assistant-history-client, App.tsx, AdminLayout.tsx) đối chiếu `apps/api/app/routers/assistant.py`,
`assistant_history.py`, `assistant_log_repo.py`, `assistant_service.py`.

Build: `pnpm build` (tsc + vite) → **PASS**, không lỗi biên dịch.

## Kết luận: CÓ THỂ DEPLOY

Không phát hiện lỗi CHẶN DEPLOY. `session_id` được sinh và gửi đúng, phân quyền admin/thường đúng ở
cả 2 lớp (route cap + isAdmin trong UI), backend contract khớp gần như hoàn toàn. Có vài điểm 🟡 nên
dọn (chủ yếu code chết + 2 file vượt chuẩn 200 dòng) nhưng không ảnh hưởng chức năng lúc deploy.

---

## 🟡 NÊN SỬA

### 1. `assistant-history-client.ts:53-59, 68, 75, 82, 96-97` — nhánh dự phòng hợp đồng CŨ, nay là code chết
Comment tại dòng 53-56 tự nhận: *"Backend hiện trả một số trường KHÁC tên so với hợp đồng API ban đầu…
Bỏ nhánh dự phòng khi backend đã chốt hẳn một dạng."* — backend ĐÃ chốt (xác nhận bằng
`assistant_log_repo.py` + `assistant_history.py` + `test_assistant_history.py`), nhánh cũ giờ chết:

- `type RawSession = HistorySession & { first_question?: string }` (dòng 57) và
  `r.title || r.first_question || ""` (dòng 68) — backend LUÔN trả `title`
  (`assistant_log_repo.py:143`: `"title": r["first_question"]` đã map sẵn ở server), `first_question`
  không bao giờ xuất hiện trong response thật.
- `type RawTurns = { items?: HistoryTurn[]; turns?: HistoryTurn[] }` (dòng 58) và
  `res.items ?? res.turns ?? []` (dòng 75) — `GET /{session_id}` LUÔN trả `{session_id, items}`
  (`assistant_history.py:83`), field `turns` không tồn tại ở endpoint này (tên `turns` chỉ dùng ở
  field khác, trong `HistorySession.turns: number`).
- `type RawStats = Partial<HistoryStats> & { total_turns?: number; total_sessions?: number }` (dòng
  59) và `res.turns ?? res.total_turns ?? 0` / `res.sessions ?? res.total_sessions ?? 0` (dòng 96-97)
  — `GET /stats` LUÔN trả `{turns, sessions, oldest}` (`assistant_log_repo.py:196-199`),
  `total_turns`/`total_sessions` không tồn tại.

Vi phạm YAGNI/DRY (rule `development-rules.md`) — thêm 3 type + 4 chỗ `??` chỉ để đỡ một hợp đồng
không còn tồn tại. Không hỏng chức năng (nhánh chính luôn trúng) nhưng nên dọn theo đúng lời nhắc
trong chính comment của tác giả. Sửa: bỏ `Raw*` types, đọc thẳng field theo `HistorySession`/
`HistoryTurn`/`HistoryStats`, không cần fallback.

`deleteSession` (dòng 79-83) cũng dự phòng backend không trả `deleted` (`typeof res.deleted ===
"number" ? ... : null`) — backend LUÔN trả `{"deleted": <int>}` (kể cả 0), fallback `null` không bao
giờ chạy nhưng vô hại hơn 3 chỗ trên (không đổi tên field, chỉ đổi kiểu) — có thể giữ hoặc dọn cùng
đợt cho nhất quán.

### 2. `AssistantHistoryPage.tsx:35-36, 66` — `adviceColor`/nhãn tư vấn sai miền giá trị
```
const ADVICE_COLOR: Record<string, string> = { raise: "green", hold: "blue", lower: "red" };
```
Giá trị THẬT của `turn.advice` là 1 trong 3 chuỗi `"data" | "model" | "adjusted"` (mức tư vấn — xem
`ChatRequest.advice` ở `schemas/assistant.py:20` và cách lưu ở `assistant_service.py:178,217`), KHÔNG
phải hướng khuyến nghị "raise/hold/lower". Map `ADVICE_COLOR` nhầm miền giá trị này với miền khác
(hướng điều chỉnh giá sàn ở tính năng "Gợi ý giá sàn") → 3 khoá không bao giờ khớp, mọi Tag luôn rơi
vào mặc định `"purple"`. Đồng thời dòng 66 hiển thị thẳng chuỗi enum tiếng Anh
`Mức tư vấn: {turn.advice}` (vd "Mức tư vấn: model") thay vì nhãn tiếng Việt đã có sẵn ở
`AssistantPage.tsx` (`ADVICE_OPTIONS`: "Chỉ tra số"/"Theo mô hình"/"Có điều chỉnh") — vi phạm quy ước
dự án (giao tiếp tiếng Việt, xem AGENTS.md §5). Không chặn deploy (chỉ sai màu/nhãn hiển thị trong
trang lịch sử) nhưng nên map lại theo đúng 3 giá trị thật + nhãn Việt hoá, tái dùng
`ADVICE_OPTIONS` từ `AssistantPage.tsx` (tránh định nghĩa nhãn 2 nơi — DRY).

### 3. File vượt chuẩn 200 dòng của dự án (AGENTS.md §5: "file code < 200 dòng")
- `AssistantPage.tsx` — 442 dòng (gấp hơn 2 lần chuẩn).
- `AssistantHistoryPage.tsx` — 321 dòng.

Cả hai đọc vẫn mạch lạc (đã tách hàm con `SkillPackChips`, `AssistantControls`, `TurnCard`, `TagRow`
ngay trong file), nhưng đang vi phạm giới hạn kích thước file của dự án. Gợi ý tách khi có dịp:
- `AssistantPage.tsx`: đưa `SCOPE_OPTIONS`/`ADVICE_OPTIONS`/`packsForScope`/`buildSuggestions`/
  `SkillPackChips`/`AssistantControls` sang 1-2 file con (vd `assistant-controls.tsx`,
  `assistant-suggestions.ts`), `AssistantPage.tsx` chỉ giữ state + layout chat.
- `AssistantHistoryPage.tsx`: đưa `TurnCard`/`TagRow`/`stamp`/`adviceColor` sang
  `assistant-history-turn-card.tsx`.

Không chặn deploy — ghi nhận nợ kỹ thuật.

### 4. `HistoryTurn.advice`/`HistoryTurn.packs` khai kiểu rộng hơn thực tế backend trả
`assistant-history-client.ts:26-27`: `advice: string | null`, `packs: string[] | null`. Backend
(`assistant_log_repo.py:89-90`: `r["advice"] or ""`, `r["packs"] or []`) KHÔNG BAO GIỜ trả `null` —
luôn là chuỗi rỗng / mảng rỗng. Không gây lỗi runtime (code dùng đều là `turn.advice &&` hoặc
`turn.packs ?? []`, xử lý đúng cả 2 trường hợp) nhưng kiểu khai sai làm người đọc tưởng cần xử lý
`null` ở nơi khác. Sửa: bỏ `| null`.

---

## 🟢 GÓP Ý (đã làm tốt, ghi nhận)

- **`session_id`** (`AssistantPage.tsx:319-323`) — sinh 1 lần bằng `crypto.randomUUID()` (có fallback
  cho môi trường không có `crypto.randomUUID`), giữ ổn định suốt phiên chat qua `useRef`, gửi đúng ở
  `sendChat(history, selected, advice, sessionId.current)` (dòng 365) và forward xuống body
  `{ ...(sessionId ? { session_id: sessionId } : {}) }` (`assistant-client.ts:58`) — khớp
  `ChatRequest.session_id` và điều kiện ghi log ở `assistant_service.py:154` (`_log_turn` chỉ bỏ qua
  khi thiếu `session_id`/`username`). Đây đúng là điểm task lo ngại nhất ("lịch sử sẽ trống nếu
  không gửi session_id") — đã làm đúng, không phải sửa.
- **Phân quyền UI** — `loadStats`/`listUsers` chỉ gọi khi `isAdmin` (`AssistantHistoryPage.tsx:120-130`)
  nên `/api/assistant/history/stats` (403 với non-admin, `assistant_history.py:70-71`) không bao giờ
  bị gọi từ tài khoản thường → không có banner lỗi đỏ xuất hiện oan. Cột "Người hỏi", nút xoá dòng,
  nút xoá trong Drawer, khu "Xoá log cũ hơn…" đều gate bằng `isAdmin` (dòng 175-195, 253-261, 280-292).
  Route `/tro-ly-ai/lich-su` gác cùng cap `assistant` như `/tro-ly-ai` (`App.tsx` diff).
- **`fetchPacks` lỗi không chặn chat** — `AssistantPage.tsx:327-333` nuốt lỗi bằng `.catch(() => {})`,
  `SkillPackChips` trả `null` khi `packs.length === 0` → khung chat + gửi câu hỏi vẫn hoạt động, đúng
  yêu cầu.
- **Trạng thái rỗng** — bảng phiên: `emptyText: "Chưa có phiên hỏi đáp nào khớp bộ lọc."`; Drawer:
  `<Empty description="…">`; `dmy(null)` trả `"—"` (không crash khi `stats.oldest` là `null` lúc DB
  chưa có log nào) — đều tử tế.
- **Bố cục chat** — `height: "calc(100vh - 150px)"` (dòng 376) + `flex:1, minHeight:0, overflowY:"auto"`
  (dòng 393) đúng pattern đã thống nhất cho khung cuộn trong Sider cố định (tránh bug sidebar kéo giãn
  từng gặp).
- **Phân trang server-side** — `AssistantHistoryPage.tsx` dùng `limit`/`offset` + `total` từ server
  (`fetchSessions`), Table `pagination.total = data.total`, không tải hết rồi lọc client. Đổi bất kỳ
  filter nào đều `resetToFirstPage()` — không rơi vào trang rỗng.
- **Icon** — toàn bộ dùng `@ant-design/icons` (`HistoryOutlined`, `DeleteOutlined`, `ToolOutlined`,
  `DatabaseOutlined`…), không thấy emoji.
- **Immutability** — `[...items].sort(...)` (dòng 142, không mutate mảng gốc từ API), spread khi cập
  nhật state (`setMsgs((m) => [...m, ...])`, `setOffPacks(next)` dựng mảng mới).
- **Không magic number** — `PAGE_SIZE`, `PURGE_DEFAULT_DAYS`, `MS_PER_SECOND`, `HISTORY_TURNS`,
  `MAX_SUGGESTIONS` đều đặt tên hằng số rõ ràng.
- **Thứ tự route menu** — `AdminLayout.tsx` đặt `/tro-ly-ai/lich-su` TRƯỚC `/tro-ly-ai` trong
  `ROUTE_KEYS` (đúng bẫy tiền tố đã ghi chú sẵn cho `/hop-dong/*`), tránh menu tô sai mục khi ở trang
  lịch sử.
- **Backend contract đối chiếu 1-1**: `GET /packs` ↔ `SkillPack` type, `POST /chat` body
  `{messages, packs?, advice?, session_id?}` ↔ `ChatRequest`, `GET /history` ↔
  `{items, total, limit, offset}`, `GET /history/{id}` ↔ `{session_id, items}`,
  `DELETE /history/{id}` và `DELETE /history?before=` ↔ `{deleted}`, `GET /history/stats` ↔
  `{turns, sessions, oldest}` — tất cả khớp, kể cả 403 cho `stats` (verify qua
  `apps/api/tests/test_assistant_history.py`).
- Import biến `assistant_tools` từ package mới (`apps/api/app/services/assistant_tools/`, thay file
  đơn cũ đã xoá) build/import Python thành công (`uv run python -c "from app.routers import
  assistant, assistant_history"` → OK), không có import vỡ lây sang service khác.

---

## Không phát hiện

- Không thấy lỗ hổng XSS (render text qua JSX, không `dangerouslySetInnerHTML`).
- Không thấy gọi API lộ thông tin chéo người dùng (backend tự ép `username=caller` khi không phải
  admin, kể cả khi client cố truyền `username` khác — trả 403 rõ ràng).
- Không thấy hardcode secret/token.
- `pnpm build` sạch, không cảnh báo TypeScript.

---

## Câu hỏi còn treo
- Không có — mọi điểm nghi vấn trong yêu cầu review đã đối chiếu được trực tiếp với code backend hiện
  hành (không cần hỏi thêm ai).
