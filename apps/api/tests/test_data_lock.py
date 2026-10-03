"""CHỐT SỐ LIỆU ĐƠN VỊ — hàng rào sau khi đơn vị xác nhận (chốt 25/08/2026).

Năm điều dễ vỡ, khoá lại bằng test:
  - Chưa xác nhận thì đơn vị vẫn sửa bình thường (khoá KHÔNG tự bật theo ngày).
  - Xác nhận xong: ngày ≤ ngày chốt hết sửa, ngày sau ngày chốt vẫn sửa.
  - Chuyên viên/quản trị KHÔNG bị chặn — sau khi chốt đó là đường sửa duy nhất.
  - Lần giao (tiêu thụ) ≤ ngày chốt đứng yên, nhưng hợp đồng vẫn thêm đợt giao mới được.
  - Huỷ đợt / quản trị mở khoá → số liệu mở lại.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import data_lock_summary, member_unit_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
UNIT = "_ZZ Data Lock Test"
USER = "zz_data_lock"
TODAY = date.today()
# ⚠ Ngày chốt đặt sát hôm nay CÓ CHỦ Ý: DB dev dùng chung có thể còn đợt chốt cũ của người khác,
# mà `current_round()` lấy đợt có ngày chốt MỚI NHẤT (hoà thì id lớn hơn thắng) — để ngày cũ là
# test đọc nhầm đợt của người khác rồi đỏ oan.
LOCK = (TODAY - timedelta(days=1)).isoformat()        # chốt số liệu đến hết ngày này
INSIDE = (TODAY - timedelta(days=2)).isoformat()      # trong vùng đã chốt
OUTSIDE = TODAY.isoformat()                           # sau ngày chốt → vẫn sửa được


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _admin() -> dict[str, str]:
    tok = client.post("/api/auth/login",
                      json={"username": "admin", "password": "admin"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _member() -> dict[str, str]:
    tok = client.post("/api/auth/login",
                      json={"username": USER, "password": "pass123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _cleanup(h: dict[str, str]) -> None:
    client.delete(f"/api/users/{USER}", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_data_lock WHERE company = :c"), {"c": UNIT})
        db.execute(text("DELETE FROM data_lock_round WHERE note = :n"), {"n": "ZZ TEST"})
        for tbl in ("unit_daily_report", "unit_purchase_plan", "sales_contract", "master_contract"):
            db.execute(text(f"DELETE FROM {tbl} WHERE company = :c"), {"c": UNIT})
        db.execute(text("DELETE FROM unit_customer WHERE company = :c"), {"c": UNIT})
    member_unit_repo.delete_unit(UNIT)


@pytest.fixture()
def env():
    """Đơn vị + tài khoản đơn vị + cửa sổ sửa đủ rộng để test ngày cũ."""
    h = _admin()
    _cleanup(h)
    member_unit_repo.add_unit(UNIT)
    client.post("/api/users", json={"username": USER, "password": "pass123",
                                    "role": "member", "member_units": [UNIT]}, headers=h)
    before = client.get("/api/settings/edit-windows", headers=h).json()
    client.put("/api/config", json={"values": {"MEMBER_EDIT_WINDOW_DAYS": "60"}}, headers=h)
    yield h, _member()
    client.put("/api/config",
               json={"values": {"MEMBER_EDIT_WINDOW_DAYS": str(before["member_days"])}}, headers=h)
    _cleanup(h)


def _round(h: dict[str, str], lock_date: str = LOCK) -> dict:
    r = client.put("/api/data-lock/rounds",
                   json={"lock_date": lock_date, "note": "ZZ TEST"}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["round"]


def _save_day(mh: dict[str, str], as_of: str, qty: float = 10):
    return client.put("/api/member/daily-report", headers=mh, json={
        "kind": "consumption", "company": UNIT, "as_of": as_of,
        "fields": {"stock_warehoused": [{"grade": "SVR 10 / CSR 10", "qty": qty}]}})


def test_lock_only_starts_after_the_unit_confirms(env) -> None:
    h, mh = env
    rnd = _round(h)

    # Đợt chốt đã phát nhưng CHƯA xác nhận → vẫn sửa được ngày trong vùng sẽ chốt.
    cur = client.get("/api/data-lock/current", headers=mh).json()
    assert cur["round"]["lock_date"] == LOCK
    assert cur["units"][0]["confirmed"] is False and cur["units"][0]["locked_until"] is None
    assert _save_day(mh, INSIDE).status_code == 200

    # Xác nhận → ngày ≤ ngày chốt hết sửa, ngày sau ngày chốt vẫn sửa bình thường.
    ok = client.post("/api/data-lock/confirm", headers=mh,
                     json={"round_id": rnd["id"], "company": UNIT})
    assert ok.status_code == 200 and ok.json()["locked_until"] == LOCK
    blocked = _save_day(mh, INSIDE, 11)
    assert blocked.status_code == 403 and "đã được chốt" in blocked.json()["detail"]
    assert _save_day(mh, LOCK, 12).status_code == 403       # đúng ngày chốt cũng nằm trong vùng
    assert _save_day(mh, OUTSIDE, 13).status_code == 200

    cur = client.get("/api/data-lock/current", headers=mh).json()
    assert cur["units"][0]["confirmed"] is True and cur["units"][0]["locked_until"] == LOCK


def test_specialist_and_admin_still_edit_locked_days(env) -> None:
    """Sau khi chốt, chuyên viên/quản trị sửa hộ là ĐƯỜNG DUY NHẤT — không được chặn họ."""
    h, mh = env
    rnd = _round(h)
    client.post("/api/data-lock/confirm", headers=mh,
                json={"round_id": rnd["id"], "company": UNIT})

    assert _save_day(mh, INSIDE).status_code == 403
    r = client.put("/api/unit-daily/report", headers=h, json={
        "kind": "consumption", "company": UNIT, "as_of": INSIDE,
        "fields": {"stock_warehoused": [{"grade": "SVR 10 / CSR 10", "qty": 99}]}})
    assert r.status_code == 200, r.text


def test_price_and_move_date_respect_the_lock(env) -> None:
    h, mh = env
    rnd = _round(h)
    assert _save_day(mh, INSIDE).status_code == 200
    client.post("/api/data-lock/confirm", headers=mh,
                json={"round_id": rnd["id"], "company": UNIT})

    # Đơn giá thu mua là một phần của số liệu thu mua đã chốt.
    px = client.put("/api/member/prices", headers=mh, json={
        "company": UNIT, "as_of": INSIDE, "price_type": "purchase", "price": 400})
    assert px.status_code == 403
    assert client.put("/api/member/prices", headers=mh, json={
        "company": UNIT, "as_of": OUTSIDE, "price_type": "purchase", "price": 400}).status_code == 200

    # Dời ngày: chặn cả hai đầu — kéo số liệu RA khỏi vùng chốt cũng là làm đổi số đã chốt.
    out = client.put("/api/member/daily-report/move-date", headers=mh, json={
        "kind": "consumption", "company": UNIT, "as_of": INSIDE, "to_date": OUTSIDE})
    assert out.status_code == 403
    assert client.put("/api/member/daily-report/move-date", headers=mh, json={
        "kind": "consumption", "company": UNIT, "as_of": OUTSIDE, "to_date": INSIDE},
    ).status_code == 403


def test_delivery_locked_but_contract_still_updatable(env) -> None:
    """'Hợp đồng có thể cập nhật nhưng tiêu thụ bị chốt lại' — yêu cầu 25/08/2026."""
    h, mh = env
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH chốt số"},
                     headers=h).json()["id"]
    line = [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]
    old = client.put("/api/sales-contracts", headers=mh, json={
        "company": UNIT, "code": "HD-LOCK-1", "customer_id": cus, "contract_type": "spot",
        "delivery_type": "single", "sign_date": INSIDE, "delivered_at": INSIDE,
        "channel": "domestic", "source": "exploit", "lines": line})
    assert old.status_code == 200, old.text
    cid = old.json()["contract"]["id"]

    rnd = _round(h)
    client.post("/api/data-lock/confirm", headers=mh,
                json={"round_id": rnd["id"], "company": UNIT})

    # Lần giao TRONG vùng chốt: không sửa, không xoá.
    edit = client.put("/api/sales-contracts", headers=mh, json={
        "id": cid, "company": UNIT, "code": "HD-LOCK-1", "customer_id": cus,
        "contract_type": "spot", "delivery_type": "single", "sign_date": INSIDE,
        "delivered_at": INSIDE, "channel": "domestic",
        "source": "exploit", "lines": [{**line[0], "qty": 99.0}]})
    assert edit.status_code == 403 and "đã được chốt" in edit.json()["detail"]
    assert client.delete(f"/api/sales-contracts/{cid}", headers=mh).status_code == 403

    # Hợp đồng MỚI + lần giao SAU ngày chốt: vẫn làm bình thường.
    fresh = client.put("/api/sales-contracts", headers=mh, json={
        "company": UNIT, "code": "HD-LOCK-2", "customer_id": cus, "contract_type": "spot",
        "delivery_type": "single", "sign_date": INSIDE, "delivered_at": OUTSIDE,
        "channel": "domestic", "source": "exploit", "lines": line})
    assert fresh.status_code == 200, fresh.text
    # …nhưng không được khai LÙI ngày giao vào vùng đã chốt.
    back = client.put("/api/sales-contracts", headers=mh, json={
        "id": fresh.json()["contract"]["id"], "company": UNIT, "code": "HD-LOCK-2",
        "customer_id": cus, "contract_type": "spot", "delivery_type": "single",
        "sign_date": INSIDE, "delivered_at": INSIDE, "channel": "domestic",
        "source": "exploit", "lines": line})
    assert back.status_code == 403


def test_admin_locks_and_unlocks_on_behalf_of_the_unit(env) -> None:
    h, mh = env
    rnd = _round(h)

    assert client.post("/api/data-lock/lock", headers=h,
                       json={"round_id": rnd["id"], "companies": [UNIT]}).json()["count"] == 1
    assert _save_day(mh, INSIDE).status_code == 403
    row = next(r for r in client.get("/api/data-lock/status", headers=h).json()["rows"]
               if r["company"] == UNIT)
    assert row["confirmed"] is True and row["by_admin"] is True

    assert client.post("/api/data-lock/unlock", headers=h,
                       json={"round_id": rnd["id"], "companies": [UNIT]}).json()["count"] == 1
    assert _save_day(mh, INSIDE).status_code == 200


def test_cancelling_a_round_releases_every_lock(env) -> None:
    h, mh = env
    rnd = _round(h)
    client.post("/api/data-lock/confirm", headers=mh,
                json={"round_id": rnd["id"], "company": UNIT})
    assert _save_day(mh, INSIDE).status_code == 403

    assert client.post(f"/api/data-lock/rounds/{rnd['id']}/cancel", headers=h).status_code == 200
    assert _save_day(mh, INSIDE).status_code == 200
    # Bỏ huỷ → khoá trở lại (xác nhận cũ vẫn còn nguyên, không bắt đơn vị bấm lại).
    assert client.post(f"/api/data-lock/rounds/{rnd['id']}/cancel?cancelled=false",
                       headers=h).status_code == 200
    assert _save_day(mh, INSIDE).status_code == 403


def test_summary_shows_the_numbers_and_missing_days(env) -> None:
    h, mh = env
    _round(h)
    assert _save_day(mh, INSIDE, 25).status_code == 200

    s = client.get("/api/data-lock/summary", headers=mh, params={"company": UNIT}).json()
    assert s["lock_date"] == LOCK and s["date_from"] == f"{LOCK[:4]}-01-01"
    assert s["stock"]["stock_warehoused"] == 25          # ảnh chụp tồn kho tại ngày chốt
    assert s["days_entered"]["consumption"] == 1
    assert INSIDE not in s["missing"]["consumption"]     # ngày đã nộp không nằm trong danh sách thiếu
    assert s["missing_total"] >= 1                       # các ngày còn lại của kỳ vẫn đang thiếu


def test_stock_missing_days_start_at_the_tracking_date(env) -> None:
    """Biểu TỒN KHO chỉ thu thập từ `STOCK_TRACKED_FROM` — ngày trước đó KHÔNG bị đòi (26/08/2026).

    Không có ngoại lệ này thì kỳ chốt đầu tiên (tính từ 01/01) đòi hơn 200 ngày mà đơn vị không có
    lỗi — cảnh báo thật chìm nghỉm trong đống ngày ma.
    """
    h, mh = env
    _round(h)
    s = client.get("/api/data-lock/summary", headers=mh, params={"company": UNIT}).json()

    assert s["date_from"] == f"{LOCK[:4]}-01-01"                 # kỳ vẫn tính từ đầu năm…
    assert s["missing_from"]["consumption"] == data_lock_summary.STOCK_TRACKED_FROM
    assert s["missing_from"]["purchase"] == s["date_from"]       # …biểu Thu mua KHÔNG đổi
    assert all(d >= data_lock_summary.STOCK_TRACKED_FROM for d in s["missing"]["consumption"])
    # Số ngày thiếu của tồn kho không thể vượt quá số ngày từ mốc thu thập tới ngày chốt.
    span = (date.fromisoformat(LOCK)
            - date.fromisoformat(data_lock_summary.STOCK_TRACKED_FROM)).days + 1
    assert s["missing_counts"]["consumption"] <= span


def test_only_admin_creates_rounds_and_no_future_lock_date(env) -> None:
    h, mh = env
    assert client.put("/api/data-lock/rounds", headers=mh,
                      json={"lock_date": LOCK, "note": "ZZ TEST"}).status_code == 403
    future = (TODAY + timedelta(days=1)).isoformat()
    bad = client.put("/api/data-lock/rounds", headers=h,
                     json={"lock_date": future, "note": "ZZ TEST"})
    assert bad.status_code == 400 and "tương lai" in bad.json()["detail"]


def test_status_filters_units_that_have_not_confirmed(env) -> None:
    h, mh = env
    rnd = _round(h)
    pending = client.get("/api/data-lock/status", headers=h,
                         params={"only_pending": True, "q": UNIT}).json()
    assert [r["company"] for r in pending["rows"]] == [UNIT]

    client.post("/api/data-lock/confirm", headers=mh,
                json={"round_id": rnd["id"], "company": UNIT})
    after = client.get("/api/data-lock/status", headers=h,
                       params={"only_pending": True, "q": UNIT}).json()
    assert after["rows"] == [] and after["confirmed"] >= 1


def test_member_cannot_confirm_for_another_unit(env) -> None:
    h, mh = env
    rnd = _round(h)
    r = client.post("/api/data-lock/confirm", headers=mh,
                    json={"round_id": rnd["id"], "company": "Công ty Cổ phần Cao Su Bà Rịa"})
    assert r.status_code == 403


def test_another_units_round_does_not_shorten_my_period(env) -> None:
    """Đợt chốt riêng của đơn vị KHÁC không được cắt đầu kỳ của đơn vị chưa chốt lần nào.

    Đã xảy ra thật 27/08/2026: Ban phát thêm một đợt "chốt đến 20/08" cho vài đơn vị sáp nhập, thế
    là 13 đơn vị khác vào xác nhận thấy kỳ chốt chỉ còn 21/08–26/08 thay vì lũy kế từ đầu năm —
    họ ký trên bảng 6 ngày. Đầu kỳ phải tính theo lần chốt trước CỦA CHÍNH ĐƠN VỊ ĐÓ.
    """
    h, mh = env
    rnd = _round(h)                                     # đợt chung, chốt đến hết LOCK
    older = (TODAY - timedelta(days=3)).isoformat()
    client.put("/api/data-lock/rounds",                 # đợt riêng của đơn vị khác, ngày cũ hơn
               json={"lock_date": older, "note": "ZZ TEST"}, headers=h)

    s = client.get(f"/api/data-lock/summary?company={UNIT}&round_id={rnd['id']}", headers=mh).json()
    assert s["date_from"] == f"{LOCK[:4]}-01-01", "đơn vị này chưa chốt lần nào → kỳ tính từ 01/01"
    assert s["prev_lock_date"] is None


def test_my_own_previous_round_does_shorten_my_period(env) -> None:
    """Ngược lại: chính đơn vị đã chốt ở đợt trước thì kỳ mới nối tiếp từ hôm sau mốc đó."""
    h, mh = env
    older = (TODAY - timedelta(days=3)).isoformat()
    first = _round(h, older)
    client.post("/api/data-lock/lock", json={"round_id": first["id"], "companies": [UNIT]},
                headers=h)
    rnd = _round(h)

    s = client.get(f"/api/data-lock/summary?company={UNIT}&round_id={rnd['id']}", headers=mh).json()
    assert s["prev_lock_date"] == older
    assert s["date_from"] == (TODAY - timedelta(days=2)).isoformat()


def test_only_the_units_own_account_can_confirm(env) -> None:
    """XÁC NHẬN là cam kết của chính đơn vị. Trước 29/09/2026 ai có cap `unit_daily` — kể cả mức
    CHỈ XEM — cũng chốt (tức khoá) được số liệu mọi đơn vị; quản trị muốn khoá thì dùng Khoá hộ."""
    h, mh = env
    rnd = _round(h)
    body = {"round_id": rnd["id"], "company": UNIT}
    client.delete("/api/users/zz_lock_viewer", headers=h)
    client.post("/api/users", json={"username": "zz_lock_viewer", "password": "pass123",
                                    "role": "editor", "permissions": ["unit_daily:view"]}, headers=h)
    try:
        vh = {"Authorization": "Bearer " + client.post("/api/auth/login", json={
            "username": "zz_lock_viewer", "password": "pass123"}).json()["access_token"]}
        # Chuyên viên vẫn XEM được bảng số liệu sẽ chốt, nhưng không bấm chốt thay đơn vị.
        assert client.get(f"/api/data-lock/summary?company={UNIT}&round_id={rnd['id']}",
                          headers=vh).status_code == 200
        assert client.post("/api/data-lock/confirm", json=body, headers=vh).status_code == 403
        assert client.post("/api/data-lock/confirm", json=body, headers=h).status_code == 403
        assert _save_day(mh, INSIDE).status_code == 200          # chưa ai chốt được → vẫn sửa
        assert client.post("/api/data-lock/confirm", json=body, headers=mh).status_code == 200
    finally:
        client.delete("/api/users/zz_lock_viewer", headers=h)


def test_regroup_of_locked_delivery_is_blocked(env) -> None:
    """Báo cáo xếp nhóm theo HỒ SƠ MẸ (01/10/2026) nên gắn/gỡ hồ sơ hay đổi HĐNT ↔ HĐDH dời sản
    lượng giữa cột chuyến · HĐNT · dài hạn. Lần giao trong kỳ đã chốt → đơn vị bị chặn, quản trị thì
    không; lần giao sau ngày chốt vẫn gắn bình thường."""
    h, mh = env
    cus = client.put("/api/customers", json={"company": UNIT, "name": "KH đổi nhóm"},
                     headers=h).json()["id"]
    line = [{"grade": "SVR 10 / CSR 10", "qty": 10.0, "price": 40.0, "ccy": "VND"}]
    nt = {"company": UNIT, "code": "NT-RG", "master_type": "principle", "customer_id": cus,
          "lines": [{"grade": "SVR 10 / CSR 10"}]}
    nt["id"] = client.put("/api/master-contracts", headers=h, json=nt).json()["master"]["id"]

    def _hd(code: str, day: str) -> int:
        r = client.put("/api/sales-contracts", headers=mh, json={
            "company": UNIT, "code": code, "customer_id": cus, "contract_type": "spot",
            "delivery_type": "single", "sign_date": INSIDE, "delivered_at": day,
            "channel": "domestic", "source": "exploit", "lines": line})
        assert r.status_code == 200, r.text
        return r.json()["contract"]["id"]

    locked, fresh = _hd("HD-RG-1", INSIDE), _hd("HD-RG-2", OUTSIDE)
    rnd = _round(h)
    client.post("/api/data-lock/confirm", headers=mh, json={"round_id": rnd["id"], "company": UNIT})

    link = lambda hh, ids, attach=True: client.put(  # noqa: E731
        f"/api/master-contracts/{nt['id']}/annexes", headers=hh,
        json={"contract_ids": ids, "attach": attach})
    assert link(mh, [locked]).status_code == 403            # chuyến → HĐNT trong kỳ đã chốt
    assert link(mh, [fresh]).status_code == 200             # giao sau ngày chốt: được
    assert link(h, [locked]).status_code == 200             # quản trị sửa hộ: được
    assert link(mh, [locked], attach=False).status_code == 403
    # Đổi HĐNT → HĐDH dời cả phụ lục đã chốt sang cột dài hạn.
    flip = {**nt, "master_type": "long_term"}
    assert client.put("/api/master-contracts", headers=mh, json=flip).status_code == 403
    # Quản trị gỡ phụ lục đã chốt ra (về "chưa khai loại") → hồ sơ chỉ còn phụ lục sau ngày chốt.
    assert link(h, [locked], attach=False).status_code == 200
    assert client.get(f"/api/sales-contracts/{locked}", headers=h).json()["contract"][
        "contract_type"] is None
    assert client.put("/api/master-contracts", headers=mh, json=flip).status_code == 200
