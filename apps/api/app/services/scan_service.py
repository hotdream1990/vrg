"""Logic quét + ghi DB — dùng chung cho router POST /scan và job theo lịch (daily_scan).

Tách khỏi router để cron có thể quét + tích lũy lịch sử mà KHÔNG cần HTTP server.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import tempfile

from app.core.paths import crawlers_dir
from app.services import price_repo

# services/crawlers (uv project riêng, có pdfplumber/httpx)
_CRAWLER_DIR = crawlers_dir()


def run_crawler(sources: str) -> list[dict]:
    """Chạy crawler subprocess → list CrawlResult (dict). Raise lỗi thô (router bọc HTTP)."""
    out = pathlib.Path(tempfile.gettempdir()) / "vrg_scan.json"
    subprocess.run(
        ["uv", "run", "python", "-m", "crawlers.run_crawl", "--source", sources, "--out", str(out)],
        cwd=_CRAWLER_DIR,
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def persist(records: list[dict], sources: str) -> tuple[int, int | None, str]:
    """Ghi bản ghi vào DB (best-effort) → (persisted, run_id, db_note). DB down → degrade."""
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


def scan_and_persist(source: str = "all") -> dict:
    """Quét tất cả nguồn → ghi DB → dict {records, sources, persisted, run_id, db}."""
    data = run_crawler(source)
    records = [rec for src in data for rec in src["records"]]
    sources = [
        {"source": s["source"], "status": s["status"], "count": len(s["records"]), "note": s.get("note")}
        for s in data
    ]
    persisted, run_id, db_note = persist(records, source)
    return {"records": records, "sources": sources, "persisted": persisted, "run_id": run_id, "db": db_note}
