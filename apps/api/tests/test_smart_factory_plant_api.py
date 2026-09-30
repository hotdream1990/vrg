"""Test API Sơ đồ vận hành (`/api/smart-factory/plant/*`) + gán `layout_key` ở cấu hình nhà máy.

SCADA giả bằng monkeypatch `scada_client.read_latest` (như test_smart_factory_api); `scada_client`
đọc driver thật được thử riêng ở cuối file với `_connect`/`_query` giả (không kết nối gì).
Dữ liệu test (nhà máy `_zz_sf…`, tài khoản `sf_…`) + cache dọn sạch trước/sau test.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime

import pytest

from app.core.db import db_healthy
from app.services import scada_client
from app.services import scada_read_guard as guard
from tests.test_smart_factory_api import _bearer, _cleanup, body, client, setup_users

_db = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")
ADMIN_URL = "/api/smart-factory/admin/factories"
LAYOUT_URL = "/api/smart-factory/plant/layout"
LIVE_URL = "/api/smart-factory/plant/live"
T0, T1 = datetime(2026, 9, 30, 22, 46), datetime(2026, 9, 30, 22, 47)


@pytest.fixture()
def admin_h():
    yield setup_users()
    _cleanup()


def _factory(admin_h: dict, **kw) -> dict:
    res = client.post(ADMIN_URL, json=body(**kw), headers=admin_h)
    assert res.status_code == 200, res.text
    return res.json()["factory"]


def _fake_latest(calls: list):
    def read(factory, tags=None, minutes=10):
        calls.append((factory["id"], tuple(tags or ()), minutes))
        return [(T0, {"MLM1 - Frequence": 40.0, "MLM1 - Running Status": 1, "PM - Power": 199.0}),
                (T1, {"MLM1 - Frequence": 41.5612, "MLM1 - Running Status": None,
                      "PM - Power": 200.7})]
    return read


@_db
def test_layout_key_validated_kept_and_listed(admin_h) -> None:
    assert client.post(ADMIN_URL, json=body(layout_key="khong_co"), headers=admin_h).status_code == 400
    f = _factory(admin_h, layout_key=" phu_rieng ")
    assert f["layout_key"] == "phu_rieng"
    # Form cũ không gửi `layout_key` → sửa nhà máy vẫn GIỮ sơ đồ; gửi null / "" mới là gỡ.
    res = client.put(f"{ADMIN_URL}/{f['id']}", json=body(water_tag="Water_Other"), headers=admin_h)
    assert res.status_code == 200 and res.json()["factory"]["layout_key"] == "phu_rieng"
    listed = client.get("/api/smart-factory/factories", headers=_bearer("sf_cap", "pass123"))
    assert [x["layout_key"] for x in listed.json()["factories"] if x["id"] == f["id"]] == ["phu_rieng"]
    assert client.put(f"{ADMIN_URL}/{f['id']}", json=body(layout_key="../x"),
                      headers=admin_h).status_code == 400
    for cleared in (None, ""):
        res = client.put(f"{ADMIN_URL}/{f['id']}", json=body(layout_key=cleared), headers=admin_h)
        assert res.status_code == 200 and res.json()["factory"]["layout_key"] is None
        client.put(f"{ADMIN_URL}/{f['id']}", json=body(layout_key="phu_rieng"), headers=admin_h)


@_db
def test_layout_endpoint_and_404s(admin_h) -> None:
    h = _bearer("sf_cap", "pass123")
    f = _factory(admin_h, layout_key="phu_rieng")
    res = client.get(LAYOUT_URL, params={"factory_id": f["id"]}, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["factory"] == {"id": f["id"], "name": f["name"]}
    # Chỉ khu đang hiện (3 khu `hidden` giữ trong file, không gửi web).
    assert out["layout"]["key"] == "phu_rieng" and len(out["layout"]["power"]) == 7
    assert [a["key"] for a in out["layout"]["areas"]] == ["khu-mu-vao"]
    assert all("hidden" not in a for a in out["layout"]["areas"])
    plain = _factory(admin_h, name="_zz_sf Không sơ đồ")
    off = _factory(admin_h, name="_zz_sf Tắt", layout_key="phu_rieng", enabled=False)
    for fid in (plain["id"], off["id"], 999999999):
        assert client.get(LAYOUT_URL, params={"factory_id": fid}, headers=h).status_code == 404
        assert client.get(LIVE_URL, params={"factory_id": fid, "area": "khu-mu-vao"},
                          headers=h).status_code == 404


@_db
def test_plant_blocked_without_cap(admin_h) -> None:
    f = _factory(admin_h, layout_key="phu_rieng")
    q = {"factory_id": f["id"], "area": "khu-mu-vao"}
    nocap = _bearer("sf_nocap", "pass123")
    assert client.get(LAYOUT_URL, params=q, headers=nocap).status_code == 403
    assert client.get(LIVE_URL, params=q, headers=nocap).status_code == 403
    assert client.get(LIVE_URL, params=q).status_code == 401


@_db
def test_live_values_rounding_and_cache_per_area(admin_h, monkeypatch) -> None:
    # Nhà máy KHÔNG khai tag điện/nước/bành vẫn xem được sơ đồ (tag lấy từ bố cục).
    f = _factory(admin_h, layout_key="phu_rieng", energy_tags=[], water_tag="", bales_tag=None)
    calls: list = []
    monkeypatch.setattr(scada_client, "read_latest", _fake_latest(calls))
    clock = [5000.0]
    monkeypatch.setattr(guard, "_clock", lambda: clock[0])
    h = _bearer("sf_cap", "pass123")
    q = {"factory_id": f["id"], "area": "khu-mu-vao"}
    res = client.get(LIVE_URL, params=q, headers=h)
    assert res.status_code == 200, res.text
    out = res.json()
    assert set(out) == {"area", "values", "fetched_at"} and out["area"] == "khu-mu-vao"
    v = out["values"]
    assert v["MLM1 - Frequence"] == {"value": 41.56, "at": "2026-09-30T22:47:00"}
    assert v["MLM1 - Running Status"] == {"value": 1, "at": "2026-09-30T22:46:00"}  # dòng cuối CÓ số
    assert v["PM - Power"]["value"] == 200.7
    assert v["CM1 - Main Left Temperature"] == {"value": None, "at": None}
    _, tags, minutes = calls[0]
    # MỘT truy vấn cho mọi khu ĐANG HIỆN; khu ẩn (hầm sấy, đóng gói…) không đọc.
    assert minutes == 1 and set(v) == set(tags)
    assert "Z01 - Champer Temperature" not in tags and "RobotTotalCount" not in tags

    client.get(LIVE_URL, params=q, headers=h)
    assert len(calls) == 1  # cache 5 giây dùng chung
    for hidden in ("vit-tai-ngang", "ham-say", "dong-goi"):  # khu ẩn = không có, không chạm SCADA
        assert client.get(LIVE_URL, params={**q, "area": hidden}, headers=h).status_code == 404
    assert len(calls) == 1
    clock[0] += 5.1
    client.get(LIVE_URL, params=q, headers=h)
    assert len(calls) == 2  # quá 5 giây → đọc lại SCADA

    res = client.get(LIVE_URL, params={**q, "area": "khong-co"}, headers=h)
    assert res.status_code == 404 and len(calls) == 2  # khu lạ không chạm SCADA
    assert client.get(LIVE_URL, params={"factory_id": f["id"]}, headers=h).status_code == 422


@_db
def test_live_scada_error_502_short_for_non_admin(admin_h, monkeypatch) -> None:
    f = _factory(admin_h, layout_key="phu_rieng")

    def boom(factory, tags=None, minutes=10):
        raise scada_client.ScadaError("Tag không tồn tại trong Historian. Chi tiết: Invalid column")
    monkeypatch.setattr(scada_client, "read_latest", boom)
    q = {"factory_id": f["id"], "area": "khu-mu-vao"}
    res = client.get(LIVE_URL, params=q, headers=_bearer("sf_cap", "pass123"))
    assert res.status_code == 502 and "báo quản trị viên" in res.json()["detail"]
    res = client.get(LIVE_URL, params=q, headers=admin_h)
    assert res.status_code == 502 and res.json()["detail"].startswith("Tag không tồn tại")


def test_read_latest_queries_given_tags_with_spaces(monkeypatch) -> None:
    """`read_latest(tags=…)` truy vấn ĐÚNG danh sách tag truyền vào (kể cả tag có dấu cách),
    không đòi nhà máy khai tag điện/nước/bành; cột trả về khớp tag không phân biệt hoa thường."""
    sqls: list[str] = []

    @contextmanager
    def fake_connect(factory):
        yield None, []

    def fake_query(session, factory, sql, params=None):
        sqls.append(sql)
        return [{"DateTime": T1, "mlm1 - frequence": 41.56, "PM - Power": None}]

    monkeypatch.setattr(scada_client, "_connect", fake_connect)
    monkeypatch.setattr(scada_client, "_query", fake_query)
    f = {"linked_server": "INSQL", "energy_tags": [], "water_tag": None, "bales_tag": None}
    rows = scada_client.read_latest(f, ["MLM1 - Frequence", "PM - Power"], minutes=3)
    assert rows == [(T1, {"MLM1 - Frequence": 41.56, "PM - Power": None})]
    assert "[MLM1 - Frequence], [PM - Power]" in sqls[0] and "DateAdd(mi,-3,GetDate())" in sqls[0]
    with pytest.raises(scada_client.ScadaError):  # không truyền tag → vẫn đòi tag đã khai như cũ
        scada_client.read_latest(f)


@_db
def test_admin_layout_options_listed(admin_h) -> None:
    res = client.get("/api/smart-factory/admin/layouts", headers=admin_h)
    assert res.status_code == 200
    assert {"key": "phu_rieng", "label": "Nhà máy Phú Riềng"} in res.json()["layouts"]
    cap_h = _bearer("sf_cap", "pass123")
    assert client.get("/api/smart-factory/admin/layouts", headers=cap_h).status_code == 403
