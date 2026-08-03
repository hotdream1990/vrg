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
from app.services import sales_contract_calc as calc
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
               customer_ids: list[int] | None = None,
               grades: list[str] | None = None) -> list[dict[str, Any]]:
    """Các LẦN GIAO có ngày giao trong [date_from, date_to] — nguồn số tiêu thụ của kỳ.

    Phụ lục KHÔNG mang khách hàng lẫn loại hợp đồng (cả hai gán ở hợp đồng mẹ) → gắn `customer_id`
    và `contract_type` của mẹ vào từng lần giao, nếu không thì không lọc/thống kê theo khách hàng
    và không tách được chỉ tiêu "HĐ dài hạn / HĐ chuyến".

    `grades` lọc theo CHỦNG LOẠI ở mức DÒNG: một lần giao có thể gồm nhiều chủng loại, nên phải
    bỏ các dòng không khớp rồi TÍNH LẠI sản lượng/quy khô/thành tiền của lần giao đó. Giữ nguyên
    cả lần giao là cộng luôn sản lượng của chủng loại người dùng không chọn.
    """
    rows = _fetch(companies,
                  ["delivered", "delivered_at IS NOT NULL",
                   "delivered_at >= CAST(:df AS date)", "delivered_at <= CAST(:dt AS date)"],
                  {"df": date_from, "dt": date_to})
    parent_ids = sorted({r["parent_id"] for r in rows if r["parent_id"] is not None})
    if parent_ids:
        owner = {p["id"]: (p["customer_id"], p["contract_type"])
                 for p in _fetch(None, ["id = ANY(:ps)"], {"ps": parent_ids})}
        for r in rows:
            if r["parent_id"] is not None:
                r["customer_id"], r["contract_type"] = owner.get(r["parent_id"], (None, None))
    if customer_ids:
        keep = set(customer_ids)
        rows = [r for r in rows if r.get("customer_id") in keep]
    if grades:
        rows = _only_grades(rows, grades)
    return rows


def _only_grades(rows: list[dict[str, Any]], grades: list[str]) -> list[dict[str, Any]]:
    """Giữ lại các dòng chi tiết thuộc `grades` rồi tính lại số tổng của từng lần giao.

    Lần giao không còn dòng nào khớp thì bị loại hẳn — kể cả khỏi số ĐẾM lần giao, vì với chủng
    loại đang lọc thì lần giao đó không tồn tại.
    """
    keep, out = set(grades), []
    for r in rows:
        lines = [ln for ln in (r.get("lines") or []) if (ln.get("grade") or "") in keep]
        if not lines:
            continue
        out.append({**r, "lines": lines,
                    "qty": calc.total_qty(lines), "qty_dry": calc.total_qty_dry(lines),
                    "revenue": calc.total_revenue_vnd(lines)})
    return out


def consumption(date_from: str, date_to: str, companies: list[str] | None = None,
                customer_ids: list[int] | None = None,
                grades: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: số tiêu thụ trong kỳ} — cộng dồn sản lượng/doanh thu, tách theo hình thức.

    `revenue` = None khi CÓ lần giao thiếu tỷ giá → báo cáo hiển thị "—" thay vì một số sai.
    `by_customer` tách sản lượng/doanh thu theo khách hàng (yêu cầu C1 của khách).
    """
    out: dict[str, dict[str, Any]] = {}
    for c in deliveries(date_from, date_to, companies, customer_ids, grades):
        acc = out.setdefault(c["company"], {
            "qty": 0.0, "qty_dry": 0.0, "revenue": 0.0, "revenue_missing": False,
            "deliveries": 0, "by_channel": {}, "by_grade": {}, "by_customer": {}, "by_type": {},
            "by_type_channel": {},
        })
        cu = str(c.get("customer_id") or 0)
        cus = acc["by_customer"].setdefault(cu, {"qty": 0.0, "revenue": 0.0})
        cus["qty"] += c["qty"]
        cus["revenue"] += c["revenue"] or 0.0
        acc["qty"] += c["qty"]
        acc["qty_dry"] += c["qty_dry"]
        acc["deliveries"] += 1
        if c["revenue"] is None:
            acc["revenue_missing"] = True
        else:
            acc["revenue"] += c["revenue"]
        ch = c.get("channel") or "domestic"
        acc["by_channel"][ch] = acc["by_channel"].get(ch, 0.0) + c["qty"]
        # Loại hợp đồng lấy từ mẹ (đã gắn ở `deliveries`); dữ liệu chưa khai gom vào khoá rỗng
        # thay vì dồn vào một loại — dồn là làm sai chỉ tiêu dài hạn/chuyến.
        ct = c.get("contract_type") or ""
        acc["by_type"][ct] = acc["by_type"].get(ct, 0.0) + c["qty"]
        # Mẫu báo cáo cần ô chéo (dài hạn × xuất khẩu, chuyến × trong nước…) nên giữ luôn bảng chéo.
        acc["by_type_channel"][f"{ct}|{ch}"] = acc["by_type_channel"].get(f"{ct}|{ch}", 0.0) + c["qty"]
        for g, q in _by_grade(c["lines"]).items():
            acc["by_grade"][g] = acc["by_grade"].get(g, 0.0) + q
    for acc in out.values():
        if acc.pop("revenue_missing"):
            acc["revenue"] = None
    return out


def undelivered_on(as_of: str, companies: list[str] | None = None,
                   grades: list[str] | None = None) -> dict[str, dict[str, Any]]:
    """{đơn vị: {qty, by_grade, items}} — ĐÃ KÝ HĐ CHƯA GIAO tại ngày `as_of` (khối 3).

    Chốt 02/08/2026 — tính theo VÒNG ĐỜI CỦA TỪNG ĐỢT GIAO, không phải theo cam kết của hợp đồng mẹ:
    một đợt nằm trong khối 3 từ **ngày bắt đầu** đến **hết ngày trước ngày giao**.
      - Phụ lục = một đợt của hợp đồng giao-nhiều-lần.
      - Hợp đồng giao-1-lần = chính nó là một đợt (ngày bắt đầu mặc định = ngày ký).
    Phần cam kết của hợp đồng mẹ **chưa phân thành đợt** KHÔNG tính vào khối 3 — hàng chưa gom vào
    kho thì không thể nằm trong tồn kho thực tế. Nhờ vậy hợp đồng khung cả năm không thổi phồng khối 3.
    """
    rows = _fetch(companies,
                  ["start_date IS NOT NULL", "start_date <= CAST(:d AS date)",
                   "(delivered_at IS NULL OR delivered_at > CAST(:d AS date))"],
                  {"d": as_of})
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        # Hợp đồng mẹ giao-nhiều-lần không phải là một đợt — hàng của nó nằm ở các phụ lục.
        if r["parent_id"] is None and r["delivery_type"] == "multi":
            continue
        by_grade = {g: q for g, q in _by_grade(r["lines"]).items()
                    if q > 1e-9 and (not grades or g in grades)}
        total = sum(by_grade.values())
        if total <= 1e-9:
            continue
        acc = out.setdefault(r["company"], {"qty": 0.0, "by_grade": {}, "items": []})
        acc["qty"] += total
        for g, q in by_grade.items():
            acc["by_grade"][g] = acc["by_grade"].get(g, 0.0) + q
        acc["items"].append({
            "id": r["id"], "code": r["code"], "parent_id": r["parent_id"],
            "customer_id": r["customer_id"], "sign_date": r["sign_date"],
            "start_date": r["start_date"], "expiry_date": r["expiry_date"],
            "qty": r["qty"], "remaining": total, "by_grade": by_grade,
        })
    return out


def parents_with_progress(companies: list[str] | None = None, *,
                          customer_ids: list[int] | None = None,
                          status: str | None = None, q: str | None = None,
                          date_from: str | None = None, date_to: str | None = None,
                          ) -> list[dict[str, Any]]:
    """Danh sách HỢP ĐỒNG MẸ kèm tiến độ giao (đã giao / còn lại / số phụ lục) cho màn danh sách."""
    extra, params = [], {}
    if customer_ids:
        extra.append("customer_id = ANY(:cu)")
        params["cu"] = list(customer_ids)
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
        # 3 rổ cộng lại bằng sản lượng cam kết:
        #   đã giao · đang chờ giao (đã mở đợt, chưa điền ngày giao) · chưa mở đợt.
        if p["delivery_type"] == "multi":
            done = sum(k["qty"] for k in ks if k["delivered_at"])
            pending = sum(k["qty"] for k in ks if not k["delivered_at"])
        else:
            done = p["qty"] if p["delivered_at"] else 0.0
            pending = 0.0 if p["delivered_at"] else p["qty"]
        remaining = max(0.0, p["qty"] - done - pending)
        item = {**p, "delivered_qty": done, "pending_qty": pending,
                "remaining_qty": remaining, "children": len(ks)}
        # "Còn hàng chưa giao" = chưa giao xong, gồm cả phần đang chờ giao lẫn phần chưa mở đợt.
        undone = pending + remaining
        if status == "open" and undone <= 1e-9:
            continue
        if status == "done" and undone > 1e-9:
            continue
        out.append(item)
    out.sort(key=lambda r: (r.get("sign_date") or "", r["company"], r["id"]), reverse=True)
    return out
