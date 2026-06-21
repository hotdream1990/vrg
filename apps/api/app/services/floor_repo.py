"""Repository Giá sàn Tập đoàn (vrg_floor_price) — biểu giá theo "lần" (nhập tay).

Mỗi lần = 1 số nguyên (tự nhảy) + ngày áp dụng + bảng giá theo chủng loại.
Bản tin tham chiếu 2 lần mới nhất <= ngày báo cáo (lần hiện tại + lần trước).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope


def next_lan() -> int:
    """Số lần kế tiếp = max(lan)+1 (mặc định 1)."""
    ensure_schema()
    with session_scope() as db:
        n = db.execute(text("SELECT COALESCE(MAX(lan), 0) FROM vrg_floor_price")).scalar()
        return int(n or 0) + 1


def list_schedules(date_from: str | None = None, date_to: str | None = None) -> list[dict[str, Any]]:
    """Danh sách biểu giá (mỗi lần 1 dòng tóm tắt), mới nhất trước. Lọc theo khoảng ngày áp dụng."""
    ensure_schema()
    where, params = [], {}
    if date_from:
        where.append("as_of >= CAST(:dfrom AS date)")
        params["dfrom"] = date_from
    if date_to:
        where.append("as_of <= CAST(:dto AS date)")
        params["dto"] = date_to
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    with session_scope() as db:
        rows = db.execute(text(f"""
            SELECT lan, as_of, COUNT(*) AS grades,
                   COUNT(fob_usd) + COUNT(domestic_vnd) AS filled,
                   MAX(ingested_at) AS updated
            FROM vrg_floor_price
            {clause}
            GROUP BY lan, as_of
            ORDER BY as_of DESC, lan DESC
        """), params).mappings().all()
        return [dict(r) for r in rows]


def get_schedule(lan: int) -> dict[str, Any] | None:
    """1 biểu giá đầy đủ theo lần → {lan, as_of, items:[{grade, fob_usd, domestic_vnd}]}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("""
            SELECT lan, as_of, grade, fob_usd, domestic_vnd
            FROM vrg_floor_price WHERE lan = :lan ORDER BY grade
        """), {"lan": lan}).mappings().all()
    if not rows:
        return None
    return {
        "lan": int(rows[0]["lan"]),
        "as_of": str(rows[0]["as_of"]),
        "items": [{"grade": r["grade"], "fob_usd": r["fob_usd"],
                   "domestic_vnd": r["domestic_vnd"]} for r in rows],
    }


def save_schedule(lan: int, as_of: str, items: list[dict[str, Any]]) -> None:
    """Ghi/cập nhật toàn bộ 1 biểu giá (upsert theo (lan, grade))."""
    ensure_schema()
    rows = [{
        "lan": lan, "as_of": as_of, "grade": it["grade"],
        "fob_usd": it.get("fob_usd"), "domestic_vnd": it.get("domestic_vnd"),
    } for it in items if it.get("grade")]
    if not rows:
        return
    with session_scope() as db:
        db.execute(text("""
            INSERT INTO vrg_floor_price (lan, as_of, grade, fob_usd, domestic_vnd)
            VALUES (:lan, :as_of, :grade, :fob_usd, :domestic_vnd)
            ON CONFLICT (lan, grade) DO UPDATE SET
                as_of = EXCLUDED.as_of, fob_usd = EXCLUDED.fob_usd,
                domestic_vnd = EXCLUDED.domestic_vnd, ingested_at = now()
        """), rows)


def delete_schedule(lan: int) -> bool:
    """Xoá toàn bộ 1 biểu giá theo lần."""
    ensure_schema()
    with session_scope() as db:
        res = db.execute(text("DELETE FROM vrg_floor_price WHERE lan = :lan"), {"lan": lan})
        return res.rowcount > 0


def floor_for_bulletin(report_date: str) -> dict[str, Any]:
    """2 biểu giá mới nhất <= ngày báo cáo → {curr, prev} (mỗi cái = get_schedule hoặc None)."""
    ensure_schema()
    with session_scope() as db:
        lans = db.execute(text("""
            SELECT DISTINCT lan, as_of FROM vrg_floor_price
            WHERE as_of <= CAST(:d AS date)
            ORDER BY as_of DESC, lan DESC LIMIT 2
        """), {"d": report_date}).mappings().all()
    curr = get_schedule(int(lans[0]["lan"])) if len(lans) >= 1 else None
    prev = get_schedule(int(lans[1]["lan"])) if len(lans) >= 2 else None
    return {"curr": curr, "prev": prev}
