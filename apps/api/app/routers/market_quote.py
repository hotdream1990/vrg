"""Router Báo giá mủ thị trường — 1 phiếu/ngày (nhập tay) + danh mục đơn vị tư nhân (Mục 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import assert_editor_window, block_unit_roles, require_admin, require_cap_edit
from app.schemas.market_quote import (
    MarketQuote,
    MarketQuoteMeta,
    MarketQuoteSummary,
    PrivateUnit,
    PrivateUnitCreate,
    VcbRateResult,
)
from app.services import market_private_unit_repo, market_quote_repo, vcb_rate

router = APIRouter(prefix="/api/market-quote", tags=["market-quote"])

#: Phiếu báo giá là số liệu mức Tập đoàn → tài khoản của đơn vị không được đọc.
#: Riêng `/vcb-rate` (tỷ giá VCB) vẫn mở: biểu Thu mua của chính đơn vị đang dùng để quy đổi.
_hq_only = [Depends(block_unit_roles)]

# ghi phiếu: quyền Báo giá mức Sửa; trả username để áp cửa sổ sửa
_editor_dep = Depends(require_cap_edit("market_quote"))


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
    """Chủng loại SVR cố định + gợi ý bao bì + danh mục đơn vị tư nhân (Mục 6) để dựng form."""
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


@router.get("/private-latest", dependencies=_hq_only)
def private_latest() -> dict:
    """Giá mủ tư nhân mới nhất của TỪNG đơn vị (kèm lần báo liền trước) — cho khối trên Dashboard."""
    from app.services import private_price_benchmark as pb

    return {"window_days": market_quote_repo.PRIVATE_PRICE_WINDOW_DAYS,
            "rows": market_quote_repo.private_prices_by_unit(),
            # Quy tắc chuyên viên (một nguồn ở backend) để khối Dashboard dựng vùng giá sàn hợp lý.
            "rule": {"floor_premium_min": pb.FLOOR_PREMIUM_MIN, "floor_premium_max": pb.FLOOR_PREMIUM_MAX}}


@router.post("/private-units", response_model=list[PrivateUnit], dependencies=_hq_only)
def add_private_unit(body: PrivateUnitCreate, username: str = _editor_dep):
    """Thêm đơn vị tư nhân vào danh mục Mục 6 (chuyên viên có quyền Báo giá). Trả danh mục mới."""
    try:
        market_private_unit_repo.add_unit(body.name, username)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return market_private_unit_repo.list_units()


@router.delete("/private-units/{unit_id}", response_model=list[PrivateUnit], dependencies=_hq_only)
def delete_private_unit(unit_id: int, _admin: str = Depends(require_admin)):
    """Xoá đơn vị tư nhân khỏi danh mục — CHỈ admin. Giá đã nhập ở các phiếu cũ giữ nguyên."""
    if not market_private_unit_repo.delete_unit(unit_id):
        raise HTTPException(404, "Không tìm thấy đơn vị tư nhân này")
    return market_private_unit_repo.list_units()


@router.get("/{as_of}", response_model=MarketQuote, dependencies=_hq_only)
def get_quote(as_of: str):
    """1 phiếu đầy đủ theo ngày."""
    quote = market_quote_repo.get_quote(as_of)
    if not quote:
        raise HTTPException(404, f"Chưa có báo giá ngày {as_of}")
    return quote


@router.put("", response_model=MarketQuote, dependencies=_hq_only)
def save_quote(mq: MarketQuote, username: str = _editor_dep):
    """Lưu/ghi đè phiếu theo ngày (trong cửa sổ sửa; admin miễn)."""
    assert_editor_window(username, mq.as_of)
    data = mq.model_dump()
    bad = market_quote_repo.invalid_private_rows(data.get("private_prices"))
    if bad:
        raise HTTPException(400, "Giá mủ tư nhân: Giá max phải lớn hơn Giá — " + ", ".join(bad))
    return market_quote_repo.save_quote(data)


@router.delete("/{as_of}", dependencies=_hq_only)
def delete_quote(as_of: str, username: str = Depends(require_cap_edit("market_quote"))) -> dict:
    """Xoá phiếu 1 ngày (payload + chuỗi market; trong cửa sổ sửa; admin miễn)."""
    assert_editor_window(username, as_of)
    if not market_quote_repo.delete_quote(as_of):
        raise HTTPException(404, f"Không có báo giá ngày {as_of}")
    return {"deleted": as_of}
