"""Router CHỐT SỐ LIỆU ĐƠN VỊ (25/08/2026).

Hai phía dùng chung router này:
- **Đơn vị thành viên**: xem đợt chốt đang có, xem bảng số liệu sẽ chốt, bấm XÁC NHẬN cho đơn vị
  của mình (`/current`, `/summary`, `/confirm`).
- **Ban TTKD / quản trị**: tạo–sửa–huỷ đợt chốt, theo dõi đơn vị nào đã/chưa xác nhận, khoá hoặc
  mở khoá hộ (`/rounds`, `/status`, `/lock`, `/unlock`).

Quyền: xem/theo dõi cần cap `unit_daily` (đúng nhóm quyền của Ban với số liệu đơn vị) — KHÔNG tạo
cap mới để hậu-deploy không phải cấp lại quyền. Mọi thao tác GHI của Ban (tạo đợt, khoá, mở khoá)
chỉ dành cho **quản trị**: chốt số liệu là quyết định điều hành, không phải thao tác nhập liệu.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import edit_window
from app.core.security import get_current_user, require_admin, require_cap, user_caps
from app.core.permissions import LEVEL_VIEW, has_cap
from app.schemas.data_lock import LockConfirmIn, LockRoundIn, LockUnitsIn
from app.services import data_lock_repo, data_lock_summary, member_unit_repo, user_repo
from app.services.unit_report_query import report_units

router = APIRouter(prefix="/api/data-lock", tags=["data-lock"])
_admin = [Depends(require_admin)]
_ban = [Depends(require_cap("unit_daily"))]


def _me(username: str) -> dict:
    return user_repo.get_user(username) or {}


def _my_units(username: str) -> list[str] | None:
    """Đơn vị tài khoản được phép thao tác: member → danh sách gán; Ban/quản trị → None (mọi đơn vị)."""
    u = _me(username)
    if u.get("role") == "member":
        return list(u.get("member_units") or [])
    if u.get("role") == "admin" or has_cap(user_caps(username), "unit_daily", LEVEL_VIEW):
        return None
    raise HTTPException(403, "Bạn không được phân quyền với mục dữ liệu này")


def _assert_company(username: str, company: str) -> None:
    units = _my_units(username)
    if units is not None and company not in units:
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _prev_lock_date(round_id: int, lock_date: str) -> str | None:
    """Ngày chốt của đợt LIỀN TRƯỚC (chưa huỷ) — đầu kỳ của bảng số liệu sẽ chốt."""
    prev = [r for r in data_lock_repo.list_rounds(50)
            if not r["cancelled_at"] and r["id"] != round_id and r["lock_date"] < lock_date]
    return max((r["lock_date"] for r in prev), default=None)


# ── Phía ĐƠN VỊ ───────────────────────────────────────────────────────────────
@router.get("/current")
def current(username: str = Depends(get_current_user)) -> dict:
    """Đợt chốt đang hiệu lực + trạng thái từng đơn vị của tài khoản (nguồn của banner cảnh báo).

    Trả cả `locked_until` để màn nhập liệu biết ngày nào đã khoá mà chuyển sang "chỉ xem".
    """
    rnd = data_lock_repo.current_round()
    units = _my_units(username)
    if units is None:
        units = [u["name"] for u in report_units(split_merged=True)]
    confirms = data_lock_repo.confirms_of_round(rnd["id"]) if rnd else {}
    locked = data_lock_repo.locked_map()
    return {
        "today": edit_window.today().isoformat(),
        "round": rnd,
        "units": [{"company": c,
                   "confirmed": c in confirms,
                   "confirmed_at": (confirms.get(c) or {}).get("locked_at"),
                   "by_admin": bool((confirms.get(c) or {}).get("by_admin")),
                   "locked_until": locked.get(c)} for c in units],
    }


@router.get("/summary")
def summary(company: str = Query(...), round_id: int | None = Query(None),
            username: str = Depends(get_current_user)) -> dict:
    """Bảng SỐ LIỆU SẼ CHỐT của một đơn vị — thứ đơn vị xem trước khi bấm xác nhận."""
    _assert_company(username, company)
    rnd = data_lock_repo.get_round(round_id) if round_id else data_lock_repo.current_round()
    if not rnd:
        raise HTTPException(404, "Chưa có đợt chốt số liệu nào.")
    prev = _prev_lock_date(rnd["id"], rnd["lock_date"])
    return {"round": rnd, **data_lock_summary.summary(company, rnd["lock_date"], prev)}


@router.post("/confirm")
def confirm(body: LockConfirmIn, username: str = Depends(get_current_user)) -> dict:
    """Đơn vị XÁC NHẬN chốt số liệu — sau bước này đơn vị hết tự sửa ngày ≤ ngày chốt."""
    _assert_company(username, body.company)
    rnd = data_lock_repo.get_round(body.round_id)
    if not rnd or rnd["cancelled_at"]:
        raise HTTPException(404, "Đợt chốt không còn hiệu lực.")
    prev = _prev_lock_date(rnd["id"], rnd["lock_date"])
    # Chụp lại CON SỐ tại lúc bấm — về sau còn đối chiếu với số hiện tại (chuyên viên sửa hộ là lệch).
    snap = data_lock_summary.summary(body.company, rnd["lock_date"], prev)
    data_lock_repo.confirm(rnd["id"], body.company, username, snapshot=snap)
    return {"ok": True, "locked_until": rnd["lock_date"]}


# ── Phía BAN TTKD / quản trị ──────────────────────────────────────────────────
@router.get("/rounds", dependencies=_ban)
def list_rounds(limit: int = Query(20, ge=1, le=100)) -> dict:
    return {"items": data_lock_repo.list_rounds(limit)}


@router.put("/rounds", dependencies=_admin)
def save_round(body: LockRoundIn, username: str = Depends(get_current_user)) -> dict:
    """Tạo (hoặc sửa) đợt chốt: 'chốt số liệu đến hết ngày X'."""
    try:
        d = date.fromisoformat(body.lock_date)
    except ValueError as exc:
        raise HTTPException(400, "Ngày chốt không hợp lệ (YYYY-MM-DD).") from exc
    if d > edit_window.today():
        raise HTTPException(400, "Không chốt số liệu cho ngày trong tương lai.")
    note = (body.note or "").strip()[:500] or None
    return {"round": data_lock_repo.save_round(d.isoformat(), note, username, body.id)}


@router.post("/rounds/{round_id}/cancel", dependencies=_admin)
def cancel_round(round_id: int, cancelled: bool = Query(True)) -> dict:
    """Huỷ đợt chốt (mở lại số liệu cho MỌI đơn vị của đợt) hoặc bỏ huỷ."""
    rnd = data_lock_repo.set_cancelled(round_id, cancelled)
    if not rnd:
        raise HTTPException(404, "Không tìm thấy đợt chốt.")
    return {"round": rnd}


@router.delete("/rounds/{round_id}", dependencies=_admin)
def delete_round(round_id: int) -> dict:
    if not data_lock_repo.delete_round(round_id):
        raise HTTPException(404, "Không tìm thấy đợt chốt.")
    return {"ok": True}


@router.get("/status", dependencies=_ban)
def status(round_id: int | None = Query(None),
           only_pending: bool = Query(False, description="Chỉ đơn vị CHƯA xác nhận"),
           q: str | None = Query(None, description="Tìm theo tên đơn vị")) -> dict:
    """Bảng theo dõi: đơn vị nào đã xác nhận chốt, đơn vị nào chưa (lọc được).

    Đơn vị đã sáp nhập vẫn đứng riêng (giống màn *Theo dõi nộp báo cáo*): "ai xác nhận" là chuyện
    của từng pháp nhân nhập liệu, gộp lại thì không biết phải đốc thúc ai.
    """
    rnd = data_lock_repo.get_round(round_id) if round_id else data_lock_repo.current_round()
    if not rnd:
        return {"round": None, "rows": [], "total": 0, "confirmed": 0}
    confirms = data_lock_repo.confirms_of_round(rnd["id"])
    locked = data_lock_repo.locked_map()
    merged = {u["name"]: u.get("merged_into") for u in member_unit_repo.list_units()
              if u.get("merged_into")}
    rows = []
    for u in report_units(split_merged=True):
        name = u["name"]
        c = confirms.get(name)
        rows.append({
            "company": name,
            "region": u.get("region"),
            "merged_into": merged.get(name),
            "confirmed": bool(c),
            "confirmed_at": (c or {}).get("locked_at"),
            "confirmed_by": (c or {}).get("locked_by"),
            "by_admin": bool((c or {}).get("by_admin")),
            "locked_until": locked.get(name),
            # Con số đơn vị đã xác nhận — để Ban đối chiếu ngay trên bảng, không phải mở từng đơn vị.
            "snapshot": (c or {}).get("snapshot"),
        })
    total, done = len(rows), sum(1 for r in rows if r["confirmed"])
    if only_pending:
        rows = [r for r in rows if not r["confirmed"]]
    if q:
        needle = q.strip().lower()
        rows = [r for r in rows if needle in r["company"].lower()]
    return {"round": rnd, "rows": rows, "total": total, "confirmed": done}


@router.post("/lock", dependencies=_admin)
def lock_units(body: LockUnitsIn, username: str = Depends(get_current_user)) -> dict:
    """Quản trị KHOÁ HỘ các đơn vị (đơn vị không bấm xác nhận nhưng Ban thấy số đã đủ)."""
    rnd = data_lock_repo.get_round(body.round_id)
    if not rnd or rnd["cancelled_at"]:
        raise HTTPException(404, "Đợt chốt không còn hiệu lực.")
    prev = _prev_lock_date(rnd["id"], rnd["lock_date"])
    # MỘT lượt tính cho cả danh sách: khoá hộ cả 70 đơn vị mà gọi `summary` từng cái là chạy lại
    # toàn bộ báo cáo kỳ 70 lần.
    snaps = data_lock_summary.summary_many(body.companies, rnd["lock_date"], prev)
    for company in body.companies:
        data_lock_repo.confirm(rnd["id"], company, username, by_admin=True,
                               snapshot=snaps.get(company))
    return {"ok": True, "count": len(body.companies)}


@router.post("/unlock", dependencies=_admin)
def unlock_units(body: LockUnitsIn) -> dict:
    """Quản trị MỞ KHOÁ cho các đơn vị (chốt nhầm / cần nhập bù) — đơn vị xác nhận lại sau."""
    n = sum(1 for company in body.companies if data_lock_repo.unlock(body.round_id, company))
    return {"ok": True, "count": n}
