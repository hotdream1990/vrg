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
- `lines[].from_date` (jsonb, không migration). NULL/không có khoá = theo ngày ký. Server chuẩn hoá:
  bằng ngày ký ⇒ lưu NULL (dòng mặc định đi theo ngày ký khi đổi ngày ký).
- Luật: `from_date ≥ sign_date`; HĐ giao 1 lần đã có ngày giao ⇒ `from_date ≤ delivered_at`.
  Đợt giao: bỏ khoá (ngày của đợt là ngày giao).
- Khối 3 (`_BLOCK3_SQL.commit_g`): chỉ cộng dòng có hiệu lực ≤ ngày tính. Mọi báo cáo theo ngày đi
  qua `undelivered_on` nên tự đúng (lưới nhập ngày, thống kê tồn kho, báo cáo kỳ, chốt số liệu,
  snapshot tuần, dashboard, còn phải giao, tồn kho Tập đoàn, trợ lý AI).
- Số "hiện tại/mọi lúc" (còn phải giao ở màn HĐ, tiến độ, thành tiền) tính MỌI dòng — giữ nguyên.
- `sales_contract_lock._lines_key` thêm `from_date` (đổi ngày hiệu lực = đổi số liệu).
- Chuyển giao 1 lần → nhiều lần: bỏ `from_date` khỏi dòng sao xuống đợt giao.
- Cảnh báo giá bán sai đơn vị (`anomaly_rules`, `member_data_check`) lấy ngày của dòng nếu có.

## Việc
- [ ] Backend: schema · calc.clean_lines · clean · lock key · block3 SQL · lifecycle · anomaly/check
- [ ] Web: type · ContractLinesTable cột "Hiệu lực từ" (chỉ khi sửa HĐ) · form kiểm tra · chi tiết · nhãn diff
- [ ] Test: tests/test_contract_line_from_date.py
- [ ] Sổ tay đơn vị + changelog
- [ ] Rà soát (code-reviewer) + test tay trên trình duyệt
