"""Router CÔNG KHAI (không cần đăng nhập) — đơn vị thành viên tự nhập giá mủ nước HÔM NAY.

Gác bằng 1 mật khẩu chung (đặt ở Cấu hình → Link công khai). Đổi mật khẩu lấy token
scope='public-purchase' (KHÔNG dùng được cho endpoint nội bộ). Chỉ ghi cho NGÀY HÔM NAY (giờ VN).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException

from app.core import request_ctx
from app.core.market_meta import PURCHASE_PRICE_UNIT, PURCHASE_SOURCE_UNIT
from app.core.security import create_public_token, require_public
from app.schemas.public_purchase import PublicAuthReq, PublicRecentReq, PublicSubmitReq
from app.services import config_repo, member_unit_repo, price_repo

router = APIRouter(prefix="/api/public/purchase", tags=["public-purchase"])
_public = [Depends(require_public)]
_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _today() -> str:
    return datetime.now(_TZ).date().isoformat()


@router.post("/auth")
def auth(body: PublicAuthReq) -> dict:
    """Đổi mật khẩu chung lấy token + danh sách đơn vị + ngày hôm nay (để dựng form)."""
    pw = config_repo.get_value("PUBLIC_PURCHASE_PASSWORD") or ""
    if not pw:
        raise HTTPException(503, "Link nhập giá chưa được cấu hình mật khẩu — liên hệ quản trị.")
    if body.password != pw:
        raise HTTPException(401, "Mật khẩu không đúng.")
    return {"token": create_public_token(), "units": member_unit_repo.active_names(), "today": _today()}


@router.post("", dependencies=_public)
def submit(body: PublicSubmitReq) -> dict:
    """Nhập giá mủ nước cho đơn vị — LUÔN ghi cho ngày hôm nay (server ép, không cho chọn ngày)."""
    if body.company not in set(member_unit_repo.active_names()):
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    if not (body.price and body.price > 0):
        raise HTTPException(400, "Giá không hợp lệ.")
    today = _today()
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
