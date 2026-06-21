"""Endpoint giá: quét đa sàn (ghi DB) · backfill lịch sử · đọc giá mới nhất / lịch sử."""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException, Query

from app.schemas.price import HistorySeries, PriceBoard, PriceRecordEdit, ScanResponse
from app.services import price_board, price_repo, scan_service

router = APIRouter(prefix="/api/prices", tags=["prices"])

_CRAWLER_DIR = pathlib.Path(__file__).resolve().parents[4] / "services" / "crawlers"


def _crawler_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(500, f"Không tìm thấy crawler: {exc}")
    if isinstance(exc, subprocess.CalledProcessError):
        return HTTPException(500, f"Crawl lỗi: {(exc.stderr or '')[-400:]}")
    if isinstance(exc, subprocess.TimeoutExpired):
        return HTTPException(504, "Crawl quá thời gian")
    return HTTPException(500, f"Lỗi crawl: {exc}")


@router.post("/scan", response_model=ScanResponse)
def scan(source: str = Query("all", description="all | anrpc,fx,sgx,shfe,tocom,lgm")) -> ScanResponse:
    """Quét tất cả nguồn → ghi DB → trả bản ghi + trạng thái nguồn + thông tin persist."""
    try:
        result = scan_service.scan_and_persist(source)
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise _crawler_http_error(exc) from exc
    return ScanResponse(**result)


@router.post("/backfill")
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


@router.delete("/purchase")
def delete_purchase(as_of: str = Query(..., description="YYYY-MM-DD")) -> dict:
    """Xoá toàn bộ giá thu mua mủ nước của 1 ngày."""
    return {"deleted": price_repo.delete_purchase_date(as_of)}


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


@router.put("/records")
def upsert_record(rec: PriceRecordEdit) -> dict:
    """Thêm mới hoặc sửa 1 bản ghi giá (theo khóa as_of+source+grade+contract+price_type)."""
    price_repo.upsert_record(rec.model_dump())
    return {"ok": True}


@router.delete("/records")
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
    source: str = Query(..., description="mã nguồn (anrpc, shfe, ...)"),
    grade: str = Query(..., description="mặt hàng (SMR20, RSS3, ...)"),
    days: int = Query(30, ge=1, le=730),
) -> HistorySeries:
    """Chuỗi giá lịch sử cho biểu đồ."""
    points = price_repo.history(source, grade, days)
    return HistorySeries(source=source, grade=grade, points=points)
