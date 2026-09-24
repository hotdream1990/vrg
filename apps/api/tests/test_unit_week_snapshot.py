"""Test SNAPSHOT số liệu tuần — bản lưu cố định thu mua · tiêu thụ · tồn kho từng đơn vị.

Ràng buộc phải khoá lại:
1. Trước hạn nhập ngày Chủ nhật → KHÔNG chụp tuần đó; đúng hạn → chụp, tổng khớp Báo cáo tổng hợp
   (`period_report`) cùng kỳ tại thời điểm chụp.
2. Chạy lại → không sinh bản thứ hai, không đè bản cũ (`taken_at` giữ nguyên).
3. Sửa số liệu sau khi chụp → bản lưu KHÔNG đổi (dù báo cáo sống đã đổi).
4. Quyền: admin/chuyên viên/lãnh đạo Tập đoàn xem; đơn vị thành viên 403; "Chụp ngay" chỉ admin.
5. Số NaN/±inf trong số liệu → lưu null, KHÔNG làm job chụp lỗi (jsonb không nhận NaN).
6. Mốc `ref` không kèm múi giờ = giờ VN (không văng TypeError khi so với hạn có múi giờ).

Dùng một tuần đầu 2025 (trước khi có tính năng) để dọn bản lưu của test không bao giờ đụng bản thật.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import edit_window
from app.core.db import db_healthy, session_scope
from app.main import app
from app.services import (
    member_unit_repo, unit_daily_repo, unit_period_report, unit_week_snapshot as svc, user_repo,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
VN = ZoneInfo("Asia/Ho_Chi_Minh")
UNIT_A, UNIT_B = "_zz_snap_a", "_zz_snap_b"
MEMBER, EXEC, PASS = "_zz_snap_member", "_zz_snap_exec", "pass123"

WEEK = date(2025, 1, 6)                                  # thứ Hai; Chủ nhật = 12/01/2025
PREV = WEEK - timedelta(days=7)
BEFORE = datetime(2025, 1, 13, 10, 59, tzinfo=VN)        # N = 1 ⇒ hạn 11:00 thứ Hai 13/01
AFTER = datetime(2025, 1, 13, 11, 0, tzinfo=VN)
D = lambda n: (WEEK + timedelta(days=n)).isoformat()     # noqa: E731 - ngày thứ n trong tuần

PURCHASE = [(UNIT_A, D(1), {"latex_wet": 10.0, "coagulum": 2.0}),
            (UNIT_A, D(3), {"latex_wet": 5.0}),
            (UNIT_B, D(2), {"latex_wet": 7.0, "lace": 1.0})]
STOCK = [(UNIT_A, D(4), {"stock_warehoused": [{"grade": "SVR 10", "qty": 100.0}],
                         "stock_material": 20.0}),
         (UNIT_A, D(6), {"stock_warehoused": [{"grade": "SVR 10", "qty": 90.0}]}),
         (UNIT_B, D(3), {"stock_not_warehoused": [{"grade": "SVR 3L", "qty": 30.0}]})]


def _clear() -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM unit_daily_report WHERE company IN (:a, :b)"),
                   {"a": UNIT_A, "b": UNIT_B})
        db.execute(text("DELETE FROM unit_week_snapshot WHERE week_start IN "
                        "(CAST(:w AS date), CAST(:p AS date))"),
                   {"w": WEEK.isoformat(), "p": PREV.isoformat()})


def _bearer(username: str, password: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def env(monkeypatch):
    """2 đơn vị có số liệu trong tuần + tài khoản admin/member/executive; N = 1, giờ chốt 11:00."""
    monkeypatch.setattr(edit_window, "member_window", lambda: 1)
    monkeypatch.setattr(edit_window, "cutoff_hour", lambda: 11)
    user_repo.seed_admin()
    for u in (UNIT_A, UNIT_B):
        if u not in member_unit_repo.active_names():
            member_unit_repo.add_unit(u)
    for name in (MEMBER, EXEC):
        user_repo.delete_user(name)
    user_repo.create_user(MEMBER, PASS, None, "member", member_units=[UNIT_A])
    user_repo.create_user(EXEC, PASS, None, "executive")
    with session_scope() as db:
        run_mark = db.execute(text("SELECT COALESCE(MAX(id), 0) FROM meta_crawl_run")).scalar()
    _clear()
    for company, day, fields in PURCHASE:
        unit_daily_repo.upsert("purchase", day, company, fields, "test")
    for company, day, fields in STOCK:
        unit_daily_repo.upsert("consumption", day, company, fields, "test")
    yield
    _clear()
    with session_scope() as db:
        db.execute(text("DELETE FROM meta_crawl_run WHERE id > :i AND sources = :s"),
                   {"i": run_mark, "s": svc.JOB_SOURCE})
    for name in (MEMBER, EXEC):
        user_repo.delete_user(name)
    for u in (UNIT_A, UNIT_B):
        member_unit_repo.delete_unit(u)


def _at(monkeypatch, moment: datetime) -> None:
    monkeypatch.setattr(edit_window, "now", lambda: moment)


def _rows(rep: dict) -> dict[str, dict]:
    return {r["company"]: r for r in rep["rows"]}


def test_due_week_follows_sunday_deadline(monkeypatch):
    """Hạn chụp = giờ chốt của Chủ nhật + N ngày; tuần đang chạy chưa bao giờ đủ điều kiện."""
    monkeypatch.setattr(edit_window, "cutoff_hour", lambda: 11)
    monkeypatch.setattr(edit_window, "member_window", lambda: 1)
    assert svc.due_week(BEFORE) == PREV
    assert svc.due_week(AFTER) == WEEK
    assert svc.due_week(AFTER + timedelta(days=6)) == WEEK            # Chủ nhật sau, chưa hết tuần
    monkeypatch.setattr(edit_window, "member_window", lambda: 7)      # N = 7 ⇒ 11:00 CN tuần sau
    assert svc.due_week(datetime(2025, 1, 19, 10, 59, tzinfo=VN)) == PREV
    assert svc.due_week(datetime(2025, 1, 19, 11, 0, tzinfo=VN)) == WEEK


def test_due_week_accepts_naive_ref_as_vn_time(monkeypatch):
    monkeypatch.setattr(edit_window, "cutoff_hour", lambda: 11)
    monkeypatch.setattr(edit_window, "member_window", lambda: 1)
    assert svc.due_week(BEFORE.replace(tzinfo=None)) == PREV
    assert svc.due_week(AFTER.replace(tzinfo=None)) == WEEK


def test_non_finite_numbers_stored_as_null_not_crash(env, monkeypatch):
    """Một ô kế hoạch bẩn (NaN) làm % KH thành NaN → trước đây CAST jsonb lỗi, job hỏng MỌI ngày."""
    real = unit_period_report.period_report

    def dirty(kind, d_from, d_to, *a, **k):
        rep = real(kind, d_from, d_to, *a, **k)
        for r in rep["rows"]:
            if kind == "purchase" and r["company"] == UNIT_A:
                r["pct_plan"], r["latex_wet"] = float("nan"), float("inf")
        return rep
    monkeypatch.setattr(unit_period_report, "period_report", dirty)
    _at(monkeypatch, AFTER)
    res = svc.run_job()
    assert res["sources"][0]["status"] == "ok" and res["persisted"] == 1
    snap = svc.detail(WEEK.isoformat())
    a = _rows(snap["purchase"])[UNIT_A]
    assert a["pct_plan"] is None and a["latex_wet"] is None
    assert snap["totals"]["purchase"]["latex_wet"] is None          # tổng dính inf → null, không lỗi
    assert _rows(snap["purchase"])[UNIT_B]["latex_wet"] == 7.0      # số sạch giữ nguyên


def test_job_takes_week_only_after_deadline_and_matches_period_report(env, monkeypatch):
    _at(monkeypatch, BEFORE)
    res = svc.run_job()
    assert svc.detail(WEEK.isoformat()) is None                      # trước hạn: tuần này chưa chụp
    assert res["sources"][0]["source"] == svc.JOB_SOURCE

    _at(monkeypatch, AFTER)
    res = svc.run_job()
    assert res["persisted"] == 1
    snap = svc.detail(WEEK.isoformat())
    assert snap and snap["taken_by"] == "job" and snap["week_end"] == D(6)
    assert snap["deadline_at"].startswith("2025-01-13T11:00")

    # Khớp tuyệt đối Báo cáo tổng hợp cùng kỳ (số liệu chưa đổi từ lúc chụp).
    for kind in svc.KINDS:
        live = unit_period_report.period_report(kind, D(0), D(6))
        assert snap[kind]["rows"] == live["rows"]
        assert snap["totals"][kind] == svc.totals(live["rows"])
    p = _rows(snap["purchase"])
    assert p[UNIT_A]["total_purchase"] == 17.0 and p[UNIT_B]["total_purchase"] == 8.0
    assert snap["totals"]["purchase"]["latex_wet"] >= 22.0
    c = _rows(snap["consumption"])
    # Tồn kho = số THỜI ĐIỂM của ngày cuối CÓ nhập tồn trong tuần (không cộng dồn các ngày).
    assert (c[UNIT_A]["stock_finished"], c[UNIT_A]["stock_as_of"]) == (90.0, D(6))
    assert (c[UNIT_B]["stock_finished"], c[UNIT_B]["stock_as_of"]) == (30.0, D(3))


def test_rerun_and_later_edits_never_change_snapshot(env, monkeypatch):
    _at(monkeypatch, AFTER)
    svc.run_job()
    first = svc.detail(WEEK.isoformat())

    again = svc.run_job()                                            # chạy lại: không bản thứ hai
    assert again["persisted"] == 0
    with session_scope() as db:
        n = db.execute(text("SELECT count(*) FROM unit_week_snapshot "
                            "WHERE week_start = CAST(:w AS date)"), {"w": WEEK.isoformat()}).scalar()
    assert n == 1

    # Đơn vị sửa số sau lúc chụp → báo cáo sống đổi, bản lưu giữ nguyên.
    unit_daily_repo.upsert("purchase", D(1), UNIT_A, {"latex_wet": 50.0}, "test")
    live = _rows(unit_period_report.period_report("purchase", D(0), D(6)))
    assert live[UNIT_A]["latex_wet"] == 55.0
    later = svc.detail(WEEK.isoformat())
    assert later == first
    assert _rows(later["purchase"])[UNIT_A]["latex_wet"] == 15.0


def test_api_permissions_and_take_now(env, monkeypatch):
    _at(monkeypatch, AFTER)
    admin, member, execu = (_bearer("admin", "admin"), _bearer(MEMBER, PASS), _bearer(EXEC, PASS))

    assert client.get("/api/unit-week-snapshots", headers=member).status_code == 403
    assert client.post("/api/unit-week-snapshots/take", headers=execu).status_code == 403

    r = client.post("/api/unit-week-snapshots/take", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["snapshot"]["taken_by"] == "admin"
    assert client.post("/api/unit-week-snapshots/take", headers=admin).status_code == 409

    lst = client.get("/api/unit-week-snapshots", headers=execu)
    assert lst.status_code == 200
    body = lst.json()
    assert body["status"]["due"]["week_start"] == WEEK.isoformat() and body["status"]["due"]["taken"]
    assert any(i["week_start"] == WEEK.isoformat() for i in body["items"])
    assert client.get(f"/api/unit-week-snapshots/{WEEK}", headers=member).status_code == 403
    assert client.get(f"/api/unit-week-snapshots/{WEEK}", headers=execu).status_code == 200
    assert client.get(f"/api/unit-week-snapshots/{D(1)}", headers=admin).status_code == 400
    x = client.get(f"/api/unit-week-snapshots/{WEEK}/excel", headers=admin)
    assert x.status_code == 200 and x.content[:2] == b"PK"
