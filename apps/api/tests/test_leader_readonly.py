"""Test LÃNH ĐẠO ĐƠN VỊ xem được số liệu đơn vị mình — và KHÔNG ghi được gì.

Hai điều phải khoá chặt:
1. Phạm vi: lãnh đạo chỉ thấy đơn vị được gán (không thấy đơn vị khác, không thấy số mức Tập đoàn).
2. Chỉ xem: MỌI method ghi đều 403, kể cả endpoint thêm sau này (chặn ở dependency theo method).
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

UNIT_A, UNIT_B = "_zz_ld_don_vi_a", "_zz_ld_don_vi_b"
ACCOUNTS = ("ld_lead_a", "ld_mem_a")
TODAY = date.today().isoformat()
DEMAND_URL = "/api/member/market-demand/items"


def _demand(company: str, customer: str = "Khách thử") -> dict:
    return {"company": company, "as_of": TODAY, "customer": customer, "grade": "LATEX"}


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(username: str, password: str) -> dict[str, str]:
    token = client.post("/api/auth/login",
                        json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin() -> dict[str, str]:
    return _bearer("admin", "admin")


@pytest.fixture
def env():
    """2 đơn vị + 1 lãnh đạo (gán đơn vị A) + 1 tài khoản nhập liệu của đơn vị A."""
    h = _admin()
    for u in ACCOUNTS:
        client.delete(f"/api/users/{u}", headers=h)
    for unit in (UNIT_A, UNIT_B):
        client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ld_lead_a", "password": "pass123",
                                    "role": "leader", "member_units": [UNIT_A]}, headers=h)
    client.post("/api/users", json={"username": "ld_mem_a", "password": "pass123",
                                    "role": "member", "member_units": [UNIT_A]}, headers=h)
    yield {"admin": h, "lead": _bearer("ld_lead_a", "pass123"), "mem": _bearer("ld_mem_a", "pass123")}
    for u in ACCOUNTS:
        client.delete(f"/api/users/{u}", headers=h)
    for unit in (UNIT_A, UNIT_B):
        client.delete(f"/api/member-units/{unit}", headers=h)


def test_lanh_dao_xem_duoc_so_lieu_don_vi_minh(env) -> None:
    """Các màn số liệu của đơn vị đều mở cho lãnh đạo, và chỉ trả đơn vị được gán."""
    lead = env["lead"]
    for url in ("/api/member/prices?days=30",
                f"/api/member/daily-report?kind=purchase&as_of={TODAY}",
                f"/api/member/daily-report?kind=consumption&as_of={TODAY}",
                DEMAND_URL,
                f"/api/member/plan?year={date.today().year}",
                "/api/member/stock-contracts"):
        r = client.get(url, headers=lead)
        assert r.status_code == 200, f"{url} → {r.status_code} {r.text[:200]}"
        units = r.json().get("units")
        if units is not None:
            assert units == [UNIT_A], f"{url} lộ đơn vị khác: {units}"


def test_lanh_dao_thay_dung_hop_dong_cua_don_vi_minh(env) -> None:
    """Màn hợp đồng dùng chung: lãnh đạo vào được, phạm vi ép về đơn vị của mình."""
    lead = env["lead"]
    meta = client.get("/api/sales-contracts/meta", headers=lead)
    assert meta.status_code == 200 and meta.json()["units"] == [UNIT_A]
    assert client.get("/api/customers", headers=lead).status_code == 200
    assert client.get("/api/master-contracts", headers=lead).status_code == 200
    assert client.get("/api/sales-contracts", headers=lead).status_code == 200


def test_lanh_dao_khong_ghi_duoc_gi(env) -> None:
    """Mọi thao tác GHI đều 403 — nhập liệu là việc của tài khoản `member` của đơn vị."""
    lead = env["lead"]
    writes = [
        ("put", "/api/member/prices",
         {"company": UNIT_A, "as_of": TODAY, "price_type": "purchase", "price": 300}),
        ("delete", f"/api/member/prices?company={UNIT_A}&as_of={TODAY}&price_type=purchase", None),
        ("put", DEMAND_URL, _demand(UNIT_A)),
        ("delete", f"{DEMAND_URL}/1", None),
        ("put", "/api/member/daily-report",
         {"kind": "purchase", "as_of": TODAY, "company": UNIT_A, "fields": {"latex_wet": 1}}),
        ("put", "/api/member/plan",
         {"year": date.today().year, "company": UNIT_A, "plan_tonnes": 100}),
        ("put", "/api/member/stock-contracts",
         {"company": UNIT_A, "grade": "SVR 10", "qty": 1, "start_date": TODAY}),
        ("put", "/api/customers", {"company": UNIT_A, "name": "Khách thử"}),
    ]
    for method, url, body in writes:
        r = getattr(client, method)(url, headers=lead, **({"json": body} if body else {}))
        assert r.status_code == 403, f"{method.upper()} {url} → {r.status_code} (đáng lẽ 403)"

    # Cùng thao tác đó, tài khoản NHẬP LIỆU của chính đơn vị vẫn làm được → hàng rào đúng chỗ.
    res = client.put(DEMAND_URL, json=_demand(UNIT_A, "đơn vị nhập"), headers=env["mem"])
    assert res.status_code == 200, res.text
    assert client.delete(f"{DEMAND_URL}/{res.json()['item']['id']}", headers=env["mem"]).status_code == 200


def test_lanh_dao_khong_thay_don_vi_khac(env) -> None:
    """Đơn vị B không thuộc tài khoản → không đọc, không ghi."""
    lead = env["lead"]
    demand = client.get(DEMAND_URL, headers=lead).json()
    assert UNIT_B not in demand["units"] and all(x["company"] != UNIT_B for x in demand["items"])
    # Endpoint của chuyên viên (mọi đơn vị) vẫn chặn lãnh đạo.
    assert client.get("/api/market-demand/items", headers=lead).status_code == 403
    assert client.get(f"/api/unit-daily/day?kind=purchase&as_of={TODAY}",
                      headers=lead).status_code == 403


def test_tai_khoan_don_vi_khong_doc_duoc_so_muc_tap_doan(env) -> None:
    """`/api/series` chia được theo TỪNG đơn vị → chặn cả lãnh đạo lẫn tài khoản nhập liệu.

    Trước đây chỉ gác đăng nhập, nên một đơn vị gọi thẳng API là đọc được sản lượng đơn vị khác.
    """
    for who in ("lead", "mem"):
        assert client.get("/api/series/purchase-volume?group_by=company",
                          headers=env[who]).status_code == 403
    assert client.get("/api/series/purchase-volume?group_by=company",
                      headers=env["admin"]).status_code == 200


def test_lanh_dao_khong_vao_duoc_hop_thu_cua_nguoi_khac_va_van_giu_ho_tro(env) -> None:
    """Mở thêm quyền xem số liệu KHÔNG được làm hỏng hộp thư Hỗ trợ của lãnh đạo."""
    ctx = client.get("/api/support/context", headers=env["lead"])
    assert ctx.status_code == 200 and ctx.json()["units"] == [UNIT_A]
    # Tài khoản nhập liệu vẫn KHÔNG vào hộp thư (hộp thư chỉ dành cho lãnh đạo).
    assert client.get("/api/support/context", headers=env["mem"]).status_code == 403


def test_lanh_dao_khong_xac_nhan_chot_so_lieu_duoc(env) -> None:
    """Chốt số liệu là việc của ĐƠN VỊ NHẬP LIỆU — lãnh đạo không bấm xác nhận thay được.

    Phải gửi body HỢP LỆ mới kết luận được: thiếu trường thì FastAPI trả 422 ngay từ khâu kiểm
    dữ liệu, chưa chạm tới hàng rào quyền.
    """
    h = env["admin"]
    rnd = client.put("/api/data-lock/rounds", json={"lock_date": TODAY, "note": "zz audit"}, headers=h)
    assert rnd.status_code == 200, rnd.text[:200]
    round_id = rnd.json()["round"]["id"] if "round" in rnd.json() else rnd.json()["id"]
    try:
        r = client.post("/api/data-lock/confirm",
                        json={"round_id": round_id, "company": UNIT_A}, headers=env["lead"])
        assert r.status_code == 403, f"lãnh đạo chốt được số liệu → {r.status_code} {r.text[:200]}"
    finally:
        client.delete(f"/api/data-lock/rounds/{round_id}", headers=h)


def test_lanh_dao_khong_nhap_excel_duoc_ke_ca_khi_bat_tinh_nang(env, monkeypatch) -> None:
    """Nhập Excel đang TẮT nên trả 503 — bật lên thì hàng rào quyền phải chặn, không phải 503 che."""
    monkeypatch.setattr("app.core.feature_flags.EXCEL_IMPORT_ENABLED", True)
    for url in ("/api/member/import/preview", "/api/member/import/commit"):
        r = client.post(url, json={"kind": "purchase", "rows": []}, headers=env["lead"])
        assert r.status_code == 403, f"{url} → {r.status_code} {r.text[:200]}"
    # Tài khoản nhập liệu thì KHÔNG bị chặn quyền (qua được hàng rào, có thể trượt vì dữ liệu).
    assert client.post("/api/member/import/preview", json={"kind": "purchase", "rows": []},
                       headers=env["mem"]).status_code != 403


def test_khong_lo_don_vi_khac_qua_bat_ky_endpoint_nao(env) -> None:
    """Quét nội dung MỌI endpoint GET lãnh đạo vào được — không được dính dấu vết của đơn vị B.

    Đây là lưới an toàn cho những chỗ trả "danh mục dùng chung" (kế hoạch năm, loại tiền theo đơn
    vị…): số liệu chính thì scope đúng, nhưng mấy danh mục kèm theo rất dễ trả nguyên si cả Tập đoàn.
    """
    h, lead = env["admin"], env["lead"]
    # Mồi số liệu cho đơn vị B qua tài khoản nhập liệu của chính B.
    client.post("/api/users", json={"username": "ld_mem_b", "password": "pass123",
                                    "role": "member", "member_units": [UNIT_B]}, headers=h)
    mem_b = _bearer("ld_mem_b", "pass123")
    secret_demand = client.put(DEMAND_URL, json=_demand(UNIT_B, "BIMATCUADONVIB"), headers=mem_b)
    assert secret_demand.status_code == 200, secret_demand.text
    client.put("/api/member/plan",
               json={"year": date.today().year, "company": UNIT_B, "plan_tonnes": 4321}, headers=mem_b)
    client.put("/api/customers", json={"company": UNIT_B, "name": "KHACHHANGRIENGCUAB"}, headers=mem_b)
    try:
        urls = [
            f"/api/member/daily-report?kind=purchase&as_of={TODAY}",
            f"/api/member/daily-report?kind=consumption&as_of={TODAY}",
            "/api/member/daily-report/timeline?kind=purchase&days=30",
            DEMAND_URL,
            f"/api/member/plan?year={date.today().year}",
            "/api/member/prices?days=30",
            "/api/member/stock-contracts",
            "/api/member/checklist",
            "/api/customers",
            "/api/master-contracts",
            "/api/sales-contracts",
            "/api/sales-contracts/meta",
            f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}",
            f"/api/sales-contracts/undelivered?as_of={TODAY}",
        ]
        for url in urls:
            r = client.get(url, headers=lead)
            assert r.status_code == 200, f"{url} → {r.status_code}"
            for secret in (UNIT_B, "BIMATCUADONVIB", "KHACHHANGRIENGCUAB"):
                assert secret not in r.text, f"{url} lộ dấu vết đơn vị khác: {secret}"
    finally:
        client.delete(f"{DEMAND_URL}/{secret_demand.json()['item']['id']}", headers=mem_b)
        client.delete("/api/users/ld_mem_b", headers=h)


def test_tai_khoan_don_vi_bi_chan_khoi_so_lieu_muc_tap_doan(env) -> None:
    """Danh mục + số liệu mức Tập đoàn (có phần chia theo TỪNG đơn vị) chặn cả 2 vai trò đơn vị."""
    hq_only = [
        "/api/member-units", "/api/member-regions", "/api/prices/purchase-sheet",
        "/api/prices/board", "/api/market-quote/meta", "/api/floor", "/api/inventory",
    ]
    for who in ("lead", "mem"):
        for url in hq_only:
            assert client.get(url, headers=env[who]).status_code == 403, f"{who} vào được {url}"
    # Tỷ giá VCB vẫn phải mở: biểu Thu mua của chính đơn vị dùng để quy đổi.
    assert client.get("/api/market-quote/vcb-rate", headers=env["mem"]).status_code == 200
