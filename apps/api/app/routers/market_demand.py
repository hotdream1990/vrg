"""Router Nhu cầu thị trường cho CHUYÊN VIÊN có quyền `market_demand` — xem/sửa phiếu MỌI đơn vị.

Đơn vị thành viên tự nhập của mình qua `/api/member/market-demand/items` (router member_self).
Mỗi phiếu = một nhu cầu của một chủng loại, có tình trạng cập nhật về sau (chốt 17/09/2026).
Hàng rào thời gian dùng chung với phía đơn vị (`market_demand_item_policy`): chuyên viên theo
cửa sổ chuyên viên, admin miễn; chỉ đổi ô theo dõi thì miễn cửa sổ.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import edit_window
from app.core.market_demand_meta import GRADES
from app.core.security import require_cap, require_cap_edit
from app.core.unit_guard import assert_unit_can_enter
from app.schemas.market_demand_item import DemandItemIn
from app.services import market_demand_item_policy as policy
from app.services import market_demand_item_repo, member_unit_repo

router = APIRouter(prefix="/api/market-demand", tags=["market-demand"])
_require_md = require_cap("market_demand")            # đọc: mức Xem là đủ
_require_md_edit = require_cap_edit("market_demand")  # ghi: bắt buộc mức Sửa
_NOT_FOUND = "Không tìm thấy phiếu nhu cầu này."


@router.get("/items")
def list_items(date_from: str | None = Query(None, description="Từ ngày nhận 'YYYY-MM-DD'"),
               date_to: str | None = Query(None, description="Đến ngày nhận 'YYYY-MM-DD'"),
               company: str | None = Query(None),
               status: str | None = Query(None, description="open | signed | failed"),
               grade: str | None = Query(None),
               q: str | None = Query(None, max_length=120),
               username: str = Depends(_require_md)) -> dict:
    """Phiếu nhu cầu MỌI đơn vị trong khoảng ngày nhận (mặc định 90 ngày gần nhất)."""
    d_from, d_to = policy.date_range(date_from, date_to)
    return {
        "units": member_unit_repo.active_names(),
        "today": edit_window.today().isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "grades": GRADES,
        "items": market_demand_item_repo.list_items(
            None, d_from, d_to, company=company, status=status, grade=grade, q=q),
    }


@router.put("/items")
def save_item(body: DemandItemIn, username: str = Depends(_require_md_edit)) -> dict:
    """Thêm (id rỗng) hoặc sửa 1 phiếu của bất kỳ đơn vị đang hoạt động nào."""
    item = policy.clean(body.model_dump())
    # Đơn vị phải còn trong danh mục và chưa sáp nhập tại NGÀY NHẬN (câu báo chỉ rõ nhập vào đâu).
    assert_unit_can_enter(item["company"], item["as_of"])
    old = market_demand_item_repo.get(item["id"]) if item["id"] else None
    if item["id"] and old is None:
        raise HTTPException(404, _NOT_FOUND)
    policy.assert_save_fences(username, old, item)
    saved = market_demand_item_repo.save(item, username)
    if saved is None:
        raise HTTPException(404, _NOT_FOUND)
    return {"item": saved}


@router.delete("/items/{item_id}")
def delete_item(item_id: int, username: str = Depends(_require_md_edit)) -> dict:
    """Xoá 1 phiếu (nhập nhầm) — trong cửa sổ theo ngày nhận của phiếu."""
    old = market_demand_item_repo.get(item_id)
    if old is None:
        raise HTTPException(404, _NOT_FOUND)
    policy.assert_delete_fences(username, old)
    if not market_demand_item_repo.delete(item_id, None):
        raise HTTPException(404, _NOT_FOUND)
    return {"ok": True}
