"""Repository HỢP ĐỒNG BÁN HÀNG 2 CẤP (sales_contract) — nguồn duy nhất tính TIÊU THỤ.

Chốt 30/07/2026:
  - `parent_id` NULL = HỢP ĐỒNG MẸ. Loại giao 'single' (giao trọn 1 lần) hoặc 'multi'
    (giao nhiều lần — mẹ giữ TỔNG sản lượng cam kết, nhập phụ lục tới khi hết).
  - `parent_id` khác NULL = PHỤ LỤC: MỖI phụ lục = 1 ĐỢT GIAO + 1 LẦN THANH TOÁN.
    KHÔNG cho phụ lục vượt sản lượng còn lại của mẹ.

Chốt 02/08/2026 — mỗi ĐỢT GIAO có vòng đời riêng: mở đợt ở `start_date` (hàng gom vào kho),
giao ở `delivered_at`. Chưa điền ngày giao = ĐANG CHỜ GIAO. Hợp đồng giao-1-lần thì chính nó là
một đợt (ngày bắt đầu mặc định = ngày ký).
Tiêu thụ = tổng các đợt ĐÃ GIAO trong kỳ; "đã ký HĐ chưa giao" = các đợt đang trong khoảng
[ngày bắt đầu → hết ngày trước ngày giao] — xem `sales_contract_report.undelivered_on`.
"""

from __future__ import annotations

import json
import math
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.core.market_meta import DELIVERY_TYPES, SALE_CHANNELS
from app.services import audit_repo, contract_docs, customer_repo, sales_contract_calc as calc

_COLS = ("id", "company", "parent_id", "code", "customer_id", "delivery_type", "sign_date",
         "expiry_date", "start_date", "lines", "delivered", "delivered_at", "channel", "to_company",
         "payment_date", "payment_qty", "payment_cost", "payment_docs", "files", "note")
_DATE_COLS = ("sign_date", "expiry_date", "start_date", "delivered_at", "payment_date")


def _row(r) -> dict[str, Any]:
    d = dict(r)
    for k in _DATE_COLS:
        d[k] = str(d[k]) if d.get(k) else None
    d["lines"] = d.get("lines") or []
    d["files"] = contract_docs.normalize(d.get("files"), None, None)
    d["payment_docs"] = contract_docs.normalize(d.get("payment_docs"), None, None)
    d["qty"] = calc.total_qty(d["lines"])
    d["qty_dry"] = calc.total_qty_dry(d["lines"])
    d["cost"] = calc.total_cost(d["lines"])
    d["revenue"] = calc.total_revenue_vnd(d["lines"])
    return d


def _as_date(v, label: str, required: bool = False) -> date | None:
    s = str(v or "").strip()[:10]
    if not s:
        if required:
            raise ValueError(f"Thiếu {label}.")
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def _num(v) -> float | None:
    """Số hợp lệ hoặc None — loại NaN/Infinity (xem `sales_contract_calc._num`)."""
    try:
        f = None if v in (None, "") else float(v)
    except (TypeError, ValueError):
        return None
    return None if f is not None and not math.isfinite(f) else f


def _money(v, label: str) -> float | None:
    """Ô tiền/sản lượng nhập tay — không được âm (âm làm doanh thu/chi phí kỳ bị trừ ngược)."""
    f = _num(v)
    if f is not None and f < 0:
        raise ValueError(f"{label} không được âm.")
    return f


def _int_id(v, label: str) -> int | None:
    """Khoá số dương hoặc None. `str(-1).isdigit()` là False nên số âm từng lặng lẽ thành None —
    một `parent_id` âm biến phụ lục thành hợp đồng mẹ, `id` âm biến 'sửa' thành 'thêm mới'."""
    s = str(v if v is not None else "").strip()
    if not s:
        return None
    if not s.isdigit() or int(s) <= 0:
        raise ValueError(f"{label} không hợp lệ.")
    return int(s)


def _assert_unit_exists(name: str, label: str) -> None:
    """Tên đơn vị phải có thật trong `member_unit` — nếu không bản ghi thành mồ côi, không bộ lọc
    nào hiển thị được mà vẫn nằm trong bảng và vẫn được cộng vào tổng."""
    from app.services import member_unit_repo

    if name not in {u["name"] for u in member_unit_repo.list_units()}:
        raise ValueError(f"{label} “{name}” không có trong danh sách đơn vị thành viên.")


def _parent_of(db, parent_id: int) -> dict[str, Any]:
    row = db.execute(text(f"SELECT {', '.join(_COLS)} FROM sales_contract WHERE id = :i"),
                     {"i": parent_id}).mappings().first()
    if row is None:
        raise ValueError("Hợp đồng mẹ không còn tồn tại (có thể đã bị xoá).")
    if row["parent_id"] is not None:
        raise ValueError("Không thể thêm phụ lục cho một phụ lục (hợp đồng chỉ có 2 cấp).")
    return _row(row)


def _delivered_qty(db, parent_id: int, exclude_id: int | None) -> float:
    """Tổng sản lượng các phụ lục ĐÃ nhập của hợp đồng mẹ (trừ chính dòng đang sửa)."""
    rows = db.execute(text("SELECT id, lines FROM sales_contract WHERE parent_id = :p"),
                      {"p": parent_id}).mappings().all()
    return sum(calc.total_qty(r["lines"] or []) for r in rows if r["id"] != exclude_id)


def clean(row: dict, company: str) -> dict[str, Any]:
    """Chuẩn hoá + kiểm tra 1 hợp đồng/phụ lục trước khi ghi (raise ValueError nếu sai)."""
    code = str(row.get("code") or "").strip()[:80]
    if not code:
        raise ValueError("Thiếu số hợp đồng / số phụ lục.")
    parent_id = _int_id(row.get("parent_id"), "Hợp đồng mẹ")
    is_child = parent_id is not None
    delivery_type = str(row.get("delivery_type") or "single").strip()
    if delivery_type not in DELIVERY_TYPES:
        raise ValueError(f"Loại giao “{row.get('delivery_type')}” không hợp lệ.")
    # MỘT ĐỢT GIAO có vòng đời (chốt 02/08/2026): mở đợt ở `start_date`, giao ở `delivered_at`.
    # Còn ĐANG CHỜ GIAO khi chưa điền ngày giao → nằm ở khối 3, chưa tính vào tiêu thụ.
    delivered_at = _as_date(row.get("delivered_at"), "Ngày giao")
    delivered = delivered_at is not None
    if is_child:
        delivery_type = "single"
    elif delivery_type == "multi" and delivered:
        raise ValueError("Hợp đồng giao nhiều lần không tự đánh dấu đã giao — hãy nhập phụ lục.")
    raw_channel = str(row.get("channel") or "").strip()
    if raw_channel and raw_channel not in SALE_CHANNELS:
        raise ValueError(f"Hình thức tiêu thụ “{raw_channel}” không hợp lệ.")
    channel = raw_channel or None
    if delivered and not channel:
        raise ValueError("Thiếu hình thức tiêu thụ (Xuất khẩu/UTXK · Trong nước · Nội bộ).")
    to_company = str(row.get("to_company") or "").strip()[:120] or None
    if channel == "internal":
        if not to_company:
            raise ValueError("Tiêu thụ nội bộ phải chọn đơn vị nhận hàng.")
        _assert_unit_exists(to_company, "Đơn vị nhận")
        if to_company == company:
            raise ValueError("Đơn vị nhận của tiêu thụ nội bộ phải khác đơn vị bán.")
    else:
        to_company = None

    sign = _as_date(row.get("sign_date"), "Ngày ký", required=not is_child)
    start = _as_date(row.get("start_date"), "Ngày bắt đầu", required=is_child)
    if start is None and delivery_type == "single" and not is_child:
        start = sign     # HĐ giao 1 lần: chính hợp đồng là một đợt, mở từ ngày ký
    if start and delivered_at and delivered_at < start:
        raise ValueError("Ngày giao không thể trước Ngày bắt đầu của đợt.")
    if start and sign and start < sign:
        raise ValueError("Ngày bắt đầu không thể trước ngày ký hợp đồng.")
    expiry = _as_date(row.get("expiry_date"), "Thời hạn hợp đồng")
    if sign and expiry and expiry < sign:
        raise ValueError("Thời hạn hợp đồng phải sau ngày ký.")
    if sign and delivered_at and delivered_at < sign:
        raise ValueError("Ngày giao không thể trước ngày ký hợp đồng.")

    paid_at = _as_date(row.get("payment_date"), "Ngày thanh toán")
    customer_id = _int_id(row.get("customer_id"), "Khách hàng")
    if customer_id is None and not is_child:
        raise ValueError("Hợp đồng phải gán một khách hàng của đơn vị.")
    if customer_id is not None:
        owner = customer_repo.owner_of(customer_id)
        if owner is None:
            raise ValueError("Khách hàng không còn tồn tại.")
        if owner != company:
            raise ValueError("Khách hàng thuộc danh mục của đơn vị khác.")

    return {
        "id": _int_id(row.get("id"), "Mã hợp đồng"),
        "company": company,
        "parent_id": parent_id,
        "code": code,
        "customer_id": customer_id,
        "delivery_type": delivery_type,
        "sign_date": sign.isoformat() if sign else None,
        "expiry_date": expiry.isoformat() if expiry else None,
        "start_date": start.isoformat() if start else None,
        # Quy khô + hình thức tiêu thụ chỉ ép khi ĐÃ GIAO — lúc mở đợt chưa bán nên chưa biết.
        "lines": calc.clean_lines(row.get("lines"), require_dry=delivered),
        "delivered": delivered,
        "delivered_at": delivered_at.isoformat() if delivered_at else None,
        "channel": channel,
        "to_company": to_company,
        "payment_date": paid_at.isoformat() if paid_at else None,
        "payment_qty": _money(row.get("payment_qty"), "Sản lượng thanh toán"),
        "payment_cost": _money(row.get("payment_cost"), "Chi phí thanh toán"),
        "payment_docs": contract_docs.normalize(row.get("payment_docs"), None, None),
        "files": contract_docs.normalize(row.get("files"), None, None),
        "note": str(row.get("note") or "").strip()[:500] or None,
    }


_INSERT = text(
    "INSERT INTO sales_contract (company, parent_id, code, customer_id, delivery_type, sign_date, "
    " expiry_date, start_date, lines, delivered, delivered_at, channel, to_company, payment_date, "
    " payment_qty, payment_cost, payment_docs, files, note, updated_by) "
    "VALUES (:company, :parent_id, :code, :customer_id, :delivery_type, CAST(:sign_date AS date), "
    " CAST(:expiry_date AS date), CAST(:start_date AS date), CAST(:lines AS jsonb), :delivered, "
    " CAST(:delivered_at AS date), "
    " :channel, :to_company, CAST(:payment_date AS date), :payment_qty, :payment_cost, "
    " CAST(:payment_docs AS jsonb), CAST(:files AS jsonb), :note, :by) RETURNING id")

_UPDATE = text(
    "UPDATE sales_contract SET code = :code, customer_id = :customer_id, "
    " delivery_type = :delivery_type, sign_date = CAST(:sign_date AS date), "
    " expiry_date = CAST(:expiry_date AS date), start_date = CAST(:start_date AS date), "
    " lines = CAST(:lines AS jsonb), "
    " delivered = :delivered, delivered_at = CAST(:delivered_at AS date), channel = :channel, "
    " to_company = :to_company, payment_date = CAST(:payment_date AS date), "
    " payment_qty = :payment_qty, payment_cost = :payment_cost, "
    " payment_docs = CAST(:payment_docs AS jsonb), files = CAST(:files AS jsonb), note = :note, "
    " updated_by = :by, updated_at = now() WHERE id = :id")


def _params(d: dict, updated_by: str | None) -> dict[str, Any]:
    return {**d, "lines": json.dumps(d["lines"]), "files": json.dumps(d["files"]),
            "payment_docs": json.dumps(d["payment_docs"]), "by": updated_by}


def _tan(v: float) -> str:
    """Số tấn theo kiểu Việt: dấu chấm ngăn nghìn, dấu phẩy thập phân.
    Đổi thẳng ',' → '.' như trước làm 50,000.000 thành 50.000.000 → người đọc hiểu là 50 TRIỆU tấn."""
    return f"{v:,.3f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def save(row: dict, company: str, updated_by: str | None) -> dict[str, Any]:
    """Thêm mới (không có id) hoặc cập nhật. Raise ValueError nếu vi phạm nghiệp vụ."""
    d = clean(row, company)
    _assert_unit_exists(company, "Đơn vị")
    ensure_schema()
    before = get(d["id"]) if d["id"] is not None else None
    with session_scope() as db:
        if d["id"] is not None:
            cur = db.execute(text("SELECT company, parent_id, delivery_type FROM sales_contract "
                                  "WHERE id = :i"), {"i": d["id"]}).mappings().first()
            if cur is None:
                raise ValueError("Hợp đồng không còn tồn tại (có thể đã bị xoá).")
            if cur["company"] != company:
                raise ValueError("Hợp đồng thuộc đơn vị khác.")
            # Cấp bậc KHÔNG đổi được khi sửa: `_UPDATE` không ghi `parent_id`, nên nhận `parent_id`
            # khác trong payload sẽ kiểm hạn mức trên hợp đồng mẹ KHÁC rồi vẫn nằm ở mẹ cũ —
            # lách được giới hạn sản lượng. Muốn chuyển mẹ thì xoá phụ lục và nhập lại.
            if (d["parent_id"] or None) != (cur["parent_id"] or None):
                raise ValueError("Không đổi được hợp đồng mẹ của phụ lục — xoá rồi nhập lại phụ lục.")
            kids = db.execute(text("SELECT count(*) FROM sales_contract WHERE parent_id = :i"),
                              {"i": d["id"]}).scalar() or 0
            if kids and d["delivery_type"] != cur["delivery_type"]:
                raise ValueError(f"Hợp đồng đang có {kids} phụ lục — không đổi được loại giao.")
            if kids and d["delivered"]:
                raise ValueError("Hợp đồng giao nhiều lần đã có phụ lục — không tự đánh dấu đã giao "
                                 "(sản lượng sẽ bị tính hai lần).")
            if kids:
                done = _delivered_qty(db, d["id"], None)
                if calc.total_qty(d["lines"]) < done - 1e-9:
                    raise ValueError(
                        f"Sản lượng cam kết mới ({_tan(calc.total_qty(d['lines']))} tấn) nhỏ hơn "
                        f"phần các phụ lục đã giao ({_tan(done)} tấn).")
        # Trùng số hợp đồng trong cùng đơn vị → chặn: lưu lại do mạng chập chờn sẽ nhân đôi sản lượng.
        dup = db.execute(text(
            "SELECT 1 FROM sales_contract WHERE company = :c AND lower(code) = lower(:k) "
            "AND (CAST(:i AS bigint) IS NULL OR id <> CAST(:i AS bigint)) LIMIT 1"),
            {"c": company, "k": d["code"], "i": d["id"]}).scalar()
        if dup:
            raise ValueError(f"Đơn vị đã có hợp đồng/phụ lục số “{d['code']}”.")

        if d["parent_id"] is not None:
            parent = _parent_of(db, d["parent_id"])
            if parent["company"] != company:
                raise ValueError("Hợp đồng mẹ thuộc đơn vị khác.")
            if parent["delivery_type"] != "multi":
                raise ValueError("Chỉ hợp đồng loại “giao nhiều lần” mới thêm được phụ lục.")
            if parent["sign_date"] and d["delivered_at"] and d["delivered_at"] < parent["sign_date"]:
                raise ValueError("Ngày giao của phụ lục không thể trước ngày ký hợp đồng mẹ.")
            done = _delivered_qty(db, d["parent_id"], d["id"])
            adding = calc.total_qty(d["lines"])
            remain = parent["qty"] - done
            if adding > remain + 1e-9:
                raise ValueError(f"Phụ lục {_tan(adding)} tấn vượt sản lượng còn lại của hợp đồng mẹ "
                                 f"({_tan(remain)} tấn).")
        if d["id"] is not None:
            db.execute(_UPDATE, _params(d, updated_by))
            new_id = d["id"]
        else:
            new_id = db.execute(_INSERT, _params(d, updated_by)).scalar()
    saved = get(new_id) or {**d, "id": new_id}
    label = ("Phụ lục " if d["parent_id"] else "HĐ ") + d["code"]
    audit_repo.log("sales_contract", "update" if before else "create", label,
                   before=before, after=saved, as_of=saved.get("delivered_at") or saved.get("sign_date"),
                   company=company)
    return saved


def get(contract_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(f"SELECT {', '.join(_COLS)} FROM sales_contract WHERE id = :i"),
                         {"i": contract_id}).mappings().first()
    return _row(row) if row else None


def companies_of_file(name: str) -> set[str]:
    """Các đơn vị có hợp đồng/phụ lục đính kèm file này — để chặn tải chéo đơn vị.

    File lưu chung một thư mục phẳng theo tên uuid; không kiểm thì bất kỳ tài khoản nào biết tên
    file đều tải được bản scan hợp đồng của đơn vị khác.
    """
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT DISTINCT company FROM sales_contract "
            "WHERE files @> CAST(:f AS jsonb) OR payment_docs @> CAST(:f AS jsonb)"),
            {"f": json.dumps([{"file": name}])}).scalars().all()
    return set(rows)


def children(parent_id: int) -> list[dict[str, Any]]:
    """Các phụ lục của 1 hợp đồng mẹ, sắp theo ngày giao."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT {', '.join(_COLS)} FROM sales_contract WHERE parent_id = :p "
                 "ORDER BY delivered_at, id"), {"p": parent_id}).mappings().all()
    return [_row(r) for r in rows]


def delete(contract_id: int, companies: list[str] | None) -> bool:
    """Xoá 1 hợp đồng/phụ lục. Hợp đồng mẹ còn phụ lục thì phải xoá phụ lục trước."""
    ensure_schema()
    before = get(contract_id)
    with session_scope() as db:
        cur = db.execute(text("SELECT company FROM sales_contract WHERE id = :i"),
                         {"i": contract_id}).scalar()
        if cur is None or (companies is not None and cur not in companies):
            return False
        kids = db.execute(text("SELECT count(*) FROM sales_contract WHERE parent_id = :i"),
                          {"i": contract_id}).scalar() or 0
        if kids:
            raise ValueError(f"Hợp đồng còn {kids} phụ lục — xoá các phụ lục trước.")
        db.execute(text("DELETE FROM sales_contract WHERE id = :i"), {"i": contract_id})
    audit_repo.log("sales_contract", "delete", (before or {}).get("code") or f"#{contract_id}",
                   before=before, as_of=(before or {}).get("sign_date"), company=cur)
    return True
