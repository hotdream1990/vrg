-- Số liệu cho ảnh "tình trạng nhập liệu của đơn vị". Mỗi dòng ra là chuỗi phân cách '|',
-- ký tự đầu là NHÓM (A/B/C) để script gom lại. Chạy với psql -tA (không header, không canh cột).
-- Tham số: :days = số ngày của kỳ xét "đã nộp chưa" (mặc định do script truyền vào).

-- ── A) Tình trạng nộp trong kỳ: A|đơn vị|thu mua|tiêu thụ-tồn kho ──────────────────────────
-- Số = SỐ NGÀY đã nộp trong kỳ; 0 = chưa nhập; '-' = KHÔNG ÁP DỤNG.
-- ⚠ Đơn vị không được giao kế hoạch thu mua (has_purchase_plan = false) thì KHÔNG phải nộp biểu
--   Thu mua → trả '-' để không tính là thiếu.
-- ⚠ CHỈ 2 biểu. Đơn giá mủ nguyên liệu nhập NGAY TRONG biểu Thu mua (ô "Đơn giá thu mua", lưu sang
--   kho giá `vrg_unit`) nên KHÔNG phải mục nộp riêng — tách ra thành cột thứ 3 là đếm trùng và báo
--   oan các đơn vị có ngày không tổ chức thu mua (ngày đó vốn không có giá). Thiếu giá xem nhóm D.
SELECT 'A|' || u.name || '|' ||
       CASE WHEN u.has_purchase_plan THEN
         (SELECT count(*) FROM unit_daily_report r
           WHERE r.company = u.name AND r.kind = 'purchase'
             AND r.as_of BETWEEN CURRENT_DATE - (:days - 1) AND CURRENT_DATE
             AND r.payload <> '{}'::jsonb)::text
       ELSE '-' END || '|' ||
       (SELECT count(*) FROM unit_daily_report r
         WHERE r.company = u.name AND r.kind = 'consumption'
           AND r.as_of BETWEEN CURRENT_DATE - (:days - 1) AND CURRENT_DATE
           AND r.payload <> '{}'::jsonb)::text
  FROM member_unit u WHERE u.is_active ORDER BY u.sort_order, u.name;

-- ── D) Có tổ chức thu mua nhưng THIẾU ĐƠN GIÁ: D|đơn vị|ngày ───────────────────────────────
-- Lỗi thật của biểu Thu mua: đã nhập sản lượng mà bỏ trống ô đơn giá.
-- ⚠ Ngày bật cờ `no_purchase` (không tổ chức thu mua) thì KHÔNG có giá là ĐÚNG → loại ra.
--   Ngày có tổ chức mà mua được 0 tấn thì VẪN phải có giá đã công bố → giữ lại.
SELECT 'D|' || r.company || '|' || r.as_of::text
  FROM unit_daily_report r
 WHERE r.kind = 'purchase' AND r.payload <> '{}'::jsonb
   AND r.as_of BETWEEN CURRENT_DATE - (:days - 1) AND CURRENT_DATE
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

-- ── C) Giá bán ở biểu Tiêu thụ SAI ĐƠN VỊ TÍNH: C|đơn vị|số dòng|từ ngày|đến ngày|giá|tiền|thiếu tỷ giá
-- VND phải nhập TRIỆU ĐỒNG/TẤN (mặt bằng 40–70) → > 200 là đã gõ đồng/tấn.
-- USD nhập USD/TẤN (mặt bằng 1.400–2.200) → > 10.000 là sai đơn vị.
-- ⚠ Loại tiền của dòng bán phải suy đúng như form nhập: dòng → ngày (`sales_ccy`) → mặc định của
--   đơn vị (trong nước VND · nước ngoài USD). Bỏ bước này thì 1.640 USD/tấn bị đọc thành
--   1.640 triệu đ/tấn → báo oan đơn vị nước ngoài.
SELECT 'C|' || company || '|' || count(*) || '|' || min(as_of)::text || '|' || max(as_of)::text
       || '|' || max(price)::bigint || '|' || string_agg(DISTINCT ccy, ',')
       || '|' || bool_or(no_fx)::text
  FROM (
    SELECT r.company, r.as_of,
           CASE WHEN s.ln->>'ccy' IN ('VND', 'USD') THEN s.ln->>'ccy'
                WHEN r.payload->>'sales_ccy' IN ('VND', 'USD') THEN r.payload->>'sales_ccy'
                WHEN COALESCE(u.currency, 'VND') = 'VND' THEN 'VND' ELSE 'USD' END AS ccy,
           (s.ln->>'price')::numeric AS price,
           (COALESCE(s.ln->>'fx', r.payload->>'fx_revenue') IS NULL) AS no_fx
      FROM unit_daily_report r
      LEFT JOIN member_unit u ON u.name = r.company
      CROSS JOIN LATERAL (
        SELECT jsonb_array_elements(COALESCE(r.payload->'sales', '[]'::jsonb)) AS ln
        UNION ALL
        SELECT jsonb_array_elements(COALESCE(r.payload->'sales_own', '[]'::jsonb))) s
     WHERE r.kind = 'consumption' AND (s.ln->>'price') ~ '^[0-9.]+$'
  ) t
 WHERE (ccy = 'VND' AND price > 200) OR (ccy = 'USD' AND price > 10000)
 GROUP BY company ORDER BY count(*) DESC, company;
