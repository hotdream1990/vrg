"""Endpoint giá: quét đa sàn (ghi DB) + đọc giá mới nhất / lịch sử cho dashboard."""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException, Query

from app.schemas.price import HistorySeries, ScanResponse
from app.services import price_repo

router = APIRouter(prefix="/api/prices", tags=["prices"])

# services/crawlers (uv project riêng, có pdfplumber/httpx)
_CRAWLER_DIR = pathlib.Path(__file__).resolve().parents[4] / "services" / "crawlers"


def _run_crawler(sources: str) -> list[dict]:
    """Chạy crawler subprocess, trả về list CrawlResult (dict)."""
    out = pathlib.Path(tempfile.gettempdir()) / "vrg_scan.json"
    try:
        subprocess.run(
            ["uv", "run", "python", "-m", "crawlers.run_crawl", "--source", sources, "--out", str(out)],
            cwd=_CRAWLER_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except FileNotFoundError as exc:
        raise HTTPException(500, f"Không tìm thấy crawler: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"Crawl lỗi: {(exc.stderr or '')[-400:]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Crawl quá thời gian") from exc
    return json.loads(out.read_text(encoding="utf-8"))


def _persist(records: list[dict], sources: str) -> tuple[int, int | None, str]:
    """Ghi bản ghi vào DB (best-effort). Trả (persisted, run_id, db_note)."""
    try:
        run_id = price_repo.create_run(sources)
    except Exception as exc:  # noqa: BLE001 - DB down → vẫn trả dữ liệu quét
        return 0, None, f"skipped:{type(exc).__name__}"
    try:
        n = price_repo.upsert_prices(records, run_id)
        price_repo.finish_run(run_id, "ok", n)
        return n, run_id, "ok"
    except Exception as exc:  # noqa: BLE001
        price_repo.finish_run(run_id, "error", 0, str(exc)[:400])
        return 0, run_id, f"error:{type(exc).__name__}"


@router.post("/scan", response_model=ScanResponse)
def scan(source: str = Query("all", description="all | anrpc,fx,sgx,shfe,tocom,lgm")) -> ScanResponse:
    """Quét tất cả nguồn → ghi DB → trả bản ghi + trạng thái nguồn + thông tin persist."""
    data = _run_crawler(source)
    records = [rec for src in data for rec in src["records"]]
    sources = [
        {"source": s["source"], "status": s["status"], "count": len(s["records"]), "note": s.get("note")}
        for s in data
    ]
    persisted, run_id, db_note = _persist(records, source)
    return ScanResponse(
        records=records, sources=sources, persisted=persisted, run_id=run_id, db=db_note
    )


@router.post("/backfill")
def backfill(
    source: str = Query("shfe", description="nguồn có lịch sử theo ngày: shfe | tocom"),
    days: int = Query(90, ge=1, le=365),
) -> dict:
    """Nạp lịch sử settlement từ sàn (shfe nhanh · tocom chậm hơn) → DB để vẽ chart thật."""
    out = pathlib.Path(tempfile.gettempdir()) / f"vrg_backfill_{source}.json"
    try:
        subprocess.run(
            ["uv", "run", "python", "-m", "crawlers.run_crawl",
             "--backfill", "--source", source, "--days", str(days), "--out", str(out)],
            cwd=_CRAWLER_DIR, check=True, capture_output=True, text=True, timeout=600,
        )
    except FileNotFoundError as exc:
        raise HTTPException(500, f"Không tìm thấy crawler: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise HTTPException(500, f"Backfill lỗi: {(exc.stderr or '')[-400:]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(504, "Backfill quá thời gian") from exc

    records = json.loads(out.read_text(encoding="utf-8"))
    persisted, run_id, db_note = _persist(records, f"backfill:{source}")
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
