# Rà soát "Hiệu lực từ" theo dòng HĐ — góc SỬA / ĐỀ NGHỊ SỬA / NHẬT KÝ / UI (30/09/2026)

Phạm vi: 0b68ca2 + f7c9943 · edit_request_ops_contract/ops/apply · sales_contract_lock · edit-request-diff ·
audit-diff · ContractFormModal/LinesTable/DetailModal/CompleteModal · MasterContractDetailModal · member_data_check.
Kiểm chứng: `tsc --noEmit` 0 lỗi · pytest `test_contract_line_from_date` 7 pass · edit_request*/sales_contract*/
data_lock 89 pass (vrg_test) · probe `is_safe_edit` 8 ca · probe `buildEditRequestDiff` (esbuild) — xem cuối file.

## ĐÃ XÁC NHẬN (xếp theo mức độ)

1. **[Trung bình] Bảng việc đơn vị báo "Quá hạn sửa" oan cho HĐ giao 1 lần đã giao có dòng mang ngày hiệu lực.**
   `apps/api/app/services/member_data_check.py:154` lấy `ln.from_date` TRƯỚC `as_of` (= `delivered_at`, SQL :40-42),
   rồi `editable = as_of >= editable_from` (:132). from_date ≤ ngày giao ⇒ ngày nhắc lùi về trước.
   Repro: HĐ ký 01/09, giao 29/09, cửa sổ 1 ngày (editable_from 29/09), dòng 2 from_date 20/09, đơn giá 61.600.000 VND
   ⇒ chip "20/09/2026 · Hợp đồng … · dòng 2 · Đơn giá" màu xám, tooltip "Quá hạn sửa — … Đề nghị sửa"
   (`MemberChecklistBanner.tsx:27,87`) trong khi form sửa thẳng được (cửa sổ HĐ tính theo ngày giao 29/09).
   Lệch luôn với `anomaly_rules.py:133` (ưu tiên `delivered_at` trước from_date).
   Sửa: SELECT thêm `k.delivered_at`, dùng `delivered_at or from_date or as_of` — cùng thứ tự với anomaly_rules.

2. **[Thấp] Lời dặn đỏ nói thiếu hệ quả của "Giảm".** `ContractLinesTable.tsx:214-217` (và sổ tay
   `docs/huong-dan/nhap-lieu-don-vi-thanh-vien/README.md:243`): "Giảm sản lượng: sửa thẳng số lượng của dòng" —
   không nói số mới áp dụng NGƯỢC về ngày hiệu lực của dòng (plan: "áp dụng từ ngày hiệu lực của chính dòng đó"),
   đơn vị dễ hiểu là giảm từ hôm nay. Đề xuất: "…sửa thẳng số lượng của dòng — số mới tính từ ngày hiệu lực
   của dòng đó (kể cả các ngày đã qua)."

3. **[Thấp] Hoàn thành HĐ giao 1 lần: ngày giao mặc định có thể < ngày hiệu lực mà web không chặn.**
   `ContractCompleteModal.tsx:36,56,95`: `minGiao` chỉ khoá lịch; giá trị mặc định `giaoDay || day` (ngày hoàn thành)
   vẫn gửi đi khi < minGiao (from_date ở tương lai — server không chặn trần — hoặc chọn ngày hoàn thành trước dòng
   tăng). Server trả 400 đúng (`repo.save → clean_lines`), nhưng câu "Dòng N (…): ngày hiệu lực … sau ngày giao …"
   hiện muộn. Thêm kiểm trong `submit`: `(giaoDay || day) < minGiao` ⇒ setErr.

4. **[Thấp] Hiển thị so sánh.** Xoá ngày hiệu lực hiện "15/09/2026 → (trống)" (`edit-request-diff.ts:198`) — Ban
   không biết "(trống)" = theo ngày ký; nhật ký (`audit-diff.ts` `fieldLabel`) hiện ISO "2026-09-15", không số dòng
   (cùng kiểu các ô dòng khác — có sẵn). Gợi ý: path kết thúc `from_date` & rỗng ⇒ "theo ngày ký".

5. **[Thấp] Lời dặn chốt số liệu** `ContractFormModal.tsx:326-327` liệt kê ô làm đổi số (sản lượng, đơn giá, ngày
   giao…) nhưng thiếu "Hiệu lực từ" — HĐ giao 1 lần đã chốt đổi ô này sẽ bật hộp đề nghị sửa.

## CÓ THỂ (chưa phải lỗi / theo thiết kế)
- P1 "Thêm dòng" khi sửa: dòng mới mặc định trống = ngày ký ⇒ quên điền là phần tăng tính ngược về ngày ký, không
  cảnh báo. Đúng chốt "không khai = ngày ký", nhưng nên cân nhắc cảnh báo mềm cho dòng MỚI thêm khi sửa mà trống ngày.
- P2 Đề nghị sửa HĐ giao 1 lần: `dates` = chỉ ngày giao ⇒ gỡ chốt từ ngày giao; đổi from_date/SL làm đổi khối 3 các
  ngày [ngày ký/from_date, ngày giao) — không gỡ. Có từ trước (SL cũng vậy), khớp chốt "hợp đồng sửa tự do".
- P3 `DateInput` gõ tay ngày < ngày ký ⇒ tự trả về giá trị cũ, không báo gì (hành vi có sẵn của ô).
- P4 Đảo thứ tự dòng ⇒ `is_safe_edit` = False, diff theo chỉ số (có sẵn).

## ĐÃ KIỂM — ỔN
- `is_safe_edit` (router + ops đều qua `model_dump`): web gửi `from_date:null`/DB thiếu khoá ⇒ an toàn; gửi = ngày ký
  ⇒ an toàn; "2026-09-12T00:00:00" ⇒ an toàn; dời/xoá ngày, dời ngày ký ⇒ KHÔNG an toàn. Không có chặn oan, không lọt.
- Duyệt: `changed_since` so repo.get ↔ before (cùng nguồn jsonb) — from_date không làm lệch; `accept_changed`,
  `expected_updated_at`, `cannot_approve` (validate lại payload đủ from_date) đúng; apply lưu from_date (schema có ô).
- Diff đề nghị: lưu không đổi ⇒ 0 dòng; đổi ⇒ "Dòng hàng 2 · Hiệu lực từ 15/09/2026 → 18/09/2026"; dòng mới đủ ô.
- Tạo mới: thân gửi y cũ (EMPTY_LINE không khoá, `fromDateOut` trả nguyên object), server chỉ ghi khoá khi có ngày
  ⇒ JSON HĐ cũ lưu lại không đổi, nhật ký không báo đổi ảo.
- Đợt giao: web gửi `undefined` (bị bỏ), server `dated=False`, lock bỏ qua cho đợt, chuyển 1→nhiều lần gỡ khoá.
- Ngày ký dời qua dòng có ngày ⇒ lỗi rõ ở web + server; `maxFromDate` HĐ giao 1 lần đã giao ở web + server;
  đổi đơn vị khoá khi sửa, remap giữ from_date; danh sách HĐ trả `lines` thô (`_COLS`) ⇒ sửa từ danh sách không mất ngày;
  `set_completion` đi qua `repo.save` nên server chặn đúng; MasterContractDetailModal (preset) = tạo mới, không hồi quy.
- Changelog + sổ tay đã cập nhật (21ed5d6).

## Thiếu test
Luồng đề nghị end-to-end: HĐ giao 1 lần đã chốt có dòng mang ngày → (a) chỉ sửa ghi chú ⇒ lưu thẳng; (b) đổi ngày
hiệu lực ⇒ 403 chặn → gửi đề nghị → duyệt ⇒ DB có from_date; (c) web-shape `from_date: null` ≡ DB thiếu khoá.

## Câu hỏi treo
- from_date ở TƯƠNG LAI (tăng dự kiến) có được phép không? Server hiện cho; nếu không thì chặn ≤ hôm nay.
