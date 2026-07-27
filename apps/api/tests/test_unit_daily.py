"""Test báo cáo tiêu thụ–tồn kho theo ngày (member + chuyên viên có quyền `unit_daily`) + cửa sổ sửa ngày."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
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
        db.execute(text("DELETE FROM fact_price WHERE source = 'vrg' AND grade = ANY(:u)"), {"u": units})
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
                                        "carry_lt_tonnes": 40, "carry_spot_tonnes": 15}

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

    # Hợp đồng đã ký = bản ghi có VÒNG ĐỜI riêng: nhập 1 lần, tự nằm trong tồn kho từ ngày bắt đầu
    # đến HẾT NGÀY TRƯỚC ngày giao → không phải nhập lại mỗi ngày.
    ct = {"company": unit, "code": "HĐ-02/2026", "grade": "RSS 3", "qty": 6, "price": 48,
          "start_date": today, "delivery_date": (date.today() + timedelta(days=10)).isoformat()}
    made = client.put("/api/unit-daily/stock-contracts", json=ct, headers=eh)
    assert made.status_code == 200 and made.json()["contract"]["id"]
    # Ngày bắt đầu phải TRƯỚC ngày giao ít nhất 1 ngày (chặn nhập sai).
    bad = client.put("/api/unit-daily/stock-contracts",
                     json={**ct, "delivered_date": today}, headers=eh)
    assert bad.status_code == 400 and "trước Ngày giao" in bad.json()["detail"]

    tl = client.get("/api/unit-daily/timeline?kind=consumption&days=30", headers=eh)
    saved = next(e for e in tl.json()["entries"] if e["company"] == unit)["fields"]
    assert saved["sales"][0]["qty"] == 12.5
    # Số HĐ/PL lưu theo TỪNG DÒNG bán; dòng không gõ thì để trống.
    assert saved["sales"][0]["code"] == "HĐ-01/2026"
    # Khối 3 hiện ra là số TỰ TÍNH từ bảng hợp đồng (không phải số client gửi kèm).
    assert [r["code"] for r in saved["stock_signed_undelivered"]] == ["HĐ-02/2026"]
    assert saved["stock_signed_undelivered"][0]["qty"] == 6
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
    # Tổng tiêu thụ = mủ thu mua (12.5) + mủ khai thác (7.5), tách đúng theo loại HĐ / hình thức.
    assert row["lt_export"] == 12.5 and row["spot_domestic"] == 7.5
    assert row["total_consumption"] == 20.0
    # Tồn kho thành phẩm = khối 1 + khối 2 = 24; khối 3 (đã ký HĐ chưa giao) báo RIÊNG —
    # KHÔNG cộng vào (≠ 30) và KHÔNG trừ ra (≠ 18).
    assert row["stock_finished"] == 24.0
    assert row["stock_finished_hd"] == 6.0 and row["stock_material"] == 3.5

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

    # 3) Hợp đồng đã ký của đơn vị: tự nằm trong tồn kho tới HẾT NGÀY TRƯỚC ngày giao.
    made = client.put("/api/member/stock-contracts", headers=mh, json={
        "company": unit, "code": "HĐ-09/2026", "grade": "SVR 10 / CSR 10", "qty": 12,
        "price": 40, "start_date": y_day, "delivered_date": t_day})
    assert made.status_code == 200
    cid = made.json()["contract"]["id"]
    y_view = client.get(f"/api/member/daily-report?kind=consumption&as_of={y_day}", headers=mh).json()
    assert y_view["entries"][unit]["fields"]["stock_signed_undelivered"][0]["qty"] == 12
    # Ngày giao: đã xuất kho → KHÔNG còn tính vào tồn kho nữa (ngày đó không còn số liệu nào).
    t_view = client.get(f"/api/member/daily-report?kind=consumption&as_of={t_day}", headers=mh).json()
    t_entry = t_view["entries"][unit] or {"fields": {}}
    assert t_entry["fields"].get("stock_signed_undelivered", []) == []
    # Đơn vị khác không xoá được hợp đồng này.
    assert client.delete(f"/api/member/stock-contracts/{cid}", headers=mh).status_code == 200

    # Không có ngày nào trước đó → found=false (không dựng số khống).
    empty = client.get(f"/api/member/daily-report/prev-stock?company={unit}&before={y_day}",
                       headers=mh).json()
    assert empty["found"] is False

    # Đơn vị khác không lấy được tồn kho của đơn vị này.
    assert client.get("/api/member/daily-report/prev-stock?company=Đơn vị khác&before=" + t_day,
                      headers=mh).status_code == 403

    _cleanup(h, ["ud_basis"], [unit])


def test_year_plan_respects_has_purchase_plan_flag() -> None:
    """Chỉ đơn vị bật cờ 'có giao kế hoạch thu mua' mới hiện ở màn Kế hoạch năm (HQ + member)."""
    h = _admin()
    unit = "_zz_ud_plan_flag"
    year = date.today().year
    client.delete("/api/users/ud_pf", headers=h)
    client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "ud_pf", "password": "pass123",
                                    "role": "member", "member_units": [unit]}, headers=h)
    mh = _bearer("ud_pf", "pass123")

    hq_units = lambda: client.get(f"/api/unit-daily/plan?year={year}", headers=h).json()["units"]
    my_units = lambda: client.get(f"/api/member/plan?year={year}", headers=mh).json()["units"]

    # Mặc định BẬT → đơn vị hiện ở cả danh sách HQ lẫn danh sách đơn vị thành viên.
    assert unit in hq_units() and unit in my_units()

    # TẮT cờ → đơn vị biến mất khỏi cả hai danh sách Kế hoạch năm.
    assert client.put(f"/api/member-units/{unit}",
                      json={"set_purchase_plan": True, "has_purchase_plan": False},
                      headers=h).status_code == 200
    assert unit not in hq_units() and unit not in my_units()

    # BẬT lại → đơn vị trở lại danh sách.
    assert client.put(f"/api/member-units/{unit}",
                      json={"set_purchase_plan": True, "has_purchase_plan": True},
                      headers=h).status_code == 200
    assert unit in hq_units() and unit in my_units()

    _cleanup(h, ["ud_pf"], [unit])


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
    delivered = client.put("/api/unit-daily/stock-contracts", headers=eh, json={
        "company": unit, "code": "HĐ-H1/2026", "grade": "RSS 3", "qty": 5, "price": 40,
        "start_date": old_day, "delivered_date": recent_day}).json()["contract"]
    undelivered = client.put("/api/unit-daily/stock-contracts", headers=eh, json={
        "company": unit, "code": "HĐ-H2/2026", "grade": "SVR 3L", "qty": 8, "price": 45,
        "start_date": recent_day}).json()["contract"]

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

    # ── Hợp đồng tồn kho: gửi DANH SÁCH nhiều file ───────────────────────────────────────
    many = client.put("/api/unit-daily/stock-contracts", headers=eh, json={
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
    legacy = client.put("/api/unit-daily/stock-contracts", headers=eh, json={
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
    # Tiêu thụ vẫn CỘNG DỒN cả 2 ngày; tồn kho giữ ảnh chụp hôm qua và nói rõ ngày đã lấy.
    assert row["total_consumption"] == 7.0
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
