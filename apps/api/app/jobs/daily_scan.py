"""Job quét giá hàng ngày → ghi TimescaleDB (tích lũy lịch sử cho mọi grade).

Mỗi lần chạy thêm 1 điểm/ngày cho mọi nguồn — kể cả physical (LGM) vốn không có
archive theo ngày → dần dần đủ điểm để vẽ chart trend từng grade (SMR20, SIR20, ...).

Chạy thủ công:  cd apps/api && uv run python -m app.jobs.daily_scan
Theo lịch:      launchd plist `infra/launchd/com.vrg.daily-scan.plist` (qua scripts/daily-scan.sh).
Chỉ cần DB chạy (không cần HTTP server).
"""

from __future__ import annotations

from app.services import scan_service


def main() -> int:
    try:
        result = scan_service.scan_and_persist("all")
    except Exception as exc:  # noqa: BLE001 - log & thoát mã lỗi để cron biết
        print(f"daily-scan: CRAWL FAILED — {type(exc).__name__}: {exc}")
        return 1

    oks = sum(1 for s in result["sources"] if s["status"] == "ok")
    print(
        f"daily-scan: {len(result['records'])} records · persisted={result['persisted']} "
        f"· db={result['db']} · run={result['run_id']} · sources_ok={oks}/{len(result['sources'])}"
    )
    return 0 if result["db"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
