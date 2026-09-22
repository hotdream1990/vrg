"""Test màn "Chỉ số đơn vị" — cây hai cấp khu vực → đơn vị.

Kiểm đúng những luật dễ làm sai khi GỘP KHU VỰC: sản lượng cộng dồn · giá là bình quân GIA QUYỀN
(không phải trung bình cộng các đơn vị) · tỷ lệ nộp tính lại trên tổng · đơn vị chưa có số vẫn giữ
dòng với ô TRỐNG (không phải 0).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_UNIT
from app.main import app
from app.services import price_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT_A, UNIT_B, UNIT_C = "_zz_sc_a", "_zz_sc_b", "_zz_sc_c"
UNITS = [UNIT_A, UNIT_B, UNIT_C]
REGION = "_zz_sc_region"
D0 = (date.today() - timedelta(days=3)).isoformat()
D1 = (date.today() - timedelta(days=2)).isoformat()
API = "/api/unit-daily/scorecard"


@pytest.fixture(autouse=True)
def _seed_admin():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _price(unit: str, as_of: str, price: float) -> None:
    price_repo.upsert_record({"as_of": as_of, "source": PURCHASE_SOURCE_UNIT, "grade": unit,
                              "contract": "", "price_type": "purchase", "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


def _cleanup(h: dict[str, str]) -> None:
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": UNITS})
        db.execute(text("DELETE FROM fact_price WHERE grade = ANY(:u)"), {"u": UNITS})
    for n in UNITS:
        client.delete(f"/api/member-units/{n}", headers=h)
    client.delete(f"/api/member-regions/{REGION}", headers=h)


@pytest.fixture()
def seeded():
    """1 khu vực · 3 đơn vị: A và B có số (giá khác nhau), C chưa nộp gì."""
    h = _admin()
    _cleanup(h)
    client.post("/api/member-regions", json={"name": REGION}, headers=h)
    for n in UNITS:
        client.post("/api/member-units", json={"name": n}, headers=h)
        client.put(f"/api/member-units/{n}", json={"region": REGION, "set_region": True}, headers=h)
        client.put("/api/unit-daily/plan",
                   json={"year": date.today().year, "company": n, "plan_tonnes": 1000}, headers=h)

    put = lambda body: client.put("/api/unit-daily/report", json=body, headers=h)  # noqa: E731
    # A: 100 tấn @400 rồi 300 tấn @500 → BQ gia quyền của riêng A = 475.
    _price(UNIT_A, D0, 400.0)
    _price(UNIT_A, D1, 500.0)
    put({"kind": "purchase", "company": UNIT_A, "as_of": D0, "fields": {"latex_wet": 100}})
    put({"kind": "purchase", "company": UNIT_A, "as_of": D1, "fields": {"latex_wet": 300}})
    # B: 100 tấn @600 → BQ của riêng B = 600. Khu vực: 250.000/500 = 500 (TB cộng sẽ ra 537,5).
    _price(UNIT_B, D1, 600.0)
    put({"kind": "purchase", "company": UNIT_B, "as_of": D1, "fields": {"latex_wet": 100}})
    # Tồn kho theo chủng loại — nguồn cho bảng chéo đơn vị × chủng loại.
    put({"kind": "consumption", "company": UNIT_A, "as_of": D1,
         "fields": {"stock_warehoused": [{"grade": "SVR 3L", "qty": 100},
                                         {"grade": "SVR 10 / CSR 10", "qty": 200}]}})
    put({"kind": "consumption", "company": UNIT_B, "as_of": D1,
         "fields": {"stock_warehoused": [{"grade": "SVR 3L", "qty": 50}]}})
    yield h
    _cleanup(h)


def _get(h: dict, tab: str = "overview", **params) -> dict:
    params.setdefault("date_from", D0)
    params.setdefault("date_to", D1)
    params.setdefault("regions", REGION)
    res = client.get(API, headers=h, params={"tab": tab, **params})
    assert res.status_code == 200, res.text
    return res.json()


def _region(rep: dict) -> dict:
    return next(g for g in rep["regions"] if g["region"] == REGION)


def _unit(rep: dict, name: str) -> dict:
    return next(u for u in _region(rep)["children"] if u["company"] == name)


def test_tabs_liet_ke_kem_co_loc_chung_loai():
    res = client.get(f"{API}/tabs", headers=_admin())
    assert res.status_code == 200
    tabs = {t["key"]: t for t in res.json()["tabs"]}
    assert set(tabs) == {"overview", "purchase", "consumption", "stock", "compliance"}
    assert tabs["stock"]["axis"] == "as_of"           # tồn kho đi trục ngày chốt
    assert tabs["consumption"]["grade_filter"] == "full"
    assert tabs["purchase"]["grade_filter"] == "partial"   # chỉ áp phần thành phẩm
    assert tabs["compliance"]["grade_filter"] == "none"


def test_cay_hai_cap_giu_ca_don_vi_chua_co_so(seeded):
    rep = _get(seeded, "purchase")
    g = _region(rep)
    assert g["units"] == 3 and g["no_data"] == 1           # C chưa nộp gì
    assert _unit(rep, UNIT_C)["has_data"] is False
    # Ô TRỐNG, tuyệt đối không phải 0 — đơn vị chưa nộp khác đơn vị nộp số 0.
    assert _unit(rep, UNIT_C)["values"]["qty_latex"] is None


def test_san_luong_khu_vuc_cong_don(seeded):
    rep = _get(seeded, "purchase")
    g = _region(rep)
    assert g["values"]["qty_latex"] == pytest.approx(500.0)
    assert (_unit(rep, UNIT_A)["values"]["qty_latex"]
            + _unit(rep, UNIT_B)["values"]["qty_latex"]) == pytest.approx(g["values"]["qty_latex"])


def test_gia_khu_vuc_la_binh_quan_gia_quyen(seeded):
    """Luật dễ sai nhất: KHÔNG lấy trung bình cộng giá của các đơn vị."""
    rep = _get(seeded, "purchase")
    assert _unit(rep, UNIT_A)["values"]["price_latex_avg"] == pytest.approx(475.0)
    assert _unit(rep, UNIT_B)["values"]["price_latex_avg"] == pytest.approx(600.0)
    assert _region(rep)["values"]["price_latex_avg"] == pytest.approx(500.0)   # ≠ 537,5


def test_ty_le_nop_tinh_lai_tren_tong(seeded):
    rep = _get(seeded, "compliance")
    g = _region(rep)["values"]
    assert g["expected"] > 0
    assert g["rate"] == pytest.approx(g["filled"] / g["expected"] * 100)
    assert g["expected"] == g["filled"] + g["no_purchase"] + g["missing"]


def test_tab_ton_kho_khong_cong_don_ky(seeded):
    """Tab tồn kho trả ảnh chụp tại ngày chốt + độ phủ; các tab khác không có độ phủ."""
    stock = _get(seeded, "stock", as_of=D1)
    assert stock["axis"] == "as_of" and stock["as_of"] == D1
    assert stock["coverage"] is not None
    assert _get(seeded, "purchase")["coverage"] is None


def test_ngay_sai_bi_chan(seeded):
    res = client.get(API, headers=seeded,
                     params={"tab": "overview", "date_from": D1, "date_to": D0})
    assert res.status_code == 400
    res = client.get(API, headers=seeded,
                     params={"tab": "khong-co", "date_from": D0, "date_to": D1})
    assert res.status_code == 422


def _by_grade(h: dict, measure: str, **params) -> dict:
    params.setdefault("date_from", D0)
    params.setdefault("date_to", D1)
    params.setdefault("as_of", D1)
    params.setdefault("regions", REGION)
    res = client.get(f"{API}/by-grade", headers=h, params={"measure": measure, **params})
    assert res.status_code == 200, res.text
    return res.json()


def test_bang_cheo_chung_loai_thanh_cot(seeded):
    """Cột = chủng loại, dòng vẫn là cây khu vực → đơn vị."""
    rep = _by_grade(seeded, "stk_total")
    cols = {c["label"]: c["key"] for c in rep["cols"]}
    assert "SVR 3L" in cols and "SVR 10 / CSR 10" in cols
    assert cols["TỔNG"] == "__total"
    g = _region(rep)["values"]
    assert g["SVR 3L"] == pytest.approx(150.0)          # A 100 + B 50
    assert g["SVR 10 / CSR 10"] == pytest.approx(200.0)
    assert _unit(rep, UNIT_A)["values"]["SVR 3L"] == pytest.approx(100.0)
    assert _unit(rep, UNIT_B)["values"]["SVR 10 / CSR 10"] is None   # B không có chủng loại này


def test_bang_cheo_cot_tong_khop_tong_cac_chung_loai(seeded):
    """Cột TỔNG lấy thẳng từ bảng thống kê, phải khớp tổng các cột chủng loại (chỉ số cộng được)."""
    rep = _by_grade(seeded, "stk_total")
    grade_keys = [c["key"] for c in rep["cols"] if c["key"] != "__total"]
    for row in [_region(rep), _unit(rep, UNIT_A), _unit(rep, UNIT_B)]:
        cells = sum(row["values"][k] or 0.0 for k in grade_keys)
        assert cells == pytest.approx(row["values"]["__total"] or 0.0)


def test_bang_cheo_khong_nhan_loc_chung_loai(seeded):
    """Cột đã là chủng loại — truyền thêm `grades` chỉ làm mất cột nên endpoint không nhận."""
    res = client.get(f"{API}/by-grade", headers=seeded,
                     params={"measure": "stk_total", "date_from": D0, "date_to": D1,
                             "grades": "SVR 3L"})
    assert res.status_code == 200
    assert any(c["label"] == "SVR 10 / CSR 10" for c in res.json()["cols"])


def test_bang_cheo_thu_mua_nguyen_lieu_gom_theo_loai_mu(seeded):
    """Mủ nguyên liệu KHÔNG có chủng loại (chốt 22/09/2026): sản lượng gom ở cột "Mủ nước /
    Mủ chén / Mủ dây". Khoá `latex_grades` của bản 0.4.79 còn sót thì bị bỏ qua, không đẻ ra cột."""
    client.put("/api/unit-daily/report", headers=seeded, json={
        "kind": "purchase", "company": UNIT_C, "as_of": D1,
        "fields": {"latex_wet": 20, "latex_grades": [{"grade": "SVR 3L", "qty": 20}]}})
    rep = _by_grade(seeded, "pur_material_qty")
    vals = _region(rep)["values"]
    labels = {c["label"] for c in rep["cols"]}
    assert "Mủ nước" in labels and "SVR 3L" not in labels
    assert vals["Mủ nước"] == pytest.approx(520.0)      # A + B (500) + C (20)
    assert vals["__total"] == pytest.approx(520.0)
