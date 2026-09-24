"""Test job "Gửi cảnh báo bất thường cho đơn vị" (`anomaly_notify`) — chạy trên DB thật.

Khoá chặt: đúng MỘT luồng cho mỗi đơn vị có cảnh báo · đơn vị sạch không nhận · đơn vị đã sáp nhập
không nhận riêng (lỗi của nó nằm trong tin của đơn vị nhận) · chạy lại trong ngày không gửi trùng ·
không có luật tính trên số gộp Tập đoàn · email không nổ khi chưa cấu hình SMTP · luật quét lỗi thì
HUỶ cả đợt (không chiếm batch) · một đơn vị dựng tin lỗi không chặn đơn vị khác · thư gửi tuần tự.

Chỉ xoá bản ghi DO TEST TẠO (lượt chạy có id > mốc lúc bắt đầu; dòng lịch chạy trả lại như cũ).
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core import edit_window
from app.core.db import db_healthy, session_scope
from app.core.market_meta import PURCHASE_SOURCE_UNIT
from app.main import app
from app.services import (
    anomaly_notify, anomaly_rules, mailer, member_unit_repo, price_repo, support_notify,
    unit_daily_repo, user_repo,
)
from app.services.anomaly_notify_content import AlertContext, compose

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
VN = ZoneInfo("Asia/Ho_Chi_Minh")

DIRTY, CLEAN, OLD = "_zz_an_dirty", "_zz_an_clean", "_zz_an_old"
UNITS = (DIRTY, CLEAN, OLD)
LEADER = "_zz_an_leader"
NOW = datetime(2026, 7, 26, 11, 5, tzinfo=VN)      # sau giờ chốt 11:00, cửa sổ 1 ngày ⇒ d0 = 25/07
BATCH = "alert-2026-07-26"
LINK = "/canh-bao-bat-thuong?date_from=2026-01-01&date_to=2026-07-25"


def _units(include_inactive: bool = True) -> list[dict]:
    rows = [
        {"name": DIRTY, "region": "R", "is_active": True, "merged_into": None, "merged_at": None},
        {"name": CLEAN, "region": "R", "is_active": True, "merged_into": None, "merged_at": None},
        {"name": OLD, "region": "R", "is_active": False, "merged_into": DIRTY,
         "merged_at": date(2026, 7, 1)},
    ]
    return rows if include_inactive else [u for u in rows if u["is_active"]]


def _run_mark() -> int:
    with session_scope() as db:
        return db.execute(text("SELECT COALESCE(MAX(id), 0) FROM meta_crawl_run")).scalar()


def _wipe(run_mark: int) -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM support_message WHERE thread_id IN "
                        "(SELECT id FROM support_thread WHERE company = ANY(:u))"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM support_thread WHERE company = ANY(:u)"), {"u": list(UNITS)})
        for table, col in (("unit_daily_report", "company"), ("fact_price", "grade"),
                           ("unit_purchase_plan", "company")):
            db.execute(text(f"DELETE FROM {table} WHERE {col} = ANY(:u)"), {"u": list(UNITS)})
        db.execute(text("DELETE FROM meta_crawl_run WHERE sources = :s AND id > :i"),
                   {"s": anomaly_notify.JOB_SOURCE, "i": run_mark})
        db.execute(text("DELETE FROM app_user WHERE username = :u"), {"u": LEADER})


def _price(company: str, day: str, ptype: str, price: float) -> None:
    price_repo.upsert_record({"as_of": day, "source": PURCHASE_SOURCE_UNIT, "grade": company,
                              "contract": "", "price_type": ptype, "price": price,
                              "currency": "VND", "unit": "đồng/độ"})


def _plan(company: str, plan_tonnes: float | None, full: bool) -> None:
    other = 0 if full else None
    with session_scope() as db:
        db.execute(text(
            "INSERT INTO unit_purchase_plan (year, company, plan_tonnes, plan_sales_spot_tonnes, "
            "signed_lt_tonnes, carry_lt_tonnes, carry_spot_tonnes) VALUES (2026, :c, :p, :o, :o, :o, :o)"),
            {"c": company, "p": plan_tonnes, "o": other})


@pytest.fixture()
def env(monkeypatch):
    """DIRTY: thiếu biểu (kể cả d0) + giá mủ sai + thiếu đơn giá + KH năm thiếu; CLEAN: đủ hết;
    OLD: đã sáp nhập vào DIRTY, có một ô giá sai của riêng nó. Email được ghi lại, không gửi thật."""
    user_repo.seed_admin()
    run_mark = _run_mark()
    _wipe(run_mark)
    monkeypatch.setattr(edit_window, "now", lambda: NOW)
    monkeypatch.setattr(edit_window, "member_window", lambda: 1)
    monkeypatch.setattr(member_unit_repo, "list_units", _units)
    monkeypatch.setattr(mailer, "base_url", lambda: "https://vrg.example.vn")
    sent: list[dict] = []
    real_send = mailer.send

    def _record(to, subject, body):   # vẫn gọi ĐÚNG hàm gửi thật (DB test không có SMTP → báo lỗi êm)
        result = real_send(list(to), subject, body)
        sent.append({"to": list(to), "subject": subject, "body": body, "result": result})
        return result
    monkeypatch.setattr(mailer, "send", _record)
    monkeypatch.setattr(mailer, "send_async", _record)
    monkeypatch.setattr(support_notify, "_in_background", lambda fn, *a: fn(*a))   # chạy đồng bộ

    unit_daily_repo.upsert("purchase", "2026-07-20", DIRTY, {"latex_wet": 5.0, "coagulum": 2.5}, "t")
    _price(DIRTY, "2026-07-20", "purchase", 25000)          # mủ nước: gõ nhầm đồng/kg
    _price(OLD, "2026-06-01", "purchase", 30000)            # lỗi còn tồn của đơn vị đã sáp nhập
    _plan(DIRTY, 100, full=False)
    _plan(CLEAN, 0, full=True)                              # 0 = không tổ chức thu mua, đã khai
    for day in ("2026-07-24", "2026-07-25"):
        unit_daily_repo.upsert("consumption", day, CLEAN, {"no_stock": True}, "t")
    user_repo.create_user(LEADER, "pass123", "Lãnh đạo test", "leader",
                          member_units=[DIRTY], email="leader@example.vn")
    yield sent
    _wipe(run_mark)


def _threads() -> list[dict]:
    with session_scope() as db:
        return [dict(r) for r in db.execute(text(
            "SELECT t.id, t.company, t.kind, t.subject, t.batch_id, t.created_by, m.author, "
            "m.author_name, m.body FROM support_thread t JOIN support_message m ON m.thread_id = t.id "
            "WHERE t.company = ANY(:u) ORDER BY t.id"), {"u": list(UNITS)}).mappings().all()]


def test_alert_window_follows_cutoff_and_member_window(monkeypatch) -> None:
    monkeypatch.setattr(edit_window, "member_window", lambda: 1)
    run_day, d0, deadline = anomaly_notify.alert_window(datetime(2026, 9, 24, 11, 5, tzinfo=VN))
    assert (run_day, d0) == (date(2026, 9, 24), date(2026, 9, 23))
    assert deadline == datetime(2026, 9, 24, 11, 0, tzinfo=VN)
    # Chạy bù buổi sáng (trước giờ chốt) ⇒ mốc là giờ chốt HÔM QUA, không nhắc sớm ngày còn hạn.
    assert anomaly_notify.alert_window(datetime(2026, 9, 24, 9, 0, tzinfo=VN))[:2] == (
        date(2026, 9, 23), date(2026, 9, 22))
    monkeypatch.setattr(edit_window, "member_window", lambda: 0)
    assert anomaly_notify.alert_window(datetime(2026, 9, 24, 11, 5, tzinfo=VN))[1] == date(2026, 9, 24)


def test_compose_never_mentions_group_wide_rules() -> None:
    """Luật doanh thu toàn Tập đoàn lộ số của đơn vị khác → không bao giờ vào tin của đơn vị."""
    ctx = AlertContext(DIRTY, date(2026, 9, 23), datetime(2026, 9, 24, 11, 0, tzinfo=VN),
                       date(2026, 9, 24), "2026-01-01", "2026-09-23")
    revenue = {"key": "revenue_outlier", "label": "Doanh thu một ngày bất thường", "count": 1,
               "rows": [{"don_vi": DIRTY, "ngay": "2026-09-01"}]}
    assert compose(ctx, {"groups": [revenue]}) is None
    plan = {"key": "plan_missing", "label": "x", "count": 1,
            "rows": [{"don_vi": DIRTY, "o_con_thieu": "KH thu mua"}]}
    msg = compose(ctx, {"groups": [revenue, plan]})
    assert msg and "Doanh thu" not in msg["body"] and "Còn trống: KH thu mua." in msg["body"]
    assert msg["subject"] == "Cảnh báo số liệu — tính đến 11:00 ngày 24/09/2026"
    assert msg["body"].startswith("Tính đến 11:00 hôm nay (hết hạn nhập số liệu ngày 23/09/2026), "
                                  f"đơn vị {DIRTY} còn các vấn đề sau:")


def test_job_sends_one_thread_per_unit_with_issues(env) -> None:
    res = anomaly_notify.run_job()
    assert res["sources"][0]["status"] == "ok"
    rows = _threads()
    assert [r["company"] for r in rows] == [DIRTY]            # CLEAN sạch · OLD đã sáp nhập
    t = rows[0]
    assert (t["kind"], t["batch_id"], t["created_by"], t["author"]) == ("alert", BATCH, "system", "system")
    assert t["author_name"] == anomaly_notify.AUTHOR_NAME
    assert t["subject"] == "Cảnh báo số liệu — tính đến 11:00 ngày 26/07/2026"
    body = t["body"]
    assert "Tính đến 11:00 hôm nay (hết hạn nhập số liệu ngày 25/07/2026)" in body
    assert "Biểu Thu mua: chưa nộp ngày 25/07/2026 (vừa hết hạn)." in body
    assert "01/01–19/07, 21/07–25/07" in body                 # gộp đoạn ngày liền nhau
    assert "Biểu Tiêu thụ – Tồn kho: chưa nộp ngày 25/07/2026 (vừa hết hạn). Từ 24/07/2026" in body
    assert "Mủ nước: 1 ô giá 25.000 đồng/độ." in body
    assert f"Mủ nước: 1 ô giá 30.000 đồng/độ (số liệu của {OLD})." in body
    assert "Ngày 20/07/2026: Mủ chén (2,5 tấn)." in body
    assert "Chưa khai đủ Kế hoạch năm 2026" in body
    assert "Doanh thu" not in body
    assert f"Xem chi tiết tại Cảnh báo bất thường: {LINK}" in body
    # Email: 1 thư cho lãnh đạo đúng đơn vị, có link TUYỆT ĐỐI; thiếu SMTP → báo lỗi êm, không nổ.
    assert len(env) == 1 and env[0]["to"] == ["leader@example.vn"]
    assert f"https://vrg.example.vn{LINK}" in env[0]["body"]
    assert env[0]["result"][0] is False
    assert res["alerts"]["no_leader"] == [] and res["alerts"]["clean"] == 1


def test_rerun_same_day_does_not_duplicate(env) -> None:
    first = anomaly_notify.send_alerts()
    second = anomaly_notify.send_alerts()
    again = anomaly_notify.run_job()
    assert first["created"] == [DIRTY]
    assert second["created"] == [] and second["skipped"] == [DIRTY]
    assert again["sources"][0]["status"] == "empty"
    assert len(_threads()) == 1 and len(env) == 1              # không thêm luồng, không thêm email


def test_unit_without_leader_still_gets_thread(env) -> None:
    with session_scope() as db:
        db.execute(text("DELETE FROM app_user WHERE username = :u"), {"u": LEADER})
    res = anomaly_notify.send_alerts()
    assert res["created"] == [DIRTY] and res["no_leader"] == [DIRTY]
    assert env == [] and "chưa có tài khoản lãnh đạo" in res["note"]


def _bearer(u: str, p: str) -> dict[str, str]:
    t = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_leader_reads_and_replies_hq_sees_alert_batch(env) -> None:
    anomaly_notify.send_alerts()
    lead = _bearer(LEADER, "pass123")
    rows = client.get("/api/support/threads", headers=lead).json()["rows"]
    alert = next(r for r in rows if r["kind"] == "alert")
    r = client.post(f"/api/support/threads/{alert['id']}/reply",
                    json={"body": "Đơn vị đã nhận, sẽ bổ sung.", "files": []}, headers=lead)
    assert r.status_code == 200
    batches = client.get("/api/support/batches", headers=_bearer("admin", "admin")).json()["rows"]
    mine = next(b for b in batches if b["batch_id"] == BATCH)
    assert mine["kind"] == "alert" and mine["unit_count"] == 1 and mine["unread_count"] == 1


def _boom(*_a, **_k):
    raise RuntimeError("statement timeout (giả lập)")


def test_scan_error_aborts_whole_batch_and_can_rerun(env, monkeypatch) -> None:
    """Đọc "đã nộp" lỗi → not_submitted/silent_unit chạy trên dữ liệu rỗng (mọi đơn vị hoá ra "chưa
    nộp"). Phải HUỶ cả đợt, lượt chạy `error` kèm tên luật, batch không bị chiếm để gửi lại."""
    real_in_range = unit_daily_repo.in_range
    monkeypatch.setattr(unit_daily_repo, "in_range", _boom)
    res = anomaly_notify.run_job()
    src = res["sources"][0]
    assert src["status"] == "error" and res["alerts"]["aborted"] is True
    assert "Chưa nộp / thiếu một phần" in src["note"] and "Đơn vị ngừng nộp nhiều ngày" in src["note"]
    assert _threads() == [] and env == []                    # không luồng nào, không email nào
    with session_scope() as db:
        st, err = db.execute(text("SELECT status, error FROM meta_crawl_run WHERE id = :i"),
                             {"i": res["run_id"]}).one()
    assert st == "error" and "Chưa nộp / thiếu một phần" in err
    # Trang xem vẫn trả kết quả như cũ — chỉ thêm cờ lỗi trên đúng 2 nhóm.
    page = anomaly_rules.scan("2026-01-01", "2026-07-25", {})
    flagged = {g["key"] for g in page["groups"] if g.get(anomaly_rules.ERROR_FLAG)}
    assert {"not_submitted", "silent_unit"} <= flagged

    monkeypatch.setattr(unit_daily_repo, "in_range", real_in_range)   # DB hồi → chạy lại gửi được
    again = anomaly_notify.run_job()
    assert again["sources"][0]["status"] == "ok" and again["alerts"]["created"] == [DIRTY]


def test_single_rule_error_is_flagged_explicitly(env, monkeypatch) -> None:
    """Luật lỗi được đánh dấu bằng CỜ (không dò chữ mô tả) → job huỷ đợt, nêu đúng tên luật."""
    broken = anomaly_rules._rule("wrong_raw_price", "Giá mủ nguyên liệu sai đơn vị tính")(_boom)
    monkeypatch.setattr(anomaly_rules, "_wrong_raw_price", broken)
    res = anomaly_notify.send_alerts()
    assert res["aborted"] and res["failed_rules"] == ["Giá mủ nguyên liệu sai đơn vị tính"]
    assert res["created"] == [] and _threads() == []


def test_one_unit_compose_error_does_not_block_others(env, monkeypatch) -> None:
    """Dựng tin lỗi ở MỘT đơn vị → bỏ qua đơn vị đó, ghi vào note; đơn vị khác vẫn nhận tin."""
    real = anomaly_notify.compose

    def flaky(ctx, result):
        if ctx.unit == CLEAN:
            raise TypeError("dòng thiếu field (giả lập)")
        return real(ctx, result)
    monkeypatch.setattr(anomaly_notify, "compose", flaky)
    res = anomaly_notify.run_job()
    src = res["sources"][0]
    assert src["status"] == "warning" and res["alerts"]["created"] == [DIRTY]
    assert res["alerts"]["compose_failed"] == [CLEAN] and res["alerts"]["clean"] == 0
    assert f"{anomaly_notify.BROKEN_NOTE} 1 đơn vị (xem log): {CLEAN}" in src["note"]


def test_batch_mail_sent_in_order_in_one_background_call(monkeypatch) -> None:
    """Cả đợt thư gửi TUẦN TỰ trong MỘT lần chạy nền; một thư lỗi không chặn các thư sau."""
    tried: list[str] = []
    runs: list[int] = []

    def fake_send(to, subject, body):
        tried.append(subject)
        if subject == "b":
            raise OSError("421 too many connections")
        return subject != "c", "lỗi giả lập"
    monkeypatch.setattr(mailer, "send", fake_send)
    monkeypatch.setattr(support_notify, "_in_background", lambda fn, *a: runs.append(fn(*a)))
    support_notify.send_batch([(u, (["x@example.vn"], u.lower(), "nội dung")) for u in "ABCD"])
    assert tried == ["a", "b", "c", "d"] and runs == [2]


def test_job_registered_and_seeded_off() -> None:
    """Job gửi tin ra ngoài hằng ngày → tạo lần đầu ở trạng thái TẮT; admin bật rồi thì khởi động
    lại (seed lại) không được tắt nó đi. Dòng lịch thật (nếu có) được trả lại NGUYÊN như cũ."""
    from app.services import schedule_repo, scheduler

    name = anomaly_notify.JOB_NAME
    meta = scheduler.JOB_REGISTRY[name]
    assert meta["catch_up"] and meta["seed_off"] and meta["default"] == (12, 0, None)
    with session_scope() as db:
        before = db.execute(text("SELECT * FROM schedule_job WHERE name = :n"),
                            {"n": name}).mappings().first()
        before = dict(before) if before else None
        db.execute(text("DELETE FROM schedule_job WHERE name = :n"), {"n": name})
    try:
        schedule_repo.seed_defaults({name: meta["default"]}, disabled={name})
        assert next(j for j in schedule_repo.list_jobs() if j["name"] == name)["enabled"] is False
        schedule_repo.update_job(name, 11, 5, True)
        schedule_repo.seed_defaults({name: meta["default"]}, disabled={name})
        assert next(j for j in schedule_repo.list_jobs() if j["name"] == name)["enabled"] is True
    finally:
        with session_scope() as db:
            db.execute(text("DELETE FROM schedule_job WHERE name = :n"), {"n": name})
            if before:
                cols = ", ".join(before)
                db.execute(text(f"INSERT INTO schedule_job ({cols}) VALUES "
                                f"({', '.join(':' + c for c in before)})"), before)
