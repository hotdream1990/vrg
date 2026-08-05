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
    assert pl.json()["plans"][unit] == {"plan_tonnes": 2000, "signed_lt_tonnes": 1500,
                                        "carry_lt_tonnes": 40, "carry_spot_tonnes": 15,
                                        "plan_sales_spot_tonnes": None}

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
    # Tiêu thụ chỉ đến từ LẦN GIAO của hợp đồng — dòng bán kiểu cũ không còn được cộng, và kỳ có
    # dữ liệu cũ chưa chuyển đổi thì phải cảnh báo (chốt 02/08/2026).
    assert row["total_consumption"] is None and row["lt_export"] is None
    assert any("CHƯA được chuyển" in w for w in pr.json()["warnings"])
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


def test_cup_basis_and_prev_stock() -> None:
    """Mủ chén tính theo độ TSC/DRC + nút 'Lấy tồn ngày trước' (tồn kho là số thời điểm)."""
    h = _admin()
    unit = "_zz_ud_basis"
    today = date.today()
    y_day, t_day = (today - timedelta(days=1)).isoformat(), today.isoformat()
    client.delete("/api/users/ud_basis", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_basis", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_basis", "pass123")

    # 1) Thu mua: chọn độ DRC → lưu kèm payload, và giá ghi vào kho mang nhãn "đồng/độ DRC".
    assert client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": unit, "as_of": t_day,
        "fields": {"coagulum": 8, "cup_basis": "drc"}}).status_code == 200
    assert client.put("/api/member/prices", headers=mh, json={
        "company": unit, "as_of": t_day, "price_type": "purchase_cup",
        "price": 480, "basis": "drc"}).status_code == 200
    day = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}", headers=mh).json()
    assert day["entries"][unit]["fields"]["cup_basis"] == "drc"

    # Giá trị lạ ngoài {tsc, drc} phải bị loại, không ghi vào payload.
    client.put("/api/member/daily-report", headers=mh, json={
        "kind": "purchase", "company": unit, "as_of": t_day,
        "fields": {"coagulum": 8, "cup_basis": "xyz"}})
    day = client.get(f"/api/member/daily-report?kind=purchase&as_of={t_day}", headers=mh).json()
    assert "cup_basis" not in day["entries"][unit]["fields"]

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
    assert any("CHƯA được chuyển" in w for w in pr.json()["warnings"])
    assert row["stock_finished"] == 24.0 and row["stock_material"] == 3.5
    assert row["stock_as_of"] == yesterday and row["last_day"] == today
    assert row["stock_by_grade"]["RSS 3"] == 24.0

    # Khớp màn Thống kê tồn kho (cùng quy tắc `has_stock`) — hai màn không được lệch nhau.
    st = client.get("/api/unit-daily/analytics/stock?group_by=company"
                    f"&date_from={yesterday}&date_to={today}", headers=eh).json()
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
