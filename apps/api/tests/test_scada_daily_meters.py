"""Test thuật toán chỉ số THEO NGÀY từ mẫu Historian (thuần hàm — không cần SQL Server)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.services import scada_daily_meters as dm

F4 = {"id": 7, "name": "NM thử", "energy_tags": ["R0", "R1", "R2", "R3"],
      "water_tag": "Water", "bales_tag": "Bales"}
D1, D2 = date(2026, 9, 1), date(2026, 9, 2)
NOW_LATER = datetime(2026, 9, 30, 15, 40, 12)  # "hôm nay" ngoài kỳ → mọi ngày là ngày cũ


def at(d: date, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day) + timedelta(hours=hour, minutes=minute)


def regs(kwh: float) -> dict[str, int]:
    wh = int(round(kwh * 1000))
    return {"R0": (wh >> 48) & 0xFFFF, "R1": (wh >> 32) & 0xFFFF,
            "R2": (wh >> 16) & 0xFFFF, "R3": wh & 0xFFFF}


def raw(ts: datetime, kwh: float | None = None, water: float | None = None,
        bales: float | None = None) -> tuple[datetime, dict]:
    vals: dict = {"R0": None, "R1": None, "R2": None, "R3": None} if kwh is None else regs(kwh)
    return ts, {**vals, "Water": water, "Bales": bales}


def hourly(day: date, kwh0: float, water0: float, bales0: float, hours: int = 24) -> list:
    """Mẫu từng giờ của một ngày, mỗi giờ tăng đều 10 kWh · 1 m³ · 2 bành."""
    return [raw(at(day, h), kwh0 + 10 * h, water0 + h, bales0 + 2 * h) for h in range(hours)]


def report(rows: list, d0: date = D1, d1: date = D2, latest: list | None = None,
           now: datetime = NOW_LATER, factory: dict = F4) -> dict:
    return dm.build_report(factory, rows, latest or [], d0, d1, now)


# ── Ghép điện năng ──

def test_combine_energy_matches_customer_formula() -> None:
    r0, r1, r2, r3 = 0, 0, 3869, 55812
    expect = (r3 + r2 * 65536 + r1 * 4294967296 + r0 * 281474976710656) / 1000
    assert dm.combine_energy([r0, r1, r2, r3]) == expect == 253614.596


def test_combine_energy_fixes_negative_register() -> None:
    """Thanh ghi 16-bit bị lưu thành số có dấu (55812 → -9724) vẫn ra đúng kWh."""
    assert dm.combine_energy([0, 0, 3869, -9724]) == dm.combine_energy([0, 0, 3869, 55812])
    assert dm.combine_energy([0.0, 0.0, 3869.0, 55811.6]) == 253614.596  # float → làm tròn trước


def test_combine_energy_missing_register_or_wrong_count() -> None:
    assert dm.combine_energy([0, None, 1, 2]) is None
    assert dm.combine_energy([1, 2, 3]) is None
    assert dm.combine_energy([]) is None
    assert dm.combine_energy([1234.5]) == 1234.5  # 1 tag = đã là kWh


# ── Theo ngày ──

def test_full_data_uses_exact_midnights() -> None:
    rows = hourly(D1, 1000, 50, 100) + hourly(D2, 1240, 74, 148) + [raw(at(D2 + timedelta(1)), 1480, 98, 196)]
    rep = report(rows)
    r1, r2 = rep["rows"]
    assert [r["date"] for r in rep["rows"]] == ["2026-09-01", "2026-09-02"]
    assert r1["energy"] == {"open": 1000.0, "open_at": "2026-09-01T00:00:00", "close": 1240.0,
                            "close_at": "2026-09-02T00:00:00", "used": 240.0, "flag": None}
    assert r1["water"]["used"] == 24.0 and r1["bales"]["used"] == 48
    assert isinstance(r1["bales"]["open"], int)
    assert r2["energy"]["close_at"] == "2026-09-03T00:00:00" and r2["energy"]["flag"] is None
    assert r1["kwh_per_bale"] == 5.0 and r1["m3_per_bale"] == 0.5
    s = rep["summary"]["energy"]
    assert s["total"] == 480.0 and s["avg_per_day"] == 240.0 and s["days_with_data"] == 2
    assert s["days_complete"] == 2
    assert rep["intensity"] == {"kwh_per_bale": 5.0, "m3_per_bale": 0.5}


def test_partial_open_when_midnight_has_no_value() -> None:
    rows = [raw(at(D1, 0)), raw(at(D1, 1)), raw(at(D1, 2), 1020, 52, 104),
            raw(at(D1, 5), 1050, 55, 110), raw(at(D2), 1240, 74, 148)]
    cell = report(rows, D1, D1)["rows"][0]["energy"]
    assert cell["open"] == 1020.0 and cell["open_at"] == "2026-09-01T02:00:00"
    assert cell["close_at"] == "2026-09-02T00:00:00" and cell["used"] == 220.0
    assert cell["flag"] == "partial"


def test_partial_close_never_borrows_next_day() -> None:
    """D+1 00:00 trống → lấy mẫu cuối TRONG ngày D, bỏ qua mẫu D+1 01:00 dù có số."""
    rows = hourly(D1, 1000, 50, 100, hours=22) + [raw(at(D2)), raw(at(D2, 1), 9999, 999, 999)]
    cell = report(rows, D1, D1)["rows"][0]["energy"]
    assert cell["close_at"] == "2026-09-01T21:00:00" and cell["close"] == 1210.0
    assert cell["used"] == 210.0 and cell["flag"] == "partial"


def test_reset_when_close_below_open() -> None:
    rows = hourly(D1, 1000, 50, 100) + [raw(at(D2), 5, 74, 148)]
    rep = report(rows, D1, D1)
    cell = rep["rows"][0]["energy"]
    assert cell["used"] is None and cell["flag"] == "reset"
    assert cell["open"] == 1000.0 and cell["close"] == 5.0
    assert rep["rows"][0]["kwh_per_bale"] is None
    assert rep["summary"]["energy"]["days_with_data"] == 0 and rep["summary"]["energy"]["total"] is None
    assert rep["intensity"]["kwh_per_bale"] is None and rep["intensity"]["m3_per_bale"] == 0.5


def test_no_data_day() -> None:
    rows = [raw(at(D1, h)) for h in range(24)] + [raw(at(D2))]
    cell = report(rows, D1, D1)["rows"][0]["water"]
    assert cell == {"open": None, "open_at": None, "close": None, "close_at": None,
                    "used": None, "flag": "no_data"}


def test_no_samples_at_all_still_returns_every_day() -> None:
    rep = report([], D1, D2)
    assert [r["date"] for r in rep["rows"]] == ["2026-09-01", "2026-09-02"]
    assert all(r[m]["flag"] == "no_data" for r in rep["rows"] for m in ("energy", "water", "bales"))
    assert rep["summary"]["bales"] == {"latest": None, "latest_at": None, "total": None,
                                       "avg_per_day": None, "days_with_data": 0,
                                       "days_complete": 0}


def test_today_closes_with_latest_value() -> None:
    now = at(D2, 15, 40)
    rows = hourly(D1, 1000, 50, 100) + hourly(D2, 1240, 74, 148, hours=16)
    latest = [raw(at(D2, 15, 38), 1394, 89.5, 178), raw(at(D2, 15, 39), 1395.5, 89.6, 179)]
    rep = report(rows, D1, D2, latest=latest, now=now)
    cell = rep["rows"][1]["energy"]
    assert cell["close"] == 1395.5 and cell["close_at"] == "2026-09-02T15:39:00"
    assert cell["used"] == 155.5 and cell["flag"] == "in_progress"
    assert rep["rows"][0]["energy"]["flag"] is None  # hôm qua đóng bằng mốc 00:00 hôm nay
    s = rep["summary"]["energy"]
    assert s["latest"] == 1395.5 and s["latest_at"] == "2026-09-02T15:39:00"
    assert rep["summary"]["bales"]["latest"] == 179
    assert rep["fetched_at"] == "2026-09-02T15:40:00"


def test_today_without_latest_uses_last_hourly_sample() -> None:
    now = at(D2, 9, 5)
    rows = [raw(at(D2, 0)), raw(at(D2, 3), 1270, 77, 154), raw(at(D2, 9), 1330, 83, 166)]
    cell = report(rows, D2, D2, now=now)["rows"][0]["energy"]
    assert cell["open_at"] == "2026-09-02T03:00:00" and cell["close_at"] == "2026-09-02T09:00:00"
    assert cell["flag"] == "in_progress"  # in_progress thắng partial


def test_today_ignores_latest_older_than_open() -> None:
    now = at(D2, 0, 5)
    rows = [raw(at(D2, 0), 1240, 74, 148)]
    latest = [raw(at(D1, 23, 58), 1239, 73.9, 147)]
    cell = report(rows, D2, D2, latest=latest, now=now)["rows"][0]["energy"]
    assert cell["close"] == 1240.0 and cell["used"] == 0.0 and cell["flag"] == "in_progress"


def test_reset_beats_in_progress() -> None:
    now = at(D2, 10)
    rows = [raw(at(D2, 0), 1240, 74, 148)]
    latest = [raw(at(D2, 9, 59), 3, 75, 150)]
    cell = report(rows, D2, D2, latest=latest, now=now)["rows"][0]["energy"]
    assert cell["flag"] == "reset" and cell["used"] is None


def test_single_energy_tag_and_missing_tags() -> None:
    f = {"id": 2, "name": "NM 1 tag", "energy_tags": ["kWh_Total"], "water_tag": None,
         "bales_tag": ""}
    assert dm.factory_metrics(f) == ["energy"]
    rows = [(at(D1), {"kWh_Total": 500.25}), (at(D2), {"kWh_Total": 800.5})]
    rep = dm.build_report(f, rows, [], D1, D1, NOW_LATER)
    assert [m["key"] for m in rep["metrics"]] == ["energy"]
    row = rep["rows"][0]
    assert set(row) == {"date", "energy", "kwh_per_bale", "m3_per_bale"}
    assert row["energy"]["used"] == 300.25 and row["kwh_per_bale"] is None
    assert rep["intensity"] == {"kwh_per_bale": None, "m3_per_bale": None}


def test_tag_lookup_is_case_insensitive() -> None:
    f = {"id": 3, "name": "NM", "energy_tags": [], "water_tag": "Water_TotalVolume",
         "bales_tag": None}
    rows = [(at(D1), {"WATER_TOTALVOLUME": 10.0}), (at(D2), {"WATER_TOTALVOLUME": 12.5})]
    assert dm.build_report(f, rows, [], D1, D1, NOW_LATER)["rows"][0]["water"]["used"] == 2.5


def test_zero_bales_gives_null_ratio_and_intensity_only_counts_paired_days() -> None:
    rows = (hourly(D1, 1000, 50, 100) + [raw(at(D2, h), 1240 + 10 * h, 74 + h, 148) for h in range(24)]
            + [raw(at(D2 + timedelta(1)), 1480, 98, 148)])
    rep = report(rows)
    assert rep["rows"][1]["bales"]["used"] == 0 and rep["rows"][1]["kwh_per_bale"] is None
    # Ngày 2 có điện nhưng 0 bành → vẫn cộng (cả hai có used): 480 kWh / 48 bành.
    assert rep["intensity"]["kwh_per_bale"] == 10.0


def test_metric_labels_and_units() -> None:
    rep = report([], D1, D1)
    assert rep["metrics"] == [{"key": "energy", "label": "Điện năng", "unit": "kWh"},
                              {"key": "water", "label": "Nước", "unit": "m³"},
                              {"key": "bales", "label": "Số bành", "unit": "bành"}]
    assert rep["factory"] == {"id": 7, "name": "NM thử"}
    assert rep["date_from"] == "2026-09-01" and rep["date_to"] == "2026-09-01"
