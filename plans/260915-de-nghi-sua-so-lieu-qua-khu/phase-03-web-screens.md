# Phase 03 — Gắn "Đề nghị sửa" vào các màn nhập liệu của đơn vị

Đọc trước: [plan.md](plan.md) · [api-contract.md](api-contract.md) §1 §6. Chạy SAU phase 02 (dùng
`useEditRequest`, `ApiError`, `isEditBlocked`).

## File được phép sửa (dưới `apps/web/src/features/command-center/`)
`pages/UnitDailyEditModal.tsx` · `pages/UnitDailyTimeline.tsx` · `pages/PurchaseForm.tsx` ·
`pages/ConsumptionForm.tsx` · `pages/UnitDailyForm.tsx` · `pages/UnitDailyMoveDateModal.tsx` ·
`pages/MarketDemandTimelinePage.tsx` · `pages/SalesContractPage.tsx` · `components/ContractFormModal.tsx` ·
`components/ContractDetailModal.tsx` · `components/ContractBatchTable.tsx` · `sections/MemberChecklistBanner.tsx`
(chỉ đổi câu "báo Ban TTKD nhập hộ"). Không tạo lại thứ phase 02 đã có.

## Nguyên tắc
- Chỉ tài khoản đơn vị nhập liệu (`canEditUnitData`) thấy nút. Đơn vị đã sáp nhập (`view_only_units`),
  ngày tương lai, lãnh đạo đơn vị ⇒ KHÔNG có nút (không phải chuyện hàng rào thời gian).
- Bản ghi đang khoá vì **cửa sổ sửa hoặc chốt số liệu** ⇒ chỗ trước đây hiện "(chỉ xem)"/"(đã chốt)"/icon khoá
  có thêm nút/link **"Đề nghị sửa"** (icon vector). Bấm ⇒ form mở ở **chế độ đề nghị**: cho sửa, nút lưu đổi
  nhãn thành **"Gửi đề nghị sửa"**, có Alert vàng ngắn "Bạn đang soạn đề nghị sửa — số liệu chỉ thay đổi sau
  khi Ban duyệt."
- Lưu ở chế độ đề nghị (và cả lưu thường ở màn hợp đồng) đi qua `saveOrRequest(direct, draft)`: server
  vẫn cho lưu thẳng thì lưu thẳng; bị chặn thì popup đề nghị. KHÔNG tự đoán luật chặn ở web.
- Payload trong `draft` = đúng body màn đó định gửi (api-contract §1). `title` tiếng Việt, ngày dd/mm/yyyy.

## Việc cần làm
1. **Biểu Thu mua / Tồn kho** (`UnitDailyEditModal` + form): khi `editable=false` vì khoá (không phải
   merged/future) ⇒ nút "Đề nghị sửa" trong Alert ⇒ `requestMode`. Lưu: direct = đúng chuỗi lưu hiện tại
   (`saveMyDaily` rồi giá); draft `daily_report` `{kind, company, as_of, fields, prices}` — `prices` lấy từ
   cùng logic `savePrices` (chỉ loại giá thay đổi; xoá = 0). ⚠ Thứ tự hiện tại lưu biểu trước rồi mới lưu
   giá: ở chế độ đề nghị phải gom CẢ HAI vào một đề nghị, không để phần biểu bị chặn còn phần giá lọt đi riêng.
   Timeline: tooltip icon khoá đổi thành "… bấm để xem hoặc gửi đề nghị sửa".
2. **Đổi ngày** (`UnitDailyMoveDateModal` + nút ở timeline đang `disabled={locked}`): cho mở ở chế độ đề
   nghị khi khoá; OK ⇒ `saveOrRequest(moveDailyDate, draft daily_move)`. Bỏ chặn cứng OK khi ngoài cửa sổ,
   thay bằng chế độ đề nghị.
3. **Nhu cầu thị trường**: dòng ngoài cửa sổ ⇒ nút "Đề nghị sửa" ⇒ ô sửa inline như bình thường ⇒ Lưu qua
   `saveOrRequest` với draft `market_demand`.
4. **Hợp đồng & đợt giao**: `ContractFormModal.save` luôn đi qua `saveOrRequest` (draft `contract_save`,
   title "Hợp đồng {code}" / "Đợt giao {code}"). "(chỉ xem)" ở `SalesContractPage` + `ContractBatchTable` +
   dòng "Đã giao quá hạn sửa…" ở `ContractDetailModal` ⇒ thêm "Đề nghị sửa" (mở form chế độ đề nghị) và
   "Đề nghị xoá" (confirm ⇒ `saveOrRequest(deleteContract, draft contract_delete)`). Hợp đồng đã hoàn thành
   (`completed_at`) KHÔNG phải hàng rào thời gian — giữ nguyên.
5. Sau khi gửi xong: đóng form, `message.success` (popup đã báo), KHÔNG reload như đã lưu số.

## Xong khi
`pnpm exec tsc --noEmit` + `pnpm build` sạch · mỗi màn có chế độ đề nghị hoạt động theo payload đúng
api-contract · file < 200 dòng mới tách (không bắt buộc tách file cũ đã vượt, nhưng không làm phình thêm
quá mức — tách hook/khối con nếu thêm > 40 dòng) · báo cáo: màn nào, payload mẫu từng op.

## Trạng thái (15/09/2026)
✅ Xong 5/5 việc · `tsc --noEmit` + `pnpm build` sạch. Thêm 2 file dựng bản nháp (ngoài danh sách, file mới):
`pages/unit-daily-edit-request.ts` (`priceChanges` · `dailyReportDraft` · `dailyMoveDraft`) ·
`pages/components/contract-edit-request.ts` (`contractSaveDraft` · `contractDeleteDraft` · `deleteConfirmText`).
Không sửa `PurchaseForm`/`ConsumptionForm`/`UnitDailyForm` (form chỉ nhận `readOnly`, nút lưu dựng ở modal).
Chip xám ở bảng nhắc việc nay bấm được (mở phiếu/màn hợp đồng) — chưa tự bật chế độ đề nghị vì
`UnitDailyPage.tsx` không thuộc phase này; đơn vị bấm "Đề nghị sửa" trong Alert của phiếu.
