"""Router danh mục nguồn tham khảo Báo cáo tuần — xem (quyền `bulletin_weekly`, gác ở main) · sửa (mức Sửa)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import require_cap_edit
from app.schemas.weekly_source import WeeklySource, WeeklySourceIn, WeeklySourceMeta, WeeklySourceUpdate
from app.services import weekly_source_defaults, weekly_source_repo

router = APIRouter(prefix="/api/weekly-sources", tags=["weekly-sources"])
_edit = require_cap_edit("bulletin_weekly")


@router.get("", response_model=list[WeeklySource])
def list_sources():
    """Toàn bộ danh mục (kể cả nguồn đang tắt), theo thứ tự hiển thị."""
    return weekly_source_repo.list_sources()


@router.get("/meta", response_model=WeeklySourceMeta)
def meta():
    """Nhãn tiếng Việt cho nhóm nguồn · cách dùng · mục báo cáo."""
    return weekly_source_defaults.meta()


@router.post("", response_model=WeeklySource)
def create_source(body: WeeklySourceIn, username: str = Depends(_edit)):
    try:
        return weekly_source_repo.create_source(body.model_dump(), username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{source_id}", response_model=WeeklySource)
def update_source(source_id: int, body: WeeklySourceUpdate, username: str = Depends(_edit)):
    try:
        updated = weekly_source_repo.update_source(source_id, body.model_dump(exclude_unset=True), username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not updated:
        raise HTTPException(404, "Không tìm thấy nguồn tham khảo.")
    return updated


@router.delete("/{source_id}", dependencies=[Depends(_edit)])
def delete_source(source_id: int) -> dict:
    if not weekly_source_repo.delete_source(source_id):
        raise HTTPException(404, "Không tìm thấy nguồn tham khảo.")
    return {"deleted": source_id}


@router.post("/reset-defaults", response_model=list[WeeklySource])
def reset_defaults(username: str = Depends(_edit)):
    """Xoá danh mục hiện tại và nạp lại bộ nguồn mặc định (theo logic viết bản tin tuần)."""
    return weekly_source_repo.reset_defaults(username)
