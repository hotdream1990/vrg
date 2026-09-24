"""Bảng "đơn vị còn thiếu gì" — hiện ngay khi tài khoản đơn vị thành viên vào hệ thống.

Nhắc số liệu còn thiếu trong cửa sổ nhập liệu — ngày đã khoá chỉ-xem thì nhắc cũng vô ích, chỉ
làm người dùng bỏ qua cả bảng. Ngoại lệ là nhóm THIẾU TỶ GIÁ: rà cả năm và vẫn hiện cả lần giao
đã quá hạn sửa, nhưng đánh dấu `editable=False` để giao diện nói rõ phải nhờ Ban TTKD điền hộ.

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
from app.services import member_data_check, unit_daily_repo
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


#: Lần giao ngoại tệ bỏ trống tỷ giá → doanh thu của lần đó KHÔNG được tính (hệ thống không đoán
#: tỷ giá thay đơn vị). Rà từ ĐẦU NĂM chứ không theo `alert_days`: đây là tiền, sót một lần giao là
#: doanh thu cả năm hụt, mà đơn vị lại chẳng có màn nào khác nhắc chuyện này.
_MISSING_FX_SQL = text("""
    SELECT k.id, k.company, k.code, COALESCE(p.code, k.code) AS contract_code, k.delivered_at,
           sum(COALESCE(NULLIF(e->>'qty', '')::numeric, 0)) AS qty,
           min(e->>'ccy') AS ccy
      FROM sales_contract k
      LEFT JOIN sales_contract p ON p.id = k.parent_id
      CROSS JOIN LATERAL jsonb_array_elements(k.lines) e
     WHERE k.company = ANY(:units) AND k.delivered
       AND k.delivered_at BETWEEN CAST(:a AS date) AND CAST(:b AS date)
       AND COALESCE(e->>'ccy', 'VND') <> 'VND' AND (e->>'fx') IS NULL
     GROUP BY k.id, k.company, k.code, contract_code, k.delivered_at
     ORDER BY k.delivered_at
""")


#: Hợp đồng CHỐT HOÀN THÀNH mà chưa ghi lần giao nào → sản lượng đó không bao giờ vào tiêu thụ.
#: Gặp thật 27/08/2026: Thanh Hoá xoá ngày giao của một hợp đồng chuyển từ lần bán thật rồi bấm
#: "Hoàn thành" — 198,66 tấn (9,8 tỷ) rơi khỏi tiêu thụ tháng 4 mà không ai hay. Nhiều khả năng
#: đơn vị hiểu "Hoàn thành hợp đồng" là cách ghi nhận ĐÃ GIAO XONG.
#: Rà từ ĐẦU NĂM như nhóm thiếu tỷ giá: đây là sản lượng + tiền, sót là báo cáo hụt cả kỳ.
_COMPLETED_NO_DELIVERY_SQL = text("""
    SELECT c.id, c.company, c.code, c.completed_at,
           COALESCE((SELECT sum(COALESCE(NULLIF(e->>'qty', '')::numeric, 0))
                       FROM jsonb_array_elements(c.lines) e), 0) AS qty
      FROM sales_contract c
     WHERE c.parent_id IS NULL AND c.company = ANY(:units)
       AND c.completed_at IS NOT NULL AND c.completed_at >= CAST(:a AS date)
       AND c.delivered_at IS NULL
       AND NOT EXISTS (SELECT 1 FROM sales_contract k
                        WHERE k.parent_id = c.id AND k.delivered_at IS NOT NULL)
     ORDER BY qty DESC
""")


def _completed_no_delivery(units: list[str], year_start: str) -> dict[str, list[dict[str, Any]]]:
    """Hợp đồng đã chốt hoàn thành nhưng KHÔNG có lần giao nào — sản lượng không vào tiêu thụ.

    Hợp đồng huỷ giữa chừng cũng rơi vào đây, nên chỉ NHẮC chứ không kết luận là sai: đơn vị mở ra
    xem, nếu hàng đã giao thật thì điền ngày giao, còn huỷ thật thì bỏ qua.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(_COMPLETED_NO_DELIVERY_SQL,
                          {"units": list(units), "a": year_start}).mappings().all()
    out: dict[str, list[dict[str, Any]]] = {u: [] for u in units}
    for r in rows:
        out.setdefault(r["company"], []).append({
            "id": r["id"], "code": r["code"], "qty": float(r["qty"] or 0),
            "completed_at": str(r["completed_at"]),
        })
    return out


def _missing_fx(units: list[str], today: date, editable_from: str) -> dict[str, list[dict[str, Any]]]:
    """Lần giao thiếu tỷ giá từ 01/01 năm nay → doanh thu & giá bán BQ đang thiếu phần này."""
    with session_scope() as db:
        rows = db.execute(_MISSING_FX_SQL, {
            "units": list(units), "a": date(today.year, 1, 1).isoformat(), "b": today.isoformat(),
        }).mappings().all()
    out: dict[str, list[dict[str, Any]]] = {u: [] for u in units}
    for r in rows:
        day = str(r["delivered_at"])
        out.setdefault(r["company"], []).append({
            "id": r["id"], "code": r["code"], "contract_code": r["contract_code"],
            "delivered_at": day, "qty": float(r["qty"] or 0), "ccy": r["ccy"],
            # Ngoài cửa sổ sửa thì đơn vị KHÔNG tự điền được — phải nói thẳng để họ báo Ban TTKD.
            "editable": day >= editable_from,
        })
    return out


def _days(alert: int, today: date) -> list[str]:
    """`alert` ngày gần nhất, TÍNH CẢ HÔM NAY, mới nhất trước (admin cấu hình `MEMBER_ALERT_DAYS`)."""
    return [(today - timedelta(days=i)).isoformat() for i in range(alert)]


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
    (3) nhắc khác — chưa khai Kế hoạch năm, đợt giao quên điền ngày giao, **hợp đồng đã chốt mà
    chưa ghi lần giao nào**, lần giao ngoại tệ thiếu tỷ giá, và **ô số liệu cần soát lại** (nhiều khả năng nhầm đơn vị tính — xem
    `member_data_check`). Hai nhóm cuối rà từ ĐẦU NĂM, không giới hạn trong `alert_days`.

    Phạm vi rà = `MEMBER_ALERT_DAYS` (admin cấu hình, mặc định 14 ngày, **0 = tắt cảnh báo**).
    Rà có thể XA HƠN cửa sổ sửa → trả kèm `editable_from` (đã tính giờ chốt, chung mọi biểu) để
    giao diện phân biệt ngày còn tự sửa được với ngày đã khoá (đơn vị phải nhờ Ban TTKD nhập hộ),
    không hứa hão là bấm vào sửa được.
    """
    units = list(units)
    today = edit_window.today()
    alert = edit_window.alert_days()
    # Mốc "còn tự sửa được" — MỘT mốc chung mọi biểu (hạn = giờ chốt của ngày D + N).
    editable_from = edit_window.editable_from(edit_window.member_window()).isoformat()
    base = {"today": today.isoformat(), "alert_days": alert, "enabled": alert > 0,
            "editable_from": editable_from}
    if alert <= 0 or not units:
        return {**base, "days": [], "units": [], "total_missing": 0}
    days = _days(alert, today)

    # Ô cần soát lại rà từ ĐẦU NĂM như nhóm thiếu tỷ giá: số nhầm đơn vị tính nằm im trong báo cáo
    # cho tới khi có người mở đúng phiếu đó ra xem — giới hạn trong `alert_days` là gần như không
    # bao giờ thấy nó.
    year_start = date(today.year, 1, 1).isoformat()
    checks = member_data_check.issues(units, year_start, editable_from)

    planned = unit_daily_repo.companies_with_purchase_plan(today.year)
    plan_now = unit_daily_repo.year_plan(today.year, units)
    done = {k: _submitted(k, units, days) for k in ("purchase", "consumption")}
    pending = _pending_batches(units, today)
    no_fx = _missing_fx(units, today, editable_from)
    closed_no_giao = _completed_no_delivery(units, year_start)

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
        total += (len(miss_p) + len(miss_s) + len(pending.get(u, []))
                  + len(no_fx.get(u, [])) + len(checks.get(u, []))
                  + len(closed_no_giao.get(u, []))
                  + (1 if plan_missing else 0))
        rows.append({"company": u, "needs_purchase": needs_purchase,
                     "purchase_missing": miss_p, "stock_missing": miss_s,
                     "year_plan_missing": plan_missing, "year": today.year,
                     "pending_batches": pending.get(u, []),
                     "missing_fx": no_fx.get(u, []),
                     "completed_no_delivery": closed_no_giao.get(u, []),
                     "data_checks": checks.get(u, [])})
    return {**base, "days": days, "units": rows, "total_missing": total}
