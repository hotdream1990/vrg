"""Repository CHỐT SỐ LIỆU ĐƠN VỊ — đợt chốt của Ban (`data_lock_round`) + xác nhận của từng đơn
vị (`unit_data_lock`).

Luật gốc (chốt 25/08/2026):
- Ban phát một ĐỢT CHỐT "chốt số liệu đến hết ngày X". Đợt mới không xoá đợt cũ — lịch sử giữ lại.
- Đơn vị tự rà rồi XÁC NHẬN. Xác nhận xong, số liệu ngày ≤ X khoá lại **với chính đơn vị đó**;
  chuyên viên và quản trị vẫn sửa được (sau khi chốt đó là đường sửa duy nhất).
- Quản trị khoá/mở hộ được (đơn vị không chịu bấm, hoặc bấm nhầm cần mở ra).
- Mốc khoá của một đơn vị = **ngày chốt LỚN NHẤT** trong các đợt CHƯA HUỶ mà đơn vị đã xác nhận.
  Huỷ đợt = gỡ khoá của đợt đó cho mọi đơn vị (không phải xoá dữ liệu).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

from app.core.db import ensure_schema, session_scope
from app.services import audit_repo

_ROUND_COLS = "id, lock_date, note, created_at, created_by, cancelled_at"


def _round_row(r) -> dict[str, Any]:
    d = dict(r)
    d["lock_date"] = str(d["lock_date"]) if d.get("lock_date") else None
    for k in ("created_at", "cancelled_at"):
        d[k] = d[k].isoformat() if d.get(k) else None
    for k in ("locked", "pending"):
        if k in d:
            d[k] = int(d[k] or 0)
    return d


# ── Đợt chốt ──────────────────────────────────────────────────────────────────
def list_rounds(limit: int = 20) -> list[dict[str, Any]]:
    """Các đợt chốt mới nhất (số đơn vị đã chốt do router đếm — xem `confirmed_companies`)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            f"SELECT {_ROUND_COLS} FROM data_lock_round ORDER BY lock_date DESC, id DESC LIMIT :n"),
            {"n": limit}).mappings().all()
        return [_round_row(r) for r in rows]


def confirmed_companies(round_ids: list[int]) -> dict[int, set[str]]:
    """{đợt: các đơn vị đã có xác nhận} — không kéo ảnh chụp (nặng) như `confirms_of_round`."""
    if not round_ids:
        return {}
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text("SELECT round_id, company FROM unit_data_lock "
                               " WHERE round_id = ANY(:ids)"), {"ids": list(round_ids)}).all()
    out: dict[int, set[str]] = {int(i): set() for i in round_ids}
    for rid, company in rows:
        out[int(rid)].add(company)
    return out


def current_round() -> dict[str, Any] | None:
    """Đợt chốt ĐANG hiệu lực = đợt chưa huỷ có ngày chốt mới nhất (đơn vị chỉ thấy đợt này)."""
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(
            f"SELECT {_ROUND_COLS} FROM data_lock_round WHERE cancelled_at IS NULL "
            " ORDER BY lock_date DESC, id DESC LIMIT 1")).mappings().first()
        return _round_row(r) if r else None


def get_round(round_id: int) -> dict[str, Any] | None:
    ensure_schema()
    with session_scope() as db:
        r = db.execute(text(f"SELECT {_ROUND_COLS} FROM data_lock_round WHERE id = :id"),
                       {"id": round_id}).mappings().first()
        return _round_row(r) if r else None


def save_round(lock_date: str, note: str | None, username: str | None,
               round_id: int | None = None) -> dict[str, Any]:
    """Tạo đợt chốt mới, hoặc sửa ngày/lời nhắn của đợt đã có.

    ⚠ Sửa NGÀY của đợt đã có đơn vị xác nhận = đổi luôn mốc khoá của họ (không bắt xác nhận lại).
    Cố ý: Ban đính chính ngày là chuyện thường, bắt cả loạt đơn vị bấm lại chỉ gây nhiễu; trang
    theo dõi vẫn hiện ngày chốt hiện hành nên không ai hiểu nhầm.
    """
    ensure_schema()
    before = get_round(round_id) if round_id else None
    with session_scope() as db:
        if round_id:
            db.execute(text("UPDATE data_lock_round SET lock_date = CAST(:d AS date), note = :n "
                            " WHERE id = :id"),
                       {"d": lock_date, "n": note, "id": round_id})
            new_id = round_id
        else:
            new_id = db.execute(text(
                "INSERT INTO data_lock_round (lock_date, note, created_by) "
                "VALUES (CAST(:d AS date), :n, :u) RETURNING id"),
                {"d": lock_date, "n": note, "u": username}).scalar()
    audit_repo.log("data_lock_round", "update" if round_id else "create", str(new_id),
                   before=before, after={"lock_date": lock_date, "note": note}, as_of=lock_date)
    return get_round(int(new_id)) or {}


def set_cancelled(round_id: int, cancelled: bool) -> dict[str, Any] | None:
    """Huỷ đợt (mọi khoá của đợt hết hiệu lực) hoặc mở lại đợt đã huỷ."""
    ensure_schema()
    before = get_round(round_id)
    if not before:
        return None
    with session_scope() as db:
        db.execute(text("UPDATE data_lock_round SET cancelled_at = "
                        "  CASE WHEN :c THEN now() ELSE NULL END WHERE id = :id"),
                   {"c": cancelled, "id": round_id})
    audit_repo.log("data_lock_round", "cancel" if cancelled else "reopen", str(round_id),
                   before=before, as_of=before.get("lock_date"))
    return get_round(round_id)


def delete_round(round_id: int) -> bool:
    """Xoá hẳn một đợt (kèm mọi xác nhận của đợt đó) — dùng khi lỡ tạo nhầm."""
    ensure_schema()
    before = get_round(round_id)
    if not before:
        return False
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_data_lock WHERE round_id = :id"), {"id": round_id})
        db.execute(text("DELETE FROM data_lock_round WHERE id = :id"), {"id": round_id})
    audit_repo.log("data_lock_round", "delete", str(round_id), before=before,
                   as_of=before.get("lock_date"))
    return True


# ── Xác nhận của đơn vị ───────────────────────────────────────────────────────
def confirm(round_id: int, company: str, username: str | None, *,
            by_admin: bool = False, snapshot: dict | None = None) -> None:
    """Ghi xác nhận chốt của 1 đơn vị (bấm lại không tạo dòng thứ hai — giữ lần đầu)."""
    import json

    ensure_schema()
    with session_scope() as db:
        n = db.execute(text(
            "INSERT INTO unit_data_lock (round_id, company, locked_by, by_admin, snapshot) "
            "VALUES (:r, :c, :u, :a, CAST(:s AS jsonb)) "
            "ON CONFLICT (round_id, company) DO NOTHING"),
            {"r": round_id, "c": company, "u": username, "a": by_admin,
             "s": json.dumps(snapshot or {}, ensure_ascii=False)}).rowcount
    if not n:       # đã có xác nhận (bấm lại / chốt kèm lần 2) → không ghi nhật ký "tạo" giả
        return
    audit_repo.log("unit_data_lock", "create", f"{round_id}|{company}",
                   after={"by_admin": by_admin}, company=company)


def unlock(round_id: int, company: str) -> bool:
    """Gỡ xác nhận của 1 đơn vị trong 1 đợt (quản trị mở khoá cho đơn vị nhập bù/sửa)."""
    ensure_schema()
    with session_scope() as db:
        n = db.execute(text("DELETE FROM unit_data_lock WHERE round_id = :r AND company = :c"),
                       {"r": round_id, "c": company}).rowcount
    if n:
        audit_repo.log("unit_data_lock", "delete", f"{round_id}|{company}", company=company)
    return bool(n)


def rounds_locked_from(company: str, from_date: str, to_date: str | None = None) -> list[dict[str, Any]]:
    """Các đợt CHƯA HUỶ đơn vị đã xác nhận có ngày chốt ≥ `from_date` (và ≤ `to_date` nếu có) — đúng
    những xác nhận phải gỡ khi Ban duyệt một đề nghị sửa số liệu ngày `from_date` (đợt cũ hơn ngày sửa
    giữ nguyên). `to_date`: đề nghị sửa Kế hoạch năm chỉ gỡ đợt của đúng năm đó."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT r.id, r.lock_date FROM unit_data_lock l "
            "  JOIN data_lock_round r ON r.id = l.round_id "
            " WHERE l.company = :c AND r.cancelled_at IS NULL "
            "   AND r.lock_date >= CAST(:d AS date) "
            "   AND (CAST(:t AS date) IS NULL OR r.lock_date <= CAST(:t AS date)) "
            " ORDER BY r.lock_date, r.id"),
            {"c": company, "d": from_date, "t": to_date}).mappings().all()
    return [{"round_id": int(r["id"]), "lock_date": str(r["lock_date"])} for r in rows]


def locked_until(company: str) -> date | None:
    """Mốc khoá của một đơn vị: ngày chốt lớn nhất trong các đợt CHƯA HUỶ đã được xác nhận."""
    ensure_schema()
    with session_scope() as db:
        return db.execute(text(
            "SELECT max(r.lock_date) FROM unit_data_lock l "
            "  JOIN data_lock_round r ON r.id = l.round_id "
            " WHERE l.company = :c AND r.cancelled_at IS NULL"), {"c": company}).scalar()


def locked_before_map(companies: list[str], before: str) -> dict[str, str]:
    """{đơn vị: mốc chốt gần nhất TRƯỚC ngày `before`} — đầu kỳ của đợt chốt đang xét.

    Đầu kỳ phải tính theo ĐƠN VỊ, không theo đợt: Ban có thể phát một đợt riêng cho vài đơn vị
    (vd chốt trước sáp nhập) mà đơn vị khác không dính vào. Lấy "đợt liền trước của hệ thống" thì
    đơn vị chưa chốt lần nào cũng bị cắt đầu kỳ theo đợt của người khác — đã xảy ra thật
    27/08/2026: 13 đơn vị xác nhận trên bảng 6 ngày thay vì lũy kế từ đầu năm.
    """
    ensure_schema()
    if not companies:
        return {}
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT l.company, max(r.lock_date) AS d FROM unit_data_lock l "
            "  JOIN data_lock_round r ON r.id = l.round_id "
            " WHERE l.company = ANY(:cs) AND r.cancelled_at IS NULL "
            "   AND r.lock_date < CAST(:d AS date) GROUP BY l.company"),
            {"cs": list(companies), "d": before}).mappings().all()
    return {r["company"]: str(r["d"]) for r in rows}


def locked_map() -> dict[str, str]:
    """{đơn vị: ngày khoá} cho MỌI đơn vị đang bị khoá — dùng cho bảng theo dõi (1 truy vấn)."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT l.company, max(r.lock_date) AS d FROM unit_data_lock l "
            "  JOIN data_lock_round r ON r.id = l.round_id "
            " WHERE r.cancelled_at IS NULL GROUP BY l.company")).mappings().all()
        return {r["company"]: str(r["d"]) for r in rows}


def confirms_of_round(round_id: int) -> dict[str, dict[str, Any]]:
    """Xác nhận của một đợt → {đơn vị: {locked_at, locked_by, by_admin, snapshot}}."""
    ensure_schema()
    with session_scope() as db:
        rows = db.execute(text(
            "SELECT company, locked_at, locked_by, by_admin, snapshot FROM unit_data_lock "
            " WHERE round_id = :r"), {"r": round_id}).mappings().all()
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = dict(r)
        d["locked_at"] = d["locked_at"].isoformat() if d.get("locked_at") else None
        out[d.pop("company")] = d
    return out
