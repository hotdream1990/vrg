"""Endpoint giá: quét đa sàn (ghi DB) · backfill lịch sử · đọc giá mới nhất / lịch sử."""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.paths import crawlers_dir
from app.core.security import require_editor
from app.schemas.price import (
    HistorySeries,
    PriceBoard,
    PriceRecordEdit,
    ReutersParseRequest,
    ReutersParseResult,
    ScanResponse,
)
from app.services import price_board, price_repo, reuters_physical_parse, scan_service

logger = logging.getLogger("vrg.api")

router = APIRouter(prefix="/api/prices", tags=["prices"])

_editor = [Depends(require_editor)]  # ghi: cần admin/editor (viewer chỉ xem)

_CRAWLER_DIR = crawlers_dir()


def _crawler_http_error(exc: Exception) -> HTTPException:
    """Log chi tiết lỗi crawl phía server; trả về message chung (không lộ đường dẫn/stderr)."""
    logger.error("Crawler thất bại", exc_info=exc)
    if isinstance(exc, subprocess.TimeoutExpired):
        return HTTPException(504, "Quá thời gian khi quét giá — vui lòng thử lại.")
    if isinstance(exc, FileNotFoundError):
        return HTTPException(500, "Không tìm thấy crawler trên máy chủ — liên hệ quản trị.")
    return HTTPException(500, "Quét giá thất bại — kiểm tra log máy chủ hoặc liên hệ quản trị.")


@router.post("/scan", response_model=ScanResponse, dependencies=_editor)
def scan(source: str = Query("all", description="all | fx,sgx,shfe,tocom,lgm")) -> ScanResponse:
    """Quét tất cả nguồn → ghi DB → trả bản ghi + trạng thái nguồn + thông tin persist."""
    try:
        result = scan_service.scan_and_persist(source)
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise _crawler_http_error(exc) from exc
    return ScanResponse(**result)


@router.post("/backfill", dependencies=_editor)
def backfill(
    source: str = Query("shfe", description="nguồn có lịch sử theo ngày: shfe | tocom | fx"),
    days: int = Query(90, ge=1, le=365),
) -> dict:
    """Nạp lịch sử settlement/tỷ giá từ sàn (shfe/tocom/fx) → DB để vẽ chart thật."""
    out = pathlib.Path(tempfile.gettempdir()) / f"vrg_backfill_{source}.json"
    try:
        subprocess.run(
            ["uv", "run", "python", "-m", "crawlers.run_crawl",
             "--backfill", "--source", source, "--days", str(days), "--out", str(out)],
            cwd=_CRAWLER_DIR, check=True, capture_output=True, text=True, timeout=600,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise _crawler_http_error(exc) from exc

    records = json.loads(out.read_text(encoding="utf-8"))
    persisted, run_id, db_note = scan_service.persist(records, f"backfill:{source}")
    return {"source": source, "days": days, "records": len(records),
            "persisted": persisted, "run_id": run_id, "db": db_note}


@router.get("/latest")
def latest() -> dict:
    """Giá mới nhất mỗi (sàn, mặt hàng) đã ghi trong DB."""
    return {"records": price_repo.latest()}


@router.get("/crawl-runs")
def crawl_runs(limit: int = Query(20, ge=1, le=100)) -> dict:
    """Nhật ký các lần quét gần nhất (manual + cron) từ meta_crawl_run."""
    return {"runs": price_repo.recent_runs(limit)}


@router.get("/board", response_model=PriceBoard)
def board() -> PriceBoard:
    """Bảng giá thành phần per sàn (native · tỷ giá · USD/T) + danh sách tỷ giá."""
    return PriceBoard(**price_board.build_board())


@router.get("/purchase-sheet")
def purchase_sheet(
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
) -> dict:
    """Lưới Giá mủ nguyên liệu (giá thu mua mủ nước): công ty × ngày (đồng/độ TSC)."""
    return price_repo.purchase_sheet(date_from, date_to)


@router.delete("/purchase", dependencies=_editor)
def delete_purchase(as_of: str = Query(..., description="YYYY-MM-DD")) -> dict:
    """Xoá toàn bộ giá thu mua mủ nước của 1 ngày."""
    return {"deleted": price_repo.delete_purchase_date(as_of)}


@router.get("/physical-sheet")
def physical_sheet(
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
) -> dict:
    """Lưới Giá Physical (giao ngay): grade × ngày (nguồn reuters)."""
    return price_repo.physical_sheet(date_from, date_to)


@router.delete("/physical", dependencies=_editor)
def delete_physical(as_of: str = Query(..., description="YYYY-MM-DD")) -> dict:
    """Xoá toàn bộ giá physical của 1 ngày."""
    return {"deleted": price_repo.delete_physical_date(as_of)}


@router.post("/physical/parse-reuters", response_model=ReutersParseResult, dependencies=_editor)
def parse_reuters(req: ReutersParseRequest) -> dict:
    """Phân giải chuỗi giá physical Reuters (paste từ MarketScreener) → preview USD/tấn (chưa ghi DB)."""
    return reuters_physical_parse.parse(req.text, as_of=req.as_of)


@router.get("/sheet")
def sheet(
    days: int = Query(30, ge=1, le=365),
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
) -> dict:
    """Lưới 'Bảng tính giá' giống sheet mẫu VRG: ngày × sàn (Native·Tỷ giá·USD) + tỷ giá."""
    from app.services import price_sheet

    return price_sheet.build_sheet(days, date_from, date_to)


@router.get("/records")
def list_records(
    source: str | None = Query(None, description="lọc theo nguồn"),
    grade: str | None = Query(None, description="lọc theo chỉ số (chứa)"),
    date_from: str | None = Query(None, description="từ ngày YYYY-MM-DD"),
    date_to: str | None = Query(None, description="đến ngày YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=500),
) -> dict:
    """Danh sách bản ghi giá để quản lý — lọc + phân trang. Trả {records, total, page, page_size}."""
    res = price_repo.list_records(source, grade, date_from, date_to, page_size, (page - 1) * page_size)
    return {**res, "page": page, "page_size": page_size}


@router.put("/records", dependencies=_editor)
def upsert_record(rec: PriceRecordEdit) -> dict:
    """Thêm mới hoặc sửa 1 bản ghi giá (theo khóa as_of+source+grade+contract+price_type)."""
    price_repo.upsert_record(rec.model_dump())
    return {"ok": True}


@router.delete("/records", dependencies=_editor)
def delete_record(
    as_of: str = Query(..., description="YYYY-MM-DD"),
    source: str = Query(...),
    grade: str = Query(...),
    contract: str = Query(""),
    price_type: str = Query(...),
) -> dict:
    """Xóa 1 bản ghi giá theo khóa."""
    if not price_repo.delete_record(as_of, source, grade, contract, price_type):
        raise HTTPException(404, "Không tìm thấy bản ghi để xóa")
    return {"deleted": True}


@router.get("/history", response_model=HistorySeries)
def history(
    source: str = Query(..., description="mã nguồn (reuters, shfe, ...)"),
    grade: str = Query(..., description="mặt hàng (SMR20, RSS3, ...)"),
    days: int = Query(30, ge=1, le=730),
) -> HistorySeries:
    """Chuỗi giá lịch sử cho biểu đồ."""
    points = price_repo.history(source, grade, days)
    return HistorySeries(source=source, grade=grade, points=points)
