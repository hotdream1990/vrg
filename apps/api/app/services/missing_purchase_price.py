"""Ngày CÓ sản lượng thu mua mủ nguyên liệu mà CHƯA có đơn giá — MỘT luật cho mọi nơi nhắc.

Hai nơi dùng: nhóm "Có thu mua nhưng thiếu đơn giá" ở màn Cảnh báo bất thường (`anomaly_rules`)
và bảng nhắc việc ở đầu các màn của tài khoản nhập liệu (`member_checklist`). Chung một hàm để
quản trị, lãnh đạo đơn vị và người nhập liệu không bao giờ thấy hai con số khác nhau.

Bỏ qua loại mủ đơn vị đã KHAI RÕ "không có giá" (`unit_daily_fields.declared_no_price` — cờ
`no_price_*` hoặc đơn giá nội tệ = 0), khác hẳn "quên khai" (chốt 07/09/2026).

Đối chiếu THEO TỪNG LOẠI MỦ (mủ nước ↔ `purchase` · mủ chén ↔ `purchase_cup` · mủ dây ↔
`purchase_lace`). Xét chung "ngày đó có giá nào không" vừa nêu oan vừa bỏ lọt: ngày chỉ mua mủ
dây mà đã khai giá vẫn bị nêu (Chưmomray 09/09/2026), còn ngày có giá mủ nước nhưng quên giá mủ
chén thì lọt lưới.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import PURCHASE_PRICE_TYPES, PURCHASE_SOURCE_UNIT
from app.services import unit_daily_fields, unit_report_rows

#: (loại mủ, ô sản lượng, loại giá trong kho) — dựng từ hằng số dùng chung để thêm loại mủ mới
#: KHÔNG phải sửa ở đây. Viết tay `IN ('purchase', 'purchase_cup')` là bỏ quên MỦ DÂY: luật
#: thiếu-đơn-giá từng nêu oan Chưmomray 09/09/2026 (đã khai `purchase_lace` = 520,5 đ/độ).
MATS = tuple((mat, qty_key, ptype) for mat, qty_key, _price_key, ptype
             in unit_report_rows.PURCHASE_MATERIALS)

#: Cách khai "ngày không có giá" — đơn vị hay để TRỐNG ô giá ở ngày nhập sản lượng chênh lệch
#: (mủ dư sau chế biến) vì nghĩ "không có giá thì khỏi điền", mà trống thì máy không phân biệt được
#: với quên nhập. Chỉ đúng cách khai ngay tại chỗ bị nhắc (chủ dự án yêu cầu 13/10/2026).
HOW_TO_DECLARE = ("Nếu đó là sản lượng chênh lệch thu mua (mủ dư sau chế biến nhập lại, không có "
                  "giá): gõ 0 vào ô đơn giá của loại mủ đó rồi lưu. Ngày đã khoá thì gõ 0 rồi bấm "
                  "Đề nghị sửa để Ban duyệt.")


def _qty(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def find(date_from: str, date_to: str, companies: list[str] | None = None) -> list[dict[str, Any]]:
    """`[{company, as_of, materials: {loại mủ: tấn}}]` xếp theo đơn vị rồi ngày.

    Chỉ xét ngày CÓ tổ chức thu mua (không tích `no_purchase`). `companies` None = mọi đơn vị.
    """
    ensure_schema()
    # Ô sản lượng đọc qua CASE có chốt chặn regex: payload là jsonb tự do, ép kiểu thẳng sẽ ném
    # lỗi nếu có bản ghi lỡ lưu chuỗi. Mệnh đề dựng từ `MATS` nên thêm loại mủ là tự có mặt.
    lacks = " OR ".join(
        f"(CASE WHEN r.payload->>'{qty_key}' ~ '^[0-9.]+$' "
        f"      THEN (r.payload->>'{qty_key}')::numeric ELSE 0 END > 0 "
        f" AND NOT ('{ptype}' = ANY(COALESCE(p.have, ARRAY[]::text[]))))"
        for _mat, qty_key, ptype in MATS)
    only = companies is not None
    # Giá gom MỘT LẦN theo khoảng ngày cố định rồi LEFT JOIN — KHÔNG hỏi `fact_price` bằng truy vấn
    # con theo từng dòng. `fact_price` là hypertable (~140 chunk): truy vấn con tương quan không
    # loại được chunk lúc lập kế hoạch → chi phí ước lượng vượt ngưỡng JIT, Postgres bỏ ~5 giây
    # BIÊN DỊCH trong khi chạy thật chỉ ~20ms (đo 13/09/2026, cả trang chờ vì luật này).
    with session_scope() as db:
        rows = db.execute(text(
            "WITH p AS ("
            "  SELECT grade AS company, as_of, array_agg(DISTINCT price_type) AS have "
            "  FROM fact_price WHERE source = :src AND price_type = ANY(:ptypes) "
            "  AND as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date) "
            + ("  AND grade = ANY(:units) " if only else "") +
            "  GROUP BY grade, as_of) "
            "SELECT r.as_of, r.company, r.payload, COALESCE(p.have, ARRAY[]::text[]) AS have "
            "FROM unit_daily_report r "
            "LEFT JOIN p ON p.company = r.company AND p.as_of = r.as_of "
            "WHERE r.kind = 'purchase' AND r.payload <> '{}'::jsonb "
            "AND r.as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date) "
            + ("AND r.company = ANY(:units) " if only else "") +
            "AND COALESCE((r.payload->>'no_purchase')::bool, false) = false "
            f"AND ({lacks}) "
            "ORDER BY r.company, r.as_of"),
            {"a": date_from, "b": date_to, "src": PURCHASE_SOURCE_UNIT,
             "ptypes": list(PURCHASE_PRICE_TYPES), "units": list(companies or [])}
        ).mappings().all()
    out = []
    for r in rows:
        payload = dict(r["payload"] or {})
        declared = unit_daily_fields.declared_no_price(payload)
        have = set(r["have"] or [])
        missing = {}
        for mat, qty_key, ptype in MATS:
            qty = _qty(payload.get(qty_key))
            if qty > 0 and mat not in declared and ptype not in have:
                missing[mat] = qty
        if missing:
            out.append({"company": r["company"], "as_of": str(r["as_of"]), "materials": missing})
    return out
