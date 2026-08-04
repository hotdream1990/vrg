"""Test HỢP ĐỒNG BÁN HÀNG 2 CẤP + danh mục khách hàng + tiêu thụ/khối 3 tính từ hợp đồng."""

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

UNIT = "_zz_sc_unit"
UNIT2 = "_zz_sc_unit2"
UNIT3 = "_zz_sc_unit3"
TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    token = client.post("/api/auth/login",
                        json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _cleanup(h: dict[str, str]) -> None:
    units = [UNIT, UNIT2, UNIT3]
    with session_scope() as db:
        db.execute(text("DELETE FROM sales_contract WHERE company = ANY(:u) OR to_company = ANY(:u)"),
                   {"u": units})
        db.execute(text("DELETE FROM unit_customer WHERE company = ANY(:u)"), {"u": units})
    for n in units:
        client.delete(f"/api/member-units/{n}", headers=h)


def _line(grade="SVR 10 / CSR 10", qty=100.0, **kw) -> dict:
    return {"grade": grade, "qty": qty, "price": 40.0, "ccy": "VND", **kw}


@pytest.fixture()
def env():
    h = _admin()
    _cleanup(h)
    for n in (UNIT, UNIT2, UNIT3):
        client.post("/api/member-units", json={"name": n}, headers=h)
    # UNIT2 là công ty CON của UNIT → hai đơn vị cùng nhóm, bán cho nhau mới là tiêu thụ NỘI BỘ.
    # UNIT3 đứng một mình (ngoài nhóm) để kiểm ràng buộc.
    client.put(f"/api/member-units/{UNIT2}", headers=h,
               json={"set_parent": True, "parent_company": UNIT})
    yield h
    _cleanup(h)


@pytest.fixture()
def cus(env):
    """Khách hàng mặc định của UNIT — hợp đồng mẹ bắt buộc gán khách."""
    return client.put("/api/customers", json={"company": UNIT, "name": "KH mặc định"},
                      headers=env).json()["id"]


def test_customer_is_per_unit_and_unique(env) -> None:
    h = env
    r = client.put("/api/customers", json={"company": UNIT, "name": "Khách A", "code": "KA"}, headers=h)
    assert r.status_code == 200, r.text
    # Cùng đơn vị, trùng tên → chặn.
    dup = client.put("/api/customers", json={"company": UNIT, "name": "Khách A"}, headers=h)
    assert dup.status_code == 400 and "đã có khách hàng" in dup.json()["detail"]
    # Đơn vị KHÁC trùng tên → cho phép (danh mục tách riêng theo đơn vị).
    assert client.put("/api/customers", json={"company": UNIT2, "name": "Khách A"},
                      headers=h).status_code == 200

    names = {(c["company"], c["name"]) for c in client.get("/api/customers", headers=h).json()}
    assert (UNIT, "Khách A") in names and (UNIT2, "Khách A") in names


def test_contract_rejects_customer_of_another_unit(env) -> None:
    h = env
    cid = client.put("/api/customers", json={"company": UNIT2, "name": "Khách B"},
                     headers=h).json()["id"]
    r = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-X", "customer_id": cid, "delivery_type": "single", "contract_type": "long_term",
        "sign_date": TODAY, "lines": [_line()]}, headers=h)
    assert r.status_code == 400 and "đơn vị khác" in r.json()["detail"]


def test_multi_contract_children_cannot_exceed_parent(env, cus) -> None:
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-M1", "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus, "sign_date": YESTERDAY,
        "lines": [_line(qty=100.0)]}, headers=h).json()["contract"]

    ok = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-01", "start_date": YESTERDAY, "delivered_at": TODAY,
        "channel": "export", "lines": [_line(qty=60.0)]}, headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract"]["delivered"] is True   # phụ lục tự chuyển ĐÃ GIAO

    over = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-02", "start_date": YESTERDAY, "delivered_at": TODAY,
        "channel": "domestic", "lines": [_line(qty=50.0)]}, headers=h)
    assert over.status_code == 400 and "vượt sản lượng còn lại" in over.json()["detail"]

    detail = client.get(f"/api/sales-contracts/{parent['id']}", headers=h).json()
    assert detail["delivered_qty"] == pytest.approx(60.0)
    assert detail["remaining_qty"] == pytest.approx(40.0)


def test_dry_weight_required_on_delivery_only(env, cus) -> None:
    h = env
    # Hợp đồng mẹ giao-nhiều-lần chỉ là cam kết → KHÔNG ép quy khô.
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-L", "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus, "sign_date": YESTERDAY,
        "lines": [_line(grade="LATEX", qty=50.0)]}, headers=h)
    assert parent.status_code == 200, parent.text

    # Phụ lục = lần giao thật → bán LATEX bắt buộc quy khô.
    bad = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent.json()["contract"]["id"], "code": "PL-L1", "start_date": YESTERDAY,
        "delivered_at": TODAY, "channel": "export",
        "lines": [_line(grade="LATEX", qty=10.0)]}, headers=h)
    assert bad.status_code == 400 and "quy khô" in bad.json()["detail"]

    good = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent.json()["contract"]["id"], "code": "PL-L1", "start_date": YESTERDAY,
        "delivered_at": TODAY, "channel": "export",
        "lines": [_line(grade="LATEX", qty=10.0, qty_dry=3.5)]}, headers=h)
    assert good.status_code == 200, good.text


def test_dry_weight_required_for_all_three_grades(env, cus) -> None:
    """Quy khô bắt buộc cho ĐỦ 3 loại (LATEX + 2 loại NL mới) — không chỉ LATEX."""
    from app.core.market_meta import DRY_REQUIRED_GRADES

    h = env
    assert len(DRY_REQUIRED_GRADES) == 3
    for i, grade in enumerate(sorted(DRY_REQUIRED_GRADES)):
        body = {"company": UNIT, "code": f"HD-DRY{i}", "delivery_type": "single", "contract_type": "long_term",
                "customer_id": cus, "sign_date": YESTERDAY, "delivered": True,
                "delivered_at": TODAY, "channel": "export"}
        bad = client.put("/api/sales-contracts",
                         json={**body, "lines": [_line(grade=grade, qty=8.0)]}, headers=h)
        assert bad.status_code == 400 and "quy khô" in bad.json()["detail"], grade
        ok = client.put("/api/sales-contracts",
                        json={**body, "lines": [_line(grade=grade, qty=8.0, qty_dry=5.0)]}, headers=h)
        assert ok.status_code == 200, f"{grade}: {ok.text}"

    # Chủng loại KHÔNG thuộc danh sách thì không bị ép (vd SVR 10) — tránh ép nhầm cả bảng.
    free = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-FREE", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus,
        "sign_date": YESTERDAY, "delivered": True, "delivered_at": TODAY, "channel": "export",
        "lines": [_line(qty=8.0)]}, headers=h)
    assert free.status_code == 200, free.text


def test_dry_weight_rejected_for_finished_grades(env, cus) -> None:
    """Thành phẩm bán ra đã là hàng khô → khai quy khô là số vô nghĩa, phải chặn.

    Nhận bừa thì chỉ tiêu "quy khô" trên Báo cáo tiêu thụ cộng cả số rác mà nhìn không ra.
    """
    h = env
    bad = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-DRYX", "delivery_type": "single", "contract_type": "spot",
        "customer_id": cus, "sign_date": YESTERDAY,
        "lines": [_line(qty=10.0, qty_dry=5.0)]}, headers=h)          # SVR 10 — hàng khô
    assert bad.status_code == 400 and "không có quy khô" in bad.json()["detail"]

    ok = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-DRYX", "delivery_type": "single", "contract_type": "spot",
        "customer_id": cus, "sign_date": YESTERDAY,
        "lines": [_line(qty=10.0)]}, headers=h)
    assert ok.status_code == 200, ok.text


def test_dry_weight_enforced_when_contract_flips_to_delivered(env, cus) -> None:
    """HĐ giao-1-lần lúc tạo CHƯA giao (không ép quy khô) — khi đánh dấu đã giao thì phải ép."""
    h = env
    body = {"company": UNIT, "code": "HD-FLIP", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus,
            "sign_date": YESTERDAY, "lines": [_line(grade="LATEX", qty=20.0)]}
    created = client.put("/api/sales-contracts", json=body, headers=h)
    assert created.status_code == 200, created.text     # chưa giao → chưa cần quy khô

    cid = created.json()["contract"]["id"]
    flip = client.put("/api/sales-contracts", json={
        **body, "id": cid, "delivered": True, "delivered_at": TODAY, "channel": "export"}, headers=h)
    assert flip.status_code == 400 and "quy khô" in flip.json()["detail"]


def test_foreign_currency_needs_fx(env, cus) -> None:
    h = env
    bad = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-LAK", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus, "sign_date": TODAY,
        "lines": [_line(qty=5.0, ccy="LAK")]}, headers=h)
    assert bad.status_code == 400 and "tỷ giá" in bad.json()["detail"]

    ok = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-LAK", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus, "sign_date": TODAY,
        "lines": [_line(qty=5.0, ccy="LAK", price=900_000.0, fx=1.24)]}, headers=h)
    assert ok.status_code == 200, ok.text
    assert ok.json()["contract"]["revenue"] == pytest.approx(5.0 * 900_000.0 * 1.24)


def test_consumption_and_block3_computed_from_contracts(env, cus) -> None:
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-M2", "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus, "sign_date": YESTERDAY,
        "lines": [_line(qty=100.0)]}, headers=h).json()["contract"]
    client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-A", "start_date": YESTERDAY, "delivered_at": TODAY,
        "channel": "internal", "to_company": UNIT2,
        "lines": [_line(qty=30.0)]}, headers=h)

    cons = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert cons["qty"] == pytest.approx(30.0)
    assert cons["by_channel"]["internal"] == pytest.approx(30.0)
    assert cons["revenue"] == pytest.approx(30.0 * 40.0 * 1_000_000)

    # Khối 3 = ĐỢT ĐANG MỞ (bắt đầu → hết ngày trước ngày giao), KHÔNG phải cam kết còn lại của mẹ.
    # Hôm nay đợt đã giao xong → rời khối 3; 70 tấn mẹ chưa phân đợt KHÔNG tính (hàng chưa gom kho).
    assert client.get(f"/api/sales-contracts/undelivered?as_of={TODAY}&company={UNIT}",
                      headers=h).json()["by_company"] == {}
    # Hôm qua đợt đã mở nhưng chưa giao → đúng 30 tấn của đợt đó nằm trong khối 3.
    und_y = client.get(f"/api/sales-contracts/undelivered?as_of={YESTERDAY}&company={UNIT}",
                       headers=h).json()["by_company"][UNIT]
    assert und_y["qty"] == pytest.approx(30.0)


def test_revenue_unknown_when_fx_missing_is_not_zero(env, cus) -> None:
    """Thiếu tỷ giá → doanh thu là KHÔNG BIẾT (None), tuyệt đối không quy về 0."""
    h = env
    c = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-USD", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus, "sign_date": YESTERDAY,
        "delivered": True, "delivered_at": TODAY, "channel": "export",
        "lines": [_line(qty=10.0, ccy="USD", price=1800.0, fx=26000.0)]}, headers=h)
    assert c.status_code == 200, c.text
    # Gỡ tỷ giá thẳng dưới DB (mô phỏng bản ghi cũ thiếu tỷ giá) rồi kiểm tổng hợp.
    with session_scope() as db:
        db.execute(text("UPDATE sales_contract SET lines = jsonb_set(lines, '{0,fx}', 'null') "
                        "WHERE id = :i"), {"i": c.json()["contract"]["id"]})
    cons = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert cons["revenue"] is None
    assert cons["qty"] == pytest.approx(10.0)


def test_internal_sale_stays_inside_the_company_group(env, cus) -> None:
    """Tiêu thụ NỘI BỘ chỉ trong nhóm công ty mẹ–con; bán ra ngoài nhóm là bán ngoài."""
    h = env
    body = {"company": UNIT, "code": "HD-IN", "delivery_type": "single",
            "contract_type": "spot", "customer_id": cus, "sign_date": YESTERDAY,
            "delivered_at": TODAY, "channel": "internal", "lines": [_line(qty=5.0)]}

    # UNIT3 đứng ngoài nhóm → chặn, kèm câu chỉ đúng chỗ cần sửa.
    out = client.put("/api/sales-contracts", json={**body, "to_company": UNIT3}, headers=h)
    assert out.status_code == 400 and "không cùng nhóm" in out.json()["detail"]

    # UNIT2 là con của UNIT → cùng nhóm, cho lưu.
    ok = client.put("/api/sales-contracts", json={**body, "to_company": UNIT2}, headers=h)
    assert ok.status_code == 200, ok.text

    # Chiều ngược lại (con bán cho mẹ) cũng là nội bộ.
    cus2 = client.put("/api/customers", json={"company": UNIT2, "name": "KH con"},
                      headers=h).json()["id"]
    back = client.put("/api/sales-contracts", json={
        **body, "company": UNIT2, "code": "HD-IN2", "customer_id": cus2, "to_company": UNIT}, headers=h)
    assert back.status_code == 200, back.text

    # Form lấy danh sách đơn vị nhận từ meta — đúng nhóm, không kèm đơn vị ngoài nhóm.
    meta = client.get("/api/sales-contracts/meta", headers=h).json()["internal_targets"]
    assert meta[UNIT] == [UNIT2] and meta[UNIT2] == [UNIT]
    assert UNIT3 not in meta          # đứng một mình → form ẩn hình thức tiêu thụ nội bộ


def test_edit_window_locks_old_deliveries_only(env, cus) -> None:
    """Cửa sổ sửa CHỈ khoá LẦN GIAO theo ngày giao; hợp đồng mẹ vẫn sửa và thêm phụ lục được.

    Khoá hợp đồng mẹ theo ngày ký sẽ chặn đúng nghiệp vụ chính: hợp đồng dài hạn ký từ lâu vẫn phải
    nhập phụ lục cho từng lần giao.
    """
    from app.services import config_repo

    h = env
    old_day = (date.today() - timedelta(days=40)).isoformat()
    config_repo.set_config({"EDITOR_EDIT_WINDOW_DAYS": "7"}, "test")
    # Admin được MIỄN cửa sổ → dùng tài khoản chuyên viên để kiểm hàng rào.
    client.delete("/api/users/zz_ct_ed", headers=h)
    client.post("/api/users", json={"username": "zz_ct_ed", "password": "pass123", "role": "editor",
                                    "permissions": ["sales_contract"]}, headers=h)
    eh = {"Authorization": f"Bearer {client.post('/api/auth/login', json={'username': 'zz_ct_ed', 'password': 'pass123'}).json()['access_token']}"}

    # Hợp đồng mẹ KÝ TỪ LÂU vẫn sửa được...
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-OLD", "delivery_type": "multi", "contract_type": "long_term",
        "customer_id": cus, "sign_date": old_day, "lines": [_line(qty=100.0)]}, headers=eh)
    assert parent.status_code == 200, parent.text
    pid = parent.json()["contract"]["id"]

    # ...và vẫn thêm được phụ lục giao TRONG cửa sổ.
    ok = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": pid, "code": "PL-NAY", "start_date": YESTERDAY,
        "delivered_at": TODAY, "channel": "export", "lines": [_line(qty=10.0)]}, headers=eh)
    assert ok.status_code == 200, ok.text

    # Nhưng KHÔNG khai được lần giao lùi quá cửa sổ.
    late = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": pid, "code": "PL-CU", "start_date": old_day,
        "delivered_at": old_day, "channel": "export", "lines": [_line(qty=10.0)]}, headers=eh)
    assert late.status_code == 403 and "chỉ xem" in late.json()["detail"]

    # Lần giao đã khoá thì không sửa, không xoá được (ghi thẳng DB cho giống dữ liệu cũ).
    with session_scope() as db:
        locked = db.execute(text(
            "INSERT INTO sales_contract (company, parent_id, code, delivery_type, sign_date, "
            " start_date, lines, delivered, delivered_at, channel, updated_by) "
            "VALUES (:c, :p, 'PL-KHOA', 'single', CAST(:d AS date), CAST(:d AS date), "
            " '[]'::jsonb, true, CAST(:d AS date), 'export', 'test') RETURNING id"),
            {"c": UNIT, "p": pid, "d": old_day}).scalar()
    assert client.delete(f"/api/sales-contracts/{locked}", headers=eh).status_code == 403
    client.delete("/api/users/zz_ct_ed", headers=h)


def test_delete_parent_blocked_while_children_exist(env, cus) -> None:
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-M3", "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus, "sign_date": YESTERDAY,
        "lines": [_line(qty=20.0)]}, headers=h).json()["contract"]
    child = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-Z", "start_date": YESTERDAY, "delivered_at": TODAY,
        "channel": "export", "lines": [_line(qty=5.0)]}, headers=h).json()["contract"]

    blocked = client.delete(f"/api/sales-contracts/{parent['id']}", headers=h)
    assert blocked.status_code == 400 and "phụ lục" in blocked.json()["detail"]
    assert client.delete(f"/api/sales-contracts/{child['id']}", headers=h).status_code == 200
    assert client.delete(f"/api/sales-contracts/{parent['id']}", headers=h).status_code == 200


def test_legacy_sales_never_counted_but_flagged(env) -> None:
    """Chốt 02/08/2026: mảng `sales` cũ KHÔNG vào báo cáo dù đã chuyển đổi hay chưa.

    Chưa chuyển đổi thì phải CẢNH BÁO — nếu không người đọc thấy 0 tấn lại tưởng đơn vị không bán.
    """
    from app.services import unit_daily_repo, unit_period_report

    line = {"code": "X1", "contract": "long_term", "channel": "export",
            "grade": "SVR 10 / CSR 10", "qty": 40.0, "price": 45.0, "ccy": "VND"}
    unit_daily_repo.upsert("consumption", TODAY, UNIT, {"sales": [line], "revenue": 40 * 45e6}, "admin")
    rep = unit_period_report.period_report("consumption", TODAY, TODAY, [UNIT])
    assert rep["rows"][0]["total_consumption"] in (0, 0.0, None)
    assert any("CHƯA được chuyển" in w for w in rep["warnings"]), rep["warnings"]

    # Đã bật cờ chuyển đổi → vẫn không cộng, và hết cảnh báo (số đã nằm ở hợp đồng).
    unit_daily_repo.upsert("consumption", TODAY, UNIT,
                           {"sales": [line], "revenue": 40 * 45e6, "sales_migrated": True}, "admin")
    after = unit_period_report.period_report("consumption", TODAY, TODAY, [UNIT])
    assert after["rows"][0]["total_consumption"] in (0, 0.0, None)
    assert not any("ngày có số tiêu thụ" in w for w in after["warnings"]), after["warnings"]

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c AND as_of = :d"),
                   {"c": UNIT, "d": TODAY})


def test_migrated_flag_survives_a_normal_edit(env) -> None:
    """Form Tồn kho không gửi `sales_migrated` — repo phải tự giữ, nếu không mảng cũ sống lại."""
    from app.services import unit_daily_repo

    unit_daily_repo.upsert("consumption", TODAY, UNIT,
                           {"sales": [{"grade": "SVR 3L", "qty": 5.0}], "sales_migrated": True}, "admin")
    unit_daily_repo.upsert("consumption", TODAY, UNIT,           # lưu lại như form Tồn kho vẫn làm
                           {"stock_warehoused": [{"grade": "SVR 3L", "qty": 9.0}]}, "admin")
    got = unit_daily_repo.entries_on("consumption", TODAY)[UNIT]["fields"]
    assert got.get("sales_migrated") is True

    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company = :c AND as_of = :d"),
                   {"c": UNIT, "d": TODAY})


def test_file_download_blocked_across_units(env, cus) -> None:
    from app.services import sales_contract_repo

    c = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-F", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus, "sign_date": TODAY,
        "files": [{"file": "abc123.pdf", "filename": "hd.pdf"}],
        "lines": [_line()]}, headers=env)
    assert c.status_code == 200, c.text
    assert sales_contract_repo.companies_of_file("abc123.pdf") == {UNIT}
    assert sales_contract_repo.companies_of_file("khong-co.pdf") == set()


def test_parent_cycle_of_any_depth_is_rejected(env) -> None:
    """A→B→C→A: vòng lặp sâu 3 mắt cũng phải bị chặn, không chỉ vòng 2 mắt."""
    from app.services import member_unit_repo

    third = "_zz_sc_unit3"
    client.post("/api/member-units", json={"name": third}, headers=env)
    try:
        member_unit_repo.set_parent(UNIT2, UNIT)     # UNIT2 → UNIT
        member_unit_repo.set_parent(third, UNIT2)    # third  → UNIT2 → UNIT
        with pytest.raises(ValueError, match="vòng lặp"):
            member_unit_repo.set_parent(UNIT, third)  # UNIT → third ⇒ vòng
    finally:
        for u in (third, UNIT2, UNIT):
            member_unit_repo.set_parent(u, None)
        client.delete(f"/api/member-units/{third}", headers=env)


def _parent(h, cus, code="HD-G", qty=1000.0) -> dict:
    return client.put("/api/sales-contracts", json={
        "company": UNIT, "code": code, "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus,
        "sign_date": YESTERDAY, "lines": [_line(qty=qty)]}, headers=h).json()["contract"]


def test_update_cannot_bypass_or_corrupt_the_parent(env, cus) -> None:
    """Nhóm lỗi phát hiện khi test đối kháng — mọi đường vòng qua PUT đều phải bị chặn."""
    h = env
    p1, p2 = _parent(h, cus, "HD-G1", 1000.0), _parent(h, cus, "HD-G2", 100_000.0)
    kid = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": p1["id"], "code": "PL-G1", "start_date": YESTERDAY, "delivered_at": TODAY,
        "channel": "domestic", "lines": [_line(qty=600.0)]}, headers=h).json()["contract"]

    # Đổi hợp đồng mẹ trong lúc sửa: hạn mức bị kiểm trên MẸ KHÁC rồi dòng vẫn nằm ở mẹ cũ.
    r = client.put("/api/sales-contracts", json={
        **kid, "parent_id": p2["id"], "lines": [_line(qty=50_000.0)]}, headers=h)
    assert r.status_code == 400 and "không đổi được hợp đồng mẹ" in r.json()["detail"].lower()

    # Hạ cam kết của mẹ xuống dưới phần phụ lục đã giao.
    r = client.put("/api/sales-contracts", json={**p1, "lines": [_line(qty=10.0)]}, headers=h)
    assert r.status_code == 400 and "nhỏ hơn" in r.json()["detail"]

    # Mẹ đang có phụ lục mà đổi sang giao-1-lần + đã giao → tiêu thụ bị đếm 2 lần.
    r = client.put("/api/sales-contracts", json={
        **p1, "delivery_type": "single", "contract_type": "long_term", "delivered": True,
        "delivered_at": TODAY, "channel": "export"}, headers=h)
    assert r.status_code == 400

    # Bỏ ngày giao = đợt quay lại trạng thái ĐANG CHỜ GIAO (không còn tính vào tiêu thụ).
    r = client.put("/api/sales-contracts", json={**kid, "delivered_at": None}, headers=h)
    assert r.status_code == 200 and r.json()["contract"]["delivered"] is False
    # Cờ `delivered` do server suy ra từ ngày giao — client gửi ngược cũng không đổi được.
    r = client.put("/api/sales-contracts", json={**kid, "delivered": False}, headers=h)
    assert r.status_code == 200 and r.json()["contract"]["delivered"] is True


def test_invalid_inputs_are_rejected_not_coerced(env, cus) -> None:
    """Giá trị sai phải BÁO LỖI. Lặng lẽ quy về VNĐ làm doanh thu sai ~38 lần."""
    h = env
    base = {"company": UNIT, "delivery_type": "single", "contract_type": "long_term", "customer_id": cus, "sign_date": TODAY}

    # "usd" viết thường nay được chuẩn hoá thành USD → vẫn đòi tỷ giá (KHÔNG lặng lẽ thành VNĐ).
    r = client.put("/api/sales-contracts",
                   json={**base, "code": "HD-usd", "lines": [_line(ccy="usd")]}, headers=h)
    assert r.status_code == 400 and "tỷ giá" in r.json()["detail"]
    # Loại tiền không nằm trong danh mục thì báo lỗi hẳn.
    r = client.put("/api/sales-contracts",
                   json={**base, "code": "HD-EUR", "lines": [_line(ccy="EUR")]}, headers=h)
    assert r.status_code == 400 and "loại tiền" in r.json()["detail"].lower()

    r = client.put("/api/sales-contracts",
                   json={**base, "code": "HD-NEG", "lines": [_line(price=-30.0)]}, headers=h)
    assert r.status_code == 400 and "không được âm" in r.json()["detail"]

    # Quy khô lớn hơn số lượng ướt là vô lý.
    r = client.put("/api/sales-contracts", json={
        **base, "code": "HD-DRY", "lines": [_line(grade="LATEX", qty=10.0, qty_dry=9_999_999.0)]},
        headers=h)
    assert r.status_code == 400 and "quy khô" in r.json()["detail"]

    # Trùng số hợp đồng trong cùng đơn vị (lưu lại do mạng chập chờn sẽ nhân đôi sản lượng).
    body = {**base, "code": "HD-DUP", "lines": [_line()]}
    assert client.put("/api/sales-contracts", json=body, headers=h).status_code == 200
    dup = client.put("/api/sales-contracts", json=body, headers=h)
    assert dup.status_code == 400 and "đã có hợp đồng" in dup.json()["detail"]

    # Đơn vị / đơn vị nhận không có thật → bản ghi mồ côi.
    r = client.put("/api/sales-contracts",
                   json={**base, "company": "_zz_khong_co_don_vi", "code": "HD-ORPHAN",
                         "lines": [_line()]}, headers=h)
    assert r.status_code == 400


def test_nan_does_not_crash(env, cus) -> None:
    """`nan <= 0` là False nên lọt mọi kiểm tra, rồi jsonb từ chối → 500."""
    from app.services import sales_contract_repo

    with pytest.raises(ValueError):
        sales_contract_repo.save(
            {"company": UNIT, "code": "HD-NAN", "delivery_type": "single", "contract_type": "long_term", "customer_id": cus,
             "sign_date": TODAY,
             "lines": [{"grade": "SVR 10 / CSR 10", "qty": float("nan"), "price": 30, "ccy": "VND"}]},
            UNIT, "admin")


def test_consumption_filter_by_customer_and_xlsx(env, cus) -> None:
    """Lọc theo khách hàng + tách theo khách + xuất Excel (khách gán ở MẸ, phụ lục kế thừa)."""
    import zipfile

    h = env
    other = client.put("/api/customers", json={"company": UNIT, "name": "KH khác"},
                       headers=h).json()["id"]
    for code, cid, qty in (("HD-C1", cus, 30.0), ("HD-C2", other, 20.0)):
        p = client.put("/api/sales-contracts", json={
            "company": UNIT, "code": code, "delivery_type": "multi", "contract_type": "long_term", "customer_id": cid,
            "sign_date": YESTERDAY, "lines": [_line(qty=100.0)]}, headers=h).json()["contract"]
        client.put("/api/sales-contracts", json={
            "company": UNIT, "parent_id": p["id"], "code": f"PL-{code}", "start_date": YESTERDAY, "delivered_at": TODAY,
            "channel": "export", "lines": [_line(qty=qty)]}, headers=h)

    url = f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}&company={UNIT}"
    rep = client.get(url, headers=h).json()
    assert rep["by_company"][UNIT]["qty"] == pytest.approx(50.0)
    # Phụ lục KHÔNG mang khách hàng → phải lấy từ hợp đồng mẹ, nếu không dồn hết vào "chưa gán".
    by_cus = rep["by_company"][UNIT]["by_customer"]
    assert by_cus[str(cus)]["qty"] == pytest.approx(30.0)
    assert by_cus[str(other)]["qty"] == pytest.approx(20.0)

    only = client.get(f"{url}&customer_id={cus}", headers=h).json()
    assert only["by_company"][UNIT]["qty"] == pytest.approx(30.0)

    xls = client.get(f"/api/sales-contracts/consumption.xlsx?date_from={TODAY}&date_to={TODAY}"
                     f"&company={UNIT}", headers=h)
    assert xls.status_code == 200
    assert zipfile.is_zipfile(__import__("io").BytesIO(xls.content))   # .xlsx là file zip hợp lệ


def test_meta_reports_currency_per_unit(env) -> None:
    """Form chỉ cho chọn nội tệ CỦA ĐƠN VỊ đó — meta phải trả loại tiền từng đơn vị (chốt Q10)."""
    m = client.get("/api/sales-contracts/meta", headers=env).json()
    assert m["unit_currency"][UNIT] == "VND"          # đơn vị test mặc định trong nước
    assert set(m["unit_currency"]) >= {UNIT, UNIT2}


def test_batch_lifecycle_drives_block3(env, cus) -> None:
    """Đợt giao có vòng đời: nằm ở khối 3 từ NGÀY BẮT ĐẦU đến HẾT NGÀY TRƯỚC ngày giao.

    Kịch bản khách chốt 02/08/2026: HĐ mẹ 500 tấn ký 01/07, phụ lục 120 tấn mở 10/07 giao 20/07.
    Phần cam kết CHƯA phân đợt (380 tấn) KHÔNG tính vào khối 3 — hàng chưa gom vào kho.
    """
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-LC", "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus,
        "sign_date": "2026-07-01", "lines": [_line(qty=500.0)]}, headers=h).json()["contract"]
    client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-LC", "start_date": "2026-07-10",
        "delivered_at": "2026-07-20", "channel": "export",
        "lines": [_line(qty=120.0)]}, headers=h)

    def block3(day: str) -> float:
        rep = client.get(f"/api/sales-contracts/undelivered?as_of={day}&company={UNIT}",
                         headers=h).json()["by_company"]
        return (rep.get(UNIT) or {}).get("qty", 0.0)

    assert block3("2026-07-05") == pytest.approx(0.0)     # chưa mở đợt
    assert block3("2026-07-10") == pytest.approx(120.0)   # mở đợt → vào khối 3
    assert block3("2026-07-19") == pytest.approx(120.0)   # hết ngày TRƯỚC ngày giao
    assert block3("2026-07-20") == pytest.approx(0.0)     # đúng ngày giao → rời khối 3

    # Tiêu thụ ghi nhận ĐÚNG ngày giao, không phải ngày mở đợt.
    def sold(day: str) -> float:
        rep = client.get(f"/api/sales-contracts/consumption?date_from=2026-07-01&date_to={day}"
                         f"&company={UNIT}", headers=h).json()["by_company"]
        return (rep.get(UNIT) or {}).get("qty", 0.0)

    assert sold("2026-07-19") == pytest.approx(0.0)
    assert sold("2026-07-20") == pytest.approx(120.0)

    # 3 rổ của hợp đồng mẹ phải cộng lại đúng bằng sản lượng cam kết.
    d = client.get(f"/api/sales-contracts/{parent['id']}", headers=h).json()
    assert d["delivered_qty"] == pytest.approx(120.0)
    assert d["pending_qty"] == pytest.approx(0.0)
    assert d["remaining_qty"] == pytest.approx(380.0)


def test_batch_waiting_for_delivery_sits_in_block3(env, cus) -> None:
    """Phụ lục để TRỐNG ngày giao = đang chờ giao: nằm ở khối 3, chưa vào tiêu thụ."""
    h = env
    parent = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-W", "delivery_type": "multi", "contract_type": "long_term", "customer_id": cus,
        "sign_date": YESTERDAY, "lines": [_line(qty=200.0)]}, headers=h).json()["contract"]
    kid = client.put("/api/sales-contracts", json={
        "company": UNIT, "parent_id": parent["id"], "code": "PL-W",
        "start_date": YESTERDAY, "lines": [_line(qty=80.0)]}, headers=h)
    # Chưa giao thì KHÔNG ép hình thức tiêu thụ / quy khô — hàng chưa bán ra.
    assert kid.status_code == 200, kid.text
    assert kid.json()["contract"]["delivered"] is False

    und = client.get(f"/api/sales-contracts/undelivered?as_of={TODAY}&company={UNIT}",
                     headers=h).json()["by_company"][UNIT]
    assert und["qty"] == pytest.approx(80.0)
    cons = client.get(f"/api/sales-contracts/consumption?date_from={YESTERDAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"]
    assert cons == {}       # chưa giao → chưa tính tiêu thụ

    d = client.get(f"/api/sales-contracts/{parent['id']}", headers=h).json()
    assert (d["delivered_qty"], d["pending_qty"], d["remaining_qty"]) == (0.0, 80.0, 120.0)


def test_member_scope_is_enforced(env) -> None:
    h = env
    client.delete("/api/users/sc_mem", headers=h)
    assert client.post("/api/users", json={"username": "sc_mem", "password": "pass123",
                                           "role": "member", "member_units": [UNIT]},
                       headers=h).status_code == 200
    tok = client.post("/api/auth/login",
                      json={"username": "sc_mem", "password": "pass123"}).json()["access_token"]
    mh = {"Authorization": f"Bearer {tok}"}
    try:
        # Đơn vị chỉ thấy đơn vị của mình trong meta.
        assert client.get("/api/sales-contracts/meta", headers=mh).json()["units"] == [UNIT]
        # Tìm khách hàng cũng bị ép phạm vi: chỉ ra khách CỦA MÌNH, đòi đơn vị khác thì 403.
        client.put("/api/customers", json={"company": UNIT, "name": "KH của tôi"}, headers=h)
        client.put("/api/customers", json={"company": UNIT2, "name": "KH đơn vị khác"}, headers=h)
        seen = client.get("/api/customers?q=KH", headers=mh).json()
        assert {c["company"] for c in seen} == {UNIT}
        assert client.get(f"/api/customers?company={UNIT2}", headers=mh).status_code == 403
        # Ghi sang đơn vị khác → 403.
        r = client.put("/api/sales-contracts", json={
            "company": UNIT2, "code": "HD-NO", "delivery_type": "single", "contract_type": "long_term", "sign_date": TODAY,
            "lines": [_line()]}, headers=mh)
        assert r.status_code == 403
    finally:
        client.delete("/api/users/sc_mem", headers=h)


def test_customer_search_runs_on_server(env) -> None:
    """Ô chọn khách tìm Ở SERVER: theo từ khoá/mã · thu hẹp theo đơn vị · cắt theo `limit` · tra theo `ids`.

    Hai đơn vị hay có khách TÊN GẦN GIỐNG nhau (danh mục tách riêng) nên phải lọc được theo đơn vị
    và tra lại được tên theo id — thiếu hai thứ đó là người dùng chọn nhầm khách của đơn vị khác.
    """
    h = env
    a = client.put("/api/customers", json={"company": UNIT, "name": "SINTEX CHEMICAL CORPORATION"},
                   headers=h).json()["id"]
    b = client.put("/api/customers", json={"company": UNIT2, "name": "SINTEX CHEMICAL CORP.",
                                           "code": "SIN2"}, headers=h).json()["id"]
    client.put("/api/customers", json={"company": UNIT, "name": "Khách không liên quan"}, headers=h)

    def ids(qs: str) -> set[int]:
        return {c["id"] for c in client.get(f"/api/customers?{qs}", headers=h).json()}

    assert ids("q=sintex") == {a, b}
    assert ids(f"q=sintex&company={UNIT2}") == {b}
    assert ids("q=SIN2") == {b}                       # tìm được cả theo MÃ, không chỉ theo tên
    assert len(client.get("/api/customers?q=sintex&limit=1", headers=h).json()) == 1

    # Khách đã ẩn: không hiện khi tìm, nhưng tra theo id vẫn ra tên (hợp đồng cũ còn gắn khách đó).
    client.put("/api/customers", json={"id": b, "company": UNIT2, "name": "SINTEX CHEMICAL CORP.",
                                       "code": "SIN2", "is_active": False}, headers=h)
    assert ids("q=sintex&include_inactive=false") == {a}
    assert ids(f"ids={a}&ids={b}&include_inactive=true") == {a, b}


def test_contract_list_filters_by_one_or_many_customers(env) -> None:
    """Bộ lọc khách hàng nhận 1 HOẶC NHIỀU khách; danh sách trả kèm tên khách cho cột hiển thị."""
    h = env
    cid, code = {}, {}
    for name in ("KH A", "KH B", "KH C"):
        cid[name] = client.put("/api/customers", json={"company": UNIT, "name": name},
                               headers=h).json()["id"]
        code[name] = f"HD-{name[-1]}"
        client.put("/api/sales-contracts", json={
            "company": UNIT, "code": code[name], "delivery_type": "single", "contract_type": "spot",
            "customer_id": cid[name], "sign_date": TODAY, "lines": [_line()]}, headers=h)

    def rows(qs: str) -> list[dict]:
        return client.get(f"/api/sales-contracts?company={UNIT}&{qs}", headers=h).json()["contracts"]

    assert {r["code"] for r in rows("")} == set(code.values())
    assert {r["code"] for r in rows(f"customer_id={cid['KH A']}")} == {"HD-A"}
    assert ({r["code"] for r in rows(f"customer_id={cid['KH A']}&customer_id={cid['KH C']}")}
            == {"HD-A", "HD-C"})

    one = rows(f"customer_id={cid['KH B']}")[0]
    assert one["customer_name"] == "KH B"
    # Màn chi tiết không còn tải sẵn danh mục khách → tên khách phải do server trả kèm.
    assert client.get(f"/api/sales-contracts/{one['id']}", headers=h).json()["customer_name"] == "KH B"


def test_cost_is_gone_everywhere(env, cus) -> None:
    """Chi phí đã bỏ khỏi hệ thống (chốt 03/08/2026): client cũ gửi lên cũng KHÔNG được lưu.

    Ô chi phí biến mất khỏi màn hình là chưa đủ — bản web cũ còn trong cache trình duyệt vẫn gửi
    `cost`/`payment_cost` lên. Nếu server âm thầm nhận, số liệu chi phí lại mọc lại trong dữ liệu
    mà không màn nào hiển thị.
    """
    h = env
    made = client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-NOCOST", "delivery_type": "single", "contract_type": "spot",
        "customer_id": cus, "sign_date": TODAY, "start_date": TODAY, "delivered_at": TODAY,
        "channel": "domestic", "payment_cost": 99.0,
        "lines": [_line(qty=10.0, cost=77.0)]}, headers=h)
    assert made.status_code == 200, made.text
    c = made.json()["contract"]
    assert "cost" not in c and "payment_cost" not in c
    assert all("cost" not in ln for ln in c["lines"])

    # Báo cáo tiêu thụ + báo cáo kỳ không còn chỉ tiêu chi phí nào.
    cons = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert "cost" not in cons
    rep = client.get(f"/api/unit-daily/period?kind=consumption&date_from={TODAY}&date_to={TODAY}",
                     headers=h).json()
    assert not [k for r in rep.get("rows", []) for k in r if k.startswith("cost")]


def test_latex_reports_dry_tonnes_but_bills_wet(env, cus) -> None:
    """PA1 (04/08/2026): latex bán theo MỦ NƯỚC — tiền tính trên SL nước, SẢN LƯỢNG báo cáo lấy QUY KHÔ.

    Đây là chỗ dễ sai nhất: lẫn hai gốc số thì hoặc doanh thu bị thổi lên (tính tiền trên số nước
    rồi lại nhân giá khô), hoặc sản lượng tiêu thụ bị đội gấp ~3 lần (báo cáo số mủ nước).
    """
    h = env
    client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-LTX", "delivery_type": "single", "contract_type": "spot",
        "customer_id": cus, "sign_date": TODAY, "start_date": TODAY, "delivered_at": TODAY,
        "channel": "domestic",
        "lines": [_line(grade="LATEX", qty=30.0, qty_dry=10.0, price=20.0)]}, headers=h)

    cons = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                      f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert cons["qty"] == pytest.approx(10.0)                    # sản lượng = QUY KHÔ
    assert cons["by_grade"]["LATEX"] == pytest.approx(10.0)
    assert cons["by_channel"]["domestic"] == pytest.approx(10.0)
    assert cons["revenue"] == pytest.approx(30.0 * 20.0 * 1_000_000)   # tiền = SL NƯỚC × đơn giá

    # Cam kết/tiến độ của hợp đồng vẫn là SL NƯỚC — đó là số ghi trên hợp đồng.
    row = next(c for c in client.get(f"/api/sales-contracts?company={UNIT}", headers=h)
               .json()["contracts"] if c["code"] == "HD-LTX")
    assert row["qty"] == pytest.approx(30.0) and row["delivered_qty"] == pytest.approx(30.0)
    assert row["revenue"] == pytest.approx(30.0 * 20.0 * 1_000_000)

    # Chủng loại KHÔNG có quy khô: sản lượng báo cáo vẫn là chính nó.
    client.put("/api/sales-contracts", json={
        "company": UNIT, "code": "HD-SVR", "delivery_type": "single", "contract_type": "spot",
        "customer_id": cus, "sign_date": TODAY, "start_date": TODAY, "delivered_at": TODAY,
        "channel": "domestic", "lines": [_line(qty=7.0)]}, headers=h)
    cons2 = client.get(f"/api/sales-contracts/consumption?date_from={TODAY}&date_to={TODAY}"
                       f"&company={UNIT}", headers=h).json()["by_company"][UNIT]
    assert cons2["qty"] == pytest.approx(17.0)                   # 10 (quy khô latex) + 7
