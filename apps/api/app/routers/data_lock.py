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
from app.core.security import (
    get_current_user, get_impersonator, require_admin, require_cap, user_caps,
)
from app.core.permissions import LEVEL_VIEW, has_cap
from app.schemas.data_lock import LockConfirmIn, LockRoundIn, LockUnitsIn
from app.services import data_lock_repo, data_lock_summary, user_repo
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


def _with_merged(companies: list[str]) -> list[str]:
    """Danh sách đơn vị + các đơn vị đã sáp nhập vào chúng (không trùng, giữ thứ tự).

    Chốt đơn vị nhận = chốt kèm đơn vị đã sáp nhập vào nó, ở MỌI đường: đơn vị tự xác nhận, Ban
    khoá hộ, Ban mở khoá. Hợp đồng ký trước sáp nhập đứng tên đơn vị cũ nhưng do đơn vị nhận giao
    nốt, còn tài khoản đơn vị chỉ gán đơn vị nhận — không kéo theo thì dòng đơn vị cũ không ai chốt.
    """
    mm = data_lock_summary.merged_map()
    return list(dict.fromkeys(u for c in companies for u in [c, *mm.get(c, [])]))


def _fully_confirmed(company: str, done: set[str] | dict, mm: dict[str, list[str]]) -> bool:
    """Đơn vị đã chốt XONG trong đợt = chính nó + mọi đơn vị đã sáp nhập vào nó đều đã có xác nhận.

    Một luật cho cả banner đơn vị, bảng theo dõi và số "đã chốt" ở ô chọn đợt — ba chỗ tự đếm
    riêng là ba con số lệch nhau (đo 29/09/2026: ô chọn đợt 54, bảng theo dõi 53/63).
    """
    return company in done and all(m in done for m in mm.get(company, []))


def _merged_cell(company: str, c: dict | None) -> dict:
    """Đơn vị đã sáp nhập trong dòng đơn vị nhận của bảng theo dõi: trạng thái + số CỘNG ĐƯỢC.

    Tồn kho không kèm: là số thời điểm, kho đơn vị cũ đã nằm trong số khai của đơn vị nhận.
    """
    snap = (c or {}).get("snapshot") or {}
    return {"company": company, "confirmed": c is not None,
            "total_purchase": (snap.get("purchase") or {}).get("total_purchase"),
            "total_consumption": (snap.get("consumption") or {}).get("total_consumption")}


def _assert_company(username: str, company: str) -> None:
    units = _my_units(username)
    if units is not None and company not in units:
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _assert_can_confirm(username: str, company: str) -> None:
    """XÁC NHẬN chốt là lời cam kết của chính đơn vị — chỉ tài khoản đơn vị, cho đơn vị được gán.

    Trước 29/09/2026 `/confirm` dùng chung `_assert_company` nên ai có cap `unit_daily` (kể cả mức
    CHỈ XEM) cũng chốt — tức KHOÁ — được số liệu của mọi đơn vị. Ban muốn khoá thay đơn vị thì
    dùng «Khoá hộ» (`/lock`, chỉ quản trị): bản ghi đó mang cờ `by_admin`, không giả làm đơn vị ký.
    """
    me = _me(username)
    if me.get("role") != "member":
        raise HTTPException(403, "Chỉ tài khoản đơn vị mới xác nhận chốt số liệu. "
                                 "Ban TTKD muốn khoá thay đơn vị thì dùng «Khoá hộ» ở màn Chốt số liệu.")
    if company not in (me.get("member_units") or []):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


def _prev_lock_date(company: str, lock_date: str) -> str | None:
    """Đầu kỳ của bảng số liệu sẽ chốt = lần chốt trước CỦA CHÍNH ĐƠN VỊ ĐÓ (chưa có thì 01/01).

    Theo đơn vị chứ không theo đợt: đợt chốt riêng của vài đơn vị (vd chốt trước sáp nhập) không
    được cắt đầu kỳ của đơn vị khác — xem `data_lock_repo.locked_before_map`.
    """
    return data_lock_repo.locked_before_map([company], lock_date).get(company)


# ── Phía ĐƠN VỊ ───────────────────────────────────────────────────────────────
@router.get("/current")
def current(username: str = Depends(get_current_user)) -> dict:
    """Đợt chốt đang hiệu lực + trạng thái từng đơn vị của tài khoản (nguồn của banner cảnh báo).

    Trả cả `locked_until` để màn nhập liệu biết ngày nào đã khoá mà chuyển sang "chỉ xem".
    """
    rnd = data_lock_repo.current_round()
    units = _my_units(username)
    if units is None:
        units = [u["name"] for u in report_units()]
    confirms = data_lock_repo.confirms_of_round(rnd["id"]) if rnd else {}
    locked = data_lock_repo.locked_map()
    mm = data_lock_summary.merged_map()
    return {
        "today": edit_window.today().isoformat(),
        "round": rnd,
        # "Đã chốt" chỉ khi chốt xong CẢ đơn vị đã sáp nhập vào nó. Không thế thì đơn vị chốt trước
        # khi có chốt kèm (hoặc Ban duyệt đề nghị sửa làm gỡ khoá riêng đơn vị cũ) sẽ không còn nút
        # nào để chốt phần đơn vị cũ — bấm lại chỉ chốt thêm phần còn thiếu, ảnh chụp cũ giữ nguyên.
        "units": [{"company": c,
                   "confirmed": _fully_confirmed(c, confirms, mm),
                   "confirmed_at": (confirms.get(c) or {}).get("locked_at"),
                   "by_admin": bool((confirms.get(c) or {}).get("by_admin")),
                   "locked_until": locked.get(c)} for c in units],
        # Mốc khoá của đơn vị đã sáp nhập vào các đơn vị trên — không có dòng/nút riêng ở banner,
        # nhưng HĐ đứng tên họ vẫn sửa qua Đề nghị sửa nên màn đó cần biết kỳ nào đã chốt.
        "merged_locked_until": {m: locked.get(m) for c in units for m in mm.get(c, [])},
    }


@router.get("/summary")
def summary(company: str = Query(...), round_id: int | None = Query(None),
            username: str = Depends(get_current_user)) -> dict:
    """Bảng SỐ LIỆU SẼ CHỐT của một đơn vị — thứ đơn vị xem trước khi bấm xác nhận."""
    _assert_company(username, company)
    rnd = data_lock_repo.get_round(round_id) if round_id else data_lock_repo.current_round()
    if not rnd:
        raise HTTPException(404, "Chưa có đợt chốt số liệu nào.")
    prev = _prev_lock_date(company, rnd["lock_date"])
    confirms = data_lock_repo.confirms_of_round(rnd["id"])
    # Đơn vị đã sáp nhập vào đơn vị này: bấm xác nhận là chốt kèm (xem `_with_merged`) nên phải bày
    # số của họ ra cùng — không thì đơn vị chốt thứ mình không nhìn thấy.
    merged = [{**m, "confirmed": m["company"] in confirms}
              for m in data_lock_summary.merged_summaries(company, rnd["lock_date"])]
    return {"round": rnd, **data_lock_summary.summary(company, rnd["lock_date"], prev),
            "merged_units": merged}


@router.post("/confirm")
def confirm(body: LockConfirmIn, username: str = Depends(get_current_user),
            imp_by: str | None = Depends(get_impersonator)) -> dict:
    """Đơn vị XÁC NHẬN chốt số liệu — sau bước này đơn vị hết tự sửa ngày ≤ ngày chốt.

    Quản trị ĐĂNG NHẬP HỘ đơn vị rồi bấm: vẫn cho (hỗ trợ qua điện thoại là chuyện thường) nhưng
    ghi đúng người thật + cờ `by_admin` — không để bản ghi trông như chính đơn vị tự xác nhận.
    """
    _assert_can_confirm(username, body.company)
    who, by_admin = (imp_by, True) if imp_by else (username, False)
    rnd = data_lock_repo.get_round(body.round_id)
    if not rnd or rnd["cancelled_at"]:
        raise HTTPException(404, "Đợt chốt không còn hiệu lực.")
    prev = _prev_lock_date(body.company, rnd["lock_date"])
    # Chụp lại CON SỐ tại lúc bấm — về sau còn đối chiếu với số hiện tại (chuyên viên sửa hộ là lệch).
    snap = data_lock_summary.summary(body.company, rnd["lock_date"], prev)
    data_lock_repo.confirm(rnd["id"], body.company, who, by_admin=by_admin, snapshot=snap)
    # Chốt KÈM đơn vị đã sáp nhập — mỗi đơn vị một ảnh chụp theo kỳ chốt riêng của nó.
    for m in data_lock_summary.merged_summaries(body.company, rnd["lock_date"]):
        data_lock_repo.confirm(rnd["id"], m["company"], who, by_admin=by_admin, snapshot=m)
    return {"ok": True, "locked_until": rnd["lock_date"]}


# ── Phía BAN TTKD / quản trị ──────────────────────────────────────────────────
@router.get("/rounds", dependencies=_ban)
def list_rounds(limit: int = Query(20, ge=1, le=100)) -> dict:
    items = data_lock_repo.list_rounds(limit)
    done = data_lock_repo.confirmed_companies([r["id"] for r in items])
    units, mm = [u["name"] for u in report_units()], data_lock_summary.merged_map()
    for r in items:
        # Đếm đúng như cột "Đã xác nhận x/y" của bảng theo dõi — xem `_fully_confirmed`.
        r["locked"] = sum(1 for u in units if _fully_confirmed(u, done[r["id"]], mm))
    return {"items": items}


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

    CHỈ đơn vị đang hoạt động (chốt 29/09/2026, như màn *Theo dõi nộp báo cáo* không đưa đơn vị đã
    sáp nhập vào mẫu số): đơn vị đã sáp nhập không còn ai quản lý để đốc thúc — họ được chốt KÈM
    đơn vị nhận (xem `_with_merged`) và hiện trong dòng của đơn vị nhận (`merged_units`). Để họ
    đứng dòng riêng là bày ra những ô "Chưa xác nhận" không ai bấm được, và làm lệch mẫu số.
    Dòng đơn vị nhận chỉ "đã chốt" khi chốt xong CẢ phần đơn vị cũ — cùng luật với banner `/current`.
    """
    rnd = data_lock_repo.get_round(round_id) if round_id else data_lock_repo.current_round()
    if not rnd:
        return {"round": None, "rows": [], "total": 0, "confirmed": 0}
    confirms = data_lock_repo.confirms_of_round(rnd["id"])
    locked = data_lock_repo.locked_map()
    mm = data_lock_summary.merged_map()
    rows = []
    for u in report_units():
        name = u["name"]
        c = confirms.get(name)
        merged = [_merged_cell(m, confirms.get(m)) for m in mm.get(name, [])]
        rows.append({
            "company": name,
            "region": u.get("region"),
            "merged_units": merged,
            "confirmed": _fully_confirmed(name, confirms, mm),
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
        # Gõ tên đơn vị CŨ vẫn ra dòng đơn vị nhận — Ban vẫn quen gọi theo tên cũ.
        needle = q.strip().lower()
        rows = [r for r in rows
                if any(needle in n.lower()
                       for n in [r["company"], *(m["company"] for m in r["merged_units"])])]
    return {"round": rnd, "rows": rows, "total": total, "confirmed": done}


@router.post("/lock", dependencies=_admin)
def lock_units(body: LockUnitsIn, username: str = Depends(get_current_user)) -> dict:
    """Quản trị KHOÁ HỘ các đơn vị (đơn vị không bấm xác nhận nhưng Ban thấy số đã đủ)."""
    rnd = data_lock_repo.get_round(body.round_id)
    if not rnd or rnd["cancelled_at"]:
        raise HTTPException(404, "Đợt chốt không còn hiệu lực.")
    targets = _with_merged(body.companies)
    # MỘT lượt tính cho mỗi ĐẦU KỲ: khoá hộ cả 70 đơn vị mà gọi `summary` từng cái là chạy lại
    # toàn bộ báo cáo kỳ 70 lần. Đầu kỳ theo từng đơn vị nên gom các đơn vị cùng đầu kỳ lại.
    prevs = data_lock_repo.locked_before_map(targets, rnd["lock_date"])
    groups: dict[str | None, list[str]] = {}
    for company in targets:
        groups.setdefault(prevs.get(company), []).append(company)
    snaps: dict[str, dict] = {}
    for prev, companies in groups.items():
        snaps.update(data_lock_summary.summary_many(companies, rnd["lock_date"], prev))
    for company in targets:
        data_lock_repo.confirm(rnd["id"], company, username, by_admin=True,
                               snapshot=snaps.get(company))
    return {"ok": True, "count": len(targets)}


@router.post("/unlock", dependencies=_admin)
def unlock_units(body: LockUnitsIn) -> dict:
    """Quản trị MỞ KHOÁ cho các đơn vị (chốt nhầm / cần nhập bù) — đơn vị xác nhận lại sau.

    Mở khoá đơn vị nhận là mở luôn đơn vị đã sáp nhập vào nó (cặp chốt kèm, xem `_with_merged`):
    nếu không, đơn vị không sửa được hợp đồng của đơn vị cũ, và lần xác nhận lại giữ nguyên ảnh
    chụp CŨ của đơn vị cũ vì dòng đó đã có sẵn.
    """
    n = sum(1 for company in _with_merged(body.companies)
            if data_lock_repo.unlock(body.round_id, company))
    return {"ok": True, "count": n}
