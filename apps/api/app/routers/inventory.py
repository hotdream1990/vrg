"""Router Tồn kho Tập đoàn (fact_inventory) — báo cáo tuần chị Hạnh.

Đọc chuỗi tuần + nhập/sửa/xoá thủ công (ghi cần quyền editor/admin).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.security import require_cap
from app.services import inventory_repo

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

_editor = [Depends(require_cap("inventory"))]


class InventoryIn(BaseModel):
    as_of: str = Field(..., description="ngày tuần (YYYY-MM-DD)")
    ton_kho: float | None = Field(None, description="tồn kho thành phẩm (tấn)")
    ton_kho_hd: float | None = Field(None, description="tồn kho đã có hợp đồng (tấn)")
    note: str | None = None


@router.get("")
def list_weeks(limit: int | None = None) -> list[dict]:
    """Danh sách tuần tồn kho (mới nhất trước)."""
    return inventory_repo.series(limit)


@router.post("")
def upsert_week(body: InventoryIn, _: object = Depends(require_cap("inventory"))) -> dict:
    """Thêm/sửa 1 tuần (khóa = as_of)."""
    if not body.as_of.strip():
        raise HTTPException(400, "Thiếu ngày tuần")
    return inventory_repo.upsert(body.as_of, body.ton_kho, body.ton_kho_hd, body.note)


@router.delete("/{as_of}", dependencies=_editor)
def delete_week(as_of: str) -> dict:
    """Xoá 1 tuần."""
    if not inventory_repo.delete(as_of):
        raise HTTPException(404, f"Không có tuần '{as_of}'")
    return {"deleted": as_of}
