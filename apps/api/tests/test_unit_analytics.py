"""Test màn Thống kê số liệu đơn vị nhập (thu mua · tiêu thụ · tồn kho · tình trạng nộp).

Kiểm các quy tắc dễ sai nhất: bình quân GIA QUYỀN (không phải trung bình cộng), tồn kho lấy
THỜI ĐIỂM cuối kỳ (không cộng dồn), dòng USD thiếu tỷ giá bị loại khỏi doanh thu + có cảnh báo,
và bộ lọc theo khu vực / chủng loại / loại HĐ / hình thức / nguồn mủ.
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
UNIT_A, UNIT_B = "_zz_an_a", "_zz_an_b"
REGION = "_zz_an_region"
D0 = (date.today() - timedelta(days=3)).isoformat()
D1 = (date.today() - timedelta(days=2)).isoformat()
API = "/api/unit-daily/analytics"


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login", json={"username": "admin", "password": "admin"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _price(unit: str, as_of: str, price_type: str, price: float) -> None:
    """Giá ĐƠN VỊ tự khai — lớp mà màn Thống kê thu mua đọc (xem test_purchase_price_layers)."""
    price_repo.upsert_record({"as_of": as_of, "source": PURCHASE_SOURCE_UNIT, "grade": unit, "contract": "",
                              "price_type": price_type, "price": price,
                              "currency": "VND", "unit": "đồng/độ TSC"})


def _customer(h: dict[str, str], company: str) -> int:
    """Khách hàng của đơn vị (tạo nếu chưa có) — hợp đồng mẹ bắt buộc gán khách."""
    made = client.put("/api/customers", json={"company": company, "name": f"KH {company}"},
                      headers=h).json().get("id")
    # Danh sách khách phân trang ở server → phải LỌC theo đơn vị, không quét trang đầu
    # (DB dev có sẵn hàng trăm khách, khách của đơn vị test không nằm trong trang 1).
    return made if made is not None else next(
        c["id"] for c in client.get(f"/api/customers?company={company}", headers=h).json()["items"]
        if c["company"] == company)


_MASTERS: dict[str, int] = {}


def _master_for(h: dict[str, str], company: str) -> int:
    """Hồ sơ hợp đồng mẹ dùng chung cho mọi HĐ dài hạn của một đơn vị (lập một lần)."""
    if company not in _MASTERS:
        _MASTERS[company] = client.put("/api/master-contracts", headers=h, json={
            "company": company, "code": f"HS-{company[-6:]}", "master_type": "long_term",
            "customer_id": _customer(h, company),
            "lines": [{"grade": "SVR 3L"}]}).json()["master"]["id"]
    return _MASTERS[company]


def _deliver(h: dict[str, str], company: str, code: str, day: str, ctype: str, channel: str,
             grade: str, qty: float, price: float, ccy: str = "VND",
             fx: float | None = None) -> None:
    """1 hợp đồng giao-1-lần ĐÃ GIAO trong ngày `day` — nguồn tiêu thụ của cơ chế mới.

    HĐ dài hạn BẮT BUỘC thuộc một hợp đồng mẹ (chốt 24/08/2026) nên helper tự lập sẵn hồ sơ cho
    đơn vị đó rồi nối vào; HĐ chuyến thì không có hồ sơ.
    """
    r = client.put("/api/sales-contracts", json={
        "company": company, "code": code, "customer_id": _customer(h, company),
        "delivery_type": "single", "contract_type": ctype, "sign_date": day, "start_date": day,
        "master_id": _master_for(h, company) if ctype == "long_term" else None,
        "delivered_at": day, "channel": channel,
        "lines": [{"grade": grade, "qty": qty, "price": price, "ccy": ccy, "fx": fx}]}, headers=h)
    assert r.status_code == 200, r.text


def _cleanup(h: dict[str, str]) -> None:
    _MASTERS.clear()
    with session_scope() as db:
        for tbl in ("unit_daily_report", "unit_purchase_plan", "unit_stock_contract",
                    "sales_contract", "master_contract"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
        db.execute(text("DELETE FROM unit_customer WHERE company = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
        db.execute(text("DELETE FROM fact_price WHERE grade = ANY(:u)"), {"u": [UNIT_A, UNIT_B]})
    for n in (UNIT_A, UNIT_B):
        client.delete(f"/api/member-units/{n}", headers=h)
    client.delete(f"/api/member-regions/{REGION}", headers=h)


@pytest.fixture()
def seeded():
    """2 đơn vị (A thuộc khu vực test) + số liệu 2 ngày cho cả 2 biểu."""
    h = _admin()
    _cleanup(h)
    client.post("/api/member-regions", json={"name": REGION}, headers=h)
    for n in (UNIT_A, UNIT_B):
        client.post("/api/member-units", json={"name": n}, headers=h)
    client.put(f"/api/member-units/{UNIT_A}", json={"region": REGION, "set_region": True}, headers=h)

    # Thu mua: giá mủ nước khác nhau 2 ngày → kiểm bình quân GIA QUYỀN (không phải TB cộng).
    _price(UNIT_A, D0, "purchase", 400.0)
    _price(UNIT_A, D1, "purchase", 500.0)
    put = lambda body: client.put("/api/unit-daily/report", json=body, headers=h)  # noqa: E731
    put({"kind": "purchase", "company": UNIT_A, "as_of": D0,
         "fields": {"latex_wet": 100, "coagulum": 10,
                    "finished": [{"grade": "SVR 3L", "qty": 5, "price": 40}]}})
    put({"kind": "purchase", "company": UNIT_A, "as_of": D1,
         "fields": {"latex_wet": 300, "finished": [{"grade": "SVR 10", "qty": 5, "price": 2000,
                                                    "ccy": "USD", "fx": None}]}})
    put({"kind": "purchase", "company": UNIT_B, "as_of": D1, "fields": {"no_purchase": True}})
    # Biểu Thu mua chỉ đòi các đơn vị ĐƯỢC GIAO kế hoạch — không có số kế hoạch thì đơn vị không
    # có màn Thu mua, bảng theo dõi cũng không được đòi nộp.
    for n in (UNIT_A, UNIT_B):
        client.put("/api/unit-daily/plan",
                   json={"year": date.today().year, "company": n, "plan_tonnes": 1000}, headers=h)

    # Tồn kho 2 ngày (vẫn nhập tay theo ngày).
    put({"kind": "consumption", "company": UNIT_A, "as_of": D0,
         "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 1000}],
                    "stock_warehoused": [{"grade": "SVR 10", "qty": 500}],
                    "stock_material": 70}})
    put({"kind": "consumption", "company": UNIT_A, "as_of": D1,
         "fields": {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 800}],
                    "stock_warehoused": [], "stock_material": 60}})
    # Tiêu thụ = 3 LẦN GIAO của hợp đồng (2 loại HĐ, 2 hình thức) — từ 02/08/2026 không còn
    # nhập tay ở biểu ngày nữa.
    _deliver(h, UNIT_A, "HD-A1", D0, "long_term", "export", "SVR 3L", 10, 30)
    _deliver(h, UNIT_A, "HD-A2", D0, "spot", "domestic", "SVR 10 / CSR 10", 20, 20)
    _deliver(h, UNIT_A, "HD-A3", D1, "long_term", "domestic", "SVR 3L", 5, 1800,
             ccy="USD", fx=26000)
    yield h
    _cleanup(h)


def _get(path: str, h: dict, **params) -> dict:
    params.setdefault("date_from", D0)
    params.setdefault("date_to", D1)
    res = client.get(f"{API}/{path}", headers=h, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _stock(h: dict, **params) -> dict:
    """Màn tồn kho đi theo NGÀY CHỐT — mặc định D1, ngày đơn vị test khai tồn lần cuối.

    Từ 21/08/2026 số của một ngày KHÔNG còn được đắp sang ngày sau (trừ khi đơn vị tick "không phát
    sinh tồn kho"), nên chốt vào hôm nay là rỗng — phải chốt đúng ngày có số.
    """
    params.setdefault("as_of", D1)
    res = client.get(f"{API}/stock", headers=h, params=params)
    assert res.status_code == 200, res.text
    return res.json()


def _row(rep: dict, key: str) -> dict:
    return next(r for r in rep["rows"] if r["key"] == key)


def test_purchase_totals_and_weighted_average(seeded) -> None:
    rep = _get("purchase", seeded, companies=f"{UNIT_A},{UNIT_B}")
    a = _row(rep, UNIT_A)
    assert a["qty_latex"] == 400 and a["qty_cup"] == 10 and a["qty_finished"] == 10
    assert a["qty_total"] == 420                      # tổng theo bộ lọc = cả 3 loại mủ
    # BQ gia quyền: (400×100 + 500×300) / 400 = 475 đ/độ — TB cộng sẽ ra 450 (sai).
    assert a["price_latex_avg"] == pytest.approx(475)
    # Thành phẩm: dòng USD thiếu tỷ giá bị loại → chỉ còn 5 tấn × 40 triệu = 40 triệu đ/tấn.
    assert a["price_finished_avg"] == pytest.approx(40)
    assert any("thiếu tỷ giá" in w for w in rep["warnings"])
    # Đơn vị B chỉ bật cờ "không tổ chức thu mua" → không có sản lượng nhưng vẫn được đếm ngày.
    assert _row(rep, UNIT_B)["no_purchase_days"] == 1
    assert rep["totals"]["qty_total"] == 420


def test_purchase_filters(seeded) -> None:
    only_latex = _get("purchase", seeded, materials="latex", companies=UNIT_A)
    a = _row(only_latex, UNIT_A)
    assert a["qty_latex"] == 400 and a["qty_cup"] is None and a["qty_total"] == 400

    by_region = _get("purchase", seeded, regions=REGION, group_by="region")
    assert [r["key"] for r in by_region["rows"]] == [REGION]     # đơn vị B ngoài khu vực → loại

    by_grade = _get("purchase", seeded, grades="SVR 3L", group_by="grade")
    assert [r["key"] for r in by_grade["rows"]] == ["SVR 3L"]
    assert by_grade["rows"][0]["qty_finished"] == 5              # chỉ áp cho mủ thành phẩm


def test_consumption_filters_and_avg_price(seeded) -> None:
    rep = _get("consumption", seeded, companies=UNIT_A)
    a = _row(rep, UNIT_A)
    assert a["qty"] == 35 and a["qty_long_term"] == 15 and a["qty_spot"] == 20
    assert a["qty_export"] == 10 and a["qty_domestic"] == 25
    # Doanh thu = 10×30tr + 20×20tr + 5×1800USD×26.000 = 934 triệu → BQ = 934/35.
    assert a["revenue_ty"] == pytest.approx(0.934)
    assert a["avg_price_trieu"] == pytest.approx(934 / 35)

    spot = _get("consumption", seeded, contract="spot", companies=UNIT_A)
    assert _row(spot, UNIT_A)["qty"] == 20
    detail = _get("consumption", seeded, group_by="none", companies=UNIT_A)
    assert detail["detail"] and len(detail["rows"]) == 3
    assert {r["contract_label"] for r in detail["rows"]} == {"HĐ dài hạn", "HĐ chuyến"}


def test_consumption_percent_of_spot_sales_plan(seeded) -> None:
    """% kế hoạch tiêu thụ: tử số CHỈ là HĐ chuyến, mẫu số gồm cả đơn vị kỳ này chưa bán tấn nào."""
    h = seeded
    year = date.today().year
    for n, plan in ((UNIT_A, 50.0), (UNIT_B, 30.0)):
        assert client.put("/api/unit-daily/plan", headers=h, json={
            "year": year, "company": n, "plan_tonnes": 1000,
            "plan_sales_spot_tonnes": plan}).status_code == 200

    rep = _get("consumption", h, companies=f"{UNIT_A},{UNIT_B}")
    a = _row(rep, UNIT_A)                                  # A bán 20 tấn HĐ chuyến / KH 50 tấn
    assert a["plan_sales_spot_tonnes"] == 50 and a["pct_plan_sales_spot"] == pytest.approx(40)
    # Tổng: mẫu số 50 + 30 dù B chưa bán tấn nào — bỏ B ra khỏi mẫu số là % tự đẹp lên.
    # Tử số vẫn là 20 (HĐ dài hạn 15 tấn KHÔNG được cộng vào, kế hoạch không đặt cho loại đó).
    t = rep["totals"]
    assert t["qty"] == 35 and t["qty_spot"] == 20
    assert t["plan_sales_spot_tonnes"] == 80 and t["pct_plan_sales_spot"] == pytest.approx(25)

    # Nhóm theo NGÀY: kế hoạch là chỉ tiêu năm của đơn vị → để trống, không chia đại cho từng ngày.
    by_day = _get("consumption", h, companies=UNIT_A, group_by="day")
    assert by_day["rows"] and all(r["pct_plan_sales_spot"] is None for r in by_day["rows"])
    assert by_day["totals"]["pct_plan_sales_spot"] == pytest.approx(40)   # tổng vẫn tính được


def test_purchase_percent_of_year_plan(seeded) -> None:
    """% kế hoạch thu mua: tử số CHỈ là mủ nguyên liệu (nước + chén), mẫu số gồm cả đơn vị chưa mua.

    Thành phẩm mua ngoài KHÔNG vào tử số — mẫu gốc Ban TTKD tính % trên sản lượng mủ thu mua, và
    cột `total_purchase` của Báo cáo tổng hợp cũng vậy; cộng thêm thành phẩm là hai màn lệch nhau.
    """
    h = seeded
    rep = _get("purchase", h, companies=f"{UNIT_A},{UNIT_B}")
    a = _row(rep, UNIT_A)                       # 400 mủ nước + 10 mủ chén + 10 thành phẩm · KH 1.000
    assert a["qty_total"] == 420 and a["qty_material"] == 410
    assert a["plan_tonnes"] == 1000 and a["pct_plan"] == pytest.approx(41)
    # Tổng: mẫu số 1.000 + 1.000 dù B chưa mua tấn nào — bỏ B ra khỏi mẫu số là % tự đẹp lên.
    t = rep["totals"]
    assert t["plan_tonnes"] == 2000 and t["pct_plan"] == pytest.approx(20.5)

    # Nhóm theo NGÀY: kế hoạch là chỉ tiêu năm của đơn vị → để trống, không chia đại cho từng ngày.
    by_day = _get("purchase", h, companies=UNIT_A, group_by="day")
    assert by_day["rows"] and all(r["pct_plan"] is None for r in by_day["rows"])
    assert by_day["totals"]["pct_plan"] == pytest.approx(41)   # tổng vẫn tính được

    # Lọc theo loại mủ → tử số chỉ còn một phần sản lượng: KHÔNG tính %, và nói rõ vì sao.
    only_latex = _get("purchase", h, companies=UNIT_A, materials="latex")
    assert _row(only_latex, UNIT_A)["pct_plan"] is None
    assert only_latex["totals"]["pct_plan"] is None
    assert any("% kế hoạch thu mua" in w for w in only_latex["warnings"])


def test_delivery_missing_fx_is_excluded_and_warned(seeded) -> None:
    """Lần giao ngoại tệ THIẾU tỷ giá (bản ghi chuyển từ cơ chế cũ) → không tính doanh thu + cảnh báo.

    Form chặn lưu USD thiếu tỷ giá nên ca này chỉ đến từ script chuyển đổi → ghi thẳng vào DB.
    """
    h = seeded
    with session_scope() as db:
        db.execute(text("UPDATE sales_contract SET lines = jsonb_set(lines, '{0,fx}', 'null') "
                        " WHERE code = 'HD-A3'"))
    a = _row(_get("consumption", h, companies=UNIT_A), UNIT_A)
    assert a["qty"] == 35                                  # sản lượng vẫn đếm đủ
    assert a["revenue_ty"] == pytest.approx(0.7)           # chỉ 2 dòng VNĐ có doanh thu
    assert a["avg_price_trieu"] == pytest.approx(700 / 30)  # BQ bỏ sản lượng thiếu tỷ giá
    assert any("thiếu tỷ giá" in w
               for w in _get("consumption", h, companies=UNIT_A)["warnings"])


def test_internal_channel_is_not_counted_as_domestic(seeded) -> None:
    """Tiêu thụ NỘI BỘ là hình thức riêng — gộp vào "trong nước" là sai chỉ tiêu báo cáo."""
    h = seeded
    # Nội bộ chỉ bán được trong nhóm mẹ–con → cho B làm công ty con của A.
    client.put(f"/api/member-units/{UNIT_B}", headers=h,
               json={"set_parent": True, "parent_company": UNIT_A})
    client.put("/api/customers", json={"company": UNIT_B, "name": f"KH {UNIT_B}"}, headers=h)
    cus = next(c["id"] for c in
               client.get(f"/api/customers?company={UNIT_B}", headers=h).json()["items"]
               if c["company"] == UNIT_B)
    r = client.put("/api/sales-contracts", json={
        "company": UNIT_B, "code": "HD-INT", "customer_id": cus, "delivery_type": "single",
        "contract_type": "spot", "sign_date": D0, "start_date": D0, "delivered_at": D0,
        "channel": "internal", "to_company": UNIT_A,
        "lines": [{"grade": "SVR 10 / CSR 10", "qty": 7, "price": 25, "ccy": "VND"}]}, headers=h)
    assert r.status_code == 200, r.text

    b = _row(_get("consumption", h, companies=UNIT_B), UNIT_B)
    assert b["qty"] == 7 and b["qty_internal"] == 7
    assert not b["qty_domestic"] and not b["qty_export"]


def test_contract_without_type_goes_to_its_own_bucket(seeded) -> None:
    """HĐ chuyển từ cơ chế cũ chưa khai loại → ô riêng, KHÔNG dồn vào dài hạn hay chuyến."""
    h = seeded
    with session_scope() as db:      # chỉ bản ghi chuyển đổi mới thiếu loại (form ép nhập)
        db.execute(text("UPDATE sales_contract SET contract_type = NULL WHERE code = 'HD-A2'"))
    a = _row(_get("consumption", h, companies=UNIT_A), UNIT_A)
    assert a["qty"] == 35 and a["qty_spot"] is None and a["qty_unknown_type"] == 20


def test_stock_is_snapshot_at_the_reference_day(seeded) -> None:
    """Ảnh chụp tại ngày chốt: lấy đúng số đơn vị đã khai ngày đó, kèm ngày thật + số ngày đã cũ."""
    rep = _stock(seeded, companies=UNIT_A)
    a = _row(rep, UNIT_A)
    # Ngày chốt D1 chính là ngày đơn vị khai: 800 tấn chưa nhập kho, khối đã nhập kho trống.
    assert a["as_of"] == D1 and a["age_days"] == 0 and a["not_warehoused"] == 800
    assert a["warehoused"] is None and a["total"] == 800      # KHÔNG cộng dồn 1000 + 800
    assert a["material"] == 60
    assert rep["as_of"] == D1 and rep["days_back"] == 0
    by_grade = _stock(seeded, group_by="grade", companies=UNIT_A)
    assert [r["key"] for r in by_grade["rows"]] == ["SVR 3L"]   # ngày cuối chỉ còn 1 chủng loại


def _sign(h: dict, code: str, day: str, qty: float, grade: str = "SVR 3L") -> None:
    """1 hợp đồng ĐÃ KÝ ngày `day` nhưng CHƯA GIAO (không có `delivered_at`) — nguồn của khối 3."""
    r = client.put("/api/sales-contracts", json={
        "company": UNIT_A, "code": code, "customer_id": _customer(h, UNIT_A),
        "delivery_type": "single", "contract_type": "long_term", "channel": "export",
        "master_id": _master_for(h, UNIT_A),   # HĐ dài hạn phải thuộc hồ sơ mẹ (24/08/2026)
        "sign_date": day, "start_date": day,
        "lines": [{"grade": grade, "qty": qty, "price": 30, "ccy": "VND"}]}, headers=h)
    assert r.status_code == 200, r.text


def test_stock_subtracts_contracts_signed_but_not_delivered(seeded) -> None:
    """Tồn có thể giao dịch = tồn thành phẩm − đã ký HĐ chưa giao, HĐ lấy tại ĐÚNG ngày của số tồn.

    Số tồn của UNIT_A là của ngày D1 (cũ 2 ngày) → phần "đã ký chưa giao" cũng phải tính tại D1.
    Lấy hợp đồng của ngày chốt trừ tồn kho ngày D1 là ghép số hai thời điểm khác nhau.
    """
    h = seeded
    _sign(h, "HD-A9", D1, 300)                          # ký D1, chưa giao → nằm trong ảnh chụp
    _sign(h, "HD-A8", date.today().isoformat(), 500)    # ký SAU ngày của số tồn → chưa được trừ
    a = _row(_stock(h, companies=UNIT_A), UNIT_A)
    assert a["total"] == 800 and a["signed_undelivered"] == 300 and a["tradable"] == 500
    # HĐ của seed đã giao xong ngay trong ngày ký → không còn nợ giao, không đội khối 3 lên.
    assert _row(_stock(h, companies=UNIT_A, group_by="grade"), "SVR 3L")["signed_undelivered"] == 300


def test_tradable_stock_stays_negative_when_signed_more_than_on_hand(seeded) -> None:
    """Đã ký nhiều hơn hàng đang có thì tồn giao dịch được ÂM — cắt về 0 là giấu mất phần thiếu."""
    _sign(seeded, "HD-A9", D1, 1000)
    a = _row(_stock(seeded, companies=UNIT_A), UNIT_A)
    assert a["signed_undelivered"] == 1000 and a["tradable"] == -200


def test_stock_only_carries_when_the_unit_declares_no_change(seeded) -> None:
    """Số ngày trước CHỈ được giữ lại khi đơn vị tick "không phát sinh tồn kho để khai".

    Chốt 21/08/2026: đơn vị im lặng thì báo thiếu (trước đây số cũ được đắp sang trong 7 ngày,
    khiến biểu đồ hiện tồn kho cho cả đơn vị chưa hề nộp).
    """
    ngay_sau = (date.fromisoformat(D1) + timedelta(days=1)).isoformat()
    im_lang = _stock(seeded, companies=UNIT_A, as_of=ngay_sau)
    assert im_lang["rows"] == [] and im_lang["totals"]["total"] is None
    assert [m["company"] for m in im_lang["coverage"]["missing"]] == [UNIT_A]
    assert any("chưa có số tồn kho" in w for w in im_lang["warnings"])

    client.put("/api/unit-daily/report", headers=seeded, json={
        "kind": "consumption", "company": UNIT_A, "as_of": ngay_sau, "fields": {"no_stock": True}})
    giu_so = _stock(seeded, companies=UNIT_A, as_of=ngay_sau)
    row = _row(giu_so, UNIT_A)
    assert row["total"] == 800 and row["age_days"] == 1     # số của D1, đã cũ 1 ngày
    assert not giu_so["coverage"]["missing"]


def test_stock_by_day_totals_are_the_reference_day_snapshot(seeded) -> None:
    """Drill xuống NGÀY: mỗi ngày là ảnh chụp riêng; Tổng cộng = ảnh chụp tại ngày chốt.

    Bẫy cũ: Tổng cộng chỉ lấy các đơn vị nhập đúng NGÀY CUỐI có dữ liệu → đơn vị nhập sớm hơn bị
    rơi khỏi tổng (đo trên prod 10/08/2026: 250,8 tấn thay vì ~100.000 tấn).
    """
    h = seeded
    client.put("/api/unit-daily/report", headers=h, json={
        "kind": "consumption", "company": UNIT_B, "as_of": D0,
        "fields": {"stock_warehoused": [{"grade": "SVR 10", "qty": 200}]}})
    # Nhóm theo NGÀY: `days_back` là phạm vi ngày muốn xem lại (không còn là "đắp số cũ").
    rep = _stock(h, companies=f"{UNIT_A},{UNIT_B}", group_by="day", days_back=7)
    assert [r["key"] for r in rep["rows"]] == [D0, D1]
    assert _row(rep, D0)["total"] == 1700      # A: 1000 + 500, B: 200
    assert _row(rep, D1)["total"] == 800
    # A lấy số D1 (800) + B lấy số D0 (200) — KHÔNG cộng dồn 2 ngày, cũng không bỏ rơi B.
    assert rep["totals"]["total"] == 1000
    assert rep["coverage"]["units_counted"] == 2
    assert any("không cộng dồn" in w for w in rep["warnings"])


def test_stock_coverage_separates_missing_from_declared_empty(seeded) -> None:
    """Đơn vị khai "không phát sinh tồn kho" là ĐÃ NỘP — không đếm thành thiếu, cũng không hoá 0."""
    h = seeded
    miss = _stock(h, companies=f"{UNIT_A},{UNIT_B}")
    assert miss["coverage"]["units_expected"] == 2 and miss["coverage"]["units_counted"] == 1
    assert [m["company"] for m in miss["coverage"]["missing"]] == [UNIT_B]

    client.put("/api/unit-daily/report", headers=h, json={
        "kind": "consumption", "company": UNIT_B, "as_of": D1, "fields": {"no_stock": True}})
    rep = _stock(h, companies=f"{UNIT_A},{UNIT_B}")
    assert rep["coverage"]["missing"] == []
    assert [e["company"] for e in rep["coverage"]["no_stock"]] == [UNIT_B]
    assert rep["totals"]["total"] == 800        # B không có số nào để cộng vào tổng
    # Đã nộp đúng hạn thì không cảnh báo — chỉ hiện ở dải độ phủ để tổng số đơn vị cộng cho đủ.
    assert not any("không phát sinh tồn kho" in w for w in rep["warnings"])


def test_drill_region_then_company(seeded) -> None:
    """Chuỗi drill: khu vực → đơn vị → ngày cho ra đúng số của nhánh đang mở."""
    by_region = _get("purchase", seeded, regions=REGION, group_by="region")
    assert _row(by_region, REGION)["qty_total"] == 420
    by_company = _get("purchase", seeded, regions=REGION, group_by="company")
    assert _row(by_company, UNIT_A)["qty_total"] == 420
    by_day = _get("purchase", seeded, companies=UNIT_A, group_by="day")
    assert [r["key"] for r in by_day["rows"]] == [D0, D1]
    assert _row(by_day, D0)["qty_total"] == 115      # 100 nước + 10 chén + 5 thành phẩm
    assert _row(by_day, D1)["qty_total"] == 305


def test_status_matrix(seeded) -> None:
    rep = _get("status", seeded, kind="purchase", companies=f"{UNIT_A},{UNIT_B}")
    assert rep["dates"] == [D0, D1]
    a = next(r for r in rep["rows"] if r["company"] == UNIT_A)
    b = next(r for r in rep["rows"] if r["company"] == UNIT_B)
    assert a["cells"][D0] == "ok" and a["filled"] == 2 and a["missing"] == 0
    assert b["cells"][D0] == "none" and b["cells"][D1] == "no_purchase"
    assert b["missing"] == 1 and rep["totals"]["expected"] == 4


def test_status_allows_a_custom_period_longer_than_three_months(seeded) -> None:
    """Theo dõi có thể chọn một kỳ dài đến một năm, không còn bị chặn ở 92 ngày."""
    long_to = (date.fromisoformat(D0) + timedelta(days=92)).isoformat()
    rep = _get("status", seeded, kind="purchase", companies=UNIT_A, date_to=long_to)
    assert len(rep["dates"]) == 93
    assert rep["dates"][0] == D0 and rep["dates"][-1] == long_to


def test_status_ignores_rows_without_real_data(seeded) -> None:
    """CÓ BẢN GHI ≠ ĐÃ NỘP.

    Biểu Tồn kho mang sẵn hàng trăm bản ghi CŨ của biểu Tiêu thụ (chỉ có mảng `sales` + cờ
    `sales_migrated`, không có khối tồn kho nào). Đếm theo "có dòng trong bảng" thì những ngày đó
    hiện ✅ và tỷ lệ nộp báo cáo cao hơn thực tế — đo trên prod 05/08/2026 là 151/566 ngày.
    """
    h = seeded
    client.put("/api/unit-daily/report", headers=h, json={
        "kind": "consumption", "company": UNIT_B, "as_of": D0,
        "fields": {"sales": [{"grade": "SVR 3L", "qty": 12, "contract": "spot",
                              "channel": "domestic"}], "sales_migrated": True}})
    rep = _get("status", seeded, kind="consumption", companies=f"{UNIT_A},{UNIT_B}")
    b = next(r for r in rep["rows"] if r["company"] == UNIT_B)
    assert b["cells"][D0] == "none" and b["filled"] == 0

    # Đơn vị bật cờ "không phát sinh tồn kho" thì VẪN tính là đã nộp.
    client.put("/api/unit-daily/report", headers=h, json={
        "kind": "consumption", "company": UNIT_B, "as_of": D1, "fields": {"no_stock": True}})
    rep2 = _get("status", seeded, kind="consumption", companies=f"{UNIT_A},{UNIT_B}")
    assert next(r for r in rep2["rows"] if r["company"] == UNIT_B)["cells"][D1] == "ok"


def test_status_purchase_only_asks_units_with_a_plan(seeded) -> None:
    """Bảng Thu mua chỉ đòi đơn vị ĐƯỢC GIAO kế hoạch — dùng đúng công tắc của màn Thu mua."""
    h = seeded
    client.put("/api/unit-daily/plan", headers=h,
               json={"year": date.today().year, "company": UNIT_B, "plan_tonnes": 0})
    rep = _get("status", seeded, kind="purchase", companies=f"{UNIT_A},{UNIT_B}")
    assert [r["company"] for r in rep["rows"]] == [UNIT_A]      # B khai kế hoạch 0 → không phải nộp
    assert rep["totals"]["expected"] == 2                        # 1 đơn vị × 2 ngày


def test_range_validation_and_xlsx(seeded) -> None:
    bad = client.get(f"{API}/purchase", headers=seeded, params={"date_from": D1, "date_to": D0})
    assert bad.status_code == 400
    xlsx = client.get(f"{API}/purchase.xlsx", headers=seeded,
                      params={"date_from": D0, "date_to": D1})
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    # Màn tồn kho: ngày chốt sai định dạng bị chặn, số ngày lùi vượt trần cũng vậy.
    assert client.get(f"{API}/stock", headers=seeded, params={"as_of": "10-08-2026"}).status_code == 400
    assert client.get(f"{API}/stock", headers=seeded,
                      params={"as_of": D1, "days_back": 400}).status_code == 422
    stock_xlsx = client.get(f"{API}/stock.xlsx", headers=seeded, params={"as_of": D1})
    assert stock_xlsx.status_code == 200 and stock_xlsx.content[:2] == b"PK"


def test_requires_unit_daily_cap(seeded) -> None:
    h = seeded
    client.delete("/api/users/an_noperm", headers=h)
    client.post("/api/users", json={"username": "an_noperm", "password": "pass123",
                                    "role": "editor"}, headers=h)
    tok = client.post("/api/auth/login", json={"username": "an_noperm", "password": "pass123"}).json()
    nh = {"Authorization": f"Bearer {tok['access_token']}"}
    res = client.get(f"{API}/purchase", headers=nh, params={"date_from": D0, "date_to": D1})
    assert res.status_code == 403
    client.delete("/api/users/an_noperm", headers=h)


def test_consumption_detail_rows_are_paged(seeded) -> None:
    """Thống kê tiêu thụ ở chế độ CHI TIẾT cắt trang, nhưng dòng Tổng cộng vẫn tính CẢ KỲ.

    Chi tiết trả từng lần bán nên số dòng tăng theo ngày; nếu tổng cũng cắt theo trang thì người
    đọc sẽ tưởng cả kỳ chỉ bán bằng đúng một trang.
    """
    h = seeded
    url = f"{API}/consumption?date_from={D0}&date_to={D1}&companies={UNIT_A}&group_by=none"
    page1 = client.get(f"{url}&page=1&page_size=2", headers=h).json()
    assert page1["detail"] is True and len(page1["rows"]) == 2 and page1["total"] == 3
    assert page1["totals"]["qty"] == pytest.approx(35.0)     # 10 + 20 + 5 tấn của CẢ kỳ

    page2 = client.get(f"{url}&page=2&page_size=2", headers=h).json()
    assert len(page2["rows"]) == 1 and page2["total"] == 3
    assert page2["totals"]["qty"] == pytest.approx(35.0)
    keys = {(r["as_of"], r["code"]) for r in page1["rows"]}
    assert not (keys & {(r["as_of"], r["code"]) for r in page2["rows"]})


def test_purchase_ignores_the_two_removed_raw_materials(seeded) -> None:
    """2 loại mủ nguyên liệu (thêm 30/07/2026, BỎ 14/08/2026) không còn là chỉ tiêu thu mua.

    Khách xác nhận đơn vị KHÔNG thu mua "Mủ NL nước chưa cán vắt (chén)" và "Mủ NL đã cán vắt
    (RSS)" → bỏ khỏi biểu nhập lẫn mọi báo cáo/thống kê thu mua. Bản ghi CŨ (prod có 1 bản, toàn
    số 0) vẫn còn khoá trong payload, nên bảng phải BỎ QUA êm chứ không được `KeyError` → 500
    (đúng kiểu sự cố 10/08/2026 khi thiếu rổ đếm cho loại mới).
    """
    h = seeded
    client.put("/api/unit-daily/report", headers=h, json={
        "kind": "purchase", "company": UNIT_A, "as_of": D1,
        "fields": {"latex_wet": 300, "cup_raw": 7, "cup_raw_price": 11000,
                   "rss_pressed": 4, "rss_pressed_price": 12000,
                   "finished": [{"grade": "SVR 10", "qty": 5, "price": 2000,
                                 "ccy": "USD", "fx": None}]}})

    rep = _get("purchase", h, companies=UNIT_A)
    a = _row(rep, UNIT_A)
    assert "qty_cup_raw" not in a and "qty_rss_pressed" not in a
    assert "price_cup_raw_avg" not in a and "price_rss_pressed_avg" not in a
    # Tổng chỉ còn: 400 mủ nước + 10 mủ chén + 10 thành phẩm — KHÔNG cộng 2 loại đã bỏ.
    assert a["qty_total"] == 420 and rep["totals"]["qty_total"] == 420

    # Nhóm theo loại mủ: 2 loại đã bỏ không còn là một dòng.
    by_material = _get("purchase", h, companies=UNIT_A, group_by="material")
    keys = [r["key"] for r in by_material["rows"]]
    assert "Mủ NL đã cán vắt (RSS)" not in keys and "Mủ NL nước chưa cán vắt (chén)" not in keys


def _mark(h: dict, **body) -> dict:
    body.setdefault("date_from", D0)
    body.setdefault("date_to", D1)
    res = client.post(f"{API}/mark-no-purchase", headers=h, json=body)
    assert res.status_code == 200, res.text
    return res.json()


def test_mark_no_purchase_preview_does_not_write(seeded) -> None:
    """Nhịp XEM TRƯỚC chỉ đếm ô trống — bảng theo dõi phải y nguyên sau khi gọi."""
    prev = _mark(seeded, companies=f"{UNIT_A},{UNIT_B}")
    assert prev["applied"] is False and prev["marked"] == 0
    # Chỉ 1 ô trống trong bộ dữ liệu mẫu: UNIT_B ngày D0 (D1 đã bật cờ, UNIT_A nhập đủ 2 ngày).
    assert prev["count"] == 1
    assert prev["units"] == [{"company": UNIT_B, "days": 1, "first": D0, "last": D0}]
    rep = _get("status", seeded, kind="purchase", companies=f"{UNIT_A},{UNIT_B}")
    assert next(r for r in rep["rows"] if r["company"] == UNIT_B)["cells"][D0] == "none"


def test_mark_no_purchase_fills_blanks_and_keeps_real_data(seeded) -> None:
    """Đánh dấu hàng loạt chỉ đụng ô TRỐNG; ngày đã có số liệu không được động vào."""
    h = seeded
    before = client.get("/api/unit-daily/day", headers=h,
                        params={"kind": "purchase", "as_of": D0}).json()["entries"][UNIT_A]

    done = _mark(h, companies=f"{UNIT_A},{UNIT_B}", apply=True)
    assert done["applied"] is True and done["marked"] == 1

    rep = _get("status", h, kind="purchase", companies=f"{UNIT_A},{UNIT_B}")
    b = next(r for r in rep["rows"] if r["company"] == UNIT_B)
    assert b["cells"][D0] == "no_purchase" and b["missing"] == 0
    a = next(r for r in rep["rows"] if r["company"] == UNIT_A)
    assert a["filled"] == 2 and a["cells"][D0] == "ok"       # số liệu thật KHÔNG bị ghi đè
    after = client.get("/api/unit-daily/day", headers=h,
                       params={"kind": "purchase", "as_of": D0}).json()["entries"][UNIT_A]
    assert after["fields"] == before["fields"]

    # Chạy lại: không còn ô trống nào để đánh dấu (thao tác lặp lại vô hại).
    assert _mark(h, companies=f"{UNIT_A},{UNIT_B}", apply=True)["marked"] == 0


def test_mark_no_purchase_is_admin_only(seeded) -> None:
    """Chuyên viên (kể cả có quyền `unit_daily`) không được dọn hàng loạt — chỉ admin."""
    h = seeded
    client.delete("/api/users/an_editor_mark", headers=h)
    client.post("/api/users", json={"username": "an_editor_mark", "password": "pass123",
                                    "role": "editor", "caps": ["unit_daily"]}, headers=h)
    tok = client.post("/api/auth/login",
                      json={"username": "an_editor_mark", "password": "pass123"}).json()
    nh = {"Authorization": f"Bearer {tok['access_token']}"}
    res = client.post(f"{API}/mark-no-purchase", headers=nh,
                      json={"date_from": D0, "date_to": D1, "apply": True})
    assert res.status_code == 403
    client.delete("/api/users/an_editor_mark", headers=h)


def test_mark_no_purchase_only_fills_days_the_unit_left_blank(seeded) -> None:
    """Chỉ điền ngày đơn vị KHÔNG nhập gì — mọi kiểu "đã nhập" đều phải sống sót nguyên vẹn.

    Các ca dễ sai, liệt kê hết ở đây vì đây là thao tác GHI HỘ đơn vị:
      · ngày có sản lượng               → giữ nguyên
      · ngày khai sản lượng 0 kèm giá   → ĐÃ nhập (tổ chức mua nhưng không mua được) → giữ nguyên
      · ngày có bản ghi RỖNG            → coi như chưa nhập → gắn cờ vào chính bản ghi đó
      · ngày đã tích "không tổ chức"    → không đụng lại
      · ngày chỉ nhập biểu Tồn kho      → biểu Thu mua vẫn trống → có điền
      · ngày SAU hôm nay                → không bao giờ điền
    """
    h = seeded
    day = lambda n: (date.today() - timedelta(days=n)).isoformat()  # noqa: E731
    put = lambda body: client.put("/api/unit-daily/report", json=body, headers=h)  # noqa: E731
    d6, d5, d4, d1, d0 = day(6), day(5), day(4), day(1), day(0)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    put({"kind": "purchase", "company": UNIT_B, "as_of": d5, "fields": {"latex_wet": 50}})
    put({"kind": "purchase", "company": UNIT_B, "as_of": d4,
         "fields": {"latex_wet": 0, "coagulum": 0}})          # mua 0 tấn — vẫn là ĐÃ nhập
    put({"kind": "purchase", "company": UNIT_B, "as_of": D0, "fields": {}})   # mở form rồi lưu trống
    put({"kind": "consumption", "company": UNIT_B, "as_of": d6,
         "fields": {"stock_material": 12}})                   # chỉ nộp biểu Tồn kho
    # D1 đã có cờ "không tổ chức thu mua" từ fixture; d1/d0/d6 (thu mua) và tomorrow bỏ trống.

    def payloads() -> dict[str, dict]:
        with session_scope() as db:
            rows = db.execute(text("SELECT as_of, payload FROM unit_daily_report "
                                   "WHERE kind = 'purchase' AND company = :c"),
                              {"c": UNIT_B}).mappings().all()
        return {str(r["as_of"]): dict(r["payload"]) for r in rows}

    before = payloads()
    done = _mark(h, companies=UNIT_B, date_from=d6, date_to=tomorrow, apply=True)
    after = payloads()

    # Đúng 4 ngày trống được điền: d6 · D0 (bản ghi rỗng) · d1 · d0. Ngày mai KHÔNG tính.
    assert done["marked"] == 4
    assert sorted(set(after) - set(before)) == sorted([d6, d1, d0])
    assert tomorrow not in after
    for d in (d5, d4, D1):
        assert after[d] == before[d], f"ngày {d} đã nhập mà bị sửa"
    assert after[d5] == {"latex_wet": 50}
    assert after[d4] == {"latex_wet": 0, "coagulum": 0}       # 0 vẫn là số liệu, không bị ghi đè
    assert after[D1] == {"no_purchase": True}                 # đã tích sẵn → không đụng lại
    assert after[D0] == {"no_purchase": True}   # gộp cờ vào bản ghi rỗng sẵn có (không insert mới)
    for d in (d6, d1, d0):
        assert after[d] == {"no_purchase": True}
