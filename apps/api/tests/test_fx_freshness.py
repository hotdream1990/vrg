"""Test kiểm độ tươi tỷ giá (services/fx_freshness.py) — sự cố 03–13/09/2026 JPY/CNY/THB chết im.

Phần lõi là hàm thuần (không DB). Phần đọc DB/HTTP chỉ ĐỌC — không ghi gì vào DB dev.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.core.market_meta import FX_PAIRS
from app.core.security import create_access_token
from app.services import fx_freshness as f

FRI, SAT, SUN, MON = date(2026, 9, 11), date(2026, 9, 12), date(2026, 9, 13), date(2026, 9, 14)


def test_monday_morning_with_friday_close_is_not_stale() -> None:
    """x-rates có close ngày D từ sáng D+1 → sáng thứ Hai mới có số thứ Sáu là bình thường."""
    assert f.business_days_after(FRI, MON) == 1
    assert f.find_stale({p: FRI for p in FX_PAIRS}, MON, 3) == []


def test_weekend_adds_no_business_days() -> None:
    assert f.business_days_after(FRI, SAT) == 0
    assert f.business_days_after(FRI, SUN) == 0
    assert f.business_days_after(SUN, SUN) == 0
    assert f.business_days_after(MON, FRI) == 0  # hôm nay trước ngày mới nhất → không âm


def test_data_from_0209_checked_on_1309_is_stale_7_sessions() -> None:
    """Đúng ca thật: số dừng ở thứ Tư 02/09, xét Chủ nhật 13/09 → trễ 7 phiên (03,04,07…11)."""
    latest = {p: date(2026, 9, 2) for p in ("USD/JPY", "USD/CNY", "USD/THB")}
    latest |= {"USD/MYR": FRI, "USD/VND (Mua)": SUN, "USD/VND (Bán)": SUN}
    stale = f.find_stale(latest, SUN, 3)
    assert [s["pair"] for s in stale] == ["USD/JPY", "USD/CNY", "USD/THB"]
    assert all(s["lag"] == 7 and s["latest"] == "2026-09-02" for s in stale)
    assert f.describe(stale[:1]) == "USD/JPY 02/09 (trễ 7 phiên)"


def test_threshold_boundary_and_long_ranges() -> None:
    wed = date(2026, 9, 9)
    assert f.business_days_after(date(2026, 9, 4), wed) == 3            # T6 → T4 tuần sau
    assert f.find_stale({"USD/JPY": date(2026, 9, 4)}, wed, 3, ["USD/JPY"])[0]["lag"] == 3
    assert f.find_stale({"USD/JPY": date(2026, 9, 7)}, wed, 3, ["USD/JPY"]) == []  # trễ 2
    assert f.business_days_after(date(2026, 8, 1), date(2026, 9, 1)) == 22  # 21 ngày T8 + 01/09


def test_missing_pair_is_reported() -> None:
    stale = f.find_stale({}, SUN, 3, ["USD/THB"])
    assert stale == [{"pair": "USD/THB", "latest": None, "lag": None}]
    assert f.describe(stale) == "USD/THB chưa có dữ liệu"


@pytest.mark.parametrize(("raw", "expected"), [
    (None, 3), ("", 3), ("abc", 3), ("0", 3), ("-2", 3), (" 5 ", 5), ("1", 1),
])
def test_parse_threshold(raw: str | None, expected: int) -> None:
    assert f.parse_threshold(raw) == expected


_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")


@_db
def test_db_read_returns_known_pairs_only() -> None:
    dates = f.latest_dates()
    assert set(dates) <= set(FX_PAIRS)
    assert isinstance(f.stale_pairs(), list)


@_db
def test_fx_health_endpoint_requires_login_and_returns_shape() -> None:
    from app.main import app
    from app.services import user_repo

    user_repo.seed_admin()
    client = TestClient(app)
    assert client.get("/api/prices/fx-health").status_code == 401
    r = client.get("/api/prices/fx-health",
                   headers={"Authorization": f"Bearer {create_access_token('admin')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"stale", "checked_at", "threshold"}
    assert body["threshold"] >= 1
