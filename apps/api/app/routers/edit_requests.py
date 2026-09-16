"""Router «Đề nghị sửa số liệu quá khứ» — phía BAN (`/api/edit-requests`).

Chỉ tài khoản có quyền `edit_request` (quản trị luôn có): xem danh sách, so trước/sau, DUYỆT (hệ thống
ghi thật + gỡ chốt của đơn vị từ ngày bị sửa) hoặc TỪ CHỐI (bắt buộc ghi chú). Luật ở
`services/edit_request_apply.py`.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_cap
from app.schemas.edit_request import ReviewIn
from app.services import contract_files, edit_request_apply, edit_request_repo
from app.services.edit_request_ops import get_op

router = APIRouter(prefix="/api/edit-requests", tags=["edit-requests"])

Reviewer = Annotated[str, Depends(require_cap("edit_request"))]
_STATUS = "^(pending|approved|rejected|cancelled|all)$"


@router.get("")
def list_requests(_: Reviewer, status: str = Query("pending", pattern=_STATUS),
                  company: str | None = Query(None, max_length=200),
                  op: str | None = Query(None, max_length=40),
                  q: str | None = Query(None, max_length=120),
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)) -> dict:
    if op:
        get_op(op)  # 400 nếu sai loại
    return edit_request_repo.list_requests(status=None if status == "all" else status,
                                           company=company, op=op, q=(q or "").strip() or None,
                                           page=page, page_size=page_size)


@router.get("/pending-count")
def pending_count(_: Reviewer) -> dict:
    return {"count": edit_request_repo.pending_count()}


@router.get("/{req_id}")
def get_request(req_id: int, _: Reviewer) -> dict:
    return edit_request_apply.detail(req_id)


@router.post("/{req_id}/approve")
def approve(req_id: int, username: Reviewer, body: ReviewIn | None = None) -> dict:
    b = body or ReviewIn()
    return {"request": edit_request_apply.approve(req_id, username, b.note, b.expected_updated_at,
                                                  b.accept_changed)}


@router.post("/{req_id}/reject")
def reject(req_id: int, body: ReviewIn, username: Reviewer) -> dict:
    return {"request": edit_request_apply.reject(req_id, username, body.note,
                                                 body.expected_updated_at)}


def _file_names(value: Any) -> set[str]:
    """Mọi tên file đính kèm (`{"file": ...}`) nằm trong payload / ảnh chụp của đề nghị."""
    if isinstance(value, dict):
        own = {value["file"]} if isinstance(value.get("file"), str) else set()
        return own.union(*(_file_names(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_file_names(v) for v in value))
    return set()


@router.get("/{req_id}/file/{name}")
def get_file(req_id: int, name: str, _: Reviewer, filename: str | None = Query(None)):
    """Tải file hợp đồng/chứng từ — CHỈ file có mặt trong chính đề nghị này (không mở kho file chung)."""
    req = edit_request_repo.get(req_id)
    if not req or name not in _file_names(req["payload"]) | _file_names(req["before"]):
        raise HTTPException(404, "Không tìm thấy file trong đề nghị này.")
    return contract_files.serve(name, filename)
