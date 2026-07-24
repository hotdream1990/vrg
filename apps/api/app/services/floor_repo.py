"""Repository Giá sàn Tập đoàn (vrg_floor_price) — biểu giá theo "lần" (nhập tay).

Mỗi lần = 1 số nguyên (tự nhảy) + ngày áp dụng + bảng giá theo chủng loại.
Bản tin tham chiếu 2 lần mới nhất <= ngày báo cáo (lần hiện tại + lần trước).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo


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
            SELECT lan, as_of, MAX(title) AS title, MAX(dispatch_no) AS dispatch_no,
                   COUNT(*) AS grades,
                   COUNT(fob_usd) + COUNT(domestic_vnd) AS filled,
                   MAX(ingested_at) AS updated
            FROM vrg_floor_price
            {clause}
            GROUP BY lan, as_of
            ORDER BY as_of DESC, lan DESC
        """), params).mappings().all()
        return [
            {**dict(r), "title": (r["title"] or "").strip() or f"Lần {int(r['lan'])}",
             "dispatch_no": (r["dispatch_no"] or "").strip()}
            for r in rows
        ]


def get_schedule(lan: int) -> dict[str, Any] | None:
    """1 biểu giá đầy đủ theo lần → {lan, as_of, items:[{grade, fob_usd, domestic_vnd}]}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("""
            SELECT lan, as_of, grade, fob_usd, domestic_vnd, title, dispatch_no, dispatch_summary
            FROM vrg_floor_price WHERE lan = :lan ORDER BY grade
        """), {"lan": lan}).mappings().all()
    if not rows:
        return None
    lan_val = int(rows[0]["lan"])
    return {
        "lan": lan_val,
        "as_of": str(rows[0]["as_of"]),
        "title": (rows[0]["title"] or "").strip() or f"Lần {lan_val}",
        "dispatch_no": (rows[0]["dispatch_no"] or "").strip(),
        "dispatch_summary": (rows[0]["dispatch_summary"] or "").strip(),
        "items": [{"grade": r["grade"], "fob_usd": r["fob_usd"],
                   "domestic_vnd": r["domestic_vnd"]} for r in rows],
    }


def save_schedule(
    lan: int, as_of: str, items: list[dict[str, Any]], title: str | None = None,
    dispatch_no: str | None = None, dispatch_summary: str | None = None,
) -> None:
    """Ghi/cập nhật toàn bộ 1 biểu giá (upsert theo (lan, grade)).

    `title` = tiêu đề custom; `dispatch_no`/`dispatch_summary` = số + trích yếu công văn
    (metadata theo lần, ghi giống nhau trên mọi dòng grade như `title`).
    """
    ensure_schema()
    title = (title or "").strip() or None
    dispatch_no = (dispatch_no or "").strip() or None
    dispatch_summary = (dispatch_summary or "").strip() or None
    rows = [{
        "lan": lan, "as_of": as_of, "grade": it["grade"], "title": title,
        "dispatch_no": dispatch_no, "dispatch_summary": dispatch_summary,
        "fob_usd": it.get("fob_usd"), "domestic_vnd": it.get("domestic_vnd"),
    } for it in items if it.get("grade")]
    if not rows:
        return
    before = get_schedule(lan)
    with session_scope() as db:
        db.execute(text("""
            INSERT INTO vrg_floor_price
                (lan, as_of, grade, fob_usd, domestic_vnd, title, dispatch_no, dispatch_summary)
            VALUES (:lan, :as_of, :grade, :fob_usd, :domestic_vnd, :title, :dispatch_no, :dispatch_summary)
            ON CONFLICT (lan, grade) DO UPDATE SET
                as_of = EXCLUDED.as_of, fob_usd = EXCLUDED.fob_usd,
                domestic_vnd = EXCLUDED.domestic_vnd, title = EXCLUDED.title,
                dispatch_no = EXCLUDED.dispatch_no, dispatch_summary = EXCLUDED.dispatch_summary,
                ingested_at = now()
        """), rows)
    audit_repo.log("floor", "update" if before else "create", f"Lần {lan}",
                   before=before, after=get_schedule(lan), as_of=as_of)


def delete_schedule(lan: int) -> bool:
    """Xoá toàn bộ 1 biểu giá theo lần."""
    ensure_schema()
    before = get_schedule(lan)
    with session_scope() as db:
        res = db.execute(text("DELETE FROM vrg_floor_price WHERE lan = :lan"), {"lan": lan})
        deleted = res.rowcount > 0
    if deleted:
        audit_repo.log("floor", "delete", f"Lần {lan}", before=before,
                       as_of=(before or {}).get("as_of"))
    return deleted


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
