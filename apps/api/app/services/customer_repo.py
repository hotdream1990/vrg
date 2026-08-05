"""Repository DANH MỤC KHÁCH HÀNG của đơn vị thành viên (unit_customer).

Chốt 30/07/2026 (Q6): danh mục quản lý RIÊNG cho từng đơn vị — KHÔNG dùng chung ở cấp Tập đoàn.
Hợp đồng chỉ được gán khách hàng của CHÍNH đơn vị đó (kiểm ở `sales_contract_repo.save`).
Trùng tên trong cùng một đơn vị bị chặn ở tầng DB (unique theo `company` + tên viết thường).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core import vn_text
from app.core.db import ensure_schema, session_scope
from app.services import audit_repo

_COLS = ("id", "company", "code", "name", "tax_code", "note", "is_active")


def _row(r) -> dict[str, Any]:
    d = dict(r)
    d.pop("total", None)      # cột đếm tổng của câu phân trang, không thuộc bản ghi khách hàng
    return d


def clean(row: dict, company: str) -> dict[str, Any]:
    """Chuẩn hoá + kiểm tra 1 khách hàng trước khi ghi (raise ValueError nếu sai)."""
    name = str(row.get("name") or "").strip()[:200]
    if not name:
        raise ValueError("Thiếu tên khách hàng.")
    return {
        "id": int(row["id"]) if str(row.get("id") or "").strip().isdigit() else None,
        "company": company,
        "code": str(row.get("code") or "").strip()[:60] or None,
        "name": name,
        "tax_code": str(row.get("tax_code") or "").strip()[:40] or None,
        "note": str(row.get("note") or "").strip()[:500] or None,
        "is_active": bool(row.get("is_active", True)),
    }


def list_customers(companies: list[str] | None = None, include_inactive: bool = True,
                   q: str | None = None, *, company: str | None = None,
                   ids: list[int] | None = None, limit: int | None = None,
                   offset: int = 0) -> dict[str, Any]:
    """Danh sách khách hàng. `companies=None` = mọi đơn vị (chuyên viên); `[]` = không đơn vị nào.

    `companies` là PHẠM VI QUYỀN (server ép, không bao giờ bỏ qua); `company` là bộ lọc người dùng
    chọn thêm — hai thứ khác nhau, cùng áp một lúc.
    `q` tìm theo tên / mã / mã số thuế; `ids` lấy đúng vài khách theo id (ô chọn khách hàng cần
    tra lại TÊN của các id đang chọn khi chúng không nằm trong trang kết quả tìm kiếm hiện tại);
    `limit`/`offset` cắt trang Ở SERVER — danh mục của cả Tập đoàn dài dần theo từng đơn vị nên
    KHÔNG bao giờ trả hết về máy; trả kèm `total` để màn quản lý hiện đúng tổng số.
    """
    ensure_schema()
    where, params = ["1 = 1"], {}
    if companies is not None:
        if not companies:
            return {"items": [], "total": 0}
        where.append("company = ANY(:cs)")
        params["cs"] = list(companies)
    if company:
        where.append("company = :co")
        params["co"] = company
    if ids is not None:
        if not ids:
            return {"items": [], "total": 0}
        where.append("id = ANY(:ids)")
        params["ids"] = [int(i) for i in ids]
    if not include_inactive:
        where.append("is_active")
    if q:
        # Tìm KHÔNG DẤU: gõ "sai gon" phải ra "Công ty CP Cao su Sài Gòn". Người nhập liệu gõ vội,
        # gõ đúng dấu mới ra kết quả thì họ tưởng chưa có khách hàng rồi tạo trùng một bản ghi nữa.
        cols = " OR ".join(f"{vn_text.fold_sql(c)} LIKE :q" for c in ("name", "code", "tax_code"))
        where.append(f"({cols})")
        params.update(vn_text.FOLD_PARAMS)
        params["q"] = f"%{vn_text.fold(q)}%"
    sql = (f"SELECT {', '.join(_COLS)}, count(*) OVER () AS total FROM unit_customer "
           f"WHERE {' AND '.join(where)} ORDER BY company, name")
    if limit:
        sql += " LIMIT :lim OFFSET :off"
        params["lim"], params["off"] = int(limit), max(0, int(offset))
    with session_scope() as db:
        rows = db.execute(text(sql), params).mappings().all()
    return {"items": [_row(r) for r in rows],
            "total": int(rows[0]["total"]) if rows else 0}


def names_by_id(companies: list[str] | None = None,
                ids: list[int] | None = None) -> dict[int, str]:
    """{id: tên khách} — gắn tên khách vào danh sách hợp đồng/báo cáo mà không join thêm.

    Truyền `ids` để chỉ lấy đúng các khách đang cần (danh mục cả Tập đoàn có thể rất dài).
    """
    return {c["id"]: c["name"] for c in list_customers(companies, ids=ids)["items"]}


def _snapshot(customer_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text(f"SELECT {', '.join(_COLS)} FROM unit_customer WHERE id = :i"),
                         {"i": customer_id}).mappings().first()
    return _row(row) if row else None


def owner_of(customer_id: int) -> str | None:
    """Đơn vị sở hữu khách hàng này (None nếu không có) — dùng kiểm chéo khi gán vào hợp đồng."""
    ensure_schema()
    with session_scope() as db:
        return db.execute(text("SELECT company FROM unit_customer WHERE id = :i"),
                          {"i": customer_id}).scalar()


def save(row: dict, company: str, updated_by: str | None) -> dict[str, Any]:
    """Thêm mới (không có id) hoặc cập nhật 1 khách hàng. Raise ValueError nếu số liệu sai."""
    d = clean(row, company)
    ensure_schema()
    before = _snapshot(d["id"]) if d["id"] is not None else None
    try:
        with session_scope() as db:
            if d["id"] is not None:
                cur = db.execute(text("SELECT company FROM unit_customer WHERE id = :i"),
                                 {"i": d["id"]}).scalar()
                if cur is None:
                    raise ValueError("Khách hàng không còn tồn tại (có thể đã bị xoá).")
                if cur != company:
                    raise ValueError("Khách hàng thuộc đơn vị khác.")
                db.execute(text(
                    "UPDATE unit_customer SET code = :code, name = :name, tax_code = :tax_code, "
                    "note = :note, is_active = :is_active, updated_by = :by, updated_at = now() "
                    "WHERE id = :id"), {**d, "by": updated_by})
                new_id = d["id"]
            else:
                new_id = db.execute(text(
                    "INSERT INTO unit_customer (company, code, name, tax_code, note, is_active, "
                    " updated_by) VALUES (:company, :code, :name, :tax_code, :note, :is_active, :by) "
                    "RETURNING id"), {**d, "by": updated_by}).scalar()
    except IntegrityError as exc:
        raise ValueError(f"Đơn vị đã có khách hàng tên “{d['name']}”.") from exc
    saved = {**d, "id": new_id}
    audit_repo.log("customer", "update" if before else "create", saved["name"],
                   before=before, after=saved, company=company)
    return saved


def delete(customer_id: int, companies: list[str] | None) -> bool:
    """Xoá 1 khách hàng. Chặn khi đã có hợp đồng tham chiếu (giữ toàn vẹn số liệu lịch sử)."""
    ensure_schema()
    before = _snapshot(customer_id)
    with session_scope() as db:
        cur = db.execute(text("SELECT company FROM unit_customer WHERE id = :i"),
                         {"i": customer_id}).scalar()
        if cur is None or (companies is not None and cur not in companies):
            return False
        used = db.execute(text("SELECT count(*) FROM sales_contract WHERE customer_id = :i"),
                          {"i": customer_id}).scalar() or 0
        if used:
            raise ValueError(
                f"Khách hàng đang gắn với {used} hợp đồng — hãy ẩn (bỏ tick Đang dùng) thay vì xoá.")
        db.execute(text("DELETE FROM unit_customer WHERE id = :i"), {"i": customer_id})
    audit_repo.log("customer", "delete", (before or {}).get("name") or f"#{customer_id}",
                   before=before, company=cur)
    return True
