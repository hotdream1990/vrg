"""Router Nhu cầu thị trường cho CHUYÊN VIÊN có quyền `market_demand` — xem/sửa MỌI đơn vị.

Đơn vị thành viên tự nhập của mình qua `/api/member/market-demand` (router member_self).
Chuyên viên (editor được cấp quyền / admin) xem toàn bộ + sửa được, áp cửa sổ sửa của chuyên viên.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import edit_window
from app.core.security import assert_editor_window, require_cap
from app.schemas.market_demand import MarketDemandEdit
from app.services import market_demand_repo, member_unit_repo

router = APIRouter(prefix="/api/market-demand", tags=["market-demand"])
_require_md = require_cap("market_demand")


@router.get("/timeline")
def timeline(days: int = Query(90, ge=1, le=730),
             username: str = Depends(_require_md)) -> dict:
    """Timeline tổng quát: chỉ các ngày ĐÃ có nhu cầu (ẩn ngày trống) trong N ngày gần nhất."""
    date_from = (edit_window.today() - timedelta(days=days)).isoformat()
    return {
        "today": edit_window.today().isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "units": member_unit_repo.active_names(),  # cho form "Thêm nhu cầu"
        "entries": market_demand_repo.recent(date_from),
    }


@router.get("")
def list_all(as_of: str = Query(..., description="YYYY-MM-DD"),
             username: str = Depends(_require_md)) -> dict:
    """Nhu cầu MỌI đơn vị cho 1 ngày → lưới xem/sửa cho chuyên viên."""
    units = member_unit_repo.active_names()
    entries = market_demand_repo.entries_on(as_of)
    return {
        "units": units,
        "today": edit_window.today().isoformat(),
        "edit_window_days": edit_window.editor_window(),
        "entries": {u: entries.get(u, "") for u in units},
    }


@router.put("")
def upsert(body: MarketDemandEdit, username: str = Depends(_require_md)) -> dict:
    """Ghi/sửa nhu cầu 1 đơn vị (trong cửa sổ sửa của chuyên viên; admin miễn).

    `create_only=True` (nút Thêm nhu cầu) → chặn 409 nếu đơn vị đã có nhu cầu ngày đó (chống ghi trùng).
    """
    if body.company not in member_unit_repo.active_names():
        raise HTTPException(400, "Đơn vị không hợp lệ.")
    assert_editor_window(username, body.as_of)
    if body.create_only and market_demand_repo.entries_on(body.as_of).get(body.company, "").strip():
        raise HTTPException(409, "Đơn vị này đã có nhu cầu cho ngày này — vui lòng dùng chức năng Sửa.")
    market_demand_repo.upsert(body.as_of, body.company, body.content.strip(), username)
    return {"ok": True}
