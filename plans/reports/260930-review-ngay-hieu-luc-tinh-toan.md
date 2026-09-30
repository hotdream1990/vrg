# Review ngày hiệu lực theo dòng (0b68ca2 + f7c9943) — góc TÍNH SỐ & BÁO CÁO

Chạy trên `vrg_test`. File kiểm của `test_contract_line_from_date.py` qua 7/7. Nhóm test hợp đồng,
backlog, chốt số liệu, cảnh báo bất thường, bảng nhắc, HĐ mẹ qua 134/134. Các tình huống dựng thêm
nằm ở scratchpad (`test_fd_adversarial.py`, 8 ca).

## ĐÃ XÁC NHẬN (xếp theo mức độ)
1. **[TB] Đợt giao được ghi TRƯỚC ngày hiệu lực của dòng cùng chủng loại mà không bị kiểm.** HĐ giao
   1 lần thì bị chặn (`sales_contract_calc.py:59`), còn đợt giao chỉ kiểm ngày ký
   (`sales_contract_repo.py:202`). Hàng đó không có dòng `c` ⇒ rơi vào `spill`
   (`sales_contract_report.py:261`) ⇒ tách theo chủng loại của khối 3 bị sai.
   Ví dụ: ký 10/09 SVR10 10 t · thêm SVR 3L 6 t từ 15/09 · đợt giao 12/09 là SVR 3L 6 t (lưu được, 200).
   Khối 3 ngày 12–14 = **4 t và ghi là "SVR 10"** (thực tế SVR10 vẫn còn 10), sang 15/09 nhảy lên SVR10 10
   dù SVR10 không có biến động nào. Tổng vẫn nhất quán (10−6, rồi 16−6), nhưng các chỗ đọc `by_grade` sai
   trong những ngày đó: lưới ngày, `stock_hd_by_grade` của báo cáo kỳ, Trợ lý `group_by=grade`.
   Biến thể cùng chủng loại: giao 14 t ngày 12 vẫn lọt trần 110%, vì trần tính trên mọi dòng (16) chứ
   không trên phần đang hiệu lực (10).
   Sửa: trong `_assert_rules`, nhánh đợt giao có `delivered_at` ⇒ mỗi chủng loại của đợt phải có một dòng
   HĐ cùng chủng loại hiệu lực ≤ ngày giao. Ngược lại, khi sửa HĐ thì chặn `from_date` muộn hơn đợt đã
   giao có chủng loại đó, nếu chủng loại ấy chưa có dòng nào hiệu lực sớm hơn. Web làm tương tự.
2. **[Thấp–TB] `member_data_check.py:154` lấy ngày cảnh báo giá theo `from_date` thay vì `delivered_at`
   của HĐ giao 1 lần đã giao.** Hệ quả là cờ `editable` tính trên một ngày cũ hơn. Kiểm: ký 01/09, giao
   29/09, dòng từ 05/09 giá 40.000, `editable_from` = 23/09 ⇒ mục ra `as_of` 2026-09-05, `editable=False`
   ("nhờ Ban TTKD"), trong khi đơn vị vẫn tự sửa được. Cửa sổ sửa bám ngày giao. Bên
   `anomaly_rules.py:133` lại ưu tiên `delivered_at` ⇒ hai màn nói hai ngày khác nhau.
   Sửa: chỉ dùng `from_date` khi `k.delivered_at` NULL. Kèm theo: điều kiện WHERE (dòng 46) vẫn lọc theo
   ngày ký, nên dòng thêm trong năm nay vào HĐ ký năm ngoái không bao giờ được soát giá.
3. **[Thấp] `set_completion` nhận ngày hoàn thành trước `from_date` muộn nhất**
   (`sales_contract_lifecycle.py:84`, chỉ so với ngày ký và lần giao cuối). Kiểm: hoàn thành 13/09 khi
   có dòng từ 20/09 ⇒ 200. Dòng đó không bao giờ vào khối 3 nhưng vẫn nằm trong SL/thành tiền HĐ và dòng
   Tổng cộng. Nên chặn, hoặc ít nhất cảnh báo. `minGiao` ở web chỉ chặn ngày giao, không chặn ngày hoàn thành.
4. **[Thấp] Ngày hiệu lực mất lặng lẽ khi ngày ký đi qua nó.** `calc.py:62` và web `fromDateOut`
   (`ContractFormModal.tsx:183`) đổi thành NULL khi trùng ngày ký. Chuỗi thao tác: ký 10 → sửa ngày ký 15
   (dòng B từ 15 thành NULL) → sửa lại 10 ⇒ B có hiệu lực từ 10, cộng ngược 6 t vào 10–14, không ai
   được báo. Đúng thiết kế đã chốt, nhưng là một thay đổi số liệu không lời nhắc. Web nên cảnh báo khi đổi
   ngày ký mà có dòng đang mang ngày riêng.

## CÓ THỂ LÀ LỖI (cần chủ dự án chốt)
5. "Hợp đồng ký mới trong kỳ" (Trợ lý `get_contract_summary`, bộ lọc ngày của danh sách —
   `sales_contract_report.py:443-446`) tính cả dòng có hiệu lực ở kỳ sau vào kỳ ký. Ví dụ HĐ ký tháng 9
   thêm 6 t hiệu lực tháng 10: 6 t đó nằm ở tháng 9, không nằm ở tháng 10. Plan xếp đây là số "hiện tại"
   nhưng thực chất nó là số THEO KỲ.
6. `anomaly_rules.py:133`: dòng có ngày trong tương lai (> `date_to`) với giá sai nay bị ẩn khỏi
   `wrong_sale_price` cho tới khi tới ngày. Trước đây nó được gắn ngày ký. Hơi ngược ý "lỗi tồn đọng".
7. Không có chặn trên theo thời hạn HĐ: `from_date` 31/12 trên HĐ hết hạn 12/09 vẫn lưu được (đã kiểm).
   Khối 3 không lọc theo hạn nên không sai số, chỉ là dữ liệu vô nghĩa.
8. Nên làm chắc thêm: `CAST(e->>'from_date' AS date)` (`report.py:201`) và `::date` (`anomaly:133`).
   Chỉ một giá trị hỏng là mọi màn dùng khối 3 và trang cảnh báo lỗi 500. Đã rà mọi đường ghi: `repo.save`
   chuẩn hoá ISO, lifecycle bỏ khoá này, script migrate không ghi ⇒ hiện chỉ SQL tay mới gây ra được.
   Có thể thêm `CASE WHEN … ~ '^\d{4}-\d{2}-\d{2}$'` để phòng.
9. Loại lỗi có từ trước nhưng tính năng này làm lộ rõ hơn:
   - `_sync_group_inventory` (`repo.py:299`) chỉ tính lại tuần hiện hành ⇒ dòng lùi ngày về tuần trước
     không cập nhật "đã có HĐ" của tuần đó.
   - HĐ vẫn sửa tự do ⇒ `from_date` ≤ ngày chốt vẫn đổi được số khối 3 đã chốt (đúng như plan chốt).

## KHÔNG CÓ LỖI (đã kiểm)
- Mọi chỗ tính theo ngày đều đi qua `_BLOCK3_SQL`: `unit_daily_repo.contracts_on`, rồi tới
  unit_report_rows, unit_period_report, data_lock_summary, unit_week_snapshot, inventory_daily/auto,
  timeline_totals; `contract_backlog.backlog_on`, rồi tới dashboard outlook; router `/undelivered`;
  Trợ lý. Không có SQL nào khác tính cam kết theo ngày từ dòng HĐ.
- Các số "hiện tại" cố ý tính mọi dòng, đúng thiết kế: `_ANNEX_SQL`, `MASTER_SQL` (dòng của HĐ mẹ, không
  có `from_date`), `parents_with_progress`, `remaining_dry_by_id` (9999-12-31).
- `INNER JOIN c` khi chưa dòng nào có hiệu lực: HĐ vắng khỏi khối 3, cam kết = 0. Đúng (ca B: 0 cho tới 20/09).
- Gốc khô/nước: `clean_lines` bắt buộc quy khô với nhóm DRY và cấm với nhóm còn lại ở MỌI lần lưu ⇒ hai
  dòng cùng chủng loại luôn cùng gốc. Latex (ca D): 1,8 → 3,3, số "mọi lúc" 3,3.
- Luật lọc HĐ đã hoàn thành giữ nguyên.
- HĐ giao 1 lần: `from_date` ≤ ngày giao bị ép cả ở luồng chốt hoàn thành (ca E: 400, câu báo rõ).
- Chuyển loại giao: 1→nhiều bỏ khoá khi sao xuống đợt; nhiều→1 giữ lại. Đúng.
- `_from_key` gom đúng các trường hợp trùng ngày ký, là đợt giao, hay NULL. Payload khác định dạng chỉ
  làm `is_safe_edit` chặt hơn, không lỏng hơn.
- Đề nghị sửa giữ `from_date` qua `ContractIn`; lúc duyệt đi qua `repo.save` nên qua `clean`.
- Định dạng lạ ('20260915', '…T23:30+07:00', '2026-09-15xyz') đều chuẩn hoá về '2026-09-15'. Hơi dễ dãi
  nhưng an toàn. Web gửi YYYY-MM-DD nên không bị lệch ngày do múi giờ UTC.

## Câu hỏi còn treo
- Ca 1: đợt giao trước ngày hiệu lực nên CHẶN hay CHO QUA rồi chấp nhận `spill`?
- Ca 5: "ký mới trong kỳ" có tách phần tăng thêm theo ngày hiệu lực không?
- Chưa sửa plan.md (nhiều agent rà cùng lúc) — agent chính cập nhật mục "Rà soát".
