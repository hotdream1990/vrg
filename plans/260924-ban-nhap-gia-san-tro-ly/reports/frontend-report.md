# Frontend — Phương án giá sàn nháp + Bản nháp tờ trình (25/09/2026)

**Kiểm tra:** `tsc --noEmit` sạch · `pnpm build` sạch (chỉ cảnh báo chunk > 500 kB có sẵn từ trước). Web chưa có vitest nên không viết unit test.

**Tạo mới** (`apps/web/src/`): `lib/floor-proposal-client.ts` · `pages/components/{FloorProposalPanel, FloorProposalCells, useProposalApply, SaveDraftModal, FloorDraftNarrative}` · `pages/{AssistantProposalDock, AssistantControls, useSessionProposal, useFloorDraft, FloorDraftListPage, FloorDraftEditorPage}`.
**Sửa:** `lib/assistant-client.ts` (gửi/nhận `proposal`) · `AssistantPage.tsx` (461 → 340 dòng: chuyển 2 công tắc sang `AssistantControls.tsx`, chỉ dời code, không đổi logic) · `ToTrinhPreview.tsx` (`load`/`title`/`extraActions`, sandbox `allow-same-origin allow-modals`, nút antd) · `FloorSuggestPage.tsx` · `App.tsx` · `sidebar-menu-builders.tsx`.

**Chỗ phải đoán theo hợp đồng** (đã đối chiếu với `schemas/floor_proposal.py` + `routers/floor_proposal.py` đang viết, thấy khớp):
- `*_delta_pct` hiểu là đơn vị %, hiển thị 1 số lẻ. `log[].at` hiểu là ISO datetime. Giữ nguyên `log[].before`.
- Nút Hoàn tác chỉ khoá khi `log` rỗng. Nếu dòng log "lập phương án" không có `before`, bấm Hoàn tác có thể nhận lỗi 400 (FE báo lỗi đó ra).
- Nút lưu nháp dùng `canEditCap("floor_suggest")`, không dùng `can`. Lãnh đạo Tập đoàn vẫn dùng được phương án trong chat (guard đã cho create/apply/preview) nhưng không thấy nút lưu, tạo, xoá.
- Đoạn diễn giải: tối đa 20 đoạn, mỗi đoạn 1.500 ký tự (khớp server). Đoạn trống bị bỏ trước khi PUT. Tiêu đề trống thì chặn lưu.

**Agent chính cần kiểm trên trình duyệt:**
1. QUAN TRỌNG — `AdminLayout.tsx` (ngoài danh sách file được sửa): thêm `"/goi-y-gia-san/ban-nhap"` vào `ROUTE_KEYS`, đặt TRƯỚC `"/goi-y-gia-san"`. Thiếu dòng này thì menu tô sáng "Gợi ý giá sàn" thay cho "Bản nháp tờ trình".
2. Nút In / Xuất PDF trong iframe sandbox: `contentWindow.print()` phải mở hộp thoại in (Chrome, Safari).
3. Sửa ô: gõ số rồi Enter hoặc bấm ra ngoài thì mới gọi `apply`. Esc trả lại số cũ, không đóng Drawer. Sửa nhanh 2–3 ô liên tiếp phải giữ đủ, nhờ hàng đợi. Lệch ≥10% so với lần trước hiện viền vàng.
4. Bố cục Trợ lý: màn ≥1200px có cột phải 560px (≥1600px là 640px), thu gọn được. Màn <1200px dùng nút "Xem phương án" mở Drawer. Khi Trợ lý đang trả lời, bảng tạm khoá để bản AI không đè mất số sửa tay.
5. Gợi ý câu hỏi: ở "Mở rộng" (5 gói, tối đa 6 câu, lấy vòng tròn) chỉ câu đầu của gói floor lọt vào. 2 câu mới chỉ hiện ở "Cơ bản". Muốn hiện ở cả "Mở rộng" thì đưa lên đầu danh sách (cần chủ dự án quyết).
6. Màn soạn nháp: `beforeunload` chỉ bắt đóng tab hoặc tải lại. Bấm menu sidebar khi chưa lưu thì KHÔNG hỏi lại, vì app dùng `BrowserRouter`, không dùng được `useBlocker`. Nút "Danh sách" có hỏi lại.
7. Phương án trong sessionStorage khoá theo username (`vrg.assistant.proposal:<user>`).

## Vòng sửa theo review (25/09/2026) — `tsc --noEmit` + `pnpm build` sạch

Giữ nguyên các sửa của agent chính (ROUTE_KEYS, cột Tiêu đề 280 + scroll 1280, `base_updated_at`).
1. **CAO, lưu nháp:** chuyển hàng đợi `useProposalApply` lên `useFloorDraft`; Panel nhận prop `applier` và không tự tạo hàng đợi. Hàng đợi có thêm `whenIdle()` (chờ tới khi đuôi hàng đợi đứng yên, trả phương án mới nhất). `save` chờ `whenIdle` rồi đọc `formRef` (cập nhật đồng bộ trong `patch`). Bộ đếm `rev` tăng ở mỗi `patch`: nếu có sửa trong lúc PUT thì chỉ `setDraft(d)` (lấy mốc `updated_at` mới), giữ nguyên form và cờ chưa lưu. Nút Lưu bật khi `dirty` hoặc đang áp.
2. **CAO, chat:** `ask` bật `loading` trước (bảng bị khoá ngay), `await applier.whenIdle()`, rồi gửi phương án mới nhất. Blur của ô xảy ra lúc nhấn chuột xuống, nên lần áp đã vào hàng đợi trước khi hàm click chạy.
3. Thêm cột "Mô hình nội địa" (`model_vnd`); bảng rộng tối thiểu 900px.
4. Lưu gặp 409: hiện hộp hỏi "Tải bản mới nhất (bỏ phần sửa của tôi)" (gọi `reload` → `getDraft` → `reset`) hoặc "Ở lại" (giữ nguyên form).
5. Tạo `features/command-center/unsaved-guard.tsx`: `useUnsavedGuardHost` + Provider đặt trong AdminLayout; menu sidebar, Hồ sơ cá nhân và Đăng xuất đều đi qua `guard()`. `useUnsavedGuard(dirty)` đăng ký lời nhắc, bật `beforeunload` và trả `guard` cho nút "Danh sách". **Hạn chế:** nút Back/Forward của trình duyệt vẫn không bị chặn; nút thoát đăng nhập hộ trên banner cũng không qua guard.
6. Khi Trợ lý đang trả lời, dock khoá Xem trước, Lưu bản nháp (cả nút lưu trong khung xem trước), Đóng phương án và Lập lại phương án. Xem trước và lưu đọc phương án qua `whenIdle`.
7. Ô số giữ `valueRef` luôn mới; server từ chối thì ô trở về giá trị của phương án hiện tại.
8. "Thêm đoạn" chèn đoạn rỗng. Khi lưu và khi xem trước, bỏ đoạn rỗng và đoạn chỉ có gạch đầu dòng. Lời dặn nhập dùng `.form-note` (ẩn khi chỉ xem).
9. Danh sách nháp dùng bộ đếm `seq`: chỉ nhận kết quả của lần gọi mới nhất.
10. `logout` trong AuthContext gọi `clearSessionProposals()` (ở `lib/floor-proposal-client.ts`, bọc try/catch), xoá mọi khoá `vrg.assistant.proposal:*`. `useSessionProposal` đọc lại khi đổi tài khoản ngay trên màn (đăng nhập hộ). Hết phiên (401) thì không xoá.
11. Ô ghi chú trong SaveDraftModal giới hạn 4.000 ký tự.
Còn phải kiểm trên trình duyệt: sửa ô rồi bấm thẳng Lưu hoặc Gửi (số vừa gõ phải có trong bản lưu/bản gửi); 409 với 2 tab; bấm menu hoặc Đăng xuất khi chưa lưu phải hiện hộp hỏi.
