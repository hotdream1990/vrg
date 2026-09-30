"""Test chặn sau review 30/09/2026 của `/meters/daily`: 502 theo vai trò + ghi log, 429 khi nhà máy
đang có lượt đọc SCADA khác, 400 nhà máy chưa khai tag, nhãn trang Lịch sử truy cập.

SCADA giả bằng monkeypatch (như test_smart_factory_api); dữ liệu test + cache dọn sạch sau test.
"""

from __future__ import annotations

import logging

import pytest

from app.core.access_meta import normalize_path, page_label
from app.core.db import db_healthy
from app.services import scada_client
from app.services import scada_read_guard as guard
from tests.test_smart_factory_api import PREFIX, _bearer, _cleanup, _fake_reader, body, client
from tests.test_smart_factory_api import setup_users

_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
URL = "/api/smart-factory/meters/daily"
ADMIN_URL = "/api/smart-factory/admin/factories"


@pytest.fixture()
def admin_h():
    yield setup_users()
    _cleanup()


def _factory(admin_h: dict, **kw) -> dict:
    res = client.post(ADMIN_URL, json=body(**kw), headers=admin_h)
    assert res.status_code == 200, res.text
    return res.json()["factory"]


def test_access_log_labels_for_smart_factory_pages() -> None:
    assert page_label(normalize_path("/nha-may-thong-minh/chi-so?x=1")) == \
        "Nhà máy thông minh — Giám sát chỉ số"
    # Cấu hình SCADA là tab trong Cấu hình hệ thống — route cũ chỉ còn chuyển hướng.
    assert page_label(normalize_path("/quan-tri/cau-hinh")) != "/quan-tri/cau-hinh"


@_db
def test_scada_error_502_full_detail_for_admin_short_for_others(admin_h, monkeypatch, caplog) -> None:
    f = _factory(admin_h)
    detail = "Sai tài khoản hoặc mật khẩu SQL Server (tài khoản «scada_ro»). Chi tiết: Login failed"

    def boom(factory, start, end):
        raise scada_client.ScadaError(detail)
    monkeypatch.setattr(scada_client, "read_meters", boom)
    q = f"?factory_id={f['id']}&date_from=2026-09-01&date_to=2026-09-02"
    short = (f"Chưa đọc được số liệu SCADA của nhà máy «{f['name']}» — đã ghi nhận, "
             "vui lòng báo quản trị viên.")
    with caplog.at_level(logging.WARNING, logger="vrg.scada"):
        for path in (URL, f"{URL}.xlsx"):
            res = client.get(path + q, headers=_bearer("sf_cap", "pass123"))
            assert res.status_code == 502 and res.json()["detail"] == short
            res = client.get(path + q, headers=admin_h)
            assert res.status_code == 502 and res.json()["detail"] == detail
    # Lỗi không cache: đọc lại thật mỗi lần; log có tên nhà máy + chi tiết, KHÔNG có mật khẩu.
    logs = [r.getMessage() for r in caplog.records if r.name == "vrg.scada"]
    assert len(logs) == 4 and all(f["name"] in m and detail in m for m in logs)
    assert not any("S3cret" in m for m in logs)


@_db
def test_busy_factory_429_and_other_factory_unaffected(admin_h, monkeypatch) -> None:
    f = _factory(admin_h)
    g = _factory(admin_h, name=f"{PREFIX} Lộc Ninh")
    calls: list = []
    monkeypatch.setattr(scada_client, "read_meters", _fake_reader(calls))
    monkeypatch.setattr(guard, "LOCK_WAIT_S", 0.05)
    h = _bearer("sf_cap", "pass123")
    q = "&date_from=2026-09-01&date_to=2026-09-02"
    lock = guard.factory_lock(f["id"])
    assert lock.acquire(timeout=1)  # giả một lượt đọc SCADA khác đang chạy lâu
    try:
        res = client.get(f"{URL}?factory_id={f['id']}{q}", headers=h)
        assert res.status_code == 429 and res.json()["detail"] == guard.BUSY_MESSAGE
        assert calls == []
        assert client.get(f"{URL}?factory_id={g['id']}{q}", headers=h).status_code == 200
    finally:
        lock.release()
    assert client.get(f"{URL}?factory_id={f['id']}{q}", headers=h).status_code == 200


@_db
def test_cache_expires_when_factory_config_changes(admin_h, monkeypatch) -> None:
    f = _factory(admin_h)
    calls: list = []
    monkeypatch.setattr(scada_client, "read_meters", _fake_reader(calls))
    h = _bearer("sf_cap", "pass123")
    q = f"?factory_id={f['id']}&date_from=2026-09-01&date_to=2026-09-02"
    assert client.get(URL + q, headers=h).status_code == 200
    assert client.get(URL + q, headers=h).status_code == 200
    assert len(calls) == 1
    # Admin sửa cấu hình → updated_at đổi → khoá cache mới → đọc lại SCADA.
    client.put(f"{ADMIN_URL}/{f['id']}", json=body(water_tag="Water_Other"), headers=admin_h)
    assert client.get(URL + q, headers=h).status_code == 200
    assert len(calls) == 2


@_db
def test_factory_without_tags_is_400_without_touching_scada(admin_h, monkeypatch) -> None:
    f = _factory(admin_h, energy_tags=[], water_tag="", bales_tag=None)
    calls: list = []
    monkeypatch.setattr(scada_client, "read_meters", _fake_reader(calls))
    for path in (URL, f"{URL}.xlsx"):
        res = client.get(f"{path}?factory_id={f['id']}", headers=_bearer("sf_cap", "pass123"))
        assert res.status_code == 400
        assert res.json()["detail"] == ("Nhà máy chưa khai tag nào — admin vào Cấu hình kết nối "
                                        "SCADA để khai.")
    assert calls == []


def test_admin_day_samples_and_tag_search(admin_h, monkeypatch) -> None:
    """Mẫu theo giờ của MỘT ngày (gồm mốc D+1 00:00) + tìm tag có tham số — chỉ admin."""
    f = _factory(admin_h)
    calls: list = []
    monkeypatch.setattr(scada_client, "read_meters", _fake_reader(calls))
    res = client.get(f"{ADMIN_URL}/{f['id']}/samples", params={"date": "2026-09-01"}, headers=admin_h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert [m["key"] for m in out["metrics"]] == ["energy", "water", "bales"]
    assert out["samples"][0]["at"] == "2026-09-01T00:00:00"
    assert out["samples"][-1]["at"] == "2026-09-02T00:00:00" and len(out["samples"]) == 25
    assert out["samples"][1]["values"]["water"] == 51.0
    seen: list = []
    monkeypatch.setattr(scada_client, "search_tags",
                        lambda fac, q: seen.append(q) or [{"tag": "RobotTotalCount", "description": ""}])
    res = client.get(f"{ADMIN_URL}/{f['id']}/tags", params={"q": "Robot"}, headers=admin_h)
    assert res.json() == {"tags": [{"tag": "RobotTotalCount", "description": ""}]} and seen == ["Robot"]
    assert client.get(f"{ADMIN_URL}/{f['id']}/tags", params={"q": "R"}, headers=admin_h).status_code == 400
    bad = client.get(f"{ADMIN_URL}/{f['id']}/samples", params={"date": "2999-01-01"}, headers=admin_h)
    assert bad.status_code == 400
    cap_h = _bearer("sf_cap", "pass123")
    assert client.get(f"{ADMIN_URL}/{f['id']}/tags", params={"q": "Robot"},
                      headers=cap_h).status_code == 403


def test_tag_search_sql_is_parameterized() -> None:
    """Từ khoá đi qua tham số %s của pymssql, không bao giờ ghép vào chuỗi SQL."""
    assert scada_client.TAG_SEARCH_SQL.count("%s") == 2 and "'" not in scada_client.TAG_SEARCH_SQL


def test_live_meters_returns_latest_cumulative_and_is_cached(admin_h, monkeypatch) -> None:
    """Số lũy kế thời gian thực: số MỚI NHẤT có giá trị của từng chỉ số; cache ngắn dùng chung."""
    from datetime import datetime
    f = _factory(admin_h)
    calls: list = []

    def latest(factory):
        calls.append(factory["id"])
        return [(datetime(2026, 9, 30, 21, 50), {"PM_EnergyReal0": 0, "PM_EnergyReal1": 0,
                                                 "PM_EnergyReal2": 3873, "PM_EnergyReal3": 23663,
                                                 "Water_TotalVolume": 12482.313, "Bales_Count": None}),
                (datetime(2026, 9, 30, 21, 49), {"Bales_Count": 21459.0})]

    monkeypatch.setattr(scada_client, "read_latest", latest)
    res = client.get("/api/smart-factory/meters/live", params={"factory_id": f["id"]}, headers=admin_h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["values"]["energy"] == {"value": 253844.591, "at": "2026-09-30T21:50:00"}
    assert out["values"]["water"]["value"] == 12482.313
    assert out["values"]["bales"] == {"value": 21459, "at": "2026-09-30T21:49:00"}
    client.get("/api/smart-factory/meters/live", params={"factory_id": f["id"]}, headers=admin_h)
    assert calls == [f["id"]]  # lần 2 trong cache
    nocap = _bearer("sf_nocap", "pass123")
    assert client.get("/api/smart-factory/meters/live", params={"factory_id": f["id"]},
                      headers=nocap).status_code == 403
