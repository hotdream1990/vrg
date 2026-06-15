"""Endpoint quét giá: bấm → chạy crawler tất cả nguồn → trả kết quả JSON cho dashboard."""

import json
import pathlib
import subprocess
import tempfile

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/prices", tags=["prices"])

# services/crawlers (uv project riêng, có pdfplumber/httpx)
_CRAWLER_DIR = pathlib.Path(__file__).resolve().parents[4] / "services" / "crawlers"


@router.get("/scan")
def scan() -> dict:
    """Quét tất cả nguồn (ANRPC · FX · SHFE · TOCOM/OSE …) và trả về bản ghi + trạng thái."""
    out = pathlib.Path(tempfile.gettempdir()) / "vrg_scan.json"
    try:
        subprocess.run(
            ["uv", "run", "python", "-m", "crawlers.run_crawl", "--source", "all", "--out", str(out)],
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

    data = json.loads(out.read_text(encoding="utf-8"))
    records = [rec for src in data for rec in src["records"]]
    sources = [
        {"source": s["source"], "status": s["status"], "count": len(s["records"]), "note": s.get("note")}
        for s in data
    ]
    return {"records": records, "sources": sources}
