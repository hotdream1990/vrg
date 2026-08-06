"""Bảng "đơn vị còn thiếu gì" — hiện ngay khi tài khoản đơn vị thành viên vào hệ thống.

Chỉ nhắc những thứ đơn vị CÒN SỬA ĐƯỢC (nằm trong cửa sổ nhập liệu). Ngày đã khoá chỉ-xem thì
nhắc cũng vô ích, chỉ làm người dùng bỏ qua cả bảng cảnh báo.

Luật "ngày nào coi là đã nộp" dùng CHUNG với màn *Theo dõi nộp báo cáo* của Ban TTKD
(`unit_daily_fields.has_data` + `companies_with_purchase_plan`) — hai bên lệch nhau thì đơn vị
bị nhắc oan hoặc yên tâm nhầm trong khi Ban TTKD vẫn thấy thiếu.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import text

from app.core import edit_window
from app.core.db import ensure_schema, session_scope
from app.services import unit_daily_repo
from app.services import unit_daily_fields as fields

#: Đợt giao mở lâu mà chưa điền ngày giao = nhiều khả năng đơn vị quên đóng đợt. Dưới ngưỡng này
#: là chuyện bình thường (hàng đang gom trong kho), nhắc sớm chỉ gây nhiễu.
PENDING_AFTER_DAYS = 7

_PENDING_SQL = text("""
    SELECT k.id, k.company, k.code, p.code AS contract_code, k.updated_at::date AS since,
           COALESCE((SELECT sum(COALESCE(NULLIF(e->>'qty', '')::numeric, 0))
                       FROM jsonb_array_elements(k.lines) e), 0) AS qty
      FROM sales_contract k
      JOIN sales_contract p ON p.id = k.parent_id
     WHERE k.parent_id IS NOT NULL AND k.delivered_at IS NULL
       AND p.completed_at IS NULL
       AND k.company = ANY(:units) AND k.updated_at::date <= :before
     ORDER BY k.updated_at
""")


def _days(window: int, today: date) -> list[str]:
    """Các ngày CÒN SỬA ĐƯỢC, mới nhất trước. Khớp `edit_window.assert_editable` (gồm cả hôm nay)."""
    return [(today - timedelta(days=i)).isoformat() for i in range(window + 1)]


_ENTRIES_SQL = text("""
    SELECT as_of, company, payload FROM unit_daily_report
     WHERE kind = :kind AND company = ANY(:units)
       AND as_of BETWEEN CAST(:a AS date) AND CAST(:b AS date)
""")


def _submitted(kind: str, units: list[str], days: list[str]) -> set[tuple[str, str]]:
    """(đơn vị, ngày) đã nộp biểu `kind` — bản ghi rỗng KHÔNG tính là đã nộp.

    Đọc thẳng payload thay vì `unit_daily_repo.in_range`: hàm đó còn tính kèm khối 3 cho TỪNG
    ngày (mỗi ngày một truy vấn nặng trên toàn bộ hợp đồng) — bảng nhắc việc không dùng tới.
    """
    with session_scope() as db:
        rows = db.execute(_ENTRIES_SQL, {"kind": kind, "units": list(units),
                                         "a": days[-1], "b": days[0]}).mappings().all()
    return {(r["company"], str(r["as_of"])) for r in rows
            if fields.has_data(kind, dict(r["payload"] or {}))}


def _pending_batches(units: list[str], today: date) -> dict[str, list[dict[str, Any]]]:
    """Đợt giao đã mở nhưng bỏ trống ngày giao → sản lượng đó KHÔNG vào tiêu thụ."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(_PENDING_SQL, {
            "units": list(units),
            "before": (today - timedelta(days=PENDING_AFTER_DAYS)).isoformat(),
        }).mappings().all()
    out: dict[str, list[dict[str, Any]]] = {u: [] for u in units}
    for r in rows:
        out.setdefault(r["company"], []).append({
            "id": r["id"], "code": r["code"], "contract_code": r["contract_code"],
            "qty": float(r["qty"] or 0), "since": str(r["since"]),
            "days": (today - r["since"]).days,
        })
    return out


def checklist(units: list[str]) -> dict[str, Any]:
    """Việc còn thiếu của TỪNG đơn vị được gán cho tài khoản.

    Ba nhóm: (1) ngày chưa nhập biểu Thu mua · (2) ngày chưa nhập biểu Tồn kho ·
    (3) nhắc khác — chưa khai Kế hoạch năm, đợt giao quên điền ngày giao.
    """
    units = list(units)
    window, today = edit_window.member_window(), edit_window.today()
    days = _days(window, today)
    if not units:
        return {"today": today.isoformat(), "window_days": window, "days": days,
                "units": [], "total_missing": 0}

    planned = unit_daily_repo.companies_with_purchase_plan(today.year)
    plan_now = unit_daily_repo.year_plan(today.year, units)
    done = {k: _submitted(k, units, days) for k in ("purchase", "consumption")}
    pending = _pending_batches(units, today)

    rows, total = [], 0
    for u in units:
        needs_purchase = u in planned
        miss_p = [d for d in days if needs_purchase and (u, d) not in done["purchase"]]
        miss_s = [d for d in days if (u, d) not in done["consumption"]]
        # "Chưa khai kế hoạch năm NAY" — `companies_with_purchase_plan` cố ý dùng lại số năm
        # trước để đơn vị không mất màn Thu mua đầu năm, nên phải hỏi riêng năm hiện tại.
        plan_missing = (plan_now.get(u) or {}).get("plan_tonnes") is None
        # Kế hoạch năm PHẢI cộng vào tổng: tổng = 0 thì banner chuyển sang dòng xanh "Đã nhập đủ"
        # và KHÔNG hiện phần chi tiết nữa → việc còn thiếu biến mất khỏi màn hình.
        total += len(miss_p) + len(miss_s) + len(pending.get(u, [])) + (1 if plan_missing else 0)
        rows.append({"company": u, "needs_purchase": needs_purchase,
                     "purchase_missing": miss_p, "stock_missing": miss_s,
                     "year_plan_missing": plan_missing, "year": today.year,
                     "pending_batches": pending.get(u, [])})
    return {"today": today.isoformat(), "window_days": window, "days": days,
            "units": rows, "total_missing": total}
