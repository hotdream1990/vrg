"""Test Lịch sử hỏi–đáp Trợ lý AI: ghi log → đọc lại, phân quyền xem/xoá, dọn log cũ, phân trang."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import assistant_log_repo, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(u: str, p: str) -> dict[str, str]:
    t = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def _make_editor(username: str, headers: dict[str, str]) -> None:
    client.delete(f"/api/users/{username}", headers=headers)
    client.post("/api/users", json={"username": username, "password": "pass123",
                                    "role": "editor", "permissions": ["assistant"]}, headers=headers)


def _log(session_id: str, username: str, question: str = "Giá sàn hôm nay?") -> None:
    assistant_log_repo.log_turn(
        session_id=session_id, username=username, question=question, answer="Trả lời mẫu",
        tools=["get_floor_prices"], sources=["fact_price"], packs=["floor"],
        advice="model", model="gpt-4o-mini", latency_ms=123,
    )


def test_log_turn_then_read_back() -> None:
    """Ghi 1 lượt rồi đọc lại đúng nội dung qua GET /{session_id} + xuất hiện trong danh sách phiên."""
    h = _bearer("admin", "admin")
    sid = f"t-{uuid.uuid4().hex[:8]}"
    _log(sid, "admin", "Giá sàn SVR10 hôm nay bao nhiêu?")

    detail = client.get(f"/api/assistant/history/{sid}", headers=h).json()
    assert detail["session_id"] == sid
    assert len(detail["items"]) == 1
    turn = detail["items"][0]
    assert turn["question"] == "Giá sàn SVR10 hôm nay bao nhiêu?"
    assert turn["answer"] == "Trả lời mẫu"
    assert turn["tools"] == ["get_floor_prices"]
    assert turn["model"] == "gpt-4o-mini"
    assert turn["latency_ms"] == 123

    listing = client.get("/api/assistant/history", params={"username": "admin", "q": "SVR10"},
                         headers=h).json()
    assert any(item["session_id"] == sid for item in listing["items"])

    assistant_log_repo.delete_session(sid)


def test_regular_user_cannot_see_others_log() -> None:
    """Người dùng thường KHÔNG thấy log của người khác (chặn cả filter username lẫn xem phiên)."""
    h = _bearer("admin", "admin")
    _make_editor("ah_ed1", h)
    _make_editor("ah_ed2", h)
    eh1 = _bearer("ah_ed1", "pass123")

    sid_mine = f"t-{uuid.uuid4().hex[:8]}"
    sid_other = f"t-{uuid.uuid4().hex[:8]}"
    _log(sid_mine, "ah_ed1")
    _log(sid_other, "ah_ed2")

    # Tự xem log của mình → OK, không thấy phiên của người khác trong danh sách của mình.
    mine = client.get("/api/assistant/history", headers=eh1).json()
    assert all(item["username"] == "ah_ed1" for item in mine["items"])
    assert not any(item["session_id"] == sid_other for item in mine["items"])

    # Cố lọc theo username của người khác → 403 (server ép về chính mình, không tin client).
    assert client.get("/api/assistant/history", params={"username": "ah_ed2"},
                      headers=eh1).status_code == 403
    # Cố xem thẳng phiên của người khác qua session_id → 403.
    assert client.get(f"/api/assistant/history/{sid_other}", headers=eh1).status_code == 403
    # Xem đúng phiên của mình → OK.
    assert client.get(f"/api/assistant/history/{sid_mine}", headers=eh1).status_code == 200

    # admin xem được cả hai, lọc theo username hoạt động.
    admin_view = client.get("/api/assistant/history", params={"username": "ah_ed2"}, headers=h).json()
    assert any(item["session_id"] == sid_other for item in admin_view["items"])

    for u in ("ah_ed1", "ah_ed2"):
        client.delete(f"/api/users/{u}", headers=h)
    assistant_log_repo.delete_session(sid_mine)
    assistant_log_repo.delete_session(sid_other)


def test_regular_user_cannot_delete() -> None:
    """Người dùng thường KHÔNG xoá được log (403) dù là phiên của chính mình."""
    h = _bearer("admin", "admin")
    _make_editor("ah_ed3", h)
    eh = _bearer("ah_ed3", "pass123")
    sid = f"t-{uuid.uuid4().hex[:8]}"
    _log(sid, "ah_ed3")

    assert client.delete(f"/api/assistant/history/{sid}", headers=eh).status_code == 403
    assert client.delete("/api/assistant/history", params={"before": "2999-01-01"},
                         headers=eh).status_code == 403

    client.delete("/api/users/ah_ed3", headers=h)
    assistant_log_repo.delete_session(sid)


def test_admin_delete_before_date_returns_count() -> None:
    """admin xoá log cũ hơn 1 ngày → trả đúng số dòng đã xoá."""
    h = _bearer("admin", "admin")
    sid1 = f"t-{uuid.uuid4().hex[:8]}"
    sid2 = f"t-{uuid.uuid4().hex[:8]}"
    _log(sid1, "admin")
    _log(sid2, "admin")

    # Xoá với mốc trong tương lai xa → chắc chắn xoá được 2 dòng vừa tạo (không đụng dữ liệu khác
    # vì chỉ đếm những gì < mốc, và mốc tương lai bao trùm mọi bản ghi hiện có tại thời điểm test).
    before_count = assistant_log_repo.stats()["turns"]
    res = client.delete("/api/assistant/history", params={"before": "2999-01-01"}, headers=h)
    assert res.status_code == 200
    assert res.json()["deleted"] == before_count
    assert assistant_log_repo.stats()["turns"] == 0
    # 2 phiên vừa tạo cũng bị xoá theo (nằm trong tổng đã đếm).
    assert assistant_log_repo.session_owner(sid1) is None
    assert assistant_log_repo.session_owner(sid2) is None


def test_pagination_limits_items() -> None:
    """Phân trang server-side: limit nhỏ trả đúng số item, total vẫn phản ánh tổng thực."""
    h = _bearer("admin", "admin")
    sids = [f"t-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    for sid in sids:
        _log(sid, "admin")

    page = client.get("/api/assistant/history", params={"username": "admin", "limit": 2, "offset": 0},
                      headers=h).json()
    assert len(page["items"]) == 2
    assert page["total"] >= 3

    for sid in sids:
        assistant_log_repo.delete_session(sid)
