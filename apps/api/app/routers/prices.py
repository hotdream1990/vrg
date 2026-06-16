"""Endpoint giá: quét đa sàn (ghi DB) · backfill lịch sử · đọc giá mới nhất / lịch sử."""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException, Query

from app.schemas.price import HistorySeries, ScanResponse
from app.services import price_repo, scan_service

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


@router.get("/history", response_model=HistorySeries)
def history(
    source: str = Query(..., description="mã nguồn (anrpc, shfe, ...)"),
    grade: str = Query(..., description="mặt hàng (SMR20, RSS3, ...)"),
    days: int = Query(30, ge=1, le=730),
) -> HistorySeries:
    """Chuỗi giá lịch sử cho biểu đồ."""
    points = price_repo.history(source, grade, days)
    return HistorySeries(source=source, grade=grade, points=points)
