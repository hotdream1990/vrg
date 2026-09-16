"""Router «Đề nghị sửa số liệu quá khứ» — phía ĐƠN VỊ THÀNH VIÊN (`/api/member/edit-requests`).

Bản ghi đơn vị không tự sửa được nữa vì cửa sổ sửa / chốt số liệu → gửi nội dung muốn sửa kèm lý do.
Số liệu thật CHƯA đổi cho tới khi Ban duyệt (xem `routers/edit_requests.py`).

Quyền: `get_unit_user` — tài khoản nhập liệu gửi/huỷ; lãnh đạo đơn vị chỉ XEM (method ghi bị chặn ở
dependency). Mọi truy vấn ép về đơn vị của tài khoản (kèm đơn vị đã sáp nhập vào — hợp đồng dở dang
của đơn vị cũ cũng được gửi đề nghị, đúng phạm vi của màn hợp đồng).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_unit_user
from app.schemas.edit_request import EditRequestIn
from app.services import audit_repo, edit_request_notify, edit_request_ops, edit_request_repo, member_unit_merge

router = APIRouter(prefix="/api/member/edit-requests", tags=["member-edit-requests"])

_STATUS = "^(pending|approved|rejected|cancelled|all)$"


def _units(member: dict) -> list[str]:
    own = list(member.get("member_units") or [])
    return member_unit_merge.expand(own) or own


def _mine(member: dict, req_id: int) -> dict:
    req = edit_request_repo.get(req_id)
    if not req or req["company"] not in _units(member):
        raise HTTPException(404, "Không tìm thấy đề nghị sửa số liệu.")
    return req


@router.post("")
def submit(body: EditRequestIn, member: dict = Depends(get_unit_user)) -> dict:
    """Gửi đề nghị. Đã có đề nghị đang chờ cho cùng bản ghi ⇒ ghi đè đề nghị đó (`replaced`)."""
    edit_request_ops.get_op(body.op)
    reason = edit_request_ops.clean_reason(body.reason)
    prep = edit_request_ops.prepare(body.op, body.payload, member)
    if not prep["blocked"]:
        raise HTTPException(409, "Bản ghi này vẫn sửa trực tiếp được — không cần gửi đề nghị.")
    req, replaced = edit_request_repo.save_pending({**prep, "reason": reason}, member["username"])
    audit_repo.log("edit_request", "update" if replaced else "create", f"#{req['id']}",
                   after={"op": req["op"], "title": req["title"], "reason": reason,
                          "payload": req["payload"]},
                   as_of=min(req["dates"]) if req["dates"] else None, company=req["company"])
    edit_request_notify.notify_submitted(req, replaced)
    return {"request": req, "replaced": replaced}


@router.get("")
def my_requests(status: str = Query("all", pattern=_STATUS),
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                member: dict = Depends(get_unit_user)) -> dict:
    return edit_request_repo.list_requests(status=None if status == "all" else status,
                                           companies=_units(member), page=page, page_size=page_size)


@router.get("/{req_id}")
def my_request(req_id: int, member: dict = Depends(get_unit_user)) -> dict:
    return {"request": _mine(member, req_id)}


@router.post("/{req_id}/cancel")
def cancel_request(req_id: int, member: dict = Depends(get_unit_user)) -> dict:
    req = _mine(member, req_id)
    if not edit_request_repo.cancel(req_id):
        raise HTTPException(409, "Đề nghị này không còn chờ duyệt — không huỷ được.")
    audit_repo.log("edit_request", "cancel", f"#{req_id}", company=req["company"],
                   after={"status": "cancelled"})
    return {"request": edit_request_repo.get(req_id)}
