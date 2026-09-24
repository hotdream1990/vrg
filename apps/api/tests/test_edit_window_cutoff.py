"""Cửa sổ nhập liệu theo GIỜ CHỐT (chốt 24/09/2026): số liệu ngày D nhập/sửa được đến 11:00 ngày D + N.

Test thuần, không cần DB — cấu hình giả qua `config_repo.get_value`. Phần gọi API thật (đơn vị ·
chuyên viên · admin, đồng hồ ghim) nằm ở `test_edit_window.py`.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.core import edit_window
from app.services import config_repo
from tests.edit_window_clock import VN, pin_clock

D = date(2026, 9, 24)


def _at(hour: int, minute: int = 0, day: date = D) -> datetime:
    return datetime.combine(day, time(hour, minute), VN)


@pytest.fixture()
def cfg(monkeypatch):
    """Cấu hình giả trong bộ nhớ — test thuần không đụng DB."""
    values: dict[str, str] = {}
    monkeypatch.setattr(config_repo, "get_value", lambda key: values.get(key))
    return values


# ── Test thuần ──────────────────────────────────────────────────────────────────────────────────
def test_deadline_is_cutoff_hour_of_day_plus_n(cfg) -> None:
    assert edit_window.deadline(D, 0) == _at(11)
    assert edit_window.deadline(D, 1) == _at(11, day=D + timedelta(days=1))
    assert edit_window.deadline(D, 7, hour=15) == _at(15, day=D + timedelta(days=7))


@pytest.mark.parametrize(("n", "hour", "minute", "expected"), [
    (0, 10, 59, D),                          # N=0 trước 11h: hôm nay còn mở
    (0, 11, 0, D + timedelta(days=1)),       # N=0 từ 11h: hôm nay cũng khoá (mốc > hôm nay)
    (1, 10, 59, D - timedelta(days=1)),      # N=1 trước 11h: hôm qua còn mở
    (1, 11, 0, D),                           # N=1 từ 11h: chỉ còn hôm nay
    (7, 8, 0, D - timedelta(days=7)),
    (7, 23, 59, D - timedelta(days=6)),
])
def test_editable_from_moves_at_the_cutoff(cfg, n, hour, minute, expected) -> None:
    assert edit_window.editable_from(n, _at(hour, minute)) == expected


def test_is_editable_never_opens_the_future(cfg) -> None:
    ref = _at(9)
    assert edit_window.is_editable(D, 0, ref)
    assert not edit_window.is_editable(D + timedelta(days=1), 7, ref)
    assert not edit_window.is_editable(D, 0, _at(11))
    assert edit_window.is_editable(D - timedelta(days=1), 1, _at(10))
    assert not edit_window.is_editable(D - timedelta(days=1), 1, _at(11))


def test_ref_in_another_timezone_is_read_as_vietnam_time(cfg) -> None:
    # 03:59 UTC = 10:59 VN (trước hạn) · 04:00 UTC = 11:00 VN (đúng hạn)
    assert edit_window.editable_from(0, datetime(2026, 9, 24, 3, 59, tzinfo=timezone.utc)) == D
    assert edit_window.editable_from(0, datetime(2026, 9, 24, 4, 0, tzinfo=timezone.utc)) == D + timedelta(days=1)


def test_cutoff_hour_is_configurable_and_falls_back_to_11(cfg) -> None:
    assert edit_window.cutoff_hour() == 11
    cfg["EDIT_CUTOFF_HOUR"] = "15"
    assert edit_window.cutoff_hour() == 15
    assert edit_window.editable_from(0, _at(14)) == D                      # 14h < 15h → hôm nay còn mở
    for bad in ("24", "-1", "abc", ""):
        cfg["EDIT_CUTOFF_HOUR"] = bad
        assert edit_window.cutoff_hour() == 11, bad


def test_window_phrase_names_the_cutoff(cfg) -> None:
    assert edit_window.window_phrase(0) == "đến 11:00 cùng ngày"
    assert edit_window.window_phrase(1) == "đến 11:00 ngày hôm sau"
    # N ≥ 2 KHÔNG được viết "ngày thứ N": "ngày thứ 7" đọc thành thứ Bảy.
    assert edit_window.window_phrase(7) == "đến 11:00, 7 ngày sau ngày số liệu"
    assert "thứ" not in edit_window.window_phrase(2)
    cfg["EDIT_CUTOFF_HOUR"] = "9"
    assert edit_window.window_phrase(1) == "đến 09:00 ngày hôm sau"


def test_huge_window_is_capped_instead_of_overflowing(cfg) -> None:
    """Admin gõ số rất lớn (hiểu là "không giới hạn") → chặn trần, không OverflowError → 500."""
    cfg["MEMBER_EDIT_WINDOW_DAYS"] = "9999999"
    assert edit_window.member_window() == edit_window.MAX_DAYS
    old = D - timedelta(days=edit_window.MAX_DAYS)
    assert edit_window.is_editable(old, edit_window.member_window(), _at(9))
    cfg["MEMBER_ALERT_DAYS"] = "9999999"
    assert edit_window.alert_days() == edit_window.MAX_DAYS


@pytest.mark.parametrize(("hour", "minute", "expected"), [
    (10, 59, _at(11)),                               # trước giờ chốt → 11:00 hôm nay
    (11, 0, _at(11, day=D + timedelta(days=1))),     # đúng/qua giờ chốt → 11:00 ngày mai
    (23, 59, _at(11, day=D + timedelta(days=1))),
])
def test_next_change_is_the_next_cutoff(cfg, hour, minute, expected) -> None:
    assert edit_window.next_change_at(_at(hour, minute)) == expected
    # Mốc không kèm múi giờ (job/test) coi như giờ VN — không được TypeError khi so với mốc có múi giờ.
    assert edit_window.next_change_at(_at(hour, minute).replace(tzinfo=None)) == expected


def test_assert_editable_marks_window_blocks(cfg, monkeypatch) -> None:
    pin_clock(monkeypatch, 11, 0, D)
    edit_window.assert_editable(D.isoformat(), 1)                           # hôm nay còn hạn
    with pytest.raises(HTTPException) as blocked:
        edit_window.assert_editable(D - timedelta(days=1), 1)
    assert blocked.value.status_code == 403
    assert blocked.value.headers == {edit_window.BLOCK_HEADER: "window"}
    assert "đến 11:00 ngày hôm sau" in blocked.value.detail
    with pytest.raises(HTTPException) as future:
        edit_window.assert_editable(D + timedelta(days=1), 1)
    assert future.value.status_code == 400 and not future.value.headers
    with pytest.raises(HTTPException) as bad:
        edit_window.assert_editable("24/09/2026", 1)
    assert bad.value.status_code == 400


def test_old_extra_day_keys_are_gone() -> None:
    keys = {s["key"] for s in config_repo.CONFIG_SPEC}
    assert "EDIT_CUTOFF_HOUR" in keys
    assert not keys & {"STOCK_EXTRA_WINDOW_DAYS", "PURCHASE_EXTRA_WINDOW_DAYS"}
