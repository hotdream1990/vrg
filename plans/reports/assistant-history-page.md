# Trang "Lịch sử hỏi đáp" — Trợ lý AI (frontend)

Ngày: 10/09/2026 · Phạm vi: `apps/web` (React + TS + Ant Design)

## 1. File đã tạo / sửa

| File | Việc |
|---|---|
| `apps/web/src/lib/assistant-history-client.ts` | **TẠO** — client API `/api/assistant/history` (danh sách phiên · chi tiết phiên · xoá phiên · dọn log · thống kê) |
| `apps/web/src/features/command-center/pages/AssistantHistoryPage.tsx` | **TẠO** — màn hình (bảng phiên + bộ lọc + ngăn chi tiết + khu dọn log) |
| `apps/web/src/App.tsx` | **SỬA** — thêm import + route `/tro-ly-ai/lich-su` trong khối `RequireCap caps={["assistant"]}` |
| `apps/web/src/features/command-center/AdminLayout.tsx` | **SỬA** — thêm mục menu "Lịch sử hỏi đáp" ngay dưới "Trợ lý AI" (+ icon `HistoryOutlined`, + khoá `/tro-ly-ai/lich-su` vào `ROUTE_KEYS`) |

Không đụng `AssistantPage.tsx` và `assistant-client.ts`.

## 2. Giao diện

**Đầu trang** — tiêu đề "Lịch sử hỏi đáp — Trợ lý AI" + mô tả ngắn.

**Thẻ bộ lọc**: `DatePicker.RangePicker` (DD/MM/YYYY, cho phép để trống 1 đầu) · `Input.Search`
tìm theo câu hỏi (xoá trắng ô = bỏ lọc ngay) · `Select` người hỏi **chỉ admin** (nạp từ
`listUsers()`) · nút "Tải lại". Đổi bất kỳ bộ lọc nào đều quay về trang 1.

**Thẻ dọn log — chỉ admin**: dòng "Đang lưu N lượt trong M phiên, cũ nhất từ DD/MM/YYYY." lấy từ
`/stats`, nút "Xoá log cũ hơn…" mở `Modal` chọn ngày (dùng `DateInput` của dự án, chặn ngày tương
lai) + `Popconfirm` xác nhận. Xong việc: `message.success` kèm **số lượt đã xoá**, đóng modal, về
trang 1 và nạp lại bảng + thống kê. Có dòng lưu ý ĐỎ (`.form-note`) theo quy ước dự án.

**Bảng phiên**: Thời gian (lượt đầu + lượt cuối) · Người hỏi (**chỉ admin**) · Số lượt · Tiêu đề
(câu hỏi đầu) · nút xoá phiên (**chỉ admin**, `Popconfirm`, bọc `stopPropagation` để không mở
chi tiết). Bấm dòng → mở `Drawer` rộng 760px.

**Drawer chi tiết**: tiêu đề = ngày phiên + số lượt, `extra` = nút "Xoá phiên" (admin, có
`Popconfirm`). Mỗi lượt là một thẻ: số thứ tự · thời điểm · thẻ **"Mức tư vấn"** (`advice`, màu
theo raise/hold/lower, giá trị lạ vẫn hiện màu trung tính) · model · độ trễ (giây) · câu hỏi ·
câu trả lời (giữ xuống dòng) · hàng thẻ **"Công cụ đã gọi"** (`tools`), **"Nguồn dữ liệu"**
(`sources`), "Gói kỹ năng" (`packs`). Lượt sắp **cũ → mới** (tự sắp lại ở client cho chắc).

**Người dùng không phải admin**: không thấy cột người hỏi, không thấy nút xoá (cả ở bảng lẫn
drawer), không thấy khu dọn log, không gọi `/stats` và không gọi `listUsers()`.

## 3. Quyết định thiết kế

- **Phân trang ở server**: `limit=20` + `offset=(page-1)*20`, `total` lấy từ response; client
  không tải hết rồi lọc (luật `server-side-paging` của dự án). Client cố ý **không có** hàm
  "tải tất cả".
- **Quyền**: dùng đúng cơ chế sẵn có — `useAuth()` cho `user.role === "admin"`, `RequireCap`
  cho route, không tự chế cơ chế mới.
- **Kiểm quyền 2 lớp**: UI ẩn nút, backend vẫn `require_admin` — UI chỉ để đỡ bấm nhầm.
- **3 thao tác xoá đều có xác nhận**: xoá phiên ở bảng · xoá phiên trong drawer · dọn log cũ
  (Popconfirm trong footer Modal, tức 2 lớp).
- **Lỗi**: lỗi tải bảng hiện `Alert` đầu trang; lỗi thao tác hiện `message.error` (dùng
  `App.useApp()` như các trang khác).

## 4. ⚠ Việc cần người khác làm (ngoài phạm vi của tôi)

### 4.1 Backend trả KHÁC hợp đồng API tôi được giao

Đọc `apps/api/app/routers/assistant_history.py` + `app/services/assistant_log_repo.py` (do agent
khác viết song song) thấy 4 chỗ lệch:

| Chỗ | Hợp đồng giao cho FE | Backend đang trả |
|---|---|---|
| `GET ""` → item | `title` | `first_question` |
| `GET "/{session_id}"` | `{items: [...]}` | `{session_id, turns: [...]}` |
| `DELETE "/{session_id}"` | `{deleted: n}` | `{ok: true}` |
| `GET "/stats"` | `{turns, sessions, oldest}` | `{total_turns, total_sessions, oldest}` |

**Xử lý tạm**: client chuẩn hoá cả 2 dạng tên (khối `RawSession/RawTurns/RawStats` trong
`assistant-history-client.ts`) nên màn hình chạy đúng dù backend ngả về bên nào.

**Cần chốt**: thống nhất MỘT dạng (đề nghị backend đổi về đúng hợp đồng: `title`, `items`,
`{deleted: n}`, `{turns, sessions}`), rồi **xoá nhánh dự phòng** trong client. Riêng
`DELETE "/{session_id}"` nên trả `{deleted: n}` — repo đã có sẵn `rowcount`, chỉ router đang
nuốt số đó — để thông báo cho người dùng nói được "đã xoá N lượt".

### 4.2 Việc nhỏ khác

- `stamp()` (ISO → `HH:mm DD/MM/YYYY`) đang bị chép ở 2 nơi (`AuditLogPage.tsx` và trang này) vì
  tôi không được sửa `lib/date.ts`. Nên đưa vào `lib/date.ts` rồi cả hai dùng chung.
- `AssistantHistoryPage.tsx` dài 321 dòng (đã tách `TagRow` + `TurnCard` trong cùng file theo
  yêu cầu chỉ tạo 2 file). Nếu muốn về dưới 200 dòng thì tách `TurnCard` + hộp dọn log ra
  `pages/components/`.
- Chưa chạy thử với dữ liệu thật (backend + DB đang có agent khác sửa song song). Sau khi backend
  merge, cần bấm thử: phân trang · lọc ngày/câu hỏi/người dùng · mở chi tiết · 3 đường xoá.
- Backend đang giới hạn `limit ≤ 100` — FE dùng cố định 20, không có bộ đổi cỡ trang (đúng ý
  "phân trang ở server", không cần thêm).

## 5. Kết quả build

```
$ cd /Volumes/Work/biz-project/VRG/apps/web && pnpm build
$ tsc && vite build
vite v6.4.3 building for production...
transforming...
✓ 4960 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.64 kB │ gzip:   0.38 kB
dist/assets/index-Cbj9rb0O.css     27.21 kB │ gzip:   5.93 kB
dist/assets/index-Dn-crU0a.js   2,196.68 kB │ gzip: 661.31 kB

(!) Some chunks are larger than 500 kB after minification. …
✓ built in 3.12s
```

`tsc` sạch, không lỗi TypeScript (tsconfig bật `noUnusedLocals`/`noUnusedParameters`). Cảnh báo
kích thước chunk là **có sẵn từ trước**, không phải do thay đổi này.
