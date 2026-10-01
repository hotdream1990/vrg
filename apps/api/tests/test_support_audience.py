"""Test NGƯỜI NHẬN thẻ Hỗ trợ & Thông báo (chốt 01/10/2026).

Mỗi thẻ có nhóm người nhận trong đơn vị (`audience`): lãnh đạo và/hoặc chuyên viên theo loại nhập
liệu. Phải khoá chặt:
1. Thẻ chỉ hiện với ĐÚNG nhóm được chọn — kể cả lãnh đạo cũng không thấy thẻ không gửi cho mình.
2. "Đã đọc" phía đơn vị tính theo TỪNG NGƯỜI.
3. Email + Web Push chỉ tới đúng nhóm, push vẫn đi khi chưa cấu hình SMTP.
4. Cách ly đơn vị giữ nguyên: một thẻ = một đơn vị.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.db import db_healthy, session_scope
from app.main import app
from app.routers.support_scope import store
from app.services import (
    edit_request_notify, mailer, support_notify, support_reminder_repo, support_repo, user_repo,
    web_push,
)

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

UNIT_A, UNIT_B = "_zz_au_don_vi_a", "_zz_au_don_vi_b"
PASSWORD = "pass123"
#: khoá → (username, role, đơn vị, loại nhập liệu, quyền)
ACCOUNTS = {
    "lead": ("au_lead_a", "leader", [UNIT_A], None, None),
    "pur": ("au_pur_a", "member", [UNIT_A], ["purchase"], None),
    "sto": ("au_sto_a", "member", [UNIT_A], ["stock"], None),
    "lead_b": ("au_lead_b", "leader", [UNIT_B], None, None),
    "pur_b": ("au_pur_b", "member", [UNIT_B], ["purchase"], None),
    "nounit": ("au_nounit", "member", [UNIT_A], ["purchase"], None),
    "hq": ("au_hq", "editor", [], None, ["support"]),
}


def _sql(sql: str, **params) -> None:
    with session_scope() as db:
        db.execute(text(sql), params)


def _bearer(username: str, password: str = PASSWORD) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _wipe_threads() -> None:
    with session_scope() as db:
        ids = db.execute(text("SELECT id FROM support_thread WHERE company = ANY(:c)"),
                         {"c": [UNIT_A, UNIT_B]}).scalars().all()
    for tid in ids:
        support_repo.delete_thread(int(tid))


def _cleanup(h: dict[str, str]) -> None:
    _wipe_threads()
    _sql("DELETE FROM support_reminder WHERE created_by = 'au_hq'")
    for username, *_ in ACCOUNTS.values():
        client.delete(f"/api/users/{username}", headers=h)
    for unit in (UNIT_A, UNIT_B):
        client.delete(f"/api/member-units/{unit}", headers=h)


@pytest.fixture(scope="module")
def env():
    user_repo.seed_admin()
    h = _bearer("admin", "admin")
    _cleanup(h)
    for unit in (UNIT_A, UNIT_B):
        client.post("/api/member-units", json={"name": unit}, headers=h)
    for username, role, units, types, perms in ACCOUNTS.values():
        body = {"username": username, "password": PASSWORD, "role": role, "member_units": units}
        if types:
            body["entry_types"] = types
        if perms:
            body["permissions"] = perms
        assert client.post("/api/users", json=body, headers=h).status_code == 200, username
        _sql("UPDATE app_user SET email = :e WHERE username = :u", e=f"{username}@example.vn",
             u=username)
        if types:   # ghi thẳng DB: không phụ thuộc màn quản trị người dùng đang làm song song
            _sql("UPDATE app_user SET entry_types = CAST(:t AS jsonb) WHERE username = :u",
                 t=json.dumps(types), u=username)
    _sql("UPDATE app_user SET member_units = '[]'::jsonb WHERE username = 'au_nounit'")
    heads = {k: _bearer(v[0]) for k, v in ACCOUNTS.items() if k != "nounit"}
    yield {"admin": h, **heads}
    _cleanup(h)


@pytest.fixture(autouse=True)
def sent(monkeypatch):
    """Ghi lại email + push thay vì gửi thật (DB dev là bản sao prod — không gửi ra ngoài)."""
    log: dict[str, list] = {"push": [], "mail": [], "batches": []}

    def _batch(items):   # một lần gọi = một luồng nền gửi cả đợt
        items = list(items)
        log["batches"].append(len(items))
        log["push"].extend({"to": list(usernames), "title": title, "body": body, "url": url,
                            "tag": tag} for usernames, title, body, url, tag in items)

    monkeypatch.setattr(web_push, "send_batch_async", _batch)
    monkeypatch.setattr(mailer, "send_async",
                        lambda to, subject, body: log["mail"].append({"to": list(to), "subject": subject}))
    yield log
    _wipe_threads()


def _announce(env, audience, subject, units=(UNIT_A,)):
    return client.post("/api/support/announcements",
                       json={"subject": subject, "body": "Nội dung thử", "scope": "units",
                             "units": list(units), "audience": audience}, headers=env["hq"])


def _rows(headers, **params) -> list[dict]:
    return client.get("/api/support/threads", params=params, headers=headers).json()["rows"]


def _tid(headers, subject) -> int | None:
    return next((x["id"] for x in _rows(headers) if x["subject"] == subject), None)


def _unread(headers) -> int:
    return client.get("/api/support/unread", headers=headers).json()["count"]


def test_thong_bao_chi_gui_cv_thu_mua(env, sent) -> None:
    """["purchase"]: CV Thu mua thấy; lãnh đạo + CV Tồn kho của CHÍNH đơn vị đó không thấy gì."""
    r = _announce(env, ["purchase"], "Bổ sung giá thu mua")
    assert r.status_code == 200 and r.json()["audience"] == ["purchase"]
    tid = _tid(env["pur"], "Bổ sung giá thu mua")
    assert tid and _unread(env["pur"]) == 1
    detail = client.get(f"/api/support/threads/{tid}", headers=env["pur"]).json()
    assert detail["thread"]["audience"] == ["purchase"]

    for who in ("lead", "sto"):
        assert _tid(env[who], "Bổ sung giá thu mua") is None
        assert client.get(f"/api/support/threads/{tid}", headers=env[who]).status_code == 404
        assert _unread(env[who]) == 0
        assert client.post(f"/api/support/threads/{tid}/reply", json={"body": "x"},
                           headers=env[who]).status_code == 404
    # Tập đoàn thấy nhóm người nhận ở cả danh sách luồng lẫn danh sách đợt gửi.
    hq_row = next(x for x in _rows(env["hq"], company=UNIT_A) if x["id"] == tid)
    assert hq_row["audience"] == ["purchase"]
    batch = next(b for b in client.get("/api/support/batches", headers=env["hq"]).json()["rows"]
                 if b["subject"] == "Bổ sung giá thu mua")
    assert batch["audience"] == ["purchase"]
    # Email + push chỉ tới CV Thu mua của đơn vị.
    assert [p["to"] for p in sent["push"]] == [["au_pur_a"]]
    assert sent["push"][0]["url"] == f"/ho-tro/{tid}"
    assert sent["push"][0]["title"] == support_notify.PUSH_ANNOUNCE
    assert [m["to"] for m in sent["mail"]] == [["au_pur_a@example.vn"]]


def test_lanh_dao_va_cv_ton_kho(env, sent) -> None:
    """["stock","leader"] → lưu theo thứ tự chuẩn, lãnh đạo + CV Tồn kho thấy, CV Thu mua không."""
    _announce(env, ["stock", "leader"], "Kiểm kê tồn kho cuối tháng")
    tid = _tid(env["lead"], "Kiểm kê tồn kho cuối tháng")
    assert tid and _tid(env["sto"], "Kiểm kê tồn kho cuối tháng") == tid
    assert client.get(f"/api/support/threads/{tid}", headers=env["pur"]).status_code == 404
    thread = client.get(f"/api/support/threads/{tid}", headers=env["lead"]).json()["thread"]
    assert thread["audience"] == ["leader", "stock"]
    assert sorted(sent["push"][0]["to"]) == ["au_lead_a", "au_sto_a"]


def test_nhieu_don_vi_van_cach_ly(env, sent) -> None:
    """Gửi 2 đơn vị cùng nhóm → 2 thẻ riêng, push/email từng đơn vị không lẫn người nhận."""
    _announce(env, ["purchase"], "Thông báo hai đơn vị", units=(UNIT_A, UNIT_B))
    id_a, id_b = _tid(env["pur"], "Thông báo hai đơn vị"), _tid(env["pur_b"], "Thông báo hai đơn vị")
    assert id_a and id_b and id_a != id_b
    assert client.get(f"/api/support/threads/{id_b}", headers=env["pur"]).status_code == 404
    assert sorted(p["to"] for p in sent["push"]) == [["au_pur_a"], ["au_pur_b"]]
    assert sent["batches"] == [2]   # 2 đơn vị → MỘT lượt gửi nền (không mỗi đơn vị một luồng)
    assert sorted(m["to"] for m in sent["mail"]) == [["au_pur_a@example.vn"], ["au_pur_b@example.vn"]]


def test_da_doc_tinh_theo_tung_nguoi(env, sent) -> None:
    """Lãnh đạo mở thẻ KHÔNG làm tắt "chưa đọc" của CV Thu mua; Tập đoàn phản hồi → cả hai chưa đọc."""
    _announce(env, ["leader", "purchase"], "Đọc riêng từng người")
    tid = _tid(env["lead"], "Đọc riêng từng người")
    assert (_unread(env["lead"]), _unread(env["pur"]), _unread(env["sto"])) == (1, 1, 0)

    client.get(f"/api/support/threads/{tid}", headers=env["lead"])
    assert (_unread(env["lead"]), _unread(env["pur"])) == (0, 1)
    assert [x["id"] for x in _rows(env["pur"], unread_only=True)] == [tid]
    assert _rows(env["lead"], unread_only=True) == []
    client.get(f"/api/support/threads/{tid}", headers=env["pur"])
    assert _unread(env["pur"]) == 0

    sent["push"].clear()
    client.post(f"/api/support/threads/{tid}/reply", json={"body": "Bổ sung"}, headers=env["hq"])
    assert (_unread(env["lead"]), _unread(env["pur"])) == (1, 1)
    assert sorted(sent["push"][0]["to"]) == ["au_lead_a", "au_pur_a"]
    assert sent["push"][0]["title"] == support_notify.PUSH_HQ_REPLY

    sent["push"].clear()
    assert client.post(f"/api/support/threads/{tid}/reply", json={"body": "Đã rõ"},
                       headers=env["pur"]).status_code == 200
    hq_push = sent["push"][0]
    assert "au_hq" in hq_push["to"] and "au_pur_a" not in hq_push["to"]
    assert hq_push["title"] == f"Đơn vị {UNIT_A} phản hồi"


def test_cv_mo_yeu_cau_nguoi_nhan_la_lanh_dao_va_loai_cua_minh(env, sent) -> None:
    """CV Thu mua gửi yêu cầu → thẻ cho lãnh đạo + Thu mua; lãnh đạo gửi → chỉ lãnh đạo."""
    r = client.post("/api/support/requests", json={"company": UNIT_A, "subject": "Hỏi cách nhập",
                                                   "body": "Cần hướng dẫn."}, headers=env["pur"])
    assert r.status_code == 200
    tid = r.json()["thread_id"]
    thread = client.get(f"/api/support/threads/{tid}", headers=env["lead"]).json()["thread"]
    assert thread["audience"] == ["leader", "purchase"]
    assert client.get(f"/api/support/threads/{tid}", headers=env["sto"]).status_code == 404
    push = sent["push"][0]
    assert "au_hq" in push["to"] and "au_pur_a" not in push["to"]
    assert push["title"] == f"Đơn vị {UNIT_A} gửi yêu cầu" and push["url"] == f"/ho-tro/{tid}"
    # Người gửi tự khép được yêu cầu của mình; gửi hộ đơn vị khác thì bị chặn.
    assert client.put(f"/api/support/threads/{tid}/status", json={"status": "closed"},
                      headers=env["pur"]).status_code == 200
    assert client.post("/api/support/requests", json={"company": UNIT_B, "subject": "x"},
                       headers=env["pur"]).status_code == 403

    r2 = client.post("/api/support/requests", json={"company": UNIT_A, "subject": "Lãnh đạo hỏi"},
                     headers=env["lead"])
    tid2 = r2.json()["thread_id"]
    assert client.get(f"/api/support/threads/{tid2}", headers=env["lead"]).json()["thread"][
        "audience"] == ["leader"]
    assert client.get(f"/api/support/threads/{tid2}", headers=env["pur"]).status_code == 404


def test_tai_dinh_kem_chan_ngoai_nhom_nguoi_nhan(env, sent) -> None:
    """File của thẻ ["purchase"]: CV Thu mua tải được; lãnh đạo / CV Tồn kho cùng đơn vị → 404."""
    up = client.post("/api/support/file", files={"file": ("bang-gia.pdf", b"%PDF-1.4 thu", "application/pdf")},
                     headers=env["hq"])
    assert up.status_code == 200
    name = up.json()["file"]
    try:
        client.post("/api/support/announcements",
                    json={"subject": "Gửi bảng giá", "scope": "units", "units": [UNIT_A],
                          "audience": ["purchase"], "files": [up.json()]}, headers=env["hq"])
        assert client.get(f"/api/support/file/{name}", headers=env["pur"]).status_code == 200
        for who in ("lead", "sto", "pur_b"):
            assert client.get(f"/api/support/file/{name}", headers=env[who]).status_code == 404, who
        assert client.get(f"/api/support/file/{name}", headers=env["hq"]).status_code == 200
    finally:
        store.path_for(name).unlink(missing_ok=True)


def test_lich_nhac_mang_nhom_nguoi_nhan(env, sent) -> None:
    """Lịch nhắc lưu `audience` (mặc định lãnh đạo) và truyền xuống thẻ khi phát."""
    future = (support_reminder_repo.now() + timedelta(days=30)).isoformat()
    body = {"title": "Nhắc kiểm kê kho", "scope": "units", "units": [UNIT_A],
            "repeat_rule": "once", "next_at": future, "enabled": False}
    bad = client.post("/api/support/reminders", json={**body, "audience": []}, headers=env["hq"])
    assert bad.status_code == 400 and "nhóm người nhận" in bad.json()["detail"]

    plain = client.post("/api/support/reminders", json=body, headers=env["hq"]).json()
    assert plain["audience"] == ["leader"]
    rid = client.post("/api/support/reminders", json={**body, "audience": ["stock"]},
                      headers=env["hq"]).json()["id"]
    rows = client.get("/api/support/reminders", headers=env["hq"]).json()["rows"]
    assert next(r for r in rows if r["id"] == rid)["audience"] == ["stock"]
    upd = client.put(f"/api/support/reminders/{rid}", json={**body, "audience": ["stock", "purchase"]},
                     headers=env["hq"])
    assert upd.json()["audience"] == ["purchase", "stock"]

    assert client.post(f"/api/support/reminders/{rid}/run", headers=env["hq"]).json()["threads"] == 1
    tid = _tid(env["sto"], "Nhắc kiểm kê kho")
    assert tid and _tid(env["pur"], "Nhắc kiểm kê kho") == tid
    assert _tid(env["lead"], "Nhắc kiểm kê kho") is None
    assert sorted(sent["push"][0]["to"]) == ["au_pur_a", "au_sto_a"]
    assert sent["push"][0]["title"] == support_notify.PUSH_REMINDER


def test_chon_nhom_nguoi_nhan_bat_buoc(env) -> None:
    for audience in ([], ["bogus"]):
        r = _announce(env, audience, "Không người nhận")
        assert r.status_code == 400 and "nhóm người nhận" in r.json()["detail"]
    assert _tid(env["hq"], "Không người nhận") is None


def test_tai_khoan_nhap_lieu_chua_gan_don_vi_bi_chan(env) -> None:
    assert client.get("/api/support/context", headers=_bearer("au_nounit")).status_code == 403


def test_loc_nguoi_nhan_theo_nhom(env) -> None:
    def names(aud):
        return {u["username"] for u in support_notify.unit_users(UNIT_A, aud)}

    assert names(None) == names(["leader"]) == {"au_lead_a"}
    assert names(["purchase"]) == {"au_pur_a"}
    assert names(["leader", "stock"]) == {"au_lead_a", "au_sto_a"}
    assert set(support_notify.unit_recipients(UNIT_A, ["purchase", "stock"])) == {
        "au_pur_a@example.vn", "au_sto_a@example.vn"}
    _sql("UPDATE app_user SET is_active = false WHERE username = 'au_sto_a'")
    try:
        assert names(["stock"]) == set()
    finally:
        _sql("UPDATE app_user SET is_active = true WHERE username = 'au_sto_a'")


def test_push_van_gui_khi_chua_cau_hinh_smtp(env, sent, monkeypatch) -> None:
    """Chưa khai SMTP: email báo lỗi êm, push vẫn đi đúng người."""
    results = []
    monkeypatch.setattr(mailer, "_cfg", lambda key, fallback="": fallback)
    monkeypatch.setattr(mailer, "send_async", lambda to, s, b: results.append(mailer.send(to, s, b)))
    _announce(env, ["purchase"], "Không có SMTP")
    assert results and results[0][0] is False
    assert [p["to"] for p in sent["push"]] == [["au_pur_a"]]


def test_de_nghi_sua_push_nguoi_duyet_va_nguoi_gui(env, sent) -> None:
    req = {"id": 987654321, "company": UNIT_A, "title": "Sửa giá ngày 01/09", "reason": "Nhập nhầm",
           "requested_by": "au_pur_a", "requested_by_name": None, "status": "approved",
           "review_note": "Đồng ý", "dates": [], "unlocked": []}
    edit_request_notify.notify_submitted(req, replaced=False)
    push = sent["push"][-1]
    assert "admin" in push["to"] and "au_pur_a" not in push["to"]
    assert push["url"].startswith("/duyet-de-nghi-sua")
    edit_request_notify.notify_result(req)
    push = sent["push"][-1]
    assert push["to"] == ["au_pur_a"] and push["url"] == "/de-nghi-sua"
