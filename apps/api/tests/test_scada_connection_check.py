"""Test nút «Kiểm tra kết nối» SCADA: giờ máy SQL Server, cảnh báo múi giờ/đồng hồ, số mới nhất
của TỪNG chỉ số (thuần hàm — `scada_client.probe` được monkeypatch)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import scada_client
from app.services import scada_connection_check as cc
from tests.test_scada_daily_meters import regs

F = {"id": 1, "name": "NM thử", "energy_tags": ["R0", "R1", "R2", "R3"], "water_tag": "Water",
     "bales_tag": "Bales", "linked_server": "INSQL"}
#: 15:40:00 giờ VN.
NOW_UTC = datetime(2026, 9, 30, 8, 40, tzinfo=timezone.utc)
ST_OK = "2026-09-30T15:40:12.9179538+07:00"


def test_parse_server_time_drops_fraction_keeps_offset() -> None:
    text, at = cc.parse_server_time(ST_OK)
    assert text == "2026-09-30T15:40:12+07:00"
    assert at == datetime(2026, 9, 30, 8, 40, 12, tzinfo=timezone.utc)
    assert cc.parse_server_time("2026-09-30T08:40:12Z")[0] == "2026-09-30T08:40:12+00:00"
    assert cc.parse_server_time("") is None and cc.parse_server_time("hôm nay") is None


def test_clock_warnings() -> None:
    assert cc.clock_warnings(ST_OK, NOW_UTC) == []
    # Cùng thời điểm tuyệt đối nhưng máy SCADA đặt múi UTC+8 → mốc ngày lệch 1 giờ.
    w = cc.clock_warnings("2026-09-30T16:40:00+08:00", NOW_UTC)
    assert w == ["Múi giờ máy SCADA là UTC+08:00 — chỉ số ngày tính theo giờ Việt Nam (UTC+7) sẽ "
                 "lệch mốc."]
    fast = cc.clock_warnings("2026-09-30T15:50:30+07:00", NOW_UTC)
    assert len(fast) == 1 and fast[0].startswith("Đồng hồ máy SCADA nhanh 10 phút")
    slow = cc.clock_warnings("2026-09-30T15:33:00+07:00", NOW_UTC)
    assert slow[0].startswith("Đồng hồ máy SCADA chậm 7 phút")
    assert cc.clock_warnings("2026-09-30T15:44:59+07:00", NOW_UTC) == []  # ≤ 5 phút: bỏ qua
    assert cc.clock_warnings("", NOW_UTC)[0].startswith("Không đọc được giờ của máy SCADA")


def _probe(monkeypatch, latest: list, server_time: str = ST_OK) -> None:
    monkeypatch.setattr(scada_client, "probe", lambda f: ("Microsoft SQL Server 2016", server_time,
                                                          latest))


def test_values_are_latest_per_metric_not_last_row(monkeypatch) -> None:
    """Dòng cuối thiếu điện (tag trễ) → điện lấy dòng trước; bành không có số → cảnh báo riêng."""
    t1, t2 = datetime(2026, 9, 30, 15, 38), datetime(2026, 9, 30, 15, 39)
    latest = [(t1, {**regs(253614.596), "Water": 12473.5, "Bales": None}),
              (t2, {"R0": None, "R1": None, "R2": None, "R3": None, "Water": 12473.64,
                    "Bales": None})]
    _probe(monkeypatch, latest)
    res = cc.check_connection(F, NOW_UTC)
    assert res["ok"] is True and res["detail"] == "Kết nối thành công"
    assert res["server_time"] == "2026-09-30T15:40:12+07:00"
    assert res["values"] == {"energy_kwh": 253614.596, "water_m3": 12473.64, "bales": None}
    assert res["latest_at"] == "2026-09-30T15:39:00"
    assert res["raw"] == {"R0": 0, "R1": 0, "R2": 3869, "R3": 55812, "Water": 12473.64,
                          "Bales": None}
    assert res["warnings"] == ["Số bành đã khai tag nhưng 10 phút gần nhất không có số — kiểm tra "
                               "tag/thiết bị đo."]


def test_no_values_and_clock_problems_are_warnings(monkeypatch) -> None:
    empty = [(datetime(2026, 9, 30, 15, 39), {"R0": None, "R1": None, "R2": None, "R3": None,
                                               "Water": None, "Bales": None})]
    _probe(monkeypatch, empty, "2026-09-30T17:40:00+09:00")
    res = cc.check_connection(F, NOW_UTC + timedelta(minutes=30))
    assert res["ok"] is True and res["latest_at"] is None
    assert res["values"] == {"energy_kwh": None, "water_m3": None, "bales": None}
    assert len(res["warnings"]) == 3
    assert res["warnings"][0].startswith("Múi giờ máy SCADA là UTC+09:00")
    assert res["warnings"][1].startswith("Đồng hồ máy SCADA chậm 30 phút")
    assert res["warnings"][2] == "10 phút gần nhất Historian không có số của các tag đã khai."


def test_factory_without_tags_and_errors(monkeypatch) -> None:
    _probe(monkeypatch, [])
    res = cc.check_connection({**F, "energy_tags": [], "water_tag": None, "bales_tag": ""},
                              NOW_UTC)
    assert res["detail"] == "Kết nối thành công — nhà máy chưa khai tag nào để đọc số"
    assert res["warnings"] == [] and "values" not in res

    def boom(f):
        raise scada_client.ScadaError("Không kết nối được tới máy chủ 10.0.0.5:1433")
    monkeypatch.setattr(scada_client, "probe", boom)
    assert cc.check_connection(F) == {"ok": False,
                                      "detail": "Không kết nối được tới máy chủ 10.0.0.5:1433"}

    def weird(f):
        raise KeyError("x")
    monkeypatch.setattr(scada_client, "probe", weird)
    assert cc.check_connection(F) == {"ok": False,
                                      "detail": "Lỗi không xác định khi kết nối (KeyError)"}
