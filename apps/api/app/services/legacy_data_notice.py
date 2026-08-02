"""Đếm DỮ LIỆU CŨ CHƯA CHUYỂN ĐỔI trong một kỳ để báo cáo nói rõ thay vì hiện số 0.

Từ 02/08/2026 báo cáo chỉ đọc cơ chế hợp đồng mới (`sales_contract`). Hai kho cũ —
`unit_stock_contract` (đã ký HĐ chưa giao) và hai mảng `sales`/`sales_own` trong bản ghi tiêu thụ
theo ngày — nằm im chờ `scripts/migrate-sales-contracts.py`.

Không cảnh báo thì một kỳ toàn dữ liệu cũ sẽ hiện 0 tấn, người đọc hiểu là "không bán gì".
"""

from __future__ import annotations

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope

#: Hợp đồng cũ CHƯA chuyển còn hiệu lực trong kỳ (mở trước khi kỳ kết thúc, giao sau khi kỳ bắt đầu).
_CONTRACTS = ("SELECT count(*) FROM unit_stock_contract WHERE NOT migrated "
              " AND (start_date IS NULL OR start_date <= CAST(:dt AS date)) "
              " AND (delivered_date IS NULL OR delivered_date >= CAST(:df AS date))")

#: NGÀY tiêu thụ cũ CHƯA chuyển mà thực sự có dòng bán.
_SALE_DAYS = ("SELECT count(*) FROM unit_daily_report WHERE kind = 'consumption' "
              " AND as_of >= CAST(:df AS date) AND as_of <= CAST(:dt AS date) "
              " AND COALESCE((payload->>'sales_migrated')::boolean, false) = false "
              " AND (jsonb_array_length(COALESCE(payload->'sales', '[]'::jsonb)) > 0 "
              "      OR jsonb_array_length(COALESCE(payload->'sales_own', '[]'::jsonb)) > 0)")


def pending(date_from: str, date_to: str, companies: list[str] | None = None) -> dict[str, int]:
    """{contracts, sale_days} — số bản ghi cũ chưa chuyển đổi chạm vào kỳ này."""
    ensure_schema()
    if companies is not None and not companies:
        return {"contracts": 0, "sale_days": 0}
    # Lọc đơn vị nối thêm vào WHERE (không dùng `:p IS NULL` — NULL không suy được kiểu ở Postgres).
    scope, args = "", {"df": date_from, "dt": date_to}
    if companies is not None:
        scope, args["cs"] = " AND company = ANY(:cs)", list(companies)
    with session_scope() as db:
        return {"contracts": db.execute(text(_CONTRACTS + scope), args).scalar() or 0,
                "sale_days": db.execute(text(_SALE_DAYS + scope), args).scalar() or 0}


def warnings(date_from: str, date_to: str, companies: list[str] | None = None) -> list[str]:
    """Câu cảnh báo cho báo cáo/thống kê — rỗng khi không còn gì chờ chuyển đổi."""
    n = pending(date_from, date_to, companies)
    out: list[str] = []
    if n["sale_days"]:
        out.append(
            f"{n['sale_days']} ngày có số tiêu thụ nhập theo cách cũ CHƯA được chuyển sang hợp đồng "
            "— phần này chưa nằm trong báo cáo. Xem ở màn Hợp đồng cũ, hoặc chạy chuyển đổi để đưa vào.")
    if n["contracts"]:
        out.append(
            f"{n['contracts']} hợp đồng nhập theo cách cũ CHƯA được chuyển đổi — sản lượng đã ký "
            "chưa giao của các hợp đồng này chưa nằm trong báo cáo.")
    return out
