"""Router Báo giá mủ thị trường — 1 phiếu/ngày (nhập tay, đồng bộ kho Giá mủ nguyên liệu)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.permissions import LEVEL_EDIT, has_cap
from app.core.security import block_unit_roles, assert_editor_window, require_any_cap, require_cap_edit, user_caps
from app.schemas.market_quote import (
    MarketQuote,
    MarketQuoteMeta,
    MarketQuoteSummary,
    VcbRateResult,
)
from app.services import market_quote_repo, vcb_rate

router = APIRouter(prefix="/api/market-quote", tags=["market-quote"])

#: Phiếu báo giá có Mục 5 = GIÁ MỦ THEO TỪNG ĐƠN VỊ → tài khoản của đơn vị không được đọc.
#: Riêng `/vcb-rate` (tỷ giá VCB) vẫn mở: biểu Thu mua của chính đơn vị đang dùng để quy đổi.
_hq_only = [Depends(block_unit_roles)]

# ghi: cần 1 trong 2 quyền (Mục 1-4 hoặc Mục 5) ở mức Sửa; trả username để áp cửa sổ sửa
_editor_dep = Depends(require_any_cap("market_quote", "raw_material", level=LEVEL_EDIT))

_REGION_FIELDS = ("regions", "regions_cup")  # Mục 5 — thuộc quyền 'raw_material'


def _keep_sections_without_edit_right(data: dict, username: str) -> dict:
    """Phiếu gồm 2 khối thuộc 2 quyền khác nhau, nhưng dùng CHUNG 1 endpoint ghi.

    Khối nào người dùng không có mức Sửa thì bỏ qua giá trị gửi lên và giữ nguyên bản đã lưu
    (phiếu mới → giữ giá trị rỗng). Chặn ghi chéo, vd `market_quote:edit` + `raw_material:view`
    vẫn sửa được Mục 5 (giá mủ khu vực đồng bộ thẳng sang kho Giá mủ nguyên liệu).
    """
    caps = user_caps(username)
    may_region = has_cap(caps, "raw_material", LEVEL_EDIT)
    may_basic = has_cap(caps, "market_quote", LEVEL_EDIT)
    if may_region and may_basic:
        return data

    stored = market_quote_repo.get_quote(data["as_of"]) or {}
    blank = MarketQuote(as_of=data["as_of"]).model_dump()
    for field in data:
        if field == "as_of":
            continue
        if not (may_region if field in _REGION_FIELDS else may_basic):
            data[field] = stored.get(field, blank[field])
    return data


@router.get("", response_model=list[MarketQuoteSummary], dependencies=_hq_only)
def list_quotes(
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
    limit: int = Query(200, ge=1, le=1000, description="Trần số phiếu trả về (mới nhất trước)"),
):
    """Danh sách phiếu báo giá theo ngày (mới nhất trước), tối đa `limit` phiếu.

    Mỗi ngày một phiếu nên danh sách dài thêm mãi — phiếu cũ hơn tra bằng bộ lọc khoảng ngày.
    """
    return market_quote_repo.list_quotes(date_from, date_to, limit)


@router.get("/meta", response_model=MarketQuoteMeta, dependencies=_hq_only)
def meta():
    """Chủng loại SVR cố định + đơn vị thành viên (cột Mục 4) để dựng form."""
    return market_quote_repo.meta()


@router.get("/vcb-rate", response_model=VcbRateResult)
def vcb_rate_now(date: str | None = Query(None, description="YYYY-MM-DD (mặc định hôm nay)")):
    """Lấy tỷ giá USD của Vietcombank realtime (mua TM/CK + bán) để điền nhanh vào phiếu."""
    try:
        return vcb_rate.fetch_usd(date)
    except Exception as exc:  # noqa: BLE001 - nguồn ngoài (mạng/định dạng) → báo nhẹ, không lộ chi tiết
        raise HTTPException(502, "Không lấy được tỷ giá VCB (mạng/nguồn) — vui lòng nhập tay.") from exc


@router.get("/history", dependencies=_hq_only)
def get_price_history(days: int = Query(90, ge=7, le=365)) -> dict:
    """Lịch sử giá SVR thị trường (4 mục) theo ngày × chủng loại — cho biểu đồ xu hướng."""
    return market_quote_repo.price_history(days)


@router.get("/{as_of}", response_model=MarketQuote, dependencies=_hq_only)
def get_quote(as_of: str):
    """1 phiếu đầy đủ theo ngày (Mục 4 đọc live từ kho Giá mủ nguyên liệu)."""
    quote = market_quote_repo.get_quote(as_of)
    if not quote:
        raise HTTPException(404, f"Chưa có báo giá ngày {as_of}")
    return quote


@router.put("", response_model=MarketQuote, dependencies=_hq_only)
def save_quote(mq: MarketQuote, username: str = _editor_dep):
    """Lưu/ghi đè phiếu theo ngày + đồng bộ Mục 4 sang kho Giá mủ nguyên liệu (trong cửa sổ sửa; admin miễn)."""
    assert_editor_window(username, mq.as_of)
    return market_quote_repo.save_quote(_keep_sections_without_edit_right(mq.model_dump(), username))


@router.delete("/{as_of}", dependencies=_hq_only)
def delete_quote(as_of: str, username: str = Depends(require_cap_edit("market_quote"))) -> dict:
    """Xoá phiếu 1 ngày (giữ nguyên giá mủ nước đã đồng bộ sang kho chung; trong cửa sổ sửa; admin miễn).

    Xoá bỏ TOÀN BỘ phần Mục 1-4 (payload + chuỗi market) — dữ liệu của quyền `market_quote`,
    nên bắt buộc mức Sửa của đúng quyền đó; `raw_material` (Mục 5) không đủ để xoá phiếu.
    """
    assert_editor_window(username, as_of)
    if not market_quote_repo.delete_quote(as_of):
        raise HTTPException(404, f"Không có báo giá ngày {as_of}")
    return {"deleted": as_of}
