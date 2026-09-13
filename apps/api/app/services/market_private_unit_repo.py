"""Danh mục "đơn vị tư nhân" cho Mục 6 Báo giá mủ thị trường (giá mủ tư nhân).

Chỉ giữ TÊN. Giá theo ngày nằm trong phiếu (`market_quote.payload.private_prices`, khoá = tên), nên
xoá một đơn vị khỏi danh mục KHÔNG mất giá đã nhập ở các phiếu cũ — phiếu cũ vẫn hiện dòng đó.
Quyền: chuyên viên có quyền Báo giá (mức Sửa) được THÊM; chỉ admin được XOÁ (gác ở router).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo

_ENTITY = "market_private_unit"


def _clean(name: str) -> str:
    """Bỏ khoảng trắng thừa — "Long Hòa ,  Phú Bình" và "Long Hòa , Phú Bình" là một."""
    return re.sub(r"\s+", " ", (name or "").strip())


def list_units() -> list[dict[str, Any]]:
    """Danh mục theo thứ tự thêm vào (dòng thêm trước đứng trước, như bảng giấy)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT id, name FROM market_private_unit ORDER BY id")).mappings().all()
    return [dict(r) for r in rows]


def add_unit(name: str, username: str) -> dict[str, Any]:
    """Thêm 1 đơn vị. ValueError nếu tên rỗng hoặc đã có (không phân biệt hoa/thường)."""
    clean = _clean(name)
    if not clean:
        raise ValueError("Nhập tên đơn vị tư nhân")
    ensure_schema()
    with session_scope() as db:
        dup = db.execute(text("SELECT name FROM market_private_unit WHERE lower(name) = lower(:n)"),
                         {"n": clean}).scalar()
        if dup:
            raise ValueError(f"Đã có đơn vị tư nhân “{dup}” trong danh mục")
    try:
        with session_scope() as db:
            row = db.execute(text("INSERT INTO market_private_unit (name, created_by) VALUES (:n, :u) "
                                  "RETURNING id, name"), {"n": clean, "u": username}).mappings().first()
    except IntegrityError as exc:  # hai người thêm cùng tên cùng lúc → chỉ mục unique chặn
        raise ValueError(f"Đã có đơn vị tư nhân “{clean}” trong danh mục") from exc
    created = dict(row)
    audit_repo.log(_ENTITY, "create", clean, after=created)
    return created


def delete_unit(unit_id: int) -> bool:
    """Xoá khỏi danh mục (giá ở các phiếu đã lưu giữ nguyên)."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("DELETE FROM market_private_unit WHERE id = :i RETURNING id, name"),
                         {"i": unit_id}).mappings().first()
    if not row:
        return False
    audit_repo.log(_ENTITY, "delete", row["name"], before=dict(row))
    return True
