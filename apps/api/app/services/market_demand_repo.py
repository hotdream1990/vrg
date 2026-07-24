"""Repository Nhu cầu thị trường (market_demand): free text theo (đơn vị, ngày).

Đơn vị thành viên tự nhập của mình; chuyên viên có quyền `market_demand` xem/sửa mọi đơn vị.
Bảng nhỏ (đơn vị × ngày) → đọc cả 1 ngày rồi lọc ở tầng router cho gọn.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo

_UPSERT = text("""
    INSERT INTO market_demand (as_of, company, content, updated_by, updated_at)
    VALUES (:as_of, :company, :content, :updated_by, now())
    ON CONFLICT (as_of, company) DO UPDATE SET
        content = EXCLUDED.content, updated_by = EXCLUDED.updated_by, updated_at = now()
""")


def upsert(as_of: str, company: str, content: str, updated_by: str | None) -> None:
    """Ghi/ghi đè nhu cầu 1 đơn vị cho 1 ngày."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(text("SELECT content FROM market_demand "
                              "WHERE as_of = :a AND company = :c"),
                         {"a": as_of, "c": company}).first()
        before = {"content": row[0]} if row else None
        db.execute(_UPSERT, {"as_of": as_of, "company": company,
                             "content": content, "updated_by": updated_by})
    audit_repo.log("market_demand", "update" if before else "create", f"{as_of}|{company}",
                   before=before, after={"content": content}, as_of=as_of, company=company)


def entries_on(as_of: str) -> dict[str, str]:
    """content theo đơn vị cho 1 ngày → {company: content}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, content FROM market_demand WHERE as_of = :d"),
            {"d": as_of},
        ).mappings().all()
    return {r["company"]: r["content"] for r in rows}


def history(company: str, days: int) -> list[dict[str, Any]]:
    """Lịch sử nhu cầu 1 đơn vị (ngày giảm dần, bỏ ngày rỗng) — cho ngữ cảnh."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, content FROM market_demand "
                 "WHERE company = :c AND content <> '' "
                 "ORDER BY as_of DESC LIMIT :n"),
            {"c": company, "n": days},
        ).mappings().all()
    return [{"as_of": str(r["as_of"]), "content": r["content"]} for r in rows]


def recent(date_from: str, companies: list[str] | None = None) -> list[dict[str, Any]]:
    """Nhu cầu ĐÃ NHẬP (bỏ ngày rỗng) từ `date_from` → nay, ngày giảm dần — cho timeline.
    `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó (đơn vị thành viên).
    Chỉ trả ngày có nội dung nên timeline tự ẩn ngày trống."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, company, content, updated_by, updated_at FROM market_demand "
                 "WHERE content <> '' AND as_of >= :d ORDER BY as_of DESC, company"),
            {"d": date_from},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    return [{"as_of": str(r["as_of"]), "company": r["company"], "content": r["content"],
             "updated_by": r["updated_by"], "updated_at": str(r["updated_at"])}
            for r in rows if keep is None or r["company"] in keep]
