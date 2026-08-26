-- Số liệu cho ảnh "tình trạng nhập liệu của đơn vị". Mỗi dòng ra là chuỗi phân cách '|',
-- ký tự đầu là NHÓM (A/B/C) để script gom lại. Chạy với psql -tA (không header, không canh cột).
-- Tham số: :days = số ngày của kỳ xét "đã nộp chưa" · :until = ngày CUỐI kỳ (script truyền vào).
-- ⚠ Kỳ chốt tới :until chứ không phải CURRENT_DATE: báo cáo đốc thúc thường chốt tới HÔM QUA,
--   vì hôm nay chưa hết ngày, đơn vị chưa nhập là chuyện bình thường — kể vào là nhắc oan.

-- ── A) Tình trạng nộp trong kỳ: A|đơn vị|thu mua|tiêu thụ-tồn kho ──────────────────────────
-- Số = SỐ NGÀY đã nộp trong kỳ; 0 = chưa nhập; '-' = KHÔNG ÁP DỤNG.
-- ⚠ Hai luật dưới đây phải GIỐNG HỆT màn *Theo dõi nộp báo cáo* và bảng nhắc việc của đơn vị
--   (`unit_daily_fields.has_data` + `companies_with_purchase_plan`), nếu không ba nơi báo ba số
--   khác nhau và đơn vị bị nhắc oan:
--   1. Đơn vị phải nộp biểu Thu mua = có **số kế hoạch thu mua > 0** ở năm gần nhất ≤ năm nay
--      (cờ `member_unit.has_purchase_plan` đã BỎ từ 03/08/2026 — cột còn trong DB nhưng không dùng).
--   2. "Đã nộp" = payload có **ô số liệu THẬT của chính biểu đó**, không phải "có bản ghi":
--      biểu Tồn kho còn mang hàng trăm bản ghi cũ của biểu Tiêu thụ (chỉ có mảng `sales`) → đếm
--      theo bản ghi là báo tỷ lệ nộp ảo.
-- ⚠ CHỈ 2 biểu. Đơn giá mủ nguyên liệu nhập NGAY TRONG biểu Thu mua (ô "Đơn giá thu mua", lưu sang
--   kho giá `vrg_unit`) nên KHÔNG phải mục nộp riêng — tách ra thành cột thứ 3 là đếm trùng và báo
--   oan các đơn vị có ngày không tổ chức thu mua (ngày đó vốn không có giá). Thiếu giá xem nhóm D.
SELECT 'A|' || u.name || '|' ||
       CASE WHEN COALESCE((SELECT p.plan_tonnes > 0 FROM unit_purchase_plan p
                            WHERE p.company = u.name AND p.plan_tonnes IS NOT NULL
                              AND p.year <= EXTRACT(YEAR FROM CAST(:until AS date))
                            ORDER BY p.year DESC LIMIT 1), false) THEN
         (SELECT count(*) FROM unit_daily_report r
           WHERE r.company = u.name AND r.kind = 'purchase'
             AND r.as_of BETWEEN CAST(:until AS date) - (:days - 1) AND CAST(:until AS date)
             AND (EXISTS (SELECT 1 FROM jsonb_each(r.payload) e
                           WHERE e.key = ANY (ARRAY['latex_wet', 'coagulum', 'cup_raw',
                                   'cup_raw_price', 'rss_pressed', 'rss_pressed_price',
                                   'price_latex_local', 'price_cup_local', 'fx_purchase',
                                   'no_purchase'])
                             AND e.value NOT IN ('null'::jsonb, '""'::jsonb))
                  OR (jsonb_typeof(r.payload->'finished') = 'array'
                      AND jsonb_array_length(r.payload->'finished') > 0)))::text
       ELSE '-' END || '|' ||
       (SELECT count(*) FROM unit_daily_report r
         WHERE r.company = u.name AND r.kind = 'consumption'
           AND r.as_of BETWEEN CAST(:until AS date) - (:days - 1) AND CAST(:until AS date)
           AND (EXISTS (SELECT 1 FROM jsonb_each(r.payload) e
                         WHERE e.key IN ('no_stock', 'stock_material')
                           AND e.value NOT IN ('null'::jsonb, '""'::jsonb))
                OR (jsonb_typeof(r.payload->'stock_warehoused') = 'array'
                    AND jsonb_array_length(r.payload->'stock_warehoused') > 0)
                OR (jsonb_typeof(r.payload->'stock_not_warehoused') = 'array'
                    AND jsonb_array_length(r.payload->'stock_not_warehoused') > 0)))::text
  FROM member_unit u WHERE u.is_active ORDER BY u.sort_order, u.name;

-- ── D) Có tổ chức thu mua nhưng THIẾU ĐƠN GIÁ: D|đơn vị|ngày ───────────────────────────────
-- Lỗi thật của biểu Thu mua: đã nhập sản lượng mà bỏ trống ô đơn giá.
-- ⚠ Ngày bật cờ `no_purchase` (không tổ chức thu mua) thì KHÔNG có giá là ĐÚNG → loại ra.
--   Ngày có tổ chức mà mua được 0 tấn thì VẪN phải có giá đã công bố → giữ lại.
SELECT 'D|' || r.company || '|' || r.as_of::text
  FROM unit_daily_report r
 WHERE r.kind = 'purchase' AND r.payload <> '{}'::jsonb
   AND r.as_of BETWEEN CAST(:until AS date) - (:days - 1) AND CAST(:until AS date)
   AND COALESCE((r.payload->>'no_purchase')::bool, false) = false
   AND NOT EXISTS (SELECT 1 FROM fact_price f
                    WHERE f.source = 'vrg_unit' AND f.grade = r.company AND f.as_of = r.as_of
                      AND f.price_type IN ('purchase', 'purchase_cup'))
 ORDER BY r.company, r.as_of;

-- ── B) Giá mủ nguyên liệu SAI ĐƠN VỊ TÍNH: B|đơn vị|loại mủ|giá lớn nhất|số ô sai ──────────
-- Phải nhập ĐỒNG/ĐỘ (mặt bằng 100–1.500). Nhập đồng/kg hoặc đồng/tấn → số vọt lên hàng chục nghìn
-- đến hàng chục triệu. KHÔNG giới hạn kỳ: đây là lỗi còn tồn trên hệ thống, sửa lúc nào cũng cần.
SELECT 'B|' || grade || '|' || price_type || '|' || max(price)::bigint || '|' || count(*)
  FROM fact_price
 WHERE source = 'vrg_unit' AND price_type IN ('purchase', 'purchase_cup') AND price > 1500
 GROUP BY grade, price_type ORDER BY grade, price_type;

-- ── C) Giá bán ở HỢP ĐỒNG TIÊU THỤ sai đơn vị tính ─────────────────────────────────────────
-- C|đơn vị|số dòng|từ ngày|đến ngày|giá lớn nhất|tiền|thiếu tỷ giá|mã hợp đồng
-- VND phải nhập TRIỆU ĐỒNG/TẤN (mặt bằng 40–70) → > 200 là đã gõ nghìn/đồng trên tấn.
-- USD nhập USD/TẤN (mặt bằng 1.400–2.200) → > 10.000 là sai đơn vị.
-- ⚠ ĐỌC `sales_contract`, KHÔNG đọc mảng `sales`/`sales_own` trong `unit_daily_report` nữa.
--   Cơ chế khai tiêu thụ theo NGÀY đã bỏ: toàn bộ dòng bán cũ được chuyển sang hợp đồng (cờ
--   `sales_migrated` trên bản ghi ngày), mảng cũ chỉ còn nằm lại để tra cứu và KHÔNG có ô nào
--   trên form để sửa. Quét mảng cũ vừa báo oan (đơn vị không sửa được, mà bản hợp đồng đã đúng),
--   vừa BỎ SÓT lỗi thật đang nằm ở `sales_contract.lines`.
-- ⚠ Loại tiền lấy ngay ở dòng hợp đồng (`lines[].ccy`); dòng nào trống mới suy theo mặc định của
--   đơn vị (trong nước VND · nước ngoài USD). Bỏ bước này thì 2.680 USD/tấn bị đọc thành
--   2.680 triệu đ/tấn → báo oan đơn vị xuất khẩu.
-- Hợp đồng mẹ và phụ lục là hai dòng riêng: cùng một lỗi có thể đếm 2 lần, nhưng cả hai đều phải
-- sửa nên vẫn liệt kê đủ mã để đơn vị biết mở phiếu nào.
SELECT 'C|' || company || '|' || count(*) || '|' || COALESCE(min(d)::text, '')
       || '|' || COALESCE(max(d)::text, '') || '|' || max(price)::bigint
       || '|' || string_agg(DISTINCT ccy, ',') || '|' || bool_or(no_fx)::text
       || '|' || string_agg(DISTINCT code, ', ')
  FROM (
    SELECT c.company,
           COALESCE(NULLIF(c.code, ''), '(chưa có mã)') AS code,
           COALESCE(c.delivered_at, c.start_date, c.sign_date, c.completed_at) AS d,
           CASE WHEN ln->>'ccy' IN ('VND', 'USD') THEN ln->>'ccy'
                WHEN COALESCE(u.currency, 'VND') = 'VND' THEN 'VND' ELSE 'USD' END AS ccy,
           (ln->>'price')::numeric AS price,
           (ln->>'fx' IS NULL) AS no_fx
      FROM sales_contract c
      LEFT JOIN member_unit u ON u.name = c.company
      CROSS JOIN LATERAL jsonb_array_elements(COALESCE(c.lines, '[]'::jsonb)) AS ln
     WHERE (ln->>'price') ~ '^[0-9.]+$'
  ) t
 WHERE (ccy = 'VND' AND price > 200) OR (ccy = 'USD' AND price > 10000)
 GROUP BY company ORDER BY count(*) DESC, company;

-- ── E) TỒN KHO theo NGÀY: E|đơn vị|khu vực|các ngày ĐÃ nộp (YYYY-MM-DD, ngăn bằng dấu phẩy) ──
-- Dựng ma trận đơn vị × ngày y như màn *Theo dõi nộp báo cáo* (tab Tồn kho). Luật "đã nộp" dùng
-- CHUNG với nhóm A ở trên — sửa một chỗ phải sửa cả hai, nếu không hai bảng trong cùng một bộ ảnh
-- lại nói khác nhau.
SELECT 'E|' || u.name || '|' || COALESCE(u.region, '') || '|' ||
       COALESCE((SELECT string_agg(to_char(r.as_of, 'YYYY-MM-DD'), ',' ORDER BY r.as_of)
                   FROM unit_daily_report r
                  WHERE r.company = u.name AND r.kind = 'consumption'
                    AND r.as_of BETWEEN CAST(:until AS date) - (:days - 1) AND CAST(:until AS date)
                    AND (EXISTS (SELECT 1 FROM jsonb_each(r.payload) e
                                  WHERE e.key IN ('no_stock', 'stock_material')
                                    AND e.value NOT IN ('null'::jsonb, '""'::jsonb))
                         OR (jsonb_typeof(r.payload->'stock_warehoused') = 'array'
                             AND jsonb_array_length(r.payload->'stock_warehoused') > 0)
                         OR (jsonb_typeof(r.payload->'stock_not_warehoused') = 'array'
                             AND jsonb_array_length(r.payload->'stock_not_warehoused') > 0))), '')
  FROM member_unit u WHERE u.is_active ORDER BY u.sort_order, u.name;

-- ── F) THU MUA gom theo THÁNG: F|đơn vị|khu vực|phải nộp(t/f)|YYYY-MM:số ngày đã nộp,... ────
-- Dùng cho báo cáo kỳ DÀI (từ đầu năm): liệt kê từng ngày thiếu của 200+ ngày thì không ai đọc,
-- gom theo tháng mới thấy được đơn vị hụt ở giai đoạn nào.
-- Luật "phải nộp" và "đã nộp" dùng CHUNG với nhóm A — sửa thì sửa cả hai.
SELECT 'F|' || u.name || '|' || COALESCE(u.region, '') || '|' ||
       CASE WHEN COALESCE((SELECT p.plan_tonnes > 0 FROM unit_purchase_plan p
                            WHERE p.company = u.name AND p.plan_tonnes IS NOT NULL
                              AND p.year <= EXTRACT(YEAR FROM CAST(:until AS date))
                            ORDER BY p.year DESC LIMIT 1), false) THEN 't' ELSE 'f' END || '|' ||
       COALESCE((SELECT string_agg(m || ':' || c, ',' ORDER BY m)
                   FROM (SELECT to_char(r.as_of, 'YYYY-MM') AS m, count(*) AS c
                           FROM unit_daily_report r
                          WHERE r.company = u.name AND r.kind = 'purchase'
                            AND r.as_of BETWEEN CAST(:until AS date) - (:days - 1)
                                            AND CAST(:until AS date)
                            AND (EXISTS (SELECT 1 FROM jsonb_each(r.payload) e
                                          WHERE e.key = ANY (ARRAY['latex_wet', 'coagulum',
                                                  'cup_raw', 'cup_raw_price', 'rss_pressed',
                                                  'rss_pressed_price', 'price_latex_local',
                                                  'price_cup_local', 'fx_purchase', 'no_purchase'])
                                            AND e.value NOT IN ('null'::jsonb, '""'::jsonb))
                                 OR (jsonb_typeof(r.payload->'finished') = 'array'
                                     AND jsonb_array_length(r.payload->'finished') > 0))
                          GROUP BY 1) x), '')
  FROM member_unit u WHERE u.is_active ORDER BY u.sort_order, u.name;

-- ── G) KẾ HOẠCH NĂM khai thiếu: G|đơn vị|khu vực|5 ô theo thứ tự trên màn (t=đã khai, f=bỏ trống) ──
-- Thứ tự khớp cột của màn Kế hoạch năm: KH thu mua · KH tiêu thụ HĐ chuyến · HĐ dài hạn đã ký ·
-- HĐ dài hạn năm trước chuyển sang · HĐ chuyến năm trước chuyển sang.
-- ⚠ Số 0 là ĐÃ KHAI (nghĩa là "không có"), chỉ NULL mới là chưa khai — đừng gộp hai thứ này.
-- Đơn vị chưa có dòng nào của năm → LEFT JOIN cho ra cả 5 ô 'f'.
SELECT 'G|' || u.name || '|' || COALESCE(u.region, '') || '|' ||
       CASE WHEN p.plan_tonnes IS NULL THEN 'f' ELSE 't' END || '|' ||
       CASE WHEN p.plan_sales_spot_tonnes IS NULL THEN 'f' ELSE 't' END || '|' ||
       CASE WHEN p.signed_lt_tonnes IS NULL THEN 'f' ELSE 't' END || '|' ||
       CASE WHEN p.carry_lt_tonnes IS NULL THEN 'f' ELSE 't' END || '|' ||
       CASE WHEN p.carry_spot_tonnes IS NULL THEN 'f' ELSE 't' END
  FROM member_unit u
  LEFT JOIN unit_purchase_plan p
         ON p.company = u.name AND p.year = EXTRACT(YEAR FROM CAST(:until AS date))
 WHERE u.is_active ORDER BY u.sort_order, u.name;
