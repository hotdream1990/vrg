# Ngày hiệu lực theo dòng chủng loại của hợp đồng (30/09/2026)

## Yêu cầu (chủ dự án)
Hợp đồng khai SL ban đầu, sau đó điều chỉnh thêm/bớt. "Đã ký HĐ chưa giao" theo ngày đang tính
ngược: ngày 10 ký 10 t, ngày 15 thêm 6 t ⇒ đúng ra 10–14 chưa giao 10 t, từ 15 chưa giao 16 t.
- Thêm **ngày hiệu lực cho từng dòng chủng loại** của HỢP ĐỒNG. Chỉ được từ ngày ký trở đi; không
  khai = theo ngày ký.
- Chỉ hiện khi SỬA hợp đồng; lúc tạo form giữ tối giản như cũ.
- Ảnh hưởng báo cáo, đề nghị sửa và các chức năng liên đới.

## Chốt nghiệp vụ (AskUserQuestion 30/09/2026)
1. **Tăng** = thêm dòng mới cùng chủng loại + ngày hiệu lực. **Giảm** = sửa thẳng số dòng (áp dụng
   từ ngày hiệu lực của chính dòng đó). KHÔNG có dòng âm.
2. **Chốt số liệu giữ như cũ**: hợp đồng vẫn sửa tự do (chỉ lần giao bị chốt). Ngày hiệu lực chỉ để
   tính đúng số chưa giao theo ngày; đề nghị sửa hiện thêm ô ngày để Ban duyệt thấy.

## Thiết kế
- `lines[].from_date` (jsonb, không migration). NULL/không có khoá = theo ngày ký. Ngày TRÙNG ngày
  ký vẫn giữ nguyên (rà soát: sửa nhầm ngày ký 10 → 15 → 10 từng làm dòng "từ 15" mất ngày).
- Luật (`sales_contract_line_dates.py`): `from_date ≥ sign_date`; HĐ giao 1 lần đã giao ⇒
  `from_date ≤ delivered_at`; đợt giao có chủng loại X không được trước ngày SỚM NHẤT có dòng X
  (kiểm cả khi thêm đợt lẫn khi dời ngày dòng trên HĐ); hoàn thành ≥ ngày hiệu lực muộn nhất.
  Đợt giao: bỏ khoá (ngày của đợt là ngày giao).
- Khối 3 (`_BLOCK3_SQL.commit_g`): chỉ cộng dòng có hiệu lực ≤ ngày tính. Mọi báo cáo theo ngày đi
  qua `undelivered_on` nên tự đúng (lưới nhập ngày, thống kê tồn kho, báo cáo kỳ, chốt số liệu,
  snapshot tuần, dashboard, còn phải giao, tồn kho Tập đoàn, trợ lý AI).
- Số "hiện tại/mọi lúc" (còn phải giao ở màn HĐ, tiến độ, thành tiền) tính MỌI dòng — giữ nguyên.
- `sales_contract_lock._lines_key` thêm `from_date` (đổi ngày hiệu lực = đổi số liệu).
- Chuyển giao 1 lần → nhiều lần: bỏ `from_date` khỏi dòng sao xuống đợt giao.
- Bảng nhắc đơn vị (`member_data_check`): dòng chưa giao nhắc theo ngày hiệu lực, soát cả dòng mới
  thêm vào HĐ ký từ lâu. Trang Cảnh báo bất thường giữ ngày cũ (lấy ngày dòng thì dòng hiệu lực
  tương lai bị ẩn cảnh báo).
- SQL khối 3 dùng CASE + regex: một chuỗi ngày hỏng ghi bằng SQL tay không làm sập báo cáo.
- Bảng so sánh đề nghị sửa: dòng không ngày hiện "Theo ngày ký" thay vì "(trống)".

## Việc
- [x] Backend: schema · calc.clean_lines · clean · lock key · block3 SQL · lifecycle · anomaly/check
- [x] Web: type · ContractLinesTable cột "Hiệu lực từ" (chỉ khi sửa HĐ) · form kiểm tra · chi tiết · nhãn diff
- [x] Test: tests/test_contract_line_from_date.py
- [x] Sổ tay đơn vị + changelog
- [x] Rà soát (code-reviewer) + test tay trên trình duyệt

## Kết quả (30/09/2026)
- 781 test pass trên DB sạch `vrg_test` (12 test mới: `test_contract_line_from_date.py`,
  `test_edit_request_line_from_date.py`); ruff + `pnpm build` sạch.
- Thử trên trình duyệt: HĐ 10 t ký 10/09 + dòng 6 t từ 15/09 ⇒ chưa giao 10 t (10–14/09), 16 t từ
  15/09 ở cả API lẫn Báo cáo tiêu thụ. Form tạo mới + form đợt giao không có ô ngày.
- Rà soát 2 góc: `plans/reports/260930-review-ngay-hieu-luc-{tinh-toan,luong-sua}.md` — đã vá hết
  lỗi xác nhận. Để lại (chưa làm): "HĐ ký mới trong kỳ" của Trợ lý vẫn tính cả phần tăng vào kỳ ký;
  không chặn ngày hiệu lực sau thời hạn HĐ; tồn kho Tập đoàn chỉ tính lại tuần hiện hành.
