"""Test luật chỉ số ngày sau review 30/09/2026 (thuần hàm): bộ đếm bị giảm giữa ngày → `reset`, gộp
mẫu phút vào chuỗi giờ, đồng hồ SCADA nhanh/chậm quanh nửa đêm, BQ/ngày + suất tiêu hao chỉ tính ngày
đủ số, ngày cuối kỳ bỏ mẫu sau D+1 00:00."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.services import scada_daily_meters as dm
from tests.test_scada_daily_meters import D1, D2, at, hourly, raw, report

D3 = D2 + timedelta(days=1)


# ── Bộ đếm bị giảm trong ngày ──

def test_counter_reset_to_zero_at_midnight_flags_every_day() -> None:
    """Số bành đặt lại về 0 lúc 00:00 mỗi ngày → mọi ngày `reset`, không đoán tiêu thụ."""
    rows = ([raw(at(D1, h), 1000 + 10 * h, 50 + h, 2 * h) for h in range(24)]
            + [raw(at(D2, h), 1240 + 10 * h, 74 + h, 2 * h) for h in range(24)]
            + [raw(at(D3), 1480, 98, 0)])
    rep = report(rows)
    assert [r["bales"]["flag"] for r in rep["rows"]] == ["reset", "reset"]
    assert all(r["bales"]["used"] is None and r["kwh_per_bale"] is None for r in rep["rows"])
    assert [r["energy"]["flag"] for r in rep["rows"]] == [None, None]
    assert rep["summary"]["bales"] == {"latest": None, "latest_at": None, "total": None,
                                       "avg_per_day": None, "days_with_data": 0,
                                       "days_complete": 0}
    assert rep["intensity"] == {"kwh_per_bale": None, "m3_per_bale": None}


def test_counter_reset_mid_day_flags_even_when_close_above_open() -> None:
    """Đặt lại lúc 06:00 (theo ca) rồi chạy lên quá số đầu ngày → cuối > đầu nhưng vẫn `reset`."""
    water = [100 + h if h < 6 else 10 * (h - 6) for h in range(24)]
    rows = ([raw(at(D1, h), 1000 + 10 * h, water[h], 100 + 2 * h) for h in range(24)]
            + [raw(at(D2), 1240, 180, 148)])
    row = report(rows, D1, D1)["rows"][0]
    assert row["water"] == {"open": 100.0, "open_at": "2026-09-01T00:00:00", "close": 180.0,
                            "close_at": "2026-09-02T00:00:00", "used": None, "flag": "reset"}
    assert row["m3_per_bale"] is None and row["kwh_per_bale"] == 5.0


def test_register_misalignment_dip_flags_reset() -> None:
    """4 thanh ghi đọc lệch nhịp: R3 đã quay vòng nhưng R2 chưa tăng → tụt ~65,5 kWh một mẫu."""
    rows = ([raw(at(D1, h), 65.4 + 0.01 * h, 50 + h, 100 + 2 * h) for h in range(24)]
            + [raw(at(D2), 65.64, 74, 148)])
    assert report(rows, D1, D1)["rows"][0]["energy"]["used"] == 0.24  # đọc đúng nhịp: bình thường
    ts, vals = rows[14]
    assert (vals["R2"], vals["R3"]) == (1, 4)  # 65,540 kWh = 65540 Wh
    rows[14] = (ts, {**vals, "R2": 0})  # đọc lệch → 0,004 kWh
    cell = report(rows, D1, D1)["rows"][0]["energy"]
    assert cell["flag"] == "reset" and cell["used"] is None and cell["close"] > cell["open"]


def test_float_noise_is_not_a_reset() -> None:
    """Giảm chỉ ở phần lẻ dưới mức làm tròn (3 số lẻ / số nguyên bành) → không phải đặt lại."""
    rows = ([raw(at(D1, h), 1000 + 10 * h, 100 + h, 100 + 2 * h) for h in range(24)]
            + [raw(at(D2), 1240, 124, 148)])
    rows[6] = raw(at(D1, 6), 1060, 105 - 1e-7, 109.6)   # mẫu 05:00: nước 105 · bành 110
    row = report(rows, D1, D1)["rows"][0]
    assert row["water"]["flag"] is None and row["water"]["used"] == 24.0
    assert row["bales"]["flag"] is None and row["bales"]["used"] == 48


def test_small_meter_backstep_is_noise_not_reset() -> None:
    """Số THẬT Phú Riềng 08/09/2026: đồng hồ nước lùi 0,003 m³ lúc 05:00 (8.486,471 → 8.486,468).
    Luật "giảm bất kỳ" từng gắn `reset` → mất 157,997 m³ mà RELCO vẫn tính. Lùi < 1% = nhiễu."""
    water = [8486.354, 8486.354, 8486.354, 8486.355, 8486.471, 8486.468, 8486.468, 8489.009]
    water += [8644.351] * 16
    rows = ([raw(at(D1, h), 195000 + 10 * h, water[h], 100 + 2 * h) for h in range(24)]
            + [raw(at(D2), 195240, 8644.351, 148)])
    cell = report(rows, D1, D1)["rows"][0]["water"]
    assert cell["flag"] is None and cell["used"] == 157.997


def test_idle_day_net_backstep_is_zero_not_negative() -> None:
    """Ngày nghỉ: đồng hồ chỉ lùi nhẹ rồi đứng yên → tiêu thụ 0, không âm, không cờ."""
    rows = ([raw(at(D1, h), 1000, 9146.557 if h < 3 else 9146.554, 500) for h in range(24)]
            + [raw(at(D2), 1000, 9146.554, 500)])
    cell = report(rows, D1, D1)["rows"][0]["water"]
    assert cell["flag"] is None and cell["used"] == 0


def test_register_misalignment_on_large_counter_is_below_reset_threshold() -> None:
    """Đánh đổi có chủ đích: lũy kế ~195.000 kWh, lệch nhịp tụt 65,536 kWh (≈0,03%) < 1% → không
    gắn `reset`; tiêu thụ ngày vẫn là cuối − đầu (mẫu lệch giữa ngày không làm sai số ngày)."""
    rows = ([raw(at(D1, h), 195000 + 100 * h, 50 + h, 100 + 2 * h) for h in range(24)]
            + [raw(at(D2), 197400, 74, 148)])
    rows[14] = raw(at(D1, 14), 195000 + 1400 - 65.536, 64, 128)
    cell = report(rows, D1, D1)["rows"][0]["energy"]
    assert cell["flag"] is None and cell["used"] == 2400.0


def test_reset_check_ignores_samples_after_midnight_close() -> None:
    """Kỳ đã qua truy vấn tới D+1 01:00: số tụt sau mốc 00:00 không thuộc ngày D."""
    rows = hourly(D1, 1000, 50, 100) + [raw(at(D2), 1240, 74, 148), raw(at(D2, 1), 5, 1, 0)]
    cell = report(rows, D1, D1)["rows"][0]["energy"]
    assert cell["close_at"] == "2026-09-02T00:00:00" and cell["used"] == 240.0
    assert cell["flag"] is None


# ── Gộp mẫu phút · đồng hồ SCADA quanh nửa đêm ──

def test_merge_samples_hourly_wins_minute_fills_gaps() -> None:
    t0, t1 = at(D1, 0, 59), at(D1, 1)
    merged = dm.merge_samples([(t1, {"energy": None, "water": 5.0})],
                              [(t1, {"energy": 7.0, "water": 6.0}), (t0, {"energy": 1.0})])
    assert merged == [(t0, {"energy": 1.0}), (t1, {"energy": 7.0, "water": 5.0})]


def test_today_with_only_minute_samples_is_not_no_data() -> None:
    """00:08 — Historian chưa trả mẫu giờ nào của hôm nay, mẫu phút đã có → hôm nay có số."""
    minute = [raw(at(D1, 23, 59), 1239.9, 73.9, 147)] + [
        raw(at(D2, 0, m), 1240 + 0.1 * m, 74 + 0.01 * m, 148) for m in range(9)]
    rep = report(hourly(D1, 1000, 50, 100), D1, D2, latest=minute, now=at(D2, 0, 8))
    d1, d2 = (r["energy"] for r in rep["rows"])
    assert d1["close_at"] == "2026-09-02T00:00:00" and d1["used"] == 240.0 and d1["flag"] is None
    assert d2 == {"open": 1240.0, "open_at": "2026-09-02T00:00:00", "close": 1240.8,
                  "close_at": "2026-09-02T00:08:00", "used": 0.8, "flag": "in_progress"}
    s = rep["summary"]["energy"]
    assert (s["latest"], s["latest_at"]) == (1240.8, "2026-09-02T00:08:00")
    assert (s["total"], s["days_with_data"], s["days_complete"], s["avg_per_day"]) == \
        (240.8, 2, 1, 240.0)


def test_scada_clock_fast_closes_today_with_exact_midnight_sample() -> None:
    """App 23:58, SCADA đã sang 00:03 hôm sau → hôm nay đóng bằng mẫu đúng 00:00 như ngày thường."""
    rows = hourly(D1, 1000, 50, 100) + [raw(at(D2), 1240, 74, 148)]
    minute = [raw(at(D2) + timedelta(minutes=t), 1240 + 0.5 * t, 74 + 0.01 * t, 148 if t >= 0 else 147)
              for t in range(-7, 4)]
    rep = report(rows, D1, D1, latest=minute, now=at(D1, 23, 58))
    cell = rep["rows"][0]["energy"]
    assert cell["close_at"] == "2026-09-02T00:00:00" and cell["close"] == 1240.0
    assert cell["used"] == 240.0 and cell["flag"] is None
    assert rep["summary"]["energy"]["days_complete"] == 1
    assert rep["summary"]["energy"]["latest_at"] == "2026-09-02T00:03:00"


def test_scada_clock_slow_leaves_yesterday_partial_and_today_empty() -> None:
    """App 00:02, SCADA còn 23:59 hôm trước → hôm qua `partial` (số cuối trong ngày), hôm nay
    `no_data` — không mượn số ngày khác."""
    minute = [raw(at(D1, 23, m), 1230 + 0.15 * m, 73 + 0.015 * m, 147) for m in range(49, 60)]
    rep = report(hourly(D1, 1000, 50, 100), D1, D2, latest=minute, now=at(D2, 0, 2))
    d1, d2 = (r["energy"] for r in rep["rows"])
    assert d1["close_at"] == "2026-09-01T23:59:00" and d1["used"] == 238.85
    assert d1["flag"] == "partial"
    assert d2["flag"] == "no_data" and d2["open"] is None


# ── BQ/ngày + suất tiêu hao chỉ tính ngày đủ số ──

def test_avg_and_intensity_only_count_complete_days() -> None:
    rows = (hourly(D1, 1000, 50, 100)
            + [raw(at(D2, h), 1240 + 10 * h, 74 + h, 148 + h) for h in range(24)]
            + [raw(at(D3))]  # mốc 00:00 ngày 3 trống → ngày 2 `partial`
            + [raw(at(D3, h), 1480 + 10 * h, 98 + h, 196 + 2 * h) for h in range(1, 13)])
    rep = report(rows, D1, D3, now=at(D3, 12))
    assert [r["energy"]["flag"] for r in rep["rows"]] == [None, "partial", "in_progress"]
    assert [r["energy"]["used"] for r in rep["rows"]] == [240.0, 230.0, 110.0]
    s = rep["summary"]["energy"]
    assert (s["total"], s["days_with_data"], s["days_complete"], s["avg_per_day"]) == \
        (580.0, 3, 1, 240.0)
    b = rep["summary"]["bales"]
    assert (b["total"], b["days_complete"], b["avg_per_day"]) == (93, 1, 48.0)
    # Ngày 2 có 230 kWh / 23 bành = 10 — không được kéo lệch suất cả kỳ (chỉ ngày 1: 240 / 48).
    assert [r["kwh_per_bale"] for r in rep["rows"]] == [5.0, None, None]
    assert rep["intensity"] == {"kwh_per_bale": 5.0, "m3_per_bale": 0.5}


def test_fetched_at_and_rows_are_ascending_even_with_unsorted_input() -> None:
    rows = list(reversed(hourly(D1, 1000, 50, 100) + [raw(at(D2), 1240, 74, 148)]))
    rep = report(rows, D1, D1, now=datetime(2026, 9, 30, 8, 0, 0, 123456))
    assert rep["rows"][0]["energy"]["used"] == 240.0 and rep["fetched_at"] == "2026-09-30T08:00:00"
