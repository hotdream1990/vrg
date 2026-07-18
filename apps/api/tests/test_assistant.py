"""Test Trợ lý AI: các tool trả số liệu thật + phân quyền cap `assistant`.
Không gọi LLM thật (cần key/mạng) — chỉ kiểm tool layer + hàng rào quyền."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.db import db_healthy
from app.main import app
from app.services import assistant_tools, user_repo

pytestmark = pytest.mark.skipif(not db_healthy(), reason="DB không sẵn sàng")

client = TestClient(app)


@pytest.fixture(autouse=True)
def _seed():
    user_repo.seed_admin()


def _bearer(u: str, p: str) -> dict[str, str]:
    t = client.post("/api/auth/login", json={"username": u, "password": p}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_tools_return_structured_data() -> None:
    # No-arg tool chạy được, trả dict có summary; artifact (nếu có) đúng khuôn.
    for name in ("get_exchange_prices", "get_floor_prices", "get_inventory_trend", "get_market_quote"):
        res = assistant_tools.run_tool(name, {})
        assert isinstance(res.get("summary"), dict), name
        art = res.get("artifact")
        if art:
            assert art["type"] in ("table", "line") and "title" in art, name
    # openai_tools schema hợp lệ (mỗi tool có name + parameters).
    schemas = assistant_tools.openai_tools()
    assert schemas and all(s["type"] == "function" and s["function"]["name"] for s in schemas)
    # tên tool lạ → báo lỗi gọn, không ném.
    assert "error" in assistant_tools.run_tool("khong_ton_tai", {})["summary"]


def test_assistant_cap_gating() -> None:
    h = _admin = _bearer("admin", "admin")
    for u in ("ast_ed", "ast_no", "ast_mem"):
        client.delete(f"/api/users/{u}", headers=h)
    client.post("/api/member-units", json={"name": "_zz_ast"}, headers=h)
    client.post("/api/users", json={"username": "ast_ed", "password": "pass123",
                                    "role": "editor", "permissions": ["assistant"]}, headers=h)
    client.post("/api/users", json={"username": "ast_no", "password": "pass123", "role": "editor"}, headers=h)
    client.post("/api/users", json={"username": "ast_mem", "password": "pass123",
                                    "role": "member", "member_units": ["_zz_ast"]}, headers=h)
    body = {"messages": [{"role": "user", "content": "Giá sàn hiện tại?"}]}

    # Editor KHÔNG có cap + đơn vị thành viên → 403 (chặn trước khi gọi LLM).
    assert client.post("/api/assistant/chat", json=body, headers=_bearer("ast_no", "pass123")).status_code == 403
    assert client.post("/api/assistant/chat", json=body, headers=_bearer("ast_mem", "pass123")).status_code == 403

    # Editor CÓ cap → qua hàng rào (không 403). Tùy cấu hình LLM: 200 (có key) hoặc 400/502.
    assert client.post("/api/assistant/chat", json=body, headers=_bearer("ast_ed", "pass123")).status_code != 403

    for u in ("ast_ed", "ast_no", "ast_mem"):
        client.delete(f"/api/users/{u}", headers=h)
