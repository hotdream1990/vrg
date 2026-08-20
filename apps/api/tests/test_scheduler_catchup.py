"""Test job định kỳ CHẠY BÙ sau khi tiến trình khởi động lại (APScheduler quên job đã lỡ).

Bối cảnh: jobstore của APScheduler nằm trong BỘ NHỚ. Máy chủ tắt/deploy đúng lúc job phải chạy là
lần đó mất luôn, không ai biết. `scheduler.missed_jobs()` so "lần chạy gần nhất" (meta_crawl_run)
với "mốc đáng lẽ phải chạy" (`last_due`) để lúc khởi động lên lịch chạy bù.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.services import inventory_auto, schedule_repo, scheduler

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

ZONE = ZoneInfo("Asia/Ho_Chi_Minh")
JOB = inventory_auto.WEEKLY_JOB_NAME


def _clear_runs() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM meta_crawl_run WHERE sources = :s"),
                   {"s": inventory_auto.WEEKLY_JOB_SOURCE})


@pytest.fixture()
def seeded_job():
    """Job có mặt trong bảng lịch + chưa có lần chạy nào; dọn các dòng chạy do test tạo ra."""
    schedule_repo.seed_defaults({k: v["default"] for k, v in scheduler.JOB_REGISTRY.items()})
    _clear_runs()
    yield
    _clear_runs()


def test_last_due_daily_vs_weekly():
    """Mốc "đáng lẽ chạy": job ngày lùi tối đa 1 ngày, job tuần lùi về đúng thứ của nó."""
    # Thứ Hai 24/08/2026, 08:00 sáng.
    ref = datetime(2026, 8, 24, 8, 0, tzinfo=ZONE)
    assert ref.weekday() == 0

    daily = scheduler.last_due(19, 0, None, ref)          # 19:00 hôm nay chưa tới → lấy hôm qua
    assert (daily.day, daily.hour) == (23, 19)

    weekly = scheduler.last_due(19, 0, "fri", ref)        # thứ Sáu gần nhất đã qua = 21/08
    assert (weekly.day, weekly.weekday()) == (21, 4)

    # Đúng thứ Sáu, sau giờ chạy → mốc là chính hôm nay.
    fri_evening = datetime(2026, 8, 21, 20, 30, tzinfo=ZONE)
    assert scheduler.last_due(19, 0, "fri", fri_evening).day == 21


def test_missed_job_detected_then_cleared_by_a_run(seeded_job):
    """Chưa chạy lần nào → tính là đã lỡ; chạy xong (kể cả khi tự tính đang TẮT) → hết nợ."""
    assert JOB in scheduler.missed_jobs()

    res = inventory_auto.run_weekly_job()
    assert res["sources"][0]["source"] == inventory_auto.WEEKLY_JOB_SOURCE
    assert res["sources"][0]["note"]                      # luôn có mô tả cho trang Lịch chạy
    assert JOB not in scheduler.missed_jobs()


def test_run_older_than_due_is_still_missed(seeded_job):
    """Lần chạy gần nhất cũ hơn mốc đáng lẽ phải chạy (máy chủ tắt cả tuần) → vẫn phải chạy bù."""
    inventory_auto.run_weekly_job()
    assert JOB not in scheduler.missed_jobs()
    with session_scope() as db:                           # đẩy lần chạy đó lùi 8 ngày
        db.execute(text("UPDATE meta_crawl_run SET started_at = started_at - interval '8 days' "
                        "WHERE sources = :s"), {"s": inventory_auto.WEEKLY_JOB_SOURCE})
    assert JOB in scheduler.missed_jobs()


def test_disabled_job_is_never_caught_up(seeded_job):
    """Admin tắt job ở trang Lịch chạy → khởi động lại cũng không được tự chạy."""
    job = next(j for j in schedule_repo.list_jobs() if j["name"] == JOB)
    schedule_repo.update_job(JOB, job["hour"], job["minute"], False)
    try:
        assert JOB not in scheduler.missed_jobs()
    finally:
        schedule_repo.update_job(JOB, job["hour"], job["minute"], True)


def test_weekly_job_runs_on_friday_evening(seeded_job):
    """Lịch mặc định = 19:00 thứ Sáu, và mốc chốt của job trùng ngày chốt tuần (thứ Sáu)."""
    job = next(j for j in schedule_repo.list_jobs() if j["name"] == JOB)
    assert (job["hour"], job["minute"], job["day_of_week"]) == (19, 0, "fri")
    ref = datetime.now(ZONE) + timedelta(days=1)
    assert scheduler.last_due(job["hour"], job["minute"], job["day_of_week"], ref).weekday() \
        == inventory_auto.ANCHOR_WEEKDAY
