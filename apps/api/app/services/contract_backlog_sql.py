"""SQL của `contract_backlog` — tách riêng cho file logic gọn (quy ước < 200 dòng / file).

Tham số: `:d` ngày tính · `:y0` 01/01 năm của ngày tính · `:cs` đơn vị.
Chỗ cắm: `{scope}` (lọc đơn vị). Lọc chủng loại làm ở Python (`contract_backlog._master_totals`).
"""

from __future__ import annotations

#: Một dòng chi tiết → SL nước · quy khô đã khai · số theo `sales_contract_calc.sale_qty` (khô nếu
#: có, không thì nước). Giữ ĐỦ BA để Python chọn gốc trừ theo từng chủng loại (xem
#: `contract_backlog._master_totals`) — chọn gốc riêng từng vế thì cam kết latex không khai quy khô
#: (1.000 t nước) bị trừ phần đã giao tính theo khô (180 t) → "còn 820 t" ảo.
_LINE_SQL = ("COALESCE(e->>'grade', '') AS grade, "
             "COALESCE(NULLIF(e->>'qty', '')::numeric, 0) AS wet, "
             "COALESCE(NULLIF(e->>'qty_dry', '')::numeric, 0) AS dry, "
             "COALESCE(NULLIF(NULLIF(e->>'qty_dry', '')::numeric, 0), "
             "NULLIF(e->>'qty', '')::numeric, 0) AS sale")

#: Mỗi HĐ mẹ có cam kết, hiệu lực chồng lên năm của `:d` → MỘT DÒNG MỖI CHỦNG LOẠI (có trong cam
#: kết HOẶC đã giao) kèm số cam kết + đã giao LŨY KẾ tới hết `:d`. Không lọc chủng loại ở SQL: một
#: HĐ mẹ có được tính hay không là chuyện của cả hồ sơ — lọc ở đây thì phụ lục của nó nhảy sang ô
#: "dài hạn ngoài HĐ mẹ" khi đổi bộ lọc; Python lọc lúc cộng.
#: Đã giao = phụ lục giao-1-lần (chính nó có ngày giao) + đợt giao của phụ lục — cùng luật khối 3.
MASTER_SQL = f"""
WITH m AS (
    SELECT id, company, code, master_type, customer_id, sign_date, expiry_date, lines
      FROM master_contract
     WHERE (sign_date IS NULL OR sign_date <= CAST(:d AS date))
       AND (expiry_date IS NULL OR expiry_date >= CAST(:y0 AS date))
       {{scope}}
), annex AS (
    SELECT id, master_id, lines, delivered_at FROM sales_contract
     WHERE parent_id IS NULL AND master_id IN (SELECT id FROM m)
), done AS (
    SELECT a.master_id AS id, a.lines FROM annex a
     WHERE a.delivered_at IS NOT NULL AND a.delivered_at <= CAST(:d AS date)
    UNION ALL
    SELECT a.master_id AS id, k.lines FROM sales_contract k JOIN annex a ON k.parent_id = a.id
     WHERE k.delivered_at IS NOT NULL AND k.delivered_at <= CAST(:d AS date)
), cg AS (
    SELECT m.id, l.grade, sum(l.wet) AS wet, sum(l.dry) AS dry, sum(l.sale) AS sale
      FROM m CROSS JOIN LATERAL (SELECT {_LINE_SQL} FROM jsonb_array_elements(m.lines) e) l
     GROUP BY 1, 2
), dg AS (
    SELECT d.id, l.grade, sum(l.wet) AS wet, sum(l.dry) AS dry, sum(l.sale) AS sale,
           count(*) FILTER (WHERE l.dry = 0) AS no_dry
      FROM done d CROSS JOIN LATERAL (SELECT {_LINE_SQL} FROM jsonb_array_elements(d.lines) e) l
     GROUP BY 1, 2
), keep AS (SELECT id FROM cg GROUP BY id HAVING sum(sale) > 0
), g AS (SELECT id, grade FROM cg UNION SELECT id, grade FROM dg)
SELECT m.id, m.company, m.code, m.master_type, m.customer_id, m.sign_date, m.expiry_date,
       g.grade, COALESCE(cg.wet, 0) AS commit_wet, COALESCE(cg.dry, 0) AS commit_dry,
       COALESCE(dg.wet, 0) AS done_wet, COALESCE(dg.dry, 0) AS done_dry,
       COALESCE(dg.sale, 0) AS done_sale, COALESCE(dg.no_dry, 0) AS done_no_dry
  FROM m
  JOIN keep ON keep.id = m.id
  JOIN g ON g.id = m.id
  LEFT JOIN cg ON cg.id = g.id AND cg.grade = g.grade
  LEFT JOIN dg ON dg.id = g.id AND dg.grade = g.grade
 ORDER BY m.company, m.id, g.grade
"""
