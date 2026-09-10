"""Router Lịch sử hỏi–đáp Trợ lý AI — xem lại hội thoại cũ + dọn log cho DB không phình.

Phân quyền:
  - Cap `assistant` (mức Xem là đủ) → xem log CỦA CHÍNH MÌNH. Server tự ép `username` theo
    tài khoản đăng nhập, KHÔNG tin tham số `username` client gửi lên.
  - **admin** → xem log MỌI người + dùng được bộ lọc `username`.
  - **Chỉ admin** được xoá (xoá 1 phiên hoặc xoá log cũ hơn 1 ngày).

Lưu ý thứ tự route: `/stats` (tĩnh) phải khai báo TRƯỚC `/{session_id}` (động), nếu không
FastAPI sẽ khớp "stats" vào tham số `session_id`.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_admin, require_cap
from app.services import assistant_log_repo, user_repo

router = APIRouter(prefix="/api/assistant/history", tags=["assistant-history"])
_require = require_cap("assistant")


def _is_admin(username: str) -> bool:
    u = user_repo.get_user(username) or {}
    return u.get("role") == "admin"


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(400, f"{label} không hợp lệ (YYYY-MM-DD).") from exc


@router.get("")
def list_sessions(
    caller: str = Depends(_require),
    username: str | None = Query(None, description="Lọc theo người dùng (chỉ admin)"),
    date_from: str | None = Query(None, description="Từ ngày 'YYYY-MM-DD'"),
    date_to: str | None = Query(None, description="Đến ngày 'YYYY-MM-DD'"),
    q: str | None = Query(None, max_length=200, description="Tìm trong câu hỏi"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """Danh sách PHIÊN (gộp theo session_id), mới nhất trước, phân trang ở server."""
    admin = _is_admin(caller)
    if not admin:
        if username and username != caller:
            raise HTTPException(403, "Bạn chỉ xem được lịch sử hỏi–đáp của chính mình")
        username = caller
    _check_date("Từ ngày", date_from)
    _check_date("Đến ngày", date_to)
    res = assistant_log_repo.list_sessions(username=username, date_from=date_from,
                                           date_to=date_to, q=q, limit=limit, offset=offset)
    return {**res, "limit": limit, "offset": offset}


@router.get("/stats")
def stats(caller: str = Depends(_require)) -> dict:
    """Tổng số lượt · số phiên · dòng cũ nhất — cho UI hiện 'đang lưu N lượt từ ngày …'.

    Là số liệu TOÀN HỆ THỐNG nên chỉ admin xem được; tài khoản thường không cần biết tổng
    dung lượng log của người khác.
    """
    if not _is_admin(caller):
        raise HTTPException(403, "Chỉ quản trị viên xem được thống kê này")
    return assistant_log_repo.stats()


@router.get("/{session_id}")
def get_session(session_id: str, caller: str = Depends(_require)) -> dict:
    """Toàn bộ lượt của 1 phiên, cũ→mới."""
    owner = assistant_log_repo.session_owner(session_id)
    if owner is None:
        raise HTTPException(404, "Không tìm thấy phiên hội thoại")
    if not _is_admin(caller) and owner != caller:
        raise HTTPException(403, "Bạn không có quyền xem phiên hội thoại này")
    return {"session_id": session_id, "items": assistant_log_repo.get_session(session_id)}


@router.delete("")
def delete_before(
    before: str = Query(..., description="Xoá log CŨ HƠN ngày này (YYYY-MM-DD)"),
    username: str = Depends(require_admin),
) -> dict:
    """Dọn log cũ cho DB không phình — chỉ admin."""
    _check_date("before", before)
    return {"deleted": assistant_log_repo.delete_before(before)}


@router.delete("/{session_id}")
def delete_session(session_id: str, username: str = Depends(require_admin)) -> dict:
    """Xoá 1 phiên — chỉ admin."""
    deleted = assistant_log_repo.delete_session(session_id)
    if not deleted:
        raise HTTPException(404, "Không tìm thấy phiên hội thoại")
    return {"deleted": deleted}
