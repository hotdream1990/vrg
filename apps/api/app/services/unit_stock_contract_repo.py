"""Repository TỒN KHO ĐÃ KÝ HỢP ĐỒNG chưa giao (unit_stock_contract).

Khác 3 khối tồn kho còn lại (nhập lại mỗi ngày vì là số thời điểm), hợp đồng đã ký là BẢN GHI CÓ
VÒNG ĐỜI: nhập MỘT LẦN khi bắt đầu tồn kho (kèm file HĐ scan), đến khi xuất kho thì chỉ cập nhật
NGÀY GIAO. Hệ thống tự tính: hợp đồng nằm trong tồn kho của ngày D khi
`start_date <= D` và (chưa giao HOẶC `D < delivered_date`) — tức tính đến hết ngày TRƯỚC ngày giao.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo, contract_docs

_CCY = {"VND", "USD"}
_COLS = ("id", "company", "code", "grade", "qty", "price", "ccy", "fx",
         "start_date", "delivery_date", "delivered_date", "file", "filename", "files")


def _row(r) -> dict[str, Any]:
    d = dict(r)
    for k in ("start_date", "delivery_date", "delivered_date"):
        d[k] = str(d[k]) if d.get(k) else None
    # Bản ghi cũ chưa có danh sách → dựng từ cột phẳng, để đọc lên vẫn thấy file đã đính kèm.
    d["files"] = contract_docs.normalize(d.get("files"), d.get("file"), d.get("filename"))
    return d


def _as_date(v, label: str, required: bool = False) -> date | None:
    """Chuỗi 'YYYY-MM-DD' → date. Raise ValueError với thông báo tiếng Việt cho người nhập."""
    s = str(v or "").strip()[:10]
    if not s:
        if required:
            raise ValueError(f"Thiếu {label}.")
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise ValueError(f"{label} không hợp lệ (YYYY-MM-DD).") from exc


def clean(row: dict, company: str) -> dict[str, Any]:
    """Chuẩn hoá + KIỂM TRA 1 hợp đồng trước khi ghi (raise ValueError nếu sai)."""
    grade = str(row.get("grade") or "").strip()[:60]
    if not grade:
        raise ValueError("Thiếu chủng loại.")
    start = _as_date(row.get("start_date"), "Ngày bắt đầu tồn kho", required=True)
    delivery = _as_date(row.get("delivery_date"), "Lịch giao")
    delivered = _as_date(row.get("delivered_date"), "Ngày giao")
    # Tồn kho phải có ít nhất 1 ngày: bắt đầu phải TRƯỚC ngày giao (và trước lịch giao).
    if delivered and start >= delivered:
        raise ValueError("Ngày bắt đầu tồn kho phải trước Ngày giao ít nhất 1 ngày.")
    if delivery and start >= delivery:
        raise ValueError("Ngày bắt đầu tồn kho phải trước Lịch giao ít nhất 1 ngày.")

    def num(v):
        try:
            return None if v in (None, "") else float(v)
        except (TypeError, ValueError):
            return None

    # Đính kèm NHIỀU file; cột phẳng file/filename vẫn ghi = file ĐẦU để bản cũ/Excel đọc được.
    docs = contract_docs.normalize(row.get("files"), row.get("file"), row.get("filename"))
    first_file, first_name = contract_docs.first(docs)
    return {
        "id": int(row["id"]) if str(row.get("id") or "").strip().isdigit() else None,
        "company": company,
        "code": str(row.get("code") or "").strip()[:60] or None,
        "grade": grade,
        "qty": num(row.get("qty")),
        "price": num(row.get("price")),
        "ccy": row.get("ccy") if row.get("ccy") in _CCY else "VND",
        "fx": num(row.get("fx")),
        "start_date": start.isoformat(),
        "delivery_date": delivery.isoformat() if delivery else None,
        "delivered_date": delivered.isoformat() if delivered else None,
        "file": first_file,
        "filename": first_name,
        "files": docs,
    }


def list_contracts(companies: list[str] | None = None, as_of: str | None = None,
                   include_delivered: bool = True, date_from: str | None = None,
                   date_to: str | None = None, status: str | None = None,
                   q: str | None = None) -> list[dict[str, Any]]:
    """Danh sách hợp đồng. `as_of` → chỉ hợp đồng ĐANG TỒN ngày đó; `companies` → lọc đơn vị.

    Bộ lọc cho màn LỊCH SỬ (dùng khi KHÔNG có `as_of`): `status` ('undelivered' | 'delivered',
    None/khác = tất cả), `date_from`/`date_to` lọc theo Ngày bắt đầu tồn kho, `q` tìm theo
    Số HĐ/PL hoặc Chủng loại (không phân biệt hoa/thường).
    """
    ensure_schema()
    where, params = ["1 = 1"], {}
    if companies is not None:
        if not companies:
            return []
        where.append("company = ANY(:cs)")
        params["cs"] = list(companies)
    if as_of:
        where.append("start_date <= CAST(:d AS date)")
        where.append("(delivered_date IS NULL OR CAST(:d AS date) < delivered_date)")
        params["d"] = as_of
    elif not include_delivered:
        where.append("delivered_date IS NULL")
    if status == "undelivered":
        where.append("delivered_date IS NULL")
    elif status == "delivered":
        where.append("delivered_date IS NOT NULL")
    if date_from:
        where.append("start_date >= CAST(:df AS date)")
        params["df"] = date_from
    if date_to:
        where.append("start_date <= CAST(:dt AS date)")
        params["dt"] = date_to
    if q:
        where.append("(code ILIKE :q OR grade ILIKE :q)")
        params["q"] = f"%{q}%"
    with session_scope() as db:
        rows = db.execute(
            text(f"SELECT {', '.join(_COLS)} FROM unit_stock_contract WHERE {' AND '.join(where)} "
                 "ORDER BY start_date, company, id"),
            params,
        ).mappings().all()
    return [_row(r) for r in rows]


def active_on(as_of: str, companies: list[str] | None = None) -> dict[str, list[dict[str, Any]]]:
    """{đơn vị: [hợp đồng đang tồn ngày `as_of`]} — dùng gắn vào khối 3 của báo cáo ngày."""
    out: dict[str, list[dict[str, Any]]] = {}
    for r in list_contracts(companies=companies, as_of=as_of):
        out.setdefault(r["company"], []).append(r)
    return out


def save(row: dict, company: str, updated_by: str | None) -> dict[str, Any]:
    """Thêm mới (không có id) hoặc cập nhật 1 hợp đồng. Raise ValueError nếu số liệu sai."""
    d = clean(row, company)
    ensure_schema()
    before = _snapshot(d["id"]) if d["id"] is not None else None
    with session_scope() as db:
        if d["id"] is not None:
            cur = db.execute(text("SELECT company FROM unit_stock_contract WHERE id = :i"),
                             {"i": d["id"]}).scalar()
            if cur is None:
                raise ValueError("Hợp đồng không còn tồn tại (có thể đã bị xoá).")
            if cur != company:
                raise ValueError("Hợp đồng thuộc đơn vị khác.")
            db.execute(text(
                "UPDATE unit_stock_contract SET code = :code, grade = :grade, qty = :qty, "
                "price = :price, ccy = :ccy, fx = :fx, start_date = CAST(:start_date AS date), "
                "delivery_date = CAST(:delivery_date AS date), "
                "delivered_date = CAST(:delivered_date AS date), file = :file, filename = :filename, "
                "files = CAST(:files AS jsonb), "
                "updated_by = :by, updated_at = now() WHERE id = :id"),
                {**d, "files": json.dumps(d["files"]), "by": updated_by})
            new_id = d["id"]
        else:
            new_id = db.execute(text(
                "INSERT INTO unit_stock_contract (company, code, grade, qty, price, ccy, fx, "
                " start_date, delivery_date, delivered_date, file, filename, files, updated_by) "
                "VALUES (:company, :code, :grade, :qty, :price, :ccy, :fx, CAST(:start_date AS date), "
                " CAST(:delivery_date AS date), CAST(:delivered_date AS date), :file, :filename, "
                " CAST(:files AS jsonb), :by) "
                "RETURNING id"), {**d, "files": json.dumps(d["files"]), "by": updated_by}).scalar()
    saved = {**d, "id": new_id}
    audit_repo.log("stock_contract", "update" if before else "create", f"HĐ #{new_id}",
                   before=before, after=saved, as_of=saved.get("start_date"), company=company,
                   note=f"Số HĐ/PL: {saved.get('code') or '(không có)'}")
    return saved


def _snapshot(contract_id: int) -> dict[str, Any] | None:
    """Ảnh chụp 1 hợp đồng theo id (None nếu không có) — giá trị TRƯỚC khi sửa/xoá."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text(f"SELECT {', '.join(_COLS)} FROM unit_stock_contract WHERE id = :i"),
            {"i": contract_id}).mappings().first()
    return _row(row) if row else None


def delete(contract_id: int, companies: list[str] | None) -> bool:
    """Xoá 1 hợp đồng (chỉ trong các đơn vị được phép). False nếu không có/không thuộc quyền."""
    ensure_schema()
    before = _snapshot(contract_id)
    with session_scope() as db:
        cur = db.execute(text("SELECT company FROM unit_stock_contract WHERE id = :i"),
                         {"i": contract_id}).scalar()
        if cur is None or (companies is not None and cur not in companies):
            return False
        db.execute(text("DELETE FROM unit_stock_contract WHERE id = :i"), {"i": contract_id})
    audit_repo.log("stock_contract", "delete", f"HĐ #{contract_id}", before=before,
                   as_of=(before or {}).get("start_date"), company=cur)
    return True
