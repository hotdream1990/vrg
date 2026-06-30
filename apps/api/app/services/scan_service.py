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


def scan_marketscreener(n: int = 5) -> dict:
    """Trigger crawl marketscreener (Firefox + login, ghi reuters physical) qua subprocess.

    Chạy trong env crawler (cần Firefox + psycopg). persist() tự ghi meta_crawl_run nên
    đọc lại run mới nhất để trả kết quả (kể cả lỗi Akamai 403).
    """
    proc = subprocess.run(
        ["uv", "run", "--with", "psycopg[binary]", "python", "-m",
         "crawlers.marketscreener", "--persist", str(n)],
        cwd=_CRAWLER_DIR, capture_output=True, text=True, timeout=300,
    )
    run = next((r for r in price_repo.recent_runs(5) if r["sources"] == "marketscreener"), None)
    if run and run["status"] in ("ok", "empty"):
        status = run["status"]
    else:
        status = "error"
    note = (run["error"] if run else None) or (proc.stderr[-300:] if status == "error" else None)
    return {
        "records": [],
        "sources": [{"source": "marketscreener", "status": status,
                     "count": run["rows"] if run else 0, "note": note}],
        "persisted": run["rows"] if run else 0,
        "run_id": run["id"] if run else None,
        "db": "ok",
    }


def scan_and_persist(source: str = "all") -> dict:
    """Quét tất cả nguồn → ghi DB → dict {records, sources, persisted, run_id, db}."""
    if source == "marketscreener":
        return scan_marketscreener()
    data = run_crawler(source)
    records = [rec for src in data for rec in src["records"]]
    sources = [
        {"source": s["source"], "status": s["status"], "count": len(s["records"]), "note": s.get("note")}
        for s in data
    ]
    persisted, run_id, db_note = persist(records, source)
    return {"records": records, "sources": sources, "persisted": persisted, "run_id": run_id, "db": db_note}
