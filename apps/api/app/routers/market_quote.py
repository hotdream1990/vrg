"""Router Báo giá mủ thị trường — 1 phiếu/ngày (nhập tay, đồng bộ kho Giá mủ nguyên liệu)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import require_any_cap
from app.schemas.market_quote import (
    MarketQuote,
    MarketQuoteMeta,
    MarketQuoteSummary,
    VcbRateResult,
)
from app.services import market_quote_repo, vcb_rate

router = APIRouter(prefix="/api/market-quote", tags=["market-quote"])

_editor = [Depends(require_any_cap("market_quote", "raw_material"))]  # cần 1 trong 2 quyền (Mục 1-4 hoặc Mục 5)


@router.get("", response_model=list[MarketQuoteSummary])
def list_quotes(
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
):
    """Danh sách phiếu báo giá theo ngày (mới nhất trước)."""
    return market_quote_repo.list_quotes(date_from, date_to)


@router.get("/meta", response_model=MarketQuoteMeta)
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


@router.get("/history")
def get_price_history(days: int = Query(90, ge=7, le=365)) -> dict:
    """Lịch sử giá SVR thị trường (4 mục) theo ngày × chủng loại — cho biểu đồ xu hướng."""
    return market_quote_repo.price_history(days)


@router.get("/{as_of}", response_model=MarketQuote)
def get_quote(as_of: str):
    """1 phiếu đầy đủ theo ngày (Mục 4 đọc live từ kho Giá mủ nguyên liệu)."""
    quote = market_quote_repo.get_quote(as_of)
    if not quote:
        raise HTTPException(404, f"Chưa có báo giá ngày {as_of}")
    return quote


@router.put("", response_model=MarketQuote, dependencies=_editor)
def save_quote(mq: MarketQuote):
    """Lưu/ghi đè phiếu theo ngày + đồng bộ Mục 4 sang kho Giá mủ nguyên liệu."""
    return market_quote_repo.save_quote(mq.model_dump())


@router.delete("/{as_of}", dependencies=_editor)
def delete_quote(as_of: str) -> dict:
    """Xoá phiếu 1 ngày (giữ nguyên giá mủ nước đã đồng bộ sang kho chung)."""
    if not market_quote_repo.delete_quote(as_of):
        raise HTTPException(404, f"Không có báo giá ngày {as_of}")
    return {"deleted": as_of}
