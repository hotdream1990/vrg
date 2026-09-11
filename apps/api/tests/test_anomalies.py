"""Test API + cấu hình ngưỡng cho màn "Cảnh báo bất thường" (chỉ ADMIN).

`anomaly_rules.scan()` (luật quét thật) được viết SONG SONG với các file này nên có thể chưa
tồn tại lúc chạy test — router trả 503 gọn thay vì sập; các test liên quan tới quét chấp nhận cả
hai trạng thái (200 khi luật đã có, 503 khi chưa) và chỉ kiểm hình dạng response khi có 200.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.core.permissions import DATA_CAPS
from app.main import app
from app.services import user_repo
from app.services.anomaly_types import THRESHOLDS

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
_SCAN_OK = (200, 503)  # 503 = anomaly_rules.py chưa sẵn sàng (đang viết song song)
_EDITOR = "_zz_anomaly_editor"


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(u: str, p: str) -> dict[str, str]:
    t = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def _admin() -> dict[str, str]:
    return _bearer("admin", "admin")


@pytest.fixture()
def editor_headers():
    """Editor có MỌI quyền dữ liệu (không phải admin) — dùng để chứng minh màn này chỉ-admin."""
    h = _admin()
    client.delete(f"/api/users/{_EDITOR}", headers=h)
    client.post("/api/users", json={
        "username": _EDITOR, "password": "pass123",
        "role": "editor", "permissions": list(DATA_CAPS),
    }, headers=h)
    yield _bearer(_EDITOR, "pass123")
    client.delete(f"/api/users/{_EDITOR}", headers=h)


def test_admin_can_scan() -> None:
    r = client.get("/api/anomalies", headers=_admin())
    assert r.status_code in _SCAN_OK
    if r.status_code == 200:
        body = r.json()
        assert {"date_from", "date_to", "groups", "summary", "thresholds"} <= body.keys()
        assert body["thresholds"].keys() == THRESHOLDS.keys()


def test_editor_with_full_data_caps_still_forbidden(editor_headers) -> None:
    """Đây là màn chỉ-admin: editor dù có mọi quyền dữ liệu (DATA_CAPS) vẫn phải bị 403,
    vì quyền quản trị (`role == admin`) không nằm trong danh sách DATA_CAPS."""
    assert client.get("/api/anomalies", headers=editor_headers).status_code == 403
    assert client.get("/api/anomalies/config", headers=editor_headers).status_code == 403
    assert client.put("/api/anomalies/config", json={"values": {}},
                      headers=editor_headers).status_code == 403
    assert client.get("/api/anomalies/export.xlsx", headers=editor_headers).status_code == 403


def test_config_lists_every_threshold() -> None:
    r = client.get("/api/anomalies/config", headers=_admin())
    assert r.status_code == 200
    body = r.json()
    assert len(body) == len(THRESHOLDS)
    assert {row["key"] for row in body} == THRESHOLDS.keys()
    for row in body:
        assert row["default"] == THRESHOLDS[row["key"]]["default"]
        assert row["label"] and row["hint"]


def test_put_config_roundtrip_then_restore() -> None:
    """Lưu ngưỡng rồi đọc lại đúng giá trị; DB dùng chung nên phải trả nguyên trạng sau test."""
    key = next(iter(THRESHOLDS))
    original = THRESHOLDS[key]["default"]
    h = _admin()
    try:
        assert client.put("/api/anomalies/config", json={"values": {key: original + 1}},
                          headers=h).status_code == 200

        rows = {r["key"]: r for r in client.get("/api/anomalies/config", headers=h).json()}
        assert rows[key]["value"] == original + 1
    finally:
        client.put("/api/anomalies/config", json={"values": {key: original}}, headers=h)

    rows = {r["key"]: r for r in client.get("/api/anomalies/config", headers=h).json()}
    assert rows[key]["value"] == original


def test_put_config_rejects_invalid_values() -> None:
    key = next(iter(THRESHOLDS))
    h = _admin()
    assert client.put("/api/anomalies/config", json={"values": {key: -5}},
                      headers=h).status_code == 400
    assert client.put("/api/anomalies/config", json={"values": {key: "khong-phai-so"}},
                      headers=h).status_code == 400
    # Khoá lạ (không có trong THRESHOLDS) → bỏ qua êm, không phải lỗi của admin.
    r = client.put("/api/anomalies/config", json={"values": {"KHONG_TON_TAI": 5}}, headers=h)
    assert r.status_code == 200 and r.json()["updated"] == 0


def test_export_xlsx_content_type() -> None:
    r = client.get("/api/anomalies/export.xlsx", headers=_admin())
    assert r.status_code in _SCAN_OK
    if r.status_code == 200:
        assert r.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        assert r.content[:2] == b"PK"  # .xlsx là file zip
