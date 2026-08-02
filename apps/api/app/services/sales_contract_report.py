"""Tổng hợp TIÊU THỤ và KHỐI 3 (đã ký HĐ chưa giao) TỪ HỢP ĐỒNG — thay cho ô nhập tay cũ.

Hai con số hệ thống tự tính (chốt 30/07/2026), đơn vị KHÔNG nhập trực tiếp nữa:
  - **Tiêu thụ** = tổng các LẦN GIAO (phụ lục, hoặc hợp đồng giao-1-lần đã đánh dấu giao)
    có `delivered_at` nằm trong kỳ báo cáo.
  - **Khối 3** = SL cam kết − tổng đã giao, TÍNH TẠI NGÀY báo cáo. Vẫn là phần NẰM TRONG tồn kho
    thành phẩm (không cộng thêm, không trừ ra).
Sản lượng đọc từ dòng chi tiết nên tách được theo chủng loại; doanh thu quy về ĐỒNG (xem `calc`).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services.sales_contract_repo import _COLS, _row

_SELECT = f"SELECT {', '.join(_COLS)} FROM sales_contract"


def _fetch(companies: list[str] | None, extra: list[str] | None = None,
           params: dict | None = None) -> list[dict[str, Any]]:
    """Đọc hợp đồng theo bộ lọc — dữ liệu nhỏ nên gom về Python tính cho dễ đọc/dễ kiểm."""
    ensure_schema()
    where, args = ["1 = 1"], dict(params or {})
    if companies is not None:
        if not companies:
            return []
        where.append("company = ANY(:cs)")
        args["cs"] = list(companies)
    where.extend(extra or [])
    with session_scope() as db:
        rows = db.execute(text(f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY company, id"),
                          args).mappings().all()
    return [_row(r) for r in rows]


def _by_grade(lines) -> dict[str, float]:
    out: dict[str, float] = {}
    for ln in lines or []:
        out[ln.get("grade") or ""] = out.get(ln.get("grade") or "", 0.0) + (ln.get("qty") or 0.0)
    return out


def deliveries(date_from: str, date_to: str, companies: list[str] | None = None,
               customer_id: int | None = None) -> list[dict[str, Any]]:
    """Các LẦN GIAO có ngày giao trong [date_from, date_to] — nguồn số tiêu thụ của kỳ.

    Phụ lục KHÔNG mang khách hàng (khách gán ở hợp đồng mẹ) → gắn `customer_id` của mẹ vào từng
    lần giao, nếu không thì không lọc/thống kê theo khách hàng được.
    """
    rows = _fetch(companies,
                  ["delivered", "delivered_at IS NOT NULL",
                   "delivered_at >= CAST(:df AS date)", "delivered_at <= CAST(:dt AS date)"],
                  {"df": date_from, "dt": date_to})
    parent_ids = sorted({r["parent_id"] for r in rows if r["parent_id"] is not None})
    if parent_ids:
        owner = {p["id"]: p["customer_id"]
                 for p in _fetch(None, ["id = ANY(:ps)"], {"ps": parent_ids})}
        for r in rows:
            if r["parent_id"] is not None:
                r["customer_id"] = owner.get(r["parent_id"])
    if customer_id is not None:
        rows = [r for r in rows if r.get("customer_id") == customer_id]
    return rows


def consumption(date_from: str, date_to: str, companies: list[str] | None = None,
                customer_id: int | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: số tiêu thụ trong kỳ} — cộng dồn sản lượng/doanh thu/chi phí, tách theo hình thức.

    `revenue` = None khi CÓ lần giao thiếu tỷ giá → báo cáo hiển thị "—" thay vì một số sai.
    `by_customer` tách sản lượng/doanh thu theo khách hàng (yêu cầu C1 của khách).
    """
    out: dict[str, dict[str, Any]] = {}
    for c in deliveries(date_from, date_to, companies, customer_id):
        acc = out.setdefault(c["company"], {
            "qty": 0.0, "qty_dry": 0.0, "cost": 0.0, "revenue": 0.0, "revenue_missing": False,
            "deliveries": 0, "by_channel": {}, "by_grade": {}, "by_customer": {},
        })
        cu = str(c.get("customer_id") or 0)
        cus = acc["by_customer"].setdefault(cu, {"qty": 0.0, "revenue": 0.0})
        cus["qty"] += c["qty"]
        cus["revenue"] += c["revenue"] or 0.0
        acc["qty"] += c["qty"]
        acc["qty_dry"] += c["qty_dry"]
        acc["cost"] += c["cost"]
        acc["deliveries"] += 1
        if c["revenue"] is None:
            acc["revenue_missing"] = True
        else:
            acc["revenue"] += c["revenue"]
        ch = c.get("channel") or "domestic"
        acc["by_channel"][ch] = acc["by_channel"].get(ch, 0.0) + c["qty"]
        for g, q in _by_grade(c["lines"]).items():
            acc["by_grade"][g] = acc["by_grade"].get(g, 0.0) + q
    for acc in out.values():
        if acc.pop("revenue_missing"):
            acc["revenue"] = None
    return out


def undelivered_on(as_of: str, companies: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: {qty, by_grade, items}} — ĐÃ KÝ HĐ CHƯA GIAO tại ngày `as_of` (khối 3).

    Chỉ tính hợp đồng đã ký tính đến ngày đó; phần đã giao tính theo `delivered_at <= as_of`
    (không dùng số liệu ngày khác thay). Còn lại âm thì kẹp về 0.
    """
    rows = _fetch(companies, ["(sign_date IS NULL OR sign_date <= CAST(:d AS date))"],
                  {"d": as_of})
    parents = [r for r in rows if r["parent_id"] is None]
    kids: dict[int, list[dict]] = {}
    for r in rows:
        if r["parent_id"] is not None:
            kids.setdefault(r["parent_id"], []).append(r)

    out: dict[str, dict[str, Any]] = {}
    for p in parents:
        want = _by_grade(p["lines"])
        done: dict[str, float] = {}
        if p["delivery_type"] == "multi":
            for k in kids.get(p["id"], []):
                if k["delivered_at"] and k["delivered_at"] <= as_of:
                    for g, q in _by_grade(k["lines"]).items():
                        done[g] = done.get(g, 0.0) + q
        elif p["delivered"] and p["delivered_at"] and p["delivered_at"] <= as_of:
            done = want
        remain = {g: max(0.0, q - done.get(g, 0.0)) for g, q in want.items()}
        total = sum(remain.values())
        if total <= 1e-9:
            continue
        acc = out.setdefault(p["company"], {"qty": 0.0, "by_grade": {}, "items": []})
        acc["qty"] += total
        for g, q in remain.items():
            if q > 1e-9:
                acc["by_grade"][g] = acc["by_grade"].get(g, 0.0) + q
        acc["items"].append({
            "id": p["id"], "code": p["code"], "customer_id": p["customer_id"],
            "delivery_type": p["delivery_type"], "sign_date": p["sign_date"],
            "expiry_date": p["expiry_date"], "qty": p["qty"], "remaining": total,
            "by_grade": {g: q for g, q in remain.items() if q > 1e-9},
        })
    return out


def parents_with_progress(companies: list[str] | None = None, *, customer_id: int | None = None,
                          status: str | None = None, q: str | None = None,
                          date_from: str | None = None, date_to: str | None = None,
                          ) -> list[dict[str, Any]]:
    """Danh sách HỢP ĐỒNG MẸ kèm tiến độ giao (đã giao / còn lại / số phụ lục) cho màn danh sách."""
    extra, params = [], {}
    if customer_id is not None:
        extra.append("customer_id = :cu")
        params["cu"] = customer_id
    if date_from:
        extra.append("(sign_date IS NULL OR sign_date >= CAST(:df AS date))")
        params["df"] = date_from
    if date_to:
        extra.append("(sign_date IS NULL OR sign_date <= CAST(:dt AS date))")
        params["dt"] = date_to
    if q:
        extra.append("(code ILIKE :q OR note ILIKE :q)")
        params["q"] = f"%{q}%"
    rows = _fetch(companies, extra, params)
    # Phụ lục luôn phải lấy kèm (kể cả khi bộ lọc chỉ khớp hợp đồng mẹ) để tính đúng tiến độ.
    parent_ids = [r["id"] for r in rows if r["parent_id"] is None]
    kids = _fetch(None, ["parent_id = ANY(:ps)"], {"ps": parent_ids}) if parent_ids else []
    by_parent: dict[int, list[dict]] = {}
    for k in kids:
        by_parent.setdefault(k["parent_id"], []).append(k)

    out: list[dict[str, Any]] = []
    for p in rows:
        if p["parent_id"] is not None:
            continue
        ks = by_parent.get(p["id"], [])
        done = (sum(k["qty"] for k in ks) if p["delivery_type"] == "multi"
                else (p["qty"] if p["delivered"] else 0.0))
        remaining = max(0.0, p["qty"] - done)
        item = {**p, "delivered_qty": done, "remaining_qty": remaining, "children": len(ks)}
        if status == "open" and remaining <= 1e-9:
            continue
        if status == "done" and remaining > 1e-9:
            continue
        out.append(item)
    out.sort(key=lambda r: (r.get("sign_date") or "", r["company"], r["id"]), reverse=True)
    return out
