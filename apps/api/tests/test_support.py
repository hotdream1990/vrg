"""Test Hỗ trợ & Thông báo · Nhắc lịch.

Điểm phải khoá chặt nhất: **đơn vị không thấy tin và phản hồi của đơn vị khác** — kể cả khi
Tập đoàn gửi CÙNG MỘT thông báo cho cả hai (cùng `batch_id`).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import support_reminder_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)

UNIT_A, UNIT_B = "_zz_sp_don_vi_a", "_zz_sp_don_vi_b"
ACCOUNTS = ("sp_lead_a", "sp_lead_b", "sp_hq", "sp_none", "sp_member")


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(username: str, password: str) -> dict[str, str]:
    token = client.post("/api/auth/login",
                        json={"username": username, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin() -> dict[str, str]:
    return _bearer("admin", "admin")


def _cleanup(h: dict[str, str]) -> None:
    for u in ACCOUNTS:
        client.delete(f"/api/users/{u}", headers=h)
    for unit in (UNIT_A, UNIT_B):
        client.delete(f"/api/member-units/{unit}", headers=h)


@pytest.fixture
def env():
    """2 đơn vị + 2 lãnh đạo + 1 chuyên viên có quyền + 1 không quyền + 1 tài khoản nhập liệu."""
    h = _admin()
    _cleanup(h)
    for unit in (UNIT_A, UNIT_B):
        client.post("/api/member-units", json={"name": unit}, headers=h)
    client.post("/api/users", json={"username": "sp_lead_a", "password": "pass123",
                                    "role": "leader", "member_units": [UNIT_A]}, headers=h)
    client.post("/api/users", json={"username": "sp_lead_b", "password": "pass123",
                                    "role": "leader", "member_units": [UNIT_B]}, headers=h)
    client.post("/api/users", json={"username": "sp_hq", "password": "pass123",
                                    "role": "editor", "permissions": ["support"]}, headers=h)
    client.post("/api/users", json={"username": "sp_none", "password": "pass123",
                                    "role": "editor"}, headers=h)
    client.post("/api/users", json={"username": "sp_member", "password": "pass123",
                                    "role": "member", "member_units": [UNIT_A]}, headers=h)
    yield {
        "admin": h,
        "a": _bearer("sp_lead_a", "pass123"),
        "b": _bearer("sp_lead_b", "pass123"),
        "hq": _bearer("sp_hq", "pass123"),
        "none": _bearer("sp_none", "pass123"),
        "member": _bearer("sp_member", "pass123"),
    }
    _cleanup(h)


def test_vai_tro_lanh_dao_duoc_gan_don_vi(env) -> None:
    """Lãnh đạo đơn vị phải được gán đơn vị; tài khoản nhập liệu và người không quyền bị chặn."""
    ctx = client.get("/api/support/context", headers=env["a"]).json()
    assert ctx["side"] == "unit" and ctx["units"] == [UNIT_A]

    ctx_hq = client.get("/api/support/context", headers=env["hq"]).json()
    assert ctx_hq["side"] == "hq" and UNIT_A in ctx_hq["units"]

    # `member` (nhập liệu của chính đơn vị đó) và editor không quyền đều KHÔNG vào được hộp thư.
    assert client.get("/api/support/context", headers=env["member"]).status_code == 403
    assert client.get("/api/support/context", headers=env["none"]).status_code == 403

    # Tạo tài khoản lãnh đạo mà không chọn đơn vị → chặn ngay từ lúc tạo.
    r = client.post("/api/users", json={"username": "sp_lead_x", "password": "pass123",
                                        "role": "leader", "member_units": []}, headers=env["admin"])
    assert r.status_code == 400


def test_thong_bao_gui_nhom_khong_lo_cheo_don_vi(env) -> None:
    """Gửi 1 thông báo cho CẢ HAI đơn vị → mỗi đơn vị 1 luồng riêng, không đọc được của nhau."""
    r = client.post("/api/support/announcements",
                    json={"subject": "Nộp báo cáo tháng 8", "body": "Đề nghị các đơn vị nộp trước 05/09.",
                          "scope": "units", "units": [UNIT_A, UNIT_B]}, headers=env["hq"])
    assert r.status_code == 200 and r.json()["threads"] == 2

    la = client.get("/api/support/threads", headers=env["a"]).json()
    lb = client.get("/api/support/threads", headers=env["b"]).json()
    assert [x["company"] for x in la["rows"]] == [UNIT_A]
    assert [x["company"] for x in lb["rows"]] == [UNIT_B]
    id_a, id_b = la["rows"][0]["id"], lb["rows"][0]["id"]
    assert id_a != id_b                       # 2 luồng khác nhau, không dùng chung
    assert la["rows"][0]["unread"] is True     # đơn vị chưa đọc → hiện chưa đọc

    # Đơn vị A KHÔNG mở được luồng của đơn vị B (kể cả biết id) — và ngược lại.
    assert client.get(f"/api/support/threads/{id_b}", headers=env["a"]).status_code == 404
    assert client.get(f"/api/support/threads/{id_a}", headers=env["b"]).status_code == 404

    # A phản hồi → B tuyệt đối không thấy phản hồi đó ở đâu.
    assert client.post(f"/api/support/threads/{id_a}/reply",
                       json={"body": "Đơn vị A đã nhận, sẽ nộp đúng hạn."},
                       headers=env["a"]).status_code == 200
    detail_b = client.get(f"/api/support/threads/{id_b}", headers=env["b"]).json()
    assert all("Đơn vị A" not in m["body"] for m in detail_b["messages"])
    assert len(detail_b["messages"]) == 1

    # Mở luồng ra là đánh dấu đã đọc cho chính bên đang xem.
    client.get(f"/api/support/threads/{id_a}", headers=env["a"])
    assert client.get("/api/support/unread", headers=env["a"]).json()["count"] == 0

    # Tập đoàn thấy cả hai + phản hồi của A; gom theo đợt gửi thì 2 luồng về 1 dòng.
    hq_list = client.get("/api/support/threads?kind=announce", headers=env["hq"]).json()
    assert {x["company"] for x in hq_list["rows"]} >= {UNIT_A, UNIT_B}
    batches = client.get("/api/support/batches", headers=env["hq"]).json()
    top = batches["rows"][0]
    assert top["subject"] == "Nộp báo cáo tháng 8" and top["unit_count"] == 2

    for tid in (id_a, id_b):
        client.delete(f"/api/support/threads/{tid}", headers=env["admin"])


def test_gui_trung_ten_don_vi_chi_tao_mot_luong(env) -> None:
    """Client gửi trùng tên đơn vị → vẫn chỉ 1 luồng cho đơn vị đó (không vỡ, không gửi 2 tin)."""
    r = client.post("/api/support/announcements",
                    json={"subject": "Thông báo gửi trùng tên", "body": "x",
                          "scope": "units", "units": [UNIT_A, UNIT_A]}, headers=env["hq"])
    assert r.status_code == 200 and r.json()["threads"] == 1

    rows = [x for x in client.get("/api/support/threads", headers=env["a"]).json()["rows"]
            if x["subject"] == "Thông báo gửi trùng tên"]
    assert len(rows) == 1
    client.delete(f"/api/support/threads/{rows[0]['id']}", headers=env["admin"])


def test_don_vi_gui_yeu_cau_len_tap_doan(env) -> None:
    """Lãnh đạo mở yêu cầu hỗ trợ → Tập đoàn thấy và trả lời được; đơn vị khác không thấy."""
    r = client.post("/api/support/requests",
                    json={"company": UNIT_A, "subject": "Đề nghị hỗ trợ giá sàn",
                          "body": "Đơn vị cần hướng dẫn áp giá sàn lần 12."}, headers=env["a"])
    assert r.status_code == 200
    tid = r.json()["thread_id"]

    # Gửi hộ đơn vị KHÔNG được gán → 403 (server ép phạm vi, không tin client).
    assert client.post("/api/support/requests",
                       json={"company": UNIT_B, "subject": "x", "body": "y"},
                       headers=env["a"]).status_code == 403

    assert client.get(f"/api/support/threads/{tid}", headers=env["b"]).status_code == 404

    hq = client.get("/api/support/threads?kind=request", headers=env["hq"]).json()
    assert any(x["id"] == tid and x["unread"] for x in hq["rows"])

    assert client.post(f"/api/support/threads/{tid}/reply",
                       json={"body": "Ban TTKD đã tiếp nhận."}, headers=env["hq"]).status_code == 200
    msgs = client.get(f"/api/support/threads/{tid}", headers=env["a"]).json()["messages"]
    assert [m["side"] for m in msgs] == ["unit", "hq"]

    # Đóng luồng rồi lọc theo trạng thái.
    assert client.put(f"/api/support/threads/{tid}/status", json={"status": "closed"},
                      headers=env["hq"]).status_code == 200
    closed = client.get("/api/support/threads?status=closed", headers=env["a"]).json()
    assert any(x["id"] == tid for x in closed["rows"])

    client.delete(f"/api/support/threads/{tid}", headers=env["admin"])


def test_chi_xem_thi_khong_gui_duoc(env) -> None:
    """Chuyên viên chỉ có mức Xem: đọc hộp thư được, gửi/phản hồi thì bị chặn."""
    h = env["admin"]
    client.put("/api/users/sp_hq", json={"permissions": ["support:view"]}, headers=h)
    view_only = _bearer("sp_hq", "pass123")
    assert client.get("/api/support/threads", headers=view_only).status_code == 200
    assert client.post("/api/support/announcements",
                       json={"subject": "x", "scope": "all"}, headers=view_only).status_code == 403


def test_nhac_lich_phat_thong_bao_va_doi_moc(env) -> None:
    """Tới hạn → phát thông báo cho đúng phạm vi rồi dời mốc sang chu kỳ sau."""
    past = (support_reminder_repo.now() - timedelta(minutes=1)).isoformat()
    r = client.post("/api/support/reminders",
                    json={"title": "Nhắc nộp số liệu tuần", "body": "Đề nghị đơn vị cập nhật.",
                          "scope": "units", "units": [UNIT_A], "repeat_rule": "weekly",
                          "next_at": past, "enabled": True}, headers=env["hq"])
    assert r.status_code == 200
    rid = r.json()["id"]
    before_next = datetime.fromisoformat(r.json()["next_at"])

    result = support_reminder_repo.run_due()
    assert result["reminders"] >= 1 and result["threads"] >= 1

    rows = client.get("/api/support/threads?kind=reminder", headers=env["a"]).json()["rows"]
    assert any(x["subject"] == "Nhắc nộp số liệu tuần" for x in rows)
    # Đơn vị B ngoài phạm vi → không nhận.
    assert not any(x["subject"] == "Nhắc nộp số liệu tuần"
                   for x in client.get("/api/support/threads", headers=env["b"]).json()["rows"])

    after = support_reminder_repo.get_reminder(rid)
    assert after["next_at"] > before_next and after["enabled"] is True
    # Chạy lại ngay: lịch đã dời mốc nên KHÔNG phát lần hai.
    assert support_reminder_repo.run_due()["reminders"] == 0

    for row in rows:
        client.delete(f"/api/support/threads/{row['id']}", headers=env["admin"])
    assert client.delete(f"/api/support/reminders/{rid}", headers=env["hq"]).status_code == 200


def test_lich_mot_lan_tu_tat_sau_khi_phat(env) -> None:
    """Chu kỳ `once`: phát xong là tắt, không phát lại."""
    past = (support_reminder_repo.now() - timedelta(minutes=1)).isoformat()
    rid = client.post("/api/support/reminders",
                      json={"title": "Nhắc họp giao ban", "scope": "units", "units": [UNIT_B],
                            "repeat_rule": "once", "next_at": past},
                      headers=env["hq"]).json()["id"]
    support_reminder_repo.run_due()
    assert support_reminder_repo.get_reminder(rid)["enabled"] is False

    rows = client.get("/api/support/threads?kind=reminder", headers=env["b"]).json()["rows"]
    for row in rows:
        client.delete(f"/api/support/threads/{row['id']}", headers=env["admin"])
    client.delete(f"/api/support/reminders/{rid}", headers=env["hq"])


def test_nhac_lich_chi_danh_cho_tap_doan(env) -> None:
    """Lãnh đạo đơn vị không đụng được vào lịch nhắc."""
    assert client.get("/api/support/reminders", headers=env["a"]).status_code == 403
    assert client.post("/api/support/reminders",
                       json={"title": "x", "next_at": support_reminder_repo.now().isoformat()},
                       headers=env["a"]).status_code == 403


def test_moc_phat_ke_tiep_theo_chu_ky() -> None:
    """Chu kỳ tháng phải giữ được ngày cuối tháng thay vì trượt sang tháng sau."""
    base = datetime(2026, 1, 31, 8, 0, tzinfo=support_reminder_repo.TZ)
    assert support_reminder_repo.next_after(base, "daily").day == 1
    assert support_reminder_repo.next_after(base, "weekly").month == 2
    monthly = support_reminder_repo.next_after(base, "monthly")
    assert (monthly.month, monthly.day) == (2, 28)
    assert support_reminder_repo.next_after(base, "once") is None


def test_the_khep_lai_la_khep_han_phai_mo_the_moi(env) -> None:
    """MỖI THẺ = MỘT TRƯỜNG HỢP (chốt 29/08/2026): khép rồi thì không ai nhắn thêm được nữa.

    Trước đây phản hồi vào thẻ đã đóng sẽ TỰ MỞ LẠI thẻ — một thẻ gánh nhiều việc, nhìn vào không
    còn biết trường hợp nào đã xong.
    """
    r = client.post("/api/support/requests",
                    json={"company": UNIT_A, "subject": "Sự việc thứ nhất",
                          "body": "Đề nghị Ban hỗ trợ."}, headers=env["a"])
    tid = r.json()["thread_id"]
    assert client.put(f"/api/support/threads/{tid}/status", json={"status": "closed"},
                      headers=env["hq"]).status_code == 200

    # Cả hai bên đều không phản hồi thêm được vào thẻ đã khép.
    for who in ("a", "hq"):
        rep = client.post(f"/api/support/threads/{tid}/reply",
                          json={"body": "nói thêm"}, headers=env[who])
        assert rep.status_code == 409, f"{who} vẫn nhắn được vào thẻ đã khép ({rep.status_code})"

    # Và thẻ vẫn ở trạng thái đã khép, số tin không đổi.
    detail = client.get(f"/api/support/threads/{tid}", headers=env["hq"]).json()
    assert detail["thread"]["status"] == "closed"
    assert len(detail["messages"]) == 1

    # Việc mới → mở THẺ MỚI, thẻ cũ để nguyên.
    r2 = client.post("/api/support/requests",
                     json={"company": UNIT_A, "subject": "Sự việc thứ hai",
                           "body": "Việc khác."}, headers=env["a"])
    assert r2.status_code == 200 and r2.json()["thread_id"] != tid

    for t in (tid, r2.json()["thread_id"]):
        client.delete(f"/api/support/threads/{t}", headers=env["admin"])
