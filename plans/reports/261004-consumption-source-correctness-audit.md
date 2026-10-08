# Rà soát tính đúng — Nguồn tiêu thụ (khai thác / thu mua) · commit `4522afd` (0.4.108)

Ngày: 04/10/2026 · Phạm vi: CHỈ ĐỌC code (`apps/api`, `apps/web`, `scripts/`). Không chạy pytest (test ghi
vào DB dev — ngoài phạm vi chỉ-đọc). `tsc --noEmit` web: **pass**. Các file lõi hợp đồng không đổi từ
`4522afd` tới `HEAD` (chỉ `edit-request-diff.ts`, `edit_request_apply.py` có thêm phần Kế hoạch năm, không đụng nguồn).

---

## 1. Mọi đường ghi `sales_contract` có thể đặt/đổi ngày giao

| # | Đường ghi | Kiểm bắt buộc nguồn khi có ngày giao | Giá trị lạ | HĐ cha multi | Xoá ngày giao |
|---|---|---|---|---|---|
| 1 | `PUT /api/sales-contracts` → `repo.validate` + `repo.save` → `clean()` (`sales_contract_clean.py:186-195`) | Có (lần giao = đợt / HĐ giao 1 lần) | Chặn 400 | Ép `None` (kể cả gửi lên) | Giữ nguyên `source` đã gửi (không xoá) |
| 2 | `PUT /{id}/completion` → `lifecycle.set_completion` (`sales_contract_lifecycle.py:94-117`) | Có — thiếu kênh/nguồn → 400; ghi qua `repo.save` nên giá trị cũng qua `clean()` | Chặn | Không áp dụng (chỉ HĐ giao 1 lần chưa giao) | — |
| 3 | `PUT /{id}/delivery-type` → `set_delivery_type` (`:160-189`, `_move_delivery_to_batch` `:204-222`) | Không qua `clean()`: INSERT…SELECT sao nguyên `source` xuống đợt 1, `_CLEAR_BATCH` xoá ở HĐ | Không kiểm (chỉ sao giá trị đã hợp lệ) | HĐ cha luôn `NULL` | — |
| 4 | Duyệt đề nghị sửa: `contract_save` (`edit_request_ops_contract.py:96-122`, `_legacy_source`), `contract_delivery_type` (→ #3), `contract_delete` | Có (qua `repo.save`) | Chặn | Như #1 | Như #1 |
| 5 | `master_contract_annexes.py:107` (nối HĐ mẹ) | Chỉ `UPDATE master_id` — không đụng ngày giao/nguồn | — | — | — |
| 6 | `member_unit_repo.py:122` (đổi tên đơn vị) | Chỉ `company`/`to_company` | — | — | — |
| 7 | `core/db.py:651-660` backfill MỘT LẦN khi thêm cột | Gán `exploit` cho mọi `delivered_at IS NOT NULL` | — | **Có thể gán cho HĐ cha multi dị thường** (xem S2) | — |
| 8 | `scripts/migrate-sales-contracts.py` (script lịch sử) | INSERT KHÔNG có `source` → chạy lại sẽ sinh lần giao NULL nguồn | — | — | — |
| — | `/api/member/*`, nhập Excel | Không có đường ghi `sales_contract` (Excel ghi biểu ngày, đang tắt) | | | |

Kết luận: mọi đường ghi qua API đều chặn đúng; HĐ cha multi không nhận nguồn qua API.

---

## 2. LỖI THẬT (đã xác minh bằng đọc code)

### F1 — TRUNG · Đề nghị sửa HĐ gửi trước 0.4.108 luôn bị coi là "số liệu đã thay đổi"
- `edit_request_ops.py:131-146` (`canon` + `changed_since` so NGUYÊN dict) · `edit_request_apply.py:72, 131`.
- `before` lưu lúc gửi = `sales_contract_repo.get()` thời chưa có cột → **không có khoá `source`**; `current`
  nay có `source` (`exploit` do backfill, hoặc `None`) → dict khác nhau dù không ai sửa gì.
- Kịch bản: mọi đề nghị `contract_save` (có `id`) / `contract_delete` / `contract_delivery_type` còn
  `pending` lúc deploy → trang duyệt hiện cảnh báo "đã thay đổi", bấm Duyệt → **409** cho tới khi tick
  "xác nhận ghi đè". Hệ quả nặng hơn: người duyệt quen ghi đè ⇒ cơ chế bắt thay đổi THẬT sau khi gửi bị
  vô hiệu với các đề nghị này. `contract_delete` còn hiện thêm dòng "Nguồn tiêu thụ: — | Khai thác | —".
- Test `test_legacy_edit_request_payload_keeps_the_stored_source` chỉ thử hàm `_legacy_source`, không
  thử duyệt end-to-end nên không lộ.
- Sửa: chạy một lần trên prod (sau khi đo S4):
  `UPDATE edit_request e SET before = e.before || jsonb_build_object('source', sc.source) FROM sales_contract sc
   WHERE e.status='pending' AND e.op IN ('contract_save','contract_delete','contract_delivery_type')
   AND e.before IS NOT NULL AND NOT (e.before ? 'source') AND sc.id = (e.before->>'id')::bigint;`
  hoặc trong code: so `current` chỉ trên các khoá có ở `before` khi `before` là dict.

### F2 — TRUNG · Chuyển "giao 1 lần" CHƯA GIAO → "nhiều lần" đẻ đợt chờ giao 100% sản lượng, chặn đợt thật
- `sales_contract_lifecycle.py:32-33, 179-180`: `any(before.get(k) for k in _BATCH_COLS)` — `source` nay
  nằm trong `_BATCH_COLS`. Form hiện ô Nguồn cho MỌI HĐ giao 1 lần (kể cả chưa giao,
  `ContractDeliveryFields.tsx`) nên đơn vị chọn nguồn lúc ký là đủ điều kiện.
- Kịch bản: HĐ 100 t, giao 1 lần, chưa giao, đã chọn Nguồn = Thu mua → "Chuyển sang giao nhiều lần" →
  sinh "HĐ…-Đợt 1" đang chờ giao, mang nguyên 100 t → thêm đợt thật 30 t: `_assert_within_cap`
  (`sales_contract_repo.py:216-217`, `_batches_qty` cộng cả đợt chờ) = 130 t > 110 t → **400**. Đơn vị
  phải tự xoá đợt ma. Lỗi cũ với `channel`/`invoice_no`, nay mở rộng thêm bởi `source`.
- Sửa: chỉ dời xuống đợt khi `delivered_at` có giá trị hoặc có chứng từ/thanh toán; các ô "nhãn"
  (`channel`, `to_company`, `source`) của HĐ chưa giao thì bỏ khi chuyển.

### F3 — THẤP-TRUNG · Bẫy ô ẩn trên form hợp đồng
- `ContractFormModal.tsx:149-150` kiểm `isDelivery && !c.source` (và `!c.channel`) cả khi
  `ContractDeliveryFields` bị ẩn (`isBatch` false).
- Kịch bản: Thêm HĐ → Giao 1 lần → điền Ngày giao → đổi sang Giao nhiều lần: form báo "Chọn nguồn tiêu
  thụ" cho ô không thấy; chọn đủ thì server báo "Hợp đồng giao nhiều lần không tự đánh dấu đã giao" —
  không xoá được Ngày giao trừ khi đổi lại loại giao. (Gốc cũ với `channel`, nay thêm một ô.)
- Sửa: khi `delivery_type` → `multi` thì xoá các ô của lần giao (`delivered_at, channel, to_company,
  source, invoice_*`); gate kiểm bằng `isBatch && isDelivery`.

### F4 — THẤP · Báo cáo lặng lẽ quy NULL → "Khai thác", trái chủ ý của chính commit
- `sales_contract_report.py:136-140` `source_of()` dùng ở báo cáo, lịch sử, Excel, thống kê. `core/db.py`
  ghi rõ "không gán bù… để khỏi che đường ghi quên khai nguồn" — nhưng tầng đọc lại che đúng chỗ đó.
- Nếu tồn tại lần giao đã giao + NULL nguồn (S3): báo cáo nói "Khai thác", bảng đợt giao/form hiện "—"
  và bắt chọn; ở kỳ ĐÃ CHỐT, sửa nội dung an toàn (đính hoá đơn) phải chọn nguồn → NULL→exploit bị coi
  là đổi số → buộc đi Đề nghị sửa.
- Sửa: thêm cảnh báo "N lần giao chưa khai nguồn" vào `warnings` báo cáo / luật ở trang Cảnh báo bất
  thường; cân nhắc CHECK DB (F5).

### F5 — THẤP · Không có ràng buộc DB cho `source`
- Cột `text` tự do. Giá trị lạ (SQL tay) → `by_source` có khoá lạ: Excel/summary chỉ lấy
  `exploit`/`purchase` (`sales_contract_consumption_summary.py:66`) → tổng nguồn ≠ tổng tiêu thụ; thống kê
  `_SOURCE_BUCKET` bỏ qua (`unit_report_consumption.py:55`), `group_by=source` rơi nhóm (key None).
- Sửa: `CHECK (source IS NULL OR source IN ('exploit','purchase'))`.

### F6 — THẤP · Chuyển tiếp: tab web mở từ trước deploy
- Không có cơ chế buộc tải lại bản mới. Bundle cũ không có ô Nguồn → mọi lần ghi nhận giao MỚI (form,
  Hoàn thành) bị 400 "Thiếu nguồn tiêu thụ" mà màn không có ô để chọn. Sửa HĐ đã giao vẫn qua (`...initial`
  mang `source` từ API đi tiếp). Chỉ cần nhắc đơn vị tải lại trang (Ctrl+Shift+R).

### F7 — THẤP · Hiển thị/nhất quán
- `ContractCompleteModal.tsx:33,36`: chọn sẵn `c.source` nhưng KHÔNG chọn sẵn `c.channel` — nguồn khai từ
  lúc ký có thể cũ mà người dùng không để ý.
- Lịch sử đợt giao: chỉ có cột nguồn từng dòng, dòng lũy kế không tách khai thác/thu mua.
- Diff đề nghị ở màn ĐƠN VỊ (không có `labels`) hiện mã thô `exploit/purchase` (giống `channel`).
- Nhật ký hoạt động: `audit-diff.ts:21` gắn nhãn chung "Nguồn" và đẩy khoá `source` xuống cuối (`:83`) như
  ô ngữ cảnh.

---

## 3. NGHI NGỜ — cần chạy SQL chỉ-đọc trên prod

- **S1 · TRUNG (cần chủ dự án chốt lại):** backfill gán `exploit` cho cả lần giao CHUYỂN TỪ biểu tiêu thụ cũ
  mảng `sales` = **mủ THU MUA**. Script `migrate-sales-contracts.py:135` ghi note
  "Chuyển từ dòng tiêu thụ cũ (mủ thu mua)" / "(mủ khai thác)" / "(mủ khai thác/mủ thu mua)". Tức là nguồn
  của giai đoạn trước 30/07/2026 VỐN ĐÃ BIẾT, nay bị ghi đè thành khai thác. Khách chốt "lần giao cũ =
  khai thác" có thể chưa biết phần này khôi phục được (trừ bản ghi gộp cả hai nguồn).
  `SELECT substring(note from '\(mủ [^)]*\)') k, count(*), min(delivered_at), max(delivered_at)
   FROM sales_contract WHERE note LIKE 'Chuyển từ dòng tiêu thụ cũ%' GROUP BY 1;`
- **S2 · HĐ cha multi dị thường** mang `delivered_at`/`source` (backfill gán nguồn + `deliveries()` đếm cả
  cha lẫn đợt): `SELECT count(*) FROM sales_contract WHERE parent_id IS NULL AND delivery_type='multi'
  AND (delivered_at IS NOT NULL OR source IS NOT NULL);`
- **S3 · Lần giao đã giao nhưng NULL nguồn** (SQL tay, clone DB, chạy lại script):
  `SELECT count(*) FROM sales_contract WHERE delivered_at IS NOT NULL AND source IS NULL
   AND (parent_id IS NOT NULL OR delivery_type='single');`
- **S4 · Số đề nghị bị F1:** `SELECT id, op, company FROM edit_request WHERE status='pending'
  AND op LIKE 'contract_%' AND before IS NOT NULL AND NOT (before ? 'source');`
- **S5 · Giá trị lạ:** `SELECT source, count(*) FROM sales_contract GROUP BY 1;`

---

## 4. Trả lời từng câu hỏi

1. **Đường ghi:** bảng mục 1 — đủ, chặn đúng; điểm yếu duy nhất ngoài API là backfill (S1, S2) và script cũ.
2. **Chốt số liệu:** ĐÚNG. `source` nằm trong `STAT_FIELDS` (`sales_contract_lock.py:36-40`), so ảnh chụp
   payload thô với bản DB; `_txt` coi ""/None là một. Hoàn thành gọi `assert_delivery_fences`, chuyển loại
   giao gọi `assert_switch_fences`, đề nghị sửa dùng cùng `is_safe_edit`. Không thấy đường lách cho tài
   khoản đơn vị (chuyên viên/admin không bị chặn — đúng thiết kế). Thiếu test.
3. **Đề nghị sửa:** payload cũ thiếu khoá → `_legacy_source` giữ nguồn đang lưu, lần giao chưa có nguồn
   → `exploit` (đúng chốt) ở cả precheck lẫn apply. Nhưng duyệt bị 409 do F1. Payload mới: nhãn
   "Nguồn tiêu thụ" + `labels.source` trên trang duyệt đúng; chỉ so khoá có trong payload.
4. **Báo cáo:** `source_of` luôn trả một trong hai giá trị ⇒ khai thác + thu mua = tổng tiêu thụ ở Báo cáo
   tiêu thụ, Excel 3 sheet, Thống kê (kể cả lọc chủng loại, gộp sáp nhập qua `sum_deep`). Chỉ vỡ khi có
   giá trị lạ (F5). Không phát sinh đếm trùng mới (multi cha bị ép NULL ngày giao); đếm trùng cũ chỉ nếu S2
   có dữ liệu. Excel ghi theo khoá cột → không lệch cột; colSpan web đếm lại khớp (14/11, 13/12, 13, footer 9+4).
5. **Web:** HĐ giao 1 lần gửi `source` trên chính HĐ; giao nhiều lần gửi trên từng đợt; HĐ cha multi không
   có ô và state mặc định `null` (không chọn sẵn) ⇒ **không có bẫy ô ẩn gửi giá trị mặc định**. Bẫy ô ẩn
   theo kiểu kiểm-ô-không-thấy: F3. Hoàn thành gửi `source` đúng; chuyển single→multi: F2.
6. **Test `test_sales_contract_source.py` phủ:** bắt buộc khi có ngày giao / giá trị lạ / chưa giao không
   bắt buộc; HĐ cha multi bỏ nguồn; đợt giao + `by_source` + lịch sử + lọc thống kê; Hoàn thành hỏi nguồn;
   chuyển single (đã giao) → multi; helper `_legacy_source`.
   **Còn thiếu:** (a) tài khoản đơn vị + kỳ đã chốt: chỉ đổi nguồn → bị chặn/đi đề nghị; sửa an toàn giữ
   nguyên nguồn → qua; (b) duyệt end-to-end đề nghị cũ có `before` thiếu `source` (lộ F1); (c) đề nghị
   mới đổi nguồn → duyệt ghi thật + gỡ chốt; (d) chuyển single CHƯA giao có nguồn → multi (F2);
   (e) Excel `consumption.xlsx`: cột "Nguồn tiêu thụ" 3 sheet, "Nhiều nguồn", tổng nguồn = tổng;
   (f) thống kê `group_by=source` + Excel thống kê; (g) gộp đơn vị sáp nhập giữ `by_source`;
   (h) Hoàn thành với nguồn sai giá trị / `no_delivery`; (i) bản ghi đã giao NULL nguồn (F4).

---

## 5. Việc nên làm (ưu tiên)
1. Đo S4 rồi vá `before` (F1) — trước khi Ban duyệt tiếp các đề nghị cũ.
2. Hỏi chủ dự án về S1 (khôi phục nguồn "mủ thu mua" từ note của bản ghi chuyển đổi).
3. Sửa F2 (điều kiện dời đợt) + F3 (xoá ô lần giao khi đổi sang multi).
4. CHECK DB (F5) + cảnh báo lần giao thiếu nguồn (F4).
5. Bổ sung test mục 6.

## Câu hỏi còn treo
- S1: giữ "mọi lần giao cũ = khai thác" hay khôi phục nguồn đã biết từ dữ liệu chuyển đổi?
- F2: HĐ giao 1 lần CHƯA giao khi chuyển sang nhiều lần — có muốn sinh đợt chờ giao không, hay chỉ khi đã giao?
