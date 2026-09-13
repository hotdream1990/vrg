"""Logic quét + ghi DB — dùng chung cho router POST /scan và job theo lịch (daily_scan).

Tách khỏi router để cron có thể quét + tích lũy lịch sử mà KHÔNG cần HTTP server.
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import tempfile

from app.core.paths import crawlers_dir
from app.services import fx_freshness, price_repo, scan_alert_email, scan_run_summary

logger = logging.getLogger("vrg.scan")

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


def _write(records: list[dict], sources: str) -> tuple[int, int | None, str]:
    """Mở lượt quét + ghi bản ghi (best-effort). Lỗi ghi → đóng lượt `error` ngay. DB down → degrade."""
    try:
        run_id = price_repo.create_run(sources)
    except Exception as exc:  # noqa: BLE001 - DB down → vẫn trả dữ liệu quét
        return 0, None, f"skipped:{type(exc).__name__}"
    try:
        return price_repo.upsert_prices(records, run_id), run_id, "ok"
    except Exception as exc:  # noqa: BLE001
        price_repo.finish_run(run_id, "error", 0, str(exc)[:400])
        return 0, run_id, f"error:{type(exc).__name__}"


def persist(records: list[dict], sources: str) -> tuple[int, int | None, str]:
    """Ghi bản ghi vào DB (best-effort) → (persisted, run_id, db_note). Dùng cho backfill."""
    n, run_id, db_note = _write(records, sources)
    if db_note == "ok" and run_id is not None:
        price_repo.finish_run(run_id, "ok", n)
    return n, run_id, db_note


def _stale_fx() -> list[dict]:
    """Tỷ giá quá cũ — kiểm SAU khi ghi (số vừa quét được tính). DB lỗi → bỏ qua, không làm hỏng quét."""
    try:
        return fx_freshness.stale_pairs()
    except Exception:  # noqa: BLE001
        logger.warning("Không kiểm được độ tươi tỷ giá", exc_info=True)
        return []


def scan_and_persist(source: str = "all") -> dict:
    """Quét → ghi DB → tổng hợp trạng thái trung thực của lượt quét.

    Trả {records, sources, persisted, run_id, db, status, warnings, stale_fx}.
    """
    data = run_crawler(source)
    records = [rec for src in data for rec in src["records"]]
    sources = [
        {"source": s["source"], "status": s["status"], "count": len(s["records"]), "note": s.get("note")}
        for s in data
    ]
    persisted, run_id, db_note = _write(records, source)
    stale = _stale_fx() if db_note == "ok" else []
    warnings = scan_run_summary.run_warnings(sources, stale)
    status = scan_run_summary.run_status(db_note, warnings)
    if db_note == "ok" and run_id is not None:
        try:
            price_repo.finish_run(run_id, status, persisted, scan_run_summary.run_note(warnings))
        except Exception:  # noqa: BLE001 - đóng lượt hỏng không được nuốt mất dữ liệu đã quét
            logger.warning("Không đóng được lượt quét #%s", run_id, exc_info=True)
    return {"records": records, "sources": sources, "persisted": persisted, "run_id": run_id,
            "db": db_note, "status": status, "warnings": warnings, "stale_fx": stale}


def scheduled_scan(source: str = "all") -> dict:
    """Lượt quét THEO LỊCH (scheduler + job CLI): quét như trên rồi email cảnh báo nếu có vấn đề.

    `alert_email` = mã kết quả gửi email (clean/no_recipients/smtp_off/duplicate/sent/…).
    Email tự nuốt mọi lỗi — không bao giờ làm hỏng lượt quét.
    """
    result = scan_and_persist(source)
    result["alert_email"] = scan_alert_email.notify(result)
    if result["alert_email"] not in ("clean", "no_recipients"):
        logger.info("[scan] email cảnh báo quét giá: %s", result["alert_email"])
    return result
