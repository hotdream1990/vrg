# Trợ lý AI — Gói kỹ năng (phần Frontend)

Ngày: 2026-09-10 · Nhánh: `feature/master-contract` · Phạm vi: **chỉ 2 file** được giao.

## 1. File đã sửa

| File | Nội dung |
|---|---|
| `/Volumes/Work/biz-project/VRG/apps/web/src/lib/assistant-client.ts` | Thêm type `SkillPack`, hàm `fetchPacks()`, `sendChat(messages, packs?)` |
| `/Volumes/Work/biz-project/VRG/apps/web/src/features/command-center/pages/AssistantPage.tsx` | Hàng chip chọn gói + gợi ý câu hỏi theo gói + ghi nhớ localStorage |

Không sửa file nào khác.

## 2. UI đã làm

**Hàng chip** nằm ngay dưới đoạn mô tả đầu trang, trong đúng khối header cũ — **không đụng vào**
`height: calc(100vh - 150px)` của khung ngoài lẫn `flex:1 / minHeight:0` của vùng cuộn, nên bug
layout kéo giãn sidebar trước đây không thể tái phát.

Nhãn hàng: `Nhóm dữ liệu Trợ lý được phép tra cứu:` — dùng `Tag.CheckableTag` (antd v6).

3 trạng thái chip:

| Trạng thái | Hiển thị | Tooltip |
|---|---|---|
| `core: true` | Đã chọn (nền xanh primary) + icon `LockOutlined`, `cursor: default`, bấm không đổi trạng thái | `{desc} (N công cụ) · Nhóm nền — luôn bật.` |
| `active: true`, thường | Bật/tắt được. Bật = nền xanh; tắt = viền liền + nền nhạt | `{desc} (N công cụ)` |
| `active: false` | Mờ (`opacity .6`), viền đứt, icon `StopOutlined`, `disabled` → không bấm/không focus được | `{desc} (N công cụ) · Không khả dụng với tài khoản của bạn hoặc đã tắt trong Cấu hình hệ thống.` |

**Gợi ý câu hỏi** giờ sinh theo gói đang bật (`PACK_SUGGESTIONS` map `market/floor/internal/unit`),
tối đa 6 câu.

## 3. Quyết định thiết kế (và vì sao)

1. **Ghi nhớ danh sách gói BỊ TẮT, không phải gói đang bật.** Key `vrg.assistant.packs.off`.
   Nếu lưu danh sách "đang bật", sau này backend thêm gói mới thì gói đó **không có trong bản ghi
   nhớ cũ → mặc định tắt âm thầm**, người dùng không bao giờ biết có tính năng mới. Lưu ngược lại
   thì gói mới luôn mặc định bật, đúng yêu cầu "mặc định bật hết gói active".
   Toàn bộ đọc/ghi localStorage bọc `try/catch` (chế độ riêng tư / máy trạm chặn storage).

2. **Gợi ý lấy VÒNG TRÒN mỗi gói một câu**, không cắt thẳng 6 câu đầu. Cắt thẳng thì với 4 gói × 2
   câu = 8 câu, gói xếp cuối (`unit`) sẽ không bao giờ có câu nào lọt vào top 6 — người dùng tưởng
   gói đó vô dụng. Vòng tròn đảm bảo mỗi gói đang bật đều có mặt.

3. **`sendChat` không gửi trường `packs` khi mảng rỗng.** Gửi `packs: []` dễ bị backend hiểu thành
   "không cho tra cứu gì cả"; bỏ hẳn trường thì đúng hợp đồng "bỏ trống = dùng tất cả gói khả dụng".

4. **Vẽ lại viền cho chip ở trạng thái tắt.** `CheckableTag` của antd v6 đặt
   `backgroundColor: transparent; borderColor: transparent` cho chip chưa chọn (đã đọc
   `node_modules/antd/es/tag/style/index.js`), nên chip tắt trông như chữ trơ, không ra hình nút.
   Thêm viền + nền nhạt inline (inline style thắng class) để cả hàng đọc được là "các nút bật/tắt".

5. **Chip `core` dùng `checked` + `onChange` rỗng, KHÔNG dùng `disabled`.** Style của antd cho
   `checkable-checked-disabled` đổi nền sang `colorBgContainerDisabled` + chữ xám → mất hẳn dáng
   "đang bật". Cách hiện tại giữ nền xanh (đúng nghĩa luôn bật) mà bấm vẫn không đổi trạng thái.

6. **Lỗi `GET /api/assistant/packs` không chặn màn chat**: `catch` im lặng, `packs` giữ `[]`,
   `SkillPackChips` early-return `null` → ẩn hàng chip, `sendChat` không gửi `packs`, chat như cũ.

7. **Bỏ emoji `📎`** ở dòng trích nguồn, thay bằng `<PaperClipOutlined />` — theo quy ước dự án
   (chỉ dùng `@ant-design/icons`). Đây là emoji duy nhất còn sót trong file.

## 4. Kiểm chứng

### Build sạch

```
$ cd /Volumes/Work/biz-project/VRG/apps/web && pnpm build
$ tsc && vite build
vite v6.4.3 building for production...
transforming...
✓ 4958 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.64 kB │ gzip:   0.38 kB
dist/assets/index-Cbj9rb0O.css     27.21 kB │ gzip:   5.93 kB
dist/assets/index-CBczqWSb.js   2,167.86 kB │ gzip: 652.11 kB
✓ built in 3.16s
```

Không có lỗi TypeScript. (Cảnh báo "chunks larger than 500 kB" là cảnh báo cũ của toàn dự án,
không liên quan thay đổi này.)

### Đã đọc mã nguồn antd để chắc runtime đúng, không chỉ đúng kiểu

`node_modules/antd/es/tag/CheckableTag.js`: `disabled` chặn cả `onClick` lẫn phím Space, đặt
`aria-disabled` + `tabIndex={-1}`; `icon` được render; `style` truyền vào được merge. Style disabled
chỉ đặt `cursor: not-allowed`, **không** đặt `pointer-events: none` → `Tooltip` bọc chip mờ vẫn hiện
bình thường (không cần bọc thêm `<span>` như với `Button disabled`).

### ⚠ Chưa kiểm chứng bằng mắt trên app thật

`/api/assistant/packs` **chưa tồn tại** (`apps/api/app/routers/assistant.py` chưa có endpoint) và API
local đang tắt, nên không chạy được kịch bản 3 trạng thái chip trên trình duyệt. Ai ghép với backend
xong xin chạy checklist mục 6.

## 5. Việc cần người khác làm (ngoài phạm vi 2 file của tôi)

1. **Backend**: `GET /api/assistant/packs` trả đúng shape hợp đồng (`key/label/desc/core/active/tools`),
   và `POST /api/assistant/chat` nhận thêm `packs: string[] | None`.
2. **Khoá gói của tài khoản**: `active` phải phản ánh **cả** quyền tài khoản **lẫn** công tắc admin.
   Frontend chỉ hiển thị, **không** tự suy quyền — và quan trọng: frontend gửi `packs` lên chỉ là
   *gợi ý thu hẹp*, **backend vẫn phải tự chặn** gói mà tài khoản không có quyền (người dùng sửa
   được payload).
3. **Cấu hình hệ thống** (`SystemConfigPage.tsx`): cần thêm công tắc bật/tắt từng gói cho toàn hệ
   thống — tooltip chip đang hứa với người dùng là có chỗ này ("đã tắt trong Cấu hình hệ thống").
4. **Key gói phải khớp** `market` / `floor` / `internal` / `unit`. Gói có key khác vẫn chạy được
   (chip hiện bình thường) nhưng **không có gợi ý câu hỏi** — nếu backend đổi/thêm key, báo lại để
   bổ sung vào `PACK_SUGGESTIONS`.

## 6. Checklist kiểm thử sau khi ghép backend

- [ ] Chip `core` (market, floor): nền xanh + ổ khoá, bấm không tắt được.
- [ ] Chip thường (internal): bấm tắt → chip đổi sang viền liền/nền nhạt; gợi ý của gói đó biến mất.
- [ ] Chip `active: false` (unit): mờ + viền đứt, bấm không ăn, tooltip đúng câu.
- [ ] Tắt `internal` → F5 → vẫn tắt (localStorage).
- [ ] Xem Network: `POST /api/assistant/chat` body có `packs` đúng danh sách đang bật.
- [ ] Giả lập lỗi (backend trả 500 cho `/packs`) → hàng chip biến mất, chat vẫn hỏi đáp được, body
      request **không** có trường `packs`.
- [ ] Sidebar không bị kéo giãn, khung chat vẫn cuộn trong vùng của nó.
