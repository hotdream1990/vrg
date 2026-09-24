"""Router CÔNG KHAI (không cần đăng nhập) — đơn vị thành viên tự nhập giá mủ nước HÔM NAY.

Gác bằng 1 mật khẩu chung (đặt ở Cấu hình → Link công khai). Đổi mật khẩu lấy token
scope='public-purchase' (KHÔNG dùng được cho endpoint nội bộ). Chỉ ghi cho NGÀY HÔM NAY (giờ VN).

Cùng hàng rào với tài khoản đơn vị (`PUT /api/member/prices`): cửa sổ nhập liệu của đơn vị (giờ
chốt — N = 0 thì qua 11:00 hôm nay cũng khoá) + mốc chốt số liệu của đơn vị. Không có thì link
này thành đường lách luật giờ chốt.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core import data_lock, edit_window, request_ctx
from app.core.unit_guard import assert_unit_can_enter
from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_UNIT
from app.core.security import create_public_token, require_public
from app.schemas.public_purchase import PublicAuthReq, PublicRecentReq, PublicSubmitReq
from app.services import config_repo, member_unit_repo, price_repo

router = APIRouter(prefix="/api/public/purchase", tags=["public-purchase"])
_public = [Depends(require_public)]


def _today() -> str:
    return edit_window.today().isoformat()


@router.post("/auth")
def auth(body: PublicAuthReq) -> dict:
    """Đổi mật khẩu chung lấy token + danh sách đơn vị + ngày hôm nay (để dựng form).

    `closed` = câu báo khi hôm nay đã quá hạn nhập (N = 0 và đã qua giờ chốt) để trang báo TRƯỚC,
    khỏi để đơn vị gõ giá xong mới bị từ chối; None = còn nhập được.
    """
    pw = config_repo.get_value("PUBLIC_PURCHASE_PASSWORD") or ""
    if not pw:
        raise HTTPException(503, "Link nhập giá chưa được cấu hình mật khẩu — liên hệ quản trị.")
    if body.password != pw:
        raise HTTPException(401, "Mật khẩu không đúng.")
    today, window = edit_window.today(), edit_window.member_window()
    closed = None if edit_window.is_editable(today, window) else edit_window.blocked_message(window)
    return {"token": create_public_token(), "units": member_unit_repo.active_names(),
            "today": today.isoformat(), "closed": closed}


@router.post("", dependencies=_public)
def submit(body: PublicSubmitReq) -> dict:
    """Nhập giá mủ nước cho đơn vị — LUÔN ghi cho ngày hôm nay (server ép, không cho chọn ngày)."""
    today = _today()
    assert_unit_can_enter(body.company, today)
    if not (body.price and body.price > 0):
        raise HTTPException(400, "Giá không hợp lệ.")
    edit_window.assert_editable(today, edit_window.member_window())
    data_lock.assert_not_locked(body.company, today)
    # Trang công khai KHÔNG có tài khoản riêng (mật khẩu dùng chung) → nhật ký ghi
    # 'public:<đơn vị>' kèm IP: truy được đơn vị nào gửi, KHÔNG khẳng định được nhân viên nào.
    with request_ctx.use_actor(f"{request_ctx.PUBLIC_PREFIX}{body.company}"):
        price_repo.upsert_record({"as_of": today, "source": PURCHASE_SOURCE_UNIT, "grade": body.company,
                                  "contract": "", "price_type": "purchase", "price": float(body.price),
                                  "currency": "VND", "unit": PURCHASE_PRICE_UNIT["purchase"]},
                                 note="Nhập từ link công khai")
    return {"ok": True, "as_of": today}


@router.post("/recent", dependencies=_public)
def recent(body: PublicRecentReq) -> dict:
    """Vài giá gần nhất của CHÍNH đơn vị đó (để đối chiếu; không thấy đơn vị khác)."""
    return {"records": price_repo.purchase_recent_for(body.company, 10, PURCHASE_SOURCE_UNIT)}
