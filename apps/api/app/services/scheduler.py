"""Scheduler TRONG tiến trình API (APScheduler) — chạy job định kỳ theo lịch lưu ở DB.

Thay cho launchd/cron của OS: lịch do app quản lý, admin xem/sửa trên UI (trang Lịch chạy).
⚠ Chạy với 1 worker uvicorn — nhiều worker sẽ lên lịch trùng (mỗi worker 1 scheduler).
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services import scan_service, schedule_repo

_TZ = "Asia/Ho_Chi_Minh"

# Đăng ký job định kỳ: name → nhãn, mô tả, nguồn (khớp meta_crawl_run.sources),
# lịch mặc định (giờ, phút), hàm chạy.
JOB_REGISTRY: dict[str, dict] = {
    "daily-scan": {
        "label": "Quét giá đa sàn",
        "purpose": "Quét giá các sàn + tỷ giá → lưu DB (tích lũy lịch sử)",
        "source": "all",
        "default": (18, 0),
        "run": lambda: scan_service.scan_and_persist("all"),
    },
}

_scheduler: BackgroundScheduler | None = None


def _run_job(name: str) -> None:
    try:
        JOB_REGISTRY[name]["run"]()  # job tự ghi meta_crawl_run
    except Exception as exc:  # noqa: BLE001
        print(f"[scheduler] job '{name}' lỗi: {exc}")


def start() -> None:
    """Seed lịch mặc định + khởi động scheduler + lên lịch các job đang bật."""
    global _scheduler
    schedule_repo.seed_defaults({k: v["default"] for k, v in JOB_REGISTRY.items()})
    _scheduler = BackgroundScheduler(timezone=_TZ)
    _scheduler.start()
    sync()


def sync() -> None:
    """Đồng bộ APScheduler theo cấu hình DB (gọi lại sau khi đổi lịch)."""
    if _scheduler is None:
        return
    for job in schedule_repo.list_jobs():
        name = job["name"]
        if name not in JOB_REGISTRY:
            continue
        jid = f"job:{name}"
        if _scheduler.get_job(jid):
            _scheduler.remove_job(jid)
        if job["enabled"]:
            _scheduler.add_job(
                _run_job,
                CronTrigger(hour=job["hour"], minute=job["minute"], timezone=_TZ),
                args=[name], id=jid, replace_existing=True,
            )


def next_run(name: str) -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job(f"job:{name}")
    return job.next_run_time.isoformat() if job and job.next_run_time else None


def run_now(name: str) -> dict:
    """Chạy job ngay (đồng bộ) — trả kết quả như scan_service."""
    if name not in JOB_REGISTRY:
        raise KeyError(name)
    return JOB_REGISTRY[name]["run"]()
