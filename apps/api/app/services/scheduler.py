"""Scheduler TRONG tiến trình API (APScheduler) — chạy job định kỳ theo lịch lưu ở DB.

Thay cho launchd/cron của OS: lịch do app quản lý, admin xem/sửa trên UI (trang Lịch chạy).
⚠ Chạy với 1 worker uvicorn — nhiều worker sẽ lên lịch trùng (mỗi worker 1 scheduler).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.services import inventory_auto, scan_service, schedule_repo, support_reminder_repo

logger = logging.getLogger("vrg.scheduler")

_TZ = "Asia/Ho_Chi_Minh"
_ZONE = ZoneInfo(_TZ)

#: Job lỡ giờ vì tiến trình đang bận/đang khởi động → APScheduler vẫn chạy bù trong khoảng này.
#: (Chỉ cứu được lúc tiến trình CÒN SỐNG; tiến trình tắt hẳn thì dựa vào `catch_up` bên dưới.)
_MISFIRE_GRACE = 3600

#: Sau khi khởi động bao lâu thì chạy các job đã lỡ (để app boot xong, DB/scheduler sẵn sàng).
_CATCHUP_DELAY_SECONDS = 30

#: 'mon'…'sun' → chỉ số của `datetime.weekday()` (0 = thứ Hai).
_DOW_INDEX = {d: i for i, d in enumerate(("mon", "tue", "wed", "thu", "fri", "sat", "sun"))}

# Các mốc quét trong ngày (giờ VN, Asia/Ho_Chi_Minh). "daily-scan" giữ tên cũ (đã seed DB) = 18:00.
# ⚠ Nguồn Á châu ra giá đầu-giữa chiều VN: LGM/MRB upload phiên "Noon" ~14:00 VN (15:00 giờ Malaysia),
# OSE/SHFE chốt settle ~13–14h VN. Trước các mốc đó nguồn CHƯA có giá hôm nay (buổi sáng chỉ lấy được
# giá hôm qua). Nên cụm chiều (14:30 · 15:00 · 18:00) mới bắt được số hôm nay + retry khi LGM prod
# chập chờn (route VN→gov.my hay EHOSTUNREACH). Mốc 12:00 lấp khoảng trống dài 07:30→15:00 (làm tươi
# SGX/tỷ giá). Seed enabled=true; admin tinh chỉnh/tắt từng mốc ở trang Lịch chạy.
_SCAN_SLOTS: dict[str, tuple[int, int]] = {
    "scan-0630": (6, 30),
    "scan-0730": (7, 30),
    "scan-1200": (12, 0),
    "scan-1430": (14, 30),
    "scan-1500": (15, 0),
    "daily-scan": (18, 0),
}


def _scan_meta(hm: tuple[int, int]) -> dict:
    return {
        "label": f"Quét giá đa sàn {hm[0]:02d}:{hm[1]:02d}",
        "purpose": "Quét giá các sàn + tỷ giá → lưu DB (tích lũy lịch sử)",
        "source": "all",
        "default": (hm[0], hm[1], None),        # (giờ, phút, thứ) — None = hằng ngày
        "run": scan_service.scheduled_scan,  # quét + email cảnh báo nếu có vấn đề
    }


# Đăng ký job định kỳ: name → nhãn, mô tả, nguồn (khớp meta_crawl_run.sources),
# lịch mặc định (giờ, phút, thứ), hàm chạy. Mỗi mốc = 1 job (admin xem/sửa/tắt riêng ở Lịch chạy).
# `catch_up=True` → lỡ giờ vì máy chủ tắt/deploy thì chạy bù ngay sau khi khởi động lại.
JOB_REGISTRY: dict[str, dict] = {name: _scan_meta(hm) for name, hm in _SCAN_SLOTS.items()}

JOB_REGISTRY[inventory_auto.WEEKLY_JOB_NAME] = {
    "label": "Chốt tồn kho Tập đoàn (tối thứ Sáu)",
    "purpose": "Cộng tồn kho từ biểu Tồn kho của đơn vị thành viên → chuỗi tuần Tồn kho Tập đoàn "
               "(chỉ chạy khi chuyên viên đã bật tự tính; không đè tuần nhập tay)",
    "source": inventory_auto.WEEKLY_JOB_SOURCE,
    "default": (19, 0, "fri"),
    "catch_up": True,
    "run": inventory_auto.run_weekly_job,
}

#: Nhịp rà NHẮC LỊCH (phút). Cố tình KHÔNG đưa vào `JOB_REGISTRY`/trang Lịch chạy: đây không phải
#: một mốc chạy trong ngày mà là vòng rà nền — giờ phát do từng lịch nhắc tự quyết (`next_at`).
_REMINDER_INTERVAL_MINUTES = 5

_scheduler: BackgroundScheduler | None = None


def _run_job(name: str) -> None:
    try:
        JOB_REGISTRY[name]["run"]()  # job tự ghi meta_crawl_run
    except Exception as exc:  # noqa: BLE001
        print(f"[scheduler] job '{name}' lỗi: {exc}")


def last_due(hour: int, minute: int, dow: str | None, ref: datetime) -> datetime:
    """Thời điểm job ĐÁNG LẼ chạy gần nhất tính đến `ref` (mốc để biết đã lỡ hay chưa).

    Hằng ngày → hôm nay (hoặc hôm qua nếu chưa tới giờ). Theo thứ → đúng thứ đó gần nhất đã qua.
    """
    d = ref.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if d > ref:
        d -= timedelta(days=1)
    if not dow:
        return d
    return d - timedelta(days=(d.weekday() - _DOW_INDEX[dow]) % 7)


def missed_jobs(now: datetime | None = None) -> list[str]:
    """Các job `catch_up` đang BẬT mà lần chạy gần nhất còn trước mốc đáng lẽ phải chạy.

    Đây là lưới an toàn cho việc tiến trình KHÔNG chạy vào giờ đó (deploy, khởi động lại, máy chủ
    tắt): APScheduler dùng jobstore trong bộ nhớ nên khởi động lại là quên sạch các lần đã lỡ.
    """
    ref = now or datetime.now(_ZONE)
    out: list[str] = []
    for job in schedule_repo.list_jobs():
        meta = JOB_REGISTRY.get(job["name"])
        if not meta or not meta.get("catch_up") or not job["enabled"]:
            continue
        due = last_due(job["hour"], job["minute"], job["day_of_week"], ref)
        last = schedule_repo.last_run_for(meta["source"])
        started = last["started_at"] if last else None
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=_ZONE)
        if started is None or started < due:
            out.append(job["name"])
    return out


def _schedule_catch_up() -> None:
    """Lên lịch chạy bù (một lần, ngay sau khi khởi động) cho các job đã lỡ."""
    if _scheduler is None:
        return
    run_at = datetime.now(_ZONE) + timedelta(seconds=_CATCHUP_DELAY_SECONDS)
    for name in missed_jobs():
        logger.warning("[scheduler] job '%s' đã lỡ giờ — chạy bù lúc %s", name, run_at)
        _scheduler.add_job(_run_job, "date", run_date=run_at, args=[name],
                           id=f"catchup:{name}", replace_existing=True)


def start() -> None:
    """Seed lịch mặc định + khởi động scheduler + lên lịch các job đang bật."""
    global _scheduler
    schedule_repo.seed_defaults({k: v["default"] for k, v in JOB_REGISTRY.items()})
    _scheduler = BackgroundScheduler(timezone=_TZ)
    _scheduler.start()
    sync()
    _schedule_catch_up()
    _schedule_reminders()


def _run_reminders() -> None:
    """Rà các lịch nhắc đã tới hạn → phát thông báo + email (xem `support_reminder_repo`)."""
    try:
        result = support_reminder_repo.run_due()
        if result["reminders"]:
            logger.info("[nhắc lịch] phát %s lịch → %s tin", result["reminders"], result["threads"])
    except Exception as exc:  # noqa: BLE001 - lỗi rà không được làm chết scheduler
        logger.warning("[nhắc lịch] lỗi khi rà: %s", exc)


def _schedule_reminders() -> None:
    """Vòng rà nhắc lịch, chạy ngay khi khởi động rồi lặp lại mỗi `_REMINDER_INTERVAL_MINUTES` phút.

    Chạy ngay lần đầu chính là cơ chế PHÁT BÙ: máy chủ tắt qua giờ hẹn thì lịch vẫn còn tới hạn,
    khởi động lại là phát.
    """
    if _scheduler is None:
        return
    _scheduler.add_job(
        _run_reminders, "interval", minutes=_REMINDER_INTERVAL_MINUTES,
        next_run_time=datetime.now(_ZONE) + timedelta(seconds=_CATCHUP_DELAY_SECONDS),
        id="job:support-reminders", replace_existing=True, misfire_grace_time=_MISFIRE_GRACE,
    )


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
                CronTrigger(day_of_week=job["day_of_week"] or None, hour=job["hour"],
                            minute=job["minute"], timezone=_TZ),
                args=[name], id=jid, replace_existing=True,
                misfire_grace_time=_MISFIRE_GRACE,
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
