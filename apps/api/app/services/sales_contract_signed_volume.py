"""Sản lượng CAM KẾT KÝ trong một kỳ, tính theo NGÀY HIỆU LỰC của từng dòng hợp đồng (30/09/2026).

Hợp đồng ký 20/08 thêm 6 tấn hiệu lực từ 15/09: 6 tấn đó là cam kết ký trong tháng 9, không phải
tháng 8. Cộng theo ngày ký của hợp đồng (như danh sách hợp đồng lọc theo ngày ký) sẽ dồn phần tăng
về kỳ ký. Dòng không khai ngày = ngày ký, nên hợp đồng không bổ sung gì cho ra đúng số cũ.
Sản lượng là ô SL của dòng (mủ nước với latex) — cùng gốc với `_QTY_SQL` của danh sách hợp đồng.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

#: ⚠ Mẫu dùng `.format(scope=…)` → ngoặc nhọn của regex phải viết đôi.
_SQL = """
SELECT p.company,
       COALESCE(sum(l.qty), 0) AS qty,
       COALESCE(sum(l.qty) FILTER (WHERE p.sign_date < CAST(:df AS date)), 0) AS topup_qty,
       count(DISTINCT p.id) FILTER (WHERE p.sign_date < CAST(:df AS date)) AS topup_contracts
  FROM sales_contract p
  CROSS JOIN LATERAL (
      SELECT COALESCE(NULLIF(e->>'qty', '')::numeric, 0) AS qty,
             CASE WHEN e->>'from_date' ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'
                  THEN CAST(e->>'from_date' AS date) ELSE p.sign_date END AS eff
        FROM jsonb_array_elements(COALESCE(p.lines, '[]'::jsonb)) e) l
 WHERE p.parent_id IS NULL
   AND l.eff BETWEEN CAST(:df AS date) AND CAST(:dt AS date)
   {scope}
 GROUP BY p.company
"""


def by_company(date_from: str, date_to: str,
               companies: list[str] | None = None) -> dict[str, dict[str, float]]:
    """{đơn vị: {qty, topup_qty, topup_contracts}} — cam kết có hiệu lực trong [date_from, date_to].

    `topup_qty` = phần BỔ SUNG trong kỳ của hợp đồng ký TRƯỚC kỳ (không nằm trong số hợp đồng ký
    trong kỳ), `topup_contracts` = số hợp đồng đó.
    """
    if companies is not None and not companies:
        return {}
    params: dict[str, Any] = {"df": date_from, "dt": date_to}
    scope = ""
    if companies is not None:
        scope, params["cs"] = "AND p.company = ANY(:cs)", list(companies)
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(_SQL.format(scope=scope)), params).mappings().all()
    return {r["company"]: {"qty": float(r["qty"]), "topup_qty": float(r["topup_qty"]),
                           "topup_contracts": int(r["topup_contracts"])} for r in rows}
