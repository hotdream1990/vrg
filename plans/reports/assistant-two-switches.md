# Trợ lý AI — thay 4 chip gói kỹ năng bằng 2 công tắc

Ngày: 2026-09-10 · Nhánh: `feature/master-contract`

## Phạm vi đã sửa (đúng 2 file)

- `apps/web/src/features/command-center/pages/AssistantPage.tsx`
- `apps/web/src/lib/assistant-client.ts`

Không đụng `App.tsx`, layout/menu, không tạo file mới.

## UI mới

Hàng điều khiển nằm ngay dưới tiêu đề màn (chỗ trước đây là hàng 4 chip):

| Thành phần | Nội dung |
|---|---|
| `Segmented` **Nguồn tham chiếu** | `Cơ bản` · `Mở rộng` (mặc định) — thêm `Tuỳ chỉnh` chỉ khi người dùng tự chỉnh chip |
| `Segmented` **Mức tư vấn** | `Chỉ tra số` · `Theo mô hình` (mặc định) · `Có điều chỉnh` |
| `Button type="link"` + `SettingOutlined` — nhãn **Nâng cao** | Mở `Popover` "Chi tiết nhóm dữ liệu" chứa nguyên hàng chip cũ |
| Dòng chú thích | `InfoCircleOutlined` + câu mô tả mức tư vấn đang chọn (font 12, opacity .65) |

- Mỗi lựa chọn của cả hai công tắc đều bọc `Tooltip` với đúng câu giải thích trong yêu cầu.
- Chú thích ví dụ khi chọn *Có điều chỉnh*: "Trợ lý có thể đề xuất khác mức mô hình và phải nêu rõ
  lý do. Mọi khuyến nghị chỉ để tham khảo, không ghi vào biểu giá sàn."
- Không có emoji; chỉ icon `@ant-design/icons`. Nhãn tiếng Việt, giữ tông tối + nhấn `#0a9e48`.

## Ánh xạ công tắc → payload

`packsForScope(scope, packs, off)` suy ra `packs` gửi lên:

| Nguồn tham chiếu | `packs` gửi lên |
|---|---|
| Cơ bản | các gói có `core: true` (hôm nay = `["market","floor"]`) — suy từ cờ `core` của API, không hardcode |
| Mở rộng | mọi gói `active: true` từ `GET /api/assistant/packs` |
| Tuỳ chỉnh | gói `active` trừ danh sách gói người dùng đã tắt tay; gói `core` luôn nằm trong |

`advice` gửi thẳng giá trị công tắc 2 (`data` / `model` / `adjusted`).

`sendChat(messages, packs?, advice?)` chỉ đính kèm trường nào có giá trị:
`packs` rỗng thì bỏ hẳn (backend hiểu là "dùng mọi gói khả dụng" — gửi mảng rỗng sẽ bị hiểu nhầm
thành "cấm tra cứu"), `advice` không truyền thì backend giữ mặc định của nó.

## Quyết định thiết kế

1. **Không vứt logic chip.** `SkillPackChips` giữ nguyên 3 trạng thái (nền khoá · bật/tắt được ·
   không khả dụng mờ) và vẫn ghi nhớ theo **danh sách gói BỊ TẮT** (`vrg.assistant.packs.off`) —
   gói mới backend thêm sau này vẫn mặc định bật. Chỉ bỏ dòng nhãn dài phía trước vì tiêu đề
   Popover đã nói thay.
2. **Nguồn sự thật đơn.** Trước đây `selected` là state được set tay lúc tải gói; nay `selected` là
   `useMemo` suy từ (scope + danh sách gói + danh sách gói tắt). Đổi công tắc không cần đồng bộ tay,
   hết cơ hội lệch trạng thái giữa chip và payload.
3. **"Tuỳ chỉnh" là trạng thái, không phải chế độ để chọn.** Chỉ xuất hiện trong `Segmented` khi
   người dùng đã bấm chip; công tắc thường vẫn đúng 2 lựa chọn như yêu cầu.
4. **Chuyển sang Tuỳ chỉnh không mất lựa chọn đang thấy.** Khi đang ở Cơ bản/Mở rộng mà bấm chip,
   điểm xuất phát là chính danh sách đang hiển thị, nên người dùng thấy đúng thứ mình vừa bật/tắt.
5. **API gói lỗi thì màn vẫn dùng được.** Ẩn nút Nâng cao, hai công tắc vẫn chạy; riêng "Cơ bản" có
   `FALLBACK_BASIC_PACKS = ["market","floor"]` để không âm thầm rơi về "mở hết".
6. **localStorage bọc `try/catch`** ở cả đọc lẫn ghi (`readStored`/`writeStored`) — chế độ riêng tư
   hoặc chính sách máy trạm chặn storage thì mất tiện nghi ghi nhớ, không được làm sập màn chat.
   Khoá mới: `vrg.assistant.scope`, `vrg.assistant.advice`.
7. **Không đụng khung chat**: `height: calc(100vh - 150px)`, vùng cuộn `flex:1 / minHeight:0` giữ
   nguyên từng dòng.
8. File 435 dòng — trên ngưỡng 200 nhưng theo yêu cầu chỉ tách component phụ **trong chính file**:
   `AssistantControls`, `SkillPackChips`, `tipOptions`, `packsForScope`, `buildSuggestions`.

## Kết quả build

```
$ pnpm build
> tsc && vite build
vite v6.4.3 building for production...
transforming...
✓ 4958 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                     0.64 kB │ gzip:   0.38 kB
dist/assets/index-Cbj9rb0O.css     27.21 kB │ gzip:   5.93 kB
dist/assets/index-BmlWBr17.js   2,172.05 kB │ gzip: 653.21 kB

(!) Some chunks are larger than 500 kB after minification. ...
✓ built in 3.20s
```

`tsc` sạch, không lỗi TypeScript. Cảnh báo chunk >500 kB là cảnh báo cũ của toàn app, không liên
quan thay đổi này.

## Đối chiếu backend (đã khớp)

Backend trong cây làm việc đã có sẵn phần của mình, khớp đúng hợp đồng:

- `apps/api/app/schemas/assistant.py`: `advice: Literal["data","model","adjusted"] = "model"`
- `apps/api/app/services/assistant_service.py`: `system_prompt(advice)` + `_scope()` giao gói người
  dùng chọn với gói admin bật.

→ Không cần đổi gì thêm ở frontend cho hợp đồng API.

## Việc cần người khác làm

1. **Kiểm thử trên trình duyệt** — chưa chạy được ở lượt này: dev server chưa bật và `apps/api` đang
   được sửa song song, bật lên dễ dính code nửa vời. Cần soát mắt 4 điểm:
   - Đổi công tắc → xem `POST /api/assistant/chat` gửi đúng `packs` + `advice` (tab Network).
   - Popover "Nâng cao": bật/tắt chip → công tắc 1 nhảy sang "Tuỳ chỉnh"; chip gói nền và gói mờ
     bấm không ăn.
   - Tải lại trang: cả 2 công tắc và các chip nhớ đúng lựa chọn cũ.
   - Khung chat không bị đẩy lệch (hàng điều khiển cao hơn hàng chip cũ ~24px do có dòng chú thích).
2. **Sổ tay/hướng dẫn người dùng**: mô tả cũ nói "chọn gói kỹ năng" nay không còn đúng, cần sửa
   thành 2 công tắc (`docs/huong-dan/`).
3. Nếu backend đổi gói nào là `core`, frontend tự bám theo cờ `core` — chỉ `FALLBACK_BASIC_PACKS`
   (dùng khi API gói lỗi) là hằng số cần sửa tay.
