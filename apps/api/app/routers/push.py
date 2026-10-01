"""Web Push — trình duyệt đăng ký / huỷ nhận thông báo cho tài khoản đang đăng nhập.

Mọi tài khoản đã đăng nhập đều dùng được (ai nhận tin gì là việc của nơi phát thông báo). Riêng
phiên ĐĂNG NHẬP HỘ thì không cho đăng ký: trình duyệt đó là của quản trị viên, đăng ký sẽ khiến máy
quản trị nhận thông báo của đơn vị.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.security import get_current_user, get_impersonator
from app.services import web_push

router = APIRouter(prefix="/api/push", tags=["push"])


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=80, max_length=100)  # điểm P-256 65 byte ≈ 87 ký tự base64url
    auth: str = Field(min_length=16, max_length=32)     # 16 byte ≈ 22 ký tự


class SubscribeIn(BaseModel):
    endpoint: str = Field(min_length=20, max_length=1000)
    keys: PushKeys


class UnsubscribeIn(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)


@router.get("/key")
def vapid_key(_: str = Depends(get_current_user)) -> dict:
    """Khoá công khai VAPID — trình duyệt cần khi gọi `pushManager.subscribe`."""
    return {"public_key": web_push.public_key()}


@router.post("/subscribe")
def subscribe(body: SubscribeIn, request: Request,
              username: str = Depends(get_current_user),
              impersonator: str | None = Depends(get_impersonator)) -> dict:
    if impersonator:
        raise HTTPException(403, "Đang đăng nhập hộ — không đăng ký nhận thông báo trên máy này.")
    try:
        web_push.validate_subscription(body.endpoint, body.keys.p256dh, body.keys.auth)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    user_agent = (request.headers.get("user-agent") or "")[:300] or None
    web_push.save_subscription(username, body.endpoint, body.keys.p256dh, body.keys.auth, user_agent)
    return {"ok": True}


@router.post("/unsubscribe")
def unsubscribe(body: UnsubscribeIn, username: str = Depends(get_current_user)) -> dict:
    """Chỉ gỡ đăng ký của CHÍNH tài khoản đang gọi (không gỡ được của người khác)."""
    return {"ok": True, "removed": web_push.delete_subscription(body.endpoint, username)}
