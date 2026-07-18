"""Repository báo cáo tiêu thụ–tồn kho theo ngày (unit_daily_report) + chỉ tiêu kế hoạch thu mua.

2 loại báo cáo ('purchase' / 'consumption'), số liệu jsonb theo (ngày, đơn vị). Đơn vị tự nhập
của mình; chuyên viên có quyền `unit_daily` xem/sửa mọi đơn vị — realtime theo mốc updated_at.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import unit_daily_fields

_UPSERT = text("""
    INSERT INTO unit_daily_report (as_of, company, kind, payload, updated_by, updated_at)
    VALUES (:as_of, :company, :kind, CAST(:payload AS jsonb), :updated_by, now())
    ON CONFLICT (as_of, company, kind) DO UPDATE SET
        payload = EXCLUDED.payload, updated_by = EXCLUDED.updated_by, updated_at = now()
""")


def upsert(kind: str, as_of: str, company: str, fields: dict, updated_by: str | None) -> None:
    """Ghi/ghi đè số liệu 1 đơn vị cho 1 ngày (payload đã lọc theo allowlist)."""
    import json

    clean = unit_daily_fields.clean_fields(kind, fields)
    ensure_schema()
    with session_scope() as db:
        db.execute(_UPSERT, {"as_of": as_of, "company": company, "kind": kind,
                             "payload": json.dumps(clean), "updated_by": updated_by})


def has_entry(kind: str, as_of: str, company: str) -> bool:
    """Đã có bản ghi CÓ số liệu cho (ngày, đơn vị, loại) chưa — dùng chống ghi trùng."""
    ensure_schema()
    with session_scope() as db:
        row = db.execute(
            text("SELECT payload FROM unit_daily_report "
                 "WHERE kind = :k AND as_of = :d AND company = :c"),
            {"k": kind, "d": as_of, "c": company},
        ).scalar()
    return bool(row)


def entries_on(kind: str, as_of: str) -> dict[str, dict[str, Any]]:
    """Số liệu mọi đơn vị cho 1 ngày → {company: {fields, updated_at, updated_by}}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, payload, updated_at, updated_by FROM unit_daily_report "
                 "WHERE kind = :k AND as_of = :d"),
            {"k": kind, "d": as_of},
        ).mappings().all()
    return {r["company"]: {"fields": dict(r["payload"] or {}),
                           "updated_at": str(r["updated_at"]), "updated_by": r["updated_by"]}
            for r in rows}


def recent(kind: str, date_from: str, companies: list[str] | None = None) -> list[dict[str, Any]]:
    """Các bản ghi CÓ số liệu từ ngày `date_from` → nay (ngày giảm dần) — cho timeline.
    `companies`=None → mọi đơn vị (chuyên viên); có danh sách → chỉ các đơn vị đó (đơn vị thành viên)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT as_of, company, payload, updated_at, updated_by FROM unit_daily_report "
                 "WHERE kind = :k AND as_of >= :d AND payload <> '{}'::jsonb "
                 "ORDER BY as_of DESC, company"),
            {"k": kind, "d": date_from},
        ).mappings().all()
    keep = set(companies) if companies is not None else None
    return [{"as_of": str(r["as_of"]), "company": r["company"], "fields": dict(r["payload"] or {}),
             "updated_at": str(r["updated_at"]), "updated_by": r["updated_by"]}
            for r in rows if keep is None or r["company"] in keep]


# ── Chỉ tiêu kế hoạch thu mua theo năm (tính % kế hoạch) ──
def plans_for_year(year: int) -> dict[str, float]:
    """{company: plan_tonnes} cho 1 năm (bỏ đơn vị chưa cấu hình)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(
            text("SELECT company, plan_tonnes FROM unit_purchase_plan WHERE year = :y"),
            {"y": year},
        ).mappings().all()
    return {r["company"]: r["plan_tonnes"] for r in rows if r["plan_tonnes"] is not None}


def set_plan(year: int, company: str, plan_tonnes: float | None, updated_by: str | None) -> None:
    """Đặt/xoá (None) chỉ tiêu kế hoạch thu mua năm cho 1 đơn vị."""
    ensure_schema()
    with session_scope() as db:
        db.execute(
            text("INSERT INTO unit_purchase_plan (year, company, plan_tonnes, updated_by, updated_at) "
                 "VALUES (:y, :c, :p, :by, now()) "
                 "ON CONFLICT (year, company) DO UPDATE SET "
                 "plan_tonnes = EXCLUDED.plan_tonnes, updated_by = EXCLUDED.updated_by, updated_at = now()"),
            {"y": year, "c": company, "p": plan_tonnes, "by": updated_by},
        )
