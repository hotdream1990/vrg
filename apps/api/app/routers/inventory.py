"""Router Tồn kho Tập đoàn (fact_inventory) — báo cáo tuần chị Hạnh.

Đọc chuỗi tuần + nhập/sửa/xoá thủ công (ghi cần quyền editor/admin).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import assert_editor_window, require_cap, require_cap_edit
from app.services import inventory_auto, inventory_repo, unit_series, unit_series_stock

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


class InventoryIn(BaseModel):
    as_of: str = Field(..., description="ngày tuần (YYYY-MM-DD)")
    ton_kho: float | None = Field(None, description="tồn kho thành phẩm (tấn)")
    ton_kho_hd: float | None = Field(None, description="tồn kho đã có hợp đồng (tấn)")
    note: str | None = None


class InventoryAutoEdit(BaseModel):
    enabled: bool = Field(..., description="bật/tắt tự tính từ số liệu đơn vị thành viên")


@router.get("")
def list_weeks(limit: int | None = None) -> list[dict]:
    """Danh sách tuần tồn kho (mới nhất trước)."""
    return inventory_repo.series(limit)


@router.get("/series")
def stock_series(
    date_from: str | None = Query(None, description="từ ngày (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="đến ngày (YYYY-MM-DD)"),
    group_by: str = Query("structure", pattern="^(structure|grade|region)$"),
) -> dict:
    """Chuỗi tồn kho THEO NGÀY cộng từ biểu Tồn kho của đơn vị thành viên.

    Khác `GET ""` (chuỗi TUẦN của Tập đoàn, số chuyên viên chốt): ở đây là diễn biến hằng ngày,
    xem được theo cơ cấu hợp đồng · chủng loại · khu vực. Chuỗi bắt đầu từ `unit_series_stock.STOCK_START`
    — trước mốc đó chưa đủ đơn vị nhập để cộng thành số của Tập đoàn.
    """
    a, b = unit_series.window(date_from, date_to, start_floor=unit_series_stock.STOCK_START)
    return unit_series_stock.stock_series(a, b, group_by)


@router.post("")
def upsert_week(body: InventoryIn, username: str = Depends(require_cap_edit("inventory"))) -> dict:
    """Thêm/sửa 1 tuần (khóa = as_of) — trong cửa sổ sửa; admin miễn."""
    if not body.as_of.strip():
        raise HTTPException(400, "Thiếu ngày tuần")
    assert_editor_window(username, body.as_of)
    return inventory_repo.upsert(body.as_of, body.ton_kho, body.ton_kho_hd, body.note)


@router.delete("/{as_of}")
def delete_week(as_of: str, username: str = Depends(require_cap_edit("inventory"))) -> dict:
    """Xoá 1 tuần (trong cửa sổ sửa; admin miễn)."""
    assert_editor_window(username, as_of)
    if not inventory_repo.delete(as_of):
        raise HTTPException(404, f"Không có tuần '{as_of}'")
    return {"deleted": as_of}


# ── Tự tính từ số liệu đơn vị thành viên ──────────────────────────────────────
# Công tắc + các nút này thuộc quyền `inventory` của CHUYÊN VIÊN (không phải admin): quyết định
# số nào vào chuỗi tuần là việc của người phụ trách số liệu tồn kho.
@router.get("/auto", dependencies=[Depends(require_cap("inventory"))])
def get_auto() -> dict:
    """Trạng thái tự tính: công tắc + chu kỳ chốt + tuần chốt gần nhất."""
    return inventory_auto.config()


@router.put("/auto")
def put_auto(body: InventoryAutoEdit,
             username: str = Depends(require_cap_edit("inventory"))) -> dict:
    """Bật/tắt tự tính. Bật chỉ ăn từ lần đơn vị nộp SAU đó → dùng /auto/recompute để lấy số đã có."""
    return inventory_auto.save_config(body.enabled, by=username)


@router.get("/auto/preview", dependencies=[Depends(require_cap("inventory"))])
def preview_auto(as_of: str = Query(..., description="ngày chốt tuần (YYYY-MM-DD)")) -> dict:
    """Xem trước số tự tính của 1 tuần (kèm độ phủ) — KHÔNG ghi gì, để chuyên viên đối chiếu."""
    return inventory_auto.compute(as_of)


@router.post("/auto/apply")
def apply_auto(as_of: str = Query(..., description="ngày chốt tuần (YYYY-MM-DD)"),
               username: str = Depends(require_cap_edit("inventory"))) -> dict:
    """Đồng bộ NGAY 1 tuần theo số đơn vị — dùng được cả khi công tắc đang TẮT.

    Đây là thao tác cố ý của chuyên viên nên ĐƯỢC ghi đè số nhập tay (khác đường tự động, vốn
    luôn giữ nguyên tuần đã gõ tay). Không chặn theo cửa sổ sửa: số ở đây do máy cộng từ chuỗi
    ngày của đơn vị chứ không phải người gõ, và luôn nhập tay lại được.
    """
    res = inventory_auto.apply_week(as_of, force=True, by=username)
    if not res["written"]:
        raise HTTPException(400, f"Chưa đơn vị nào có số tồn kho cho tuần {as_of}")
    return res


@router.post("/auto/recompute")
def recompute_auto(weeks: int = Query(inventory_auto.DEFAULT_RECOMPUTE_WEEKS, ge=1,
                                      le=inventory_auto.MAX_RECOMPUTE_WEEKS),
                   username: str = Depends(require_cap_edit("inventory"))) -> dict:
    """Lấy số đã có: tính lại N tuần gần nhất, GIỮ NGUYÊN các tuần chuyên viên đã nhập tay."""
    return inventory_auto.recompute(weeks, by=username)
