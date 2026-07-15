"""Router tài khoản ĐƠN VỊ THÀNH VIÊN — tự xem/nhập giá mủ nước + mủ chén của CÁC đơn vị được gán.

Gác bằng `get_current_member` (role=member, đã gán ≥1 đơn vị). Mỗi thao tác ghi phải kèm `company`
và server kiểm tra company thuộc danh sách gán của tài khoản → không thể đụng đơn vị khác. Chỉ
nhập/sửa được HÔM NAY + N ngày gần nhất (server ép); ngày cũ hơn chỉ để xem.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import edit_window
from app.core.security import get_current_member
from app.schemas.member_self import MemberPriceEdit
from app.services import price_repo

router = APIRouter(prefix="/api/member", tags=["member-self"])

_UNIT = {"purchase": "đồng/độ TSC", "purchase_cup": "đồng/kg"}


def _assert_company(member: dict, company: str) -> None:
    """Chặn ghi cho đơn vị không được gán cho tài khoản này."""
    if company not in (member.get("member_units") or []):
        raise HTTPException(403, "Đơn vị không thuộc quyền quản lý của tài khoản.")


@router.get("/prices")
def my_prices(days: int = Query(30, ge=1, le=180),
              member: dict = Depends(get_current_member)) -> dict:
    """Lịch sử giá mủ nước + mủ chén của TỪNG đơn vị được gán (dựng lưới xem/nhập)."""
    units = list(member["member_units"])
    sheets = {u: price_repo.member_price_history(u, days) for u in units}
    return {"units": units, "today": edit_window.today().isoformat(),
            "edit_window_days": edit_window.member_window(), "sheets": sheets}


@router.put("/prices")
def upsert_my_price(body: MemberPriceEdit,
                    member: dict = Depends(get_current_member)) -> dict:
    """Nhập/sửa 1 ô giá (mủ nước hoặc mủ chén) cho 1 đơn vị được gán, trong cửa sổ cho phép."""
    _assert_company(member, body.company)
    edit_window.assert_editable(body.as_of, edit_window.member_window())
    price_repo.upsert_record({
        "as_of": body.as_of, "source": "vrg", "grade": body.company, "contract": "",
        "price_type": body.price_type, "price": float(body.price),
        "currency": "VND", "unit": _UNIT[body.price_type],
    })
    return {"ok": True}


@router.delete("/prices")
def clear_my_price(
    company: str = Query(...),
    as_of: str = Query(..., description="YYYY-MM-DD"),
    price_type: str = Query(..., description="purchase | purchase_cup"),
    member: dict = Depends(get_current_member),
) -> dict:
    """Xoá 1 ô giá của 1 đơn vị được gán (trong cửa sổ cho phép)."""
    _assert_company(member, company)
    if price_type not in _UNIT:
        raise HTTPException(400, "Loại giá không hợp lệ.")
    edit_window.assert_editable(as_of, edit_window.member_window())
    price_repo.delete_record(as_of, "vrg", company, "", price_type)
    return {"deleted": True}
