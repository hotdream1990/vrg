# Phase 02 — Web lõi (apps/web): client, popup, 2 màn danh sách, route, menu, quyền

Đọc trước: [plan.md](plan.md) · [api-contract.md](api-contract.md). Backend làm song song — code
theo đúng hợp đồng API, không chờ.

## File được phép sửa / tạo (đường dẫn dưới `apps/web/src/`)
Sửa: `lib/http.ts` · `lib/permissions.ts` · `App.tsx` · `features/command-center/sidebar-menu-builders.tsx` ·
`features/command-center/AdminLayout.tsx` (ROUTE_KEYS + đếm số chờ duyệt) ·
`features/command-center/sections/MemberDataLockBanner.tsx` (đổi câu "báo Ban TTKD sửa hộ" → hướng dẫn bấm Đề nghị sửa).
Tạo: `lib/edit-request-client.ts` · `lib/use-edit-request.tsx` · `lib/edit-request-diff.ts` ·
`features/command-center/components/EditRequestSubmitModal.tsx` ·
`features/command-center/pages/MyEditRequestsPage.tsx` · `features/command-center/pages/EditRequestReviewListPage.tsx` ·
`features/command-center/pages/EditRequestReviewDetailPage.tsx` · `features/command-center/components/EditRequestDiffTable.tsx` ·
`features/command-center/edit-request.css` (nếu cần; ưu tiên tái dùng class `support.css`/`.form-note`).
KHÔNG sửa các màn nhập liệu (UnitDaily*, MarketDemand*, Contract*, SalesContractPage) — phase 03 làm.

## Việc cần làm
1. `lib/http.ts`: `ApiError` (status + blocked đọc header `X-Edit-Blocked`), `isEditBlocked`. Mọi nhánh lỗi
   ném `ApiError` (vẫn là `Error`, message giữ nguyên) ⇒ không vỡ màn nào.
2. `lib/permissions.ts`: cap `edit_request` ("Duyệt đề nghị sửa số liệu của đơn vị"), 1 cấp, không vào
   EXECUTIVE_CAPS, đặt vào nhóm CAP_GROUPS hợp lý (cùng nhóm với quản lý số liệu đơn vị).
3. `lib/edit-request-client.ts`: type + hàm cho mọi endpoint §3 §4 (+ `editRequestFileUrl`/mở file như
   `openContractFile` của `sales-contract-client.ts`).
4. `lib/use-edit-request.tsx` + `EditRequestSubmitModal.tsx`: đúng giao diện §6. Hook chỉ mở popup khi
   `canEditUnitData` (AuthContext) và `isEditBlocked(e)`. Popup tự `fetchLockCurrent()` (lib/data-lock-client.ts)
   để dựng lưu ý chốt theo `company` + `min(dates)`. Lý do bắt buộc (trim ≥ 5 ký tự), TextArea maxLength 2000.
   Lưu ý dùng class `.form-note` (đỏ) — xem memory: hướng dẫn trong form nhập phải đỏ.
5. `MyEditRequestsPage` (`/de-nghi-sua`, tài khoản đơn vị): Segmented trạng thái (Chờ duyệt · Đã duyệt ·
   Từ chối · Đã huỷ · Tất cả, kèm số), bảng/danh sách: thời gian gửi, đơn vị, nội dung (`title` + `op_label`),
   lý do, trạng thái (Tag màu), ghi chú của Ban, nút "Huỷ đề nghị" (pending, `canEditUnitData`), phân trang
   server. Đề nghị đã duyệt có `unlocked` ⇒ dòng nhắc đỏ "Chốt số liệu đã được gỡ — vào xác nhận chốt lại".
   Bấm 1 dòng mở Drawer/Modal xem chi tiết + `EditRequestDiffTable` (trước lúc gửi ↔ đề nghị).
6. `EditRequestReviewListPage` (`/duyet-de-nghi-sua`, RequireCap `edit_request`): lọc trạng thái (mặc định
   Chờ duyệt), đơn vị, loại (op), ô tìm; bảng phân trang server; bấm dòng ⇒ trang chi tiết.
7. `EditRequestReviewDetailPage` (`/duyet-de-nghi-sua/:id`): thông tin đề nghị (đơn vị, người gửi, lúc gửi,
   nội dung, lý do, câu báo chặn lúc gửi); cảnh báo vàng nếu `changed_since_submit`; khối "Ảnh hưởng chốt số
   liệu" (`lock.locked_until`, `will_unlock`); `EditRequestDiffTable` 3 cột **Lúc gửi · Hiện tại · Đề nghị**
   (chỉ các dòng có khác biệt, tô nổi ô đề nghị khác hiện tại); nút **Duyệt** (Modal.confirm, ô ghi chú tuỳ
   chọn, nêu rõ sẽ gỡ chốt đợt nào) và **Từ chối** (Modal ghi chú bắt buộc). Lỗi duyệt hiện Alert đỏ.
8. `lib/edit-request-diff.ts` + `EditRequestDiffTable`: làm phẳng object lồng nhau thành đường dẫn
   (`fields.finished[1].qty`), so từng đường dẫn (5 == 5.0, "" == null), nhãn tiếng Việt: tái dùng nhãn cột
   có sẵn (`lib/unit-daily-fields.ts`, các label của form hợp đồng nếu có export) — thiếu nhãn thì hiện
   khoá gốc. Mảng file `{file, filename}` hiện tên file + mở qua `/api/edit-requests/{id}/file/{name}`.
   `before`/`current`/`payload` có hình dạng khác nhau theo op (api-contract §2) — so `payload.fields` với
   `before.fields`, `payload.prices` với `before.prices`, `payload.content` với `before.content`, hợp đồng so
   nguyên bản ghi (bỏ các khoá kỹ thuật: id, updated_at, updated_by, created_*).
9. Menu: đơn vị (`buildMemberMenu`) thêm "Đề nghị sửa số liệu"; Ban (`buildMenu`) thêm "Duyệt đề nghị sửa"
   khi `can("edit_request")`, nhãn kèm antd `Badge` số chờ (poll `/pending-count` ở AdminLayout lúc đổi route
   + `DATA_SAVED_EVENT`, không poll dày). Icon vector `@ant-design/icons`, KHÔNG emoji.
10. Route trong `App.tsx` (chi tiết đặt trước danh sách nếu cần), `ROUTE_KEYS` ở AdminLayout.

## Xong khi
`cd apps/web && pnpm exec tsc --noEmit` và `pnpm build` sạch · file < 200 dòng (tách component khi vượt) ·
báo cáo ngắn: file tạo/sửa + chữ ký thật của `useEditRequest` (phase 03 dùng).

## Trạng thái (15/09/2026)
✅ Xong 10/10 việc · `tsc --noEmit` + `pnpm build` sạch. Thêm 2 file ngoài danh sách (tách cho < 200 dòng):
`components/EditRequestInfo.tsx` (khối thông tin dùng chung) · `components/EditRequestReviewModal.tsx` (popup Duyệt/Từ chối).
