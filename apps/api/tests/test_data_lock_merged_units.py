"""CHỐT KÈM đơn vị đã sáp nhập (phản ánh của Chư prông 29/09/2026).

Hợp đồng ký trước sáp nhập đứng tên đơn vị cũ nhưng do đơn vị nhận giao nốt; tài khoản đơn vị chỉ
gán đơn vị nhận nên không ai phía đơn vị chốt được dòng của đơn vị cũ. Khoá lại:
  - bảng chốt của đơn vị nhận bày kèm số của đơn vị cũ, theo kỳ chốt RIÊNG của đơn vị cũ;
  - đơn vị nhận xác nhận → đơn vị cũ cũng chốt, có ảnh chụp riêng;
  - Ban khoá hộ / mở khoá đơn vị nhận → đơn vị cũ đi cùng; mở khoá riêng đơn vị cũ không kéo ai.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import member_unit_merge, member_unit_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
NEW, OLD = "_ZZ Lock Merge Nhan", "_ZZ Lock Merge Cu"
USER = "zz_lock_merge"
TODAY = date.today()
# Ngày chốt sát hôm nay CÓ CHỦ Ý — xem ghi chú cùng chỗ ở test_data_lock.py.
LOCK = (TODAY - timedelta(days=1)).isoformat()
D_MERGE = (TODAY - timedelta(days=20)).isoformat()
PREV_OLD = (TODAY - timedelta(days=25)).isoformat()   # đơn vị cũ từng được khoá hộ tới ngày này


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _login(username: str, password: str) -> dict[str, str]:
    tok = client.post("/api/auth/login",
                      json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _cleanup(h: dict[str, str]) -> None:
    client.delete(f"/api/users/{USER}", headers=h)
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_data_lock WHERE company = ANY(:c)"), {"c": [NEW, OLD]})
        db.execute(text("DELETE FROM data_lock_round WHERE note LIKE 'ZZ MERGE%'"))
    for u in (OLD, NEW):
        try:
            member_unit_merge.unmerge(u)
        except ValueError:
            pass
        member_unit_repo.delete_unit(u)


@pytest.fixture()
def env():
    h = _login("admin", "admin")
    _cleanup(h)
    member_unit_repo.add_unit(NEW)
    member_unit_repo.add_unit(OLD)
    member_unit_merge.merge(OLD, NEW, D_MERGE)
    client.post("/api/users", json={"username": USER, "password": "pass123",
                                    "role": "member", "member_units": [NEW]}, headers=h)
    yield h, _login(USER, "pass123")
    _cleanup(h)


def _round(h: dict[str, str], lock_date: str, note: str = "ZZ MERGE") -> dict:
    r = client.put("/api/data-lock/rounds", json={"lock_date": lock_date, "note": note}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["round"]


def _status(h: dict[str, str], rid: int) -> dict[str, dict]:
    """Xác nhận THÔ của từng pháp nhân trong đợt — bảng theo dõi không còn dòng đơn vị cũ."""
    from app.services import data_lock_repo

    got = data_lock_repo.confirms_of_round(rid)
    return {c: {"confirmed": c in got, "confirmed_by": (got.get(c) or {}).get("locked_by"),
                "by_admin": bool((got.get(c) or {}).get("by_admin")),
                "snapshot": (got.get(c) or {}).get("snapshot")} for c in (NEW, OLD)}


def test_summary_lists_merged_unit_with_its_own_period(env) -> None:
    h, mh = env
    # Đợt cũ Ban đã khoá hộ riêng đơn vị cũ ⇒ kỳ của đơn vị cũ nối tiếp mốc đó, KHÔNG theo đơn vị nhận.
    old_rnd = _round(h, PREV_OLD, "ZZ MERGE old")
    client.post("/api/data-lock/lock", headers=h, json={"round_id": old_rnd["id"], "companies": [OLD]})
    rnd = _round(h, LOCK)

    got = client.get(f"/api/data-lock/summary?company={NEW}&round_id={rnd['id']}", headers=mh).json()
    assert got["company"] == NEW and got["date_from"] == f"{LOCK[:4]}-01-01"
    [m] = got["merged_units"]
    assert m["company"] == OLD and m["confirmed"] is False
    assert m["date_from"] == (date.fromisoformat(PREV_OLD) + timedelta(days=1)).isoformat()


def test_member_confirm_also_locks_the_merged_unit(env) -> None:
    h, mh = env
    rnd = _round(h, LOCK)

    r = client.post("/api/data-lock/confirm", json={"round_id": rnd["id"], "company": NEW}, headers=mh)
    assert r.status_code == 200, r.text
    st = _status(h, rnd["id"])
    assert st[NEW]["confirmed"] and st[OLD]["confirmed"]
    assert st[OLD]["confirmed_by"] == USER and st[OLD]["by_admin"] is False
    assert st[OLD]["snapshot"]["company"] == OLD           # ảnh chụp RIÊNG của đơn vị cũ

    # Bảng chốt đọc lại: đơn vị cũ hiện "đã chốt".
    got = client.get(f"/api/data-lock/summary?company={NEW}&round_id={rnd['id']}", headers=mh).json()
    assert got["merged_units"][0]["confirmed"] is True


def test_admin_lock_and_unlock_carry_the_merged_unit(env) -> None:
    h, _ = env
    rnd = _round(h, LOCK)
    body = {"round_id": rnd["id"], "companies": [NEW]}

    assert client.post("/api/data-lock/lock", headers=h, json=body).json()["count"] == 2
    st = _status(h, rnd["id"])
    assert st[NEW]["confirmed"] and st[OLD]["confirmed"] and st[OLD]["by_admin"]

    assert client.post("/api/data-lock/unlock", headers=h, json=body).json()["count"] == 2
    st = _status(h, rnd["id"])
    assert not st[NEW]["confirmed"] and not st[OLD]["confirmed"]

    # Chiều ngược lại KHÔNG kéo: khoá/mở riêng đơn vị cũ chỉ đụng đơn vị cũ.
    only_old = {"round_id": rnd["id"], "companies": [OLD]}
    assert client.post("/api/data-lock/lock", headers=h, json=only_old).json()["count"] == 1
    assert not _status(h, rnd["id"])[NEW]["confirmed"]


def test_banner_reopens_when_only_the_receiving_unit_is_confirmed(env) -> None:
    """Đơn vị nhận chốt TRƯỚC khi có chốt kèm (hoặc Ban duyệt đề nghị sửa làm gỡ khoá riêng đơn vị
    cũ) → banner phải mời xác nhận lại; bấm lại chỉ chốt thêm đơn vị cũ, ảnh chụp cũ giữ nguyên."""
    from app.services import data_lock_repo

    h, mh = env
    rnd = _round(h, LOCK)
    data_lock_repo.confirm(rnd["id"], NEW, USER, snapshot={"company": NEW, "mark": "cu"})

    unit = client.get("/api/data-lock/current", headers=mh).json()["units"][0]
    assert unit["company"] == NEW and unit["confirmed"] is False

    client.post("/api/data-lock/confirm", json={"round_id": rnd["id"], "company": NEW}, headers=mh)
    st = _status(h, rnd["id"])
    assert st[OLD]["confirmed"] and st[NEW]["snapshot"]["mark"] == "cu"
    assert client.get("/api/data-lock/current", headers=mh).json()["units"][0]["confirmed"] is True


def test_status_folds_the_merged_unit_into_the_receiving_row(env) -> None:
    """Bảng theo dõi của Ban: đơn vị đã sáp nhập KHÔNG có dòng riêng, không vào mẫu số; dòng đơn
    vị nhận ghi kèm đơn vị cũ và chỉ "đã chốt" khi chốt xong cả hai (chốt 29/09/2026)."""
    from app.services import data_lock_repo

    h, mh = env
    rnd = _round(h, LOCK)
    url = f"/api/data-lock/status?round_id={rnd['id']}"
    before = client.get(url, headers=h).json()
    names = [r["company"] for r in before["rows"]]
    assert NEW in names and OLD not in names
    row = next(r for r in before["rows"] if r["company"] == NEW)
    assert [(m["company"], m["confirmed"]) for m in row["merged_units"]] == [(OLD, False)]

    # Gõ tên đơn vị CŨ vẫn tìm ra dòng đơn vị nhận.
    found = client.get(f"{url}&q=Merge Cu", headers=h).json()["rows"]
    assert [r["company"] for r in found] == [NEW]

    # Chỉ đơn vị nhận chốt (như trước khi có chốt kèm) → dòng vẫn "chưa xong", nằm trong lọc chưa xác nhận.
    data_lock_repo.confirm(rnd["id"], NEW, USER, snapshot={"company": NEW})
    pend = client.get(f"{url}&only_pending=true", headers=h).json()
    row = next(r for r in pend["rows"] if r["company"] == NEW)
    assert row["confirmed"] is False and row["confirmed_at"]
    assert _listed_locked(h, rnd["id"]) == pend["confirmed"]      # ô chọn đợt đếm cùng luật

    client.post("/api/data-lock/confirm", json={"round_id": rnd["id"], "company": NEW}, headers=mh)
    after = client.get(url, headers=h).json()
    row = next(r for r in after["rows"] if r["company"] == NEW)
    assert row["confirmed"] is True and row["merged_units"][0]["confirmed"] is True
    assert after["total"] == before["total"] and after["confirmed"] == before["confirmed"] + 1
    # Số "đã chốt" ở ô chọn đợt cũng không đếm đơn vị cũ.
    assert _listed_locked(h, rnd["id"]) == after["confirmed"]


def _listed_locked(h: dict[str, str], rid: int) -> int:
    items = client.get("/api/data-lock/rounds", headers=h).json()["items"]
    return next(x for x in items if x["id"] == rid)["locked"]


def test_impersonated_confirm_is_recorded_as_the_admin(env) -> None:
    """Quản trị đăng nhập hộ đơn vị rồi bấm xác nhận: vẫn chốt được (hỗ trợ qua điện thoại) nhưng
    bản ghi mang tên người thật + cờ Ban khoá — không trông như đơn vị tự ký."""
    h, _ = env
    rnd = _round(h, LOCK)
    imp = client.post("/api/auth/impersonate", json={"username": USER}, headers=h).json()
    ih = {"Authorization": f"Bearer {imp['access_token']}"}

    assert client.post("/api/data-lock/confirm", json={"round_id": rnd["id"], "company": NEW},
                       headers=ih).status_code == 200
    st = _status(h, rnd["id"])
    for c in (NEW, OLD):
        assert st[c]["by_admin"] is True and st[c]["confirmed_by"] == "admin"


def test_status_row_and_banner_carry_the_merged_units_numbers(env) -> None:
    """Dòng đơn vị nhận mang số đã chốt của đơn vị cũ (để cộng như Báo cáo tổng hợp); banner trả
    mốc khoá đơn vị cũ cho màn Đề nghị sửa hợp đồng đứng tên họ."""
    from app.services import data_lock_repo

    h, mh = env
    rnd = _round(h, LOCK)
    data_lock_repo.confirm(rnd["id"], NEW, USER, snapshot={"consumption": {"total_consumption": 10}})
    data_lock_repo.confirm(rnd["id"], OLD, USER, snapshot={"consumption": {"total_consumption": 2.5},
                                                          "purchase": {"total_purchase": 1}})
    rows = client.get(f"/api/data-lock/status?round_id={rnd['id']}", headers=h).json()["rows"]
    [m] = next(r for r in rows if r["company"] == NEW)["merged_units"]
    assert m == {"company": OLD, "confirmed": True, "total_purchase": 1, "total_consumption": 2.5}

    cur = client.get("/api/data-lock/current", headers=mh).json()
    assert cur["merged_locked_until"] == {OLD: LOCK}
