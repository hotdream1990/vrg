"""Test báo cáo tiêu thụ–tồn kho theo ngày (member + chuyên viên có quyền `unit_daily`) + cửa sổ sửa ngày."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(username: str, password: str) -> dict[str, str]:
    token = client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin() -> dict[str, str]:
    return _bearer("admin", "admin")


def _wipe_unit(unit: str) -> None:
    """Xoá sạch dấu vết của một đơn vị test (hợp đồng → khách hàng → phiếu ngày)."""
    with session_scope() as db:
        for tbl in ("sales_contract", "unit_customer", "unit_daily_report"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = :c"), {"c": unit})


def _legacy_contract(company: str, code: str, grade: str, qty: float,
                     start: str, delivered: str | None) -> dict:
    """Dựng 1 hợp đồng ở bảng CŨ như dữ liệu lịch sử sẵn có.

    Bảng `unit_stock_contract` đã đóng băng (API chỉ cho SỬA, không cho lập mới) nên test màn tra
    cứu/sửa phải ghi thẳng vào DB — đúng tình huống thật: bản ghi có từ trước ngày chuyển cơ chế.
    """
    from sqlalchemy import text

    from app.core.db import session_scope
    with session_scope() as db:
        new_id = db.execute(text(
            "INSERT INTO unit_stock_contract (company, code, grade, qty, price, ccy, start_date, "
            " delivered_date, updated_by) "
            "VALUES (:c, :code, :g, :q, 40, 'VND', CAST(:s AS date), CAST(:d AS date), 'test') "
            "RETURNING id"),
            {"c": company, "code": code, "g": grade, "q": qty, "s": start, "d": delivered}).scalar()
    return {"id": new_id, "code": code}


def _cleanup(h: dict[str, str], users: list[str], units: list[str]) -> None:
    """Dọn sạch dữ liệu test — không để lại tài khoản/đơn vị `_zz_*` trong DB dev."""
    from sqlalchemy import text

    from app.core.db import session_scope
    for u in users:
        client.delete(f"/api/users/{u}", headers=h)
    with session_scope() as db:
        for tbl, col in (("unit_daily_report", "company"), ("unit_purchase_plan", "company"),
                         ("unit_stock_contract", "company")):
            db.execute(text(f"DELETE FROM {tbl} WHERE {col} = ANY(:u)"), {"u": units})
        # Giá đơn vị nằm ở CẢ 2 lớp: chuyên viên chốt ('vrg') và đơn vị tự khai ('vrg_unit').
        db.execute(text("DELETE FROM fact_price WHERE source IN ('vrg', 'vrg_unit') "
                        "AND grade = ANY(:u)"), {"u": units})
    for n in units:
        client.delete(f"/api/member-units/{n}", headers=h)


def test_unit_daily_member_and_editor_flow() -> None:
    h = _admin()
    unit = "_zz_ud_unit"
    today = date.today().isoformat()
    for u in ("ud_mem", "ud_ed", "ud_noed"):
        client.delete(f"/api/users/{u}", headers=h)

    client.post("/api/member-units", json={"name": unit}, headers=h)
    assert client.post("/api/users", json={"username": "ud_mem", "password": "pass123",
                                           "role": "member", "member_units": [unit]}, headers=h).status_code == 200
    client.post("/api/users", json={"username": "ud_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily"]}, headers=h)
    client.post("/api/users", json={"username": "ud_noed", "password": "pass123", "role": "editor"}, headers=h)
    mh, eh, nh = _bearer("ud_mem", "pass123"), _bearer("ud_ed", "pass123"), _bearer("ud_noed", "pass123")

    # Member ghi số liệu thu mua hôm nay (key rác 'bad' bị loại).
    # Thu mua thành phẩm = BẢNG NHIỀU DÒNG theo chủng loại (mỗi dòng: chủng loại · SL · đơn giá ·
    # loại tiền · tỷ giá) — dòng rác/thiếu loại tiền vẫn phải được chuẩn hoá về mặc định VND.
    body = {"kind": "purchase", "company": unit, "as_of": today,
            "fields": {"latex_wet": 120.5, "coagulum": 30, "cum_purchase": 800, "bad": 9,
                       "finished": [{"grade": "SVR CV 50", "qty": 12, "price": 40.5},
                                    {"grade": "SVR 3L", "qty": 8, "price": 1750,
                                     "ccy": "USD", "fx": 26000, "rac": 1}]}}
    assert client.put("/api/member/daily-report", json=body, headers=mh).status_code == 200
    g = client.get(f"/api/member/daily-report?kind=purchase&as_of={today}", headers=mh)
    assert g.status_code == 200 and g.json()["units"] == [unit]
    saved = g.json()["entries"][unit]["fields"]
    assert saved["latex_wet"] == 120.5 and "bad" not in saved
    fin = saved["finished"]
    assert [r["grade"] for r in fin] == ["SVR CV 50", "SVR 3L"]
    assert fin[0]["qty"] == 12 and fin[0]["ccy"] == "VND"       # thiếu loại tiền → mặc định VND
    assert fin[1]["ccy"] == "USD" and fin[1]["fx"] == 26000 and "rac" not in fin[1]

    # Member không được đụng đơn vị khác.
    bad = {"kind": "purchase", "company": "khac", "as_of": today, "fields": {"latex_wet": 1}}
    assert client.put("/api/member/daily-report", json=bad, headers=mh).status_code == 403

    # create_only chống ghi trùng (đã có số → 409).
    dup = {**body, "create_only": True}
    assert client.put("/api/member/daily-report", json=dup, headers=mh).status_code == 409

    # Chuyên viên có quyền: xem lưới cả ngày + đặt SỐ LIỆU NĂM (kế hoạch thu mua + HĐ dài hạn đã ký).
    dy = client.get(f"/api/unit-daily/day?kind=purchase&as_of={today}", headers=eh)
    assert dy.status_code == 200 and unit in dy.json()["entries"]
    assert client.put("/api/unit-daily/plan",
                      json={"year": date.today().year, "company": unit, "plan_tonnes": 2000,
                            "signed_lt_tonnes": 1500, "carry_lt_tonnes": 40, "carry_spot_tonnes": 15},
                      headers=eh).status_code == 200
    pl = client.get(f"/api/unit-daily/plan?year={date.today().year}", headers=eh)
    assert pl.json()["plans"][unit] == {"plan_exploit_tonnes": None,
                                        "plan_tonnes": 2000, "signed_lt_tonnes": 1500,
                                        "carry_lt_tonnes": 40, "carry_spot_tonnes": 15,
                                        "plan_sales_spot_tonnes": None,
                                        "plan_revenue_ty": None}

    # Đơn vị thành viên tự cập nhật số liệu năm của mình; không đụng được đơn vị khác.
    assert client.put("/api/member/plan",
                      json={"year": date.today().year, "company": unit, "plan_tonnes": 2500},
                      headers=mh).status_code == 200
    mp = client.get(f"/api/member/plan?year={date.today().year}", headers=mh)
    assert mp.status_code == 200 and mp.json()["plans"][unit]["plan_tonnes"] == 2500
    assert client.put("/api/member/plan",
                      json={"year": date.today().year, "company": "Đơn vị khác", "plan_tonnes": 1},
                      headers=mh).status_code == 403

    # Chuyên viên sửa số của đơn vị (consumption) + timeline hiện bản ghi.
    # Biểu tiêu thụ dùng BẢNG NHIỀU DÒNG: `sales` + tồn kho dạng mảng. Tồn kho tính bằng TẤN
    # và KHÔNG còn "loại bành"; giá bán chọn loại tiền qua `sales_ccy`.
    # Mủ THU MUA (`sales`) và mủ KHAI THÁC (`sales_own`) nhập tách riêng, tổng thì cộng chung.
    cons = {"kind": "consumption", "company": unit, "as_of": today, "fields": {
        "sales": [{"code": "HĐ-01/2026", "contract": "long_term", "channel": "export",
                   "grade": "RSS 3", "qty": 12.5, "price": 45}],
        "sales_own": [{"contract": "spot", "channel": "domestic", "grade": "SVR 3L",
                       "qty": 7.5, "price": 40,
                       "warehouse_date": "2026-07-20", "invoice_date": "2026-07-21",
                       "wh_file": "px.pdf", "wh_filename": "phieu-xuat-kho.pdf",
                       "inv_file": "hd.pdf", "inv_filename": "hoa-don.pdf"}],
        "sales_ccy": "VND", "stock_ccy": "VND",
        "revenue": 862_500_000,
        "stock_not_warehoused": [{"grade": "RSS 3", "bale": "bỏ đi", "qty": 9}],
        "stock_warehoused": [{"grade": "RSS 3", "qty": 15}],
        # Khối 3 (đã ký HĐ) KHÔNG đi trong payload ngày nữa — gửi kèm thì server phải BỎ QUA.
        "stock_signed_undelivered": [{"code": "rác", "grade": "RSS 3", "qty": 999}],
        "stock_material": 3.5,
    }}
    assert client.put("/api/unit-daily/report", json=cons, headers=eh).status_code == 200

    # Hợp đồng ở bảng CŨ vẫn ghi được qua endpoint (chỉ màn web là chỉ-xem), nhưng từ 02/08/2026
    # KHÔNG còn được cộng vào khối 3 — kiểm ngay bên dưới.
    ct = {"company": unit, "code": "HĐ-02/2026", "grade": "RSS 3", "qty": 6, "price": 48,
          "start_date": today, "delivery_date": (date.today() + timedelta(days=10)).isoformat()}
    made = client.put("/api/unit-daily/stock-contracts", json=ct, headers=eh)
    assert made.status_code == 200 and made.json()["contract"]["id"]

    tl = client.get("/api/unit-daily/timeline?kind=consumption&days=30", headers=eh)
    saved = next(e for e in tl.json()["entries"] if e["company"] == unit)["fields"]
    assert saved["sales"][0]["qty"] == 12.5
    # Số HĐ/PL lưu theo TỪNG DÒNG bán; dòng không gõ thì để trống.
    assert saved["sales"][0]["code"] == "HĐ-01/2026"
    # Khối 3 là số TỰ TÍNH từ `sales_contract` (không phải số client gửi kèm, cũng KHÔNG lấy
    # hợp đồng theo bảng cũ) — đơn vị này chưa có hợp đồng nào ở cơ chế mới nên bằng 0.
    assert saved["stock_signed_undelivered"]["qty"] == 0
    assert saved["stock_signed_undelivered"]["items"] == []
    assert saved["sales_own"][0]["code"] is None
    # Dòng mủ khai thác lưu riêng, giữ đủ 2 mốc ngày + các file chứng từ đính kèm.
    own = saved["sales_own"][0]
    assert own["qty"] == 7.5 and own["contract"] == "spot" and own["channel"] == "domestic"
    assert own["warehouse_date"] == "2026-07-20" and own["invoice_date"] == "2026-07-21"
    assert own["wh_filename"] == "phieu-xuat-kho.pdf" and own["inv_filename"] == "hoa-don.pdf"
    assert saved["stock_not_warehoused"][0]["qty"] == 9 and saved["stock_warehoused"][0]["qty"] == 15
    assert "bale" not in saved["stock_not_warehoused"][0]  # cột loại bành đã bỏ hẳn
    assert saved["sales_ccy"] == "VND" and saved["stock_material"] == 3.5

    # Báo cáo tổng hợp theo kỳ: cộng dồn sản lượng, tồn kho lấy thời điểm cuối kỳ (đã là tấn).
    pr = client.get(f"/api/unit-daily/period-report?kind=consumption&date_from={today}&date_to={today}",
                    headers=eh)
    assert pr.status_code == 200
    row = next(r for r in pr.json()["rows"] if r["company"] == unit)
    # Tiêu thụ chỉ đến từ LẦN GIAO của hợp đồng — dòng bán kiểu cũ không còn được cộng
    # (chốt 02/08/2026).
    assert row["total_consumption"] is None and row["lt_export"] is None
    # Tồn kho thành phẩm = khối 1 + khối 2 = 24; khối 3 (đã ký HĐ chưa giao) báo RIÊNG, và đơn vị
    # này chưa có hợp đồng ở cơ chế mới nên bằng 0 (KHÔNG lấy hợp đồng bảng cũ).
    assert row["stock_finished"] == 24.0
    assert not row["stock_finished_hd"] and row["stock_material"] == 3.5

    # Đơn vị thành viên KHÔNG được xem báo cáo tổng hợp (chỉ admin / quyền unit_daily).
    assert client.get(f"/api/unit-daily/period-report?kind=purchase&date_from={today}&date_to={today}",
                      headers=mh).status_code == 403
    assert client.get(f"/api/member/period-report?kind=purchase&date_from={today}&date_to={today}",
                      headers=mh).status_code == 404

    # Editor KHÔNG quyền unit_daily bị chặn; member không vào được endpoint chuyên viên.
    assert client.get(f"/api/unit-daily/day?kind=purchase&as_of={today}", headers=nh).status_code == 403
    assert client.get(f"/api/unit-daily/day?kind=purchase&as_of={today}", headers=mh).status_code == 403

    _cleanup(h, ["ud_mem", "ud_ed", "ud_noed"], [unit])


def test_unit_daily_edit_window_blocks_old_day() -> None:
    h = _admin()
    unit = "_zz_ud_win"
    old_day = (date.today() - timedelta(days=60)).isoformat()
    client.delete("/api/users/ud_win", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_win", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_win", "pass123")

    body = {"kind": "purchase", "company": unit, "as_of": old_day, "fields": {"latex_wet": 1}}
    # Ngày đã quá cửa sổ sửa (mặc định 7 ngày) → 403 chỉ-xem.
    assert client.put("/api/member/daily-report", json=body, headers=mh).status_code == 403

    # Ngày trong tương lai → 400.
    future = {**body, "as_of": (date.today() + timedelta(days=14)).isoformat()}
    assert client.put("/api/member/daily-report", json=future, headers=mh).status_code == 400

    _cleanup(h, ["ud_win"], [unit])


def test_every_daily_form_shares_the_cutoff_deadline(monkeypatch) -> None:
    """Hạn nhập = giờ chốt 11:00 của ngày D + N — CHUNG mọi biểu (chốt 24/09/2026).

    Bỏ 2 ô "biểu Thu mua / Tồn kho được nhập trễ hơn": đặt N = 1 thì số liệu hôm qua (cả Thu mua,
    Tồn kho lẫn đơn giá mủ trên biểu Thu mua, cho cả đơn vị lẫn chuyên viên) nhập được tới 11:00
    hôm nay, sau đó khoá; N = 0 thì hôm nay nhập tới 11:00 hôm nay. Admin miễn.
    """
    from tests.edit_window_clock import pin_clock, window_config

    h = _admin()
    unit = "_zz_ud_stock_win"
    day = pin_clock(monkeypatch, 10, 59).date()
    today = day.isoformat()
    yesterday = (day - timedelta(days=1)).isoformat()
    client.delete("/api/users/ud_stock_win", headers=h)
    client.delete("/api/users/ud_stock_ed", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_stock_win", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    client.post("/api/users", json={"username": "ud_stock_ed", "password": "pass123", "role": "editor",
                                    "permissions": ["unit_daily", "raw_material"]}, headers=h)
    mh, eh = _bearer("ud_stock_win", "pass123"), _bearer("ud_stock_ed", "pass123")

    def put(path: str, body: dict, hdr: dict, **kw) -> int:
        return client.put(path, json={**body, **kw}, headers=hdr).status_code

    purchase = {"kind": "purchase", "company": unit, "as_of": yesterday, "fields": {"latex_wet": 1}}
    stock = {"kind": "consumption", "company": unit, "as_of": yesterday, "fields": {"stock_material": 5}}
    my_price = {"company": unit, "as_of": yesterday, "price_type": "purchase", "price": 400}
    hq_price = {"as_of": yesterday, "source": "vrg", "grade": unit, "contract": "",
                "price_type": "purchase", "price": 400, "currency": "VND", "unit": "đồng/độ TSC"}
    forms = ((purchase, "/api/member/daily-report", mh), (stock, "/api/member/daily-report", mh),
             (my_price, "/api/member/prices", mh), (purchase, "/api/unit-daily/report", eh),
             (stock, "/api/unit-daily/report", eh), (hq_price, "/api/prices/records", eh))

    def editable_from(url: str, hdr: dict) -> str:
        return client.get(url, headers=hdr).json()["editable_from"]

    # N = 1 cho CẢ đơn vị lẫn chuyên viên, giờ chốt 11:00 đặt TƯỜNG MINH (DB có thể đang cấu hình
    # giờ khác); cấu hình cũ được trả lại khi ra khỏi khối.
    with window_config(member=1, editor=1, hour=11):
        # 10:59 — số liệu hôm qua còn hạn ở MỌI biểu (không biểu nào được ưu ái hơn biểu nào).
        for body, path, hdr in forms:
            assert put(path, body, hdr) == 200, (path, body)
        assert editable_from(f"/api/member/daily-report?kind=consumption&as_of={today}", mh) == yesterday
        assert editable_from("/api/unit-daily/timeline?kind=purchase&days=7", eh) == yesterday

        # 11:00 — hôm qua hết hạn cùng lúc ở mọi biểu, hôm nay vẫn mở.
        pin_clock(monkeypatch, 11, 0, day)
        for body, path, hdr in forms:
            res = client.put(path, json=body, headers=hdr)
            assert res.status_code == 403 and res.headers.get("X-Edit-Blocked") == "window", (path, res.text)
            assert "đến 11:00 ngày hôm sau" in res.json()["detail"]
            assert put(path, body, hdr, as_of=today) == 200, (path, body)
        for url in (f"/api/member/daily-report?kind=purchase&as_of={today}", "/api/member/prices",
                    "/api/member/checklist"):
            assert editable_from(url, mh) == today, url
        s = client.get("/api/settings/edit-windows", headers=mh).json()
        assert (s["member_days"], s["member_editable_from"], s["cutoff_hour"]) == (1, today, 11)
        # Admin miễn hàng rào: vẫn ghi được số liệu hôm qua.
        assert put("/api/unit-daily/report", stock, h) == 200
    _cleanup(h, ["ud_stock_win", "ud_stock_ed"], [unit])


def test_price_basis_is_fixed_and_prev_stock() -> None:
    """Cơ sở tính độ CỐ ĐỊNH (mủ nước TSC · mủ chén DRC) + nút 'Lấy tồn ngày trước'."""
    h = _admin()
    unit = "_zz_ud_basis"
    today = date.today()
    y_day, t_day = (today - timedelta(days=1)).isoformat(), today.isoformat()
    client.delete("/api/users/ud_basis", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_basis", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_basis", "pass123")

    # 1) Cơ sở tính độ KHÔNG còn là lựa chọn của người nhập (chốt 17/08/2026): mủ nước luôn
    #    đồng/độ TSC, mủ chén luôn đồng/độ DRC. Client cũ gửi `basis` lên thì server BỎ QUA —
    #    nếu nhận theo thì nhãn kho giá lại lệch đúng như lỗi cũ.
    assert client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": unit, "as_of": t_day,
        "fields": {"coagulum": 8, "cup_basis": "drc"}}).status_code == 200
    day = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}", headers=mh).json()
    assert "cup_basis" not in day["entries"][unit]["fields"]   # ô chọn đã bỏ, không lưu nữa

    for ptype, sent_basis, want in (("purchase_cup", "tsc", "đồng/độ DRC"),
                                    ("purchase", "drc", "đồng/độ TSC")):
        assert client.put("/api/member/prices", headers=mh, json={
            "company": unit, "as_of": t_day, "price_type": ptype,
            "price": 480, "basis": sent_basis}).status_code == 200
        with session_scope() as db:
            unit_label = db.execute(text(
                "SELECT unit FROM fact_price WHERE grade = :g AND price_type = :p "
                "AND as_of = CAST(:d AS date) ORDER BY ingested_at DESC LIMIT 1"),
                {"g": unit, "p": ptype, "d": t_day}).scalar()
        assert unit_label == want, f"{ptype} phải mang nhãn {want}, đang là {unit_label}"

    # 2) Tồn kho hôm qua → "Lấy tồn ngày trước" của HÔM NAY phải trả đúng số đó (đơn vị tấn).
    assert client.put("/api/member/daily-report", headers=mh, json={
        "kind": "consumption", "company": unit, "as_of": y_day, "fields": {
            "stock_not_warehoused": [{"grade": "RSS 3", "qty": 30}],
            "stock_material": 5, "stock_ccy": "USD"}}).status_code == 200
    prev = client.get(f"/api/member/daily-report/prev-stock?company={unit}&before={t_day}",
                      headers=mh).json()
    assert prev["found"] and prev["as_of"] == y_day
    assert prev["stock_not_warehoused"][0]["qty"] == 30 and prev["stock_material"] == 5
    assert prev["stock_ccy"] == "USD"
    assert "sales" not in prev          # KHÔNG chép dòng bán sang ngày mới (số phát sinh)
    # HĐ đã ký cũng KHÔNG chép sang — nó tự nối ngày theo vòng đời, chép lại là nhân đôi.
    assert "stock_signed_undelivered" not in prev

    # 3) Hợp đồng ở bảng CŨ không còn vào khối 3 của báo cáo ngày (chốt 02/08/2026) — khối 3 chỉ
    # tính từ `sales_contract`. Số cũ vẫn tra cứu được ở màn "Hợp đồng cũ" (chỉ xem).
    made = client.put("/api/member/stock-contracts", headers=mh, json={
        "company": unit, "code": "HĐ-09/2026", "grade": "SVR 10 / CSR 10", "qty": 12,
        "price": 40, "start_date": y_day, "delivered_date": t_day})
    assert made.status_code == 200
    y_view = client.get(f"/api/member/daily-report?kind=consumption&as_of={y_day}", headers=mh).json()
    assert y_view["entries"][unit]["fields"]["stock_signed_undelivered"]["qty"] == 0

    # Không có ngày nào trước đó → found=false (không dựng số khống).
    empty = client.get(f"/api/member/daily-report/prev-stock?company={unit}&before={y_day}",
                       headers=mh).json()
    assert empty["found"] is False

    # Đơn vị khác không lấy được tồn kho của đơn vị này.
    assert client.get("/api/member/daily-report/prev-stock?company=Đơn vị khác&before=" + t_day,
                      headers=mh).status_code == 403

    _cleanup(h, ["ud_basis"], [unit])


def test_year_plan_open_to_all_units_and_drives_purchase_screen() -> None:
    """Chốt 03/08/2026: Kế hoạch năm mở cho MỌI đơn vị; chính SỐ kế hoạch bật màn Thu mua.

    Không còn cờ bật/tắt theo đơn vị. Quy tắc:
      - chưa khai số  → đơn vị vẫn hiện ở Kế hoạch năm, nhưng KHÔNG có màn Thu mua;
      - khai `0`      → coi như không tổ chức thu mua (vẫn tắt);
      - khai `> 0`    → bật màn Thu mua;
      - năm nay chưa khai thì lấy NĂM GẦN NHẤT đã khai (đầu năm không ai bị mất màn Thu mua).
    """
    h = _admin()
    unit = "_zz_ud_plan_flag"
    year = date.today().year
    client.delete("/api/users/ud_pf", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_pf", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)

    def hq_units() -> list[str]:
        return client.get(f"/api/unit-daily/plan?year={year}", headers=h).json()["units"]

    def my_units() -> list[str]:
        mh = _bearer("ud_pf", "pass123")
        return client.get(f"/api/member/plan?year={year}", headers=mh).json()["units"]

    def has_purchase() -> bool:
        mh = _bearer("ud_pf", "pass123")
        return client.get("/api/auth/me", headers=mh).json()["member_has_purchase_plan"]

    # Chưa khai kế hoạch: vẫn hiện ở Kế hoạch năm (cả HQ lẫn đơn vị), nhưng chưa có màn Thu mua.
    assert unit in hq_units() and unit in my_units()
    assert has_purchase() is False

    # ⚠ Đơn vị CHƯA khai lần nào vẫn phải TỰ KHAI ĐƯỢC. Khoá màn này lại (từng khoá ở frontend tới
    # 06/08/2026) là bẫy vòng tròn: số khai ở đây mới bật màn Thu mua, mà muốn khai thì phải vào
    # được màn — 31 đơn vị trên prod đã kẹt đúng kiểu đó.
    mh0 = _bearer("ud_pf", "pass123")
    assert client.put("/api/member/plan", headers=mh0,
                      json={"year": year, "company": unit, "plan_tonnes": 500}).status_code == 200
    assert has_purchase() is True
    with session_scope() as db:      # trả lại trạng thái "chưa khai" cho các bước sau
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :c"), {"c": unit})
    assert has_purchase() is False

    # Khai 0 = không tổ chức thu mua → vẫn tắt.
    assert client.put("/api/unit-daily/plan", headers=h,
                      json={"year": year, "company": unit, "plan_tonnes": 0}).status_code == 200
    assert has_purchase() is False

    # Khai > 0 → bật màn Thu mua, đơn vị vẫn nằm nguyên trong danh sách Kế hoạch năm.
    assert client.put("/api/unit-daily/plan", headers=h,
                      json={"year": year, "company": unit, "plan_tonnes": 1200}).status_code == 200
    assert has_purchase() is True
    assert unit in hq_units() and unit in my_units()

    # Sang năm sau CHƯA khai → vẫn bật nhờ số của năm gần nhất (đầu năm không mất màn Thu mua).
    from app.services import unit_daily_repo
    assert unit in unit_daily_repo.companies_with_purchase_plan(year + 1)

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :c"), {"c": unit})
    _cleanup(h, ["ud_pf"], [unit])


def test_year_plan_stores_spot_sales_plan() -> None:
    """Kế hoạch TIÊU THỤ cho HĐ chuyến: lưu được và trả về đúng ô (chốt 03/08/2026)."""
    h = _admin()
    unit = "_zz_ud_plan_spot"
    year = date.today().year
    client.post("/api/member-units", json={"name": unit}, headers=h)
    assert client.put("/api/unit-daily/plan", headers=h,
                      json={"year": year, "company": unit, "plan_tonnes": 100,
                            "plan_sales_spot_tonnes": 80}).status_code == 200
    row = client.get(f"/api/unit-daily/plan?year={year}", headers=h).json()["plans"][unit]
    assert row["plan_sales_spot_tonnes"] == 80 and row["plan_tonnes"] == 100

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :c"), {"c": unit})
    _cleanup(h, [], [unit])


def test_stock_contract_history() -> None:
    """Lịch sử hợp đồng: liệt kê CẢ hợp đồng đã giao (đã biến mất khỏi tồn kho ngày) + bộ lọc."""
    h = _admin()
    unit = "_zz_ud_hist"
    today = date.today()
    old_day = (today - timedelta(days=20)).isoformat()
    recent_day = (today - timedelta(days=2)).isoformat()
    for u in ("ud_hist_ed", "ud_hist_mem", "ud_hist_noed"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_hist_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily"]}, headers=h)
    client.post("/api/users", json={"username": "ud_hist_mem", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    eh = _bearer("ud_hist_ed", "pass123")
    mh = _bearer("ud_hist_mem", "pass123")

    # 1 HĐ đã giao (delivered) + 1 HĐ chưa giao (undelivered), khác ngày bắt đầu để test lọc/sắp xếp.
    # Bảng cũ đã đóng băng (không lập mới qua API) → dựng thẳng vào DB như dữ liệu lịch sử có sẵn.
    delivered = _legacy_contract(unit, "HĐ-H1/2026", "RSS 3", 5, old_day, recent_day)
    undelivered = _legacy_contract(unit, "HĐ-H2/2026", "SVR 3L", 8, recent_day, None)

    # HĐ đã giao KHÔNG còn hiện trong danh sách tồn kho hôm nay (hành vi hiện có)...
    todays = client.get(f"/api/unit-daily/stock-contracts?as_of={today.isoformat()}&company={unit}",
                        headers=eh).json()["contracts"]
    assert delivered["id"] not in [c["id"] for c in todays]

    # ...nhưng MÀN LỊCH SỬ vẫn liệt kê đủ cả hai, mới nhất (ngày bắt đầu) trước.
    hist = client.get(f"/api/unit-daily/contracts/history?company={unit}", headers=eh).json()
    ids = [c["id"] for c in hist["contracts"]]
    assert delivered["id"] in ids and undelivered["id"] in ids
    assert ids.index(undelivered["id"]) < ids.index(delivered["id"])
    assert unit in hist["units"]

    # Lọc trạng thái.
    only_delivered = client.get(f"/api/unit-daily/contracts/history?company={unit}&status=delivered",
                                headers=eh).json()["contracts"]
    assert [c["id"] for c in only_delivered] == [delivered["id"]]
    only_undelivered = client.get(f"/api/unit-daily/contracts/history?company={unit}&status=undelivered",
                                  headers=eh).json()["contracts"]
    assert [c["id"] for c in only_undelivered] == [undelivered["id"]]

    # Lọc theo khoảng ngày (Ngày bắt đầu tồn kho) + tìm theo Số HĐ/PL.
    ranged = client.get(
        f"/api/unit-daily/contracts/history?company={unit}&date_from={recent_day}&date_to={recent_day}",
        headers=eh).json()["contracts"]
    assert [c["id"] for c in ranged] == [undelivered["id"]]
    searched = client.get(f"/api/unit-daily/contracts/history?company={unit}&q=H2", headers=eh).json()["contracts"]
    assert [c["id"] for c in searched] == [undelivered["id"]]

    # Thiếu quyền `unit_daily` → 403.
    client.post("/api/users", json={"username": "ud_hist_noed", "password": "pass123", "role": "editor"}, headers=h)
    nh = _bearer("ud_hist_noed", "pass123")
    assert client.get("/api/unit-daily/contracts/history", headers=nh).status_code == 403

    # Đơn vị thành viên: xem được lịch sử của đơn vị mình (kể cả đã giao).
    my_hist = client.get("/api/member/stock-contracts/history", headers=mh).json()
    my_ids = [c["id"] for c in my_hist["contracts"]]
    assert delivered["id"] in my_ids and undelivered["id"] in my_ids

    client.delete("/api/users/ud_hist_noed", headers=h)
    _cleanup(h, ["ud_hist_ed", "ud_hist_mem"], [unit])


def test_contract_docs_multi_file() -> None:
    """Mỗi ô đính kèm giữ NHIỀU file, đồng thời vẫn ghi cặp khoá cũ = file ĐẦU.

    Điểm quan trọng: bản ghi CŨ (chỉ có `file`/`filename`) đọc lên phải tự thành danh sách 1 file —
    nhờ vậy dữ liệu đã lưu trên production không cần chuyển đổi.
    """
    h = _admin()
    unit = "_zz_ud_docs"
    today = date.today().isoformat()
    day = (date.today() - timedelta(days=1)).isoformat()
    client.delete("/api/users/ud_docs_ed", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_docs_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily"]}, headers=h)
    eh = _bearer("ud_docs_ed", "pass123")

    # ── Hợp đồng tồn kho (bảng CŨ, chỉ SỬA được): gửi DANH SÁCH nhiều file ────────────────
    d1 = _legacy_contract(unit, "HĐ-D1", "RSS 3", 5, day, None)
    many = client.put("/api/unit-daily/stock-contracts", headers=eh, json={
        "id": d1["id"],
        "company": unit, "code": "HĐ-D1", "grade": "RSS 3", "qty": 5, "price": 40,
        "start_date": day,
        "files": [{"file": "a.pdf", "filename": "hop-dong.pdf"},
                  {"file": "b.pdf", "filename": "phu-luc.pdf"}],
    }).json()["contract"]
    assert [d["file"] for d in many["files"]] == ["a.pdf", "b.pdf"]
    assert many["file"] == "a.pdf" and many["filename"] == "hop-dong.pdf"  # khoá cũ = file đầu

    # Đọc lại từ DB vẫn đủ 2 file.
    got = client.get(f"/api/unit-daily/stock-contracts?as_of={today}&company={unit}",
                     headers=eh).json()["contracts"]
    assert [d["file"] for d in next(c for c in got if c["id"] == many["id"])["files"]] == ["a.pdf", "b.pdf"]

    # ── Client CŨ chỉ gửi cặp khoá phẳng → server tự dựng thành danh sách 1 file ──────────
    d2 = _legacy_contract(unit, "HĐ-D2", "SVR 3L", 3, day, None)
    legacy = client.put("/api/unit-daily/stock-contracts", headers=eh, json={
        "id": d2["id"],
        "company": unit, "code": "HĐ-D2", "grade": "SVR 3L", "qty": 3, "price": 41,
        "start_date": day, "file": "old.pdf", "filename": "ban-cu.pdf",
    }).json()["contract"]
    assert legacy["files"] == [{"file": "old.pdf", "filename": "ban-cu.pdf"}]

    # ── Biểu tiêu thụ: ô "bộ Hợp đồng" nhiều file · ô "hoá đơn" nhập kiểu CŨ ─────────────
    assert client.put("/api/unit-daily/report", headers=eh, json={
        "kind": "consumption", "company": unit, "as_of": today, "fields": {
            "sales": [{"contract": "long_term", "channel": "export", "grade": "RSS 3",
                       "qty": 1, "price": 40,
                       "files": [{"file": "c1.pdf", "filename": "hd.pdf"},
                                 {"file": "c2.pdf", "filename": "pl.pdf"},
                                 {"file": "c2.pdf", "filename": "trung-lap.pdf"}],  # trùng → bỏ
                       "inv_file": "inv.pdf", "inv_filename": "hoa-don.pdf"}],
            "sales_ccy": "VND", "stock_ccy": "VND",
        }}).status_code == 200
    tl = client.get("/api/unit-daily/timeline?kind=consumption&days=3", headers=eh).json()
    ln = next(e for e in tl["entries"] if e["company"] == unit)["fields"]["sales"][0]
    assert [d["file"] for d in ln["files"]] == ["c1.pdf", "c2.pdf"]   # khử trùng lặp theo tên lưu
    assert ln["file"] == "c1.pdf" and ln["filename"] == "hd.pdf"
    assert ln["inv_files"] == [{"file": "inv.pdf", "filename": "hoa-don.pdf"}]  # ô cũ → danh sách
    assert ln["wh_files"] == [] and ln["wh_file"] is None                       # ô trống vẫn trống

    client.delete("/api/users/ud_docs_ed", headers=h)
    _cleanup(h, ["ud_docs_ed"], [unit])


def test_period_report_keeps_last_real_stock() -> None:
    """Đơn vị nhập dòng bán cho ngày mới nhưng CHƯA chốt tồn → báo cáo kỳ giữ lần chốt tồn gần nhất.

    Trước đây báo cáo lấy bản ghi ngày cuối vô điều kiện: bản ghi chỉ có dòng bán làm tồn kho về 0
    (hiểu nhầm là hết hàng) và tổng toàn Tập đoàn hụt đúng phần tồn của các đơn vị đó.
    """
    h = _admin()
    unit = "_zz_ud_stock"
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    client.delete("/api/users/ud_stock_ed", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_stock_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily"]}, headers=h)
    eh = _bearer("ud_stock_ed", "pass123")

    # Hôm qua: có chốt tồn kho (khối 1 + khối 2 = 24 tấn) + tồn nguyên liệu.
    assert client.put("/api/unit-daily/report", headers=eh, json={
        "kind": "consumption", "company": unit, "as_of": yesterday, "fields": {
            "sales": [{"contract": "long_term", "channel": "export", "grade": "RSS 3",
                       "qty": 5, "price": 40}],
            "sales_ccy": "VND", "stock_ccy": "VND", "revenue": 200_000_000,
            "stock_not_warehoused": [{"grade": "RSS 3", "qty": 9}],
            "stock_warehoused": [{"grade": "RSS 3", "qty": 15}],
            "stock_material": 3.5,
        }}).status_code == 200

    # Hôm nay: CHỈ nhập dòng bán, khối tồn kho để trống (chưa cập nhật tồn).
    assert client.put("/api/unit-daily/report", headers=eh, json={
        "kind": "consumption", "company": unit, "as_of": today, "fields": {
            "sales": [{"contract": "spot", "channel": "domestic", "grade": "RSS 3",
                       "qty": 2, "price": 41}],
            "sales_ccy": "VND", "stock_ccy": "VND", "revenue": 82_000_000,
            "stock_not_warehoused": [], "stock_warehoused": [],
        }}).status_code == 200

    pr = client.get("/api/unit-daily/period-report?kind=consumption"
                    f"&date_from={yesterday}&date_to={today}", headers=eh)
    assert pr.status_code == 200
    row = next(r for r in pr.json()["rows"] if r["company"] == unit)
    # Tồn kho giữ ảnh chụp hôm qua và nói rõ ngày đã lấy. Dòng bán kiểu cũ KHÔNG vào tiêu thụ nữa
    # (chốt 02/08/2026) — nhưng bản ghi chỉ có dòng bán vẫn KHÔNG được kéo tồn kho về 0.
    assert row["total_consumption"] is None
    assert row["stock_finished"] == 24.0 and row["stock_material"] == 3.5
    assert row["stock_as_of"] == yesterday and row["last_day"] == today
    assert row["stock_by_grade"]["RSS 3"] == 24.0

    # Khớp màn Thống kê tồn kho (cùng quy tắc `has_stock`) — hai màn không được lệch nhau.
    # Màn đó chốt theo NGÀY nên phải chốt vào ĐÚNG ngày đơn vị khai tồn: từ 21/08/2026 hôm nay chỉ
    # có dòng bán thì không còn được đắp số hôm qua sang (đơn vị phải tick "không phát sinh").
    st = client.get("/api/unit-daily/analytics/stock?group_by=company"
                    f"&as_of={yesterday}", headers=eh).json()
    srow = next(r for r in st["rows"] if r["key"] == unit)
    assert srow["total"] == row["stock_finished"] and srow["as_of"] == row["stock_as_of"]

    client.delete("/api/users/ud_stock_ed", headers=h)
    _cleanup(h, ["ud_stock_ed"], [unit])


def test_move_report_date_respects_edit_window() -> None:
    """Đổi ngày bản ghi nhập nhầm: chuyển nguyên nội dung + đơn giá, vẫn kẹp trong cửa sổ sửa."""
    from app.core.market_meta import PURCHASE_SOURCE_UNIT
    from app.services import price_repo

    h = _admin()
    unit = "_zz_ud_move"
    today = date.today().isoformat()
    wrong = (date.today() - timedelta(days=2)).isoformat()      # nhập nhầm vào ngày này
    right = (date.today() - timedelta(days=1)).isoformat()      # ngày đúng
    old = (date.today() - timedelta(days=60)).isoformat()       # ngoài cửa sổ sửa
    _cleanup(h, ["ud_mv_mem", "ud_mv_ed"], [unit])   # dọn rác của lần chạy hỏng trước (nếu có)

    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_mv_mem", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    client.post("/api/users", json={"username": "ud_mv_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily"]}, headers=h)
    mh, eh = _bearer("ud_mv_mem", "pass123"), _bearer("ud_mv_ed", "pass123")

    body = {"kind": "purchase", "company": unit, "as_of": wrong,
            "fields": {"latex_wet": 11.5, "coagulum": 4}}
    assert client.put("/api/member/daily-report", json=body, headers=mh).status_code == 200
    # Đơn giá nhập trong biểu Thu mua nằm ở kho "Giá mủ nguyên liệu" (lớp đơn vị tự khai).
    assert client.put("/api/member/prices", headers=mh, json={
        "company": unit, "as_of": wrong, "price_type": "purchase", "price": 555}).status_code == 200

    move = {"kind": "purchase", "company": unit, "as_of": wrong, "to_date": right}
    # Ngày mới trong tương lai / ngoài cửa sổ → chặn TRƯỚC khi đụng dữ liệu.
    future = (date.today() + timedelta(days=1)).isoformat()
    assert client.put("/api/member/daily-report/move-date",
                      json={**move, "to_date": future}, headers=mh).status_code == 400
    assert client.put("/api/member/daily-report/move-date",
                      json={**move, "to_date": old}, headers=mh).status_code == 403
    # Đơn vị khác → 403 (member không đụng được đơn vị không được gán).
    assert client.put("/api/member/daily-report/move-date",
                      json={**move, "company": "khac"}, headers=mh).status_code == 403

    ok = client.put("/api/member/daily-report/move-date", json=move, headers=mh)
    assert ok.status_code == 200 and ok.json()["moved_prices"] == ["purchase"]

    # Nội dung nguyên vẹn ở ngày mới, ngày cũ sạch — và đơn giá đi theo.
    got = client.get(f"/api/member/daily-report?kind=purchase&as_of={right}", headers=mh).json()
    assert got["entries"][unit]["fields"]["latex_wet"] == 11.5
    assert client.get(f"/api/member/daily-report?kind=purchase&as_of={wrong}",
                      headers=mh).json()["entries"][unit] is None
    assert price_repo.purchase_by_company_on_date(right, "purchase", PURCHASE_SOURCE_UNIT)[unit] == 555
    assert unit not in price_repo.purchase_by_company_on_date(wrong, "purchase", PURCHASE_SOURCE_UNIT)

    # Ngày đích đã có số liệu → 409, KHÔNG gộp/ghi đè.
    assert client.put("/api/member/daily-report", headers=mh, json={
        **body, "as_of": wrong, "fields": {"latex_wet": 2}}).status_code == 200
    dup = client.put("/api/member/daily-report/move-date", json=move, headers=mh)
    assert dup.status_code == 409 and "đã có số liệu" in dup.json()["detail"]
    assert client.get(f"/api/member/daily-report?kind=purchase&as_of={wrong}",
                      headers=mh).json()["entries"][unit]["fields"]["latex_wet"] == 2

    # Chuyên viên: cùng luật cửa sổ (bản ghi nằm ở ngày quá cũ → 403).
    assert client.put("/api/unit-daily/report", headers=eh, json={
        "kind": "consumption", "company": unit, "as_of": right,
        "fields": {"sales": [{"contract": "spot", "channel": "domestic", "grade": "RSS 3",
                              "qty": 3, "price": 40}], "sales_ccy": "VND"}}).status_code == 200
    assert client.put("/api/unit-daily/report/move-date", headers=eh, json={
        "kind": "consumption", "company": unit, "as_of": right, "to_date": old}).status_code == 403
    moved = client.put("/api/unit-daily/report/move-date", headers=eh, json={
        "kind": "consumption", "company": unit, "as_of": right, "to_date": today})
    assert moved.status_code == 200 and moved.json()["moved_prices"] == []
    tl = client.get("/api/unit-daily/timeline?kind=consumption&days=10", headers=eh).json()
    assert [(e["as_of"], e["company"]) for e in tl["entries"] if e["company"] == unit] == [(today, unit)]

    # Nhật ký hoạt động ghi lại việc đổi ngày (truy vết được ai đổi, từ ngày nào sang ngày nào).
    log = client.get(f"/api/audit?entity=unit_daily&company={unit}", headers=h)
    assert log.status_code == 200
    assert any("Đổi ngày" in (r.get("note") or "") for r in log.json()["items"])

    for u in ("ud_mv_mem", "ud_mv_ed"):
        client.delete(f"/api/users/{u}", headers=h)
    _cleanup(h, ["ud_mv_mem", "ud_mv_ed"], [unit])


def test_consumption_timeline_is_paged_but_purchase_is_not() -> None:
    """Timeline Tiêu thụ–Tồn kho cắt trang ở server; Thu mua trả trọn khoảng.

    Bản ghi tiêu thụ mang cả mảng dòng bán + danh sách file nên phải cắt trang. Biểu Thu mua thì
    KHÔNG được cắt: bảng có dòng "Lũy kế (khoảng đang xem)" — cắt trang là lũy kế báo sai.
    """
    h = _admin()
    unit = "_zz_ud_page"
    client.delete("/api/users/ud_page", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_page", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_page", "pass123")
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(5)]
    for i, d in enumerate(days):
        for kind, fields in (("consumption", {"stock_material": 10.0 + i}),
                             ("purchase", {"latex_wet": 5.0 + i})):
            assert client.put("/api/member/daily-report", headers=mh,
                              json={"kind": kind, "company": unit, "as_of": d,
                                    "fields": fields}).status_code == 200

    got = client.get("/api/member/daily-report/timeline?kind=consumption&days=30&page=1&page_size=2",
                     headers=mh).json()
    assert got["paged"] is True and len(got["entries"]) == 2 and got["total"] == 5
    page2 = client.get("/api/member/daily-report/timeline?kind=consumption&days=30&page=2&page_size=2",
                       headers=mh).json()
    assert [e["as_of"] for e in page2["entries"]] == days[2:4]      # ngày giảm dần, không lặp trang 1

    whole = client.get("/api/member/daily-report/timeline?kind=purchase&days=30&page_size=2",
                       headers=mh).json()
    assert whole["paged"] is False and len(whole["entries"]) == 5 == whole["total"]

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c"), {"c": unit})
    client.delete("/api/users/ud_page", headers=h)
    client.delete(f"/api/member-units/{unit}", headers=h)


def test_consumption_timeline_totals_come_from_contracts_not_the_old_declared_arrays() -> None:
    """Lũy kế biểu Tồn kho: tiêu thụ lấy TỪ HỢP ĐỒNG, tồn kho lấy ẢNH CHỤP MỚI NHẤT.

    Nhóm cột "Tiêu thụ (số cũ đã khai)" đã gỡ 20/08/2026: nó đọc ô `revenue` chốt cứng lúc lưu
    phiếu nên không đổi theo khi hợp đồng được sửa (đợt sửa đơn giá 10/08/2026 chỉnh hợp đồng mà ô
    đó vẫn giữ số sai gấp 1.000 lần). Test này khoá hai điều: mảng `sales`/`sales_own`/`revenue` cũ
    KHÔNG được cộng vào đâu nữa, và số tiêu thụ phải khớp các lần giao.

    Cộng tồn kho qua các ngày là đếm đi đếm lại cùng một lô hàng. Bảng lại cắt trang ở server nên
    tổng phải do server cộng trên cả khoảng; tổng của trang 2 mà khác trang 1 là báo sai.
    """
    h = _admin()
    unit = "_zz_ud_totals"
    _wipe_unit(unit)                      # lần chạy trước hỏng giữa chừng thì dọn lại cho sạch
    client.post("/api/member-units", json={"name": unit}, headers=h)
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(3)]

    # Số CŨ trong phiếu — cố ý để lệch hẳn (14 tấn / 6 tỷ) để thấy rõ nó KHÔNG còn được cộng.
    payloads = [
        {"revenue": 3_000_000_000.0, "stock_warehoused": [{"grade": "SVR 3L Mix", "qty": 100.0}],
         "sales": [{"qty": 5.0, "channel": "export"}]},
        {"revenue": 2_000_000_000.0, "stock_warehoused": [{"grade": "SVR 3L Mix", "qty": 80.0}],
         "sales": [{"qty": 7.0, "channel": "domestic"}]},
        {"revenue": 1_000_000_000.0, "sales_own": [{"qty": 2.0, "channel": "export"}]},
    ]
    for d, fields in zip(days, payloads, strict=True):
        assert client.put("/api/unit-daily/report", headers=h,
                          json={"kind": "consumption", "company": unit, "as_of": d,
                                "fields": fields}).status_code == 200

    # Số HIỆN HÀNH: 2 lần giao của một hợp đồng — 5 tấn XK (ngày mới nhất) + 7 tấn nội tiêu.
    cus = client.put("/api/customers", json={"company": unit, "name": "KH tổng"},
                     headers=h).json()["id"]
    line = lambda qty: {"grade": "SVR 10 / CSR 10", "qty": qty, "price": 40.0, "ccy": "VND"}  # noqa: E731
    parent = client.put("/api/sales-contracts", json={
        "company": unit, "code": "HD-TOTALS", "delivery_type": "multi", "contract_type": "spot",
        "customer_id": cus, "sign_date": days[2], "lines": [line(100.0)]}, headers=h).json()["contract"]
    for code, d, channel, qty in (("PL-1", days[0], "export", 5.0), ("PL-2", days[1], "domestic", 7.0)):
        r = client.put("/api/sales-contracts", json={
            "company": unit, "parent_id": parent["id"], "code": code, "delivered_at": d,
            "channel": channel, "lines": [line(qty)]}, headers=h)
        assert r.status_code == 200, r.text

    # Gọi thẳng `timeline_page` với BỘ LỌC ĐƠN VỊ: endpoint của chuyên viên không lọc đơn vị nên
    # trên máy có sẵn dữ liệu thật, tổng sẽ gộp cả Tập đoàn và test không nói lên điều gì.
    from app.routers.unit_daily import timeline_page
    page1 = timeline_page("consumption", days[2], days[0], [unit], 1, 2)
    t = page1["totals"]
    # Khoá cũ phải BIẾN MẤT hẳn — còn sót là nhóm cột cũ đã lẻn về.
    for gone in ("total_consumption", "qty_export", "qty_domestic", "revenue", "avg_price"):
        assert gone not in t, f"khoá cũ {gone} vẫn còn trong lũy kế"
    assert t["c_qty"] == pytest.approx(12.0)                      # 5 + 7 từ hợp đồng, KHÔNG phải 14
    assert t["c_qty_export"] == pytest.approx(5.0)
    assert t["c_qty_domestic"] == pytest.approx(7.0)
    assert t["c_revenue"] == pytest.approx(0.48)                  # 12 × 40 triệu = 0,48 tỷ (≠ 6 tỷ)
    assert t["c_avg_price"] == pytest.approx(40.0)
    # Tồn kho = ảnh chụp ngày mới nhất CÓ tồn, không phải 100 + 80.
    assert t["stock_warehoused_t"] == pytest.approx(100.0)
    assert t["stock_finished_t"] == pytest.approx(100.0)
    assert t["stock_as_of"] == days[0]

    # Từng DÒNG cũng mang số theo hợp đồng của đúng (đơn vị × ngày) đó.
    row = next(e for e in page1["entries"] if e["as_of"] == days[0])
    assert row["fields"]["c_qty"] == pytest.approx(5.0)
    assert row["fields"]["c_qty_export"] == pytest.approx(5.0)
    assert row["fields"]["c_qty_domestic"] is None                # ngày đó không bán nội tiêu

    page2 = timeline_page("consumption", days[2], days[0], [unit], 2, 2)
    assert len(page2["entries"]) == 1                             # trang 2 chỉ còn 1 dòng…
    assert page2["totals"] == t                                   # …nhưng tổng vẫn của cả khoảng

    _wipe_unit(unit)
    client.delete(f"/api/member-units/{unit}", headers=h)


def test_grade_catalog_is_one_list_shared_by_every_entry_screen() -> None:
    """Thu mua · tồn kho · tiêu thụ phải CÙNG một danh mục chủng loại, và web không được lệch.

    Trước 08/08/2026 mỗi màn đọc một hằng số khác nhau (tồn kho/thu mua thiếu 2 loại mủ nguyên
    liệu mà hợp đồng bán lại có) nên cùng một đơn vị nhìn thấy 3 danh mục — test này chốt lại.
    """
    import re
    from pathlib import Path

    from app.core.market_meta import UNIT_GRADES
    from app.services import unit_daily_excel_io, unit_period_report

    # "Mủ ngoại lệ" nằm NGAY DƯỚI "Chủng loại khác" (khách chốt 08/08/2026) — thứ tự là thứ tự
    # hiện trên ô chọn, đổi chỗ là đổi trải nghiệm nhập liệu nên phải khoá lại.
    assert UNIT_GRADES[UNIT_GRADES.index("Chủng loại khác") + 1] == "Mủ ngoại lệ"
    # "RSS 5" ngay dưới "RSS 1" (thêm 13/09/2026) — chỉ ở danh mục nhập liệu, không có giá sàn.
    assert UNIT_GRADES[UNIT_GRADES.index("RSS 1") + 1] == "RSS 5"
    assert len(UNIT_GRADES) == len(set(UNIT_GRADES)), "Danh mục chủng loại có mục trùng."

    # Mọi nơi phía backend dùng đúng danh sách đó (biểu Excel, báo cáo kỳ).
    assert unit_daily_excel_io.GRADES == list(UNIT_GRADES)
    assert unit_period_report.GRADES == list(UNIT_GRADES)

    # …và 3 endpoint cấp danh mục cho 3 màn nhập liệu đều trả về đúng nó.
    h = _admin()
    for url in ("/api/sales-contracts/meta", "/api/unit-daily/contracts/history",
                "/api/unit-daily/analytics/filters"):
        got = client.get(url, headers=h)
        assert got.status_code == 200, f"{url}: {got.text}"
        assert got.json()["grades"] == list(UNIT_GRADES), f"{url} trả danh mục lệch."

    # Web giữ bản sao riêng (form dựng ngay khi mở, không chờ gọi API) → so thẳng từng phần tử.
    src = Path(__file__).resolve().parents[3] / "apps/web/src/lib/unit-daily-consumption.ts"
    block = re.search(r"export const GRADES: string\[\] = \[(.*?)\];", src.read_text("utf-8"),
                      re.S).group(1)
    assert re.findall(r'"([^"]+)"', block) == list(UNIT_GRADES), (
        "Danh mục chủng loại ở web đã lệch khỏi UNIT_GRADES — sửa cả 2 nơi.")


def test_year_plan_keeps_revenue_target_in_ty_dong() -> None:
    """Kế hoạch DOANH THU năm (TỶ ĐỒNG) lưu được, để trống là xoá chỉ tiêu.

    Đơn vị tính là tỷ đồng — cùng đơn vị `revenue_ty` của báo cáo kỳ, nên "% thực hiện" là phép
    chia cùng đơn vị chứ không phải quy đổi (chỗ dự án đã sai nhiều lần).
    """
    h = _admin()
    unit = "_zz_ud_plan_rev"
    year = date.today().year
    client.post("/api/member-units", json={"name": unit}, headers=h)
    body = {"year": year, "company": unit, "plan_tonnes": 1000,
            "plan_sales_spot_tonnes": 300, "plan_revenue_ty": 250.5}
    assert client.put("/api/unit-daily/plan", json=body, headers=h).status_code == 200
    row = client.get(f"/api/unit-daily/plan?year={year}", headers=h).json()["plans"][unit]
    assert row["plan_revenue_ty"] == pytest.approx(250.5)
    # Các ô cũ không bị đụng khi thêm ô mới.
    assert row["plan_tonnes"] == 1000 and row["plan_sales_spot_tonnes"] == 300

    client.put("/api/unit-daily/plan", json={**body, "plan_revenue_ty": None}, headers=h)
    again = client.get(f"/api/unit-daily/plan?year={year}", headers=h).json()["plans"][unit]
    assert again["plan_revenue_ty"] is None

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_purchase_plan WHERE company = :c"), {"c": unit})
    _cleanup(h, [], [unit])


def test_year_plan_stores_exploit_target_and_blank_clears_it() -> None:
    """Kế hoạch KHAI THÁC năm (tấn, chốt 24/09/2026): ghi → đọc lại → để trống = NULL.

    Đi qua CẢ HAI cửa ghi: chuyên viên (`/api/unit-daily/plan`) và đơn vị tự khai
    (`/api/member/plan`); lãnh đạo đơn vị chỉ xem. Ô mới không làm lệch ô cũ, KHÔNG phải công tắc
    màn Thu mua (công tắc vẫn là kế hoạch THU MUA), và báo cáo kỳ chỉ hiện chỉ tiêu — chưa có số
    thực hiện khai thác nên không có % nào đi kèm.
    """
    from app.services import unit_daily_repo, unit_period_report

    h = _admin()
    unit = "_zz_ud_plan_exploit"
    year = date.today().year
    users = ["ud_px", "ud_px_lead"]
    for u in users:
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    for u, role in zip(users, ("member", "leader")):
        client.post("/api/users", json={"username": u, "password": "pass123", "role": role,
                                        "member_units": [unit]}, headers=h)
    mh, lh = _bearer("ud_px", "pass123"), _bearer("ud_px_lead", "pass123")

    def row_of(path: str, hdr: dict[str, str]) -> dict:
        return client.get(f"{path}?year={year}", headers=hdr).json()["plans"][unit]

    body = {"year": year, "company": unit, "plan_exploit_tonnes": 3500.5, "plan_tonnes": 1200}
    assert client.put("/api/unit-daily/plan", json=body, headers=h).status_code == 200
    row = row_of("/api/unit-daily/plan", h)
    assert row["plan_exploit_tonnes"] == pytest.approx(3500.5) and row["plan_tonnes"] == 1200

    # Đơn vị tự sửa chỉ tiêu của mình; lãnh đạo đơn vị đọc được nhưng không ghi được.
    assert client.put("/api/member/plan", json={**body, "plan_exploit_tonnes": 4000},
                      headers=mh).status_code == 200
    assert row_of("/api/member/plan", mh)["plan_exploit_tonnes"] == 4000
    assert client.put("/api/member/plan", json={**body, "plan_exploit_tonnes": 1},
                      headers=lh).status_code == 403
    assert row_of("/api/member/plan", lh)["plan_exploit_tonnes"] == 4000

    # Để trống = XOÁ chỉ tiêu (NULL trong DB), không giữ số cũ; các ô khác nguyên vẹn.
    assert client.put("/api/member/plan", json={**body, "plan_exploit_tonnes": None},
                      headers=mh).status_code == 200
    with session_scope() as db:
        raw = db.execute(text("SELECT plan_exploit_tonnes, plan_tonnes FROM unit_purchase_plan "
                              "WHERE year = :y AND company = :c"), {"y": year, "c": unit}).one()
    assert raw.plan_exploit_tonnes is None and raw.plan_tonnes == 1200

    # Chỉ khai khai thác (xoá thu mua bằng null TƯỜNG MINH — khoá không gửi thì giữ số cũ)
    # → KHÔNG bật màn Thu mua.
    assert client.put("/api/unit-daily/plan", headers=h,
                      json={"year": year, "company": unit, "plan_exploit_tonnes": 999,
                            "plan_tonnes": None}).status_code == 200
    assert unit not in unit_daily_repo.companies_with_purchase_plan(year)

    # Báo cáo kỳ (biểu Thu mua) trả kèm chỉ tiêu, không bịa % thực hiện khai thác.
    rep = unit_period_report.period_report("purchase", f"{year}-01-01", f"{year}-01-31",
                                           companies=[unit])
    got = next(r for r in rep["rows"] if r["company"] == unit)
    assert got["plan_exploit_tonnes"] == 999
    assert not [k for k in got if k.startswith("pct_") and "exploit" in k]

    _cleanup(h, users, [unit])


def test_year_plan_put_keeps_unsent_keys_and_rejects_nan() -> None:
    """PUT /plan chỉ ghi khoá CÓ trong body; null tường minh = xoá; NaN/Infinity/số âm → 422.

    Hồi quy review 24/09/2026: trình duyệt còn giữ bản web cũ (chưa biết ô khai thác) sửa bất kỳ ô
    nào là xoá oan chỉ tiêu khai thác người khác vừa khai; còn "NaN" lọt xuống DB làm hỏng JSON
    của báo cáo kỳ, nhật ký và bản lưu tuần.
    """
    h = _admin()
    unit, user = "_zz_ud_plan_partial", "ud_pp"
    year = date.today().year
    client.delete(f"/api/users/{user}", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": user, "password": "pass123", "role": "member",
                                    "member_units": [unit]}, headers=h)
    mh = _bearer(user, "pass123")
    doors = (("/api/unit-daily/plan", h), ("/api/member/plan", mh))

    def row() -> dict:
        return client.get(f"/api/unit-daily/plan?year={year}", headers=h).json()["plans"][unit]

    try:
        full = {"year": year, "company": unit, "plan_exploit_tonnes": 2500, "plan_tonnes": 800,
                "plan_revenue_ty": 12.5}
        assert client.put("/api/unit-daily/plan", json=full, headers=h).status_code == 200

        # Body y như bản web CŨ (6 ô, chưa có khai thác/doanh thu) → 2 ô vắng mặt giữ nguyên.
        old_web = {"year": year, "company": unit, "plan_tonnes": 900, "signed_lt_tonnes": None,
                   "carry_lt_tonnes": None, "carry_spot_tonnes": None, "plan_sales_spot_tonnes": 300}
        for path, hdr in doors:
            assert client.put(path, json=old_web, headers=hdr).status_code == 200, path
            got = row()
            assert got["plan_exploit_tonnes"] == 2500, path
            assert got["plan_revenue_ty"] == pytest.approx(12.5), path
            assert got["plan_tonnes"] == 900 and got["plan_sales_spot_tonnes"] == 300

        # null TƯỜNG MINH vẫn là xoá — và chỉ xoá đúng ô đó.
        assert client.put("/api/member/plan", headers=mh,
                          json={"year": year, "company": unit,
                                "plan_exploit_tonnes": None}).status_code == 200
        got = row()
        assert got["plan_exploit_tonnes"] is None and got["plan_tonnes"] == 900

        # NaN / Infinity dạng chuỗi, số âm → 422 ở cả 2 cửa. Literal JSON NaN (trình duyệt không bao
        # giờ gửi — JSON.stringify(NaN) = null) cũng bị từ chối; FastAPI không JSON hoá nổi `nan`
        # trong câu báo 422 nên trả 500 — không ghi gì là đủ ở đây.
        raw_client = TestClient(app, raise_server_exceptions=False)
        for path, hdr in doors:
            for bad, via in (('"NaN"', client), ('"-inf"', client), ("-1", client),
                             ("NaN", raw_client), ("Infinity", raw_client)):
                r = via.put(path, headers={**hdr, "Content-Type": "application/json"},
                            content=f'{{"year": {year}, "company": "{unit}", "plan_tonnes": {bad}}}')
                assert r.status_code == 422 if via is client else r.status_code >= 400, (path, bad)
        assert row()["plan_tonnes"] == 900
    finally:
        _cleanup(h, [user], [unit])


def test_lace_purchase_saves_its_tonnage_and_its_own_price_slot() -> None:
    """MỦ DÂY (chốt 28/08/2026) — loại mủ nguyên liệu thứ ba của biểu Thu mua.

    Khai y hệt mủ nước / mủ chén: MỘT ô sản lượng theo tấn quy khô + một ô đơn giá. Kiểm 3 điều
    dễ hỏng nhất khi thêm một loại mủ vào biểu:
      1. ô sản lượng `lace` lọt qua allowlist payload — sót là đơn vị gõ xong, lưu xong, mở lại
         thấy trống;
      2. đơn giá đi vào ĐÚNG ô riêng `purchase_lace` của kho "Giá mủ nguyên liệu" với nhãn
         đồng/độ DRC — dùng nhầm ô của mủ nước/mủ chén là ghi đè giá loại khác;
      3. báo cáo kỳ cộng sản lượng mủ dây vào tổng thu mua.
    """
    h = _admin()
    unit = "_zz_ud_lace"
    t_day = date.today().isoformat()
    client.delete("/api/users/ud_lace", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_lace", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_lace", "pass123")

    assert client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": unit, "as_of": t_day,
        "fields": {"latex_wet": 20, "lace": 15.5}}).status_code == 200
    saved = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}",
                       headers=mh).json()["entries"][unit]["fields"]
    assert saved["lace"] == 15.5
    # Biểu Thu mua KHÔNG nhận ô "chưa quy khô" (chốt 29/08/2026) — allowlist phải loại nó ra.
    assert "lace_raw" not in saved

    assert client.put("/api/member/prices", headers=mh, json={
        "company": unit, "as_of": t_day, "price_type": "purchase_lace",
        "price": 260}).status_code == 200
    with session_scope() as db:
        row = db.execute(text(
            "SELECT price, unit FROM fact_price WHERE grade = :g AND price_type = 'purchase_lace' "
            "AND as_of = CAST(:d AS date) ORDER BY ingested_at DESC LIMIT 1"),
            {"g": unit, "d": t_day}).mappings().first()
    assert row is not None and float(row["price"]) == 260 and row["unit"] == "đồng/độ DRC"
    # Đơn giá mủ dây KHÔNG được lọt vào ô của mủ nước — hai loại đọc ra hai con số khác nhau.
    px = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}",
                    headers=mh).json()["prices"][unit]
    assert px["lace"] == 260 and px["latex"] is None

    # Báo cáo tổng hợp là màn của chuyên viên (đơn vị thành viên không có endpoint này).
    pr = client.get(f"/api/unit-daily/period-report?kind=purchase&date_from={t_day}&date_to={t_day}",
                    headers=h).json()
    row = next(r for r in pr["rows"] if r["company"] == unit)
    assert row["lace"] == 15.5
    assert row["total_purchase"] == pytest.approx(35.5)   # 20 mủ nước + 15,5 mủ dây
    assert row["price_lace_avg"] == pytest.approx(260)

    _cleanup(h, ["ud_lace"], [unit])


def test_stock_totals_drop_merged_units_and_flag_stale_snapshots() -> None:
    """Dòng "Lũy kế" của biểu Tồn kho: bỏ đơn vị đã sáp nhập, và nói ra số đã cũ.

    Hai lỗi được khoá lại ở đây (phát hiện 06/09/2026, khi đối chiếu 4 màn tồn kho trên prod):

    1. Luật sáp nhập trước đó chỉ có ở Thống kê tồn kho và Báo cáo tổng hợp — dòng lũy kế này vẫn
       cộng ảnh chụp cuối của đơn vị cũ, tức đếm hai lần chính lô hàng mà đơn vị nhận đã khai chung.
    2. Khoảng mặc định của bảng là 90 ngày và mỗi đơn vị lấy ảnh chụp mới nhất của mình, nên trong
       tổng có thể lẫn số của đơn vị đã lâu không nộp mà nhãn chỉ khoe ngày mới nhất.
    """
    from app.services import member_unit_merge, member_unit_repo, unit_daily_repo
    from app.services import unit_daily_timeline_totals as tt

    old, new = "_zz_ud_merge_cu", "_zz_ud_merge_moi"
    today = date.today()
    d_old = (today - timedelta(days=20)).isoformat()      # ảnh chụp CŨ của đơn vị bị sáp nhập
    d_now = today.isoformat()
    d_from = (today - timedelta(days=90)).isoformat()

    def _cleanup() -> None:
        for u in (old, new):
            _wipe_unit(u)
        with session_scope() as db:
            db.execute(text("UPDATE member_unit SET merged_into = NULL, merged_at = NULL "
                            "WHERE name = ANY(:u)"), {"u": [old, new]})
            db.execute(text("DELETE FROM member_unit WHERE name = ANY(:u)"), {"u": [old, new]})

    _cleanup()
    try:
        for u in (old, new):
            member_unit_repo.add_unit(u)
        unit_daily_repo.upsert("consumption", d_old, old,
                               {"stock_warehoused": [{"grade": "SVR 10", "qty": 60.0}]}, "test")
        unit_daily_repo.upsert("consumption", d_now, new,
                               {"stock_warehoused": [{"grade": "SVR 10", "qty": 100.0}]}, "test")

        apart = tt.consumption_totals(d_from, d_now, [old, new])
        assert apart["stock_finished_t"] == pytest.approx(160.0)   # chưa sáp nhập → cộng cả hai
        assert apart["stock_units"] == 2
        assert apart["stock_stale_units"] == 1                     # ảnh chụp 20 ngày > ngưỡng
        assert apart["stock_oldest_as_of"] == d_old
        assert apart["stock_as_of"] == d_now                       # nhãn cũ chỉ khoe ngày mới nhất

        member_unit_merge.merge(old, new, (today - timedelta(days=15)).isoformat())
        after = tt.consumption_totals(d_from, d_now, [old, new])
        assert after["stock_finished_t"] == pytest.approx(100.0)   # kho cũ đã nằm trong số bên nhận
        assert after["stock_units"] == 1
        assert after["stock_stale_units"] is None
    finally:
        _cleanup()
