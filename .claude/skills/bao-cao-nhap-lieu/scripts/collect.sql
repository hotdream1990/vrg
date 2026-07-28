-- Số liệu cho ảnh "tình trạng nhập liệu của đơn vị". Mỗi dòng ra là chuỗi phân cách '|',
-- ký tự đầu là NHÓM (A/B/C) để script gom lại. Chạy với psql -tA (không header, không canh cột).
-- Tham số: :days = số ngày của kỳ xét "đã nộp chưa" (mặc định do script truyền vào).

-- ── A) Tình trạng nộp trong kỳ: A|đơn vị|thu mua|tiêu thụ-tồn kho|giá mủ ───────────────────
-- Số = SỐ NGÀY đã nộp trong kỳ; 0 = chưa nhập; '-' = KHÔNG ÁP DỤNG.
-- ⚠ Đơn vị không được giao kế hoạch thu mua (has_purchase_plan = false) thì KHÔNG phải nộp biểu
--   Thu mua → trả '-' để không tính là thiếu.
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
           AND r.payload <> '{}'::jsonb)::text || '|' ||
       -- Giá mủ nguyên liệu: tính CẢ mủ nước lẫn mủ chén (đơn vị chỉ mua mủ chén vẫn là đã nhập).
       (SELECT count(DISTINCT p.as_of) FROM fact_price p
         WHERE p.source = 'vrg_unit' AND p.grade = u.name
           AND p.price_type IN ('purchase', 'purchase_cup')
           AND p.as_of BETWEEN CURRENT_DATE - (:days - 1) AND CURRENT_DATE)::text
  FROM member_unit u WHERE u.is_active ORDER BY u.sort_order, u.name;

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
