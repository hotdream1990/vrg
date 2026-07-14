"""Router Giá sàn Tập đoàn — biểu giá theo lần (nhập tay, không hàng ngày)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.market_meta import VRG_FLOOR_GRADES
from app.core.security import require_editor
from app.schemas.floor import (
    FloorSaveRequest,
    FloorSchedule,
    FloorScheduleSummary,
)
from app.services import floor_repo

router = APIRouter(prefix="/api/floor", tags=["floor"])

_editor = [Depends(require_editor)]  # ghi: cần admin/editor (viewer chỉ xem)


@router.get("", response_model=list[FloorScheduleSummary])
def list_schedules(
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
):
    """Danh sách biểu giá (mỗi lần 1 dòng), mới nhất trước — lọc theo ngày áp dụng."""
    rows = floor_repo.list_schedules(date_from, date_to)
    return [
        FloorScheduleSummary(
            lan=int(r["lan"]), as_of=str(r["as_of"]), title=r["title"],
            dispatch_no=r.get("dispatch_no", ""), grades=int(r["grades"]),
            filled=int(r["filled"]), updated=str(r["updated"]) if r.get("updated") else None,
        )
        for r in rows
    ]


@router.get("/next-lan")
def next_lan() -> dict:
    """Số lần kế tiếp + danh sách chủng loại mặc định (để dựng form tạo mới)."""
    return {"next_lan": floor_repo.next_lan(), "grades": VRG_FLOOR_GRADES}


@router.get("/{lan}", response_model=FloorSchedule)
def get_schedule(lan: int):
    """1 biểu giá đầy đủ theo lần."""
    sch = floor_repo.get_schedule(lan)
    if not sch:
        raise HTTPException(404, f"Không có biểu giá lần {lan}")
    return sch


@router.post("", response_model=FloorSchedule, dependencies=_editor)
def create_schedule(req: FloorSaveRequest):
    """Tạo biểu giá mới — số lần tự nhảy = max(lan)+1; tiêu đề custom (mặc định "Lần {lan}")."""
    lan = floor_repo.next_lan()
    items = [it.model_dump() for it in req.items]
    floor_repo.save_schedule(lan, req.as_of, items, req.title, req.dispatch_no, req.dispatch_summary)
    return floor_repo.get_schedule(lan)


@router.put("/{lan}", response_model=FloorSchedule, dependencies=_editor)
def update_schedule(lan: int, req: FloorSaveRequest):
    """Sửa biểu giá lần đã có (ghi đè giá + ngày áp dụng + tiêu đề)."""
    floor_repo.save_schedule(
        lan, req.as_of, [it.model_dump() for it in req.items],
        req.title, req.dispatch_no, req.dispatch_summary,
    )
    sch = floor_repo.get_schedule(lan)
    if not sch:
        raise HTTPException(404, f"Không có biểu giá lần {lan}")
    return sch


@router.delete("/{lan}", dependencies=_editor)
def delete_schedule(lan: int) -> dict:
    """Xoá 1 biểu giá theo lần."""
    if not floor_repo.delete_schedule(lan):
        raise HTTPException(404, f"Không có biểu giá lần {lan}")
    return {"deleted": lan}
