"""Test API phương án nháp + bản nháp tờ trình (CRUD, phân quyền, escape HTML) và vòng chat của
Trợ lý với phương án (LLM giả — không gọi mạng)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import assistant_service, user_repo
from app.services.assistant_tools import proposal_tools
from tests import floor_proposal_env as env

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)
SVR10 = "SVR 10 / CSR 10"
USERS = {"fp_ast": ["assistant"], "fp_none": [], "fp_exec": None}


def _bearer(u: str, p: str) -> dict[str, str]:
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def h():
    env.seed()
    user_repo.seed_admin()
    admin = _bearer("admin", "admin")
    for u, perms in USERS.items():
        client.delete(f"/api/users/{u}", headers=admin)
        body = {"username": u, "password": "pass123", "full_name": u,
                "role": "executive" if perms is None else "editor", "permissions": perms or []}
        assert client.post("/api/users", json=body, headers=admin).status_code == 200
    yield {"admin": admin, **{u: _bearer(u, "pass123") for u in USERS}}
    for u in USERS:
        client.delete(f"/api/users/{u}", headers=admin)
    env.clear()


def _row(prop: dict, grade: str = SVR10) -> dict:
    return next(r for r in prop["rows"] if r["grade"] == grade)


def test_apply_and_preview_endpoints(h) -> None:
    p = env.proposal()
    r = client.post("/api/floor-proposal/apply", headers=h["fp_ast"], json={
        "proposal": p, "changes": [{"grades": [SVR10], "op": "step", "value": 2}]})
    assert r.status_code == 200, r.text
    new = r.json()["proposal"]
    assert _row(new)["fob"] == _row(p)["fob"] + 10 and _row(new)["origin"] == "manual"
    bad = client.post("/api/floor-proposal/apply", headers=h["fp_ast"], json={
        "proposal": p, "changes": [{"grades": [SVR10], "op": "set", "value": 99_000_000}]})
    assert bad.status_code == 400 and "khoảng hợp lý" in bad.json()["detail"]
    html = client.post("/api/floor-proposal/preview", headers=h["fp_ast"], json={
        "proposal": new, "n1": ["<script>alert(1)</script> thị trường tăng"]})
    assert html.status_code == 200 and "TỜ TRÌNH" in html.text
    assert "<script>" not in html.text and "&lt;script&gt;" in html.text   # diễn giải sửa tay bị escape
    assert "2.095" in html.text                                             # khối 3 = số phương án
    assert client.post("/api/floor-proposal/apply", headers=h["fp_none"], json={
        "proposal": p, "changes": [{"op": "undo"}]}).status_code == 403


def test_draft_crud_and_permissions(h) -> None:
    p = env.proposal()
    r = client.post("/api/floor-proposal/drafts", headers=h["admin"],
                    json={"source": "assistant", "proposal": p, "note": "thử"})
    assert r.status_code == 201, r.text
    d = r.json()
    try:
        assert d["as_of"] == env.AS_OF and d["title"].startswith("Dự kiến giá sàn lần")
        assert d["doc"]["n1"] and d["proposal"]["rows"][0]["label"] == "CV50"
        lst = client.get("/api/floor-proposal/drafts?page=1&page_size=5", headers=h["admin"]).json()
        assert lst["page_size"] == 5 and lst["total"] >= 1 and len(lst["items"]) <= 5
        assert lst["items"][0]["id"] == d["id"] and lst["items"][0]["headline"].startswith("SVR10")
        # Sửa tay: số + diễn giải; tờ trình của bản đã lưu phản ánh đúng.
        moved = client.post("/api/floor-proposal/apply", headers=h["admin"], json={
            "proposal": d["proposal"], "changes": [{"grades": [SVR10], "op": "set", "value": 2105}]}).json()
        up = client.put(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"], json={
            "title": "Nháp lần sau", "proposal": moved["proposal"], "n1": ["Đoạn 1 sửa tay", "  "],
            "n2": ["Tồn kho 58.786 tấn"]})
        assert up.status_code == 200, up.text
        assert up.json()["doc"]["n1"] == ["Đoạn 1 sửa tay"] and up.json()["title"] == "Nháp lần sau"
        doc = client.get(f"/api/floor-proposal/drafts/{d['id']}/html", headers=h["admin"]).text
        assert "Đoạn 1 sửa tay" in doc and "2.105" in doc
        # Không đổi được ngày tờ trình của bản nháp (ảnh chụp thị trường gắn với ngày đó).
        other = {**moved["proposal"], "as_of": "1990-01-03"}
        assert client.put(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"], json={
            "title": "x", "proposal": other}).status_code == 400
        # Chỉ có quyền Trợ lý: dùng phương án được, KHÔNG xem/lưu bản nháp.
        assert client.get("/api/floor-proposal/drafts", headers=h["fp_ast"]).status_code == 403
        assert client.post("/api/floor-proposal/drafts", headers=h["fp_ast"],
                           json={"proposal": p}).status_code == 403
        assert client.post("/api/floor-proposal/preview", headers=h["fp_ast"],
                           json={"proposal": p, "draft_id": d["id"]}).status_code == 403
        # Lãnh đạo Tập đoàn: xem được, không ghi được; phương án (chỉ tính) vẫn dùng được.
        assert client.get(f"/api/floor-proposal/drafts/{d['id']}", headers=h["fp_exec"]).status_code == 200
        assert client.delete(f"/api/floor-proposal/drafts/{d['id']}", headers=h["fp_exec"]).status_code == 403
        assert client.post("/api/floor-proposal/apply", headers=h["fp_exec"], json={
            "proposal": p, "changes": [{"grades": ["all"], "op": "step", "value": 1}]}).status_code == 200
    finally:
        assert client.delete(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"]).status_code == 200
    assert client.get(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"]).status_code == 404


class _FakeLLM:
    """OpenAI giả: lượt 1 gọi adjust_floor_proposal, lượt 2 trả lời. Ghi lại messages đã nhận."""

    def __init__(self, changes: list[dict]) -> None:
        self.seen: list[list[dict]] = []
        self._changes = changes
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.seen.append(kw["messages"])
        if len(self.seen) == 1:
            call = SimpleNamespace(id="c1", function=SimpleNamespace(
                name="adjust_floor_proposal", arguments=json.dumps({"changes": self._changes})))
            msg = SimpleNamespace(tool_calls=[call], content="")
        else:
            msg = SimpleNamespace(tool_calls=None, content="Đã tăng SVR 10 / CSR 10 thêm 1 bước.")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _fake(monkeypatch, changes: list[dict]) -> _FakeLLM:
    fake = _FakeLLM(changes)
    monkeypatch.setattr(assistant_service.llm, "openai_client", lambda: (fake, "fake"))
    real = assistant_service.config_repo.get_value
    monkeypatch.setattr(assistant_service.config_repo, "get_value",
                        lambda k, d=None: "openai" if k == "LLM_PROVIDER" else ("" if k == "ASSISTANT_PACKS" else real(k, d)))
    return fake


def test_chat_round_trip_updates_session_proposal(h, monkeypatch) -> None:
    fake = _fake(monkeypatch, [{"grades": [SVR10], "op": "step", "value": 1}])
    p = env.proposal()
    r = client.post("/api/assistant/chat", headers=h["fp_ast"], json={
        "messages": [{"role": "user", "content": "tăng mủ 10 lên tí xíu"}], "proposal": p})
    assert r.status_code == 200, r.text
    out = r.json()
    assert _row(out["proposal"])["fob"] == _row(p)["fob"] + 5 and _row(out["proposal"])["origin"] == "ai"
    assert out["artifacts"] and out["artifacts"][0]["type"] == "table"
    # Lượt đầu, LLM đã được xem phương án đang mở (số định dạng sẵn), kèm nhãn "không phải giá chính thức".
    block = next(m["content"] for m in fake.seen[0] if m["role"] == "system" and "PHƯƠNG ÁN" in m["content"][:40])
    assert "KHÔNG phải giá chính thức" in block and "SVR 10 / CSR 10: FOB 2.085 USD/tấn" in block
    # Không chỉnh gì ⇒ proposal trả về null (frontend giữ nguyên bản đang có).
    monkeypatch.setattr(assistant_service.llm, "openai_client", lambda: (SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(tool_calls=None, content="ok"))])))), "fake"))
    r2 = client.post("/api/assistant/chat", headers=h["fp_ast"], json={
        "messages": [{"role": "user", "content": "chào"}], "proposal": out["proposal"]})
    assert r2.json()["proposal"] is None


def test_data_mode_hides_model_and_blocks_reset_to_model(h) -> None:
    p = env.proposal()
    assert "mức mô hình" not in proposal_tools.context_block(p, "data")
    assert "mức mô hình" in proposal_tools.context_block(p, "model")
    ctx = {"proposal": p, "advice": "data", "changed": False}
    res = proposal_tools.TOOLS["adjust_floor_proposal"]["run"](
        {"changes": [{"grades": ["all"], "op": "reset_model"}]}, ctx)
    assert "error" in res["summary"] and not ctx["changed"]
    ok = proposal_tools.TOOLS["adjust_floor_proposal"]["run"](
        {"changes": [{"grades": ["rss"], "op": "percent", "value": -1}]}, ctx)
    assert ctx["changed"] and ok["summary"]["da_lam"] and all("mức mô hình" not in x for x in ok["summary"]["dong_da_doi"])


def test_save_conflict_empty_proposal_and_replace_guard(h) -> None:
    p = env.proposal()
    d = client.post("/api/floor-proposal/drafts", headers=h["admin"], json={"proposal": p}).json()
    try:
        body = {"title": "A", "proposal": d["proposal"], "base_updated_at": d["updated_at"]}
        first = client.put(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"], json=body)
        assert first.status_code == 200
        if first.json()["updated_at"] != d["updated_at"]:      # cùng một giây thì mốc trùng — bỏ qua
            stale = client.put(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"], json=body)
            assert stale.status_code == 409 and "tải lại" in stale.json()["detail"]
        assert client.put(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"],
                          json={"title": "A", "proposal": {}}).status_code == 400
    finally:
        client.delete(f"/api/floor-proposal/drafts/{d['id']}", headers=h["admin"])
    edited, _, _ = proposal_tools.ops.apply(p, [{"grades": [SVR10], "op": "step", "value": 1}])
    ctx = {"proposal": edited, "advice": "model", "changed": False}
    res = proposal_tools.TOOLS["create_floor_proposal"]["run"]({}, ctx)
    assert "error" in res["summary"] and "MẤT" in res["summary"]["error"] and ctx["proposal"] is edited
